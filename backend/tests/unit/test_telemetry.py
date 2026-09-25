"""Unit tests for operational telemetry wiring (ADR-009)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Sampler, SamplingResult
from opentelemetry.trace import SpanContext

from app.config import TraceSettings
from app.observability import telemetry
from app.observability.telemetry import configure_telemetry, span_for_session

ORG_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")

# The only attributes ``span_for_session`` may put on a span. ADR-009 keeps
# prompts, transcripts, and retrieved knowledge in PostgreSQL, never on a span.
CORRELATION_KEYS = {"session_id", "org_id"}


def _settings(*, otel_endpoint: str | None = None, log_level: str = "INFO") -> TraceSettings:
    return TraceSettings(retention_days=90, otel_endpoint=otel_endpoint, log_level=log_level)


def _installed_provider() -> TracerProvider:
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider), f"expected an SDK provider, got {provider!r}"
    return provider


def _installed_exporter() -> SpanExporter:
    """The single exporter ``configure_telemetry`` wired up.

    The SDK exposes no public accessor for the installed processors, and
    "exactly one of these" is the property idempotency and the exporter choice
    both turn on, so the test reaches into the SDK.
    """
    processors = _installed_provider()._active_span_processor._span_processors
    assert len(processors) == 1, f"expected one span processor, got {processors!r}"
    return processors[0].span_exporter


def _collect_spans() -> InMemorySpanExporter:
    """Subscribe to the real provider so a test can read the real spans back."""
    collector = InMemorySpanExporter()
    _installed_provider().add_span_processor(SimpleSpanProcessor(collector))
    return collector


class _ExplodingSampler(Sampler):
    """A real SDK sampler whose failure stands in for an unusable provider."""

    def should_sample(self, *args: Any, **kwargs: Any) -> SamplingResult:
        raise RuntimeError("sampler unavailable")

    def get_description(self) -> str:
        return "ExplodingSampler"


class _ExplodingExporter(SpanExporter):
    """A real exporter whose failure stands in for an unreachable collector."""

    def __init__(self) -> None:
        self.attempts = 0

    def export(self, spans: Any) -> Any:
        self.attempts += 1
        raise RuntimeError("collector unreachable")

    def shutdown(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _isolate_telemetry():
    """Give each test a clean, self-consistent process-wide OTel configuration.

    ``configure_telemetry`` and ``set_tracer_provider`` are process-wide and
    once-only by design, so a test can only observe a real installation if it
    first undoes whatever an earlier test installed. The asyncpg patch is
    unwound too, otherwise "already instrumented" would be the state under
    test. Everything is restored afterwards.
    """
    saved_provider = trace._TRACER_PROVIDER
    saved_once = trace._TRACER_PROVIDER_SET_ONCE._done
    saved_configured = telemetry._configured
    was_instrumented = telemetry._asyncpg_instrumentor._is_instrumented_by_opentelemetry
    if was_instrumented:
        telemetry._asyncpg_instrumentor.uninstrument()
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    telemetry._configured = False
    try:
        yield
    finally:
        if telemetry._asyncpg_instrumentor._is_instrumented_by_opentelemetry:
            telemetry._asyncpg_instrumentor.uninstrument()
        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            provider.shutdown()
        trace._TRACER_PROVIDER = saved_provider
        trace._TRACER_PROVIDER_SET_ONCE._done = saved_once
        telemetry._configured = saved_configured
        if was_instrumented:
            telemetry._asyncpg_instrumentor.instrument()


# ---------------------------------------------------------------------------
# The brief's smoke test
# ---------------------------------------------------------------------------


def test_console_exporter_configured_without_endpoint():
    configure_telemetry(TraceSettings(retention_days=90, otel_endpoint=None, log_level="INFO"))
    with span_for_session(1, uuid.uuid4()) as span:
        span.set_attribute("session_id", 1)
    assert span.is_recording() or not span.is_recording()  # exporter smoke test, no exception


# ---------------------------------------------------------------------------
# Exporter choice
# ---------------------------------------------------------------------------


def test_no_endpoint_selects_the_console_exporter():
    configure_telemetry(_settings())

    assert isinstance(_installed_exporter(), ConsoleSpanExporter)


def test_otlp_endpoint_falls_back_to_console_when_the_exporter_is_absent(caplog):
    """ADR-009 makes the exporter a deployment choice, never a hard dependency.

    The OTLP exporter ships in its own distribution, which this backend does
    not depend on, so a configured endpoint must degrade to the console with a
    warning rather than take the process down or export nothing at all.
    """
    with caplog.at_level("WARNING", logger=telemetry.__name__):
        configure_telemetry(_settings(otel_endpoint="http://collector.internal:4318"))

    assert isinstance(_installed_exporter(), ConsoleSpanExporter)
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in caplog.text
    assert "opentelemetry-exporter-otlp-proto-http" in caplog.text


def test_resource_identifies_the_service_and_environment():
    configure_telemetry(_settings(log_level="DEBUG"))

    attributes = _installed_provider().resource.attributes
    assert attributes["service.name"] == "horus-backend"
    assert attributes["deployment.environment"] == "DEBUG"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def _asyncpg_wrapper_depth(method: str = "execute") -> int:
    """How many times ``asyncpg``'s method has been wrapped by wrapt."""
    depth = 0
    wrapped: Any = getattr(asyncpg.connection.Connection, method)
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
        depth += 1
    return depth


def test_repeated_configuration_installs_one_pipeline(caplog):
    settings = _settings()

    with caplog.at_level("WARNING"):
        configure_telemetry(settings)
        provider = _installed_provider()
        exporter = _installed_exporter()
        configure_telemetry(settings)
        configure_telemetry(_settings(log_level="ERROR"))

    assert trace.get_tracer_provider() is provider
    assert _installed_exporter() is exporter
    # Reconfiguring must be silent: without the guard, a leaked provider or a
    # re-applied instrumentor shows up as an "overriding"/"already
    # instrumented" warning from OTel on every lifespan.
    complaints = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("opentelemetry")
    ]
    assert complaints == []
    assert _asyncpg_wrapper_depth() == 1


def test_fastapi_app_is_instrumented_once():
    application = FastAPI()

    @application.get("/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), application)
    configure_telemetry(_settings(), application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get("/probe").status_code == 200

    assert application._is_instrumented_by_opentelemetry is True
    assert [span.name for span in collector.get_finished_spans()].count("GET /probe") == 1


# ---------------------------------------------------------------------------
# Telemetry must never break the product
# ---------------------------------------------------------------------------


def test_span_creation_failure_does_not_reach_the_caller():
    trace.set_tracer_provider(TracerProvider(sampler=_ExplodingSampler()))
    telemetry._configured = True

    reached: list[str] = []
    with span_for_session(7, ORG_ID) as span:
        reached.append("body ran")
        span.set_attribute("session_id", 7)

    assert reached == ["body ran"]
    assert not span.is_recording()


def test_exporter_failure_does_not_break_the_session_span():
    exporter = _ExplodingExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    telemetry._configured = True

    reached: list[str] = []
    with span_for_session(7, ORG_ID) as span:
        span.set_attribute("graph.node", "respond")
        reached.append("body ran")

    assert reached == ["body ran"]
    assert exporter.attempts == 1, "the exporter really was reached, and really did fail"


def test_caller_exceptions_still_propagate():
    configure_telemetry(_settings())

    with pytest.raises(RuntimeError, match="product failure"), span_for_session(7, ORG_ID):
        raise RuntimeError("product failure")


def test_configuration_failure_leaves_the_backend_running(monkeypatch: pytest.MonkeyPatch):
    def explode(settings: TraceSettings) -> SpanExporter:
        raise RuntimeError("no telemetry for you")

    monkeypatch.setattr(telemetry, "_build_exporter", explode)
    configure_telemetry(_settings())  # must not raise
    assert telemetry._configured is False

    # The backend keeps serving: a session span still works, just untraced.
    reached: list[str] = []
    with span_for_session(7, ORG_ID):
        reached.append("body ran")
    assert reached == ["body ran"]


# ---------------------------------------------------------------------------
# Privacy: spans carry identifiers and timings, never product content
# ---------------------------------------------------------------------------


def test_session_span_carries_only_correlation_keys():
    configure_telemetry(_settings())
    collector = _collect_spans()

    with span_for_session(42, ORG_ID):
        pass
    with span_for_session(43, None):
        pass

    tenant_span, anonymous_span = collector.get_finished_spans()
    assert tenant_span.name == "session.exchange"
    assert dict(tenant_span.attributes) == {"session_id": 42, "org_id": str(ORG_ID)}
    assert set(tenant_span.attributes) == CORRELATION_KEYS
    # org_id is omitted rather than reported as null, so absence means "no tenant".
    assert dict(anonymous_span.attributes) == {"session_id": 43}


def test_session_span_carries_no_prompt_or_transcript_content():
    configure_telemetry(_settings())
    collector = _collect_spans()

    # Graph node and provider metadata are allowed; product content is not.
    with span_for_session(42, ORG_ID) as span:
        span.set_attribute("graph.node", "respond")
        span.set_attribute("llm.provider", "ollama")

    exported = collector.get_finished_spans()[0]
    assert set(exported.attributes) == CORRELATION_KEYS | {"graph.node", "llm.provider"}

    serialised = json.dumps(exported.to_json())
    for content_field in ("transcript", "prompt", "chunks", "student_said", "atc_reply"):
        assert content_field not in serialised


def test_span_context_carries_a_valid_sampled_trace_id():
    configure_telemetry(_settings())

    with span_for_session(42, ORG_ID) as span:
        context = span.get_span_context()

    assert isinstance(context, SpanContext)
    assert context.is_valid
    assert context.trace_flags.sampled
