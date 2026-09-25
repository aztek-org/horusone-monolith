"""OpenTelemetry wiring for operational telemetry.

See ADR-009. Two rules shape this module:

* **Telemetry is not a product dependency.** No API key, no licence, no
  outbound call is required, and no failure here may reach a caller. A broken
  exporter, an unreachable collector, or a provider that cannot sample all
  degrade to "no telemetry" rather than break a request or a training session.
* **Spans carry identifiers and timings, never product content.** Prompts,
  student radio transcripts, and retrieved knowledge chunks stay in
  PostgreSQL, where the session access check already governs them. This module
  only ever sets ``session_id`` and ``org_id`` itself; callers adding
  graph/node and provider metadata are responsible for keeping content out.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.trace import Span

from app.config import TraceSettings

logger = logging.getLogger(__name__)

SERVICE_NAME = "horus-backend"
TRACER_NAME = "app.observability.telemetry"
SESSION_SPAN_NAME = "session.exchange"

# Guards repeated configuration. Both ``set_tracer_provider`` and the OTel
# instrumentors are process-wide and refuse to run twice, so an unguarded
# second call would only produce an "already configured" warning on every
# lifespan -- and the test suite opens many TestClients.
_configured = False

# A single instrumentor instance: BaseInstrumentor remembers that it already
# ran, so a retry after a partial failure is declined instead of re-patching.
_asyncpg_instrumentor = AsyncPGInstrumentor()


class _QueryStringScrubber(SpanProcessor):
    """Remove query strings from URL attributes before they reach an exporter.

    FastAPI instrumentation records the request URL on server spans. Query
    parameters are caller-controlled free text, so retaining them would violate
    this module's privacy contract. ``ReadableSpan`` exposes attributes through
    a read-only mapping, so the processor replaces its backing attributes after
    the span has ended and before the next processor exports it.
    """

    _URL_ATTRIBUTES = ("http.url", "url.full")

    def on_end(self, span: ReadableSpan) -> None:
        attributes = span.attributes
        if attributes is None:
            return
        scrubbed_attributes = dict(attributes)
        changed = False
        for attribute in self._URL_ATTRIBUTES:
            value = scrubbed_attributes.get(attribute)
            if not isinstance(value, str):
                continue
            try:
                parsed = urlsplit(value)
            except ValueError:
                continue
            if parsed.query or parsed.fragment:
                scrubbed_attributes[attribute] = urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, "", "")
                )
                changed = True
        if changed:
            # ReadableSpan exposes an immutable mapping, so replace its backing
            # attributes only after the span has ended and before the next
            # processor exports it.
            setattr(span, "_attributes", scrubbed_attributes)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class _NoopSpanExporter(SpanExporter):
    """Discard spans in the testing environment without console or memory capture."""

    def export(self, spans: Any) -> Any:
        return None

    def shutdown(self) -> None:
        return None


def _build_exporter(settings: TraceSettings, *, environment: str) -> SpanExporter:
    """Return the OTLP exporter for a configured endpoint, else the console one.

    The OTLP exporter ships in its own distribution so that a deployment that
    never exports off-box does not pull an HTTP/gRPC stack in. Its absence is
    therefore a configuration state, not an error: warn and export to the
    console rather than leaving the deployment silently untraced.
    """
    if environment == "testing":
        return _NoopSpanExporter()

    endpoint = settings.otel_endpoint
    if not endpoint:
        return ConsoleSpanExporter()

    try:
        # Optional by design: see the module docstring on deployment choices.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
    except ImportError:
        try:
            endpoint_host = urlsplit(endpoint).hostname or "<redacted>"
        except ValueError:
            endpoint_host = "<redacted>"
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT for host %s is set but the OTLP exporter "
            "package is not installed; exporting spans to the console instead. "
            "Install opentelemetry-exporter-otlp-proto-http to send them to a collector.",
            endpoint_host,
        )
        return ConsoleSpanExporter()

    return OTLPSpanExporter(endpoint=endpoint)  # type: ignore[no-any-return]


def configure_telemetry(
    settings: TraceSettings, *, environment: str, app: FastAPI | None = None
) -> None:
    """Install OTel FastAPI + asyncpg instrumentation and a console or OTLP exporter.

    Provider and asyncpg installation are process-wide and guarded for
    idempotency. FastAPI instrumentation is per application, so each new app
    handed to this function is instrumented even when the provider already
    exists.
    """
    global _configured
    if not _configured:
        try:
            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": SERVICE_NAME,
                        "deployment.environment": environment,
                    }
                )
            )
            provider.add_span_processor(_QueryStringScrubber())
            provider.add_span_processor(
                BatchSpanProcessor(_build_exporter(settings, environment=environment))
            )
            trace.set_tracer_provider(provider)
            _asyncpg_instrumentor.instrument()
        except Exception:
            logger.warning(
                "OpenTelemetry configuration failed; continuing without telemetry.",
                exc_info=True,
            )
            return
        _configured = True
    else:
        logger.debug("Telemetry already configured; leaving the installed pipeline alone.")

    if app is not None:
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            logger.warning(
                "OpenTelemetry FastAPI instrumentation failed for the supplied app; "
                "continuing without it.",
                exc_info=True,
            )


def _session_attributes(session_id: int, org_id: uuid.UUID | None) -> dict[str, Any]:
    """Correlation keys for a session span, and nothing else.

    ``org_id`` is omitted rather than set to null when unknown, so a downstream
    query can treat its absence as "no tenant" rather than as a value.
    """
    attributes: dict[str, Any] = {"session_id": session_id}
    if org_id is not None:
        attributes["org_id"] = str(org_id)
    return attributes


@contextmanager
def _session_span(session_id: int, org_id: uuid.UUID | None) -> Iterator[Span]:
    """Open the raw session span. May raise; :func:`span_for_session` absorbs it."""
    tracer = trace.get_tracer(TRACER_NAME)
    with tracer.start_as_current_span(
        SESSION_SPAN_NAME, attributes=_session_attributes(session_id, org_id)
    ) as span:
        yield span


@contextmanager
def span_for_session(session_id: int, org_id: uuid.UUID | None) -> Iterator[Span]:
    """Yield a ``session.exchange`` span tagged with ``session_id`` and ``org_id``.

    Failing to open the span never reaches the caller: a non-recording no-op
    span is yielded instead, whose ``set_attribute`` and friends do nothing.
    Once open, the span behaves normally -- it records the caller's exceptions,
    and the SDK's span processors absorb exporter failures, so an unreachable
    collector cannot break the caller's ``with`` block either. Exceptions from
    the caller's own body are deliberately *not* swallowed.
    """
    stack = ExitStack()
    try:
        span = stack.enter_context(_session_span(session_id, org_id))
    except Exception:
        logger.warning("Could not open a telemetry span; continuing without one.", exc_info=True)
        yield trace.INVALID_SPAN
        return

    with stack:
        yield span
