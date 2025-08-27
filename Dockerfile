# Stage 1: Build the whisper.cpp binary
FROM debian:bullseye-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        wget \
        ca-certificates \
        cmake && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

WORKDIR /app/whisper.cpp

# Build using cmake
RUN cmake -B build -DWHISPER_CUDA=OFF -DCMAKE_CUDA_ARCHITECTURES=OFF
RUN cmake --build build --config Release


# Stage 2: Final production image
FROM python:3.9-slim-bullseye

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        wget && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the compiled binary from the builder stage
COPY --from=builder /app/whisper.cpp/build/bin/main /usr/local/bin/whisper

# Copy the model downloader script and run it
COPY --from=builder /app/whisper.cpp/models/download-ggml-model.sh /app/models/
RUN /app/models/download-ggml-model.sh small /app/models/

# Copy the application file
COPY main.py .

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
