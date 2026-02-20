# Horus ATC Voice Communication System - Complete Setup Guide

This guide covers the complete setup for the Horus Aviation Training Platform with real-time Air Traffic Control voice communication.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Nuxt.js + Vue 3)                             │
│  - VoiceCommBubble: Floating mic button                 │
│  - Push-to-talk interface                               │
│  - WebSocket client                                     │
└─────────────────────────────────────────────────────────┘
                           ↕ WebSocket (ws://localhost:8000/ws/voice)
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI + Python)                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 1. Speech-to-Text (Whisper)                     │   │
│  │ 2. ATC AI Agent (LangChain + Ollama)            │   │
│  │ 3. Text-to-Speech (Coqui TTS)                   │   │
│  │ 4. Radio Effects (scipy filters + noise)        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows (WSL2 recommended for Windows)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk**: 10GB free space for models
- **GPU**: Optional (improves TTS/STT performance)

### Required Software

1. **Node.js 18+** and **pnpm**
```bash
# Install Node.js (https://nodejs.org)
# Install pnpm
npm install -g pnpm
```

2. **Python 3.10+** and **uv**
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

3. **Ollama** (Local LLM runtime)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve  # Keep this running in a terminal

# Pull the LLM model (in another terminal)
ollama pull llama3.2:3b  # ~2GB download
```

4. **FFmpeg** (Audio processing)
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1

# macOS
brew install ffmpeg libsndfile

# Verify
ffmpeg -version
```

## Installation

### 1. Clone and Setup Project

```bash
# Clone repository
git clone <your-repo-url>
cd horus-mvp

# Install frontend dependencies
cd frontend
pnpm install
cd ..

# Setup backend
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
cd ..
```

### 2. Configure Backend

```bash
cd backend

# Create environment file
cp .env.example .env

# Edit configuration (optional - defaults work fine)
nano .env
```

**Key configuration options:**
```bash
# .env file
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b
WHISPER_MODEL=base  # Options: tiny, base, small, medium, large
ENABLE_RADIO_EFFECTS=true
CORS_ORIGINS=http://localhost:3000
```

### 3. Download Models

Models are automatically downloaded on first run, but you can pre-download them:

```bash
# Whisper model (auto-downloads on first use)
# ~150MB for 'base' model

# Coqui TTS model (auto-downloads on first use)
# ~500MB for default model

# Ollama model (already pulled above)
ollama list  # Verify llama3.2:3b is installed
```

## Running the System

### Terminal 1: Ollama Server
```bash
ollama serve
# Keep this running
```

### Terminal 2: Backend API
```bash
cd backend
source .venv/bin/activate

# Run with auto-reload (development)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Backend will be at: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Terminal 3: Frontend
```bash
# From project root
cd frontend
pnpm dev

# Frontend will be at: http://localhost:3000
```

## Using the Voice Communication System

### Quick Start

1. **Open the app**: Navigate to http://localhost:3000
2. **Wait for connection**: Green dot on voice bubble indicates ready
3. **Press and hold**: Click and hold the mic button
4. **Speak**: Say your pilot transmission (e.g., "Tower, Cessna 172 November 1234 Alpha, ready for takeoff")
5. **Release**: Let go to send your audio
6. **Listen**: ATC will respond automatically

### Voice Bubble States

- **Cyan with mic icon**: Ready to record
- **Red pulsing**: Recording your voice
- **Blue with spinner**: Processing transmission
- **Blue with speaker**: ATC is speaking
- **Gray**: Disconnected or unavailable

### Example Communications

**Takeoff Clearance:**
```
You: "Tower, Cessna 172 November 1234 Alpha, ready for takeoff, runway 27"
ATC: "Cessna 1234 Alpha, cleared for takeoff runway 27, wind 280 at 10 knots"
```

**Altitude Change:**
```
You: "Approach, requesting descent to flight level 250"
ATC: "Roger, descend and maintain flight level 250, reduce speed 250 knots"
```

**Position Report:**
```
You: "Center, we are 10 miles east of the airport at 3500 feet"
ATC: "Roger, continue present heading, report 5 mile final"
```

## Troubleshooting

### Backend Issues

**Ollama connection error**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

**Whisper model not loading**:
```bash
# Check Python environment
which python
pip list | grep whisper

# Reinstall if needed
uv pip install --force-reinstall openai-whisper
```

**TTS errors**:
```bash
# Install system dependencies
sudo apt-get install -y espeak-ng libsndfile1  # Linux
brew install espeak-ng  # macOS

# Reinstall TTS
uv pip install --force-reinstall TTS
```

**Port already in use**:
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in .env
PORT=8001
```

### Frontend Issues

**WebSocket connection fails**:
- Check backend is running at http://localhost:8000
- Check CORS settings in backend `.env`
- Verify WebSocket URL in `frontend/app/composables/useVoiceComm.ts`

**Microphone access denied**:
- Grant browser permission for microphone
- Use HTTPS in production (required for mic access)
- Check browser console for errors

**No audio playback**:
- Check browser audio permissions
- Verify audio output device is working
- Check browser console for playback errors

### Performance Issues

**Slow response times**:
- Use smaller Whisper model: `WHISPER_MODEL=tiny` or `base`
- Use smaller Ollama model: `ollama pull llama3.2:1b`
- Disable radio effects: `ENABLE_RADIO_EFFECTS=false`
- Ensure adequate RAM (8GB+ recommended)

**High CPU usage**:
- Normal during audio processing
- Consider using GPU acceleration (CUDA for NVIDIA GPUs)
- Reduce concurrent connections

## Architecture Details

### Backend Structure
```
backend/app/
├── main.py                      # FastAPI application
├── config.py                    # Configuration
├── api/routes/
│   ├── health.py                # Health checks
│   └── voice.py                 # WebSocket endpoint
├── core/
│   ├── audio_pipeline.py        # End-to-end processing
│   └── websocket_manager.py     # Connection management
└── services/
    ├── stt/whisper_service.py   # Speech-to-Text
    ├── tts/tts_service.py       # Text-to-Speech
    ├── llm/atc_agent.py         # ATC AI agent
    └── audio_effects/filters.py # Radio effects
```

### Frontend Structure
```
frontend/app/
├── composables/
│   └── useVoiceComm.ts          # WebSocket client
└── components/shared/
    └── VoiceCommBubble.vue      # Voice UI component
```

### Communication Flow
1. User presses mic button → Start recording
2. Audio chunks → WebSocket stream to backend
3. Backend: Whisper STT → Transcribe to text
4. Backend: LangChain + Ollama → Generate ATC response
5. Backend: Coqui TTS → Synthesize speech
6. Backend: Radio effects → Add realistic audio effects
7. Audio response → WebSocket stream to frontend
8. Frontend: Play audio → User hears ATC

## API Endpoints

### HTTP
- `GET /` - API information
- `GET /health` - Health check
- `GET /health/ready` - Readiness check
- `GET /docs` - Swagger UI documentation

### WebSocket
- `WS /ws/voice` - Bi-directional voice communication

## Development Tips

### Backend Development
```bash
# Run with debug logging
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload

# Test API endpoints
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

### Frontend Development
```bash
# Run frontend only
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```

### Testing Voice Communication
```bash
# Test with Python script
cd backend
python -c "
import asyncio
import websockets

async def test():
    async with websockets.connect('ws://localhost:8000/ws/voice') as ws:
        print(await ws.recv())  # Connection message

asyncio.run(test())
"
```

## Production Deployment

### Backend (Docker recommended)
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY backend/ .
RUN pip install uv && uv pip install -e .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend (Static hosting)
```bash
pnpm build
# Deploy .output/public/ to your hosting provider
```

### Environment Variables (Production)
```bash
# Backend
ENVIRONMENT=production
OLLAMA_BASE_URL=http://ollama:11434  # Docker service name
CORS_ORIGINS=https://your-domain.com
LOG_LEVEL=INFO

# Frontend
NUXT_PUBLIC_WS_URL=wss://api.your-domain.com/ws/voice
```

## Next Steps

1. **Customize ATC prompts**: Edit `backend/app/services/llm/prompts.py`
2. **Adjust audio effects**: Modify `backend/app/services/audio_effects/filters.py`
3. **Add flight context**: Integrate with scenario data for contextual ATC responses
4. **Add authentication**: Implement user auth for production use
5. **Optimize models**: Fine-tune Whisper or use faster TTS models

## Support & Resources

- **Backend README**: `backend/README.md`
- **Frontend README**: `README.md`
- **Ollama Docs**: https://ollama.ai/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Nuxt.js Docs**: https://nuxt.com

## License

MIT
