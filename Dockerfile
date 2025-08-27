# =====================================================================
# Stage 1: Builder - Tahap untuk kompilasi C++ dan dependensi build
# =====================================================================
FROM ubuntu:24.04 AS builder

# Mencegah prompt interaktif saat instalasi package
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install dependensi sistem yang dibutuhkan untuk build
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    && \
    # Membersihkan cache untuk menjaga ukuran image
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Menetapkan direktori kerja
WORKDIR /app

# 3. Clone dan build whisper.cpp
# Perintah digabung dalam satu layer RUN untuk efisiensi cache
RUN git clone https://github.com/ggerganov/whisper.cpp.git && \
    cd whisper.cpp && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make -j$(nproc)

# =====================================================================
# Stage 2: Final - Image akhir yang bersih, ringan, dan siap jalan
# =====================================================================
FROM python:3.12-slim-bookworm

# Mencegah prompt interaktif
ENV DEBIAN_FRONTEND=noninteractive

# 1. Menetapkan direktori kerja utama
WORKDIR /app

# 2. Membuat user non-root untuk keamanan
# Menjalankan aplikasi sebagai root adalah praktik yang tidak aman
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 3. Membuat virtual environment
# Walaupun di dalam kontainer, venv adalah praktik yang baik untuk manajemen dependensi
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 4. Install dependensi Python
# Menyalin requirements.txt terlebih dahulu memanfaatkan Docker cache
COPY --chown=appuser:appuser main.py .
RUN pip install --no-cache-dir fastapi uvicorn python-multipart

# 5. Salin artefak yang dibutuhkan dari stage 'builder'
COPY --from=builder /app/whisper.cpp/build/main /usr/local/bin/whisper

# 6. Download model dan salin kode aplikasi
RUN mkdir -p /app/models && \
    chown -R appuser:appuser /app
RUN wget -O /app/models/ggml-small.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# 7. Ganti path binary di main.py agar sesuai dengan path baru
RUN sed -i 's|"/app/whisper.cpp/build/main"|"/usr/local/bin/whisper"|g' main.py

# 8. Ganti kepemilikan direktori aplikasi ke user baru
RUN chown -R appuser:appuser /app /opt/venv

# 9. Ganti ke user non-root
USER appuser

# 10. Expose port yang digunakan
EXPOSE 5000

# 11. Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
