# Groq development setup

1. Create an API key yourself in the Groq console.
2. Put it only in the ignored local `.env` as `GROQ_API_KEY`; never paste it into chat or commit it.
3. Keep `LLM_MODEL=openai/gpt-oss-20b` and `LLM_BILLING_MODE=free_tier` for this development configuration.
4. Set `LLM_LIVE_CALLS_ENABLED=true` only for the bounded demo or marked smoke test.
5. Disable live calls immediately afterward.

The application and full default test suite work without the key. Never print environment values. The smoke test requires both `RUN_LIVE_GROQ_SMOKE=true` and the key and makes at most one small request.
