# =====================================================================
# Final Single-Stage Dockerfile
# This version builds everything in one consistent environment to maximize compatibility.
# =====================================================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/venv/bin:$PATH"

# 1. Install all build-time and run-time dependencies in one go.
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

# 2. Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# 3. Build whisper.cpp
RUN cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j$(nproc)

# 4. Download the GGML model
RUN mkdir -p /app/models && \
    wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 5. Copy the Python application code
COPY main.py .

# 6. IMPORTANT FIX: Update the binary path directly in the script
# This avoids any potential issues with symbolic links.
RUN sed -i 's|"/app/whisper.cpp/build/main"|"/app/whisper.cpp/build/bin/main"|g' main.py

# 7. Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 8. Create a virtual environment and install Python packages
RUN python3 -m venv /opt/venv && \
    pip install --no-cache-dir fastapi uvicorn python-multipart

# 9. Change ownership of the entire app directory
RUN chown -R appuser:appuser /app

# 10. Switch to the non-root user
USER appuser

EXPOSE 5000

# 11. Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
