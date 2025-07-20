#!/bin/bash

# Scribe System Startup Script
# This script starts the Scribe Viewer web application with proper checks

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Scribe System...${NC}"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "scribe_cli.py" ]; then
    echo -e "${RED}Error: This script must be run from the scribe project root directory${NC}"
    exit 1
fi

# Check Python environment
echo -e "\n${YELLOW}Checking Python environment...${NC}"
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: No Python virtual environment detected${NC}"
    echo "Consider activating your virtual environment first"
    echo "Example: source venv/bin/activate or uv venv && source .venv/bin/activate"
else
    echo -e "${GREEN}✓ Python environment active: $VIRTUAL_ENV${NC}"
fi

# Check for uv
echo -e "\n${YELLOW}Checking uv (Python package manager)...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed${NC}"
    echo "Please install uv: https://github.com/astral-sh/uv"
    exit 1
fi
echo -e "${GREEN}✓ uv $(uv --version)${NC}"

# Check uv Python version
echo -e "\n${YELLOW}Checking Python via uv...${NC}"
UV_PYTHON_VERSION=$(uv run python --version 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ ${UV_PYTHON_VERSION}${NC}"
else
    echo -e "${RED}Error: Could not run Python via uv${NC}"
    echo "Try running: uv venv && uv pip install -r requirements.txt"
    exit 1
fi

# Check for database
echo -e "\n${YELLOW}Checking database...${NC}"
if [ -f "media_tracking.db" ]; then
    echo -e "${GREEN}✓ Database found: media_tracking.db${NC}"
    # Show quick stats
    echo -e "\n${YELLOW}Database statistics:${NC}"
    uv run python scribe_cli.py status --summary 2>/dev/null || echo "Could not fetch database stats"
else
    echo -e "${YELLOW}⚠ No database found. The viewer will work but won't show processing status.${NC}"
fi

# Check for .env file
echo -e "\n${YELLOW}Checking configuration...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Configuration file found: .env${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found. Some features may not work.${NC}"
    echo "  Create one with: cp .env.example .env"
fi

# Check Node.js and pnpm
echo -e "\n${YELLOW}Checking Node.js environment...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node --version)${NC}"

if ! command -v pnpm &> /dev/null; then
    echo -e "${RED}Error: pnpm is not installed${NC}"
    echo "Install with: npm install -g pnpm"
    exit 1
fi
echo -e "${GREEN}✓ pnpm $(pnpm --version)${NC}"

# Navigate to scribe-viewer
echo -e "\n${YELLOW}Starting Scribe Viewer...${NC}"
cd scribe-viewer

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pnpm install
fi

# Check if manifest exists
if [ ! -f "public/manifest.min.json" ]; then
    echo -e "${YELLOW}⚠ No manifest.min.json found. The viewer needs this file to display interviews.${NC}"
    echo "  Generate one with: python scripts/build_manifest.py"
fi

# Start the viewer
echo -e "\n${GREEN}Launching Scribe Viewer...${NC}"
echo "=================================="
echo -e "${GREEN}✓ Opening http://localhost:3000${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"

# Open browser after a short delay
(sleep 3 && open http://localhost:3000) &

# Start the development server
pnpm dev 