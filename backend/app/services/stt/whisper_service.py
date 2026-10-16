"""Speech-to-Text service using Whisper."""

import io
import logging
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import whisper

from app.config import get_settings

logger = logging.getLogger(__name__)


class WhisperSTTService:
    """Speech-to-Text service using OpenAI Whisper."""

    def __init__(self) -> None:
        """Initialize Whisper model."""
        self.settings = get_settings()
        logger.info(f"Loading Whisper model: {self.settings.whisper_model}")
        self.model = whisper.load_model(self.settings.whisper_model)
        logger.info("Whisper model loaded successfully")
        self._ffmpeg_available: bool | None = None

    async def transcribe(self, audio_data: bytes, language: str | None = None) -> tuple[str, str]:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (WAV, WebM, or raw PCM format)
            language: Optional language override (None uses config default)

        Returns:
            Tuple of (transcribed text, detected language code)
        """
        try:
            audio_array = None
            sample_rate = 16000

            # Detect audio format by magic bytes
            is_webm = audio_data[:4] == b"\x1aE\xdf\xa3"

            # Try to read as a standard audio file (WAV, etc.)
            try:
                audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
                logger.debug(f"Successfully read audio file: {sample_rate}Hz")
            except Exception as read_error:
                logger.debug(f"Could not read as audio file: {read_error}")

                if is_webm:
                    logger.info("Detected WebM/Opus format — converting via pydub+ffmpeg")
                try:
                    from pydub import AudioSegment

                    audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))

                    samples = np.array(audio_segment.get_array_of_samples())
                    sample_rate = audio_segment.frame_rate

                    if audio_segment.sample_width == 2:
                        audio_array = samples.astype(np.float32) / 32768.0
                    elif audio_segment.sample_width == 4:
                        audio_array = samples.astype(np.float32) / 2147483648.0
                    else:
                        audio_array = samples.astype(np.float32)

                    if audio_segment.channels == 2:
                        audio_array = audio_array.reshape((-1, 2)).mean(axis=1)

                    logger.info(f"Converted audio using pydub: {sample_rate}Hz")

                except Exception as pydub_error:
                    if is_webm and not self._check_ffmpeg():
                        logger.error(
                            "WebM/Opus audio received but ffmpeg is NOT installed — "
                            "install ffmpeg to enable voice transcription"
                        )
                        return "", "en"

                    logger.error(f"Could not convert audio with pydub: {pydub_error}")

                    logger.warning("Attempting to treat as raw PCM data at 16kHz")
                    audio_array = (
                        np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                    )
                    sample_rate = 16000

            if audio_array is None:
                logger.error("Failed to process audio data")
                return ""

            # Ensure mono audio
            if len(audio_array.shape) > 1:
                audio_array = np.mean(audio_array, axis=1)

            # Whisper expects 16kHz sample rate
            if sample_rate != 16000:
                logger.info(f"Resampling from {sample_rate}Hz to 16000Hz")
                # Simple resampling (for production, use librosa or scipy)
                from scipy import signal

                number_of_samples = int(len(audio_array) * 16000 / sample_rate)
                audio_array = signal.resample(audio_array, number_of_samples)
                sample_rate = 16000

            # Create temporary file for Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                sf.write(tmp_file.name, audio_array, sample_rate)
                tmp_path = Path(tmp_file.name)

            try:
                effective_language = language or (
                    None
                    if self.settings.whisper_language == "auto"
                    else self.settings.whisper_language
                )

                result = self.model.transcribe(
                    str(tmp_path),
                    language=effective_language or None,
                    task="transcribe",
                    fp16=False,
                )

                transcription = result["text"].strip()
                detected_language = result.get("language", "en")
                logger.info(f"Transcription ({detected_language}): {transcription}")
                return transcription, detected_language

            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return "", "en"

    async def transcribe_stream(
        self, audio_chunks: list[bytes], language: str | None = None
    ) -> tuple[str, str]:
        """Transcribe a stream of audio chunks.

        Args:
            audio_chunks: List of audio byte chunks
            language: Optional language override

        Returns:
            Tuple of (transcribed text, detected language code)
        """
        combined_audio = b"".join(audio_chunks)
        return await self.transcribe(combined_audio, language=language)

    def _check_ffmpeg(self) -> bool:
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available
        try:
            import subprocess

            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
            self._ffmpeg_available = True
        except Exception:
            self._ffmpeg_available = False
        return self._ffmpeg_available
