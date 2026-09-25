"""Self-hosted Ollama generation and embedding adapter."""

from __future__ import annotations

import asyncio

import httpx
from langchain_community.llms import Ollama
from ollama import Client

from app.config import LLMSettings
from app.llm.scene_constraints import SceneConstraints, merge
from app.llm.types import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMTransientError,
    LLMUsageError,
)


class OllamaAdapter:
    """Generate and embed through one reusable self-hosted Ollama client."""

    provider = "ollama"
    provider_is_external = False

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self._client = Ollama(
            base_url=settings.base_url,
            model=settings.model,
            temperature=settings.temperature,
            num_predict=settings.max_output_tokens,
        )
        self._embedding_client = Client(settings.base_url)
        self._base_constraints = SceneConstraints(
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate text with scene overrides applied to configured defaults."""
        constraints = merge(self._base_constraints, request.scene_constraints)
        try:
            text = await asyncio.wait_for(
                self._client.ainvoke(
                    request.prompt,
                    temperature=constraints.temperature,
                    num_predict=constraints.max_output_tokens,
                ),
                timeout=self.settings.timeout_seconds,
            )
        except (asyncio.TimeoutError, httpx.TransportError) as exc:
            raise LLMTransientError(str(exc)) from exc
        except Exception as exc:
            raise LLMUsageError(str(exc)) from exc

        return GenerationResult(
            text=text,
            provider=self.provider,
            model=self.settings.model,
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed texts with the configured Ollama embedding model."""
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._embedding_client.embed,
                    model=self.settings.embedding_model,
                    input=texts,
                ),
                timeout=self.settings.timeout_seconds,
            )
        except (asyncio.TimeoutError, httpx.TransportError) as exc:
            raise LLMTransientError(str(exc)) from exc
        except Exception as exc:
            raise LLMUsageError(str(exc)) from exc

        vectors = [[float(value) for value in vector] for vector in response.embeddings]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider,
            model=self.settings.embedding_model,
            dimensions=len(vectors[0]) if vectors else 0,
        )
