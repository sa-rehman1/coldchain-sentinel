# ADR 0008: Groq free-tier development provider

Status: accepted, 2026-09-19.

Development may use Groq at `https://api.groq.com/openai/v1` with `openai/gpt-oss-20b`. Calls require both a locally supplied `GROQ_API_KEY` and `LLM_LIVE_CALLS_ENABLED=true`; defaults disable calls. Each demo incident permits at most one attempt. A zero cost estimate means “configured free-tier mode,” not independently verified billing. Production provider selection remains open.
