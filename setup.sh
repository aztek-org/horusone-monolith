#!/bin/bash

# Horus ATC Quick Setup Script
# This script helps set up the complete voice communication system

set -e

echo "🎙️ Horus ATC Voice Communication System - Quick Setup"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if command_exists node; then
    echo -e "${GREEN}✓${NC} Node.js installed ($(node --version))"
else
    echo -e "${RED}✗${NC} Node.js not found. Please install Node.js 18+ from https://nodejs.org"
    exit 1
fi

if command_exists pnpm; then
    echo -e "${GREEN}✓${NC} pnpm installed ($(pnpm --version))"
else
    echo -e "${YELLOW}!${NC} pnpm not found. Installing..."
    npm install -g pnpm
fi

if command_exists python3; then
    echo -e "${GREEN}✓${NC} Python installed ($(python3 --version))"
else
    echo -e "${RED}✗${NC} Python 3.10+ not found. Please install Python from https://python.org"
    exit 1
fi

if command_exists uv; then
    echo -e "${GREEN}✓${NC} uv installed ($(uv --version))"
else
    echo -e "${YELLOW}!${NC} uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Check Ollama by trying to connect to the service
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Ollama service is accessible (http://localhost:11434)"
elif command_exists ollama; then
    echo -e "${YELLOW}!${NC} Ollama command found but service not running"
    echo "   Please start Ollama: ollama serve"
else
    echo -e "${RED}✗${NC} Ollama not found. Please install from https://ollama.ai"
    echo "   Run: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

if command_exists ffmpeg; then
    echo -e "${GREEN}✓${NC} FFmpeg installed"
else
    echo -e "${RED}✗${NC} FFmpeg not found. Please install:"
    echo "   Ubuntu/Debian: sudo apt-get install ffmpeg libsndfile1"
    echo "   macOS: brew install ffmpeg libsndfile"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ All prerequisites satisfied!"
echo "=================================================="
echo ""

# Step 2: Install frontend dependencies
echo "📦 Step 2: Installing frontend dependencies..."
cd frontend
pnpm install
cd ..
echo -e "${GREEN}✓${NC} Frontend dependencies installed"
echo ""

# Step 3: Setup backend
echo "🐍 Step 3: Setting up backend..."
cd backend

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    uv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

echo "Installing backend dependencies..."
source .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate 2>/dev/null
uv pip install -e .
echo -e "${GREEN}✓${NC} Backend dependencies installed"

if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env file created"
else
    echo -e "${YELLOW}!${NC} .env file already exists, skipping"
fi

cd ..
echo ""

# Step 4: Check Ollama
echo "🤖 Step 4: Checking Ollama setup..."

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Ollama server is running (http://localhost:11434)"
    
    # Check if model is installed (if ollama command is available)
    if command_exists ollama; then
        if ollama list 2>/dev/null | grep -q "llama3.2:3b"; then
            echo -e "${GREEN}✓${NC} llama3.2:3b model installed"
        else
            echo -e "${YELLOW}!${NC} llama3.2:3b model not found. Downloading..."
            echo "   This will download ~2GB, please wait..."
            ollama pull llama3.2:3b
            echo -e "${GREEN}✓${NC} Model downloaded"
        fi
    else
        # Check via API if ollama command not available
        if curl -s http://localhost:11434/api/tags | grep -q "llama3.2:3b"; then
            echo -e "${GREEN}✓${NC} llama3.2:3b model found via API"
        else
            echo -e "${YELLOW}!${NC} llama3.2:3b model not detected"
            echo "   If using shared/remote Ollama, ensure the model is available"
            echo "   Otherwise run: ollama pull llama3.2:3b"
        fi
    fi
else
    echo -e "${YELLOW}!${NC} Ollama server not running on http://localhost:11434"
    echo "   Please start Ollama in another terminal: ollama serve"
    echo "   Or update OLLAMA_BASE_URL in backend/.env if using remote Ollama"
fi

echo ""
echo "=================================================="
echo "🎉 Setup Complete!"
echo "=================================================="
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Start Ollama (if not running):"
echo "   ${YELLOW}ollama serve${NC}"
echo ""
echo "2. Start Backend API:"
echo "   ${YELLOW}cd backend${NC}"
echo "   ${YELLOW}source .venv/bin/activate${NC}  # On Windows: .venv\\Scripts\\activate"
echo "   ${YELLOW}uv run uvicorn app.main:app --reload${NC}"
echo ""
echo "3. Start Frontend (in another terminal):"
echo "   ${YELLOW}cd frontend && pnpm dev${NC}"
echo ""
echo "4. Open your browser:"
echo "   ${GREEN}http://localhost:3000${NC}"
echo ""
echo "5. Click the mic button (bottom-right) and start talking!"
echo ""
echo "📚 Documentation:"
echo "   - Complete setup: PROJECT_SETUP.md"
echo "   - Implementation details: IMPLEMENTATION_SUMMARY.md"
echo "   - Backend docs: backend/README.md"
echo ""
echo "🎙️ Happy flying! ✈️"
