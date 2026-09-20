# ADR 0003: JSON Schema event contracts

- Status: Accepted
- Date: 2026-09-19

## Context

JSON Schema, Avro, and Protobuf all support Kafka workflows. Avro has strong schema
registry conventions but adds a serialization toolchain. Protobuf is compact and
strongly typed but is less natural for browser/operator integrations. JSON Schema
matches FastAPI/Pydantic and keeps early event inspection straightforward.

## Decision

Use JSON messages governed by committed draft-2020-12 JSON Schema snapshots.
Pydantic models are the authoring source. Every message carries `schemaVersion`;
examples are validated in tests. Compatibility rules are backward-compatible
additions within a version and a new version for breaking changes. A schema
registry will enforce compatibility when shared Kafka infrastructure is added.

## Consequences

Messages are larger than binary encodings and governance discipline is required.
The current choice optimizes delivery and inspectability without preventing a
future migration if throughput measurements justify one.
