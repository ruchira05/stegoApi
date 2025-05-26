import os
import librosa
import numpy as np
import wave
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# Configure logging
logging.basicConfig(
    filename='log.txt',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

# Parameters
TARGET_PEAK = -1.0
MASKING_FACTOR = 0.02
FRAME_SIZE = 1024
HOP_LENGTH = 128
EMBEDDING_DEPTH = 2
TARGET_SR = 44100

def generate_aes_key():
    """Generate a 256-bit AES key"""
    try:
        key = os.urandom(32)  # 256 bits
        logging.debug(f"Generated AES key of length: {len(key)} bytes")
        return key
    except Exception as e:
        logging.error(f"Error generating AES key: {e}")
        raise

def read_aes_key(key_path):
    """Read AES key from file"""
    try:
        with open(key_path, "rb") as key_file:
            key = key_file.read()
        
        if len(key) != 32:
            raise ValueError("Invalid AES key length. Must be 32 bytes (256 bits).")
        
        logging.debug(f"Successfully loaded AES key from {key_path}")
        return key
    except Exception as e:
        logging.error(f"Error loading AES key from {key_path}: {e}")
        raise

def encrypt_data(data, key):
    """Encrypt data using AES-256-CBC"""
    try:
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        combined_bytes = iv + encrypted_data
        logging.debug(f"Data encrypted: original size {len(data)} bytes, encrypted size {len(combined_bytes)} bytes")
        return combined_bytes
    except Exception as e:
        logging.error(f"Error encrypting data: {e}")
        raise

def decrypt_data(encrypted_data, key):
    """Decrypt data using AES-256-CBC"""
    try:
        if len(encrypted_data) < 16:
            raise ValueError("Not enough bytes for IV.")
        
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        logging.debug(f"Data decrypted: encrypted size {len(encrypted_data)} bytes, decrypted size {len(decrypted_data)} bytes")
        return decrypted_data
    except Exception as e:
        logging.error(f"Error decrypting data: {e}")
        raise

def prepare_secret_data(secret_data, key):
    """Encrypt secret data and prepare binary string with length prefix"""
    try:
        if isinstance(secret_data, str):
            secret_data = secret_data.encode('utf-8')
        
        encrypted_data = encrypt_data(secret_data, key)
        secret_bin = ''.join(format(byte, '08b') for byte in encrypted_data)
        length = len(secret_bin)
        length_bin = format(length, '032b')
        total_binary_to_embed = length_bin + secret_bin
        
        logging.debug(f"Secret data prepared: {len(secret_data)} bytes -> {len(total_binary_to_embed)} bits to embed")
        return total_binary_to_embed
    except Exception as e:
        logging.error(f"Error preparing secret data: {e}")
        raise

def embed_secret_in_audio(input_audio_path, secret_data, key, output_audio_path):
    """Embed encrypted secret data into audio file"""
    try:
        logging.debug(f"Starting audio embedding: {input_audio_path} -> {output_audio_path}")
        
        # Load and resample audio
        audio_data, sr = librosa.load(input_audio_path, sr=None)
        if sr != TARGET_SR:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=TARGET_SR)
            sr = TARGET_SR
        
        # Normalize audio
        normalized_audio = audio_data / np.max(np.abs(audio_data)) * (10 ** (TARGET_PEAK / 20))
        
        # Compute STFT and frame energies
        stft = librosa.stft(normalized_audio, n_fft=FRAME_SIZE, hop_length=HOP_LENGTH)
        magnitude = np.abs(stft)
        frame_energies = np.sum(magnitude ** 2, axis=0)
        
        # Compute masking thresholds
        thresholds = np.zeros_like(frame_energies)
        for i in range(1, len(frame_energies)):
            thresholds[i] = max(frame_energies[i] * MASKING_FACTOR, thresholds[i - 1] * 0.9)
        
        # Identify maskable samples
        maskable_samples = []
        for frame_idx, energy in enumerate(frame_energies):
            if energy > thresholds[frame_idx]:
                start_sample = frame_idx * HOP_LENGTH
                end_sample = min(start_sample + HOP_LENGTH, len(normalized_audio))
                maskable_samples.extend(range(start_sample, end_sample))
        
        # Calculate capacity
        max_capacity_bits = len(maskable_samples) * EMBEDDING_DEPTH
        logging.debug(f"Audio capacity: {max_capacity_bits} bits ({max_capacity_bits/8/1024:.2f} KB)")
        
        # Prepare secret data
        secret_bin = prepare_secret_data(secret_data, key)
        
        if len(secret_bin) > max_capacity_bits:
            raise ValueError(f"Not enough capacity. Need {len(secret_bin)} bits, have {max_capacity_bits} bits")
        
        # Convert audio to int16
        audio_int = (normalized_audio * 32767).astype(np.int16)
        frames = bytearray(audio_int.tobytes())
        
        # Embed secret data
        data_index = 0
        embedded_samples = 0
        
        for sample_idx in maskable_samples:
            if data_index < len(secret_bin):
                bits_to_embed = secret_bin[data_index:data_index + EMBEDDING_DEPTH]
                if len(bits_to_embed) < EMBEDDING_DEPTH:
                    bits_to_embed = bits_to_embed.ljust(EMBEDDING_DEPTH, '0')
                
                byte_index = sample_idx * 2
                if byte_index + 2 <= len(frames):
                    sample_bytes = frames[byte_index:byte_index + 2]
                    sample_int = int.from_bytes(sample_bytes, byteorder='little', signed=True)
                    sample_int &= ~(2**EMBEDDING_DEPTH - 1)  # Clear LSBs
                    sample_int |= int(bits_to_embed, 2)
                    frames[byte_index:byte_index + 2] = sample_int.to_bytes(2, byteorder='little', signed=True)
                    data_index += EMBEDDING_DEPTH
                    embedded_samples += 1
            else:
                break
        
        # Write stego audio
        with wave.open(output_audio_path, 'wb') as stego_audio:
            stego_audio.setnchannels(1)
            stego_audio.setsampwidth(2)
            stego_audio.setframerate(sr)
            stego_audio.writeframes(bytes(frames))
        
        logging.debug(f"Embedding completed: {data_index}/{len(secret_bin)} bits embedded in {embedded_samples} samples")
        
        return {
            "success": True,
            "embedded_bits": data_index,
            "total_bits": len(secret_bin),
            "capacity_used": f"{(data_index/max_capacity_bits)*100:.2f}%",
            "output_file": output_audio_path
        }
        
    except Exception as e:
        logging.error(f"Error in embed_secret_in_audio: {e}")
        raise

def extract_secret_from_audio(stego_audio_path, key):
    """Extract and decrypt secret data from stego audio"""
    try:
        logging.debug(f"Starting extraction from: {stego_audio_path}")
        
        # Load stego audio
        audio_data, sr = librosa.load(stego_audio_path, sr=None)
        if sr != TARGET_SR:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=TARGET_SR)
            sr = TARGET_SR
        
        # Normalize audio (same as during embedding)
        normalized_audio = audio_data / np.max(np.abs(audio_data)) * (10 ** (TARGET_PEAK / 20))
        
        # Compute STFT and frame energies (same as during embedding)
        stft = librosa.stft(normalized_audio, n_fft=FRAME_SIZE, hop_length=HOP_LENGTH)
        magnitude = np.abs(stft)
        frame_energies = np.sum(magnitude ** 2, axis=0)
        
        # Compute masking thresholds (same as during embedding)
        thresholds = np.zeros_like(frame_energies)
        for i in range(1, len(frame_energies)):
            thresholds[i] = max(frame_energies[i] * MASKING_FACTOR, thresholds[i - 1] * 0.9)
        
        # Identify maskable samples (same as during embedding)
        maskable_samples = []
        for frame_idx, energy in enumerate(frame_energies):
            if energy > thresholds[frame_idx]:
                start_sample = frame_idx * HOP_LENGTH
                end_sample = min(start_sample + HOP_LENGTH, len(normalized_audio))
                maskable_samples.extend(range(start_sample, end_sample))
        
        # Convert audio to int16 (same format as embedding)
        audio_int = (normalized_audio * 32767).astype(np.int16)
        frames = bytearray(audio_int.tobytes())
        
        # Extract binary data
        extracted_bin = ""
        extracted_samples = 0
        
        for sample_idx in maskable_samples:
            byte_index = sample_idx * 2
            if byte_index + 2 <= len(frames):
                sample_bytes = frames[byte_index:byte_index + 2]
                sample_int = int.from_bytes(sample_bytes, byteorder='little', signed=True)
                lsb_bits = sample_int & (2**EMBEDDING_DEPTH - 1)  # Extract LSBs
                extracted_bin += format(lsb_bits, f'0{EMBEDDING_DEPTH}b')
                extracted_samples += 1
        
        # Extract length (first 32 bits)
        if len(extracted_bin) < 32:
            raise ValueError("Not enough bits extracted to read data length.")
        
        length_bin = extracted_bin[:32]
        data_length = int(length_bin, 2)
        logging.debug(f"Expected data length: {data_length} bits")
        
        # Extract secret data
        secret_bin = extracted_bin[32:32 + data_length]
        if len(secret_bin) < data_length:
            raise ValueError(f"Incomplete data extracted: got {len(secret_bin)} bits, expected {data_length} bits.")
        
        # Convert binary to bytes
        secret_bytes = bytearray()
        for i in range(0, len(secret_bin), 8):
            byte_bin = secret_bin[i:i + 8]
            if len(byte_bin) == 8:
                secret_bytes.append(int(byte_bin, 2))
        
        # Decrypt data
        decrypted_data = decrypt_data(secret_bytes, key)
        
        logging.debug(f"Extraction completed: {len(secret_bin)} bits extracted from {extracted_samples} samples")
        
        return {
            "success": True,
            "extracted_data": decrypted_data,
            "extracted_bits": len(secret_bin),
            "samples_processed": extracted_samples
        }
        
    except Exception as e:
        logging.error(f"Error in extract_secret_from_audio: {e}")
        raise