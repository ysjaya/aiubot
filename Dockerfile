# Menggunakan base image Python 3.12
FROM python:3.12-slim

WORKDIR /app

# Menginstal build tools dengan versi dev yang sesuai
RUN apt-get update && apt-get install -y gcc python3.12-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
