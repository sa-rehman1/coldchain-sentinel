# Read-only/local demo commands. No model calls are enabled by this script.
$ErrorActionPreference = "Stop"
$env:COLDCHAIN_OTEL_TRACING_ENABLED = "true"

docker compose --project-name coldchain-sentinel-independent-m1c --profile observability `
  --env-file .env up -d --build --wait

uv run python scripts/run_evaluations.py

Write-Host "Grafana:    http://localhost:13001"
Write-Host "Prometheus: http://localhost:19090"
Write-Host "Jaeger:     http://localhost:16687"
Write-Host "Generate synthetic telemetry through the existing API, inspect the dashboards, then approve"
Write-Host "a HOLD_SHIPMENT as a dispatcher to demonstrate that governance remains authoritative."
