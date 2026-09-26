"""A flight-plan validation is tenant-scoped, and persists nothing.

``POST /api/v1/flight-plans/{id}/validate`` runs the Session module's
``validate()``, which is the only path that checks a flight plan before a
training session exists.  Two properties have to hold at once, and neither is
visible from the other:

* the validation retrieves the calling tenant's private manuals, which requires
  the route to pass its resolved ``org_id`` into ``HorusState.org_id``;
* the validation still creates no ``TrainingSession`` row and no
  ``session_started`` event, because a validation is not a session.

The second is the one a tenant-aware ``validate()`` could plausibly break: it
runs the same graph as ``start()`` with the same real collaborators, so an
org-scoped path that acquired one ``start()`` step would quietly start writing
durable rows and provenance from a read-shaped endpoint.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.config import KnowledgeSettings
from app.db.session import get_session_factory
from app.knowledge.ingest import KnowledgeIngestor
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import DocumentUpload
from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.knowledge_document import ContentChunk, ContentDocument
from app.models.organization import Organization
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.session_module import TrainingSessionModule
from app.services.training_sessions.session_store import InMemorySessionStore
from app.services.training_sessions.trace import SqlAlchemyTraceRecorder

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="needs Postgres"
)

SETTINGS = KnowledgeSettings(
    chunk_size=1000,
    chunk_overlap=150,
    embedding_dimensions=768,
    # A validation has no Scene, so no ``knowledge_refs`` narrows the corpus and
    # every published chunk competes for the result set.  The fake adapter
    # returns an all-zero embedding, so the dense leg's ordering carries no
    # signal; a generous ``top_k`` keeps a reachability assertion about tenant
    # scoping from being decided by an arbitrary cut-off.
    top_k=1000,
    default_chunk_quota=1000,
)

FLIGHT_PLAN = {
    "departure_icao": "KLAX",
    "arrival_icao": "KSFO",
    "flight_rules": "VFR",
    "aircraft_type": "C172",
    "fuel_on_board": 30.0,
    "fuel_reserve": 5.0,
    "total_weight": 2000.0,
    "max_weight": 2450.0,
    "cruise_altitude": 3500,
    "route": [{"name": "KLAX", "lat": 33.94, "lng": -118.40}],
}


def _module() -> TrainingSessionModule:
    """A module with the collaborators a deployment really composes.

    The real ``PgVectorRetriever`` and the real database-backed session factory
    and trace recorder are deliberate: a stubbed database could not detect a
    write, and a stubbed retriever could not detect a missing tenant.
    """
    return TrainingSessionModule(
        InMemorySessionStore(),
        SqlAlchemyTraceRecorder(),
        SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE}),
        FakeAdapter(),
        db_session_factory=get_session_factory(),
        knowledge=PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS),
        require_org=True,
    )


def _upload(*, org_id: uuid.UUID):
    """Stage one tenant-private manual the validation's own query can find.

    The validation builds its retrieval query from the flight plan's
    ``departure_icao``/``arrival_icao``/``flight_rules`` and runs it in hybrid
    mode, and the text leg is an AND over every token of that query.  A real
    manual would be found by the dense leg, which the fake provider cannot rank
    (it returns the same all-zero embedding for everything), so the fixture
    repeats the query tokens verbatim.  Both tenants' manuals do, which is what
    makes the isolation assertion below a real one: both are retrievable, and
    only the caller's may come back.
    """
    suffix = uuid.uuid4().hex
    return DocumentUpload(
        title=f"Validation manual {suffix}",
        source_filename=f"validation-manual-{suffix}.md",
        content=(
            b"departure_icao KLAX arrival_icao KSFO flight_rules VFR. "
            b"Private tenant procedure for the coastal corridor. "
            b"Altitude 3500 feet. Waypoint restrictions apply. " * 12
        ),
        org_id=org_id,
        created_by=None,
        is_published=True,
    )


async def _seed_tenant_document(org_id: uuid.UUID) -> tuple[uuid.UUID, str]:
    factory = get_session_factory()
    async with factory() as db:
        upload = _upload(org_id=org_id)
        result = await KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text").ingest(
            db, upload
        )
        await db.commit()
    return result.document_id, upload.source_filename


async def _chunk_ids(document_id: uuid.UUID) -> list[str]:
    factory = get_session_factory()
    async with factory() as db:
        rows = await db.scalars(
            select(ContentChunk.id).where(ContentChunk.document_id == document_id)
        )
        return [str(chunk_id) for chunk_id in rows]


async def _durable_row_counts() -> tuple[int, int]:
    """Count the rows a session would create, as they stand right now."""
    factory = get_session_factory()
    async with factory() as db:
        sessions = await db.scalar(select(func.count(TrainingSession.id)))
        started = await db.scalar(
            select(func.count(TrainingSessionEvent.id)).where(
                TrainingSessionEvent.event_type.in_(("session_started", "created"))
            )
        )
    return int(sessions or 0), int(started or 0)


async def _cleanup(org_id: uuid.UUID, document_id: uuid.UUID) -> None:
    factory = get_session_factory()
    async with factory() as db:
        await db.execute(
            delete(ContentDocument).where(ContentDocument.id == document_id)
        )
        await db.execute(delete(Organization).where(Organization.id == org_id))
        await db.commit()


@pytest.mark.asyncio
async def test_tenant_scoped_validation_retrieves_own_knowledge_and_persists_nothing() -> None:
    """The validation reaches the tenant's manuals and writes no session.

    Both halves are asserted against the real database, because the failure this
    guards is silent in either direction: retrieval scoped to ``org_id IS NULL``
    returns plausible-looking results with no tenant knowledge, and a persisted
    session is indistinguishable from a legitimate one until the audit trail is
    read.
    """
    owner, other = uuid.uuid4(), uuid.uuid4()
    factory = get_session_factory()
    async with factory() as db:
        db.add_all(
            [
                Organization(id=owner, name="Validation owner", slug=f"val-{owner}"),
                Organization(id=other, name="Validation other", slug=f"val-{other}"),
            ]
        )
        await db.commit()

    owner_document, _ = await _seed_tenant_document(owner)
    other_document, _ = await _seed_tenant_document(other)
    try:
        owner_chunk_ids = await _chunk_ids(owner_document)
        other_chunk_ids = await _chunk_ids(other_document)
        assert owner_chunk_ids and other_chunk_ids
        before = await _durable_row_counts()

        snapshot = await _module().validate(
            user_id=None,
            flight_plan=FLIGHT_PLAN,
            org_id=owner,
        )

        assert set(owner_chunk_ids) <= set(snapshot.state["retrieved_chunk_ids"])
        assert not set(other_chunk_ids) & set(snapshot.state["retrieved_chunk_ids"])
        assert snapshot.state["org_id"] == str(owner)
        # Nothing was stored, so there is no session to address.
        assert snapshot.session_id == 0
        assert await _durable_row_counts() == before
    finally:
        await _cleanup(other, other_document)
        await _cleanup(owner, owner_document)


@pytest.mark.asyncio
async def test_tenant_less_validation_sees_no_tenant_knowledge() -> None:
    """With no tenant the validation is global-only, and still writes nothing.

    ``org_id`` is optional on the route (a platform admin may have none), so the
    tenant-less path must stay reachable and stay fail-closed.
    """
    org_id = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as db:
        db.add(Organization(id=org_id, name="Validation owner", slug=f"val-{org_id}"))
        await db.commit()

    document_id, _filename = await _seed_tenant_document(org_id)
    try:
        tenant_chunk_ids = await _chunk_ids(document_id)
        before = await _durable_row_counts()

        snapshot = await _module().validate(
            user_id=None,
            flight_plan=FLIGHT_PLAN,
        )

        assert not set(tenant_chunk_ids) & set(snapshot.state["retrieved_chunk_ids"])
        assert snapshot.state["org_id"] is None
        assert snapshot.session_id == 0
        assert await _durable_row_counts() == before
    finally:
        await _cleanup(org_id, document_id)
