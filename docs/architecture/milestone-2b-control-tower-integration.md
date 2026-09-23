# Milestone 2B: real control-tower integration

The React control tower keeps its typed `ControlTowerDataSource` boundary. `mock` mode is reserved
for isolated visual development and deterministic screenshots; the Compose demo builds in `api`
mode. API mode uses one same-origin client, strict Zod response validation, bounded timeouts,
correlation headers, cancellation, one retry for safe reads, and no mutation retry. It never falls
back to fixtures.

The existing incident tables remain authoritative. Incident reads aggregate telemetry, immutable
evidence, recommendation provenance, deterministic governance, the final human decision, command,
simulated action result, and the hash-linked audit timeline. No database migration is required.

The local-only `/api/v1/demo` boundary publishes synthetic telemetry through the normal Kafka
publisher. It is hidden unless demo mode is enabled in a local or test environment and requires an
explicit local identity. It never writes workflow records directly. Worker processing, SOP retrieval
from Qdrant, deterministic fallback, governance, approval, idempotent command creation, and the
simulated action adapter remain the only path to durable state.

The containerized frontend is served by an unprivileged Nginx process. `/api/` is reverse-proxied to
FastAPI, so no database, Kafka, Qdrant, credential, or internal service URL reaches the browser.
All published ports bind to localhost.
