FROM ubuntu:24.04

# Mencegah prompt interaktif saat instalasi package
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install dependensi sistem
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    wget \
    python3 \
    python3-pip \
    python3-venv && \
    # Membersihkan cache untuk menjaga ukuran image
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Menetapkan direktori kerja utama
WORKDIR /app

# 3. Membuat dan mengaktifkan virtual environment di dalam direktori kerja
RUN python3 -m venv venv

# 4. Install dependensi Python menggunakan pip dari venv
RUN venv/bin/pip install --no-cache-dir fastapi uvicorn python-multipart

# 5. Clone dan build whisper.cpp
RUN git clone https://github.com/ggerganov/whisper.cpp.git
# Build whisper.cpp dalam satu layer untuk efisiensi
RUN mkdir -p whisper.cpp/build && \
    cd whisper.cpp/build && \
    cmake .. && \
    make -j$(nproc)

# 6. Download model
RUN mkdir -p models
RUN wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 7. Salin kode aplikasi ke direktori kerja
COPY main.py .

# 8. Expose port yang digunakan oleh aplikasi
EXPOSE 5000

# 9. Perintah untuk menjalankan aplikasi menggunakan uvicorn dari venv
# CMD ini akan dieksekusi dari WORKDIR (/app)
CMD ["/app/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
