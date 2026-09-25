import os
import uuid

import pytest
from sqlalchemy import select

from app.config import KnowledgeSettings
from app.db.session import get_session_factory
from app.knowledge.ingest import KnowledgeIngestor
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import DocumentUpload, RetrievalQuery
from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.organization import Organization

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="needs Postgres"
)

SETTINGS = KnowledgeSettings(
    chunk_size=100,
    chunk_overlap=15,
    embedding_dimensions=768,
    top_k=5,
    default_chunk_quota=1000,
)


async def _organization_ids() -> tuple:
    async with get_session_factory()() as db:
        result = await db.execute(select(Organization).order_by(Organization.created_at).limit(2))
        organizations = list(result.scalars().all())
        if len(organizations) < 2:
            suffix = uuid.uuid4().hex
            organizations.extend(
                [
                    Organization(name=f"Knowledge Test A {suffix}", slug=f"knowledge-test-a-{suffix}"),
                    Organization(name=f"Knowledge Test B {suffix}", slug=f"knowledge-test-b-{suffix}"),
                ][: 2 - len(organizations)]
            )
            db.add_all(organizations)
            await db.commit()
    assert len(organizations) == 2
    return organizations[0].id, organizations[1].id


@pytest.mark.asyncio
async def test_private_chunk_never_leaks_across_tenants():
    org_a, org_b = await _organization_ids()
    async with get_session_factory()() as db:
        await KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text").ingest(
            db,
            DocumentUpload(
                title="A secret",
                source_filename="a.md",
                content=b"secret phrase zebra " * 40,
                org_id=org_a,
                created_by=None,
                is_published=True,
            ),
        )
        await db.commit()

    retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
    results = await retriever.search(
        RetrievalQuery(query="zebra", org_id=org_b, top_k=5)
    )
    assert all(result.org_id != org_a for result in results)


@pytest.mark.asyncio
async def test_scene_reference_filter_restricts_results_to_named_document():
    org_id = (await _organization_ids())[0]
    reference = f"keflavik-approach-{uuid.uuid4().hex}.md"
    async with get_session_factory()() as db:
        ingest_result = await KnowledgeIngestor(
            FakeAdapter(), SETTINGS, "nomic-embed-text"
        ).ingest(
            db,
            DocumentUpload(
                title=f"Named approach plate {reference}",
                source_filename=reference,
                content=b"keflavik zebra approach " * 50,
                org_id=org_id,
                created_by=None,
                is_published=True,
            ),
        )
        await db.commit()

    retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
    results = await retriever.search(
        RetrievalQuery(
            query="keflavik",
            org_id=org_id,
            top_k=20,
            knowledge_refs=[reference],
        )
    )
    assert results
    assert all(result.document_id == ingest_result.document_id for result in results)


@pytest.mark.asyncio
async def test_unpublished_chunk_is_not_retrievable():
    org_id = (await _organization_ids())[0]
    async with get_session_factory()() as db:
        await KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text").ingest(
            db,
            DocumentUpload(
                title="Draft secret",
                source_filename="draft.md",
                content=b"secret phrase unpublished " * 40,
                org_id=org_id,
                created_by=None,
                is_published=False,
            ),
        )
        await db.commit()

    retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
    results = await retriever.search(
        RetrievalQuery(query="unpublished", org_id=org_id, top_k=5)
    )
    assert all(result.title != "Draft secret" for result in results)
