# Single-stage Dockerfile that keeps all build tools in the final image.
# This results in a larger image but makes debugging inside the container easier.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:$PATH"

# Install all build-time and run-time dependencies in one go.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    build-essential \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Build whisper.cpp
RUN cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j$(nproc)

# FIX: Create a symbolic link from the actual binary location to the path expected by main.py
# This is more robust than using 'sed'.
RUN ln -s /app/whisper.cpp/build/bin/main /app/whisper.cpp/build/main

# Download the GGML model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy the Python application code
COPY --chown=appuser:appuser main.py .

# Create a virtual environment and install Python packages
RUN python3 -m venv /opt/venv && \
    pip install --no-cache-dir fastapi uvicorn python-multipart

# Change ownership of the entire app directory and the venv
RUN chown -R appuser:appuser /app /opt/venv

# Switch to the non-root user
USER appuser

EXPOSE 5000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
