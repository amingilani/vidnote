FROM python:3.11-slim

# 1. Install System Dependencies (FFmpeg & OpenCV requirements)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
# distinct from opencv-python to prevent GUI deps
RUN pip install --no-cache-dir \
    openai-whisper \
    scenedetect[opencv] \
    opencv-python-headless \
    tqdm \
    numpy

# 3. Copy Application Code
WORKDIR /app
COPY main.py /app/main.py

# 4. Define Entrypoint
ENTRYPOINT ["python", "main.py"]
