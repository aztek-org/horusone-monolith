"""Value types shared by knowledge ingestion and retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class DocumentUpload:
    """Source bytes and tenancy metadata supplied to the ingestor."""

    title: str
    source_filename: str
    content: bytes
    org_id: uuid.UUID | None
    created_by: uuid.UUID | None
    is_published: bool = False
    knowledge_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IngestResult:
    """The durable outcome of one successful document ingestion."""

    document_id: uuid.UUID
    chunk_count: int
    embedding_dimensions: int
    status: str


@dataclass(frozen=True)
class RetrievalQuery:
    """A tenant-scoped hybrid retrieval request."""

    query: str
    org_id: uuid.UUID | None
    top_k: int
    knowledge_refs: list[str] = field(default_factory=list)
    mode: Literal["hybrid", "vector", "text"] = "hybrid"


@dataclass(frozen=True)
class RetrievedChunk:
    """A citation-ready chunk returned by a retriever."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    org_id: uuid.UUID | None
    title: str
    content: str
    score: float
    page: int | None
    section: str | None
    char_start: int
    char_end: int


class KnowledgeRetriever(Protocol):
    """The narrow retrieval seam consumed by the training session module."""

    async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]: ...


class EmbeddingDimensionMismatchError(RuntimeError):
    """The provider returned vectors with a different dimension than configured."""


EmbeddingDimensionMismatch = EmbeddingDimensionMismatchError


class QuotaExceededError(RuntimeError):
    """A document would exceed the tenant's configured chunk quota."""


QuotaExceeded = QuotaExceededError
