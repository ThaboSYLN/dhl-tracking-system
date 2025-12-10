#!/bin/bash

# Check Automation Service Status

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Automation Service Status${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if PID file exists
if [ ! -f "automation.pid" ]; then
    echo -e "${RED} Service is NOT running${NC}"
    echo -e "${YELLOW}   Start with: ./scripts/start_automation.sh${NC}"
    echo ""
    exit 1
fi

# Read PID
PID=$(cat automation.pid)

# Check if process is running
if ps -p $PID > /dev/null 2>&1; then
    echo -e "${GREEN} Service is RUNNING${NC}"
    echo -e "${GREEN}   PID: $PID${NC}"
    echo ""
    
    # Show process info
    echo -e "${GREEN}Process Info:${NC}"
    ps -p $PID -o pid,ppid,cmd,%cpu,%mem,etime
    echo ""
    
    # Show recent logs
    if [ -f "data/logs/automation.log" ]; then
        echo -e "${GREEN}Recent Logs (last 10 lines):${NC}"
        echo -e "${YELLOW}---${NC}"
        tail -n 10 data/logs/automation.log
        echo -e "${YELLOW}---${NC}"
        echo ""
    fi
    
    # Show inbox status
    if [ -d "\\soj3serv07\Production To Office\DHL\inbox" ]; then
        FILE_COUNT=$(ls -1 data/inbox 2>/dev/null | wc -l)
        echo -e "${GREEN}Inbox Status:${NC}"
        echo -e "   Files waiting: $FILE_COUNT"
        echo "" 
    fi
    
    # Show processed/failed counts
    if [ -d "data/processed" ]; then
        PROCESSED_COUNT=$(ls -1 data/processed 2>/dev/null | wc -l)
        echo -e "${GREEN}Processed Files: $PROCESSED_COUNT${NC}"
    fi
    
    if [ -d "data/failed" ]; then
        FAILED_COUNT=$(ls -1 data/failed 2>/dev/null | wc -l)
        if [ $FAILED_COUNT -gt 0 ]; then
            echo -e "${RED}Failed Files: $FAILED_COUNT${NC}"
        else
            echo -e "${GREEN}Failed Files: $FAILED_COUNT${NC}"
        fi
    fi
    
    echo ""
    exit 0
else
    echo -e "${RED} Service is NOT running (stale PID file)${NC}"
    echo -e "${YELLOW}   Removing stale PID file...${NC}"
    rm automation.pid
    echo -e "${YELLOW}   Start with: ./scripts/start_automation.sh${NC}"
    echo ""
    exit 1
fi

