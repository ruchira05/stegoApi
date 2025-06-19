from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import os
import tempfile
import logging
import json
from werkzeug.utils import secure_filename
from steganography import (
    generate_aes_key, 
    read_aes_key,
    embed_secret_in_audio, 
    extract_secret_from_audio
)
from datetime import datetime

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, origins=['*'], methods=['GET', 'POST', 'OPTIONS'])

# Configure upload folders - use /app instead of /tmp for Azure Container Apps
UPLOAD_FOLDER = '/app/uploads'
OUTPUT_FOLDER = '/app/outputs'
LOG_FOLDER = '/app/logs'

# Create directories if they don't exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, LOG_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Configure logging with proper path
log_file = os.path.join(LOG_FOLDER, 'app.log')
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG for production
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also log to console for Azure Container Apps
    ]
)

# Get port from environment variable (Azure Container Apps requirement)
PORT = int(os.environ.get('PORT', 8080))

# Swagger UI Configuration
SWAGGER_URL = '/swagger'
API_URL = '/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Audio Steganography API with AES Encryption",
        'dom_id': '#swagger-ui',
        'url_prefix': SWAGGER_URL,
        'layout': 'StandaloneLayout',
        'deepLinking': True,
        'showExtensions': True,
        'showCommonExtensions': True,
        'tryItOutEnabled': True
    }
)

app.register_blueprint(swaggerui_blueprint)

# OpenAPI Specification (updated with correct port)
OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Audio Steganography API with AES Encryption",
        "description": "REST API for embedding encrypted secret messages in audio files using advanced steganography techniques with AES-256-CBC encryption",
        "version": "2.0.0",
        "contact": {
            "email": "support@example.com"
        }
    },
    "servers": [
        {
            "url": "/",
            "description": "Current server"
        }
    ],
    "tags": [
        {
            "name": "steganography",
            "description": "Steganography operations with encryption"
        },
        {
            "name": "security",
            "description": "Security and key management operations"
        },
        {
            "name": "system",
            "description": "System operations"
        }
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["system"],
                "summary": "Health check endpoint",
                "description": "Check if the API is running properly",
                "operationId": "healthCheck",
                "responses": {
                    "200": {
                        "description": "API is running correctly",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "ok"
                                        },
                                        "timestamp": {
                                            "type": "string",
                                            "format": "date-time",
                                            "description": "Current server timestamp"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/generate-key": {
            "post": {
                "tags": ["security"],
                "summary": "Generate AES encryption key",
                "description": "Generates a new 256-bit AES encryption key for secure steganography operations",
                "operationId": "generateKey",
                "responses": {
                    "200": {
                        "description": "AES key generated successfully",
                        "content": {
                            "application/octet-stream": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": "AES-256 encryption key file (.key extension)"
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Key generation failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/embed": {
            "post": {
                "tags": ["steganography"],
                "summary": "Embed encrypted secret data in audio",
                "description": "Embeds encrypted secret text into a WAV audio file using advanced steganography with psychoacoustic masking",
                "operationId": "embedSecret",
                "requestBody": {
                    "description": "Audio file, AES key, and secret data to embed",
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "key_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "AES encryption key file (.key extension)"
                                    },
                                    "audio_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "WAV audio file (will be resampled to 44.1kHz)"
                                    },
                                    "secret_text": {
                                        "type": "string",
                                        "description": "Secret text to embed in the audio (alternative to secret_file)"
                                    },
                                    "secret_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "Text file containing the secret to embed (alternative to secret_text)"
                                    }
                                },
                                "required": ["key_file", "audio_file"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Secret data embedded successfully",
                        "content": {
                            "audio/wav": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": "WAV audio file with embedded encrypted secret"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request - missing required files or invalid input",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Embedding operation failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/extract": {
            "post": {
                "tags": ["steganography"],
                "summary": "Extract and decrypt secret data from audio",
                "description": "Extracts and decrypts secret text from a WAV audio file with embedded steganographic data",
                "operationId": "extractSecret",
                "requestBody": {
                    "description": "Audio file with embedded secret and AES key for decryption",
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "audio_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "WAV audio file with embedded encrypted secret"
                                    },
                                    "key_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "AES encryption key file (.key extension) used for embedding"
                                    }
                                },
                                "required": ["audio_file", "key_file"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Secret data extracted successfully",
                        "content": {
                            "text/plain": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": "Text file containing the extracted secret data"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request - missing required files",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Extraction operation failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/docs": {
            "get": {
                "tags": ["system"],
                "summary": "Get API documentation",
                "description": "Returns JSON documentation for the API endpoints and features",
                "operationId": "getApiDocs",
                "responses": {
                    "200": {
                        "description": "API documentation retrieved successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ApiDocumentation"
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "description": "Error message describing what went wrong"
                    }
                },
                "required": ["error"]
            },
            "ApiDocumentation": {
                "type": "object",
                "properties": {
                    "api": {
                        "type": "string",
                        "description": "API name"
                    },
                    "version": {
                        "type": "string",
                        "description": "API version"
                    },
                    "description": {
                        "type": "string",
                        "description": "API description"
                    },
                    "endpoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string"
                                },
                                "method": {
                                    "type": "string"
                                },
                                "description": {
                                    "type": "string"
                                },
                                "parameters": {
                                    "type": "array",
                                    "items": {
                                        "type": "object"
                                    }
                                },
                                "returns": {
                                    "type": "string"
                                }
                            }
                        }
                    },
                    "features": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of API features"
                    }
                }
            }
        }
    }
}

@app.route('/swagger.json')
def swagger_json():
    """Serve the OpenAPI specification as JSON"""
    return jsonify(OPENAPI_SPEC)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logging.info("Health check requested")
    return jsonify({
        "status": "ok", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }), 200

@app.route('/')
def index():
    """Root endpoint"""
    return jsonify({
        "message": "Audio Steganography API",
        "version": "2.0.0",
        "swagger_ui": "/swagger",
        "api_docs": "/api/docs",
        "health": "/health"
    })

@app.route('/generate-key', methods=['POST'])
def generate_key():
    """Generate and download AES encryption key"""
    try:
        logging.info("Key generation requested")
        
        key = generate_aes_key()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key_filename = f"aes_key_{timestamp}.key"
        key_path = os.path.join(OUTPUT_FOLDER, key_filename)
        
        with open(key_path, 'wb') as key_file:
            key_file.write(key)
        
        logging.info(f"AES key generated and saved: {key_filename}")
        
        return send_file(
            key_path,
            as_attachment=True,
            download_name=key_filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logging.error(f"Error generating key: {e}")
        return jsonify({"error": f"Key generation failed: {str(e)}"}), 500

@app.route('/embed', methods=['POST'])
def embed_secret():
    """Embed secret data into audio file using AES encryption"""
    key_path = None
    audio_path = None
    
    try:
        logging.info("Embed operation requested")
        
        # Validate required files
        if 'key_file' not in request.files:
            return jsonify({"error": "No key file provided"}), 400
        
        if 'audio_file' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        key_file = request.files['key_file']
        audio_file = request.files['audio_file']
        
        if key_file.filename == '' or audio_file.filename == '':
            return jsonify({"error": "Empty file name provided"}), 400
        
        # Get secret data
        secret_data = None
        if 'secret_file' in request.files:
            secret_file = request.files['secret_file']
            if secret_file.filename != '':
                secret_data = secret_file.read()
                logging.info(f"Secret data loaded from file: {len(secret_data)} bytes")
        elif 'secret_text' in request.form:
            secret_data = request.form['secret_text'].encode('utf-8')
            logging.info(f"Secret text provided: {len(secret_data)} bytes")
        
        if secret_data is None:
            return jsonify({"error": "No secret data provided"}), 400
        
        # Save files temporarily
        key_filename = secure_filename(key_file.filename or "uploaded_key.key")
        key_path = os.path.join(UPLOAD_FOLDER, key_filename)
        key_file.save(key_path)
        
        audio_filename = secure_filename(audio_file.filename or "uploaded_audio.wav")
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        audio_file.save(audio_path)
        
        # Load AES key
        aes_key = read_aes_key(key_path)
        
        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"stego_{timestamp}_{audio_filename}"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        # Embed secret data
        result = embed_secret_in_audio(
            input_audio_path=audio_path,
            secret_data=secret_data,
            key=aes_key,
            output_audio_path=output_path
        )
        
        logging.info(f"Embed operation completed: {result['embedded_bits']}/{result['total_bits']} bits embedded")
        
        # Return the processed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='audio/wav'
        )
        
    except Exception as e:
        logging.error(f"Error in embed operation: {e}")
        return jsonify({"error": f"Embed operation failed: {str(e)}"}), 500
    finally:
        # Clean up temporary files
        for temp_file in [key_path, audio_path]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

@app.route('/extract', methods=['POST'])
def extract_secret():
    """Extract hidden data from steganographic audio file"""
    audio_path = None
    key_path = None
    
    try:
        logging.info("Extract operation requested")
        
        # Validate required files
        if 'audio_file' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        if 'key_file' not in request.files:
            return jsonify({"error": "No key file provided"}), 400
        
        audio_file = request.files['audio_file']
        key_file = request.files['key_file']
        
        if audio_file.filename == '' or key_file.filename == '':
            return jsonify({"error": "Empty file name provided"}), 400
        
        # Save files temporarily
        audio_filename = secure_filename(audio_file.filename or "uploaded_audio.wav")
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        audio_file.save(audio_path)
        
        key_filename = secure_filename(key_file.filename or "uploaded_key.key")
        key_path = os.path.join(UPLOAD_FOLDER, key_filename)
        key_file.save(key_path)
        
        # Load AES key
        aes_key = read_aes_key(key_path)
        
        # Extract secret data
        result = extract_secret_from_audio(audio_path, aes_key)
        
        # Create output text file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"extracted_secret_{timestamp}.txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        # Save extracted data to file
        with open(output_path, 'wb') as output_file:
            output_file.write(result['extracted_data'])
        
        logging.info(f"Extract operation completed: {result['extracted_bits']} bits extracted")
        
        # Return the extracted text file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='text/plain'
        )
        
    except Exception as e:
        logging.error(f"Error in extract operation: {e}")
        return jsonify({"error": f"Extract operation failed: {str(e)}"}), 500
    finally:
        # Clean up temporary files
        for temp_file in [audio_path, key_path]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

@app.route('/api/docs', methods=['GET'])
def api_docs():
    """API documentation"""
    docs = {
        "api": "Audio Steganography API with AES Encryption",
        "version": "2.0",
        "description": "Secure audio steganography with AES-256-CBC encryption",
        "endpoints": [
            {
                "path": "/health",
                "method": "GET",
                "description": "Health check endpoint",
                "returns": "Status information"
            },
            {
                "path": "/generate-key",
                "method": "POST",
                "description": "Generate AES encryption key",
                "parameters": [],
                "returns": "AES key file (.key extension)"
            },
            {
                "path": "/embed",
                "method": "POST",
                "description": "Embed encrypted secret data into audio file",
                "parameters": [
                    {"name": "key_file", "type": "file", "required": True, "description": "AES key file (.key extension)"},
                    {"name": "audio_file", "type": "file", "required": True, "description": "WAV audio file"},
                    {"name": "secret_text", "type": "form-data", "required": False, "description": "Secret text to embed"},
                    {"name": "secret_file", "type": "file", "required": False, "description": "Secret text file to embed"}
                ],
                "returns": "WAV file with embedded encrypted secret"
            },
            {
                "path": "/extract",
                "method": "POST",
                "description": "Extract and decrypt hidden data from audio file",
                "parameters": [
                    {"name": "audio_file", "type": "file", "required": True, "description": "WAV file with hidden message"},
                    {"name": "key_file", "type": "file", "required": True, "description": "AES key file (.key extension)"}
                ],
                "returns": "Text file with extracted secret data"
            }
        ],
        "features": [
            "AES-256-CBC encryption",
            "Psychoacoustic masking",
            "44.1kHz audio processing",
            "Automatic capacity calculation",
            "Comprehensive logging"
        ]
    }
    return jsonify(docs)

@app.errorhandler(413)
def too_large(e):
    logging.warning("File too large uploaded")
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(400)
def bad_request(e):
    logging.warning(f"Bad request: {e}")
    return jsonify({"error": "Bad request"}), 400

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logging.info("Starting Audio Steganography API server")
    print("🚀 Server starting...")
    print(f"📚 Swagger UI available at: http://localhost:{PORT}/swagger")
    print(f"🔧 API documentation at: http://localhost:{PORT}/api/docs")
    print(f"❤️  Health check at: http://localhost:{PORT}/health")
    app.run(host='0.0.0.0', port=PORT, debug=False)