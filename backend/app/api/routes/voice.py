"""WebSocket route for voice communication."""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audio_pipeline import AudioPipeline
from app.core.websocket_manager import manager
from app.db.repositories.session_repo import TrainingSessionRepository
from app.db.repositories.voice_log_repo import VoiceLogRepository
from app.db.session import get_session_factory
from app.schemas.training_session import TrainingSessionCreate
from app.schemas.voice_log import VoiceLogCreate

logger = logging.getLogger(__name__)

router = APIRouter()

# Global audio pipeline instance (lazy-initialized)
audio_pipeline: AudioPipeline | None = None
_session_repo = TrainingSessionRepository()
_voice_log_repo = VoiceLogRepository()


def get_audio_pipeline() -> AudioPipeline:
    """Get or create the audio pipeline instance."""
    global audio_pipeline
    if audio_pipeline is None:
        audio_pipeline = AudioPipeline()
    return audio_pipeline


async def _persist_voice_exchange(
    db_session_id: int,
    pilot_transcript: str,
    atc_response: str,
) -> None:
    """Persist a pilot/ATC exchange to the database.

    Silently logs and swallows DB errors so a DB outage never breaks voice comms.

    Args:
        db_session_id: TrainingSession primary key.
        pilot_transcript: What the pilot said.
        atc_response: What the ATC responded.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            await _voice_log_repo.create(
                db,
                VoiceLogCreate(session_id=db_session_id, role="pilot", transcript=pilot_transcript),
            )
            await _voice_log_repo.create(
                db,
                VoiceLogCreate(session_id=db_session_id, role="atc", transcript=atc_response),
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"Could not persist voice logs (DB unavailable?): {e}")


@router.websocket("/ws/voice")
async def voice_communication(websocket: WebSocket) -> None:
    """WebSocket endpoint for bi-directional voice communication.

    Protocol:
    1. Client sends audio chunks as binary data
    2. Server processes audio through pipeline
    3. Server sends audio response back as binary data
    4. Server also sends JSON status updates

    Args:
        websocket: WebSocket connection
    """
    client_id = str(uuid.uuid4())
    pipeline = get_audio_pipeline()

    await manager.connect(websocket, client_id)
    logger.info(f"Voice communication started for client {client_id}")

    # Create a TrainingSession in the DB (best-effort — voice still works if DB is down)
    db_session_id: int | None = None
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            training_session = await _session_repo.create(
                db,
                TrainingSessionCreate(client_id=client_id, language="auto"),
            )
            db_session_id = training_session.id
            await db.commit()
            logger.info(f"Created TrainingSession id={db_session_id} for client {client_id}")
    except Exception as e:
        logger.warning(f"Could not create TrainingSession (DB unavailable?): {e}")

    # Send connection confirmation
    await manager.send_json(client_id, {
        "type": "connected",
        "client_id": client_id,
        "message": "Voice communication ready",
    })

    audio_chunks: list[bytes] = []

    try:
        while True:
            # Receive data from client
            data = await websocket.receive()

            # Handle binary audio data
            if "bytes" in data:
                audio_chunk = data["bytes"]
                audio_chunks.append(audio_chunk)
                logger.debug(f"Received audio chunk: {len(audio_chunk)} bytes")

            # Handle text/JSON messages
            elif "text" in data:
                message = json.loads(data["text"])

                if message.get("type") == "audio_end":
                    # Client finished sending audio, process it
                    logger.info(f"Processing {len(audio_chunks)} audio chunks")

                    # Send processing status
                    await manager.send_json(client_id, {
                        "type": "processing",
                        "message": "Processing your transmission...",
                    })

                    # Combine audio chunks and process
                    if audio_chunks:
                        combined_audio = b"".join(audio_chunks)
                        audio_chunks = []

                        result = await pipeline.process_audio(combined_audio)

                        if result.audio:
                            # Persist voice exchange to DB (non-blocking, best-effort)
                            if db_session_id and result.pilot_transcript:
                                await _persist_voice_exchange(
                                    db_session_id,
                                    result.pilot_transcript,
                                    result.atc_response,
                                )

                            await manager.send_audio(client_id, result.audio)
                            await manager.send_json(client_id, {
                                "type": "response_complete",
                                "message": "ATC response sent",
                            })
                        else:
                            await manager.send_json(client_id, {
                                "type": "error",
                                "message": "No response generated",
                            })

                elif message.get("type") == "reset":
                    pipeline.reset_conversation()
                    await manager.send_json(client_id, {
                        "type": "reset_complete",
                        "message": "Conversation reset",
                    })

                elif message.get("type") == "ping":
                    await manager.send_json(client_id, {"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Error in voice communication: {e}", exc_info=True)
        manager.disconnect(client_id)
