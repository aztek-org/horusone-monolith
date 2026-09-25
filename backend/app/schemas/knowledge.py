"""Knowledge citation schemas exposed by training sessions."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


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


class Citation(BaseModel):
    """Source attribution for knowledge used in an ATC response."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    page: int | None = None
    section: str | None = None
    snippet: str
