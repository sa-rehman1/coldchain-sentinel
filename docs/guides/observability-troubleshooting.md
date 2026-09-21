# Observability troubleshooting

If a dashboard is empty, confirm `/metrics` responds on the API and worker, then inspect Prometheus
**Status → Targets**. An unhealthy target does not imply that application readiness should fail.

If traces are absent, confirm the observability profile includes Jaeger and that the application
process was started with `COLDCHAIN_OTEL_TRACING_ENABLED=true`. The endpoint inside Compose is
`http://jaeger:4318/v1/traces`; the host port is for local tools only.

If a host port is occupied, choose unused `COLDCHAIN_PROMETHEUS_HOST_PORT`,
`COLDCHAIN_GRAFANA_HOST_PORT`, `COLDCHAIN_JAEGER_UI_HOST_PORT`,
`COLDCHAIN_JAEGER_OTLP_HTTP_HOST_PORT`, or `COLDCHAIN_WORKER_METRICS_HOST_PORT` values. Always use a
unique Compose project name. Do not remove unrelated containers or volumes.

If an evaluation fails, read the ignored JSON report for per-scenario checks. Fix implementation or
fixture drift; do not lower thresholds merely to make the run pass.
