"""Readiness must reflect the configured provider, not a hardcoded one.

``/health/ready`` used to probe ``<LLM_BASE_URL>/api/tags``, which only exists
for Ollama: a healthy Groq or NVIDIA NIM deployment answered 404 and reported
itself not ready.  These tests pin that the probe is delegated to the adapter.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import health
from app.config import Settings
from app.llm.routing import build_llm


class _StubLLM:
    """Adapter double whose probe reports whatever the test needs."""

    def __init__(self, status: str = "ok", error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.probes = 0

    async def probe(self) -> str:
        self.probes += 1
        if self.error is not None:
            raise self.error
        return self.status


def _request(llm: object | None) -> Any:
    state = SimpleNamespace() if llm is None else SimpleNamespace(llm=llm)
    return SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.asyncio
async def test_probe_delegates_to_the_configured_adapter() -> None:
    llm = _StubLLM("ok")

    assert await health._probe_llm(_request(llm)) == "ok"
    assert llm.probes == 1


@pytest.mark.asyncio
async def test_probe_reports_a_degraded_provider() -> None:
    assert await health._probe_llm(_request(_StubLLM("degraded"))) == "degraded"


@pytest.mark.asyncio
async def test_probe_reports_an_unreachable_provider() -> None:
    assert await health._probe_llm(_request(_StubLLM("unreachable"))) == "unreachable"


@pytest.mark.asyncio
async def test_probe_survives_an_adapter_that_raises() -> None:
    llm = _StubLLM(error=RuntimeError("probe exploded"))

    assert await health._probe_llm(_request(llm)) == "unreachable"


@pytest.mark.asyncio
async def test_probe_reports_unreachable_when_no_provider_is_configured() -> None:
    assert await health._probe_llm(_request(None)) == "unreachable"


def test_probe_uses_the_routers_own_provider_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A built router is probed through its primary, in that provider's protocol."""
    llm = build_llm(
        Settings(
            _env_file=None,
            environment="testing",
            llm={"provider": "fake", "base_url": "", "model": "fake"},
        )
    )
    primary = llm.primary
    seen: list[int] = []

    async def probe() -> str:
        seen.append(1)
        return "ok"

    monkeypatch.setattr(primary, "probe", probe)

    assert asyncio.run(llm.probe()) == "ok"
    assert seen == [1]


def test_readiness_reports_the_llm_field(client: TestClient, monkeypatch) -> None:
    """The response names the provider, and a healthy one keeps ``ready`` true."""
    monkeypatch.setattr(health, "_probe_database", _returning("ok"))
    monkeypatch.setattr(health, "_probe_redis", _returning("ok"))

    response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert "llm" in data["services"]
    assert "ollama" not in data["services"]
    assert data["services"]["llm"] == "loaded"
    assert data["ready"] is True


def test_readiness_is_false_when_the_provider_is_down(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(health, "_probe_database", _returning("ok"))
    monkeypatch.setattr(health, "_probe_redis", _returning("ok"))
    monkeypatch.setattr(health, "_probe_llm", _returning("unreachable"))

    data = client.get("/health/ready").json()

    assert data["ready"] is False
    assert data["services"]["llm"] == "unreachable"


def _returning(value: str):
    async def probe(*_args: object, **_kwargs: object) -> str:
        return value

    return probe
