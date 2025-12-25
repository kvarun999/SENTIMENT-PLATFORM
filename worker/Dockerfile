FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (needed for PostgreSQL adapter)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Increase timeout because torch is huge
RUN pip install --no-cache-dir -r requirements.txt --timeout 100

COPY . .

# Fix for "silent" logs: ensures Python prints immediately to Docker logs
ENV PYTHONUNBUFFERED=1

CMD ["python", "worker.py"]