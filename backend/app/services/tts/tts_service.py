"""Text-to-Speech service using gTTS (Google Text-to-Speech)."""

import io
import logging
import os
import tempfile

import soundfile as sf
from gtts import gTTS

from app.config import get_settings

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-Speech service using gTTS."""

    def __init__(self) -> None:
        """Initialize TTS service."""
        self.settings = get_settings()
        logger.info("TTS service initialized (using gTTS)")

    async def synthesize(self, text: str, language: str = None) -> bytes:
        """Synthesize speech from text.

        Args:
            text: Text to convert to speech
            language: Language code (en, es) - defaults to config setting

        Returns:
            Audio data as WAV bytes
        """
        try:
            # Use provided language or fall back to config
            lang = language or self.settings.tts_language
            logger.info(f"Synthesizing text in {lang}: {text}")

            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                mp3_path = mp3_file.name

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                wav_path = wav_file.name

            try:
                # Generate speech with gTTS
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(mp3_path)

                # Convert MP3 to WAV using soundfile
                # Read the MP3 (requires ffmpeg)
                from pydub import AudioSegment

                audio = AudioSegment.from_mp3(mp3_path)

                # Export as WAV
                audio.export(wav_path, format="wav")

                # Read WAV file
                audio_data, sample_rate = sf.read(wav_path)

                # Convert to bytes
                audio_buffer = io.BytesIO()
                sf.write(audio_buffer, audio_data, sample_rate, format="WAV")
                audio_bytes = audio_buffer.getvalue()

                logger.info(f"Synthesized {len(audio_bytes)} bytes of audio")
                return audio_bytes

            finally:
                # Clean up temp files
                if os.path.exists(mp3_path):
                    os.unlink(mp3_path)
                if os.path.exists(wav_path):
                    os.unlink(wav_path)

        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            # Return empty audio on error
            return b""

    async def synthesize_streaming(
        self, text: str, language: str = None
    ) -> list[bytes]:
        """Synthesize speech in chunks for streaming.

        Args:
            text: Text to convert to speech
            language: Language code (en, es) - defaults to config setting

        Returns:
            List of audio chunk bytes
        """
        # For now, just return the full audio
        audio_bytes = await self.synthesize(text, language)

        # Split into chunks for streaming
        chunk_size = 4096
        chunks = [
            audio_bytes[i : i + chunk_size]
            for i in range(0, len(audio_bytes), chunk_size)
        ]

        return chunks
