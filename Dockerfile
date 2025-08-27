# Stage 1: Build the whisper.cpp binary
FROM debian:bullseye-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        wget \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Build the main binary
WORKDIR /app/whisper.cpp
RUN make


# Stage 2: Final production image
FROM python:3.9-slim-bullseye

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install runtime dependencies (ffmpeg for audio conversion)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the compiled binary from the builder stage
COPY --from=builder /app/whisper.cpp/main /usr/local/bin/whisper

# Copy the model downloader script and run it
# This keeps the model separate from the main application code
COPY --from=builder /app/whisper.cpp/models/download-ggml-model.sh /app/models/
RUN /app/models/download-ggml-model.sh small /app/models/

# Copy the application file
COPY main.py .

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
