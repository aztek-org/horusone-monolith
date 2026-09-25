"""External Groq generation adapter."""

from __future__ import annotations

import asyncio

import httpx
from groq import APIConnectionError, APIStatusError
from langchain_groq import ChatGroq

from app.config import LLMSettings
from app.llm.scene_constraints import SceneConstraints, merge
from app.llm.types import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMTransientError,
    LLMUsageError,
)


class GroqAdapter:
    """Generate text through Groq's OpenAI-compatible API."""

    provider = "groq"
    provider_is_external = True

    def __init__(self, settings: LLMSettings) -> None:
        if not settings.api_key:
            raise LLMUsageError("GROQ_API_KEY is required")
        self.settings = settings
        self._client = ChatGroq(
            api_key=settings.api_key,  # type: ignore[arg-type]
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
            max_retries=0,
            timeout=settings.timeout_seconds,
        )
        self._base_constraints = SceneConstraints(
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate text with scene overrides applied to configured defaults."""
        constraints = merge(self._base_constraints, request.scene_constraints)
        try:
            response = await self._client.ainvoke(
                request.prompt,
                temperature=constraints.temperature,
                max_tokens=constraints.max_output_tokens,
            )
        except APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMTransientError(str(exc)) from exc
            raise LLMUsageError(str(exc)) from exc
        except (APIConnectionError, asyncio.TimeoutError, httpx.TransportError) as exc:
            raise LLMTransientError(str(exc)) from exc
        except Exception as exc:
            raise LLMUsageError(str(exc)) from exc

        if not isinstance(response.content, str):
            raise LLMUsageError("Groq returned a non-text response")
        return GenerationResult(
            text=response.content,
            provider=self.provider,
            model=self.settings.model,
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Reject embeddings because Groq is generation-only in v1."""
        raise LLMUsageError("Groq adapter does not support embeddings")
