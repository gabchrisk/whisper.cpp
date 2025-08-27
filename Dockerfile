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

# Clone and build whisper.cpp with server
RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    make server

# Download model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-base.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

# Create non-root user
RUN groupadd -r whisper && \
    useradd -r -g whisper whisper && \
    chown -R whisper:whisper /app

USER whisper

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run server
CMD ["./whisper.cpp/server", "-m", "/app/models/ggml-base.bin", "--host", "0.0.0.0", "--port", "8080"]
