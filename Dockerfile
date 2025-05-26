FROM python:3.9-slim

# Install system dependencies for librosa and soundfile
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY steganography.py .
COPY static/ ./static/
COPY templates/ ./templates/

# Create directories for file storage
RUN mkdir -p /tmp/uploads /tmp/outputs

# Expose port
EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:5000", "app:app"]
