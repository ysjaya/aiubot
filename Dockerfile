FROM python:3.11-slim

# Menambahkan build tools yang diperlukan
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Menetapkan direktori kerja di dalam container
WORKDIR /app

# Menyalin file requirements terlebih dahulu untuk caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Menyalin seluruh kode aplikasi
COPY ./app /app

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
