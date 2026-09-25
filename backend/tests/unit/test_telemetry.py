"""Unit tests for operational telemetry wiring (ADR-009)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from typing import Any, cast

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import SynchronousMultiSpanProcessor, TracerProvider
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
    exporters = [
        processor.span_exporter
        for processor in processors
        if hasattr(processor, "span_exporter")
    ]
    assert len(exporters) == 1, f"expected one span exporter, got {exporters!r}"
    return cast(SpanExporter, exporters[0])


def _collect_spans() -> InMemorySpanExporter:
    """Subscribe to the real provider so a test can read the real spans back."""
    collector = InMemorySpanExporter()
    _installed_provider().add_span_processor(SimpleSpanProcessor(collector))
    return collector


def _carrier_attributes(carrier: Any) -> dict[str, Any]:
    """A span's, event's, or link's attributes as a plain dict.

    The SDK types every one of these as a ``Mapping | None``, so reading
    attributes off them directly makes each privacy assertion a ``None`` check
    rather than a check on the value.
    """
    return dict(carrier.attributes or {})


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


class _SerialisingExporter(SpanExporter):
    """Serialise each span *during* ``export``, and keep the text.

    ``InMemorySpanExporter`` retains the live ``ReadableSpan`` and serialises it
    later, so by the time a test reads it, an in-place mutation by a processor
    that ran after the exporter is invisible. Recording the text at export time
    is the only way to observe which processor saw the span first.
    """

    def __init__(self) -> None:
        self.snapshots: list[str] = []

    def export(self, spans: Any) -> Any:
        self.snapshots.extend(json.dumps(span.to_json()) for span in spans)

    def shutdown(self) -> None:
        return None


class _DiscardingProcessorChain(SynchronousMultiSpanProcessor):
    """A chain that accepts a write to ``_span_processors`` and keeps the old value.

    Stands in for a future SDK whose processor field stays writable but is no
    longer the tuple the provider iterates, which is precisely the case the
    read-back assertion exists to turn from a silent pass into a loud failure.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_span_processors" and "_span_processors" in self.__dict__:
            return
        super().__setattr__(name, value)


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
    configure_telemetry(TraceSettings(retention_days=90, otel_endpoint=None, log_level="INFO"), environment="development")
    with span_for_session(1, uuid.uuid4()) as span:
        span.set_attribute("session_id", 1)
    assert span.is_recording() or not span.is_recording()  # exporter smoke test, no exception


# ---------------------------------------------------------------------------
# Exporter choice
# ---------------------------------------------------------------------------


def test_no_endpoint_selects_the_console_exporter():
    configure_telemetry(_settings(), environment="development")

    assert isinstance(_installed_exporter(), ConsoleSpanExporter)


def test_otlp_endpoint_falls_back_to_console_when_the_exporter_is_absent(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """ADR-009 makes the exporter a deployment choice, never a hard dependency.

    The OTLP exporter ships in its own distribution, so a configured endpoint
    must degrade to the console with a warning rather than take the process down
    or export nothing at all. The import is forced to fail rather than relying
    on the extra being absent, so this covers the degradation path in an
    environment installed with ``.[otel]`` too; the present-extra case is
    covered by the test below.
    """
    module_name = "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    # A ``None`` entry in sys.modules makes the import machinery raise
    # ImportError for that name, which is exactly what an uninstalled
    # distribution looks like to ``_build_exporter``.
    monkeypatch.setitem(sys.modules, module_name, None)

    with caplog.at_level("WARNING", logger=telemetry.__name__):
        configure_telemetry(
            _settings(otel_endpoint="https://user:secret@collector.internal:4318"),
            environment="development",
        )

    assert isinstance(_installed_exporter(), ConsoleSpanExporter)
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in caplog.text
    assert "opentelemetry-exporter-otlp-proto-http" in caplog.text
    assert "user:secret" not in caplog.text
    assert "secret" not in caplog.text


def test_otlp_endpoint_constructs_exporter_when_optional_extra_is_present() -> None:
    exporter_module = pytest.importorskip(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter"
    )

    exporter = telemetry._build_exporter(
        _settings(otel_endpoint="https://collector.internal:4318"),
        environment="development",
    )

    assert isinstance(exporter, exporter_module.OTLPSpanExporter)


def test_resource_identifies_the_service_and_environment():
    configure_telemetry(_settings(log_level="DEBUG"), environment="production")

    attributes = _installed_provider().resource.attributes
    assert attributes["service.name"] == "horus-backend"
    assert attributes["deployment.environment"] == "production"


def test_testing_environment_discards_spans_without_console_export() -> None:
    configure_telemetry(_settings(), environment="testing")

    assert isinstance(_installed_exporter(), telemetry._NoopSpanExporter)


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
        configure_telemetry(settings, environment="development")
        provider = _installed_provider()
        exporter = _installed_exporter()
        configure_telemetry(settings, environment="development")
        configure_telemetry(_settings(log_level="ERROR"), environment="development")

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


def test_existing_provider_receives_the_scrubber_before_its_exporter() -> None:
    """A refused global override must not leave the active pipeline unfiltered."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="testing", app=application)

    with TestClient(application) as client:
        assert client.get("/search?q=student%20radios%20said%20clearance").status_code == 200

    server_span = next(
        span for span in exporter.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    serialised_attributes = json.dumps(json.loads(server_span.to_json())["attributes"])
    assert telemetry._configured is True
    assert trace.get_tracer_provider() is provider
    assert "q=" not in serialised_attributes
    assert "student radios" not in serialised_attributes
    assert "clearance" not in serialised_attributes


def test_scrubber_installation_order_is_observable_at_export_time() -> None:
    """Pin the property that makes prepending load-bearing, through the real installer.

    ``InMemorySpanExporter`` retains the live ``ReadableSpan`` and serialises it
    later, so an in-place mutation by a processor that ran *after* it is
    invisible and prepending could silently regress to appending without any
    test noticing. An exporter that serialises during ``export`` is what makes
    the order visible; the test below proves it can see the difference.
    """
    exporter = _SerialisingExporter()
    provider = TracerProvider()
    telemetry._install_scrubber_before_exporters(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with provider.get_tracer("test.ordering").start_as_current_span("probe") as span:
        span.set_attribute("http.url", "https://example.test/search?q=ORDERLEAK")
    provider.force_flush()

    assert exporter.snapshots, "the exporter was never reached"
    assert "ORDERLEAK" not in exporter.snapshots[0]


def test_an_exporter_before_the_scrubber_serialises_the_unscrubbed_span() -> None:
    """The witness for the test above: order really is visible at export time.

    Same exporter, same span, the scrubber appended instead of prepended, so the
    text is there to be seen. Without this, an exporter that never captured
    anything would make the ordering assertion pass for the wrong reason.
    """
    exporter = _SerialisingExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    provider.add_span_processor(telemetry._QueryStringScrubber())

    with provider.get_tracer("test.ordering").start_as_current_span("probe") as span:
        span.set_attribute("http.url", "https://example.test/search?q=ORDERLEAK")
    provider.force_flush()

    assert exporter.snapshots, "the exporter was never reached"
    assert "ORDERLEAK" in exporter.snapshots[0]


def test_pre_installed_provider_with_its_own_exporter_is_left_alone_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A provider installed by someone else keeps its own pipeline, loudly.

    Attaching the configured exporter as well would export every span twice; the
    deployment choice is therefore not applied, and that is reported rather than
    left to be discovered from a missing trace.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    with caplog.at_level("WARNING", logger=telemetry.__name__):
        configure_telemetry(_settings(), environment="testing")

    processors = provider._active_span_processor._span_processors
    assert telemetry._configured is True
    assert len(processors) == 2
    assert isinstance(processors[0], telemetry._QueryStringScrubber)
    assert [p for p in processors if isinstance(p, SimpleSpanProcessor)] == [
        processors[1]
    ]
    assert "span exporter" in caplog.text
    assert "not attached" in caplog.text


def test_pre_installed_provider_without_an_exporter_receives_the_configured_one() -> None:
    """With nowhere else to go, the deployment's exporter choice still applies."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    configure_telemetry(_settings(), environment="testing")

    processors = provider._active_span_processor._span_processors
    assert isinstance(processors[0], telemetry._QueryStringScrubber)
    exporters = [p for p in processors if hasattr(p, "span_exporter")]
    assert len(exporters) == 1
    assert isinstance(exporters[0].span_exporter, telemetry._NoopSpanExporter)


def test_concurrent_provider_installation_still_receives_the_scrubber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider that wins the once-only global slot must be the protected one.

    ``set_tracer_provider`` is once-only, so a provider installed between the
    read and the write leaves our own provider inactive. The read-back below is
    what notices, and the winner then gets the scrubber prepended.
    """
    winner = TracerProvider()

    def lose_the_race(provider: TracerProvider) -> None:
        """Simulate a concurrent installer taking the slot first."""
        trace._TRACER_PROVIDER = winner
        trace._TRACER_PROVIDER_SET_ONCE._done = True

    monkeypatch.setattr(trace, "set_tracer_provider", lose_the_race)
    configure_telemetry(_settings(), environment="testing")

    processors = winner._active_span_processor._span_processors
    assert telemetry._configured is True
    assert isinstance(processors[0], telemetry._QueryStringScrubber)
    assert [p for p in processors if isinstance(p, telemetry._QueryStringScrubber)] == [
        processors[0]
    ], "the scrubber must be installed exactly once, ahead of every exporter"


def test_scrubber_installation_that_is_discarded_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A write the provider does not honour must not be reported as success."""
    provider = TracerProvider()
    chain = _DiscardingProcessorChain()
    provider._active_span_processor = chain
    trace.set_tracer_provider(provider)

    try:
        with caplog.at_level("WARNING", logger=telemetry.__name__):
            configure_telemetry(_settings(), environment="testing")
    finally:
        # Leave a real chain behind so the isolation fixture can shut the
        # provider down without tripping over the double.
        provider._active_span_processor = SynchronousMultiSpanProcessor()

    assert telemetry._configured is False
    assert "privacy scrubber was not confirmed active" in caplog.text


def test_non_prependable_processor_chain_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unrecognised chain shape is a configuration failure, not a pass."""
    provider = TracerProvider()
    provider._active_span_processor = cast(SynchronousMultiSpanProcessor, object())
    trace.set_tracer_provider(provider)

    try:
        with caplog.at_level("WARNING", logger=telemetry.__name__):
            configure_telemetry(_settings(), environment="testing")
    finally:
        provider._active_span_processor = SynchronousMultiSpanProcessor()

    assert telemetry._configured is False
    assert "privacy scrubber was not confirmed active" in caplog.text


def test_fastapi_app_is_instrumented_once():
    application = FastAPI()

    @application.get("/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="development", app=application)
    configure_telemetry(_settings(), environment="development", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get("/probe").status_code == 200

    assert application._is_instrumented_by_opentelemetry is True
    assert [span.name for span in collector.get_finished_spans()].count("GET /probe") == 1


def test_each_app_is_instrumented_after_provider_configuration() -> None:
    first_app = FastAPI()
    second_app = FastAPI()

    @first_app.get("/first")
    async def first() -> dict[str, bool]:
        return {"ok": True}

    @second_app.get("/second")
    async def second() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="development", app=first_app)
    configure_telemetry(_settings(), environment="development", app=second_app)
    collector = _collect_spans()

    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        assert first_client.get("/first").status_code == 200
        assert second_client.get("/second").status_code == 200

    span_names = [span.name for span in collector.get_finished_spans()]
    assert span_names.count("GET /first") == 1
    assert span_names.count("GET /second") == 1


def test_shipped_app_produces_a_server_span_when_instrumented_at_import() -> None:
    """The shipped composition root must instrument before TestClient starts it."""
    script = """
import json
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from app.main import app

provider = trace.get_tracer_provider()
if not isinstance(provider, TracerProvider):
    print("[]")
    raise SystemExit(0)
collector = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(collector))
with TestClient(app) as client:
    assert client.get("/openapi.json").status_code == 200
print(json.dumps([span.name for span in collector.get_finished_spans()]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.getcwd(),
        env={**os.environ, "ENVIRONMENT": "testing"},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "GET /openapi.json" in json.loads(result.stdout)


def test_server_span_drops_query_string_before_export() -> None:
    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="development", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get("/search?q=student%20radios%20said%20clearance%20denied").status_code == 200

    server_span = next(span for span in collector.get_finished_spans() if span.name == "GET /search")
    serialised = json.dumps(server_span.to_json())
    assert "q=" not in _carrier_attributes(server_span).get("http.url", "")
    assert "q=" not in _carrier_attributes(server_span).get("url.full", "")
    assert "student radios" not in serialised
    assert "clearance" not in serialised


def test_server_span_drops_query_string_when_the_url_cannot_be_parsed() -> None:
    """A malformed, caller-controlled ``Host`` must not smuggle a query out.

    ``Host`` reaches the instrumented URL verbatim, and a caller can make the
    resulting netloc unparsable. Boundary-based scrubbing does not depend on
    parsing, so malformed and well-formed URLs follow the same fail-closed path.
    """
    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="development", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        # "[" without a closing "]" is an invalid IPv6 literal, so urlsplit raises.
        response = client.get("/search?q=clearance-denied", headers={"Host": "[bad"})
        assert response.status_code == 200

    server_span = next(span for span in collector.get_finished_spans() if span.name == "GET /search")
    serialised = json.dumps(server_span.to_json())
    # The scheme, netloc, and path are kept -- they are not sensitive -- and
    # everything from the "?" on is gone.
    assert _carrier_attributes(server_span)["http.url"] == "http://[bad/search"
    assert "q=" not in _carrier_attributes(server_span).get("url.full", "")
    assert "clearance-denied" not in serialised
    assert "clearance" not in serialised


@pytest.mark.parametrize(
    ("host", "private_text", "expected"),
    [
        ("evil.test?q=HOSTLEAK", "HOSTLEAK", "evil.test"),
        ("evil.test#HOSTFRAG", "HOSTFRAG", "evil.test"),
        ("evil.test%3Fq=HOSTENC", "HOSTENC", "evil.test"),
    ],
)
def test_server_span_drops_query_and_fragment_text_from_the_host_header(
    host: str, private_text: str, expected: str
) -> None:
    """The ASGI instrumentation copies ``Host`` verbatim into ``http.server_name``.

    An ordinary, well-formed request header is enough to carry free text out, so
    the authority carrier needs the same treatment as ``http.url`` itself.
    """
    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="testing", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get("/search?q=LEAKME", headers={"Host": host}).status_code == 200

    server_span = next(
        span for span in collector.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    serialised = json.dumps(server_span.to_json())
    assert _carrier_attributes(server_span)["http.server_name"] == expected
    assert _carrier_attributes(server_span)["http.url"] == f"http://{expected}"
    assert private_text not in serialised
    assert "q=" not in serialised
    assert "LEAKME" not in serialised


def test_server_span_drops_query_text_from_the_user_agent_header() -> None:
    """``User-Agent`` is caller-controlled text copied verbatim onto the span."""
    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="testing", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        response = client.get(
            "/search?q=LEAKME", headers={"User-Agent": "curl/8.0?q=UALEAK"}
        )
        assert response.status_code == 200

    server_span = next(
        span for span in collector.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    serialised = json.dumps(server_span.to_json())
    assert _carrier_attributes(server_span)["http.user_agent"] == "curl/8.0"
    assert "UALEAK" not in serialised
    assert "q=" not in serialised
    assert "LEAKME" not in serialised


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("http.server_name", "evil.test"),
        ("http.host", "evil.test"),
        ("server.address", "evil.test"),
        ("client.address", "evil.test"),
        ("http.user_agent", "curl/8.0"),
        ("user_agent.original", "curl/8.0"),
    ],
)
def test_request_header_attributes_are_scrubbed_by_pattern(
    attribute: str, expected: str
) -> None:
    """The authority and user-agent carriers, by name pattern rather than by list.

    ``server.address``/``client.address`` carry no caller text in this
    deployment, but a proxy that writes the forwarded authority or
    ``X-Forwarded-For`` into the ASGI scope turns both into carriers, so the
    name policy covers them ahead of that deployment existing.
    """
    value = "curl/8.0?q=HEADERLEAK" if "agent" in attribute else "evil.test?q=HEADERLEAK"

    attributes, serialised = _url_attribute_json(value, attribute=attribute)

    assert attributes[attribute] == expected
    assert "HEADERLEAK" not in serialised
    assert "q=" not in serialised


def test_route_template_and_caller_bearing_attributes_survive_scrubbing() -> None:
    """Widening the name policy must not start deleting ordinary telemetry.

    ``http.route`` is the matched route template, never caller text, and is
    asserted to survive a request that carries free text in three other
    attributes.
    """
    application = FastAPI()

    @application.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    configure_telemetry(_settings(), environment="testing", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get("/search?q=LEAKME", headers={"Host": "evil.test?q=HOSTLEAK"}).status_code == 200

    server_span = next(
        span for span in collector.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    attributes = _carrier_attributes(server_span)
    assert attributes["http.route"] == "/search"
    assert attributes["http.method"] == "GET"
    assert attributes["http.status_code"] == 200
    assert attributes["http.scheme"] == "http"
    # The decision itself, pinned: the matched route template is a code-level
    # constant, so its name must not be classified as a carrier at all.
    route_tokens = telemetry._QueryStringScrubber._attribute_tokens("http.route")
    assert not route_tokens.intersection(telemetry._QueryStringScrubber._URL_BEARING_TERMS)
    assert not route_tokens.intersection(telemetry._QueryStringScrubber._CALLER_TEXT_TERMS)


@pytest.mark.parametrize(
    ("path", "expected_target", "private_text"),
    [
        ("/missing%3Fq=LEAKME", "/missing", "LEAKME"),
        ("/missing%23private-fragment", "/missing", "private-fragment"),
    ],
)
def test_encoded_request_target_drops_query_and_fragment_text(
    path: str, expected_target: str, private_text: str
) -> None:
    """Decoded ASGI targets must be filtered before any exporter sees them."""
    application = FastAPI()
    configure_telemetry(_settings(), environment="testing", app=application)
    collector = _collect_spans()

    with TestClient(application) as client:
        assert client.get(path).status_code == 404

    server_span = next(
        span for span in collector.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    attributes = json.loads(server_span.to_json())["attributes"]
    assert attributes["http.target"] == expected_target
    assert private_text not in json.dumps(attributes)
    assert "?" not in attributes["http.target"]
    assert "#" not in attributes["http.target"]


def test_unparsable_url_attributes_lose_their_query_and_fragment() -> None:
    """Malformed full URLs take the same boundary-based path as valid ones.

    ``url.full`` is client-side and ``http.url`` server-side, so both standard
    names are asserted directly. The fragment-without-a-query case is separate
    on purpose: truncating at the "?" alone would leave a trailing fragment
    welded to the path, so both markers have to be their own input.
    """
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()
    cases = {
        "http://[bad/search?q=clearance-denied#tail": "http://[bad/search",
        "http://[bad/search#tail": "http://[bad/search",
    }

    for unparsable in cases:
        with trace.get_tracer("test.scrubber").start_as_current_span("probe") as span:
            span.set_attribute("http.url", unparsable)
            span.set_attribute("url.full", unparsable)

    exported = collector.get_finished_spans()
    assert len(exported) == len(cases)
    for exported_span, expected in zip(exported, cases.values()):
        serialised = json.dumps(exported_span.to_json())
        assert _carrier_attributes(exported_span)["http.url"] == expected
        assert _carrier_attributes(exported_span)["url.full"] == expected
        assert "clearance-denied" not in serialised
        assert "q=" not in serialised
        assert "#tail" not in serialised


def _url_attribute_json(
    value: Any, *, attribute: str = "http.url"
) -> tuple[dict[str, Any], str]:
    """Export one real SDK span carrying a URL-like attribute and return its JSON."""
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()

    with trace.get_tracer("test.scrubber").start_as_current_span("probe") as span:
        span.set_attribute(attribute, value)

    serialised = json.loads(collector.get_finished_spans()[0].to_json())
    assert isinstance(serialised, dict)
    attributes = serialised.get("attributes", {})
    assert isinstance(attributes, dict)
    return dict(attributes), json.dumps(serialised)


def test_url_attribute_list_drops_query_text() -> None:
    attributes, serialised = _url_attribute_json(
        ["https://example.test/search?q=clearance-denied"]
    )

    assert attributes["http.url"] == ["https://example.test/search"]
    assert "q=" not in serialised
    assert "clearance-denied" not in serialised


def test_url_attribute_list_drops_fragment_text() -> None:
    attributes, serialised = _url_attribute_json(
        ["https://example.test/search#private-fragment"]
    )

    assert attributes["http.url"] == ["https://example.test/search"]
    assert "#private-fragment" not in serialised
    assert "private-fragment" not in serialised


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            [
                "https://example.test/search?q=clearance-denied",
                "https://example.test/other#private-fragment",
            ],
            ["https://example.test/search", "https://example.test/other"],
        ),
        ([], []),
    ],
)
def test_url_attribute_mixed_and_empty_lists_are_safe(
    value: list[str], expected: list[str]
) -> None:
    attributes, serialised = _url_attribute_json(value)

    assert attributes["http.url"] == expected
    assert "q=" not in serialised
    assert "#private-fragment" not in serialised
    assert "clearance-denied" not in serialised


def test_url_attribute_drops_non_string_non_sequence_value() -> None:
    attributes, serialised = _url_attribute_json(42)

    assert "http.url" not in attributes
    assert "q=" not in serialised
    assert "#private-fragment" not in serialised


def test_future_url_attribute_names_are_scrubbed_by_pattern() -> None:
    attributes, serialised = _url_attribute_json(
        "https://example.test/search?q=clearance-denied", attribute="rpc.request_uri"
    )

    assert attributes["rpc.request_uri"] == "https://example.test/search"
    assert "q=" not in serialised
    assert "clearance-denied" not in serialised


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("url.query", "q=clearance-denied"),
        ("url.fragment", "private-fragment"),
    ],
)
def test_query_and_fragment_named_attributes_are_removed(
    attribute: str, value: str
) -> None:
    """A query/fragment attribute is entirely caller text, not a URL prefix."""
    attributes, serialised = _url_attribute_json(value, attribute=attribute)

    assert attribute not in attributes
    assert value not in serialised


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([], []),
        ([""], [""]),
        (["?"], [""]),
        (
            ["https://example.test/search?q=" + "clearance-denied" * 1_000],
            ["https://example.test/search"],
        ),
        (
            ("https://example.test/search#private-fragment",),
            ["https://example.test/search"],
        ),
        (
            ["https://example.test/search?q=encoded%3Fquestion"],
            ["https://example.test/search"],
        ),
    ],
)
def test_previously_verified_string_shapes_remain_safe(
    value: Any, expected: list[str]
) -> None:
    attributes, serialised = _url_attribute_json(value)

    assert attributes["http.url"] == expected
    assert "clearance-denied" not in serialised
    assert "private-fragment" not in serialised
    assert "encoded%3Fquestion" not in serialised


@pytest.mark.parametrize(
    "value",
    [
        [["https://example.test/search?q=clearance-denied"]],
        {"url": "https://example.test/search?q=clearance-denied"},
        42,
        None,
    ],
)
def test_previously_verified_unsupported_shapes_are_removed(value: Any) -> None:
    attributes, serialised = _url_attribute_json(value)

    assert "http.url" not in attributes
    assert "clearance-denied" not in serialised


# ---------------------------------------------------------------------------
# Privacy: the carriers outside ``span.attributes``
# ---------------------------------------------------------------------------


def test_exception_text_carrying_caller_text_is_removed_from_span_events() -> None:
    """Exception text is caller-influenced by construction.

    A handler that interpolates the query into its error message puts that text
    on the span twice over: once in ``exception.message`` and again on the final
    ``ValueError: ...`` line of ``exception.stacktrace``. The message carries no
    query delimiter to truncate at, so the only safe policy is to remove the
    runtime-formatted text and keep the exception *type*.
    """
    application = FastAPI()

    @application.get("/parse")
    async def parse(q: str = "") -> dict[str, bool]:
        raise ValueError(f"could not parse search text {q!r}")

    configure_telemetry(_settings(), environment="testing", app=application)
    collector = _collect_spans()

    with TestClient(application, raise_server_exceptions=False) as client:
        assert client.get("/parse?q=EXCLEAK").status_code == 500

    server_span = next(
        span for span in collector.get_finished_spans() if span.kind == trace.SpanKind.SERVER
    )
    exception_events = [event for event in server_span.events if event.name == "exception"]
    assert len(exception_events) == 1
    attributes = _carrier_attributes(exception_events[0])
    serialised = json.dumps(server_span.to_json())
    assert attributes["exception.type"] == "ValueError"
    assert "exception.message" not in attributes
    assert "exception.stacktrace" not in attributes
    assert "EXCLEAK" not in serialised
    assert "could not parse search text" not in serialised


def test_url_bearing_event_attribute_is_scrubbed() -> None:
    """Event attributes obey exactly the name policy span attributes do."""
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()

    with trace.get_tracer("test.scrubber").start_as_current_span("probe") as span:
        span.add_event("attempt", {"http.target": "/search?q=EVENTLEAK"})

    exported = collector.get_finished_spans()[0]
    event_attributes = _carrier_attributes(exported.events[0])
    assert event_attributes["http.target"] == "/search"
    assert "EVENTLEAK" not in json.dumps(exported.to_json())


def _linked_span_context() -> SpanContext:
    """A valid context, so ``add_link`` keeps the link it is given."""
    return SpanContext(
        trace_id=0x000000000000000000000000DEADBEEF,
        span_id=0x0000000000000BEEF,
        is_remote=False,
        trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
    )


def test_event_names_and_link_attributes_are_scrubbed() -> None:
    """An event name is caller-assembled text, and a link carries attributes."""
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()

    with trace.get_tracer("test.scrubber").start_as_current_span("probe") as span:
        span.add_event("failed to parse /search?q=EVENTLEAK")
        span.add_link(_linked_span_context(), {"url.full": "https://example.test/search?q=LINKLEAK"})

    exported = collector.get_finished_spans()[0]
    link_attributes = _carrier_attributes(exported.links[0])
    serialised = json.dumps(exported.to_json())
    assert exported.events[0].name == "failed to parse /search"
    assert link_attributes["url.full"] == "https://example.test/search"
    assert "EVENTLEAK" not in serialised
    assert "LINKLEAK" not in serialised
    assert "q=" not in serialised


def test_span_name_and_status_description_lose_query_text() -> None:
    """A caller-built span name is truncated at the delimiter, as any URL is."""
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()

    with trace.get_tracer("test.scrubber").start_as_current_span(
        "GET /search?q=NAMELEAK"
    ) as span:
        span.set_status(trace.StatusCode.ERROR, "failed on /search?q=DESCREAK")

    exported = collector.get_finished_spans()[0]
    serialised = json.dumps(exported.to_json())
    assert exported.name == "GET /search"
    assert exported.status.status_code is trace.StatusCode.ERROR
    assert "q=" not in exported.name
    assert "NAMELEAK" not in serialised
    assert "DESCREAK" not in serialised


def test_span_name_without_a_delimiter_is_left_alone() -> None:
    """Only the delimiter is the trigger; ordinary span names are untouched."""
    configure_telemetry(_settings(), environment="development")
    collector = _collect_spans()

    with trace.get_tracer("test.scrubber").start_as_current_span("session.exchange") as span:
        span.set_status(trace.StatusCode.OK)

    exported = collector.get_finished_spans()[0]
    assert exported.name == "session.exchange"
    assert exported.status.description is None


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
    configure_telemetry(_settings(), environment="development")

    with pytest.raises(RuntimeError, match="product failure"), span_for_session(7, ORG_ID):
        raise RuntimeError("product failure")


def test_configuration_failure_leaves_the_backend_running(monkeypatch: pytest.MonkeyPatch):
    def explode(settings: TraceSettings, *, environment: str) -> SpanExporter:
        raise RuntimeError("no telemetry for you")

    monkeypatch.setattr(telemetry, "_build_exporter", explode)
    configure_telemetry(_settings(), environment="development")  # must not raise
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
    configure_telemetry(_settings(), environment="development")
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
    configure_telemetry(_settings(), environment="development")
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
    configure_telemetry(_settings(), environment="development")

    with span_for_session(42, ORG_ID) as span:
        context = span.get_span_context()

    assert isinstance(context, SpanContext)
    assert context.is_valid
    assert context.trace_flags.sampled
