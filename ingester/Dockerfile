FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Unbuffered output ensures logs show up immediately in docker console
ENV PYTHONUNBUFFERED=1

CMD ["python", "ingester.py"]