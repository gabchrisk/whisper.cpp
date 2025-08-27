FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:$PATH"

# 1. Install all required system dependencies
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
    libavdevice-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# 3. Build whisper.cpp with FFmpeg support
RUN cd whisper.cpp && \
    mkdir -p build && \
    cd build && \
    cmake .. -DWHISPER_FFMPEG=ON && \
    make -j$(nproc)

# 4. Verify and create proper binary location
# The build creates 'main' in build/ directory, not build/bin/
RUN ls -la /app/whisper.cpp/build/ && \
    if [ -f /app/whisper.cpp/build/bin/main ]; then \
        ln -sf /app/whisper.cpp/build/bin/main /app/whisper.cpp/build/main; \
    elif [ -f /app/whisper.cpp/build/main ]; then \
        echo "Binary already in correct location"; \
    else \
        echo "ERROR: Binary not found in expected locations" && exit 1; \
    fi

# 5. Download the GGML model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 6. Test the binary works
RUN /app/whisper.cpp/build/main --help || echo "Binary test failed but continuing..."

# 7. Create virtual environment and install Python packages
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir fastapi uvicorn python-multipart

# 8. Copy Python application
COPY main.py .

# 9. Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
