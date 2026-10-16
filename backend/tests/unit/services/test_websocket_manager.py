"""Unit tests for the WebSocket ConnectionManager.

WebSocket clients are replaced with AsyncMocks so no sockets are opened.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.websocket_manager import ConnectionManager, manager


def _fake_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnectAndDisconnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_and_registers(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()

        await cm.connect(ws, "client-1")

        ws.accept.assert_awaited_once()
        assert cm.active_connections["client-1"] is ws
        assert "client-1" in cm.client_ids

    def test_disconnect_removes_known_client(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()
        cm.active_connections["client-1"] = ws
        cm.client_ids.add("client-1")

        cm.disconnect("client-1")

        assert "client-1" not in cm.active_connections
        assert "client-1" not in cm.client_ids

    def test_disconnect_unknown_client_is_noop(self) -> None:
        cm = ConnectionManager()

        cm.disconnect("ghost")

        assert cm.active_connections == {}
        assert cm.client_ids == set()


class TestSendAudio:
    @pytest.mark.asyncio
    async def test_sends_bytes_to_connected_client(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()
        await cm.connect(ws, "client-1")

        await cm.send_audio("client-1", b"audio-bytes")

        ws.send_bytes.assert_awaited_once_with(b"audio-bytes")

    @pytest.mark.asyncio
    async def test_ignores_unknown_client(self) -> None:
        cm = ConnectionManager()

        await cm.send_audio("missing", b"x")

        assert cm.active_connections == {}

    @pytest.mark.asyncio
    async def test_disconnects_client_on_send_failure(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()
        ws.send_bytes.side_effect = RuntimeError("socket closed")
        await cm.connect(ws, "client-1")

        await cm.send_audio("client-1", b"x")

        assert "client-1" not in cm.active_connections
        assert "client-1" not in cm.client_ids


class TestSendJson:
    @pytest.mark.asyncio
    async def test_sends_payload_to_connected_client(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()
        await cm.connect(ws, "client-1")

        await cm.send_json("client-1", {"type": "response"})

        ws.send_json.assert_awaited_once_with({"type": "response"})

    @pytest.mark.asyncio
    async def test_disconnects_client_on_send_failure(self) -> None:
        cm = ConnectionManager()
        ws = _fake_ws()
        ws.send_json.side_effect = RuntimeError("socket closed")
        await cm.connect(ws, "client-1")

        await cm.send_json("client-1", {"type": "x"})

        assert "client-1" not in cm.active_connections


def test_module_exposes_a_shared_manager() -> None:
    assert isinstance(manager, ConnectionManager)
