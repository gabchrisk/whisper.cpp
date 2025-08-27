FROM ubuntu:24.04

# Install dependencies
RUN apt update && apt install -y \
    git \
    cmake \
    build-essential \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    python3-full

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install FastAPI in virtual environment
RUN pip install fastapi uvicorn python-multipart

# Setup working directory
WORKDIR /app

# Clone whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git
WORKDIR /app/whisper.cpp

# Build whisper.cpp
RUN mkdir build && cd build && cmake .. && make -j$(nproc)

# Create model folder
RUN mkdir -p /app/models

# Download small model otomatis
RUN wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# Copy FastAPI wrapper
COPY main.py /app/whisper.cpp/main.py

# Expose API port
EXPOSE 5000

# Jalankan FastAPI dengan virtual environment
CMD ["/opt/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
