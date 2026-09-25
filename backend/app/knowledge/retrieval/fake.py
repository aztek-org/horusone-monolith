"""In-memory retriever used outside production."""

from __future__ import annotations

import re

from app.knowledge.types import RetrievalQuery, RetrievedChunk

_TOKEN_PATTERN = re.compile(r"\w+")


class FakeRetriever:
    """A small deterministic retriever for development and route tests."""

    def __init__(self) -> None:
        self._chunks: list[RetrievedChunk] = []

    async def add(self, chunk: RetrievedChunk) -> None:
        """Add a citation-ready chunk to the local result set."""
        self._chunks.append(chunk)

    async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        """Return chunks matching the tenant, references, and query tokens."""
        query_tokens = set(_TOKEN_PATTERN.findall(query.query.lower()))
        candidates: list[tuple[float, RetrievedChunk]] = []
        for chunk in self._chunks:
            if chunk.org_id not in {query.org_id, None}:
                continue
            if query.knowledge_refs and not (
                str(chunk.document_id) in query.knowledge_refs
                or chunk.title in query.knowledge_refs
            ):
                continue
            chunk_tokens = set(_TOKEN_PATTERN.findall(chunk.content.lower()))
            score = float(len(query_tokens & chunk_tokens))
            if score:
                candidates.append((score, chunk))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                org_id=chunk.org_id,
                title=chunk.title,
                content=chunk.content,
                score=score,
                page=chunk.page,
                section=chunk.section,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
            for score, chunk in candidates[: query.top_k]
        ]
