#!/bin/bash
set -e

echo "Starting Rescored backend..."

cd /app/backend

# Check if using fake Redis (eager mode - no worker needed)
if [ "$USE_FAKE_REDIS" = "true" ]; then
    echo "Using eager mode (synchronous task execution)"
    exec python -u main.py
else
    # Production mode - start Celery worker in background
    echo "Starting Celery worker..."
    celery -A celery_app worker --loglevel=info --concurrency=1 &
    CELERY_PID=$!
    
    # Give Celery a moment to start
    sleep 2
    
    # Start FastAPI server
    echo "Starting FastAPI server on port ${API_PORT}..."
    python -u main.py &
    API_PID=$!
    
    # Wait for both processes
    wait $CELERY_PID $API_PID
fi
