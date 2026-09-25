"""OpenAI-compatible NVIDIA NIM generation and embedding adapter."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import LLMSettings
from app.llm.scene_constraints import SceneConstraints, merge
from app.llm.types import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMTransientError,
    LLMUsageError,
)


class NvidiaNIMAdapter:
    """Generate and embed through an OpenAI-compatible NVIDIA NIM endpoint."""

    provider = "nvidia-nim"
    provider_is_external = True

    def __init__(self, settings: LLMSettings) -> None:
        if not settings.api_key:
            raise LLMUsageError("NVIDIA_NIM_API_KEY is required")
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self._base_constraints = SceneConstraints(
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.api_key}"}

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers=self._headers(),
                )
            if response.status_code >= 500:
                raise LLMTransientError(f"NVIDIA NIM returned {response.status_code}")
            if response.is_error:
                raise LLMUsageError(f"NVIDIA NIM returned {response.status_code}")
            return response.json()
        except (asyncio.TimeoutError, httpx.TransportError) as exc:
            raise LLMTransientError(str(exc)) from exc

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate text with scene overrides applied to configured defaults."""
        constraints = merge(self._base_constraints, request.scene_constraints)
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": constraints.temperature,
            "max_tokens": constraints.max_output_tokens,
        }
        try:
            response = await self._post("/v1/chat/completions", payload)
            text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMUsageError("NVIDIA NIM returned an invalid response") from exc

        return GenerationResult(
            text=text,
            provider=self.provider,
            model=self.settings.model,
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed texts with the configured NVIDIA NIM embedding model."""
        payload = {"model": self.settings.embedding_model, "input": texts}
        try:
            response = await self._post("/v1/embeddings", payload)
            ordered = sorted(
                response["data"],
                key=lambda item: item.get("index", 0),
            )
            vectors = [
                [float(value) for value in item["embedding"]]
                for item in ordered
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMUsageError("NVIDIA NIM returned an invalid response") from exc

        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider,
            model=self.settings.embedding_model,
            dimensions=len(vectors[0]) if vectors else 0,
        )
