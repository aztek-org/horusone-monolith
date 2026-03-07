# Skill: Debug the Audio Pipeline

Use this skill when voice communication is not working correctly in Horus.

## Pipeline Overview

```
Microphone (client)
  ↓ WebM/Opus audio via WebSocket binary message
FastAPI WebSocket handler (app/api/routes/voice.py)
  ↓ AudioPipeline.process_audio()
Whisper STT → transcript text
  ↓ ATCAgent.get_response(transcript)
LangChain + Ollama → ATC response text
  ↓ TTSService.synthesize(text)
Audio WAV bytes
  ↓ AudioEffectsFilter.apply_radio_effects(audio)
Processed WAV bytes
  ↓ WebSocket binary message
Browser audio playback (client)
```

## Step-by-Step Debug Checklist

### Step 1: Verify all services are running

```bash
# Check backend health
curl http://localhost:8000/health/ready

# Should return something like:
# { "status": "ready", "services": { "ollama": true, "whisper": true, "tts": true } }
```

If any service is `false`:
- **Ollama**: Run `ollama serve` in a separate terminal. Then `ollama list` to verify your model exists.
- **Whisper**: The model downloads on first use. Check for disk space. Check backend logs for download errors.
- **TTS (Coqui)**: Also downloads on first use. Falls back to gTTS if unavailable — check logs.

### Step 2: Check the WebSocket connection

In browser DevTools → Network → WS tab:
- Is the WebSocket connecting to the right URL? Should be `ws://localhost:8000/ws/voice` (dev) or the configured `NUXT_PUBLIC_WS_URL` (production).
- Is the initial `{ "type": "connected" }` message received?

If not connecting:
- Check CORS: Backend `.env` `CORS_ORIGINS` must include the frontend origin.
- Check firewall: Port 8000 must be open on VPS.

### Step 3: Check audio recording in browser

In browser console, look for:
```
Recording started
Audio sent to server
```

If you see `Microphone access denied`:
- Browser must be on `https://` or `localhost` for microphone access.
- User must grant permission.

### Step 4: Check STT (Whisper)

Look for these backend log lines:
```
Transcribing audio...
Transcript: "[what the pilot said]"
```

If transcript is empty or `[BLANK_AUDIO]`:
- Audio format may be wrong — Whisper expects WAV/PCM. The client sends WebM which is converted.
- Check `soundfile` / `pydub` conversion in `audio_pipeline.py`.
- Try a louder or longer utterance.

### Step 5: Check LLM (Ollama)

Look for:
```
Sending to LLM: "[transcript]"
LLM Response: "[atc response]"
```

If LLM is slow or errors:
- Run `ollama run llama3` in terminal to test the model directly.
- Increase timeout in `atc_agent.py` if needed.
- Check `OLLAMA_LLM_MODEL` in `.env` — must match an installed model.

### Step 6: Check TTS

Look for:
```
Synthesizing TTS for: "[text]"
TTS complete, [N] bytes generated
```

If audio sounds wrong or robotic:
- Coqui TTS is primary — check it downloaded correctly.
- If falling back to gTTS, it requires internet connectivity.
- Check `TTS_LANGUAGE` in `.env` matches the language being spoken.

### Step 7: Check audio effects

```python
# In backend .env:
ENABLE_RADIO_EFFECTS=false  # Disable to isolate issues
```

If disabling effects fixes the audio, the scipy filter is causing clipping or distortion.
Adjust `NOISE_LEVEL` and `STATIC_LEVEL` to lower values.

### Step 8: Check audio playback in browser

Look for:
```
Received audio response
Playing ATC response
```

If audio arrives but doesn't play:
- User gesture required: Browser needs a user interaction before allowing `Audio.play()`.
- Check for `NotAllowedError` in console.

## Key Files for Debugging

| File | What to look at |
|------|----------------|
| `backend/app/core/audio_pipeline.py` | Full pipeline orchestration |
| `backend/app/services/stt/whisper_service.py` | STT transcription |
| `backend/app/services/llm/atc_agent.py` | LLM agent + conversation history |
| `backend/app/services/tts/tts_service.py` | TTS synthesis |
| `backend/app/services/audio_effects/filters.py` | Radio effect filtering |
| `frontend/app/composables/useVoiceComm.ts` | WebSocket client + audio recording |

## Useful Backend Debug Commands

```bash
# Test Ollama directly
curl http://localhost:11434/api/generate -d '{"model": "llama3", "prompt": "ATC clearance test", "stream": false}'

# Test Whisper Python
cd backend
python -c "import whisper; m = whisper.load_model('base'); print('Whisper OK')"

# Run backend with debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```
