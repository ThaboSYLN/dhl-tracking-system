#!/bin/bash

# Stop DHL Tracking Automation Service

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW} Stopping DHL Tracking Automation Service...${NC}"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if PID file exists
if [ ! -f "automation.pid" ]; then
    echo -e "${YELLOW}  No PID file found. Service may not be running.${NC}"
    exit 1
fi

# Read PID
PID=$(cat automation.pid)

# Check if process is running
if ! ps -p $PID > /dev/null 2>&1; then
    echo -e "${YELLOW}  Process $PID is not running${NC}"
    rm automation.pid
    exit 1
fi

# Stop the process
echo -e "${YELLOW}   Stopping process $PID...${NC}"
kill $PID

# Wait for process to stop (max 10 seconds)
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Force kill if still running
if ps -p $PID > /dev/null 2>&1; then
    echo -e "${YELLOW}   Force stopping...${NC}"
    kill -9 $PID
fi

# Remove PID file
rm automation.pid

echo -e "${GREEN} Automation service stopped successfully${NC}"
echo ""

