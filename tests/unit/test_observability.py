import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState
from prometheus_client import CollectorRegistry, generate_latest

from coldchain.api.app import create_app
from coldchain.api.middleware import normalize_route
from coldchain.api.schemas import ObservabilitySummaryView
from coldchain.application.observability import ObservabilitySummaryService, PrometheusReader
from coldchain.config import Settings
from coldchain.observability.logging import JsonFormatter
from coldchain.observability.metrics import Metrics, bounded, render_metrics
from coldchain.observability.tracing import (
    configure_tracing,
    extract_kafka_context,
    inject_kafka_headers,
    safe_attributes,
    span,
)


def test_metric_contract_and_cardinality_are_bounded() -> None:
    registry = CollectorRegistry()
    contract = Metrics(registry)
    route = normalize_route("/api/v1/incidents/untrusted-identifier")
    contract.api_requests.labels(method="GET", route=route, status_class="2xx").inc()
    contract.worker_events.labels(outcome="processed").inc()
    payload = generate_latest(registry).decode()
    assert 'route="/api/v1/incidents/{incident_id}"' in payload
    assert "untrusted-identifier" not in payload
    assert bounded("arbitrary-id", {"allowed"}) == "other"
    assert normalize_route("/unbounded/value") == "unmatched"


async def test_metrics_endpoint_is_independent_of_readiness() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert "coldchain_api_requests_total" in response.text
    payload, content_type = render_metrics()
    assert payload
    assert "text/plain" in content_type


def test_structured_logging_uses_allowlist_and_redacts_secrets() -> None:
    formatter = JsonFormatter()
    record = logging.makeLogRecord(
        {
            "name": "test.component",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "authorization=Bearer abc.def gsk_not-a-real-key",
            "component": "worker",
            "eventName": "safe_event",
            "correlationId": "safe-correlation",
            "prompt": "must-never-appear",
            "arbitrary": "also-omitted",
        }
    )
    parsed = json.loads(formatter.format(record))
    assert parsed["severity"] == "INFO"
    assert parsed["component"] == "worker"
    assert parsed["correlationId"] == "safe-correlation"
    assert "abc.def" not in parsed["message"]
    assert "gsk_not-a-real-key" not in parsed["message"]
    assert "prompt" not in parsed
    assert "arbitrary" not in parsed


def test_trace_helpers_are_fail_safe_and_filter_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert configure_tracing("test", enabled=False, endpoint="unused", timeout_seconds=1) is None
    monkeypatch.setattr(
        "coldchain.observability.tracing.OTLPSpanExporter",
        lambda **_: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert configure_tracing("test", enabled=True, endpoint="unused", timeout_seconds=1) is None
    assert safe_attributes({"coldchain.action": "HOLD_SHIPMENT", "secret": "no"}) == {
        "coldchain.action": "HOLD_SHIPMENT"
    }
    with pytest.raises(ValueError, match="workflow"):
        with span("test.span"):
            raise ValueError("workflow")


def test_kafka_trace_headers_handle_empty_and_malformed_context() -> None:
    trace_id = 0x1234567890ABCDEF1234567890ABCDEF
    span_id = 0x1234567890ABCDEF
    source = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    token = context_api.attach(trace.set_span_in_context(NonRecordingSpan(source)))
    try:
        headers = inject_kafka_headers([("application-header", b"safe")])
    finally:
        context_api.detach(token)
    assert ("application-header", b"safe") in headers
    assert any(key == "traceparent" for key, _ in headers)
    extracted = extract_kafka_context(headers)
    assert extracted is not None
    assert trace.get_current_span(extracted).get_span_context().trace_id == trace_id
    malformed = extract_kafka_context([("traceparent", b"not-valid"), ("binary", b"\xff")])
    assert malformed is not None


def test_provisioned_dashboards_are_query_backed() -> None:
    root = Path(__file__).resolve().parents[2]
    dashboard_dir = root / "observability" / "grafana" / "dashboards"
    documents = [
        json.loads(path.read_text(encoding="utf-8")) for path in dashboard_dir.glob("*.json")
    ]
    assert {document["title"] for document in documents} == {
        "Operations Control Tower",
        "Governed AI",
    }
    assert all(len(document["panels"]) >= 8 for document in documents)
    assert all(
        target.get("expr")
        for document in documents
        for panel in document["panels"]
        for target in panel["targets"]
    )


def test_prometheus_scrapes_both_services_and_provisions_required_alerts() -> None:
    root = Path(__file__).resolve().parents[2]
    prometheus = yaml.safe_load(
        (root / "observability" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")
    )
    alerts = yaml.safe_load(
        (root / "observability" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
    )
    jobs = {item["job_name"] for item in prometheus["scrape_configs"]}
    names = {rule["alert"] for group in alerts["groups"] for rule in group["rules"]}
    assert jobs == {"coldchain-api", "coldchain-worker"}
    assert names == {
        "ColdChainDeadLetterActivity",
        "ColdChainHighFallbackRate",
        "ColdChainGovernanceFailClosed",
        "ColdChainWorkerFailure",
        "ColdChainApiErrorRate",
    }


class HealthyDatabase:
    async def ping(self) -> None:
        return None


class DashboardReaderStub:
    async def dashboard(self) -> dict[str, object]:
        return {"metrics": {"openIncidents": 3, "awaitingHumanReview": 2}}


class PrometheusStub:
    async def instant(self, key: str) -> float | None:
        return {
            "request_rate": 1.25,
            "p95_latency": 42.5,
            "error_rate": 0.0,
            "worker_throughput": 12.0,
            "dlq_activity": 0.0,
            "recommendation_count": 0.0,
            "recommendation_p95": None,
            "fallback_count": 0.0,
            "simulated_actions": 1.0,
        }[key]

    async def series(self, key: str, _now: object) -> list[dict[str, object]]:
        return (
            [{"timestamp": "2026-09-27T12:00:00+00:00", "value": 1.0}]
            if key != "dlqActivity"
            else []
        )

    async def targets(self) -> dict[str, bool]:
        return {"coldchain-api": True, "coldchain-worker": True}

    async def alerts(self) -> tuple[list[dict[str, str]], int]:
        return (
            [
                {
                    "name": "ColdChainApiErrorRate",
                    "state": "INACTIVE",
                    "severity": "warning",
                    "summary": "API error rate is bounded",
                }
            ],
            0,
        )


async def safe_json_getter(url: str) -> dict[str, object]:
    if "/api/traces" in url:
        return {"data": []}
    return {"status": "ok"}


async def test_prometheus_reader_parses_allowlisted_metrics_targets_and_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = PrometheusReader("http://prometheus:9090/", 1.0)

    async def fake_get(path: str, params: dict[str, str] | None = None) -> dict[str, object]:
        assert params is None or "query" in params or params == {"type": "alert"}
        if path == "/api/v1/query":
            query = str(params.get("query", "")) if params else ""
            value = "0" if "vector(0)" in query else "1.25"
            return {"data": {"result": [{"value": [1_000, value]}]}}
        if path == "/api/v1/query_range":
            return {
                "data": {
                    "result": [
                        {
                            "values": [
                                [1_000, "2.5"],
                                [1_060, "not-a-number"],
                                [1_120, "3.75"],
                            ]
                        }
                    ]
                }
            }
        if path == "/api/v1/targets":
            return {
                "data": {
                    "activeTargets": [
                        {"labels": {"job": "coldchain-api"}, "health": "up"},
                        {"labels": {"job": "coldchain-worker"}, "health": "down"},
                        {"labels": {"job": "unrelated"}, "health": "up"},
                    ]
                }
            }
        return {
            "data": {
                "groups": [
                    {
                        "rules": [
                            {
                                "name": "ColdChainApiErrorRate",
                                "state": "firing",
                                "labels": {"severity": "warning"},
                                "annotations": {"summary": "Error rate is elevated"},
                            }
                        ]
                    }
                ]
            }
        }

    monkeypatch.setattr(reader, "_get", fake_get)
    assert await reader.instant("request_rate") == 0
    assert await reader.instant("error_rate") == 0
    assert await reader.instant("p95_latency") == 1.25
    assert await reader.series("apiRequestRate", datetime.now(UTC)) == [
        {"timestamp": "1970-01-01T00:16:40+00:00", "value": 2.5},
        {"timestamp": "1970-01-01T00:18:40+00:00", "value": 3.75},
    ]
    assert await reader.targets() == {"coldchain-api": True, "coldchain-worker": False}
    rules, firing = await reader.alerts()
    assert firing == 1
    assert rules[0] == {
        "name": "ColdChainApiErrorRate",
        "state": "FIRING",
        "severity": "warning",
        "summary": "Error rate is elevated",
    }


async def test_observability_trace_projection_retains_only_safe_metadata() -> None:
    async def trace_json_getter(url: str) -> dict[str, object]:
        if "/api/traces" not in url:
            return {"status": "ok"}
        return {
            "data": [
                {
                    "traceID": "1234567890abcdef1234567890abcdef",
                    "spans": [
                        {
                            "operationName": "incident.recommendation",
                            "duration": 12_500,
                            "startTime": 1_750_000_000_000_000,
                            "tags": [{"key": "prompt", "value": "must not escape"}],
                        },
                        {"operationName": "child", "duration": 4_000},
                    ],
                }
            ]
        }

    service = ObservabilitySummaryService(
        Settings(environment="test", database_url=None, kafka_bootstrap_servers="127.0.0.1:1"),
        None,
        None,
        prometheus=PrometheusStub(),
        json_getter=trace_json_getter,
    )
    traces, state = await service._traces()
    assert state == "AVAILABLE"
    assert traces == [
        {
            "traceId": "1234567890abcdef",
            "operation": "incident.recommendation",
            "durationMs": 12.5,
            "spanCount": 2,
            "startedAt": "2025-06-15T15:06:40+00:00",
        }
    ]
    assert "prompt" not in json.dumps(traces).lower()


async def test_observability_summary_has_typed_units_bounded_services_and_no_sensitive_fields() -> (
    None
):
    settings = Settings(
        environment="test",
        database_url=None,
        kafka_bootstrap_servers="127.0.0.1:1",
        prometheus_url="http://prometheus:9090",
        grafana_url="http://grafana:3000",
        jaeger_url="http://jaeger:16686",
    )
    service = ObservabilitySummaryService(
        settings,
        HealthyDatabase(),
        DashboardReaderStub(),
        prometheus=PrometheusStub(),
        json_getter=safe_json_getter,
    )
    result = await service.summary()
    ObservabilitySummaryView.model_validate(result)
    metrics = {item["key"]: item for item in result["metrics"]}
    assert metrics["request_rate"]["unit"] == "requests/second"
    assert metrics["p95_latency"]["unit"] == "milliseconds"
    assert metrics["worker_throughput"]["unit"] == "events/minute"
    assert metrics["error_rate"] == {
        "key": "error_rate",
        "label": "API error rate",
        "value": 0.0,
        "unit": "percent",
        "state": "AVAILABLE",
        "source": "Prometheus",
    }
    assert metrics["dlq_activity"]["value"] == 0.0
    assert metrics["recommendation_count"]["value"] == 0.0
    assert metrics["fallback_count"]["value"] == 0.0
    assert metrics["consumer_lag"]["state"] == "NO_SAMPLES"
    assert metrics["open_incidents"]["value"] == 3
    assert len(result["services"]) == 9
    safe_result = dict(result)
    safe_result.pop("privacyNotice")
    serialized = json.dumps(safe_result).lower()
    assert all(
        token not in serialized
        for token in ("authorization", "password", "connectionstring", "prompt", "sop text")
    )


class UnavailablePrometheus(PrometheusStub):
    async def targets(self) -> dict[str, bool]:
        raise TimeoutError

    async def instant(self, key: str) -> float | None:
        raise TimeoutError(key)

    async def series(self, key: str, _now: object) -> list[dict[str, object]]:
        raise TimeoutError(key)

    async def alerts(self) -> tuple[list[dict[str, str]], int]:
        raise TimeoutError


async def test_observability_summary_degrades_safely_on_prometheus_timeout() -> None:
    async def unavailable(_: str) -> dict[str, object]:
        raise TimeoutError

    service = ObservabilitySummaryService(
        Settings(environment="test", database_url=None, kafka_bootstrap_servers="127.0.0.1:1"),
        None,
        None,
        prometheus=UnavailablePrometheus(),
        json_getter=unavailable,
    )
    result = await service.summary()
    prometheus = next(item for item in result["services"] if item["name"] == "Prometheus")
    assert prometheus["status"] == "OPTIONAL_NOT_STARTED"
    metrics = {item["key"]: item for item in result["metrics"]}
    assert metrics["request_rate"]["state"] == "UNAVAILABLE"
    assert metrics["p95_latency"]["state"] == "UNAVAILABLE"
    assert metrics["worker_throughput"]["state"] == "UNAVAILABLE"
    assert metrics["recommendation_count"]["state"] == "UNAVAILABLE"
    assert metrics["consumer_lag"]["state"] == "NO_SAMPLES"
    assert metrics["open_incidents"]["state"] == "NO_SAMPLES"
    assert result["alerts"] == {"state": "UNAVAILABLE", "rules": []}
    assert result["traces"] == {"state": "UNAVAILABLE", "items": []}
