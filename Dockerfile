FROM python:3.11-slim

# Menambahkan build tools yang diperlukan untuk beberapa paket Python
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --upgrade pip && pip install -r requirements.txt

# CMD diubah untuk menggunakan environment variable $PORT dari Kinsta.
# Jangan gunakan "EXPOSE 8000" karena port tidak lagi tetap.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
