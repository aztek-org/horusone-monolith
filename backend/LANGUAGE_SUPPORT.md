# Multi-Language Support

The Horus ATC backend now supports both English and Spanish for voice communication.

## Features

### Speech-to-Text (STT)
- **Auto-detection**: Automatically detects the language spoken by the pilot
- **Supported Languages**: English (en), Spanish (es)
- **Configuration**: Set `WHISPER_LANGUAGE` in `.env`

### Text-to-Speech (TTS)
- **Dynamic Response**: Responds in the same language as the pilot's transmission
- **Supported Languages**: English (en), Spanish (es)
- **Configuration**: Set `TTS_LANGUAGE` for default language

### ATC Agent (LLM)
- **Bilingual Prompts**: Uses language-specific ATC phraseology
- **Context-Aware**: Responds appropriately based on detected language
- **Professional Terminology**: Uses standard ICAO phraseology in both languages

## Configuration

Edit `backend/.env`:

```bash
# Auto-detect language from pilot's speech
WHISPER_LANGUAGE=auto

# Or force a specific language
# WHISPER_LANGUAGE=en  # English only
# WHISPER_LANGUAGE=es  # Spanish only

# Default TTS language (overridden by detected language)
TTS_LANGUAGE=en
```

## Usage Examples

### Automatic Language Detection (Recommended)

Set `WHISPER_LANGUAGE=auto` in `.env`:

```bash
WHISPER_LANGUAGE=auto
TTS_LANGUAGE=en
```

**English conversation:**
- Pilot: "Tower, Cessna 172 November 1234 Alpha, ready for takeoff, runway 27."
- ATC: "Cessna 1234 Alpha, cleared for takeoff runway 27, wind 280 at 10 knots."

**Spanish conversation:**
- Piloto: "Torre, Cessna 172 November 1234 Alpha, listo para despegar, pista 27."
- ATC: "Cessna 1234 Alpha, autorizado para despegar pista 27, viento 280 a 10 nudos."

### Force Specific Language

**English only:**
```bash
WHISPER_LANGUAGE=en
TTS_LANGUAGE=en
```

**Spanish only:**
```bash
WHISPER_LANGUAGE=es
TTS_LANGUAGE=es
```

## How It Works

1. **Pilot speaks** → Audio captured by frontend
2. **Whisper STT** → Transcribes audio and detects language
3. **ATC Agent** → Generates response using language-specific prompts
4. **gTTS** → Synthesizes speech in the detected language
5. **Radio Effects** → Applies realistic radio filters
6. **Frontend plays** → Pilot hears ATC response in their language

## Language-Specific Prompts

The system uses different prompts for each language:

### English ATC Prompt
- Uses ICAO standard phraseology
- Examples: "cleared for takeoff", "descend and maintain", "reduce speed"

### Spanish ATC Prompt  
- Uses OACI standard phraseology (Spanish ICAO)
- Examples: "autorizado para despegar", "descienda y mantenga", "reduzca velocidad"

## Supported Languages

| Language | Code | STT | TTS | ATC Agent |
|----------|------|-----|-----|-----------|
| English  | en   | ✅  | ✅  | ✅        |
| Spanish  | es   | ✅  | ✅  | ✅        |

## Technical Details

### Whisper (STT)
- Model: OpenAI Whisper
- Supports 99+ languages for transcription
- Returns detected language code
- Configured via `WHISPER_MODEL` (tiny, base, small, medium, large)

### gTTS (TTS)
- Service: Google Text-to-Speech
- Supports 100+ languages
- Free and unlimited usage
- Natural-sounding voices

### LLM Prompts
- Language-specific system prompts
- Context templates adapted per language
- Maintains aviation terminology accuracy

## Troubleshooting

### Wrong Language Detected
If Whisper incorrectly detects the language:
- Speak more clearly
- Use standard aviation terminology
- Set `WHISPER_LANGUAGE` to specific language instead of `auto`

### Mixed Language Conversations
The system handles each transmission independently:
- Each pilot message is analyzed separately
- Language can switch between transmissions
- History maintains language per exchange

### Performance Considerations
- Auto-detection adds ~0.1-0.2s latency
- Forcing a language is slightly faster
- Language detection accuracy: >95% with clear audio

## Future Enhancements

Planned language support:
- [ ] French (fr)
- [ ] German (de)  
- [ ] Portuguese (pt)
- [ ] Italian (it)
- [ ] Chinese (zh)
- [ ] Japanese (ja)

To request additional languages, please open an issue on GitHub.
