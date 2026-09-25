from types import SimpleNamespace
from uuid import UUID

import pytest

from app.config import KnowledgeSettings
from app.knowledge.retrieval.fake import FakeRetriever
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import RetrievalQuery, RetrievedChunk
from app.llm.adapters.fake_adapter import FakeAdapter


@pytest.mark.asyncio
async def test_fake_retriever_applies_tenant_and_reference_filters():
    org_a = "00000000-0000-0000-0000-00000000000a"
    org_b = "00000000-0000-0000-0000-00000000000b"
    doc_a = "00000000-0000-0000-0000-00000000000c"
    doc_b = "00000000-0000-0000-0000-00000000000d"
    retriever = FakeRetriever()
    await retriever.add(
        RetrievedChunk(
            chunk_id="00000000-0000-0000-0000-00000000000e",
            document_id=doc_a,
            org_id=org_a,
            title="Private",
            content="zebra phrase",
            score=0,
            page=None,
            section=None,
            char_start=0,
            char_end=12,
        )
    )
    await retriever.add(
        RetrievedChunk(
            chunk_id="00000000-0000-0000-0000-00000000000f",
            document_id=doc_b,
            org_id=None,
            title="Platform",
            content="zebra phrase",
            score=0,
            page=None,
            section=None,
            char_start=0,
            char_end=12,
        )
    )

    results = await retriever.search(
        RetrievalQuery(query="zebra", org_id=org_b, top_k=5, knowledge_refs=[doc_b])
    )
    assert [result.document_id for result in results] == [doc_b]


@pytest.mark.asyncio
async def test_pgvector_retriever_applies_filters_and_combines_rrf_scores():
    org_id = UUID("00000000-0000-0000-0000-00000000000a")
    document_id = UUID("00000000-0000-0000-0000-00000000000c")
    other_document_id = UUID("00000000-0000-0000-0000-00000000000d")
    chunk_id = UUID("00000000-0000-0000-0000-00000000000e")
    other_chunk_id = UUID("00000000-0000-0000-0000-00000000000f")
    reference = "approach.md"

    document = SimpleNamespace(title="Approach", source_filename=reference)
    other_document = SimpleNamespace(title="Other", source_filename="other.md")
    chunk = SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        org_id=org_id,
        content="first",
        page=None,
        section=None,
        char_start=0,
        char_end=5,
    )
    other_chunk = SimpleNamespace(
        id=other_chunk_id,
        document_id=other_document_id,
        org_id=org_id,
        content="second",
        page=None,
        section=None,
        char_start=0,
        char_end=6,
    )
    statements = []

    class Result:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class Session:
        def __init__(self):
            self._rows = [[(chunk, document)], [(chunk, document), (other_chunk, other_document)]]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, statement):
            statements.append(str(statement))
            return Result(self._rows.pop(0))

    def db_factory():
        return Session()

    results = await PgVectorRetriever(
        db_factory,
        FakeAdapter(),
        KnowledgeSettings(),
    ).search(
        RetrievalQuery(
            query="approach",
            org_id=org_id,
            top_k=5,
            knowledge_refs=[reference],
        )
    )

    assert [result.chunk_id for result in results] == [chunk_id, other_chunk_id]
    assert results[0].score == pytest.approx(2 / 61)
    assert results[1].score == pytest.approx(1 / 62)
    assert len(statements) == 2
    for statement in statements:
        assert "content_chunks.org_id" in statement
        assert "content_documents.is_published" in statement
        assert "source_filename IN" in statement
        assert "title IN" in statement
