# Target architecture

## Decision summary

ColdChain Sentinel is a Python-only modular application with separate process
entrypoints. It starts as one repository and deployable codebase, not as premature
microservices. Modules share versioned domain and contract packages while process
boundaries allow independent scaling later.

```text
Telemetry sources -> Kafka -> telemetry worker -> PostgreSQL incidents
                                          |             |
SOPs + weather + telemetry -> AI investigation worker   |
                                          |             v
                                          +-> recommendation
                                                    |
Dispatcher UI -> FastAPI control plane -> governance -> approval
                                                    |
                                                    v
                                             action worker
                                          (simulated first)
```

## Module boundaries

- `api`: transport, authentication integration, errors, and dependency wiring.
- `domain`: framework-free entities, value types, policies, and interfaces.
- `application`: use cases, transaction orchestration, and ports.
- `infrastructure`: PostgreSQL, Kafka, weather, retrieval, and vendor adapters.
- `contracts`: versioned external messages and JSON Schema definitions.
- `governance`: deterministic implementations of domain governance interfaces.
- `ai`: bounded LangGraph investigation and typed recommendations.
- `workers`: independent telemetry, investigation, and action entrypoints.
- `observability`: structured logging, tracing, metrics, and redaction.

The domain layer must not import FastAPI, Kafka, SQLAlchemy, LangGraph, or vendor
SDKs. Infrastructure depends inward on application/domain interfaces.

## Process responsibilities

### FastAPI control plane

Owns shipment, telemetry, incident, recommendation, policy, approval, action
command, and authoritative audit APIs. It validates identity and authorization,
persists decisions, and emits events through a transactional outbox.

### Telemetry worker

Consumes versioned Kafka messages, validates and normalizes readings, enforces
event-id idempotency, detects deterministic anomalies, and creates incidents in a
single transaction before committing offsets.

### AI investigation worker

Uses bounded LangGraph orchestration to assemble temporally aligned telemetry,
weather, operational, and versioned SOP evidence. It emits a typed recommendation
that explicitly carries no authority. It cannot call action adapters.

### Governance engine

Evaluates versioned policies deterministically. Kill-switch and prohibited-action
decisions take precedence; unknown actions fail closed. LLM output is data, never
a policy decision.

### Action worker

Consumes authorized commands only, revalidates parameters and policy context,
uses an idempotency key, initially calls simulated adapters, and records outcomes.

## Data and event strategy

PostgreSQL is the authoritative operational store. Kafka carries versioned facts
and commands. Producers assign globally unique `eventId` values. Consumers store
processed IDs under a uniqueness constraint in the same transaction as business
changes, then commit Kafka offsets. Commands also carry domain idempotency keys.
The transactional outbox prevents database/event divergence.

SQL Server remains a future read-only legacy adapter. Qdrant is deferred until
versioned SOP retrieval is implemented. Redis is added only for a demonstrated
caching, rate-limiting, or coordination requirement.

## Security and observability

Non-local database connections require certificate verification; Kafka requires
encrypted transport. Authentication, RBAC, secret management, input redaction,
retention, and tamper-evident audit controls are phased in before production.

Langfuse, OpenTelemetry, Prometheus, and Grafana enter with the first governed
workflow in Milestone 1. Langfuse is for AI diagnostics and evaluation, not the
authoritative compliance audit.

## Current versus planned

Milestones 0 and 1A implement the application, persistence, configuration, and
contract foundations plus Kafka telemetry consumption, deterministic breach
detection, incident evidence, non-authoritative recommendations, governance,
dispatcher approval, idempotent simulated actions, and the hash-linked audit
timeline. Enriched weather/SOP investigation, governed LLM recommendations,
production identity, observability integrations, real action adapters, and the
dispatcher UI remain planned.
