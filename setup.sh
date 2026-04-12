#!/usr/bin/env bash

# Horus ATC Quick Setup Script
# This script helps set up the complete voice communication system

set -euo pipefail

echo "🛩️ Horus MVP - Quick Setup"
echo "=================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d backend || ! -d frontend ]]; then
    echo "Run this script from the repository root."
    exit 1
fi

read_ollama_model_from_file() {
    local env_file="$1"
    local value
    value="$(awk -F= '/^OLLAMA_LLM_MODEL=/{value=substr($0, index($0, "=") + 1)} END{print value}' "$env_file")"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
if [[ -f backend/.env ]]; then
    ENV_OLLAMA_MODEL="$(read_ollama_model_from_file backend/.env)"
    if [[ -n "$ENV_OLLAMA_MODEL" ]]; then
        OLLAMA_MODEL="$ENV_OLLAMA_MODEL"
    fi
elif [[ -f backend/.env.example ]]; then
    ENV_OLLAMA_MODEL="$(read_ollama_model_from_file backend/.env.example)"
    if [[ -n "$ENV_OLLAMA_MODEL" ]]; then
        OLLAMA_MODEL="$ENV_OLLAMA_MODEL"
    fi
fi

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
    echo -e "${RED}✗${NC} Node.js not found. Please install Node.js 22+ from https://nodejs.org"
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
uv sync
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
        if ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
            echo -e "${GREEN}✓${NC} ${OLLAMA_MODEL} model installed"
        else
            echo -e "${YELLOW}!${NC} ${OLLAMA_MODEL} model not found. Downloading..."
            echo "   This will download ~2GB, please wait..."
            ollama pull "$OLLAMA_MODEL"
            echo -e "${GREEN}✓${NC} Model downloaded"
        fi
    else
        # Check via API if ollama command not available
        if curl -s http://localhost:11434/api/tags | grep -q "$OLLAMA_MODEL"; then
            echo -e "${GREEN}✓${NC} ${OLLAMA_MODEL} model found via API"
        else
            echo -e "${YELLOW}!${NC} ${OLLAMA_MODEL} model not detected"
            echo "   If using shared/remote Ollama, ensure the model is available"
            echo "   Otherwise run: ollama pull $OLLAMA_MODEL"
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
echo -e "1. Start Ollama (if not running):"
echo -e "   ${YELLOW}ollama serve${NC}"
echo ""
echo -e "2. Start Backend API:"
echo -e "   ${YELLOW}cd backend${NC}"
echo -e "   ${YELLOW}source .venv/bin/activate${NC}  # On Windows: .venv\\\\Scripts\\\\activate"
echo -e "   ${YELLOW}uv run uvicorn app.main:app --reload${NC}"
echo ""
echo -e "3. Start Frontend (in another terminal):"
echo -e "   ${YELLOW}cd frontend && pnpm dev${NC}"
echo ""
echo -e "4. Open your browser:"
echo -e "   ${GREEN}http://localhost:3000${NC} (squawk)"
echo -e "   ${GREEN}http://localhost:3001${NC} (tower)"
echo -e "   ${GREEN}http://localhost:3002${NC} (hangar)"
echo ""
echo "5. Click the mic button (bottom-right) and start talking!"
echo ""
echo "📚 Documentation:"
echo "   - Documentation index: docs/README.md"
echo "   - Developer guide: docs/development.md"
echo "   - Backend docs: backend/README.md"
echo ""
echo "🎙️ Happy flying! ✈️"
