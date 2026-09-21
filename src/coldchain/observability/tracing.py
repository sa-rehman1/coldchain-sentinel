"""Fail-safe OpenTelemetry helpers with a deliberately small data surface."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_SAFE_ATTRIBUTE_KEYS = frozenset(
    {
        "coldchain.component",
        "coldchain.outcome",
        "coldchain.breach_type",
        "coldchain.severity",
        "coldchain.action",
        "coldchain.governance_decision",
        "coldchain.provider",
        "coldchain.model",
        "coldchain.fallback_reason",
        "messaging.destination.name",
        "messaging.operation.name",
        "http.request.method",
        "http.route",
        "http.response.status_code",
    }
)


def configure_tracing(
    service_name: str, *, enabled: bool, endpoint: str, timeout_seconds: float
) -> TracerProvider | None:
    """Configure OTLP; exporter setup can never block service startup."""

    if not enabled:
        return None
    try:
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=timeout_seconds))
        )
        trace.set_tracer_provider(provider)
        return provider
    except Exception:
        return None


def safe_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    """Retain only documented, non-sensitive span attributes."""

    if not attributes:
        return {}
    return {key: value for key, value in attributes.items() if key in _SAFE_ATTRIBUTE_KEYS}


@contextmanager
def span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    context: otel_context.Context | None = None,
) -> Iterator[trace.Span]:
    """Create a span while making instrumentation failures harmless."""

    try:
        manager = trace.get_tracer("coldchain.observability").start_as_current_span(
            name, attributes=safe_attributes(attributes), context=context
        )
    except Exception:
        yield trace.INVALID_SPAN
        return
    with manager as current:
        yield current


def inject_kafka_headers(
    headers: Sequence[tuple[str, bytes]] | None = None,
) -> list[tuple[str, bytes]]:
    """Add W3C trace context without exposing application payload data."""

    carrier: dict[str, str] = {}
    try:
        propagate.inject(carrier)
    except Exception:
        return list(headers or ())
    existing = [(key, value) for key, value in (headers or ()) if key.lower() not in carrier]
    return [*existing, *((key, value.encode("ascii")) for key, value in carrier.items())]


def extract_kafka_context(
    headers: Sequence[tuple[str, bytes]] | None,
) -> otel_context.Context | None:
    """Extract W3C context from Kafka headers, ignoring malformed values."""

    carrier: dict[str, str] = {}
    for key, value in headers or ():
        try:
            carrier[key] = value.decode("ascii")
        except (UnicodeDecodeError, AttributeError):
            continue
    try:
        return propagate.extract(carrier)
    except Exception:
        return None


def current_trace_ids() -> tuple[str | None, str | None]:
    """Return canonical lowercase trace identifiers for log correlation."""

    current = trace.get_current_span().get_span_context()
    if not current.is_valid:
        return None, None
    return f"{current.trace_id:032x}", f"{current.span_id:016x}"
