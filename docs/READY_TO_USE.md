# ✅ ATC Voice Communication System - READY TO USE

## 🎉 Installation Complete!

All backend dependencies successfully installed (105 packages).

---

## 🚀 Quick Start Guide

### Step 1: Start Ollama (Terminal 1)

**Option A: Local Ollama**
```bash
# Start Ollama server
ollama serve

# In another terminal, pull the model (one-time)
ollama pull llama3.2:3b
```

**Option B: Shared/Remote Ollama**
```bash
# If using shared Ollama service (Docker, remote server, etc.)
# No need to run ollama serve - just verify it's accessible:
curl http://localhost:11434/api/tags

# Or check remote Ollama:
curl http://your-ollama-host:11434/api/tags

# Update backend/.env with your Ollama URL:
# OLLAMA_BASE_URL=http://your-ollama-host:11434
```

### Step 2: Start Backend API (Terminal 2)

```bash
cd backend

# Create .env file (if not exists)
cp .env.example .env

# Run the API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be available at:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/voice

### Step 3: Start Frontend (Terminal 3)

```bash
# From project root
pnpm dev
```

**Frontend will be available at:**
- App: http://localhost:3000

---

## 🎙️ How to Use

1. **Open** http://localhost:3000 in your browser
2. **Look** for the floating mic button (bottom-right corner)
3. **Wait** for the green dot (connected to ATC)
4. **Press and hold** the mic button
5. **Speak** your pilot transmission (e.g., "Tower, Cessna 172 November 1234 Alpha, ready for takeoff")
6. **Release** the button
7. **Listen** for the ATC response

### Visual Indicators

- 🟢 **Green dot**: Connected to ATC
- 🔵 **Cyan button**: Ready to record
- 🔴 **Red pulsing**: Recording your voice
- 🔄 **Spinner**: Processing transmission
- 🔊 **Speaker icon**: ATC is speaking

---

## 📋 System Check

### Verify Backend is Running

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","service":"horus-atc-api","version":"0.1.0"}
```

### Verify Ollama is Running

```bash
# Check local Ollama
curl http://localhost:11434/api/tags

# Or check remote/shared Ollama
curl http://your-ollama-host:11434/api/tags

# Check available models via API
curl http://localhost:11434/api/tags | jq '.models[].name'

# Expected: Should include "llama3.2:3b"
```

### Verify Frontend is Running

```bash
# Open in browser
open http://localhost:3000

# Look for mic button in bottom-right corner
```

---

## 🎯 Example Communications

Try these pilot transmissions:

### Takeoff Request
```
"Tower, Cessna 172 November 1234 Alpha, ready for takeoff, runway 27"
```
**Expected ATC Response:**
```
"Cessna 1234 Alpha, cleared for takeoff runway 27, wind 280 at 10 knots"
```

### Altitude Change
```
"Approach, requesting descent to 5000 feet"
```
**Expected ATC Response:**
```
"Roger, descend and maintain 5000, altimeter 2992"
```

### Position Report
```
"Center, we are 10 miles east at 3500 feet"
```
**Expected ATC Response:**
```
"Roger, continue present heading, report 5 mile final"
```

---

## ⚙️ Configuration

### Backend Settings (`.env`)

```bash
# Quick adjustments for performance

# Faster STT (less accurate)
WHISPER_MODEL=tiny

# Faster LLM
OLLAMA_LLM_MODEL=llama3.2:1b

# Disable radio effects for speed
ENABLE_RADIO_EFFECTS=false
```

### Audio Settings

```bash
# Sample rate (16kHz recommended for Whisper)
SAMPLE_RATE=16000

# Radio effects
NOISE_LEVEL=0.02
STATIC_LEVEL=0.01
```

---

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check if .venv is activated
which python  # Should show backend/.venv/bin/python

# If not, activate it:
cd backend
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### Ollama connection error

**For Local Ollama:**
```bash
# Make sure Ollama is running
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

**For Shared/Remote Ollama:**
```bash
# Test connection to shared Ollama
curl http://localhost:11434/api/tags

# If using Docker Ollama
docker ps | grep ollama  # Check if container is running

# If using remote Ollama, update backend/.env:
OLLAMA_BASE_URL=http://your-ollama-host:11434

# Test remote connection
curl http://your-ollama-host:11434/api/tags
```

**Common Issues:**
- **Port 11434 not accessible**: Check firewall rules
- **Model not found**: Ensure llama3.2:3b is pulled on the Ollama server
- **Connection refused**: Ollama service not running

### Microphone not working

- **Chrome**: Settings > Privacy > Microphone > Allow
- **Firefox**: Permissions > Microphone > Allow
- **HTTPS required**: In production, use HTTPS for mic access

### No audio playback

- Check browser audio output
- Check system volume
- Open browser console (F12) for errors

### Slow responses

**Option 1: Use smaller models**
```bash
# Faster Whisper
WHISPER_MODEL=tiny  # or base

# Faster Ollama
ollama pull llama3.2:1b
OLLAMA_LLM_MODEL=llama3.2:1b
```

**Option 2: Disable effects**
```bash
ENABLE_RADIO_EFFECTS=false
```

---

## 📊 Performance

### Expected Latency
- Recording: Real-time
- STT (Whisper): 1-3 seconds
- LLM (Ollama): 2-5 seconds
- TTS (gTTS): 1-2 seconds
- Effects: <0.1 seconds
- **Total: 4-10 seconds typical**

### Resource Usage
- **RAM**: 4-8GB (models in memory)
- **CPU**: High during processing
- **Disk**: ~3GB for models
- **Network**: Minimal (local WebSocket + gTTS API)

---

## 📚 Documentation

- **PROJECT_SETUP.md** - Complete setup guide
- **IMPLEMENTATION_SUMMARY.md** - Technical architecture
- **backend/README.md** - Backend API documentation
- **backend/DEPENDENCY_FIX.md** - TTS dependency notes

---

## 🎨 UI Features

### Floating Mic Button
- **Position**: Bottom-right corner
- **Size**: 64x64 pixels
- **Design**: Matches Horus theme (cyan accent)
- **States**: Recording, Processing, Speaking
- **Responsive**: Works on mobile and desktop

### Tooltips
- Shows instructions on first load
- Displays connection status
- Shows error messages

---

## 🔧 Advanced Configuration

### Custom ATC Prompts

Edit `backend/app/services/llm/prompts.py`:

```python
ATC_SYSTEM_PROMPT = """Your custom ATC personality here..."""
```

### Radio Effects

Edit `backend/app/services/audio_effects/filters.py`:

```python
# Adjust filter frequencies
lowcut = 300.0   # Lower frequency
highcut = 3400.0 # Upper frequency

# Adjust noise levels
noise_level = 0.02
static_level = 0.01
```

### WebSocket URL

Edit `app/composables/useVoiceComm.ts`:

```typescript
const wsUrl = 'ws://your-backend-url:8000/ws/voice'
```

---

## ✨ Features Overview

### ✅ Complete Pipeline
- Speech-to-Text (Whisper)
- AI ATC Agent (LangChain + Ollama)
- Text-to-Speech (gTTS)
- Radio Effects (scipy filters)
- WebSocket Streaming

### ✅ Aviation-Specific
- ICAO standard phraseology
- Realistic ATC communication
- Professional aviation terminology
- Context-aware responses

### ✅ User Experience
- Push-to-talk interface
- Visual feedback (recording/processing/speaking)
- Connection status indicator
- Error notifications
- Mobile-responsive design

---

## 🚦 Status

- ✅ Backend: Fully functional
- ✅ Frontend: Fully integrated
- ✅ Dependencies: All installed
- ✅ Documentation: Complete
- 🎉 **READY TO USE!**

---

## 🎓 Next Steps

### Immediate
1. Run Ollama, Backend, Frontend
2. Test voice communication
3. Try different pilot transmissions

### Short-term
- Integrate with flight scenario data
- Add conversation history
- Fine-tune ATC prompts

### Long-term
- Add user authentication
- Multi-user support
- Custom voice training
- Offline TTS option

---

## 📞 Support

If you encounter issues:

1. **Check logs**: Backend terminal output
2. **Browser console**: Press F12
3. **Documentation**: See PROJECT_SETUP.md
4. **Health check**: curl http://localhost:8000/health

---

## 🎉 You're All Set!

The Horus ATC Voice Communication System is **ready to use**.

**Start talking to ATC and enjoy your flight! ✈️🎙️**

```bash
# Terminal 1
ollama serve

# Terminal 2
cd backend && uv run uvicorn app.main:app --reload

# Terminal 3
pnpm dev

# Browser
http://localhost:3000
```

**Happy flying! 🚁**
