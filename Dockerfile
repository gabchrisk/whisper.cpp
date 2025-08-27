# =====================================================================
# Stage 1: Build whisper.cpp executable
# =====================================================================
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone and build whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j$(nproc)

# =====================================================================
# Stage 2: Final production image
# =====================================================================
# Use the same base image as the builder to ensure runtime compatibility
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
# Set PATH to include venv binaries
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies (Python, wget, and ffmpeg for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user for better security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create a virtual environment
RUN python3 -m venv /opt/venv

# Copy application and install python packages
COPY --chown=appuser:appuser main.py .
RUN pip install --no-cache-dir fastapi uvicorn python-multipart

# Copy build artifacts from the builder stage
COPY --from=builder /app/whisper.cpp/build/bin/main /usr/local/bin/whisper

# Download model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# Update the binary path in the script to the new location
RUN sed -i 's|"/app/whisper.cpp/build/main"|"/usr/local/bin/whisper"|g' main.py

# Change ownership of app files to the non-root user
RUN chown -R appuser:appuser /app /opt/venv

# Switch to the non-root user
USER appuser

EXPOSE 5000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
