# Audio Steganography REST API

This project provides a RESTful API for audio steganography operations, allowing you to embed secret text data into WAV audio files. The API is containerized using Docker for easy deployment.

## Features

- RESTful API for audio steganography operations
- Embed secret text into WAV audio files
- Accept both direct text input and text files
- Containerized with Docker for easy deployment
- Clean separation of controller (API) and core functionality

## Project Structure

```
steganography-api/
├── app.py                # Flask API controller
├── steganography.py      # Core steganography implementation
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker build configuration
├── docker-compose.yml    # Docker Compose configuration
├── test_api.py           # Test client for the API
├── static/               # Static files directory
│   └── swagger.json      # Swagger API specification
├── templates/            # HTML templates
│   └── index.html        # Main landing page
└── README.md             # This file
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for local development)

### Running with Docker

1. Clone the repository:
   ```
   git clone <repository-url>
   cd steganography-api
   ```

2. Build and start the container:
   ```
   docker-compose up -d
   ```

3. The API will be available at `http://localhost:5000`

### Local Development

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python app.py
   ```

## API Endpoints

### `GET /`

Landing page with web interface for the API.

### `GET /health`

Health check endpoint to verify API is running.

**Response:**
```json
{
  "status": "ok"
}
```

### `POST /embed`

Embeds secret text into a WAV audio file.

**Request:**
- Form data:
  - `audio_file`: WAV audio file (required)
  - `secret_text`: Text to embed (optional if secret_file is provided)
  - `secret_file`: Text file to embed (optional if secret_text is provided)

**Response:**
- WAV file with embedded secret text

**Example using curl:**
```bash
# Embed text
curl -X POST -F "audio_file=@input.wav" -F "secret_text=This is a secret message" \
     http://localhost:5000/embed -o output.wav

# Embed file
curl -X POST -F "audio_file=@input.wav" -F "secret_file=@secret.txt" \
     http://localhost:5000/embed -o output.wav
```

### `GET /api/docs`

Returns API documentation in JSON format.

### `GET /swagger`

Interactive Swagger UI for exploring and testing the API.

## Testing the API

You can use the included `test_api.py` script to test the API:

```bash
python test_api.py --audio path/to/audio.wav --text "This is a secret message"
```

or 

```bash
python test_api.py --audio path/to/audio.wav --file path/to/secret.txt
```

## Technical Details

The steganography implementation uses several advanced techniques:

1. **Audio Normalization**: Normalizes audio to a specific peak level before embedding
2. **Psychoacoustic Masking**: Uses psychoacoustic principles to find suitable embedding locations
3. **Least Significant Bit (LSB) Encoding**: Embeds data in the least significant bits of audio samples
4. **Energy Thresholding**: Only embeds data in high-energy regions where modifications are less perceptible

## Limitations

- Currently only supports mono WAV files
- No encryption of the embedded text
- No extraction functionality in this version

## Future Enhancements

- Add extraction functionality
- Support for stereo audio files
- Add encryption for the embedded data
- Support additional audio formats (MP3, FLAC, etc.)
- Add user authentication for the API