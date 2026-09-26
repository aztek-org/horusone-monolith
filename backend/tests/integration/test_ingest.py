import os

import pytest

from app.config import KnowledgeSettings
from app.db.session import get_session_factory
from app.knowledge.ingest import KnowledgeIngestor, QuotaExceeded
from app.knowledge.types import DocumentUpload
from app.llm.adapters.fake_adapter import FakeAdapter

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


@pytest.mark.asyncio
async def test_ingest_writes_chunks_and_event():
    async with get_session_factory()() as db:
        result = await KnowledgeIngestor(
            FakeAdapter(), SETTINGS, "nomic-embed-text"
        ).ingest(
            db,
            DocumentUpload(
                title="SOP",
                source_filename="sop.md",
                content=b"# SOP\nclearance rules " * 50,
                org_id=None,
                created_by=None,
            ),
        )
        await db.commit()
        assert result.chunk_count > 0 and result.embedding_dimensions == 768


@pytest.mark.asyncio
async def test_quota_blocks_before_embedding():
    class RecordingLLM(FakeAdapter):
        def __init__(self):
            super().__init__()
            self.embed_calls = 0

        async def embed(self, texts):
            self.embed_calls += 1
            return await super().embed(texts)

    llm = RecordingLLM()
    settings = KnowledgeSettings(
        chunk_size=100,
        chunk_overlap=15,
        embedding_dimensions=768,
        top_k=5,
        default_chunk_quota=1,
    )
    async with get_session_factory()() as db:
        with pytest.raises(QuotaExceeded):
            await KnowledgeIngestor(llm, settings, "nomic-embed-text").ingest(
                db,
                DocumentUpload(
                    title="big",
                    source_filename="b.md",
                    content=b"x " * 100000,
                    org_id=None,
                    created_by=None,
                ),
            )
    assert llm.embed_calls == 0
