import pytest

from app.llm.routing import FallbackLLM
from app.llm.scene_constraints import SceneConstraints, merge
from app.llm.types import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMTransientError,
    LLMUnavailableError,
    LLMUsageError,
)


class StubLLM:
    provider = "stub"
    provider_is_external = False

    def __init__(self, *, exc: Exception | None = None) -> None:
        self.exc = exc
        self.generate_calls = 0
        self.embed_calls = 0

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.generate_calls += 1
        if self.exc is not None:
            raise self.exc
        return GenerationResult(
            text="ok",
            provider=self.provider,
            model="m",
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls += 1
        if self.exc is not None:
            raise self.exc
        return EmbeddingResult(
            vectors=[[0.0]],
            provider=self.provider,
            model="e",
            dimensions=1,
        )


class ExternalStubLLM(StubLLM):
    provider = "groq"
    provider_is_external = True


REQUEST = GenerationRequest(prompt="p", purpose="atc_response")


@pytest.mark.asyncio
async def test_fallback_is_used_when_allowed() -> None:
    primary = ExternalStubLLM(exc=LLMTransientError("timeout"))
    fallback = ExternalStubLLM()

    result = await FallbackLLM(primary, fallback, allow_external_fallback=True).generate(REQUEST)

    assert result.text == "ok"
    assert result.fallback_used is True
    assert fallback.generate_calls == 1


@pytest.mark.asyncio
async def test_fallback_is_blocked_when_external_fallback_is_disallowed() -> None:
    fallback = ExternalStubLLM()
    llm = FallbackLLM(
        ExternalStubLLM(exc=LLMTransientError("timeout")),
        fallback,
        allow_external_fallback=False,
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await llm.generate(REQUEST)

    assert exc_info.value.fallback_attempted is False
    assert fallback.generate_calls == 0


@pytest.mark.asyncio
async def test_external_fallback_cannot_receive_self_hosted_primary_traffic() -> None:
    fallback = ExternalStubLLM()
    llm = FallbackLLM(
        StubLLM(exc=LLMTransientError("timeout")),
        fallback,
        allow_external_fallback=True,
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await llm.generate(REQUEST)

    assert exc_info.value.fallback_attempted is False
    assert fallback.generate_calls == 0


@pytest.mark.asyncio
async def test_embed_never_falls_back() -> None:
    fallback = ExternalStubLLM()
    llm = FallbackLLM(
        ExternalStubLLM(exc=LLMTransientError("timeout")),
        fallback,
        allow_external_fallback=True,
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await llm.embed(["a"])

    assert exc_info.value.fallback_attempted is False
    assert fallback.embed_calls == 0


@pytest.mark.asyncio
async def test_unavailable_records_that_a_usable_fallback_was_attempted() -> None:
    llm = FallbackLLM(
        ExternalStubLLM(exc=LLMTransientError("primary timeout")),
        ExternalStubLLM(exc=LLMTransientError("fallback timeout")),
        allow_external_fallback=True,
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await llm.generate(REQUEST)

    assert exc_info.value.fallback_attempted is True


@pytest.mark.asyncio
async def test_usage_error_does_not_fall_back() -> None:
    fallback = ExternalStubLLM()
    llm = FallbackLLM(
        ExternalStubLLM(exc=LLMUsageError("bad request")),
        fallback,
        allow_external_fallback=True,
    )

    with pytest.raises(LLMUsageError):
        await llm.generate(REQUEST)

    assert fallback.generate_calls == 0


def test_router_exposes_primary_provider_and_external_classification() -> None:
    primary = ExternalStubLLM()
    llm = FallbackLLM(primary, None, allow_external_fallback=False)

    assert llm.provider == "groq"
    assert llm.provider_is_external is True


def test_self_hosted_router_is_not_external() -> None:
    assert FallbackLLM(StubLLM(), None, allow_external_fallback=False).provider_is_external is False


def test_merge_uses_override_values_only_when_present() -> None:
    base = SceneConstraints(temperature=0.3, max_output_tokens=150)

    result = merge(base, SceneConstraints(temperature=0.7))

    assert result == SceneConstraints(temperature=0.7, max_output_tokens=150)
