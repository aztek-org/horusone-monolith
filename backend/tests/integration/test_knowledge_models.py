import os

import pytest
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.knowledge_document import ContentChunk, ContentDocument, IngestEvent

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")


@pytest.mark.asyncio
async def test_chunk_roundtrip():
    factory = get_session_factory()
    async with factory() as db:
        doc = ContentDocument(
            title="Manual",
            source_filename="m.md",
            source_type="markdown",
            content_hash="a" * 64,
            is_published=True,
            chunk_count=1,
        )
        db.add(doc)
        await db.flush()
        db.add(
            ContentChunk(
                document_id=doc.id,
                org_id=None,
                chunk_index=0,
                content="x",
                token_count=1,
                embedding=[0.0] * 768,
                char_start=0,
                char_end=1,
            )
        )
        db.add(
            IngestEvent(
                document_id=doc.id,
                org_id=None,
                status="succeeded",
                embedding_model="nomic-embed-text",
                embedding_dimensions=768,
                chunk_size=1000,
                chunk_overlap=150,
                chunk_count=1,
            )
        )
        await db.commit()
        rows = (
            await db.execute(select(ContentChunk).where(ContentChunk.document_id == doc.id))
        ).scalars().all()
        assert len(rows) == 1 and len(rows[0].embedding) == 768
