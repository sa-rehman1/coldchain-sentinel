# ADR 0007: OpenAI-compatible recommendation boundary

Status: accepted, 2026-09-19.

Use a provider-neutral HTTP boundary implementing the OpenAI chat-completions shape and strict JSON Schema output. Configuration supplies provider, base URL, key environment variable, model, timeouts, token limit, temperature, live-call flag, and billing mode. This avoids a Groq SDK dependency and permits a future official OpenAI endpoint without domain changes. One bounded retry and a circuit breaker limit failure amplification.
