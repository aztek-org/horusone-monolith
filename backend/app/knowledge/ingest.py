"""One transactional entry point for document ingestion."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import KnowledgeSettings
from app.knowledge.chunking import chunk_document
from app.knowledge.documents import extract_text, source_type
from app.knowledge.types import (
    DocumentUpload,
    EmbeddingDimensionMismatch,
    IngestResult,
    QuotaExceeded,
)
from app.llm.types import EmbeddingResult, LLMModule
from app.models.knowledge_document import ContentChunk, ContentDocument, IngestEvent


class KnowledgeIngestor:
    """Extract, chunk, embed, and stage one knowledge document."""

    def __init__(
        self,
        llm: LLMModule,
        settings: KnowledgeSettings,
        embedding_model: str,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._embedding_model = embedding_model

    async def _count_org_chunks(self, db: AsyncSession, org_id: UUID | None) -> int:
        result = await db.execute(
            select(func.count(ContentChunk.id)).where(ContentChunk.org_id == org_id)
        )
        return int(result.scalar() or 0)

    async def ingest(self, db: AsyncSession, upload: DocumentUpload) -> IngestResult:
        """Stage a document and its chunks without committing the transaction.

        The caller owns the transaction boundary. Quota validation deliberately
        happens before the embedding provider is called.

        **A failed ingest leaves no durable trace by default.** The ``failed``
        ``IngestEvent`` added in the ``except`` branch is only ever flushed on
        the caller's session, and the caller re-raises and rolls back, so the
        audit row is discarded along with the partial document and chunks. That
        is the correct behaviour for the document -- there is nothing half-written
        to keep -- but it means "failed ingests are audited" is not true of a
        caller that owns the transaction. To make the failure survive, commit the
        failure event on its own connection, outside the caller's transaction, or
        log it where the transaction cannot reach it. See
        ``docs/knowledge/INGEST.md`` for the operator-facing statement.
        """
        text, hints = extract_text(upload.source_filename, upload.content)
        spans = chunk_document(
            text, self._settings.chunk_size, self._settings.chunk_overlap
        )
        existing = await self._count_org_chunks(db, upload.org_id)
        if existing + len(spans) > self._settings.default_chunk_quota:
            raise QuotaExceeded(f"org {upload.org_id} would exceed chunk quota")

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        document = ContentDocument(
            title=upload.title,
            source_filename=upload.source_filename,
            source_type=source_type(upload.source_filename),
            content_hash=text_hash,
            is_published=upload.is_published,
            org_id=upload.org_id,
            created_by=upload.created_by,
        )
        embedding: EmbeddingResult | None = None
        try:
            db.add(document)
            await db.flush()
            embedding = await self._llm.embed([text[start:end] for start, end, _ in spans])
            if embedding.dimensions != self._settings.embedding_dimensions:
                raise EmbeddingDimensionMismatch(
                    f"expected {self._settings.embedding_dimensions}, "
                    f"got {embedding.dimensions}"
                )

            for index, ((start, end, token_count), vector) in enumerate(
                zip(spans, embedding.vectors)
            ):
                db.add(
                    ContentChunk(
                        document_id=document.id,
                        org_id=upload.org_id,
                        chunk_index=index,
                        content=text[start:end],
                        token_count=token_count,
                        embedding=vector,
                        page=hints.get("page"),
                        section=hints.get("section"),
                        char_start=start,
                        char_end=end,
                    )
                )
            db.add(
                IngestEvent(
                    document_id=document.id,
                    org_id=upload.org_id,
                    status="succeeded",
                    embedding_model=self._embedding_model,
                    embedding_dimensions=embedding.dimensions,
                    chunk_size=self._settings.chunk_size,
                    chunk_overlap=self._settings.chunk_overlap,
                    chunk_count=len(spans),
                )
            )
            document.chunk_count = len(spans)
            document.ingested_at = datetime.now(timezone.utc)
            await db.flush()
        except Exception as exc:
            if document.id is not None:
                db.add(
                    IngestEvent(
                        document_id=document.id,
                        org_id=upload.org_id,
                        status="failed",
                        embedding_model=self._embedding_model,
                        embedding_dimensions=(
                            embedding.dimensions if embedding is not None else 0
                        ),
                        chunk_size=self._settings.chunk_size,
                        chunk_overlap=self._settings.chunk_overlap,
                        chunk_count=len(spans),
                        error=str(exc),
                    )
                )
            raise

        return IngestResult(
            document_id=document.id,
            chunk_count=len(spans),
            embedding_dimensions=embedding.dimensions,
            status="succeeded",
        )


__all__ = [
    "EmbeddingDimensionMismatch",
    "KnowledgeIngestor",
    "QuotaExceeded",
]
