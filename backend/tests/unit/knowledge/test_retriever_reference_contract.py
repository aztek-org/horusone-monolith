"""Both retrievers must answer the same ``knowledge_refs`` question.

``PgVectorRetriever`` accepts three reference forms — document UUID, source
filename, and document title — and ``FakeRetriever`` must accept the same three.
A Scene names its references in
``docs/architecture/scene-config.example.yaml``; if the two adapters disagree
about which forms resolve, the same Scene behaves differently in development
and in production, and the difference is invisible until an instructor asks why
the knowledge did not show up.

``tests/unit/knowledge/test_pgvector_retriever.py`` covers the pgvector side
(its compiled SQL is asserted to carry ``source_filename IN`` and ``title IN``).
This file covers the in-memory side, which had no filename case at all.
"""

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.config import KnowledgeSettings
from app.knowledge.retrieval.fake import FakeRetriever
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import RetrievalQuery, RetrievedChunk
from app.llm.adapters.fake_adapter import FakeAdapter

ORG_ID = UUID("00000000-0000-0000-0000-00000000000a")
DOCUMENT_ID = UUID("00000000-0000-0000-0000-00000000000c")
CHUNK_ID = UUID("00000000-0000-0000-0000-00000000000e")
FILENAME = "keflavik-approach-plate.md"
TITLE = "Keflavik ILS Runway 25L"


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        org_id=ORG_ID,
        title=TITLE,
        content="keflavik zebra approach",
        score=0,
        page=None,
        section=None,
        char_start=0,
        char_end=24,
        source_filename=FILENAME,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", [str(DOCUMENT_ID), FILENAME, TITLE])
async def test_fake_retriever_resolves_every_reference_form(reference: str) -> None:
    retriever = FakeRetriever()
    await retriever.add(_chunk())

    results = await retriever.search(
        RetrievalQuery(query="keflavik", org_id=ORG_ID, top_k=5, knowledge_refs=[reference])
    )

    assert [result.chunk_id for result in results] == [CHUNK_ID]


@pytest.mark.asyncio
async def test_fake_retriever_ignores_a_reference_it_cannot_resolve() -> None:
    retriever = FakeRetriever()
    await retriever.add(_chunk())

    results = await retriever.search(
        RetrievalQuery(
            query="keflavik",
            org_id=ORG_ID,
            top_k=5,
            knowledge_refs=["keflavik-approach-plate"],
        )
    )

    assert results == []


@pytest.mark.asyncio
async def test_pgvector_populates_source_filename_on_every_result() -> None:
    chunk = SimpleNamespace(
        id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        org_id=ORG_ID,
        content="keflavik zebra approach",
        page=None,
        section=None,
        char_start=0,
        char_end=24,
    )
    document = SimpleNamespace(title=TITLE, source_filename=FILENAME)

    class Result:
        def all(self):
            return [(chunk, document)]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _statement):
            return Result()

    results = await PgVectorRetriever(
        Session, FakeAdapter(), KnowledgeSettings()
    ).search(RetrievalQuery(query="keflavik", org_id=ORG_ID, top_k=5))

    assert [result.source_filename for result in results] == [FILENAME]
