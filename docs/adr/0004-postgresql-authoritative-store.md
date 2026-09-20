# ADR 0004: PostgreSQL as authoritative operational store

- Status: Accepted
- Date: 2026-09-19

## Decision

Use PostgreSQL for shipments, incidents, recommendations, approvals, action
commands, audit events, idempotency records, and the transactional outbox. Access
it asynchronously through SQLAlchemy 2.x and evolve it exclusively with Alembic.

SQL Server is retained later as a read-only legacy adapter, not as the platform's
system of record.

## Consequences

PostgreSQL provides mature transactions, constraints, JSON support, operational
tooling, and outbox support. Production connections must verify server identity;
local plaintext development is explicitly isolated and non-production.
