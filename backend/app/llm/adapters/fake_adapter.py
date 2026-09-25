"""Deterministic in-process LLM adapter for tests."""

from __future__ import annotations

import re

from app.config import LLMSettings
from app.llm.types import EmbeddingResult, GenerationRequest, GenerationResult

_REPLY_DIRECTIVE = re.compile(r"\[\[reply:(.*?)\]\]", re.DOTALL)


class FakeAdapter:
    """Return deterministic text and embedding vectors without a provider."""

    provider = "fake"
    provider_is_external = False

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings
        self.calls: list[GenerationRequest] = []

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Return the first inline reply directive, or the standard fallback text."""
        self.calls.append(request)
        match = _REPLY_DIRECTIVE.search(request.prompt)
        text = match.group(1).strip() if match else "Say again, transmission unclear."
        return GenerationResult(
            text=text,
            provider=self.provider,
            model="fake",
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Return one deterministic 768-dimensional vector per input."""
        return EmbeddingResult(
            vectors=[[0.0] * 768 for _ in texts],
            provider=self.provider,
            model="fake",
            dimensions=768,
        )
