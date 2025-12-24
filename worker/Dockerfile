FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (for Postgres)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Increase timeout because torch is huge
RUN pip install --no-cache-dir -r requirements.txt --timeout 100

COPY . .

CMD ["python", "worker.py"]