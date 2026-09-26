# Horus ATC Voice Communication API

Real-time bi-directional voice communication system for Air Traffic Control simulation using FastAPI, WebSockets, Whisper STT, gTTS, and Ollama LLMs.

## Features

- **Speech-to-Text**: Whisper model for accurate aviation communication transcription
- **Multi-Language Support**: English and Spanish with automatic language detection
- **Text-to-Speech**: Google Text-to-Speech (gTTS) for natural-sounding ATC responses
- **AI-Powered ATC**: LangChain + Ollama for realistic air traffic control conversations
- **Radio Effects**: Band-pass filters, noise, and static for authentic radio simulation
- **WebSocket Communication**: Real-time bi-directional audio streaming
- **No Authentication**: Simple setup for development and training purposes

## Architecture

```
Pilot Audio (WebSocket) 
    ↓
Speech-to-Text (Whisper)
    ↓
ATC Agent (LangChain + Ollama)
    ↓
Text-to-Speech (Coqui TTS)
    ↓
Radio Effects (scipy filters)
    ↓
ATC Audio Response (WebSocket)
```

## Prerequisites

- **Python 3.10+**
- **uv** package manager ([Installation](https://github.com/astral-sh/uv))
- **Ollama** running locally ([Installation](https://ollama.ai))
- **FFmpeg** for audio processing

### Install Prerequisites

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install FFmpeg
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve  # Start Ollama server

# Pull the LLM model
ollama pull llama3.2:3b
```

## Installation

```bash
# Navigate to backend directory
cd backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .

# Create .env file
cp .env.example .env

# Edit .env with your settings (optional, defaults work fine)
nano .env
```

## Configuration

Edit `.env` to configure the API:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b

# Whisper Model (base, small, medium, large)
WHISPER_MODEL=base
WHISPER_LANGUAGE=auto  # en, es, or auto for auto-detection

# TTS Configuration
TTS_LANGUAGE=en  # en or es (overridden by detected language)

# Scene registry (blank uses the packaged default-v1 Scene)
SCENES_PATH=

# Audio Processing
SAMPLE_RATE=16000
ENABLE_RADIO_EFFECTS=true

# Server
HOST=0.0.0.0
PORT=8000

# CORS (add your frontend URL)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Multi-Language Support

The system supports **English** and **Spanish** with automatic language detection:

- **Auto-detection**: Set `WHISPER_LANGUAGE=auto` to automatically detect the pilot's language
- **English**: Set `WHISPER_LANGUAGE=en` for English-only mode
- **Spanish**: Set `WHISPER_LANGUAGE=es` for Spanish-only mode

**Example conversations:**

English:
```
Pilot: "Tower, Cessna 172 November 1234 Alpha, ready for takeoff, runway 27."
ATC: "Cessna 1234 Alpha, cleared for takeoff runway 27, wind 280 at 10 knots."
```

Spanish:
```
Piloto: "Torre, Cessna 172 November 1234 Alpha, listo para despegar, pista 27."
ATC: "Cessna 1234 Alpha, autorizado para despegar pista 27, viento 280 a 10 nudos."
```

See [LANGUAGE_SUPPORT.md](LANGUAGE_SUPPORT.md) for detailed documentation.

## Running the API

```bash
# Development mode (with auto-reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python -m app.main

# The API will be available at:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - WebSocket: ws://localhost:8000/ws/voice
```

## API Endpoints

### HTTP Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `GET /health/ready` - Readiness check
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

### WebSocket Endpoint

- `WS /ws/voice` - Bi-directional voice communication

## WebSocket Protocol

### Client → Server

**Audio Data (Binary)**:
```
Send raw WAV audio chunks as binary frames
```

**Control Messages (JSON)**:
```json
// Signal end of audio transmission
{"type": "audio_end"}

// Reset conversation
{"type": "reset"}

// Heartbeat
{"type": "ping"}
```

### Server → Client

**Audio Response (Binary)**:
```
Receives processed ATC audio as WAV binary data
```

**Status Updates (JSON)**:
```json
// Connection established
{"type": "connected", "client_id": "uuid", "message": "Voice communication ready"}

// Processing audio
{"type": "processing", "message": "Processing your transmission..."}

// Response complete
{"type": "response_complete", "message": "ATC response sent"}

// Error occurred
{"type": "error", "message": "Error description"}

// Heartbeat response
{"type": "pong"}
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application
│   ├── config.py                    # Configuration management
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── health.py            # Health check endpoints
│   │       └── voice.py             # WebSocket voice endpoint
│   │
│   ├── core/
│   │   ├── audio_pipeline.py        # Complete audio processing pipeline
│   │   └── websocket_manager.py     # WebSocket connection manager
│   │
│   ├── services/
│   │   ├── stt/
│   │   │   └── whisper_service.py   # Speech-to-Text
│   │   ├── tts/
│   │   │   └── tts_service.py       # Text-to-Speech
│   │   ├── llm/
│   │   │   ├── atc_agent.py         # ATC AI agent
│   │   │   └── prompts.py           # Aviation prompts
│   │   └── audio_effects/
│   │       └── filters.py           # Radio effects
│   │
│   └── models/                      # Data models (future)
│
├── pyproject.toml                   # Project dependencies
├── .env.example                     # Environment template
└── README.md                        # This file
```

## Usage Example

### Python Client

```python
import asyncio
import websockets

async def test_voice_communication():
    uri = "ws://localhost:8000/ws/voice"
    
    async with websockets.connect(uri) as websocket:
        # Send audio file
        with open("pilot_audio.wav", "rb") as f:
            audio_data = f.read()
            await websocket.send(audio_data)
        
        # Signal end of transmission
        await websocket.send('{"type": "audio_end"}')
        
        # Receive ATC response
        response = await websocket.recv()
        
        # Save response audio
        with open("atc_response.wav", "wb") as f:
            f.write(response)

asyncio.run(test_voice_communication())
```

## Aviation Communication Examples

The ATC agent uses standard ICAO phraseology:

**Pilot**: "Tower, Cessna 172 November 1234 Alpha, ready for takeoff, runway 27."

**ATC**: "Cessna 1234 Alpha, cleared for takeoff runway 27, wind 280 at 10 knots."

---

**Pilot**: "Approach, Boeing 737 United 456, requesting descent."

**ATC**: "United 456, descend and maintain flight level 250, reduce speed 250 knots."

## Troubleshooting

### Ollama Connection Error

```bash
# Make sure Ollama is running
ollama serve

# Test Ollama
curl http://localhost:11434/api/tags
```

### Whisper Model Loading Error

The first time you run the API, Whisper will download the model (~150MB for base model). This may take a few minutes.

### TTS Model Loading Error

Coqui TTS will download models on first use. Ensure you have enough disk space (~500MB).

### Audio Format Issues

The API expects WAV format audio. Ensure your audio is:
- Format: WAV
- Sample Rate: 16kHz (recommended)
- Channels: Mono or Stereo (will be converted to mono)

## Performance Tips

- Use `WHISPER_MODEL=base` for faster transcription (less accurate)
- Use `WHISPER_MODEL=small` or `medium` for better accuracy
- Disable radio effects with `ENABLE_RADIO_EFFECTS=false` for faster processing
- Use a smaller Ollama model like `llama3.2:3b` for faster responses

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run linter
ruff check app/

# Run type checker
mypy app/

# Format code
ruff format app/
```

## License

MIT
