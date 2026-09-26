"""Postgres integration coverage for the persisted training Session module."""

import os
import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.organization import Organization
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.postgres_session_store import PostgresSessionStore
from app.services.training_sessions.session_module import TrainingSessionModule
from app.services.training_sessions.trace import SqlAlchemyTraceRecorder
from app.services.training_sessions.types import SendTransmissionCommand, StartSessionCommand

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for Session module integration tests",
)


@pytest.mark.asyncio
async def test_send_persists_exchange_and_trace_event() -> None:
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    session_id: int | None = None

    async with session_factory() as db:
        org = Organization(
            id=org_id,
            name="Session integration test",
            slug=f"session-{org_id}",
        )
        db.add(org)
        await db.flush()
        session_id = await db.scalar(
            text(
                "INSERT INTO training_sessions (language, status, org_id) "
                "VALUES ('en', 'active', :org_id) RETURNING id"
            ),
            {"org_id": org_id},
        )
        await db.commit()

    store = PostgresSessionStore(DATABASE_URL)
    await store.setup()
    module = TrainingSessionModule(
        store,
        SqlAlchemyTraceRecorder(),
        SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE}),
        FakeAdapter(),
        db_session_factory=session_factory,
        require_org=True,
    )

    try:
        await module.start(
            StartSessionCommand(
                org_id,
                None,
                session_id,
                DEFAULT_SCENE.version,
                "en",
                {
                    "departure_icao": "KLAX",
                    "arrival_icao": "KSFO",
                    "flight_rules": "VFR",
                    "aircraft_type": "C172",
                    "fuel_on_board": 30.0,
                    "fuel_reserve": 5.0,
                    "total_weight": 2000.0,
                    "max_weight": 2450.0,
                    "cruise_altitude": 3500,
                    "route": [
                        {"name": "KLAX", "lat": 33.94, "lng": -118.40},
                        {"name": "KSFO", "lat": 37.62, "lng": -122.38},
                    ],
                },
            )
        )
        result = await module.send(
            SendTransmissionCommand(org_id, session_id, "Tower, request taxi")
        )

        assert result.exchange_count == 1
        async with session_factory() as db:
            event = await db.scalar(
                select(TrainingSessionEvent).where(
                    TrainingSessionEvent.session_id == session_id,
                    TrainingSessionEvent.event_type == "exchange_completed",
                )
            )
        assert event is not None
        assert event.event_payload["provider"] == "fake"
        assert event.event_payload["scene_version"] == DEFAULT_SCENE.version
    finally:
        if session_id is not None:
            await store.delete(org_id, session_id)
        async with session_factory() as db:
            await db.execute(
                delete(TrainingSessionEvent).where(
                    TrainingSessionEvent.session_id == session_id
                )
            )
            await db.execute(
                delete(TrainingSession).where(TrainingSession.id == session_id)
            )
            await db.execute(delete(Organization).where(Organization.id == org_id))
            await db.commit()
        await store._pool.close()
        await engine.dispose()
