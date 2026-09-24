# Milestone 1A: governed temperature-breach slice

> Historical implementation record. See the [target architecture](target-architecture.md) for the current system.

## Runtime flow

`TelemetryEvent` is accepted by the API, validated, and published to `coldchain.telemetry.v1` with the shipment identifier as its Kafka key. The manual-commit worker validates the message again, evaluates the versioned fresh/perishable policy, and writes telemetry, incident, evidence, recommendation, governance, and audit records in one PostgreSQL transaction. Only then is the Kafka offset committed.

Invalid contracts are wrapped in `FailureEnvelope` v1 and published to `coldchain.telemetry.dlq.v1`. Infrastructure or transaction failures do not advance the source offset, allowing safe retry. The source event UUID is the persistence idempotency boundary, so redelivery cannot create another incident.

The deterministic local provider returns an evidence-linked, expiring `HOLD_SHIPMENT` recommendation explicitly marked as non-authoritative. Deterministic governance classifies that action as approval-required. A local-only identity adapter accepts explicit actor and role headers in local/test environments and fails closed elsewhere.

After an authenticated dispatcher approves, the repository atomically records the decision and unique command. The client supplies an idempotency key of 16–200 characters. Its deterministic approval identifier, the unique recommendation decision, the unique command key, and the unique action-result constraint form database-enforced replay boundaries. An exact replay returns the original approval, command, and durable action result without adding audit events. Reusing the key with different incident, recommendation, actor, decision, or rationale returns HTTP 409. A replay that finds a committed command without a result safely resumes that same command through the idempotent adapter.

The simulated adapter is idempotent on the command key. Completion resolves the incident and appends the final audit event. Rejection creates no command. Decisions are final: neither an approval nor a rejection can be reversed, and expired recommendations, self-approval, missing dispatcher authority, and non-permitting governance all fail closed.

## Trust boundaries

- Domain and policy code import no web, persistence, messaging, or vendor SDKs.
- Recommendation generation cannot execute actions.
- Governance is deterministic and runs after recommendation generation.
- Human identity and dispatcher authorization are checked before command creation.
- Approval, command, action-result, and consumed-event uniqueness are database-enforced.
- Audit records are ordered, hash-linked, and protected by an append-only database trigger.
- Secrets and connection strings are never included in timeline payloads or structured logs.

## Deliberate limits

The action adapter does not contact a carrier or warehouse system. A production adapter must honor the same idempotency-key contract at its external boundary. The identity provider is for local/test use only. Weather and SOP evidence providers, an LLM-backed recommender, production IAM, observability products, and user-interface work remain later milestones.
