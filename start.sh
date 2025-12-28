#!/bin/bash

# Rescored Startup Script
# Starts all services: Redis, Backend API, Celery Worker, and Frontend

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Rescored - Starting All Services${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check if Redis is running
echo -e "${YELLOW}Checking Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${YELLOW}Starting Redis service...${NC}"
    brew services start redis
    sleep 2
    if ! redis-cli ping > /dev/null 2>&1; then
        echo -e "${RED}✗ Failed to start Redis${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Redis is running${NC}"
echo ""

# Check virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo -e "${RED}✗ Backend virtual environment not found at backend/.venv${NC}"
    echo -e "${YELLOW}Please set up the backend first (see README.md)${NC}"
    exit 1
fi

# Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    echo ""
fi

# Check storage directory
if [ ! -d "storage" ]; then
    echo -e "${YELLOW}Creating storage directory...${NC}"
    mkdir -p storage
fi

# Check for YouTube cookies
if [ ! -f "storage/youtube_cookies.txt" ]; then
    echo -e "${YELLOW}⚠️  Warning: YouTube cookies not found at storage/youtube_cookies.txt${NC}"
    echo -e "${YELLOW}   You will need to set this up for video downloads to work${NC}"
    echo -e "${YELLOW}   See README.md for instructions${NC}"
    echo ""
fi

echo -e "${BLUE}Starting services...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    jobs -p | xargs -r kill 2>/dev/null
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create logs directory and files
mkdir -p logs
rm -f logs/api.log logs/worker.log logs/frontend.log
touch logs/api.log logs/worker.log logs/frontend.log

# Start Backend API
echo -e "${BLUE}[1/3] Starting Backend API...${NC}"
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../logs/api.log 2>&1 &
API_PID=$!
cd ..
echo -e "${GREEN}✓ Backend API started (PID: $API_PID)${NC}"
echo -e "      Logs: logs/api.log"
echo ""

# Start Celery Worker
echo -e "${BLUE}[2/3] Starting Celery Worker...${NC}"
cd backend
source .venv/bin/activate
# Use --pool=solo for macOS to avoid fork() issues with ML libraries
celery -A tasks worker --loglevel=info --pool=solo > ../logs/worker.log 2>&1 &
WORKER_PID=$!
cd ..
echo -e "${GREEN}✓ Celery Worker started (PID: $WORKER_PID)${NC}"
echo -e "      Logs: logs/worker.log"
echo ""

# Start Frontend
echo -e "${BLUE}[3/3] Starting Frontend...${NC}"
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
echo -e "      Logs: logs/frontend.log"
echo ""

# Wait a moment for services to start
sleep 3

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  All Services Running!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  Frontend:  ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend:   ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  API:       tail -f logs/api.log"
echo -e "  Worker:    tail -f logs/worker.log"
echo -e "  Frontend:  tail -f logs/frontend.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait
