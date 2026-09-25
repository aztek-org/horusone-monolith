"""Pydantic schemas for knowledge upload and retrieval responses."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class IngestStatusResponse(BaseModel):
    """Result returned after staging a document ingestion."""

    document_id: uuid.UUID
    chunk_count: int
    status: str


class RetrievedChunk(BaseModel):
    """Knowledge chunk metadata available to a training session."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    org_id: uuid.UUID | None = None
    title: str
    content: str
    score: float
    page: int | None = None
    section: str | None = None
    char_start: int
    char_end: int


class RetrievedChunkRead(RetrievedChunk):
    """Citation metadata and content returned for a retrieved chunk."""

    model_config = ConfigDict(from_attributes=True)


class Citation(BaseModel):
    """Source attribution for knowledge used in an ATC response."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    page: int | None = None
    section: str | None = None
    snippet: str


class KnowledgeSearchResponse(BaseModel):
    """A list of retrieved chunks."""

    results: list[RetrievedChunkRead]
