# ADR 0006: deterministic local recommendation provider

## Status

Accepted for Milestone 1A.

## Decision

The recommendation boundary is a provider-neutral Python protocol. Milestone 1A uses `DeterministicLocalRecommendationProvider`, which produces a typed, evidence-linked, 30-minute `HOLD_SHIPMENT` recommendation without network access. Its author identity is a system identity distinct from dispatchers, and every result states that it is not authorization.

Recommendation output always passes through deterministic governance and human approval before command creation. Providers have no action-adapter reference and cannot execute commands.

## Consequences

The complete demonstration is reproducible, offline, and free of paid API dependencies. A later LLM provider can implement the same interface, but must retain typed validation, evidence references, expiry, author identity, governance evaluation, self-approval prevention, and the non-authoritative contract.
