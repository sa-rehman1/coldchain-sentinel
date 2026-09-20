$ErrorActionPreference = "Stop"

# Inspect running projects and port ownership before starting anything.
docker compose ls
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 6333,8000,9092,5432

# Start only after reviewing those results and local .env values.
docker compose --env-file .env up -d --build --wait
uv run python scripts/ingest_sop.py

# Safe status contains no key and triggers no model call.
Invoke-RestMethod http://localhost:8000/api/v1/health/ai

# Deterministic fallback demonstration: leave LLM_LIVE_CALLS_ENABLED=false,
# run the Milestone 1A breach flow, and inspect recommendation provenance.
Write-Host "Live model calls remain disabled; fallback preserves dispatcher approval."

# Optional live smoke test is a separate deliberate command after manual key setup:
# $env:RUN_LIVE_GROQ_SMOKE = "true"
# $env:LLM_LIVE_CALLS_ENABLED = "true"
# uv run pytest -m live_groq tests/live/test_groq_smoke.py -q
# Remove-Item Env:RUN_LIVE_GROQ_SMOKE
# Remove-Item Env:LLM_LIVE_CALLS_ENABLED
