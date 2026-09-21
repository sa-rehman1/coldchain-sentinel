"""Bounded-cardinality Prometheus metrics for the local demo stack."""

from collections.abc import Iterable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

UNKNOWN = "other"


def bounded(value: str, allowed: Iterable[str]) -> str:
    """Map arbitrary values onto an explicitly bounded label vocabulary."""

    allowed_values = frozenset(allowed)
    return value if value in allowed_values else UNKNOWN


class Metrics:
    """Own the complete stable metric contract."""

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        self.api_requests = Counter(
            "coldchain_api_requests",
            "API requests by route and status class.",
            ("method", "route", "status_class"),
            registry=registry,
        )
        self.api_duration = Histogram(
            "coldchain_api_request_duration_seconds",
            "API request latency.",
            ("method", "route"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
            registry=registry,
        )
        self.api_active = Gauge(
            "coldchain_api_active_requests",
            "Currently active API requests.",
            ("method", "route"),
            registry=registry,
        )
        self.structured_errors = Counter(
            "coldchain_structured_errors",
            "Safe error classifications.",
            ("component", "error_type"),
            registry=registry,
        )
        self.worker_events = Counter(
            "coldchain_worker_events",
            "Worker events by bounded outcome.",
            ("outcome",),
            registry=registry,
        )
        self.worker_duration = Histogram(
            "coldchain_worker_processing_duration_seconds",
            "Worker event processing latency.",
            ("outcome",),
            registry=registry,
        )
        self.incidents_created = Counter(
            "coldchain_incidents_created",
            "Incidents by breach type and severity.",
            ("breach_type", "severity"),
            registry=registry,
        )
        self.incidents_current = Gauge(
            "coldchain_incidents_current",
            "Current incidents by lifecycle state.",
            ("state",),
            registry=registry,
        )
        self.incident_transition_failures = Counter(
            "coldchain_incident_state_transition_failures",
            "Rejected state transitions.",
            ("reason",),
            registry=registry,
        )
        self.retrieval_duration = Histogram(
            "coldchain_retrieval_duration_seconds",
            "SOP retrieval latency.",
            ("outcome",),
            registry=registry,
        )
        self.retrieval_chunks = Histogram(
            "coldchain_retrieval_chunks_returned",
            "Chunks returned per retrieval.",
            buckets=(0, 1, 2, 3, 5, 8, 13),
            registry=registry,
        )
        self.retrieval_outcomes = Counter(
            "coldchain_retrieval_outcomes",
            "SOP retrieval outcomes.",
            ("outcome",),
            registry=registry,
        )
        self.recommendations = Counter(
            "coldchain_recommendations",
            "Recommendation results.",
            ("provider", "model", "validation_result"),
            registry=registry,
        )
        self.recommendation_fallback = Counter(
            "coldchain_recommendation_fallback",
            "Deterministic fallback activations.",
            ("reason",),
            registry=registry,
        )
        self.provider_duration = Histogram(
            "coldchain_provider_duration_seconds",
            "Provider latency.",
            ("provider", "model", "outcome"),
            registry=registry,
        )
        self.provider_tokens = Counter(
            "coldchain_provider_tokens",
            "Provider token usage.",
            ("provider", "model", "direction"),
            registry=registry,
        )
        self.provider_cost = Counter(
            "coldchain_provider_configured_cost_estimate",
            "Configured cost estimate.",
            ("provider", "model"),
            registry=registry,
        )
        self.governance_decisions = Counter(
            "coldchain_governance_decisions",
            "Governance decisions.",
            ("decision",),
            registry=registry,
        )
        self.governance_fail_closed = Counter(
            "coldchain_governance_fail_closed",
            "Fail-closed decisions.",
            ("reason",),
            registry=registry,
        )
        self.approval_decisions = Counter(
            "coldchain_approval_decisions",
            "Human approval decisions.",
            ("decision",),
            registry=registry,
        )
        self.recommendations_expired = Counter(
            "coldchain_recommendations_expired",
            "Expired recommendation attempts.",
            registry=registry,
        )
        self.kill_switch_blocks = Counter(
            "coldchain_kill_switch_blocks", "Kill-switch blocks.", registry=registry
        )
        self.commands_created = Counter(
            "coldchain_commands_created",
            "Authorized commands by action.",
            ("action",),
            registry=registry,
        )
        self.simulated_actions = Counter(
            "coldchain_simulated_actions",
            "Simulated action outcomes.",
            ("outcome",),
            registry=registry,
        )


metrics = Metrics()


def render_metrics() -> tuple[bytes, str]:
    """Return the Prometheus exposition payload and media type."""

    return generate_latest(), CONTENT_TYPE_LATEST
