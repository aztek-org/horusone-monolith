"""WebSocket route for voice communication."""

import json
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import delete

from app.core.audio_pipeline import AudioPipeline, PipelineResult
from app.core.websocket_manager import manager
from app.db.repositories.seat_repo import SeatRepository
from app.db.repositories.voice_log_repo import VoiceLogRepository
from app.db.session import get_session_factory
from app.middleware.auth import TokenUser, get_current_user_ws
from app.models.training_session import TrainingSession
from app.schemas.voice_log import VoiceLogCreate
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.training_sessions.audit import record_session_created
from app.services.training_sessions.types import (
    SendTransmissionCommand,
    SessionModule,
    StartSessionCommand,
)
from app.services.user_sync import sync_user_from_token

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_AUDIO_CHUNK_BYTES = 2 * 1024 * 1024
MAX_AUDIO_MESSAGE_BYTES = 10 * 1024 * 1024

_voice_log_repo = VoiceLogRepository()
_seat_repo = SeatRepository()


def _org_id_from_token(token_user: TokenUser) -> uuid.UUID | None:
    """Return the caller's organization as a UUID, or ``None`` when unscoped."""
    raw = token_user.organization_id
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        logger.warning("Token carried a non-UUID organization_id; treating as unscoped")
        return None


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


async def _discard_session(db_session_id: int) -> None:
    """Remove a session row that could not be started, so no orphan is left behind.

    The row must be committed before the Session module can record anything
    against it, so a failed start is compensated for by deleting the row here
    rather than leaving a session that claims to exist but has no provenance.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            await db.execute(
                delete(TrainingSession).where(TrainingSession.id == db_session_id)
            )
            await db.commit()
    except Exception as e:
        logger.warning("Could not discard training session %s: %s", db_session_id, e)


@dataclass(frozen=True)
class _ExchangeOutcome:
    """Result of one pilot transmission, plus why no audio was produced."""

    result: PipelineResult
    pending_instructor: bool = False


async def _process_exchange(
    pipeline: AudioPipeline,
    session_module: SessionModule,
    org_id: uuid.UUID | None,
    db_session_id: int,
    audio: bytes,
    language: str | None,
) -> _ExchangeOutcome:
    """Answer one pilot transmission through the persisted training Session.

    The pilot transmission is transcribed, handed to the Session module that
    owns the session's graph state, and the returned ATC response is spoken
    back.  Any citations the module returns are logged here; the module records
    the same provenance as a trace event against the session.
    """
    pilot_transcript, detected_language = await pipeline.transcribe(audio, language=language)
    if not pilot_transcript:
        logger.warning("No transcription received, returning silence")
        return _ExchangeOutcome(
            PipelineResult(
                audio=b"", pilot_transcript="", atc_response="", language=detected_language or "en"
            )
        )

    exchange = await session_module.send(
        SendTransmissionCommand(
            org_id=org_id,
            session_id=db_session_id,
            pilot_message=pilot_transcript,
        )
    )
    if exchange.pending_instructor:
        logger.info("Exchange for session %s is awaiting instructor review", db_session_id)
        return _ExchangeOutcome(
            PipelineResult(
                audio=b"",
                pilot_transcript=pilot_transcript,
                atc_response="",
                language=detected_language,
            ),
            pending_instructor=True,
        )
    if exchange.citations:
        logger.info(
            "Session %s exchange cited %d knowledge chunk(s)",
            db_session_id,
            len(exchange.citations),
        )

    atc_audio = await pipeline.speak(exchange.atc_response, language=detected_language)
    return _ExchangeOutcome(
        PipelineResult(
            audio=atc_audio,
            pilot_transcript=pilot_transcript,
            atc_response=exchange.atc_response,
            language=detected_language,
        )
    )


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
    org_id = _org_id_from_token(token_user)
    session_module = websocket.app.state.session_module
    pipeline = AudioPipeline(
        llm=websocket.app.state.llm,
        scene=websocket.app.state.scene_registry.get(DEFAULT_SCENE.version),
    )

    await manager.connect(websocket, client_id)
    logger.info(f"Voice communication started for client {client_id}")

    session_language = "auto"
    db_session_id: int | None = None
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            training_session = TrainingSession(
                client_id=client_id,
                language=session_language,
                org_id=org_id,
                scene_version=DEFAULT_SCENE.version,
            )
            db.add(training_session)
            await db.flush()
            db_session_id = training_session.id
            # The row and its created audit event commit together, so a voice
            # session can never exist without the event that explains it.
            record_session_created(db, training_session, user_id=None)
            await db.commit()
            logger.info(f"Created TrainingSession id={db_session_id} for client {client_id}")
        # Voice clients do not choose a Scene, so the session runs the packaged
        # default and records it as provenance against the persisted row.
        await session_module.start(
            StartSessionCommand(
                org_id=org_id,
                user_id=None,
                session_id=db_session_id,
                scene_version=DEFAULT_SCENE.version,
                language=session_language,
                flight_plan={},
            )
        )
    except Exception as e:
        logger.warning(f"Could not start TrainingSession (DB unavailable?): {e}")
        if db_session_id is not None:
            await _discard_session(db_session_id)
        db_session_id = None

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
                    logger.info(f"Processing {len(audio_chunks)} audio chunks")

                    await manager.send_json(
                        client_id,
                        {
                            "type": "processing",
                            "message": "Processing your transmission...",
                        },
                    )

                    if audio_chunks:
                        combined_audio = b"".join(audio_chunks)
                        audio_chunks = []
                        current_audio_bytes = 0

                        logger.info(
                            f"Processing {len(combined_audio)} bytes of audio"
                        )
                        if db_session_id is not None:
                            try:
                                outcome = await _process_exchange(
                                    pipeline,
                                    session_module,
                                    org_id,
                                    db_session_id,
                                    combined_audio,
                                    session_language,
                                )
                            except Exception:
                                # A Session failure must never look like a
                                # successful exchange: tell the client, rather
                                # than answering from the pipeline outside the
                                # recorded session.  The cause stays in the log;
                                # provider, graph and database errors must not be
                                # disclosed to the client.
                                logger.exception(
                                    "Session exchange failed for session %s",
                                    db_session_id,
                                )
                                await manager.send_json(
                                    client_id,
                                    {
                                        "type": "error",
                                        "code": "SESSION_ERROR",
                                        "message": (
                                            "Training session unavailable. "
                                            "Please try again."
                                        ),
                                    },
                                )
                                continue
                        else:
                            outcome = _ExchangeOutcome(
                                await pipeline.process_audio(
                                    combined_audio, language=session_language
                                )
                            )
                        result = outcome.result

                        if outcome.pending_instructor:
                            await manager.send_json(
                                client_id,
                                {
                                    "type": "awaiting_instructor",
                                    "message": (
                                        "Transmission held for instructor review. "
                                        "No ATC response will be sent until it is approved."
                                    ),
                                },
                            )
                        elif result.audio:
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

                elif message.get("type") == "language_change":
                    new_lang = message.get("language", "auto")
                    if new_lang in ("auto", "en", "es"):
                        session_language = new_lang
                        await manager.send_json(
                            client_id,
                            {
                                "type": "language_changed",
                                "language": session_language,
                                "message": f"Language set to {session_language}",
                            },
                        )
                        logger.info(f"Client {client_id} language changed to {session_language}")

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
