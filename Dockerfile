# Gunakan base image yang lebih spesifik untuk stabilitas
FROM python:3.11.9-slim-bullseye

# Set environment variables untuk mencegah pembuatan file .pyc dan buffering output
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build-essential untuk beberapa paket yang mungkin memerlukan kompilasi
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Buat pengguna non-root yang lebih aman
RUN useradd -m -u 1001 -s /bin/bash appuser

# Set direktori kerja
WORKDIR /app

# Salin requirements dan instal sebagai root untuk manajemen paket
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Salin sisa kode aplikasi
COPY . .

# Berikan kepemilikan direktori kepada pengguna baru
RUN chown -R appuser:appuser /app

# Ganti ke pengguna non-root
USER appuser

# Jalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
