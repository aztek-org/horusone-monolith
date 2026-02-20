"""WebSocket connection manager for handling multiple client connections."""

import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for voice communication."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_ids: Set[str] = set()

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and store a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept
            client_id: Unique identifier for the client
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_ids.add(client_id)
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            client_id: Unique identifier for the client to disconnect
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.client_ids.discard(client_id)
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_audio(self, client_id: str, audio_data: bytes) -> None:
        """Send audio data to a specific client.

        Args:
            client_id: The client to send audio to
            audio_data: Raw audio bytes to send
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_bytes(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio to client {client_id}: {e}")
                self.disconnect(client_id)

    async def send_json(self, client_id: str, data: dict) -> None:
        """Send JSON data to a specific client.

        Args:
            client_id: The client to send data to
            data: Dictionary to send as JSON
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending JSON to client {client_id}: {e}")
                self.disconnect(client_id)


# Global connection manager instance
manager = ConnectionManager()
