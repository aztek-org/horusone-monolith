"""Provider construction and fallback routing."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.config import Settings
from app.llm.types import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMModule,
    LLMTransientError,
    LLMUnavailableError,
)

if TYPE_CHECKING:
    from app.config import LLMSettings


def build_llm(settings: Settings) -> LLMModule:
    """Build the configured primary adapter and its optional fallback."""
    from app.llm.adapters.fake_adapter import FakeAdapter
    from app.llm.adapters.groq_adapter import GroqAdapter
    from app.llm.adapters.nvidia_nim_adapter import NvidiaNIMAdapter
    from app.llm.adapters.ollama_adapter import OllamaAdapter

    factories: dict[str, type] = {
        "ollama": OllamaAdapter,
        "groq": GroqAdapter,
        "nvidia-nim": NvidiaNIMAdapter,
        "fake": FakeAdapter,
    }
    llm: LLMSettings = settings.llm
    if llm.provider not in factories:
        raise ValueError(f"Unknown LLM_PROVIDER {llm.provider!r}")

    primary = factories[llm.provider](llm)
    fallback = None
    if llm.fallback_provider and llm.provider != llm.fallback_provider:
        fallback = factories[llm.fallback_provider](llm)
    return FallbackLLM(
        primary,
        fallback,
        allow_external_fallback=llm.allow_external_fallback,
    )


class FallbackLLM:
    """Try a permitted fallback once after a transient primary failure."""

    def __init__(
        self,
        primary: LLMModule,
        fallback: LLMModule | None,
        allow_external_fallback: bool,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.allow_external_fallback = allow_external_fallback

    @property
    def provider(self) -> str:
        """Return the primary adapter's provider name."""
        return str(getattr(self.primary, "provider", ""))

    @property
    def provider_is_external(self) -> bool:
        """Return whether prompts sent to the primary leave the deployment."""
        return bool(getattr(self.primary, "provider_is_external", False))

    def _fallback_is_permitted(self) -> bool:
        if self.fallback is None or not self.allow_external_fallback:
            return False
        fallback_is_external = bool(
            getattr(self.fallback, "provider_is_external", False)
        )
        return not (fallback_is_external and not self.provider_is_external)

    @staticmethod
    def _unavailable(error: Exception, *, fallback_attempted: bool) -> LLMUnavailableError:
        return LLMUnavailableError(
            str(error),
            fallback_attempted=fallback_attempted,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate text, falling back at most once for a transient failure."""
        try:
            return await self.primary.generate(request)
        except LLMTransientError as error:
            if not self._fallback_is_permitted():
                raise self._unavailable(error, fallback_attempted=False) from error

        assert self.fallback is not None
        try:
            result = await self.fallback.generate(request)
        except LLMTransientError as error:
            raise self._unavailable(error, fallback_attempted=True) from error
        return replace(result, fallback_used=True)

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed with the primary only; provider embedding models are incompatible."""
        try:
            return await self.primary.embed(texts)
        except LLMTransientError as error:
            raise self._unavailable(error, fallback_attempted=False) from error

    async def probe(self) -> str:
        """Report the primary provider's reachability, in its own protocol."""
        return await self.primary.probe()
