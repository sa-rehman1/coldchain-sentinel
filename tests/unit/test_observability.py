import json
import logging
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
