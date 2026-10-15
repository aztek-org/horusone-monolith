"""Unit tests for the knowledge upload/retrieval schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.knowledge import (
    Citation,
    IngestStatusResponse,
    KnowledgeSearchResponse,
    RetrievedChunk,
    RetrievedChunkRead,
)


def _chunk_kwargs() -> dict:
    return {
        "chunk_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "title": "AIM",
        "content": "text",
        "score": 0.9,
        "char_start": 0,
        "char_end": 4,
    }


class TestIngestStatusResponse:
    def test_accepts_status(self) -> None:
        response = IngestStatusResponse(
            document_id=uuid.uuid4(), chunk_count=3, status="staged"
        )
        assert response.chunk_count == 3

    def test_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            IngestStatusResponse(chunk_count=0)


class TestRetrievedChunk:
    def test_defaults_optional_metadata(self) -> None:
        chunk = RetrievedChunk(**_chunk_kwargs())
        assert chunk.org_id is None
        assert chunk.page is None
        assert chunk.section is None

    def test_requires_char_offsets(self) -> None:
        kwargs = _chunk_kwargs()
        kwargs.pop("char_end")
        with pytest.raises(ValidationError, match="char_end"):
            RetrievedChunk(**kwargs)

    def test_read_subclass_accepts_same_shape(self) -> None:
        chunk = RetrievedChunkRead(**_chunk_kwargs(), org_id=uuid.uuid4())
        assert chunk.score == 0.9


class TestCitation:
    def test_accepts_citation(self) -> None:
        citation = Citation(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            title="AIM",
            snippet="...",
        )
        assert citation.page is None

    def test_requires_snippet(self) -> None:
        with pytest.raises(ValidationError, match="snippet"):
            Citation(chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), title="AIM")


class TestKnowledgeSearchResponse:
    def test_wraps_results(self) -> None:
        response = KnowledgeSearchResponse(
            results=[RetrievedChunkRead(**_chunk_kwargs())]
        )
        assert len(response.results) == 1
