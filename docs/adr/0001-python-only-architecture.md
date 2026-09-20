# ADR 0001: Python-only architecture

- Status: Accepted
- Date: 2026-09-19

## Context

The platform requires operational APIs, event workers, AI orchestration, retrieval,
data processing, and integrations. No client or organizational constraint requires
a second application runtime.

## Decision

Use Python 3.12 for the control plane and workers. Do not introduce Java, Spring
Boot, Maven, or Gradle. Engineering depth will come from governance, reliability,
security, event processing, auditability, testing, and observability.

## Consequences

The team operates one language ecosystem and can share typed contracts and domain
logic. Architectural boundaries and independent entrypoints remain mandatory so
the platform does not collapse into a monolithic interactive application.
