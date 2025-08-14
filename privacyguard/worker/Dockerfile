FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Reuse requirements from backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code for backend and worker
COPY backend/app ./backend/app
COPY worker ./worker

ENV PYTHONPATH=/app

CMD ["celery", "-A", "worker.tasks", "worker", "--loglevel=info"]