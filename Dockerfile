.FROM python:3.12-slim

WORKDIR /app

# ⬇️ MEMPERBAIKI MASALAH SSL DENGAN MENAMBAHKAN ca-certificates ⬇️
RUN apt-get update && apt-get install -y gcc python3-dev ca-certificates

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
