# Milestone 1B data flow and trust boundaries

1. Kafka telemetry enters as untrusted input and is contract-validated.
2. Deterministic breach policy creates incident facts and immutable evidence.
3. The embedding provider converts bounded text; it has no authority.
4. Qdrant returns candidate SOP chunks; results are untrusted evidence, filtered by effective and superseded dates.
5. The model receives system restrictions, validated facts, deterministic policy result, delimited SOP context, and JSON Schema. Its response is untrusted.
6. Schema and citation validation produce a candidate recommendation or select fallback.
7. Deterministic governance independently evaluates expiry, action, citations, evidence, kill switch, and approval requirements.
8. PostgreSQL stores validated output and safe provenance. API responses expose only safe fields.
9. Only authenticated dispatcher approval can create a hold command; the simulated adapter remains idempotent.
