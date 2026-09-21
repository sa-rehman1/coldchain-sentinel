# Local dashboards and alerts

Start the optional services with the `observability` Compose profile and a unique project name.
Set `COLDCHAIN_OTEL_TRACING_ENABLED=true` only for that process if traces are desired. Default URLs:

- Grafana: `http://localhost:13001`
- Prometheus: `http://localhost:19090`
- Jaeger: `http://localhost:16687`
- Worker metrics: `http://localhost:18005/metrics`

Grafana provisions **Operations Control Tower** and **Governed AI** from version-controlled JSON.
Every panel is backed by a PromQL query. Alert rules cover dead-letter activity, elevated fallback
rate, fail-closed governance, worker failure, and API 5xx rate. Alerts are local demonstrations and
have no paging integration.

Host ports are configurable with the corresponding `COLDCHAIN_*_HOST_PORT` settings. All
observability host bindings use `127.0.0.1`.
