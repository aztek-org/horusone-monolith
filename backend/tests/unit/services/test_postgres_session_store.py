"""Unit tests for the Postgres-backed session store.

Only the pure helpers and the checkpoint-shape translation are exercised:
the LangGraph saver is replaced with an AsyncMock, so no database or
connection pool is contacted.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.training_sessions.postgres_session_store import PostgresSessionStore
from app.services.training_sessions.session_store import StoredState

DATABASE_URL = "postgresql+asyncpg://horus:horus@localhost:5432/horus_db"


def _store() -> PostgresSessionStore:
    store = PostgresSessionStore(DATABASE_URL)
    store._saver = AsyncMock()
    return store


class TestHelpers:
    def test_thread_id_is_tenant_scoped(self) -> None:
        org = uuid.uuid4()
        assert PostgresSessionStore.thread_id(org, 42) == f"{org}:42"

    def test_config_wraps_thread_id(self) -> None:
        org = uuid.uuid4()
        store = _store()

        config = store._config(org, 7)

        assert config == {
            "configurable": {"thread_id": f"{org}:7", "checkpoint_ns": ""}
        }

    def test_configured_saver_requires_setup(self) -> None:
        store = PostgresSessionStore(DATABASE_URL)

        with pytest.raises(RuntimeError, match="setup"):
            _ = store._configured_saver

    @pytest.mark.asyncio
    async def test_setup_is_idempotent(self) -> None:
        store = PostgresSessionStore(DATABASE_URL)
        store._saver = AsyncMock()

        await store.setup()

        assert store._saver is not None


class TestLoad:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_checkpoint(self) -> None:
        store = _store()
        store._saver.aget_tuple = AsyncMock(return_value=None)
        org = uuid.uuid4()

        assert await store.load(org, 1) is None
        store._saver.aget_tuple.assert_awaited_once_with(
            {"configurable": {"thread_id": f"{org}:1", "checkpoint_ns": ""}}
        )

    @pytest.mark.asyncio
    async def test_maps_checkpoint_to_stored_state(self) -> None:
        store = _store()
        checkpoint_tuple = SimpleNamespace(
            checkpoint={"channel_values": {"exchange_count": 2}, "id": "ck-1"},
            metadata={},
            pending_writes=[],
        )
        store._saver.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        state = await store.load(uuid.uuid4(), 1)

        assert state == StoredState(
            values={"exchange_count": 2},
            checkpoint_id="ck-1",
            pending_instructor=False,
        )

    @pytest.mark.asyncio
    async def test_detects_pending_instructor_from_write(self) -> None:
        store = _store()
        checkpoint_tuple = SimpleNamespace(
            checkpoint={"channel_values": {}, "id": "ck-2"},
            metadata={},
            pending_writes=[("task-1", "generate_atc_response", "value")],
        )
        store._saver.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        state = await store.load(uuid.uuid4(), 1)

        assert state is not None
        assert state.pending_instructor is True

    @pytest.mark.asyncio
    async def test_detects_pending_instructor_from_metadata(self) -> None:
        store = _store()
        checkpoint_tuple = SimpleNamespace(
            checkpoint={"channel_values": {}, "id": "ck-3"},
            metadata={"pending_instructor": True},
            pending_writes=[],
        )
        store._saver.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        state = await store.load(uuid.uuid4(), 1)

        assert state is not None
        assert state.pending_instructor is True


class TestSave:
    @pytest.mark.asyncio
    async def test_translates_state_into_a_checkpoint(self) -> None:
        store = _store()
        store._saver.aput = AsyncMock(
            return_value={"configurable": {"checkpoint_id": "ck-new"}}
        )
        org = uuid.uuid4()

        state = await store.save(org, 3, {"exchange_count": 5}, pending_instructor=True)

        assert state == StoredState(
            values={"exchange_count": 5},
            checkpoint_id="ck-new",
            pending_instructor=True,
        )
        args = store._saver.aput.call_args
        config, checkpoint, metadata, versions = args.args
        assert config == {"configurable": {"thread_id": f"{org}:3", "checkpoint_ns": ""}}
        assert checkpoint["channel_values"] == {"exchange_count": 5}
        assert metadata == {"pending_instructor": True}
        assert versions == {"exchange_count": checkpoint["id"]}

    @pytest.mark.asyncio
    async def test_reuses_supplied_checkpoint_and_strips_it(
        self,
    ) -> None:
        store = _store()
        store._saver.aput = AsyncMock(
            return_value={"configurable": {"checkpoint_id": "ck-4"}}
        )

        state = await store.save(
            uuid.uuid4(),
            3,
            {"__checkpoint__": {"id": "existing"}, "exchange_count": 1},
        )

        assert state.values == {"exchange_count": 1}
        checkpoint = store._saver.aput.call_args.args[1]
        assert checkpoint["id"] == "existing"

    @pytest.mark.asyncio
    async def test_delete_uses_tenant_thread_id(self) -> None:
        store = _store()
        store._saver.adelete_thread = AsyncMock()
        org = uuid.uuid4()

        await store.delete(org, 9)

        store._saver.adelete_thread.assert_awaited_once_with(f"{org}:9")
