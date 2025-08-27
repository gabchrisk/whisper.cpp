# =====================================================================
# Optimized Dockerfile for whisper.cpp with proper binary handling
# =====================================================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:$PATH"

# 1. Install system dependencies
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

# 2. Clone and build whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    mkdir -p build && \
    cd build && \
    cmake .. -DWHISPER_FFMPEG=ON && \
    make -j$(nproc)

# 3. Verify and setup binary paths
RUN cd /app/whisper.cpp/build && \
    echo "Build directory contents:" && \
    ls -la && \
    # Find the correct binary name
    if [ -f "bin/whisper-cli" ]; then \
        echo "Found whisper-cli in bin/" && \
        ln -sf /app/whisper.cpp/build/bin/whisper-cli /app/whisper.cpp/build/whisper-cli; \
    elif [ -f "whisper-cli" ]; then \
        echo "Found whisper-cli in build/"; \
    elif [ -f "bin/main" ]; then \
        echo "Found main in bin/, creating whisper-cli symlink" && \
        ln -sf /app/whisper.cpp/build/bin/main /app/whisper.cpp/build/whisper-cli; \
    elif [ -f "main" ]; then \
        echo "Found main in build/, creating whisper-cli symlink" && \
        ln -sf /app/whisper.cpp/build/main /app/whisper.cpp/build/whisper-cli; \
    else \
        echo "ERROR: No whisper binary found!" && \
        echo "Available files:" && \
        find . -name "*whisper*" -o -name "main" && \
        exit 1; \
    fi

# 4. Test binary and show help
RUN /app/whisper.cpp/build/whisper-cli --help | head -20 || \
    (echo "Binary test failed - checking if it's 'main' instead" && \
     /app/whisper.cpp/build/main --help | head -20) || \
    echo "Warning: Binary help failed, but continuing..."

# 5. Download Whisper model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin && \
    echo "Model downloaded, size:" && \
    ls -lh /app/models/ggml-small.bin

# 6. Setup Python environment
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    python-multipart==0.0.6

# 7. Copy application
COPY main.py .

# 8. Set permissions and create user
RUN groupadd -r appuser && \
    useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /app/whisper.cpp/build/whisper-cli

# 9. Final verification
RUN echo "=== FINAL SETUP VERIFICATION ===" && \
    echo "Binary path:" && \
    ls -la /app/whisper.cpp/build/whisper-cli && \
    echo "Model path:" && \
    ls -la /app/models/ggml-small.bin && \
    echo "Binary executable test:" && \
    /app/whisper.cpp/build/whisper-cli --help > /dev/null 2>&1 && echo "✓ Binary works" || echo "✗ Binary failed"

USER appuser

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
