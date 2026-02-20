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

    async def transcribe(self, audio_data: bytes) -> tuple[str, str]:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (WAV, WebM, or raw PCM format)

        Returns:
            Tuple of (transcribed text, detected language code)
        """
        try:
            audio_array = None
            sample_rate = 16000  # Default sample rate

            # Try to read as a standard audio file (WAV, etc.)
            try:
                audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
                logger.debug(f"Successfully read audio file: {sample_rate}Hz")
            except Exception as read_error:
                logger.warning(f"Could not read as audio file: {read_error}")

                # Try using pydub to handle various formats (WebM, Opus, etc.)
                try:
                    from pydub import AudioSegment

                    # Try to load with pydub
                    audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))

                    # Convert to numpy array
                    samples = np.array(audio_segment.get_array_of_samples())
                    sample_rate = audio_segment.frame_rate

                    # Convert to float32 and normalize
                    if audio_segment.sample_width == 2:  # 16-bit
                        audio_array = samples.astype(np.float32) / 32768.0
                    elif audio_segment.sample_width == 4:  # 32-bit
                        audio_array = samples.astype(np.float32) / 2147483648.0
                    else:
                        audio_array = samples.astype(np.float32)

                    # Handle stereo
                    if audio_segment.channels == 2:
                        audio_array = audio_array.reshape((-1, 2)).mean(axis=1)

                    logger.info(f"Converted audio using pydub: {sample_rate}Hz")

                except Exception as pydub_error:
                    logger.error(f"Could not convert audio with pydub: {pydub_error}")

                    # Last resort: assume raw PCM data at 16kHz mono
                    logger.warning("Attempting to treat as raw PCM data at 16kHz")
                    audio_array = (
                        np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                        / 32768.0
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
                # Transcribe using Whisper
                # Use auto-detection if configured, otherwise use specified language
                language_param = (
                    None
                    if self.settings.whisper_language == "auto"
                    else self.settings.whisper_language
                )

                result = self.model.transcribe(
                    str(tmp_path),
                    language=language_param,
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

    async def transcribe_stream(self, audio_chunks: list[bytes]) -> tuple[str, str]:
        """Transcribe a stream of audio chunks.

        Args:
            audio_chunks: List of audio byte chunks

        Returns:
            Tuple of (transcribed text, detected language code)
        """
        # Combine all chunks
        combined_audio = b"".join(audio_chunks)
        return await self.transcribe(combined_audio)
