#!/bin/bash
set -e

echo "� Starting Rescored backend..."

cd /app/backend

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A celery_app worker --loglevel=info --concurrency=1 &
CELERY_PID=$!

# Give Celery a moment to start
sleep 2

# Start FastAPI server in the foreground
echo "Starting FastAPI server on port ${API_PORT}..."
python -u main.py &
API_PID=$!

# Wait for both processes
wait $CELERY_PID $API_PID
