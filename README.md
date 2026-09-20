# ColdChain Sentinel

ColdChain Sentinel is becoming a governed Python operations platform for
temperature-sensitive shipments. It will ingest telemetry, detect deterministic
anomalies, collect bounded evidence, produce non-authoritative AI recommendations,
require policy-driven human approval, and execute only authorized actions.

## Current status

Milestone 0 provides the secure, reproducible foundation, and Milestone 1A adds a governed temperature-breach vertical slice:

- a modular Python package and FastAPI application factory;
- liveness and database-backed readiness endpoints;
- typed settings, JSON logs, correlation IDs, and consistent errors;
- async SQLAlchemy and Alembic foundations for PostgreSQL;
- versioned JSON Schema contracts and example messages;
- deterministic governance decisions and a kill switch;
- pinned local PostgreSQL and Kafka KRaft infrastructure;
- linting, type checking, tests, coverage, and CI.
- a manual-commit Kafka telemetry worker with a versioned dead-letter envelope;
- deterministic breach detection, local recommendations, governance, and dispatcher approval;
- idempotent simulated commands and a hash-linked, append-only incident timeline.

Weather/SOP evidence providers, a governed LLM provider, production identity,
and the dispatcher control-tower UI remain planned work.

## Requirements

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) 0.8 or later
- Docker Desktop with Docker Compose for local PostgreSQL and Kafka

## Python setup and validation

```powershell
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python scripts/export_contract_schemas.py
uv run alembic upgrade head --sql
```

`uv.lock` is committed. CI and local development use `--locked`/`--frozen` so a
dependency change cannot be introduced without an explicit lock update.

## Run the API without containers

Copy the safe template and set a valid PostgreSQL URL if readiness should pass:

```powershell
Copy-Item .env.example .env
uv run uvicorn coldchain.api.app:create_app --factory --reload
```

- Liveness: `http://localhost:8000/api/v1/health/live`
- Readiness: `http://localhost:8000/api/v1/health/ready`
- OpenAPI: `http://localhost:8000/docs`

Liveness works without external services. Readiness returns `503` until the
configured PostgreSQL database accepts a verified query.

## Run the local stack

The template values are deliberately local-only placeholders:

```powershell
Copy-Item .env.example .env
docker compose --env-file .env config -q
docker compose --env-file .env up -d --build --wait
curl.exe http://localhost:8000/api/v1/health/ready
```

Local ports are `8000` for the API, `5432` for PostgreSQL, and `9092` for Kafka.
Kafka runs in single-node KRaft mode and `kafka-init` creates
`coldchain.telemetry.v1` and `coldchain.telemetry.dlq.v1`. The one-shot migration
service applies Alembic before the API and worker start. Named volumes retain local database and Kafka data.
Plaintext local transport is not approved for staging or production.

Stop containers without deleting their named volumes:

```powershell
docker compose --env-file .env stop
```

## Milestone 1A demo

With the local stack healthy, run the deterministic unsafe-temperature scenario:

```powershell
uv run --no-sync python scripts/run_temperature_breach_demo.py
```

The equivalent request-by-request walkthrough is in
`docs/demo/milestone-1a-walkthrough.ps1`, and the expected eight-event audit
sequence is documented in `docs/demo/expected-incident-timeline.md`. Local/test
approval uses explicit `X-Actor-ID` and `X-Actor-Roles` headers; this identity
adapter fails closed in staging and production. Approval and rejection bodies also
require a stable `idempotencyKey` (16–200 characters). Exact retries return the
original decision and result; conflicting reuse returns HTTP 409.

## Contracts

Contract examples live under `contracts/examples` and their committed JSON Schema
snapshots live under `contracts/schemas`. After changing a Pydantic contract, run
the exporter and tests. Breaking changes require a new schema version and Kafka
topic compatibility review.

## Documentation

- [Target architecture](docs/architecture/target-architecture.md)
- [Phased roadmap](docs/roadmap.md)
- [Architecture decisions](docs/adr/)

## Security

Never commit `.env` files, credentials, private keys, or production connection
strings. Non-local configuration requires verified PostgreSQL TLS and encrypted
Kafka transport. AI recommendations are evidence-bearing proposals and are never
authorization to execute an operational action.
