import os
import librosa
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import wave

# Parameters
TARGET_PEAK = -1.0
MASKING_FACTOR = 0.02
FRAME_SIZE = 1024
HOP_LENGTH = 128
EMBEDDING_DEPTH = 8

def convert_text_to_binary(text):
    """Convert text to binary string with EOF marker"""
    binary = ''.join(format(ord(c), '08b') for c in text) + '1111111111111110'
    return binary

def embed_secret_in_audio(input_audio_path, secret_data, output_audio_path):
    """
    Embed secret data into an audio file using audio steganography
    
    Args:
        input_audio_path (str): Path to input audio file
        secret_data (str): Secret text to embed
        output_audio_path (str): Path to save output audio file
    
    Returns:
        dict: Statistics about the embedding process
    """
    # Convert secret data to binary
    secret_bin = convert_text_to_binary(secret_data)
    
    # Log info for debugging
    print(f"First 20 chars of original: {secret_data[:20]!r}")
    print(f"Original text length: {len(secret_data)} characters")
    print(f"Secret data size: {len(secret_bin)} bits")
    
    # Load and normalize audio
    audio_data, sr = librosa.load(input_audio_path, sr=None)
    normalized_audio = pyln.normalize.peak(audio_data, TARGET_PEAK)
    
    # Compute STFT to analyze frequency content
    stft = librosa.stft(normalized_audio, n_fft=FRAME_SIZE, hop_length=HOP_LENGTH)
    magnitude = np.abs(stft)
    frame_energies = np.sum(magnitude ** 2, axis=0)
    
    # Calculate masking thresholds
    thresholds = np.zeros_like(frame_energies)
    for i in range(1, len(frame_energies)):
        thresholds[i] = max(frame_energies[i] * MASKING_FACTOR, thresholds[i - 1] * 0.9)
    
    # Find maskable samples
    maskable_samples = []
    for frame_idx, energy in enumerate(frame_energies):
        if energy > thresholds[frame_idx]:
            start_sample = frame_idx * HOP_LENGTH
            end_sample = min(start_sample + HOP_LENGTH, len(normalized_audio))
            maskable_samples.extend(range(start_sample, end_sample))
    
    # Check capacity
    available_capacity = len(maskable_samples) * EMBEDDING_DEPTH
    print(f"Available capacity: {available_capacity} bits")
    
    if len(secret_bin) > available_capacity:
        raise ValueError(f"Not enough capacity to embed all secret data. Need {len(secret_bin)} bits, but only have {available_capacity} bits available.")
    
    # Convert audio to bytes for manipulation
    audio_int = (normalized_audio * 32767).astype(np.int16)
    frames = bytearray(audio_int.tobytes())
    
    # Embed the secret data
    data_index = 0
    for sample_idx in maskable_samples:
        if data_index < len(secret_bin):
            bits_to_embed = min(EMBEDDING_DEPTH, len(secret_bin) - data_index)
            byte_val = frames[sample_idx * 2] & 0xFF
            byte_val = (byte_val & (0xFF << bits_to_embed)) | int(secret_bin[data_index:data_index + bits_to_embed], 2)
            frames[sample_idx * 2] = byte_val
            data_index += bits_to_embed
        else:
            break
    
    # Save the output file
    with wave.open(output_audio_path, 'wb') as stego_audio:
        stego_audio.setnchannels(1)
        stego_audio.setsampwidth(2)
        stego_audio.setframerate(sr)
        stego_audio.writeframes(bytes(frames))
    
    # Return statistics
    return {
        "original_text_length": len(secret_data),
        "secret_bits": len(secret_bin),
        "embedded_bits": data_index,
        "available_capacity": available_capacity,
        "output_file": output_audio_path
    }

def extract_secret_from_audio(stego_audio_path):
    """
    Extract secret data from a steganographic audio file
    
    Args:
        stego_audio_path (str): Path to the steganographic audio file
        
    Returns:
        str: Extracted secret text
    """
    # Load the audio file
    audio_data, sr = librosa.load(stego_audio_path, sr=None)
    
    # Compute STFT to analyze frequency content
    stft = librosa.stft(audio_data, n_fft=FRAME_SIZE, hop_length=HOP_LENGTH)
    magnitude = np.abs(stft)
    frame_energies = np.sum(magnitude ** 2, axis=0)
    
    # Calculate masking thresholds
    thresholds = np.zeros_like(frame_energies)
    for i in range(1, len(frame_energies)):
        thresholds[i] = max(frame_energies[i] * MASKING_FACTOR, thresholds[i - 1] * 0.9)
    
    # Find maskable samples
    maskable_samples = []
    for frame_idx, energy in enumerate(frame_energies):
        if energy > thresholds[frame_idx]:
            start_sample = frame_idx * HOP_LENGTH
            end_sample = min(start_sample + HOP_LENGTH, len(audio_data))
            maskable_samples.extend(range(start_sample, end_sample))
    
    # Read the audio bytes
    with wave.open(stego_audio_path, 'rb') as stego_audio:
        frames = bytearray(stego_audio.readframes(stego_audio.getnframes()))
    
    # Extract binary data
    extracted_bin = ''
    for sample_idx in maskable_samples:
        if sample_idx * 2 < len(frames):
            byte_val = frames[sample_idx * 2] & 0xFF
            extracted_bin += format(byte_val & ((1 << EMBEDDING_DEPTH) - 1), '0' + str(EMBEDDING_DEPTH) + 'b')
    
    # Look for EOF marker
    eof_marker = '1111111111111110'
    eof_idx = extracted_bin.find(eof_marker)
    if eof_idx != -1:
        extracted_bin = extracted_bin[:eof_idx]
    
    # Convert binary to text
    extracted_text = ''
    for i in range(0, len(extracted_bin) - len(extracted_bin) % 8, 8):
        byte = extracted_bin[i:i+8]
        try:
            extracted_text += chr(int(byte, 2))
        except:
            # Skip invalid characters
            pass
    
    return {
        "extracted_text": extracted_text,
        "stats": {
            "total_maskable_samples": len(maskable_samples),
            "max_extractable_bits": len(maskable_samples) * EMBEDDING_DEPTH,
            "extracted_binary_length": len(extracted_bin),
            "eof_marker_found": eof_idx != -1,
            "extracted_text_length": len(extracted_text)
        }
    }