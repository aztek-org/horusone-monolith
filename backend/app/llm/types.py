"""Narrow language-model interface shared by provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.llm.scene_constraints import SceneConstraints

GenerationPurpose = Literal[
    "atc_response",
    "weather_briefing",
    "student_evaluation",
    "flight_plan_parse",
    "readback_evaluation",
    "knowledge_embedding",
]


@dataclass(frozen=True)
class GenerationRequest:
    """A provider-independent generation request."""

    prompt: str
    purpose: GenerationPurpose
    scene_constraints: SceneConstraints = SceneConstraints()
    language: str = "en"


@dataclass(frozen=True)
class GenerationResult:
    """Generated text and its provider provenance."""

    text: str
    provider: str
    model: str
    fallback_used: bool


@dataclass(frozen=True)
class EmbeddingResult:
    """Embedding vectors and their provider provenance."""

    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int


class LLMModule(Protocol):
    """Operations required from every generation and embedding provider."""

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...


class LLMTransientError(RuntimeError):
    """Provider timed out or returned a transient error; eligible for fallback."""


class LLMUsageError(RuntimeError):
    """Provider rejected the request; not eligible for fallback."""


class LLMUnavailableError(RuntimeError):
    """No permitted provider could complete a request."""

    def __init__(self, message: str, *, fallback_attempted: bool) -> None:
        super().__init__(message)
        self.fallback_attempted = fallback_attempted
