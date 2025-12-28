#!/bin/bash

# Rescored Stop Script
# Stops all running Rescored services

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping Rescored services...${NC}"

# Kill processes by name
pkill -f "uvicorn main:app" && echo -e "${GREEN}✓ Stopped Backend API${NC}"
pkill -f "celery -A tasks worker" && echo -e "${GREEN}✓ Stopped Celery Worker${NC}"
pkill -f "vite" && echo -e "${GREEN}✓ Stopped Frontend${NC}"

echo -e "${GREEN}All services stopped${NC}"
