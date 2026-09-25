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
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from typing import Any
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.attributes import BoundedAttributes
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import (
    Event,
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
from opentelemetry.trace import Link, Span, Status

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

# Marks an attribute that must be removed rather than rewritten.
_DELETED = object()


def _without_query_or_fragment(value: str) -> str:
    """Drop literal or percent-encoded query and fragment delimiters.

    ASGI instrumentation decodes request targets before recording them, while
    full URLs can retain the original encoding. Checking both forms closes that
    mismatch without parsing the URL. Repeated percent-decoding handles double
    encoded input; the original value is retained if decoding never reveals a
    delimiter.

    Cutting at a boundary is not the end of the work. A value can hold a doubly
    encoded ``%253F`` that only a further decode pass resolves, sitting *before*
    a literal ``?`` or ``#`` later in the same value: returning the truncated
    prefix would leave that earlier one intact, and the prefix would still carry
    a query once decoded. So a cut is followed by another pass over what is left.
    The loop terminates because each pass either shortens the value (a cut, or a
    decode that resolved at least one escape) or leaves it unchanged and returns.
    """
    while True:
        boundary = _QUERY_OR_FRAGMENT_BOUNDARY.search(value)
        if boundary is not None:
            value = value[: boundary.start()]
            continue
        decoded = unquote(value)
        if decoded == value:
            return value
        value = decoded


def _rebuild_bounded_attributes(attributes: dict[str, Any], original: Any) -> Any:
    """Re-wrap scrubbed attributes in the container the SDK handed us.

    ``BoundedAttributes`` enforces the span's attribute-count and value-length
    limits when it is built, and a replacement built without them would export
    values the SDK had already truncated. A container this control does not
    recognise is passed through as a plain mapping rather than dropped, because
    the values themselves are already scrubbed.
    """
    if isinstance(original, BoundedAttributes):
        return BoundedAttributes(
            maxlen=original.maxlen,
            attributes=attributes,
            immutable=True,
            max_value_len=original.max_value_len,
        )
    return attributes


class _QueryStringScrubber(SpanProcessor):
    """Remove caller text from every span carrier, before export.

    One policy, applied wherever a value appears, in two steps.

    **Names** are matched by token, never enumerated: a name is split across
    dots, delimiters, snake case, and camel case, and any term in
    ``_URL_BEARING_TERMS`` or ``_CALLER_TEXT_TERMS`` classifies it. The terms
    are ``url``, ``uri``, ``target``, ``path``, ``referer``/``referrer``,
    ``location`` and ``endpoint`` for a URL; ``host``, ``server``, ``client`` and
    ``agent`` for the request-header carriers -- the ASGI instrumentation copies
    the ``Host`` and ``User-Agent`` headers onto the span verbatim, and a proxy
    that writes a forwarded authority into the ASGI scope puts the same text in
    ``http.host``, ``server.address`` and ``client.address``; and ``query``,
    ``fragment``, ``message``, ``stacktrace`` and ``traceback`` for text that is
    wholly the caller's.

    **Values** follow from the classification. An attribute whose name is wholly
    caller text is deleted: it is free text with no URL prefix to keep, and the
    usual case -- a runtime-formatted exception message -- has no delimiter to
    truncate at. That is a blunt instrument while product code still interpolates
    request text into its errors, which is why
    :func:`configure_telemetry` says so in the deploy log; an exception message
    built from constants and the exception type could be kept instead. Any other
    matched value keeps only the prefix before a literal or percent-encoded
    query/fragment delimiter. A numeric matched value is left alone, because a
    number cannot contain a delimiter: that is what keeps ``net.host.port``,
    ``server.port`` and ``client.port`` in the span, and the three host attributes
    that really do carry caller text -- ``http.host``, ``http.server_name`` and
    ``http.user_agent`` -- are strings, so they stay fully covered. A matched
    value in any other shape, or a sequence containing a non-string, is deleted
    because this control cannot confidently inspect it. Deleting malformed
    telemetry is safer than exporting a possible bypass. A matched value that is
    already free of a delimiter is left exactly as it is, so ordinary telemetry
    is not disturbed.

    **Carriers** are every field ``ReadableSpan.to_json`` serialises: span
    attributes, span events (name and attributes), span links (attributes), the
    span name, and the status description. Exception text reaches a span twice --
    once as ``exception.message`` and again on the final line of
    ``exception.stacktrace`` -- so leaving either alone would leave the leak.
    ``http.route`` is the matched route template, never caller text, and matches
    no term, so it is left alone. Two things an exported span also carries sit
    outside this control: the resource attributes and the instrumentation scope
    name, which it is not given and does not rewrite.

    Every step here is total: a missing attribute mapping, an absent event
    collection, a non-string description, and an unset status are all handled as
    ordinary cases. Through the SDK's own types that leaves nothing to raise on,
    so a request does not see a failure from here. It is a property of those
    types rather than a guarantee of this control: it runs inside
    ``SynchronousMultiSpanProcessor.on_end``, which has no exception guard of its
    own, so a value outside them -- a ``None`` span name, say -- would propagate
    into ``Span.end()``.
    """

    _URL_BEARING_TERMS = frozenset(
        {
            "agent",
            "client",
            "endpoint",
            "host",
            "location",
            "path",
            "referer",
            "referrer",
            "server",
            "target",
            "uri",
            "url",
        }
    )
    _CALLER_TEXT_TERMS = frozenset({"fragment", "message", "query", "stacktrace", "traceback"})

    @classmethod
    def _attribute_tokens(cls, attribute: str) -> frozenset[str]:
        """Split dotted, delimited, snake-case, and camel-case names into terms."""
        separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", attribute)
        separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
        return frozenset(re.findall(r"[a-z0-9]+", separated.lower()))

    @classmethod
    def _scrub_url_value(cls, value: Any) -> Any:
        """Scrub a scalar or homogeneous string sequence, or return ``None`` to drop it."""
        # A number cannot spell a delimiter: the type is the proof, so the
        # port attributes (``net.host.port`` and friends) are matched by name
        # and still exported. A caller cannot turn a host attribute into a
        # number, and a number is not free text.
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            return _without_query_or_fragment(value)
        if not isinstance(value, (list, tuple)):
            return None
        if not all(isinstance(element, str) for element in value):
            return None
        return [_without_query_or_fragment(element) for element in value]

    @classmethod
    def _scrub_attributes(cls, attributes: Mapping[str, Any]) -> dict[str, Any] | None:
        """Return rewritten attributes, or ``None`` when the name policy matched nothing."""
        scrubbed: dict[str, Any] | None = None
        for attribute, value in attributes.items():
            tokens = cls._attribute_tokens(attribute)
            if tokens.intersection(cls._CALLER_TEXT_TERMS):
                replacement: Any = _DELETED
            elif tokens.intersection(cls._URL_BEARING_TERMS):
                replacement = cls._scrub_url_value(value)
                if replacement is None:
                    replacement = _DELETED
            else:
                continue
            if scrubbed is None:
                scrubbed = dict(attributes)
            if replacement is _DELETED:
                del scrubbed[attribute]
            else:
                scrubbed[attribute] = replacement
        return scrubbed

    def on_end(self, span: ReadableSpan) -> None:
        """Rewrite the finished span in place, before the next processor exports it.

        ``ReadableSpan`` exposes immutable mappings, so each carrier's backing
        field is replaced only after the span has ended. The live ``Span`` the
        caller holds is a different object and is never touched.
        """
        self._scrub_span_attributes(span)
        self._scrub_events(span)
        self._scrub_links(span)
        self._scrub_identity(span)

    def _scrub_span_attributes(self, span: ReadableSpan) -> None:
        attributes = span.attributes
        if attributes is None:
            return
        scrubbed = self._scrub_attributes(attributes)
        if scrubbed is not None:
            setattr(span, "_attributes", scrubbed)

    def _scrub_events(self, span: ReadableSpan) -> None:
        events = span.events
        if not events:
            return
        scrubbed: list[Event] | None = None
        for index, event in enumerate(events):
            name = _without_query_or_fragment(event.name)
            attributes = self._scrub_attributes(event.attributes or {})
            if name == event.name and attributes is None:
                continue
            if scrubbed is None:
                scrubbed = list(events)
            scrubbed[index] = Event(
                name=name,
                attributes=(
                    _rebuild_bounded_attributes(attributes, event.attributes)
                    if attributes is not None
                    else event.attributes
                ),
                timestamp=event.timestamp,
            )
        if scrubbed is not None:
            setattr(span, "_events", scrubbed)

    def _scrub_links(self, span: ReadableSpan) -> None:
        links = span.links
        if not links:
            return
        scrubbed: list[Link] | None = None
        for index, link in enumerate(links):
            attributes = self._scrub_attributes(link.attributes or {})
            if attributes is None:
                continue
            if scrubbed is None:
                scrubbed = list(links)
            scrubbed[index] = Link(
                link.context, _rebuild_bounded_attributes(attributes, link.attributes)
            )
        if scrubbed is not None:
            setattr(span, "_links", scrubbed)

    def _scrub_identity(self, span: ReadableSpan) -> None:
        """Truncate the span name and the status description at the delimiter.

        A span name is normally a code-level constant, but a caller that builds
        one from the request turns it into a carrier, and the rule for that is
        the same as for any other value: keep the prefix, drop the query.
        """
        name = _without_query_or_fragment(span.name)
        if name != span.name:
            setattr(span, "_name", name)
        status = span.status
        description = status.description
        if not isinstance(description, str):
            return
        scrubbed_description = _without_query_or_fragment(description)
        if scrubbed_description == description:
            return
        # ``Status`` keeps a description only on an ERROR status, which is the
        # only status that can hold one; an empty result is passed as ``None``
        # so a fully-scrubbed description does not trip that guard.
        setattr(span, "_status", Status(status.status_code, scrubbed_description or None))

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
    only ordering-safe installation point. The result is then read back, because a
    provider whose chain is writable but no longer the one it iterates would
    accept the write and quietly keep exporting unfiltered spans. Failure to
    recognize, mutate, or confirm the active processor is explicit and leaves
    telemetry unconfigured.
    """
    active_processor = provider._active_span_processor
    if not isinstance(active_processor, SynchronousMultiSpanProcessor):
        raise RuntimeError(
            "the active tracer provider does not expose a prependable SDK processor chain"
        )
    with active_processor._lock:
        processors = active_processor._span_processors
        remaining = tuple(
            processor
            for processor in processors
            if not isinstance(processor, _QueryStringScrubber)
        )
        active_processor._span_processors = (_QueryStringScrubber(), *remaining)
        installed = active_processor._span_processors
    if not installed or not isinstance(installed[0], _QueryStringScrubber):
        raise RuntimeError(
            "the active tracer provider discarded the privacy scrubber installation"
        )


def _install_configured_exporter(
    provider: TracerProvider, settings: TraceSettings, *, environment: str
) -> None:
    """Attach the configured exporter unless the provider already exports spans.

    ``set_tracer_provider`` is once-only, so a provider another component
    installed is the one that will actually export. Its own exporter is left
    alone -- adding a second one would export every span twice -- and the fact
    that the deployment's exporter choice (console, OTLP, or the testing no-op)
    is not applied to it is reported rather than left to be discovered from a
    missing trace.
    """
    active_processor = provider._active_span_processor
    if not isinstance(active_processor, SynchronousMultiSpanProcessor):
        raise RuntimeError("the active tracer provider does not expose its processor chain")
    with active_processor._lock:
        already_exports = any(
            getattr(processor, "span_exporter", None) is not None
            for processor in active_processor._span_processors
        )
    if already_exports:
        logger.warning(
            "A tracer provider was installed before this application configured "
            "telemetry and it already has a span exporter; that pipeline is left in "
            "place, so the configured exporter is not attached and spans reach that "
            "exporter instead of the one this deployment selected. The privacy "
            "scrubber is installed ahead of it either way."
        )
        return
    provider.add_span_processor(
        BatchSpanProcessor(_build_exporter(settings, environment=environment))
    )


def _warn_exception_text_is_removed() -> None:
    """Say out loud, at deploy time, that spans carry no exception text.

    The removal is a real observability cost, and an engineer has to learn it
    from the log of the deployment they are looking at -- never from the trace
    that stopped being useful during an incident.
    """
    logger.warning(
        "telemetry privacy policy: exception.message and exception.stacktrace are "
        "removed from every exported span, because either can carry request text "
        "interpolated at runtime. Spans keep exception.type, the span status and "
        "the HTTP status, but no exception message and no stack trace. Exception "
        "messages built from constants and the exception type only could be kept "
        "instead; until product code is written that way, this is the cost."
    )


def configure_telemetry(
    settings: TraceSettings, *, environment: str, app: FastAPI | None = None
) -> None:
    """Install OTel FastAPI + asyncpg instrumentation and a console or OTLP exporter.

    Provider and asyncpg installation are process-wide and guarded for
    idempotency. FastAPI instrumentation is per application, so each new app
    handed to this function is instrumented even when the provider already
    exists. The first successful configuration also reports, once, that exception
    text is being removed from spans; see :func:`_warn_exception_text_is_removed`.
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
                _install_configured_exporter(
                    active_provider, settings, environment=environment
                )
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
                _install_configured_exporter(provider, settings, environment=environment)
                trace.set_tracer_provider(provider)
                installed_provider = trace.get_tracer_provider()
                if not isinstance(installed_provider, TracerProvider):
                    raise RuntimeError("the global tracer provider is not an SDK provider")
                if installed_provider is not provider:
                    # A concurrent installer won the once-only global slot. Its
                    # active processor still has to receive the scrubber first,
                    # and it is the one that will really export, so the configured
                    # exporter is attached to it too.
                    _install_scrubber_before_exporters(installed_provider)
                    _install_configured_exporter(
                        installed_provider, settings, environment=environment
                    )
            _asyncpg_instrumentor.instrument()
        except Exception:
            logger.warning(
                "OpenTelemetry configuration failed; the privacy scrubber was not "
                "confirmed active; continuing without telemetry.",
                exc_info=True,
            )
            return
        _configured = True
        _warn_exception_text_is_removed()
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
