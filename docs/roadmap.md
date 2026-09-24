# Roadmap and current scope

## Implemented locally

- Versioned telemetry, Kafka ingestion, deterministic breach policy, PostgreSQL persistence, and Alembic migrations.
- Immutable evidence, Qdrant SOP retrieval, strict provider output, deterministic fallback and governance, human approval, idempotent commands, and simulated execution.
- React control tower, local scenarios, Prometheus/Grafana dashboards, OpenTelemetry/Jaeger tracing, structured logs, and deterministic evaluation.
- Optional Groq validation and offline-tested OpenAI support; deterministic mode remains the default.

## Production hardening still required

- Enterprise OIDC/RBAC, managed secrets, TLS, network policy, privacy/retention controls, and immutable audit storage.
- Real telemetry, weather, carrier/TMS, notification, and action adapters.
- Transactional outbox/inbox patterns, durable retries, capacity testing, failure injection, recovery procedures, SLOs, backups, HA, and disaster recovery.
- Provider contracts, cost budgets, model qualification, shadow evaluation, and operating-environment validation.

## Deliberately out of scope

Cloud deployment, Kubernetes/Terraform, autonomous consequential actions, real shipment control, and production-scale claims are not part of the portfolio release.
