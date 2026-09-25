from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from groq import InternalServerError

from app.config import LLMSettings, Settings
from app.llm.adapters.fake_adapter import FakeAdapter
from app.llm.adapters.groq_adapter import GroqAdapter
from app.llm.adapters.nvidia_nim_adapter import NvidiaNIMAdapter
from app.llm.adapters.ollama_adapter import OllamaAdapter
from app.llm.routing import FallbackLLM, build_llm
from app.llm.scene_constraints import SceneConstraints
from app.llm.types import GenerationRequest, LLMTransientError, LLMUsageError


def _settings(provider: str = "ollama", **overrides: Any) -> LLMSettings:
    values: dict[str, Any] = {
        "provider": provider,
        "base_url": "http://x:11434",
        "model": "m",
        "embedding_model": "nomic-embed-text",
        "temperature": 0.3,
        "max_output_tokens": 150,
        "timeout_seconds": 30.0,
        "allow_external_fallback": False,
        "fallback_provider": None,
        "api_key": None,
    }
    values.update(overrides)
    return LLMSettings(**values)


REQUEST = GenerationRequest(
    prompt="pilot transmission",
    purpose="atc_response",
    scene_constraints=SceneConstraints(temperature=0.7, max_output_tokens=220),
    language="es",
)


@pytest.mark.asyncio
async def test_fake_adapter_returns_first_inline_reply_and_records_request() -> None:
    adapter = FakeAdapter(_settings("fake"))
    request = GenerationRequest(
        prompt="before [[reply: cleared for takeoff runway 27 ]] after",
        purpose="atc_response",
        language="es",
    )

    result = await adapter.generate(request)

    assert result.text == "cleared for takeoff runway 27"
    assert result.provider == "fake"
    assert result.model == "fake"
    assert result.fallback_used is False
    assert adapter.calls == [request]


@pytest.mark.asyncio
async def test_fake_adapter_uses_first_of_multiple_inline_replies() -> None:
    adapter = FakeAdapter()

    result = await adapter.generate(
        GenerationRequest(
            prompt="[[reply:first]] and [[reply:second]]",
            purpose="readback_evaluation",
        )
    )

    assert result.text == "first"


@pytest.mark.asyncio
async def test_fake_adapter_uses_standard_fallback_without_directive() -> None:
    result = await FakeAdapter().generate(REQUEST)

    assert result.text == "Say again, transmission unclear."


@pytest.mark.asyncio
async def test_fake_adapter_embeds_each_text_as_768_dimensions() -> None:
    result = await FakeAdapter().embed(["a", "b"])

    assert result.vectors == [[0.0] * 768, [0.0] * 768]
    assert result.dimensions == 768
    assert result.provider == "fake"


def test_ollama_adapter_builds_once_with_grouped_settings() -> None:
    adapter = OllamaAdapter(_settings())

    assert adapter.provider == "ollama"
    assert adapter.provider_is_external is False
    assert adapter._client.base_url == "http://x:11434"
    assert adapter._client.model == "m"
    assert adapter._client.temperature == 0.3
    assert adapter._client.num_predict == 150


def test_ollama_adapter_uses_only_brief_provider_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.llm.adapters.ollama_adapter.Ollama", Client)

    OllamaAdapter(_settings(timeout_seconds=30.0))

    assert captured == {
        "base_url": "http://x:11434",
        "model": "m",
        "temperature": 0.3,
        "num_predict": 150,
    }


def test_ollama_adapter_builds_with_empty_base_url_outside_production() -> None:
    adapter = OllamaAdapter(_settings(base_url=""))

    assert adapter._client.base_url == ""


@pytest.mark.asyncio
async def test_ollama_generate_applies_scene_constraints_and_returns_result() -> None:
    adapter = OllamaAdapter(_settings())

    class Client:
        def __init__(self) -> None:
            self.call: tuple[str, dict[str, Any]] | None = None

        async def ainvoke(self, prompt: str, **kwargs: Any) -> str:
            self.call = (prompt, kwargs)
            return "roger"

    client = Client()
    adapter._client = client  # type: ignore[assignment]

    result = await adapter.generate(REQUEST)

    assert result.text == "roger"
    assert result.provider == "ollama"
    assert result.model == "m"
    assert client.call == (
        "pilot transmission",
        {"temperature": 0.7, "num_predict": 220},
    )


@pytest.mark.asyncio
async def test_ollama_transport_failure_is_transient() -> None:
    adapter = OllamaAdapter(_settings())

    class Client:
        async def ainvoke(self, prompt: str, **kwargs: Any) -> str:
            raise httpx.ConnectError("offline")

    adapter._client = Client()  # type: ignore[assignment]

    with pytest.raises(LLMTransientError):
        await adapter.generate(REQUEST)


@pytest.mark.asyncio
async def test_ollama_rejected_request_is_usage_error() -> None:
    adapter = OllamaAdapter(_settings())

    class Client:
        async def ainvoke(self, prompt: str, **kwargs: Any) -> str:
            raise ValueError("invalid model")

    adapter._client = Client()  # type: ignore[assignment]

    with pytest.raises(LLMUsageError):
        await adapter.generate(REQUEST)


@pytest.mark.asyncio
async def test_ollama_embed_returns_provider_vectors() -> None:
    adapter = OllamaAdapter(_settings())

    class Client:
        def embed(self, *, model: str, input: list[str]) -> Any:
            assert model == "nomic-embed-text"
            assert input == ["a", "b"]
            return SimpleNamespace(embeddings=[[1.0, 2.0], [3.0, 4.0]])

    adapter._embedding_client = Client()  # type: ignore[assignment]

    result = await adapter.embed(["a", "b"])

    assert result.vectors == [[1.0, 2.0], [3.0, 4.0]]
    assert result.dimensions == 2


def test_groq_adapter_requires_api_key() -> None:
    with pytest.raises(LLMUsageError) as exc_info:
        GroqAdapter(_settings("groq", base_url="https://api.groq.test"))

    assert str(exc_info.value) == "GROQ_API_KEY is required"


def test_nvidia_nim_adapter_requires_its_api_key() -> None:
    with pytest.raises(LLMUsageError) as exc_info:
        NvidiaNIMAdapter(_settings("nvidia-nim", base_url="http://nim.test"))

    assert str(exc_info.value) == "NVIDIA_NIM_API_KEY is required"


@pytest.mark.asyncio
async def test_groq_generate_uses_configured_client_and_constraints() -> None:
    adapter = GroqAdapter(
        _settings("groq", base_url="https://api.groq.test", api_key="secret")
    )

    class Message:
        content = "cleared to land"

    class Client:
        def __init__(self) -> None:
            self.call: tuple[Any, dict[str, Any]] | None = None

        async def ainvoke(self, prompt: Any, **kwargs: Any) -> Message:
            self.call = (prompt, kwargs)
            return Message()

    client = Client()
    adapter._client = client  # type: ignore[assignment]

    result = await adapter.generate(REQUEST)

    assert result.text == "cleared to land"
    assert result.provider == "groq"
    assert result.model == "m"
    assert client.call == (
        "pilot transmission",
        {"temperature": 0.7, "max_tokens": 220},
    )


@pytest.mark.asyncio
async def test_groq_server_failure_is_transient() -> None:
    adapter = GroqAdapter(
        _settings("groq", base_url="https://api.groq.test", api_key="secret")
    )

    class Client:
        async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
            request = httpx.Request("POST", "https://api.groq.test/chat")
            response = httpx.Response(503, request=request)
            raise InternalServerError("unavailable", response=response, body=None)

    adapter._client = Client()  # type: ignore[assignment]

    with pytest.raises(LLMTransientError):
        await adapter.generate(REQUEST)


@pytest.mark.asyncio
async def test_nvidia_nim_generate_posts_openai_compatible_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 30.0

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> httpx.Response:
            calls.append((url, json, headers))
            request = httpx.Request("POST", "http://nim.test")
            return httpx.Response(
                200,
                request=request,
                json={"choices": [{"message": {"content": "cleared"}}]},
            )

    monkeypatch.setattr("app.llm.adapters.nvidia_nim_adapter.httpx.AsyncClient", Client)
    adapter = NvidiaNIMAdapter(
        _settings("nvidia-nim", base_url="http://nim.test", api_key="secret")
    )

    result = await adapter.generate(REQUEST)

    assert result.text == "cleared"
    assert result.provider == "nvidia-nim"
    assert result.model == "m"
    assert calls == [
        (
            "http://nim.test/v1/chat/completions",
            {
                "model": "m",
                "messages": [{"role": "user", "content": "pilot transmission"}],
                "temperature": 0.7,
                "max_tokens": 220,
            },
            {"Authorization": "Bearer secret"},
        )
    ]


@pytest.mark.asyncio
async def test_nvidia_nim_server_error_is_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
            request = httpx.Request("POST", "http://nim.test")
            return httpx.Response(503, request=request)

    monkeypatch.setattr("app.llm.adapters.nvidia_nim_adapter.httpx.AsyncClient", Client)
    adapter = NvidiaNIMAdapter(
        _settings("nvidia-nim", base_url="http://nim.test", api_key="secret")
    )

    with pytest.raises(LLMTransientError):
        await adapter.generate(REQUEST)


def test_build_llm_returns_router_for_fake_provider() -> None:
    llm = build_llm(
        Settings(
            environment="testing",
            llm=_settings("fake", base_url="", model="fake"),
        )
    )

    assert isinstance(llm, FallbackLLM)
    assert llm.provider == "fake"
    assert llm.provider_is_external is False


def test_build_llm_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER 'unknown'"):
        build_llm(Settings(environment="testing", llm=_settings("unknown")))
