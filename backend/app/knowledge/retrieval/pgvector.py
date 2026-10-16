"""PostgreSQL pgvector hybrid retriever."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.config import KnowledgeSettings
from app.knowledge.types import (
    EmbeddingDimensionMismatch,
    RetrievalQuery,
    RetrievedChunk,
)
from app.llm.types import LLMModule
from app.models.knowledge_document import ContentChunk, ContentDocument


class PgVectorRetriever:
    """Search published chunks with tenant-safe dense and text legs."""

    def __init__(
        self,
        db_factory: Callable[[], Any],
        llm: LLMModule,
        settings: KnowledgeSettings,
    ) -> None:
        self._db_factory: Callable[[], AsyncSession]
        candidate_factory = db_factory()
        if hasattr(candidate_factory, "__call__") and not hasattr(candidate_factory, "__aenter__"):
            self._db_factory = cast(Callable[[], AsyncSession], candidate_factory)
        else:
            self._db_factory = db_factory
        self._llm = llm
        self._settings = settings

    @staticmethod
    def _reference_filter(query: RetrievalQuery) -> ColumnElement[bool] | None:
        """Match UUID references and the filename/title form used by Scenes."""
        if not query.knowledge_refs:
            return None

        uuid_refs = []
        name_refs = []
        for reference in query.knowledge_refs:
            try:
                uuid_refs.append(UUID(reference))
            except ValueError:
                name_refs.append(reference)

        clauses: list[ColumnElement[bool]] = []
        if uuid_refs:
            clauses.append(ContentChunk.document_id.in_(uuid_refs))
        if name_refs:
            clauses.append(
                or_(
                    ContentDocument.source_filename.in_(name_refs),
                    ContentDocument.title.in_(name_refs),
                )
            )
        if not clauses:
            return ContentChunk.document_id.in_([])
        return or_(*clauses)

    async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        """Run the requested search legs and merge them with RRF."""
        embedding = None
        if query.mode in {"hybrid", "vector"}:
            embedding = await self._llm.embed([query.query])
            if embedding.dimensions != self._settings.embedding_dimensions:
                raise EmbeddingDimensionMismatch(
                    f"expected {self._settings.embedding_dimensions}, got {embedding.dimensions}"
                )

        filters = [
            or_(ContentChunk.org_id == query.org_id, ContentChunk.org_id.is_(None)),
            ContentDocument.is_published.is_(True),
        ]
        reference_filter = self._reference_filter(query)
        if reference_filter is not None:
            filters.append(reference_filter)

        dense_rows: Sequence[Any] = []
        text_rows: Sequence[Any] = []
        async with self._db_factory() as db:
            if embedding is not None:
                vector_value = literal(
                    embedding.vectors[0], Vector(self._settings.embedding_dimensions)
                )
                dense_statement = (
                    select(ContentChunk, ContentDocument)
                    .join(ContentDocument, ContentChunk.document_id == ContentDocument.id)
                    .where(*filters)
                    .order_by(ContentChunk.embedding.op("<=>")(vector_value))
                    .limit(query.top_k)
                )
                dense_rows = (await db.execute(dense_statement)).all()

            if query.mode in {"hybrid", "text"}:
                ts_vector = func.to_tsvector("english", ContentChunk.content)
                ts_query = func.plainto_tsquery("english", query.query)
                rank = func.ts_rank_cd(ts_vector, ts_query)
                text_statement = (
                    select(ContentChunk, ContentDocument)
                    .join(ContentDocument, ContentChunk.document_id == ContentDocument.id)
                    .where(*filters, ts_vector.op("@@")(ts_query))
                    .order_by(rank.desc())
                    .limit(query.top_k)
                )
                text_rows = (await db.execute(text_statement)).all()

        scores: dict[UUID, float] = {}
        chunks: dict[UUID, RetrievedChunk] = {}
        for rank_number, row in enumerate(dense_rows, start=1):
            self._record_row(row, scores, chunks, 1 / (60 + rank_number))
        for rank_number, row in enumerate(text_rows, start=1):
            self._record_row(row, scores, chunks, 1 / (60 + rank_number))

        ordered_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
        return [
            RetrievedChunk(
                **{
                    **vars(chunks[chunk_id]),
                    "score": scores[chunk_id],
                }
            )
            for chunk_id in ordered_ids[: query.top_k]
        ]

    @staticmethod
    def _record_row(
        row: Any, scores: dict[UUID, float], chunks: dict[UUID, RetrievedChunk], score: float
    ) -> None:
        """Add one SQL row to the RRF accumulator."""
        chunk, document = row[0], row[1]
        chunk_id = chunk.id
        scores[chunk_id] = scores.get(chunk_id, 0.0) + score
        chunks.setdefault(
            chunk_id,
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                org_id=chunk.org_id,
                title=document.title,
                content=chunk.content,
                score=score,
                page=chunk.page,
                section=chunk.section,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                source_filename=document.source_filename,
            ),
        )
