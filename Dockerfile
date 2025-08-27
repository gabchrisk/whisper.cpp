FROM python:3.9-bullseye

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install all dependencies in one go: build tools and runtime tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        wget \
        ca-certificates \
        cmake \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Build the main binary
WORKDIR /app/whisper.cpp
RUN cmake -B build -DWHISPER_CUDA=OFF -DCMAKE_CUDA_ARCHITECTURES=OFF
RUN cmake --build build --config Release

# Move back to the app directory
WORKDIR /app

# Install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the model
RUN /app/whisper.cpp/models/download-ggml-model.sh small /app/models/

# Copy the application file
COPY main.py .

# Modify main.py to point to the correct binary path inside this unified image
# The binary will be at /app/whisper.cpp/build/bin/main
RUN sed -i 's|/usr/local/bin/whisper|/app/whisper.cpp/build/bin/main|g' main.py

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
