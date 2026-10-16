"""Knowledge retriever composition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.knowledge.retrieval.fake import FakeRetriever
from app.knowledge.retrieval.pgvector import PgVectorRetriever
from app.knowledge.types import KnowledgeRetriever
from app.llm.types import LLMModule


def build_retriever(
    settings: Settings,
    db_factory: Callable[[], Any],
    llm: LLMModule,
) -> KnowledgeRetriever:
    """Build the production pgvector adapter or the local in-memory adapter."""
    if settings.environment == "production":
        return PgVectorRetriever(db_factory, llm, settings.knowledge)
    return FakeRetriever()
