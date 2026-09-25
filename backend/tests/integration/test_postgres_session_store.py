"""Integration tests for the Postgres-backed training session store."""

import os
import uuid

import pytest

from app.services.training_sessions.postgres_session_store import PostgresSessionStore

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for Postgres session store integration tests",
)


@pytest.mark.asyncio
async def test_postgres_roundtrip_and_tenant_isolation():
    org_a, org_b, sid = uuid.uuid4(), uuid.uuid4(), 17
    store = PostgresSessionStore(DATABASE_URL)
    await store.setup()
    try:
        await store.save(org_a, sid, {"exchange_count": 1})
        assert (await store.load(org_a, sid)).values["exchange_count"] == 1
        assert await store.load(org_b, sid) is None
        await store.delete(org_a, sid)
        assert await store.load(org_a, sid) is None
    finally:
        await store._pool.close()


@pytest.mark.asyncio
async def test_state_survives_a_new_store_instance():
    org_id, session_id = uuid.uuid4(), 18
    first_store = PostgresSessionStore(DATABASE_URL)
    await first_store.setup()
    try:
        await first_store.save(org_id, session_id, {"exchange_count": 1})
    finally:
        await first_store._pool.close()

    restarted_store = PostgresSessionStore(DATABASE_URL)
    await restarted_store.setup()
    try:
        loaded = await restarted_store.load(org_id, session_id)
        assert loaded is not None
        assert loaded.values["exchange_count"] == 1
    finally:
        await restarted_store._pool.close()
