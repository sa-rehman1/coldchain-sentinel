# Milestone 1C: local observability and evaluation

> Historical implementation record. See the [target architecture](target-architecture.md) for the current system.

Milestone 1C adds a local, portfolio-sized observability plane without changing the authority
boundary established in Milestone 1B. Prometheus collects bounded application metrics, Grafana
loads two provisioned dashboards, and Jaeger receives OTLP/HTTP traces directly from the API and
worker. An OpenTelemetry Collector is intentionally omitted because the single local exporter path
does not justify another service.

The request path is represented as nested spans: HTTP intake, Kafka publish, Kafka consume, policy
evaluation, persistence, SOP retrieval, recommendation or fallback, governance, human decision,
command creation, and simulated action. W3C `traceparent` and `tracestate` values travel only in
Kafka headers. Identifiers remain in traces and correlated logs where needed; they are never metric
labels.

Observability is advisory. An exporter, dashboard, or metrics failure cannot authorize an action,
alter deterministic policy, bypass approval, or make the API readiness check fail. Live model calls
remain disabled by default. The evaluation harness uses synthetic fixtures and no network access.

## Local footprint

The optional profile pins Prometheus 3.14.0, Grafana 13.2.2, and Jaeger all-in-one 1.76.0. It is
expected to use roughly 0.6–1.1 GB RAM, 1–2 GB of image layers, up to 256 MB of Prometheus data,
and less than 100 MB of Grafana data. Jaeger uses in-memory storage. This is deliberately a local
demo architecture, not a production topology.

Jaeger 1.76.0 is the final release of the named `all-in-one` v1 distribution and is end-of-life.
It is retained here only to satisfy the compact, single-container local demo requirement. A future
production design must migrate to supported Jaeger v2 components and review its deployment model;
that expansion is outside Milestone 1C.
