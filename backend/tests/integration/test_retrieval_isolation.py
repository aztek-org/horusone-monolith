import os
import uuid

import pytest
from sqlalchemy import func, select

from app.config import KnowledgeSettings
from app.db.session import get_session_factory
from app.knowledge.ingest import KnowledgeIngestor
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import DocumentUpload, RetrievalQuery
from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.knowledge_document import ContentChunk
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


async def _fresh_organization_id() -> object:
    """Create and commit a tenant with no knowledge chunks of its own."""
    suffix = uuid.uuid4().hex
    organization = Organization(
        name=f"Knowledge Empty Tenant {suffix}",
        slug=f"knowledge-empty-tenant-{suffix}",
    )
    async with get_session_factory()() as db:
        db.add(organization)
        await db.commit()
    return organization.id


@pytest.mark.asyncio
async def test_private_chunk_never_leaks_across_tenants():
    org_a = (await _organization_ids())[0]
    org_b = await _fresh_organization_id()
    platform_filename = f"platform-wide-{uuid.uuid4().hex}.md"
    async with get_session_factory()() as db:
        ingestor = KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text")
        await ingestor.ingest(
            db,
            DocumentUpload(
                title="A secret",
                source_filename=f"private-{uuid.uuid4().hex}.md",
                content=b"secret phrase zebra " * 40,
                org_id=org_a,
                created_by=None,
                is_published=True,
            ),
        )
        # A platform-wide published document is inside org_b's candidate set.  It
        # is what makes the assertion below falsifiable: without at least one
        # row org_b *can* see, `all(... for ... in [])` is vacuously true and the
        # test still passes if `PgVectorRetriever.search` returns nothing at all,
        # which is the exact failure it exists to catch.
        await ingestor.ingest(
            db,
            DocumentUpload(
                title=f"Platform zebra {platform_filename}",
                source_filename=platform_filename,
                content=b"platform zebra reference " * 40,
                org_id=None,
                created_by=None,
                is_published=True,
            ),
        )
        await db.commit()

    async with get_session_factory()() as db:
        chunk_count = await db.execute(
            select(func.count()).select_from(ContentChunk).where(ContentChunk.org_id == org_b)
        )
        assert chunk_count.scalar_one() == 0

    retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
    results = await retriever.search(
        RetrievalQuery(query="zebra", org_id=org_b, top_k=50)
    )
    # The platform-wide chunk is inside org_b's candidate set, so the result set
    # is non-empty and org_a's private chunk is absent from it.  A membership
    # assertion over a generous `top_k` is used rather than an exact result
    # list because platform-wide rows accumulate across runs in a shared test
    # database and the dense leg returns the `top_k` nearest chunks regardless
    # of the query text.
    assert results
    assert f"Platform zebra {platform_filename}" in {result.title for result in results}
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
    published_title = f"Published zebra {uuid.uuid4().hex}"
    async with get_session_factory()() as db:
        ingestor = KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text")
        await ingestor.ingest(
            db,
            DocumentUpload(
                title="Draft secret",
                source_filename=f"draft-{uuid.uuid4().hex}.md",
                content=b"secret phrase unpublished " * 40,
                org_id=org_id,
                created_by=None,
                is_published=False,
            ),
        )
        # A published sibling that matches the same query, so the assertion below
        # runs over a result set the retriever actually produced.  Without it
        # `all(title != "Draft secret" for ... in [])` would also hold if the
        # publication filter dropped everything.
        await ingestor.ingest(
            db,
            DocumentUpload(
                title=published_title,
                source_filename=f"published-{uuid.uuid4().hex}.md",
                content=b"secret phrase unpublished " * 40,
                org_id=org_id,
                created_by=None,
                is_published=True,
            ),
        )
        await db.commit()

    retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
    results = await retriever.search(
        RetrievalQuery(query="unpublished", org_id=org_id, top_k=50)
    )
    titles = {result.title for result in results}
    assert published_title in titles
    assert "Draft secret" not in titles
