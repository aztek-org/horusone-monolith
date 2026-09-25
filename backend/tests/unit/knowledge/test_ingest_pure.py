import pytest

from app.config import KnowledgeSettings
from app.knowledge.ingest import EmbeddingDimensionMismatch, KnowledgeIngestor
from app.knowledge.types import DocumentUpload
from app.llm.adapters.fake_adapter import FakeAdapter
from app.models.knowledge_document import ContentChunk


class FakeEmbedder(FakeAdapter):
    async def embed(self, texts):
        from app.llm.types import EmbeddingResult

        return EmbeddingResult(
            vectors=[[0.0] * 384 for _ in texts],
            provider="fake",
            model="test-384",
            dimensions=384,
        )


class RecordingSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        pass

    async def execute(self, statement):
        class Result:
            def scalar(self):
                return 0

        return Result()


@pytest.mark.asyncio
async def test_embedding_dimension_mismatch_does_not_add_content_chunks():
    db = RecordingSession()
    settings = KnowledgeSettings(
        chunk_size=100,
        chunk_overlap=15,
        embedding_dimensions=768,
        top_k=5,
        default_chunk_quota=100,
    )

    with pytest.raises(EmbeddingDimensionMismatch):
        await KnowledgeIngestor(FakeEmbedder(), settings, "test-384").ingest(
            db,
            DocumentUpload(
                title="Dimension test",
                source_filename="dimension.md",
                content=b"# Dimension\n\ntext " * 40,
                org_id=None,
                created_by=None,
            ),
        )

    assert not any(isinstance(value, ContentChunk) for value in db.added)
