# Resume and portfolio material

## Resume bullets — exactly four

- Engineered a governed-AI cold-chain control tower with FastAPI, React/TypeScript, Kafka, PostgreSQL, and Qdrant, converting synthetic telemetry into evidence-backed, auditable incident workflows.
- Designed a provider-neutral recommendation boundary with strict structured output, citation allowlists, trusted provenance, bounded retries/circuit breaking, and deterministic fallback across local, Groq, and offline-tested OpenAI configurations.
- Enforced human-in-the-loop safety through versioned deterministic governance, kill-switch precedence, role-checked approval, idempotent command creation, simulated execution, and a hash-linked audit timeline.
- Delivered reproducible quality gates with 109 passing non-live backend tests at 87.09% coverage, 50 frontend/accessibility tests, and 16/16 deterministic evaluation scenarios, plus Prometheus/Grafana and OpenTelemetry/Jaeger observability.

## Two-line resume description

Built a local governed-AI operations platform for synthetic temperature-sensitive shipment incidents. Combined trusted SOP retrieval and bounded recommendations with deterministic policy, human approval, idempotent actions, auditability, and full-stack observability.

## GitHub description

Governed AI cold-chain control tower with deterministic policy enforcement, trusted SOP retrieval, human approval, and end-to-end observability.

## LinkedIn project description

ColdChain Sentinel is a portfolio-scale control tower that processes synthetic cold-chain telemetry through Kafka, persists evidence and incident state in PostgreSQL, retrieves versioned SOPs from Qdrant, and produces bounded AI recommendations. Deterministic governance and an authorized human—not the model—control command creation. The React interface exposes the complete workflow, with Prometheus/Grafana and OpenTelemetry/Jaeger for local observability.

## LinkedIn launch post draft

I built **ColdChain Sentinel** to explore a question beyond “Can an LLM produce a useful answer?”: **Can an operational system prove the evidence, enforce policy independently, keep a human accountable, and fail safely?**

The local project combines React, FastAPI, Kafka, PostgreSQL, Qdrant, deterministic governance, strict provider output, human approval, idempotent simulated actions, and end-to-end observability. AI is deliberately non-authoritative: it recommends, policy decides, and a human authorizes.

Development validation includes 109 passing non-live backend tests at 87.09% coverage, 50 frontend/accessibility tests, and 16/16 deterministic evaluation scenarios. All data and actions are synthetic; this is a portfolio system, not a production deployment.

## Portfolio-card summary

An evidence-first cold-chain operations demo where AI recommendations are constrained by strict schemas and trusted citations, deterministic policy remains authoritative, and humans approve consequential actions.

## Suggested GitHub topics

`governed-ai`, `human-in-the-loop`, `fastapi`, `react`, `typescript`, `kafka`, `postgresql`, `qdrant`, `rag`, `prometheus`, `grafana`, `opentelemetry`, `ai-agents`, `supply-chain`, `portfolio-project`

## Key technologies and verified results

Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, React 19, TypeScript 6, Kafka 3.9, PostgreSQL 16, Qdrant 1.19, Prometheus, Grafana, OpenTelemetry, Jaeger, Docker Compose, uv, Vitest, pytest, mypy, Ruff, ESLint, Zod, and jest-axe.

Verified locally: 109 non-live backend tests; 87.09% coverage; 50 frontend/accessibility tests; 16/16 deterministic evaluations; one controlled Groq validation; zero OpenAI live requests. These are development-validation results, not production usage metrics.
