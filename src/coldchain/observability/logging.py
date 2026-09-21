"""Structured, correlated JSON logging with explicit safe-field controls."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from coldchain.observability.tracing import current_trace_ids

_SAFE_FIELDS = frozenset(
    {
        "service",
        "component",
        "eventName",
        "correlationId",
        "causationId",
        "outcome",
        "status",
        "durationMs",
        "method",
        "route",
        "statusCode",
        "partition",
        "offset",
        "retryable",
        "errorType",
        "breachType",
        "severity",
        "action",
        "governanceDecision",
        "provider",
        "model",
        "fallbackReason",
    }
)
_SENSITIVE_MARKERS = (
    "authorization",
    "credential",
    "database_url",
    "password",
    "prompt",
    "secret",
    "sop_text",
    "token",
    "api_key",
    "model_response",
)
_service_name = "coldchain"
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]+|gsk_[a-z0-9_-]+|(?:api[_-]?key|password)\s*[=:]\s*\S+)"
)


def _safe_value(key: str, value: Any) -> Any:
    if any(marker in key.lower() for marker in _SENSITIVE_MARKERS):
        return "[REDACTED]"
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", value[:256])
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:256]


class JsonFormatter(logging.Formatter):
    """Serialize a stable allowlist of operational fields as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = current_trace_ids()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "service": getattr(record, "service", _service_name),
            "component": getattr(record, "component", record.name),
            "eventName": getattr(record, "eventName", "log"),
            "message": _safe_value("message", record.getMessage()),
        }
        if trace_id is not None:
            payload["traceId"] = trace_id
            payload["spanId"] = span_id
        for key in _SAFE_FIELDS:
            if key in record.__dict__:
                payload[key] = _safe_value(key, record.__dict__[key])
        if record.exc_info:
            payload["errorType"] = record.exc_info[0].__name__ if record.exc_info[0] else "unknown"
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str, service: str = "coldchain") -> None:
    """Configure the process root logger once at application startup."""

    global _service_name
    _service_name = service
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
