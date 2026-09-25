"""Complete audio processing pipeline for ATC voice communication."""

import io
import logging
from dataclasses import dataclass

import soundfile as sf

from app.llm import LLMModule
from app.services.audio_effects.filters import RadioEffectsProcessor
from app.services.llm.atc_agent import ATCAgent
from app.services.llm.scenes.registry import SceneConfig
from app.services.stt.whisper_service import WhisperSTTService
from app.services.tts.tts_service import TTSService

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full audio pipeline processing run.

    Attributes:
        audio: Processed ATC response audio (WAV bytes). Empty bytes if pipeline failed.
        pilot_transcript: What the pilot said (from STT).
        atc_response: What the ATC responded with (from LLM).
        language: Detected language code (e.g. "en", "es").
    """

    audio: bytes
    pilot_transcript: str
    atc_response: str
    language: str


class AudioPipeline:
    """End-to-end audio processing pipeline for ATC communication."""

    def __init__(self, llm: LLMModule, scene: SceneConfig) -> None:
        """Initialize all pipeline components with injected LLM dependencies."""
        logger.info("Initializing audio pipeline...")

        self.stt_service = WhisperSTTService()
        self.atc_agent = ATCAgent(llm, scene)
        self.tts_service = TTSService()
        self.effects_processor = RadioEffectsProcessor()

        logger.info("Audio pipeline initialized successfully")

    async def process_audio(
        self,
        audio_data: bytes,
        context: dict | None = None,
        language: str | None = None,
    ) -> PipelineResult:
        """Process audio through the complete pipeline.

        Flow: Audio -> STT -> ATC Agent -> TTS -> Radio Effects -> Audio

        Args:
            audio_data: Input audio from pilot (WAV bytes)
            context: Optional flight context
            language: Optional language override for STT + TTS

        Returns:
            PipelineResult with processed audio and transcripts.
        """
        empty_result = PipelineResult(
            audio=b"", pilot_transcript="", atc_response="", language="en"
        )
        try:
            # Step 1: Speech to Text (with language detection)
            logger.info("Step 1: Transcribing pilot audio...")
            pilot_text, detected_language = await self.stt_service.transcribe(
                audio_data, language=language
            )

            if not pilot_text:
                logger.warning("No transcription received, returning silence")
                return empty_result

            logger.info(f"Pilot said ({detected_language}): {pilot_text}")

            # Step 2: Generate ATC Response (in detected language)
            logger.info(f"Step 2: Generating ATC response in {detected_language}...")
            atc_text = await self.atc_agent.generate_response(
                pilot_text, context, language=detected_language
            )
            logger.info(f"ATC responds: {atc_text}")

            # Step 3: Text to Speech (in detected language)
            logger.info(f"Step 3: Synthesizing ATC speech in {detected_language}...")
            atc_audio_bytes = await self.tts_service.synthesize(
                atc_text, language=detected_language
            )

            if not atc_audio_bytes:
                logger.warning("No audio synthesized, returning silence")
                return PipelineResult(
                    audio=b"",
                    pilot_transcript=pilot_text,
                    atc_response=atc_text,
                    language=detected_language,
                )

            # Step 4: Apply Radio Effects
            logger.info("Step 4: Applying radio effects...")
            atc_audio_bytes = await self._apply_effects_to_bytes(atc_audio_bytes)

            logger.info("Pipeline processing complete")
            return PipelineResult(
                audio=atc_audio_bytes,
                pilot_transcript=pilot_text,
                atc_response=atc_text,
                language=detected_language,
            )

        except Exception as e:
            logger.error(f"Error in audio pipeline: {e}", exc_info=True)
            return PipelineResult(
                audio=b"",
                pilot_transcript=empty_result.pilot_transcript,
                atc_response=empty_result.atc_response,
                language="en",
            )

    async def _apply_effects_to_bytes(self, audio_bytes: bytes) -> bytes:
        """Apply radio effects to audio bytes.

        Args:
            audio_bytes: Input audio as WAV bytes

        Returns:
            Processed audio as WAV bytes
        """
        try:
            # Load audio from bytes
            audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))

            # Apply radio effects
            processed_audio = self.effects_processor.apply_radio_effects(
                audio_array,
                sample_rate,
            )

            # Add transmission clicks
            processed_audio = self.effects_processor.add_transmission_clicks(
                processed_audio,
                sample_rate,
            )

            # Convert back to bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, processed_audio, sample_rate, format="WAV")
            return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"Error applying effects: {e}")
            return audio_bytes

    def reset_conversation(self) -> None:
        """Reset the ATC conversation state."""
        self.atc_agent.reset_conversation()
        logger.info("Conversation reset")
