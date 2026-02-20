"""WebSocket route for voice communication."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audio_pipeline import AudioPipeline
from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global audio pipeline instance
audio_pipeline: Optional[AudioPipeline] = None


def get_audio_pipeline() -> AudioPipeline:
    """Get or create the audio pipeline instance."""
    global audio_pipeline
    if audio_pipeline is None:
        audio_pipeline = AudioPipeline()
    return audio_pipeline


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
                import json
                message = json.loads(data["text"])
                
                if message.get("type") == "audio_end":
                    # Client finished sending audio, process it
                    logger.info(f"Processing {len(audio_chunks)} audio chunks")
                    
                    # Send processing status
                    await manager.send_json(client_id, {
                        "type": "processing",
                        "message": "Processing your transmission...",
                    })

                    # Combine audio chunks
                    if audio_chunks:
                        combined_audio = b"".join(audio_chunks)
                        audio_chunks = []  # Reset for next transmission

                        # Process through pipeline
                        response_audio = await pipeline.process_audio(combined_audio)

                        if response_audio:
                            # Send audio response
                            await manager.send_audio(client_id, response_audio)
                            
                            # Send completion status
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
                    # Reset conversation
                    pipeline.reset_conversation()
                    await manager.send_json(client_id, {
                        "type": "reset_complete",
                        "message": "Conversation reset",
                    })

                elif message.get("type") == "ping":
                    # Heartbeat
                    await manager.send_json(client_id, {
                        "type": "pong",
                    })

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Error in voice communication: {e}", exc_info=True)
        manager.disconnect(client_id)
