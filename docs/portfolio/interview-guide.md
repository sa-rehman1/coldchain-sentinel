# Interview and recruiter guide

## Core explanations

**30 seconds:** ColdChain Sentinel is a local governed-AI control tower for synthetic cold-chain incidents. It combines Kafka telemetry, deterministic breach policy, PostgreSQL evidence, Qdrant SOP retrieval, bounded AI recommendations, human approval, idempotent simulated actions, and end-to-end observability.

**90 seconds:** A Kafka worker turns versioned temperature readings into durable incidents and immutable evidence. It retrieves effective SOP chunks from Qdrant and obtains either deterministic advice or an optional strict provider response. Local validation checks actions, schema, citations, evidence, expiry, and provenance. Deterministic governance—not the model—decides whether approval is required. An authorized dispatcher can approve once using an idempotency key, producing one simulated command and a hash-linked audit trail. React exposes the lifecycle; Prometheus, Grafana, OpenTelemetry, and Jaeger expose bounded operational signals.

**Three minutes:** Walk through telemetry → policy → evidence → retrieval → recommendation → validation → governance → approval → command → simulated result → audit. Emphasize the separate trust boundaries, fallback behavior, server-only keys, strict contracts, same-origin frontend API, and truthful local limitations.

**Non-technical:** It is a safety-focused dashboard for temperature-sensitive deliveries. Software gathers the facts and procedures, AI may suggest what to do, fixed rules check the suggestion, and a responsible person makes the final decision.

## System-design walkthrough and tradeoffs

- **Kafka:** decouples ingestion from processing and demonstrates ordering, consumer groups, manual commits, and dead-letter handling. It adds operational complexity that would be unnecessary for a tiny synchronous application.
- **PostgreSQL:** authoritative relational workflow state, transactions, constraints, and audit queries. It is not used as an event broker.
- **Qdrant:** vector retrieval plus payload filtering for effective/superseded SOP versions. Deterministic embeddings keep the local demo offline.
- **Redis:** intentionally not used. Current idempotency and state live durably in PostgreSQL; adding Redis would duplicate state without a demonstrated need.
- **FastAPI/Pydantic:** typed async boundaries, generated OpenAPI, dependency injection, strict validation, and clear error envelopes.
- **React/TypeScript/Zod:** operational UI with compile-time types plus runtime validation of untrusted API responses.
- **Prometheus/Grafana:** bounded operational metrics and local dashboards.
- **OpenTelemetry/Jaeger:** cross-service correlation across HTTP and Kafka without storing sensitive payloads.
- **Provider-neutral AI:** deterministic, Groq, and optional OpenAI share one contract; provider changes do not alter governance.
- **Human-in-the-loop:** meaningful because identity, expiry, rationale, idempotency, command creation, and audit are enforced server-side.

## Failure scenarios

Provider failures, invalid schema, unknown citations, insufficient evidence, stale telemetry, duplicates, unauthorized approvals, expired recommendations, conflicting idempotency reuse, and an active kill switch all fail closed or fall back deterministically. The UI shows unavailable state rather than silently using fixtures in API mode.

## What is simulated

Telemetry and identities are synthetic; the action adapter records a simulated shipment hold. Infrastructure is single-node and localhost-only. No carrier, warehouse, customer, or production provider account is integrated.

## What changes for production

Add enterprise IAM/RBAC, managed secrets, TLS/network policy, real telemetry/TMS adapters, transactional outbox/inbox patterns, data classification and retention, immutable audit storage, capacity/chaos/recovery testing, SLOs, backups, HA/DR, provider governance, and regulated validation.

## Likely interview questions

1. **Why not let the model decide?** Consequential authority needs deterministic, testable policy and accountable authorization; model output remains advisory.
2. **What prevents hallucinated citations?** Returned identifiers must be subsets of the retrieved SOP and incident-evidence allowlists.
3. **How do you prevent prompt injection?** Retrieved text is delimited as untrusted, model actions are closed enums, unsafe phrases are rejected, and deterministic governance re-evaluates output.
4. **What happens when the provider is down?** Bounded retries/circuit breaking end in deterministic fallback; the workflow remains usable.
5. **Why Kafka?** It demonstrates asynchronous telemetry processing, consumer semantics, replay boundaries, and DLQ handling.
6. **Why PostgreSQL rather than only Kafka?** Operators need transactional, queryable authoritative state for decisions, commands, and audit relationships.
7. **Why Qdrant?** It supports vector search and metadata filters for versioned SOP chunks.
8. **Why deterministic embeddings?** They make tests and the default demo reproducible, offline, and cost-free.
9. **Why no Redis?** There is no justified ephemeral-state or caching requirement; PostgreSQL already owns durable idempotency.
10. **How does idempotency work?** A stable key binds to decision content; exact replay returns the original result and conflicting reuse fails.
11. **Can the AI execute a command?** No. Only an authorized approved recommendation can cross the command boundary.
12. **What does the kill switch do?** It takes precedence in deterministic governance and blocks operational command creation.
13. **How are secrets protected?** Keys are server-side, ignored locally, absent from frontend bundles, and excluded from logs and traces.
14. **How is provenance trusted?** Application code creates identity, prompt hash, timestamps, expiry, correlation, token, and validation metadata.
15. **What is observable?** Bounded outcomes, durations, health, and trace relationships—not prompts, SOP text, credentials, or payloads.
16. **How do you handle stale or duplicate telemetry?** Deterministic policy and repository constraints classify or suppress it; scenarios verify behavior.
17. **How do frontend failures behave?** API mode surfaces unavailable/schema errors and never substitutes mock incidents.
18. **What tests matter most?** Workflow/governance tests, mocked provider failures, schema drift, integration boundaries, accessibility, and deterministic evaluations.
19. **Is the audit log immutable?** It is append-only and hash-linked in the demo; production needs stronger immutable storage and retention controls.
20. **Did this process real shipments?** No. All scenarios and identities are synthetic, and execution is simulated.
21. **Why support multiple providers?** It prevents domain coupling and lets cost/availability change without changing authority boundaries.
22. **What would you optimize first?** Measure real workload needs before caching; prioritize transactional delivery, IAM, recovery, and data governance.
23. **How do you prevent duplicate external actions?** The command and adapter boundary must carry the same idempotency contract; the local adapter demonstrates this behavior.
24. **What is the strongest architectural choice?** Authority is encoded structurally: recommendation, policy, approval, command, and action are distinct states.
