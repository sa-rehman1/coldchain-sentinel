# Milestone 1B: Governed AI Recommendations with SOP Retrieval

> Historical implementation record. See the [target architecture](target-architecture.md) for the current system.

Milestone 1B adds an evidence-producing AI path without moving authority out of deterministic governance. The worker creates immutable incident evidence, retrieval selects effective non-superseded SOP chunks, and an OpenAI-compatible provider may return a strict recommendation. Schema, citation, expiry, evidence, provider, and policy checks run before governance. Any failure selects the deterministic recommendation provider; `HOLD_SHIPMENT` still requires dispatcher approval.

The provider boundary is configured by `LLM_*` settings. Groq is the development endpoint; domain, retrieval, persistence, governance, and APIs contain no Groq-specific types. No model call occurs during startup, health checks, ingestion, default tests, or ordinary Compose startup.

Stored provenance is limited to provider/model identifiers, prompt/schema/corpus versions and hashes, citations, correlation/request IDs, timestamps, latency, token counts, configured billing-mode estimate, retry/fallback/validation results, uncertainty, sufficiency, and expiry. Secrets, authorization headers, raw prompts, hidden reasoning, and unrestricted provider responses are excluded.
