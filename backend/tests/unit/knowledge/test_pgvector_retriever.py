import pytest

from app.knowledge.retrieval.fake import FakeRetriever
from app.knowledge.types import RetrievalQuery, RetrievedChunk


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
