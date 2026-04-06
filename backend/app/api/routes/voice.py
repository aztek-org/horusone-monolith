"""WebSocket route for voice communication."""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audio_pipeline import AudioPipeline
from app.core.websocket_manager import manager
from app.db.repositories.seat_repo import SeatRepository
from app.db.repositories.session_repo import TrainingSessionRepository
from app.db.repositories.voice_log_repo import VoiceLogRepository
from app.db.session import get_session_factory
from app.middleware.auth import get_current_user_ws
from app.schemas.training_session import TrainingSessionCreate
from app.schemas.voice_log import VoiceLogCreate
from app.services.user_sync import sync_user_from_token

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_AUDIO_CHUNK_BYTES = 2 * 1024 * 1024
MAX_AUDIO_MESSAGE_BYTES = 10 * 1024 * 1024

# Global audio pipeline instance (lazy-initialized)
audio_pipeline: AudioPipeline | None = None
_session_repo = TrainingSessionRepository()
_voice_log_repo = VoiceLogRepository()
_seat_repo = SeatRepository()


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

    Requires authentication (token query param) and an **active seat**.
    Users without a seat receive a close frame with code 4003.

    Protocol:
    1. Client sends audio chunks as binary data
    2. Server processes audio through pipeline
    3. Server sends audio response back as binary data
    4. Server also sends JSON status updates

    Args:
        websocket: WebSocket connection
    """
    # --- Authenticate ---
    try:
        token_user = await get_current_user_ws(websocket)
    except Exception:
        # get_current_user_ws already closes the socket on failure
        return

    # --- Verify active seat (platform-admins bypass) ---
    if "platform-admin" not in token_user.roles:
        try:
            session_factory = get_session_factory()
            async with session_factory() as db:
                local_user = await sync_user_from_token(db, token_user)
                seats = await _seat_repo.get_user_seats(db, local_user.id)
                active_seats = [s for s in seats if s.is_active]
                if not active_seats:
                    await websocket.accept()
                    await websocket.send_json({
                        "type": "error",
                        "code": "NO_ACTIVE_SEAT",
                        "message": "You do not have an active seat. Contact your organization admin.",
                    })
                    await websocket.close(code=4003, reason="No active seat")
                    return
        except Exception as e:
            logger.error("Seat check failed during WS connect: %s", e)
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Could not verify seat status",
            })
            await websocket.close(code=4500, reason="Internal error")
            return

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
    await manager.send_json(
        client_id,
        {
            "type": "connected",
            "client_id": client_id,
            "message": "Voice communication ready",
        },
    )

    audio_chunks: list[bytes] = []
    current_audio_bytes = 0

    try:
        while True:
            # Receive data from client
            data = await websocket.receive()

            # Handle binary audio data
            if "bytes" in data and data["bytes"] is not None:
                audio_chunk = data["bytes"]
                if len(audio_chunk) > MAX_AUDIO_CHUNK_BYTES:
                    await manager.send_json(
                        client_id,
                        {
                            "type": "error",
                            "code": "AUDIO_CHUNK_TOO_LARGE",
                            "message": (
                                "Audio chunk exceeds size limit "
                                f"({MAX_AUDIO_CHUNK_BYTES} bytes)"
                            ),
                        },
                    )
                    await websocket.close(code=4009, reason="Audio chunk too large")
                    manager.disconnect(client_id)
                    return

                current_audio_bytes += len(audio_chunk)
                if current_audio_bytes > MAX_AUDIO_MESSAGE_BYTES:
                    await manager.send_json(
                        client_id,
                        {
                            "type": "error",
                            "code": "AUDIO_PAYLOAD_TOO_LARGE",
                            "message": (
                                "Audio transmission exceeds size limit "
                                f"({MAX_AUDIO_MESSAGE_BYTES} bytes)"
                            ),
                        },
                    )
                    await websocket.close(code=4009, reason="Audio payload too large")
                    manager.disconnect(client_id)
                    return

                audio_chunks.append(audio_chunk)
                logger.debug(f"Received audio chunk: {len(audio_chunk)} bytes")

            # Handle text/JSON messages
            elif "text" in data and data["text"] is not None:
                try:
                    message = json.loads(data["text"])
                except json.JSONDecodeError:
                    await manager.send_json(
                        client_id,
                        {
                            "type": "error",
                            "code": "INVALID_JSON",
                            "message": "Invalid JSON message format",
                        },
                    )
                    continue

                if message.get("type") == "audio_end":
                    # Client finished sending audio, process it
                    logger.info(f"Processing {len(audio_chunks)} audio chunks")

                    # Send processing status
                    await manager.send_json(
                        client_id,
                        {
                            "type": "processing",
                            "message": "Processing your transmission...",
                        },
                    )

                    # Combine audio chunks and process
                    if audio_chunks:
                        combined_audio = b"".join(audio_chunks)
                        audio_chunks = []
                        current_audio_bytes = 0

                        logger.info(
                            f"Processing {len(combined_audio)} bytes of audio"
                        )
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
                            await manager.send_json(
                                client_id,
                                {
                                    "type": "response_complete",
                                    "message": "ATC response sent",
                                },
                            )
                        else:
                            detail = "No response generated"
                            if not result.pilot_transcript:
                                detail = "Could not transcribe audio (STT failed)"
                            elif not result.atc_response:
                                detail = "LLM did not generate a response"
                            else:
                                detail = "Text-to-speech failed to produce audio"
                            logger.warning(
                                f"Pipeline returned no audio: {detail} "
                                f"(transcript={result.pilot_transcript!r}, "
                                f"atc={result.atc_response!r})"
                            )
                            await manager.send_json(
                                client_id,
                                {
                                    "type": "error",
                                    "message": detail,
                                },
                            )

                elif message.get("type") == "reset":
                    pipeline.reset_conversation()
                    await manager.send_json(
                        client_id,
                        {
                            "type": "reset_complete",
                            "message": "Conversation reset",
                        },
                    )

                elif message.get("type") == "ping":
                    await manager.send_json(client_id, {"type": "pong"})

                else:
                    await manager.send_json(
                        client_id,
                        {
                            "type": "error",
                            "code": "UNSUPPORTED_MESSAGE_TYPE",
                            "message": "Unsupported message type",
                        },
                    )

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Error in voice communication: {e}", exc_info=True)
        manager.disconnect(client_id)
