# Expected Milestone 1A incident timeline

The deterministic unsafe-temperature scenario produces these hash-linked events in order:

1. `TELEMETRY_RECEIVED` — validated `TelemetryEvent` and correlation identifier.
2. `BREACH_POLICY_EVALUATED` — exact policy version, inputs, reason codes, and outcome.
3. `EVIDENCE_SNAPSHOT_CREATED` — immutable content hash and evidence summary.
4. `RECOMMENDATION_CREATED` — local provider identity, expiry, evidence linkage, and non-authoritative marker.
5. `GOVERNANCE_EVALUATED` — `APPROVAL_REQUIRED`, policy version, inputs, and reason codes.
6. `HUMAN_DECISION_RECORDED` — dispatcher identity, role, rationale, and approval identifier.
7. `COMMAND_CREATED` — action type, command identifier, and idempotency key.
8. `SIMULATED_ACTION_COMPLETED` — adapter identity and `SUCCEEDED` result.

Each entry contains correlation and causation identifiers, component/schema versions, its own SHA-256 hash, and the previous entry's hash. PostgreSQL rejects updates and deletes against the audit table.

Replaying the approval request with the same actor, decision, rationale, and `idempotencyKey` returns the same approval, command, and action result. The timeline remains at eight entries. Conflicting reuse of that key returns HTTP 409.
