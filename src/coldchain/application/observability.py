"""Safe, read-only observability aggregation for the local portfolio demo."""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Protocol

import httpx

from coldchain.application.interfaces import DashboardReader
from coldchain.config import Settings

JsonGetter = Callable[[str], Awaitable[dict[str, Any]]]

_INSTANT_QUERIES = {
    "request_rate": "sum(rate(coldchain_api_requests_total[5m])) or vector(0)",
    "p95_latency": (
        "histogram_quantile(0.95, "
        "sum(rate(coldchain_api_request_duration_seconds_bucket[5m])) by (le)) * 1000"
    ),
    "error_rate": (
        '(sum(rate(coldchain_api_requests_total{status_class="5xx"}[5m])) or vector(0)) / '
        "clamp_min((sum(rate(coldchain_api_requests_total[5m])) or vector(0)), 0.001) * 100"
    ),
    "worker_throughput": (
        '(sum(rate(coldchain_worker_events_total{outcome="processed"}[5m])) or vector(0)) * 60'
    ),
    "dlq_activity": (
        'sum(increase(coldchain_worker_events_total{outcome="dlq"}[15m])) or vector(0)'
    ),
    "recommendation_count": "sum(increase(coldchain_recommendations_total[1h])) or vector(0)",
    "recommendation_p95": (
        "histogram_quantile(0.95, "
        "sum(rate(coldchain_provider_duration_seconds_bucket[10m])) by (le)) * 1000"
    ),
    "fallback_count": ("sum(increase(coldchain_recommendation_fallback_total[1h])) or vector(0)"),
    "simulated_actions": "sum(increase(coldchain_simulated_actions_total[1h])) or vector(0)",
}

_RANGE_QUERIES = {
    "apiRequestRate": _INSTANT_QUERIES["request_rate"],
    "apiP95Latency": _INSTANT_QUERIES["p95_latency"],
    "workerThroughput": _INSTANT_QUERIES["worker_throughput"],
    "dlqActivity": _INSTANT_QUERIES["dlq_activity"],
}


class DatabaseProbe(Protocol):
    async def ping(self) -> None: ...


class PrometheusProbe(Protocol):
    async def instant(self, query_key: str) -> float | None: ...

    async def series(self, query_key: str, now: datetime) -> list[dict[str, object]]: ...

    async def targets(self) -> dict[str, bool]: ...

    async def alerts(self) -> tuple[list[dict[str, str]], int]: ...


class PrometheusReader:
    """Bounded Prometheus HTTP API reader with strict timeouts and no dynamic PromQL."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise ValueError("observability response was not successful")
        return payload

    async def instant(self, query_key: str) -> float | None:
        query = _INSTANT_QUERIES[query_key]
        payload = await self._get("/api/v1/query", {"query": query})
        result = payload.get("data", {}).get("result", [])
        if not isinstance(result, list) or not result:
            return None
        value = result[0].get("value") if isinstance(result[0], dict) else None
        return _finite_number(value[1] if isinstance(value, list) and len(value) == 2 else None)

    async def series(self, query_key: str, now: datetime) -> list[dict[str, object]]:
        query = _RANGE_QUERIES[query_key]
        payload = await self._get(
            "/api/v1/query_range",
            {
                "query": query,
                "start": str(int((now - timedelta(minutes=30)).timestamp())),
                "end": str(int(now.timestamp())),
                "step": "60",
            },
        )
        result = payload.get("data", {}).get("result", [])
        values = result[0].get("values") if isinstance(result, list) and result else None
        points: list[dict[str, object]] = []
        for item in values if isinstance(values, list) else []:
            if not isinstance(item, list) or len(item) != 2:
                continue
            value = _finite_number(item[1])
            if value is not None:
                points.append(
                    {
                        "timestamp": datetime.fromtimestamp(float(item[0]), UTC).isoformat(),
                        "value": round(value, 3),
                    }
                )
        return points[-31:]

    async def targets(self) -> dict[str, bool]:
        payload = await self._get("/api/v1/targets")
        active = payload.get("data", {}).get("activeTargets", [])
        result: dict[str, bool] = {}
        for target in active if isinstance(active, list) else []:
            if not isinstance(target, dict):
                continue
            labels = target.get("labels", {})
            job = labels.get("job") if isinstance(labels, dict) else None
            if job in {"coldchain-api", "coldchain-worker"}:
                result[str(job)] = target.get("health") == "up"
        return result

    async def alerts(self) -> tuple[list[dict[str, str]], int]:
        payload = await self._get("/api/v1/rules", {"type": "alert"})
        groups = payload.get("data", {}).get("groups", [])
        rules: list[dict[str, str]] = []
        firing = 0
        for group in groups if isinstance(groups, list) else []:
            for rule in group.get("rules", []) if isinstance(group, dict) else []:
                if not isinstance(rule, dict) or len(rules) >= 20:
                    continue
                state = str(rule.get("state", "inactive")).upper()
                firing += int(state == "FIRING")
                labels = rule.get("labels", {})
                annotations = rule.get("annotations", {})
                rules.append(
                    {
                        "name": str(rule.get("name", "Unnamed rule"))[:80],
                        "state": state,
                        "severity": str(labels.get("severity", "info"))[:20],
                        "summary": str(annotations.get("summary", "No summary provided"))[:160],
                    }
                )
        return rules, firing


class ObservabilitySummaryService:
    """Aggregate bounded operational data without exposing underlying payloads."""

    def __init__(
        self,
        settings: Settings,
        database: DatabaseProbe | None,
        dashboard_reader: DashboardReader | None,
        prometheus: PrometheusProbe | None = None,
        json_getter: JsonGetter | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._dashboard_reader = dashboard_reader
        self._prometheus = prometheus or PrometheusReader(
            settings.prometheus_url, settings.observability_timeout_seconds
        )
        self._json_getter = json_getter or self._get_json

    async def summary(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        checked_at = now.isoformat()
        prometheus_available = True
        try:
            targets = await self._prometheus.targets()
        except Exception:
            targets = {}
            prometheus_available = False

        values = await asyncio.gather(
            *(self._safe_instant(key) for key in _INSTANT_QUERIES),
        )
        metrics = dict(zip(_INSTANT_QUERIES, values, strict=True))
        series_values = await asyncio.gather(
            *(self._safe_series(key, now) for key in _RANGE_QUERIES),
        )
        series = dict(zip(_RANGE_QUERIES, series_values, strict=True))

        dashboard: dict[str, Any] = {}
        if self._dashboard_reader is not None:
            try:
                dashboard = await self._dashboard_reader.dashboard()
            except Exception:
                dashboard = {}
        dashboard_metrics = dashboard.get("metrics", {})

        database_status, database_signal, database_latency = await self._database_status()
        kafka_status, kafka_signal, kafka_latency = await self._tcp_status(
            self._settings.kafka_bootstrap_servers, "Kafka broker reachable"
        )
        qdrant_status, qdrant_signal, qdrant_latency = await self._http_status(
            f"{self._settings.qdrant_url.rstrip('/')}/readyz", "Qdrant readiness confirmed"
        )
        grafana_status, grafana_signal, grafana_latency = await self._http_status(
            f"{self._settings.grafana_url.rstrip('/')}/api/health",
            "Grafana API healthy",
            optional=True,
        )
        jaeger_status, jaeger_signal, jaeger_latency = await self._http_status(
            f"{self._settings.jaeger_url.rstrip('/')}/api/services",
            "Jaeger query API available",
            optional=True,
        )

        services = [
            self._service("FastAPI", "HEALTHY", "Observability summary served", None, checked_at),
            self._service(
                "Worker",
                "HEALTHY" if targets.get("coldchain-worker") else "UNAVAILABLE",
                "Prometheus scrape target is up"
                if targets.get("coldchain-worker")
                else "Worker metrics target is unavailable",
                None,
                checked_at,
            ),
            self._service(
                "PostgreSQL", database_status, database_signal, database_latency, checked_at
            ),
            self._service("Kafka", kafka_status, kafka_signal, kafka_latency, checked_at),
            self._service("Qdrant", qdrant_status, qdrant_signal, qdrant_latency, checked_at),
            self._service(
                "Prometheus",
                "HEALTHY" if prometheus_available else "OPTIONAL_NOT_STARTED",
                "API and worker targets queried"
                if prometheus_available
                else "Optional observability profile is not available",
                None,
                checked_at,
                self._settings.local_prometheus_url,
            ),
            self._service(
                "Grafana",
                grafana_status,
                grafana_signal,
                grafana_latency,
                checked_at,
                self._settings.local_grafana_url,
            ),
            self._service(
                "Jaeger",
                jaeger_status,
                jaeger_signal,
                jaeger_latency,
                checked_at,
                self._settings.local_jaeger_url,
            ),
            self._service(
                "Recommendation provider",
                "HEALTHY" if self._provider_configured() else "DEGRADED",
                self._provider_signal(),
                None,
                checked_at,
            ),
        ]

        try:
            rules, active_alerts = await self._prometheus.alerts()
            alert_state = "AVAILABLE"
        except Exception:
            rules, active_alerts, alert_state = [], 0, "UNAVAILABLE"
        traces, trace_state = await self._traces()

        metric_rows = [
            _metric(
                "request_rate",
                "Request rate",
                metrics["request_rate"],
                "requests/second",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-api", False),
            ),
            _metric(
                "p95_latency",
                "API P95 latency",
                metrics["p95_latency"],
                "milliseconds",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-api", False),
            ),
            _metric(
                "error_rate",
                "API error rate",
                metrics["error_rate"],
                "percent",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-api", False),
            ),
            _metric(
                "worker_throughput",
                "Worker throughput",
                metrics["worker_throughput"],
                "events/minute",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
            _metric("consumer_lag", "Consumer lag", None, "messages", "Not instrumented"),
            _metric(
                "dlq_activity",
                "DLQ activity",
                metrics["dlq_activity"],
                "messages/15 minutes",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
            _metric(
                "recommendation_count",
                "Recommendations",
                metrics["recommendation_count"],
                "count/hour",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
            _metric(
                "recommendation_p95",
                "Recommendation P95 latency",
                metrics["recommendation_p95"],
                "milliseconds",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
            _metric(
                "fallback_count",
                "Fallback activations",
                metrics["fallback_count"],
                "count/hour",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
            _metric(
                "open_incidents",
                "Open incidents",
                _number(dashboard_metrics.get("openIncidents")),
                "incidents",
                "PostgreSQL showcase read model",
            ),
            _metric(
                "awaiting_review",
                "Awaiting review",
                _number(dashboard_metrics.get("awaitingHumanReview")),
                "incidents",
                "PostgreSQL showcase read model",
            ),
            _metric(
                "simulated_actions",
                "Simulated action outcomes",
                metrics["simulated_actions"],
                "count/hour",
                "Prometheus",
                source_available=prometheus_available and targets.get("coldchain-worker", False),
            ),
        ]
        healthy = sum(item["status"] == "HEALTHY" for item in services)
        required_bad = any(
            item["status"] in {"DEGRADED", "UNAVAILABLE"}
            for item in services
            if item["name"] not in {"Prometheus", "Grafana", "Jaeger"}
        )
        return {
            "generatedAt": checked_at,
            "overallStatus": "DEGRADED" if required_bad else "HEALTHY",
            "healthyServices": healthy,
            "totalServices": len(services),
            "activeAlerts": active_alerts,
            "autoRefreshSeconds": 12,
            "services": services,
            "metrics": metric_rows,
            "series": series,
            "alerts": {"state": alert_state, "rules": rules},
            "traces": {"state": trace_state, "items": traces},
            "privacyNotice": (
                "Metrics and traces exclude incident payloads, prompts, SOP text, credentials, "
                "and provider responses."
            ),
        }

    async def _safe_instant(self, key: str) -> float | None:
        try:
            return await self._prometheus.instant(key)
        except Exception:
            return None

    async def _safe_series(self, key: str, now: datetime) -> list[dict[str, object]]:
        try:
            return await self._prometheus.series(key, now)
        except Exception:
            return []

    async def _database_status(self) -> tuple[str, str, float | None]:
        if self._database is None:
            return "UNAVAILABLE", "Database is not configured", None
        started = perf_counter()
        try:
            await asyncio.wait_for(
                self._database.ping(), self._settings.observability_timeout_seconds
            )
            return "HEALTHY", "Authoritative workflow store reachable", _elapsed_ms(started)
        except Exception:
            return "UNAVAILABLE", "Database readiness check failed", None

    async def _tcp_status(self, address: str, signal: str) -> tuple[str, str, float | None]:
        first = address.split(",", 1)[0]
        host, _, port_text = first.rpartition(":")
        started = perf_counter()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port_text)),
                self._settings.observability_timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return "HEALTHY", signal, _elapsed_ms(started)
        except Exception:
            return "UNAVAILABLE", "Broker connectivity check failed", None

    async def _http_status(
        self, url: str, signal: str, *, optional: bool = False
    ) -> tuple[str, str, float | None]:
        started = perf_counter()
        try:
            await self._json_getter(url)
            return "HEALTHY", signal, _elapsed_ms(started)
        except Exception:
            status = "OPTIONAL_NOT_STARTED" if optional else "UNAVAILABLE"
            return (
                status,
                "Optional service is not available" if optional else "Readiness check failed",
                None,
            )

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self._settings.observability_timeout_seconds
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                payload = {}
        if not isinstance(payload, dict):
            raise ValueError("expected an object response")
        return payload

    async def _traces(self) -> tuple[list[dict[str, object]], str]:
        try:
            payload = await self._json_getter(
                f"{self._settings.jaeger_url.rstrip('/')}/api/traces"
                "?service=coldchain-control-plane&limit=5&lookback=1h"
            )
        except Exception:
            return [], "UNAVAILABLE"
        traces: list[dict[str, object]] = []
        for item in payload.get("data", []) if isinstance(payload.get("data"), list) else []:
            if not isinstance(item, dict):
                continue
            spans = item.get("spans", [])
            if not isinstance(spans, list) or not spans:
                continue
            root = spans[0] if isinstance(spans[0], dict) else {}
            durations = [float(span.get("duration", 0)) for span in spans if isinstance(span, dict)]
            if not durations:
                continue
            trace_id = str(item.get("traceID", ""))
            traces.append(
                {
                    "traceId": trace_id[-16:] if trace_id else "unavailable",
                    "operation": str(root.get("operationName", "workflow"))[:80],
                    "durationMs": round(
                        max(durations) / 1000,
                        2,
                    ),
                    "spanCount": len(spans),
                    "startedAt": datetime.fromtimestamp(
                        float(root.get("startTime", 0)) / 1_000_000, UTC
                    ).isoformat(),
                }
            )
        return traces, "AVAILABLE" if traces else "NO_SAMPLES"

    def _provider_configured(self) -> bool:
        return self._settings.llm_provider == "deterministic" or bool(
            os.getenv(self._settings.selected_llm_api_key_env, "")
            and self._settings.selected_llm_model
        )

    def _provider_signal(self) -> str:
        if self._settings.llm_provider == "deterministic":
            return "Deterministic local engine; no external model call"
        if not self._settings.llm_live_calls_enabled:
            return f"{self._settings.llm_provider.title()} configured; live calls disabled"
        return f"{self._settings.llm_provider.title()} live calls enabled"

    @staticmethod
    def _service(
        name: str,
        status: str,
        signal: str,
        measurement: float | None,
        checked_at: str,
        inspection_url: str | None = None,
    ) -> dict[str, object]:
        return {
            "name": name,
            "status": status,
            "signal": signal,
            "measurement": measurement,
            "measurementUnit": "milliseconds" if measurement is not None else None,
            "checkedAt": checked_at,
            "inspectionUrl": inspection_url,
        }


def _finite_number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _number(value: object) -> float | None:
    return _finite_number(value)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 2)


def _metric(
    key: str,
    label: str,
    value: float | None,
    unit: str,
    source: str,
    *,
    source_available: bool = True,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": round(value, 3) if value is not None else None,
        "unit": unit,
        "state": (
            "AVAILABLE"
            if value is not None
            else "NO_SAMPLES"
            if source_available
            else "UNAVAILABLE"
        ),
        "source": source,
    }
