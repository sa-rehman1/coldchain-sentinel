# ADR 0005: uv dependency management

- Status: Accepted
- Date: 2026-09-19

## Decision

Declare runtime dependencies in PEP 621 `project.dependencies`, development tools
in a `dev` dependency group, and commit the universal `uv.lock`. Use `uv sync
--locked --all-groups` locally and `uv sync --frozen --all-groups` in CI.

## Consequences

Resolution is deterministic and fast, production images can omit development
tools, and dependency edits visibly change both the declaration and lock.
