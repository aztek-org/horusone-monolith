---
name: Debug Audio Pipeline
description: >
  Step-by-step checklist for debugging voice communication issues in the Horus
  STT → LLM → TTS → Radio Effects pipeline, with service verification and log analysis.
---

# Debug the Audio Pipeline

Use this skill when voice communication is not working correctly in Horus.

## Pipeline Overview

```
Microphone (client)
  ↓ WebM/Opus via WebSocket
FastAPI WebSocket (app/api/routes/voice.py)
  ↓ AudioPipeline.process_audio()
Whisper STT → transcript
  ↓ ATCAgent.get_response(transcript)
LangChain + Ollama → ATC response text
  ↓ TTSService.synthesize(text)
Audio WAV bytes
  ↓ AudioEffectsFilter.apply_radio_effects()
Processed WAV → WebSocket → Browser playback
```

## Debug Checklist

### Step 1: Verify all services

```bash
curl http://localhost:8000/health/ready
# Check: ollama, whisper, tts all true
```

- **Ollama**: `ollama serve` + `ollama list`
- **Whisper**: downloads on first use — check disk space
- **TTS**: falls back to gTTS if Coqui unavailable

### Step 2: WebSocket connection

Browser DevTools → Network → WS tab:
- URL: `ws://localhost:8000/ws/voice` (dev) or `NUXT_PUBLIC_WS_URL`
- Look for `{ "type": "connected" }` message

### Step 3: Audio recording

Console should show `Recording started` / `Audio sent to server`.
Microphone requires `https://` or `localhost`.

### Step 4: STT (Whisper)

Backend logs: `Transcribing audio...` → `Transcript: "..."`.
If empty/`[BLANK_AUDIO]`: check audio format conversion or try louder input.

### Step 5: LLM (Ollama)

Backend logs: `Sending to LLM` → `LLM Response`.
Test directly: `ollama run llama3`. Check `OLLAMA_LLM_MODEL` matches installed model.

### Step 6: TTS

Backend logs: `Synthesizing TTS` → `TTS complete, N bytes`.
Check `TTS_LANGUAGE` matches the language. gTTS fallback needs internet.

### Step 7: Audio effects

Disable to isolate: `ENABLE_RADIO_EFFECTS=false` in `.env`.
If that fixes it, lower `NOISE_LEVEL` and `STATIC_LEVEL`.

### Step 8: Browser playback

Look for `NotAllowedError` — user gesture required before `Audio.play()`.

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/core/audio_pipeline.py` | Pipeline orchestration |
| `backend/app/services/stt/whisper_service.py` | STT |
| `backend/app/services/llm/atc_agent.py` | LLM agent |
| `backend/app/services/tts/tts_service.py` | TTS |
| `backend/app/services/audio_effects/filters.py` | Radio effects |
| `frontend/app/composables/useVoiceComm.ts` | WebSocket client |

## Debug Commands

```bash
# Test Ollama
curl http://localhost:11434/api/generate -d '{"model": "llama3", "prompt": "test", "stream": false}'

# Test Whisper
python -c "import whisper; m = whisper.load_model('base'); print('OK')"

# Debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```
