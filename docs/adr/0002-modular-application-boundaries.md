# ADR 0002: Modular application with process entrypoints

- Status: Accepted
- Date: 2026-09-19

## Decision

Begin with one modular Python package and separate API/worker entrypoints. Use
inward dependencies: transport and infrastructure depend on application/domain
ports. The domain imports no FastAPI, Kafka, SQLAlchemy, LangGraph, or vendor SDK.

## Consequences

This avoids premature distributed-system overhead while keeping processes
independently testable and deployable. A module may become a service only after a
measured scaling, isolation, ownership, or availability requirement appears.
