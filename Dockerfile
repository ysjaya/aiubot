FROM python:3.12-slim

WORKDIR /app

# ⬇️ KEMBALI MENGGUNAKAN NAMA PAKET YANG UMUM ⬇️
RUN apt-get update && apt-get install -y gcc python3-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
