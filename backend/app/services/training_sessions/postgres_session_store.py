"""Postgres-backed training session storage using LangGraph checkpoints."""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.engine import make_url

from app.services.training_sessions.session_store import SessionStore, StoredState


class PostgresSessionStore:
    """Persist tenant-scoped training state in LangGraph's Postgres checkpointer."""

    def __init__(self, database_url: str) -> None:
        dsn = make_url(database_url).set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        self._pool = AsyncConnectionPool(dsn, open=False, max_size=10)
        self._saver: AsyncPostgresSaver | None = None

    @staticmethod
    def thread_id(org_id: uuid.UUID, session_id: int) -> str:
        return SessionStore.thread_id(org_id, session_id)

    async def setup(self) -> None:
        """Open the pool and initialize the checkpointer schema when needed."""
        if self._saver is not None:
            return
        await self._pool.open()
        self._saver = AsyncPostgresSaver(self._pool)
        await self._saver.setup()

    @property
    def _configured_saver(self) -> AsyncPostgresSaver:
        if self._saver is None:
            raise RuntimeError("PostgresSessionStore.setup() must be called first")
        return self._saver

    @staticmethod
    def _config(org_id: uuid.UUID, session_id: int) -> dict[str, dict[str, str]]:
        return {
            "configurable": {
                "thread_id": SessionStore.thread_id(org_id, session_id),
                "checkpoint_ns": "",
            }
        }

    async def load(self, org_id: uuid.UUID, session_id: int) -> StoredState | None:
        checkpoint_tuple = await self._configured_saver.aget_tuple(self._config(org_id, session_id))
        if checkpoint_tuple is None:
            return None

        checkpoint = checkpoint_tuple.checkpoint
        pending_writes = checkpoint_tuple.pending_writes or []
        pending_instructor = bool(
            checkpoint_tuple.metadata.get("pending_instructor", False)
        ) or any(
            write[1] == "generate_atc_response" for write in pending_writes
        )
        return StoredState(
            values=dict(checkpoint.get("channel_values") or {}),
            checkpoint_id=checkpoint.get("id"),
            pending_instructor=pending_instructor,
        )

    async def save(
        self,
        org_id: uuid.UUID,
        session_id: int,
        state: dict[str, Any],
        pending_instructor: bool = False,
    ) -> StoredState:
        checkpoint = state.get("__checkpoint__")
        if not isinstance(checkpoint, dict):
            checkpoint = empty_checkpoint()
        else:
            checkpoint = dict(checkpoint)

        values = {key: value for key, value in state.items() if key != "__checkpoint__"}
        checkpoint["channel_values"] = values
        versions = {key: checkpoint["id"] for key in values}
        checkpoint["channel_versions"] = versions
        checkpoint["versions_seen"] = versions

        config = self._config(org_id, session_id)
        saved_config = await self._configured_saver.aput(
            config,
            checkpoint,
            {"pending_instructor": pending_instructor},
            versions,
        )
        return StoredState(
            values=dict(values),
            checkpoint_id=saved_config["configurable"]["checkpoint_id"],
            pending_instructor=pending_instructor,
        )

    async def delete(self, org_id: uuid.UUID, session_id: int) -> None:
        await self._configured_saver.adelete_thread(SessionStore.thread_id(org_id, session_id))
