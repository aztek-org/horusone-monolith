import uuid

import pytest

from app.services.training_sessions.session_store import InMemorySessionStore, SessionStore


@pytest.mark.asyncio
async def test_roundtrip_and_tenant_isolation():
    store = InMemorySessionStore()
    org_a, org_b, sid = uuid.uuid4(), uuid.uuid4(), 7
    await store.save(org_a, sid, {"exchange_count": 1})
    assert (await store.load(org_a, sid)).values["exchange_count"] == 1
    assert await store.load(org_b, sid) is None
    assert SessionStore.thread_id(org_a, sid) == f"{org_a}:{sid}"
    assert InMemorySessionStore.thread_id(org_a, sid) == f"{org_a}:{sid}"
    await store.delete(org_a, sid)
    assert await store.load(org_a, sid) is None
