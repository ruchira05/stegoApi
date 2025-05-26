from flask import Flask, request, send_file, jsonify, render_template
import os
import tempfile
from werkzeug.utils import secure_filename
from steganography import embed_secret_in_audio, extract_secret_from_audio
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__, static_folder='static')

# Configure upload folders
UPLOAD_FOLDER = '/tmp/uploads'
OUTPUT_FOLDER = '/tmp/outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200

@app.route('/embed', methods=['POST'])
def embed_secret():
    """
    Endpoint to embed secret text into an audio file
    
    Expects:
    - audio_file: WAV file
    - secret_text: Text content OR
    - secret_file: Text file
    
    Returns:
    - WAV file with embedded secret
    """
    # Check if files are in the request
    if 'audio_file' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    # Get the audio file
    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({"error": "Empty audio file name"}), 400
    
    # Get the secret data
    secret_data = None
    if 'secret_file' in request.files:
        secret_file = request.files['secret_file']
        if secret_file.filename != '':
            # Read the secret file
            secret_data = secret_file.read().decode('utf-8')
    elif 'secret_text' in request.form:
        secret_data = request.form['secret_text']
    
    if secret_data is None:
        return jsonify({"error": "No secret data provided"}), 400
    
    # Save the audio file temporarily
    audio_filename = secure_filename(audio_file.filename)
    audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
    audio_file.save(audio_path)
    
    # Create a unique output filename
    output_filename = f"stego_{audio_filename}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    
    # Process the audio and embed the secret
    try:
        embed_secret_in_audio(
            input_audio_path=audio_path,
            secret_data=secret_data,
            output_audio_path=output_path
        )
        
        # Return the processed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='audio/wav'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up temporary files
        if os.path.exists(audio_path):
            os.remove(audio_path)

@app.route('/extract', methods=['POST'])
def extract_secret():
    """
    Endpoint to extract hidden text from a steganographic audio file

    Expects:
    - audio_file: WAV file with embedded secret

    Returns:
    - Extracted secret text and metadata
    """
    if 'audio_file' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({"error": "Empty audio file name"}), 400

    # Save the audio file temporarily
    audio_filename = secure_filename(audio_file.filename)
    audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
    audio_file.save(audio_path)

    try:
        result = extract_secret_from_audio(audio_path)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

@app.route('/api/docs', methods=['GET'])
def api_docs():
    """Simple API documentation"""
    docs = {
        "api": "Audio Steganography API",
        "version": "1.0",
        "endpoints": [
            {
                "path": "/health",
                "method": "GET",
                "description": "Health check endpoint"
            },
            {
                "path": "/embed",
                "method": "POST",
                "description": "Embed secret text into audio file",
                "parameters": [
                    {"name": "audio_file", "type": "file", "required": True, "description": "WAV audio file"},
                    {"name": "secret_text", "type": "form-data", "required": False, "description": "Secret text to embed"},
                    {"name": "secret_file", "type": "file", "required": False, "description": "Secret text file to embed"}
                ],
                "returns": "WAV file with embedded secret"
            },
            {
                "path": "/extract",
                "method": "POST",
                "description": "Extract hidden text from audio file",
                "parameters": [
                    {"name": "audio_file", "type": "file", "required": True, "description": "WAV file with hidden message"}
                ],
                "returns": "Extracted text and statistics"
            }

        ]
    }
    return jsonify(docs)

# Register Swagger UI blueprint
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Audio Steganography API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/')
def index():
    """Landing page with links to API docs and Swagger UI"""
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)