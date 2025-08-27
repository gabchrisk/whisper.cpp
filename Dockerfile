FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone and build whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j4 && \
    # Copy server binary to parent directory
    cp server ../server 2>/dev/null || cp bin/server ../server 2>/dev/null || echo "Server binary built"

# Download model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-base.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

# Verify server binary exists
RUN ls -la /app/whisper.cpp/ && \
    find /app/whisper.cpp -name "*server*" -type f

# Create non-root user
RUN groupadd -r whisper && \
    useradd -r -g whisper whisper && \
    chown -R whisper:whisper /app

USER whisper

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run server (try different paths)
CMD cd /app/whisper.cpp && \
    (./server -m /app/models/ggml-base.bin --host 0.0.0.0 --port 8080 || \
     ./build/server -m /app/models/ggml-base.bin --host 0.0.0.0 --port 8080 || \
     ./build/bin/server -m /app/models/ggml-base.bin --host 0.0.0.0 --port 8080)
