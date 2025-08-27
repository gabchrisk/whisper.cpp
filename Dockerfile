# =====================================================================
# Final Single-Stage Dockerfile based on official whisper.cpp repository
# This version includes all necessary build and runtime dependencies in one stage
# to ensure maximum compatibility and prevent runtime errors.
# =====================================================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:$PATH"

# 1. Install all required system dependencies
# Includes build tools, Python, and crucially, FFmpeg and SDL2 libraries for audio processing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    build-essential \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libsdl2-2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# 3. Build whisper.cpp with FFmpeg support enabled
# This ensures the binary can handle various audio formats like .m4a
RUN cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. -DWHISPER_FFMPEG=ON && \
    make -j$(nproc)

# 4. Download the GGML model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 5. Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 6. Copy the Python application code
COPY --chown=appuser:appuser main.py .

# 7. Create a virtual environment and install Python packages
RUN python3 -m venv /opt/venv && \
    pip install --no-cache-dir fastapi uvicorn python-multipart

# 8. Change ownership of the entire app directory to the new user
RUN chown -R appuser:appuser /app

# 9. Switch to the non-root user
USER appuser

EXPOSE 5000

# 10. Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
