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
import re
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import (
    ReadableSpan,
    SpanProcessor,
    SynchronousMultiSpanProcessor,
    TracerProvider,
)
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


_QUERY_OR_FRAGMENT_BOUNDARY = re.compile(r"\?|#|%3f|%23", re.IGNORECASE)


def _without_query_or_fragment(value: str) -> str:
    """Drop literal or percent-encoded query and fragment delimiters.

    ASGI instrumentation decodes request targets before recording them, while
    full URLs can retain the original encoding. Checking both forms closes that
    mismatch without parsing the URL. Repeated percent-decoding handles double
    encoded input; the original value is retained if decoding never reveals a
    delimiter.
    """
    while True:
        boundary = _QUERY_OR_FRAGMENT_BOUNDARY.search(value)
        if boundary is not None:
            return value[: boundary.start()]
        decoded = unquote(value)
        if decoded == value:
            return value
        value = decoded


class _QueryStringScrubber(SpanProcessor):
    """Remove caller text from every URL-like attribute before export.

    Attribute **names** are matched by token, rather than enumerated. Any name
    containing a URL-bearing term (``url``, ``uri``, ``target``, ``path``,
    ``query``, ``fragment``, ``referer``/``referrer``, ``location``, or
    ``endpoint``) is covered, including names added by future instrumentation.
    A name containing ``query`` or ``fragment`` denotes wholly caller-controlled
    data, so that attribute is deleted. Other URL-like values retain only the
    prefix before a literal or percent-encoded query/fragment delimiter.

    This is deny-by-default for matched values and shapes. Unknown non-URL
    attributes are left alone, but every matched string and string sequence is
    scrubbed. A matched value in any other shape, or a sequence containing a
    non-string, is deleted because this control cannot confidently inspect it.
    Deleting malformed telemetry is safer than exporting a possible bypass.
    """

    _URL_BEARING_TERMS = frozenset(
        {
            "endpoint",
            "fragment",
            "location",
            "path",
            "query",
            "referer",
            "referrer",
            "target",
            "uri",
            "url",
        }
    )
    _QUERY_OR_FRAGMENT_TERMS = frozenset({"fragment", "query"})

    @classmethod
    def _attribute_tokens(cls, attribute: str) -> frozenset[str]:
        """Split dotted, delimited, snake-case, and camel-case names into terms."""
        separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", attribute)
        separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
        return frozenset(re.findall(r"[a-z0-9]+", separated.lower()))

    @classmethod
    def _scrub_url_value(cls, value: Any) -> Any:
        """Scrub a scalar or homogeneous string sequence, or return ``None`` to drop it."""
        if isinstance(value, str):
            return _without_query_or_fragment(value)
        if not isinstance(value, (list, tuple)):
            return None
        if not all(isinstance(element, str) for element in value):
            return None
        return [_without_query_or_fragment(element) for element in value]

    def on_end(self, span: ReadableSpan) -> None:
        attributes = span.attributes
        if attributes is None:
            return
        scrubbed_attributes = dict(attributes)
        changed = False
        for attribute, value in attributes.items():
            tokens = self._attribute_tokens(attribute)
            if not tokens.intersection(self._URL_BEARING_TERMS):
                continue
            if tokens.intersection(self._QUERY_OR_FRAGMENT_TERMS):
                del scrubbed_attributes[attribute]
                changed = True
                continue
            scrubbed = self._scrub_url_value(value)
            if scrubbed is None:
                del scrubbed_attributes[attribute]
                changed = True
            elif scrubbed != value:
                scrubbed_attributes[attribute] = scrubbed
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


def _install_scrubber_before_exporters(provider: TracerProvider) -> None:
    """Put the privacy processor first in an SDK provider's processor chain.

    OpenTelemetry invokes processors in registration order and offers no public
    prepend operation. Appending to a provider installed by another component
    would therefore be too late: its exporter would receive the unfiltered span
    first. The SDK's synchronous processor stores an immutable tuple under a
    lock, so atomically replacing that tuple with the scrubber prepended is the
    only ordering-safe installation point. Failure to recognize or mutate the
    active processor is explicit and leaves telemetry unconfigured.
    """
    active_processor = provider._active_span_processor
    if not isinstance(active_processor, SynchronousMultiSpanProcessor):
        raise RuntimeError(
            "the active tracer provider does not expose a prependable SDK processor chain"
        )
    with active_processor._lock:
        processors = active_processor._span_processors
        if not any(isinstance(processor, _QueryStringScrubber) for processor in processors):
            active_processor._span_processors = (_QueryStringScrubber(), *processors)


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
            active_provider = trace.get_tracer_provider()
            if isinstance(active_provider, TracerProvider):
                # The global API is once-only. If another component installed an
                # SDK provider first, protect that provider rather than creating
                # an inactive provider around the scrubber and marking success.
                _install_scrubber_before_exporters(active_provider)
            else:
                provider = TracerProvider(
                    resource=Resource.create(
                        {
                            "service.name": SERVICE_NAME,
                            "deployment.environment": environment,
                        }
                    )
                )
                _install_scrubber_before_exporters(provider)
                provider.add_span_processor(
                    BatchSpanProcessor(_build_exporter(settings, environment=environment))
                )
                trace.set_tracer_provider(provider)
                installed_provider = trace.get_tracer_provider()
                if not isinstance(installed_provider, TracerProvider):
                    raise RuntimeError("the global tracer provider is not an SDK provider")
                if installed_provider is not provider:
                    # A concurrent installer won the once-only global slot. Its
                    # active processor still has to receive the scrubber first.
                    _install_scrubber_before_exporters(installed_provider)
            _asyncpg_instrumentor.instrument()
        except Exception:
            logger.warning(
                "OpenTelemetry configuration failed; the privacy scrubber was not "
                "confirmed active; continuing without telemetry.",
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
