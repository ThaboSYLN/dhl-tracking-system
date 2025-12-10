#!/bin/bash

# Start DHL Tracking Automation Service
# This script starts the automation service in the background

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}DHL Tracking Automation Service${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if service is already running
if [ -f "automation.pid" ]; then
    PID=$(cat automation.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW} Automation service is already running (PID: $PID)${NC}"
        echo -e "${YELLOW}   Use './scripts/stop_automation.sh' to stop it first${NC}"
        exit 1
    else
        echo -e "${YELLOW}  Stale PID file found, removing...${NC}"
        rm automation.pid
    fi
fi

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d "Traker_Env_Venv" ]; then
    echo -e "${RED} Virtual environment not found${NC}"
    echo -e "${YELLOW}   Please activate your virtual environment first${NC}"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "Traker_Env_Venv" ]; then
    source Traker_Env_Venv/bin/activate
fi

# Install required packages if not already installed
echo -e "${GREEN} Checking dependencies...${NC}"
pip install -q apscheduler pyyaml 2>/dev/null || true

# Create necessary directories
mkdir -p \\soj3serv07\Production To Office\DHL\inbox data/processed data/failed data/logs

# Start the automation service in background
echo -e "${GREEN} Starting automation service...${NC}"
nohup python -m app.automation.automation_service > data/logs/automation_service.log 2>&1 &

# Save PID
echo $! > automation.pid

PID=$(cat automation.pid)
echo -e "${GREEN} Automation service started successfully!${NC}"
echo -e "${GREEN}   PID: $PID${NC}"
echo ""
# \\soj3serv07\Production To Office\DHL
echo -e "${GREEN} Drop files here: \\soj3serv07\Production To Office\DHL\inbox/${NC}"
echo -e "${GREEN} View logs: tail -f data/logs/automation.log${NC}"
echo -e "${GREEN} Stop service: ./scripts/stop_automation.sh${NC}"
echo ""
echo -e "${GREEN}======================================${NC}"

