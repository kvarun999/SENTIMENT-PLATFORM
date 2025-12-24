FROM python:3.9-slim

WORKDIR /app

# 1. Install system dependencies (needed for PostgreSQL adapter)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 3. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 5. Command to run the application
# "main:app" means: look in main.py for the object named 'app'
# --reload enables auto-restart when you change code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]