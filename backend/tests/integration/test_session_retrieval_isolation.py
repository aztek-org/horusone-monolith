"""A training session may only retrieve its own tenant's knowledge.

The validation graph's retrieval node used to hardcode ``org_id=None``, so
every session resolved to globally published chunks only: tenant-scoped
retrieval was unreachable outside the manual ``GET /knowledge/search`` route.
These tests drive the real ``PgVectorRetriever`` through the real
``TrainingSessionModule`` to prove both halves of the fix — a session reaches
its own private manuals, and never another tenant's.
"""

import os
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import delete, select

from app.config import KnowledgeSettings
from app.db.session import get_session_factory
from app.knowledge.ingest import KnowledgeIngestor
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.knowledge_document import ContentDocument
from app.models.organization import Organization
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.session_module import TrainingSessionModule
from app.services.training_sessions.session_store import InMemorySessionStore
from app.services.training_sessions.trace import InMemoryTraceRecorder
from app.services.training_sessions.types import SendTransmissionCommand, StartSessionCommand

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="needs Postgres"
)

SETTINGS = KnowledgeSettings(
    chunk_size=1000,
    chunk_overlap=150,
    embedding_dimensions=768,
    top_k=5,
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


class _NoDb:
    """Session factory stand-in; ``start`` writes nothing that needs a row."""

    async def __aenter__(self) -> "_NoDb":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        return None

    async def commit(self) -> None:
        return None


async def _seed_tenant_document(org_id: uuid.UUID) -> tuple[uuid.UUID, str]:
    """Ingest one published, tenant-private document and return it and its name."""
    suffix = uuid.uuid4().hex
    filename = f"tenant-manual-{suffix}.md"
    factory = get_session_factory()
    async with factory() as db:
        result = await KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text").ingest(
            db,
            _upload(
                title=f"Tenant manual {suffix}",
                filename=filename,
                org_id=org_id,
            ),
        )
        await db.commit()
    return result.document_id, filename


def _upload(*, title: str, filename: str, org_id: uuid.UUID):
    from app.knowledge.types import DocumentUpload

    return DocumentUpload(
        title=title,
        source_filename=filename,
        content=(
            b"Private tenant procedure. KLAX to KSFO VFR via the coastal corridor. "
            b"Altitude 3500 feet. Waypoint restrictions apply. " * 12
        ),
        org_id=org_id,
        created_by=None,
        is_published=True,
    )


def _module(scene_knowledge_refs: list[str]) -> TrainingSessionModule:
    scene = replace(DEFAULT_SCENE, knowledge_refs=scene_knowledge_refs)
    return TrainingSessionModule(
        InMemorySessionStore(),
        InMemoryTraceRecorder(),
        SceneRegistry({scene.version: scene}),
        FakeAdapter(),
        db_session_factory=_NoDb,
        knowledge=PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS),
        require_org=True,
    )


@pytest.mark.asyncio
async def test_session_retrieves_its_own_tenant_knowledge() -> None:
    """A session reaches the private manual its own Scene names."""
    org_id = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as db:
        db.add(Organization(id=org_id, name="Retrieval owner", slug=f"retr-{org_id}"))
        await db.commit()

    document_id, filename = await _seed_tenant_document(org_id)
    try:
        snapshot = await _module([filename]).start(
            StartSessionCommand(
                org_id, None, 1, DEFAULT_SCENE.version, "en", FLIGHT_PLAN
            )
        )

        own_chunk_ids = await _chunk_ids(document_id)
        assert own_chunk_ids
        assert set(own_chunk_ids) <= set(snapshot.state["retrieved_chunk_ids"])
    finally:
        await _cleanup(org_id, document_id)


@pytest.mark.asyncio
async def test_session_never_retrieves_another_tenants_knowledge() -> None:
    """The foreign tenant's chunks stay invisible, refs or not."""
    owner = uuid.uuid4()
    other = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as db:
        db.add_all(
            [
                Organization(id=owner, name="Retrieval owner", slug=f"retr-{owner}"),
                Organization(id=other, name="Retrieval other", slug=f"retr-{other}"),
            ]
        )
        await db.commit()

    document_id, filename = await _seed_tenant_document(owner)
    try:
        snapshot = await _module([filename]).start(
            StartSessionCommand(
                other, None, 1, DEFAULT_SCENE.version, "en", FLIGHT_PLAN
            )
        )

        foreign_chunk_ids = await _chunk_ids(document_id)
        assert foreign_chunk_ids
        assert not set(snapshot.state["retrieved_chunk_ids"]) & set(foreign_chunk_ids)
    finally:
        await _cleanup(other, None)
        await _cleanup(owner, document_id)


async def _chunk_ids(document_id: uuid.UUID) -> list[str]:
    from app.models.knowledge_document import ContentChunk

    factory = get_session_factory()
    async with factory() as db:
        rows = await db.scalars(
            select(ContentChunk.id).where(ContentChunk.document_id == document_id)
        )
        return [str(chunk_id) for chunk_id in rows]


async def _cleanup(org_id: uuid.UUID, document_id: uuid.UUID | None) -> None:
    factory = get_session_factory()
    async with factory() as db:
        if document_id is not None:
            await db.execute(
                delete(ContentDocument).where(ContentDocument.id == document_id)
            )
        await db.execute(delete(Organization).where(Organization.id == org_id))
        await db.commit()


@pytest.mark.asyncio
async def test_live_exchange_cites_its_own_tenant_knowledge_only() -> None:
    """A live exchange attaches citations and never leaks another tenant's.

    Both sessions name the same document *filename* in their Scene knowledge
    refs, so the reference filter alone cannot separate them — the tenant
    predicate on the live retrieval query must.
    """
    owner = uuid.uuid4()
    other = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as db:
        db.add_all(
            [
                Organization(id=owner, name="Citation owner", slug=f"cite-{owner}"),
                Organization(id=other, name="Citation other", slug=f"cite-{other}"),
            ]
        )
        await db.commit()

    document_id, filename = await _seed_tenant_document(owner)
    try:
        own_chunk_ids = await _chunk_ids(document_id)
        assert own_chunk_ids
        transmission = "KLAX to KSFO VFR via the coastal corridor"

        owner_module = _module([filename])
        await owner_module.start(
            StartSessionCommand(owner, None, 1, DEFAULT_SCENE.version, "en", FLIGHT_PLAN)
        )
        owner_result = await owner_module.send(SendTransmissionCommand(owner, 1, transmission))

        cited = {str(citation.chunk_id) for citation in owner_result.citations}
        assert cited
        assert cited <= set(own_chunk_ids)

        other_module = _module([filename])
        await other_module.start(
            StartSessionCommand(other, None, 2, DEFAULT_SCENE.version, "en", FLIGHT_PLAN)
        )
        other_result = await other_module.send(SendTransmissionCommand(other, 2, transmission))

        assert not ({str(c.chunk_id) for c in other_result.citations} & set(own_chunk_ids))
    finally:
        await _cleanup(other, None)
        await _cleanup(owner, document_id)
