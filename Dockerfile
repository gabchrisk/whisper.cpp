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
        ffmpeg \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Build the main binary
WORKDIR /app/whisper.cpp
RUN cmake -B build -DWHISPER_CUDA=OFF -DCMAKE_CUDA_ARCHITECTURES=OFF
RUN cmake --build build --config Release

# Verify the binary was built
RUN ls -la /app/whisper.cpp/build/bin/
RUN file /app/whisper.cpp/build/bin/main

# Move back to the app directory
WORKDIR /app

# Install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create models directory
RUN mkdir -p /app/models

# Download the model with proper error handling
RUN cd /app/whisper.cpp && \
    chmod +x models/download-ggml-model.sh && \
    ./models/download-ggml-model.sh small && \
    cp models/ggml-small.bin /app/models/ && \
    ls -la /app/models/

# Copy the application file
COPY main.py .

# Verify all required files exist
RUN ls -la /app/whisper.cpp/build/bin/main
RUN ls -la /app/models/ggml-small.bin

# Create a health check script
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/health || exit 1' > /app/healthcheck.sh
RUN chmod +x /app/healthcheck.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD /app/healthcheck.sh

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
