# Milestone 2B local demonstration

Start the integrated local demo with external AI disabled:

```powershell
$env:LLM_LIVE_CALLS_ENABLED='false'
docker compose --profile demo up -d --build --wait
```

Open `http://127.0.0.1:4173`, confirm the header says `Local demo · API`, and select
`Dispatcher` under `Local demonstration identity`. In Demo Lab, start **Sustained temperature
breach**. The progress display advances only when the API reports durable worker state. Open the
created incident, inspect telemetry, trusted SOP citation identifiers, deterministic-fallback
provenance, governance, and the audit trail. Enter a reviewer rationale and approve the hold. The
refreshed investigation shows the single durable command and simulated action result. Repeating the
same uncertain submission uses the same browser-held idempotency key and returns the original result.

Use the healthy scenario to demonstrate that in-range telemetry creates no unsafe action. Change the
local identity to `Read-only Auditor` to demonstrate server-side rejection. Rejection records a final
decision without creating a command. Observability links remain local and show `Unavailable` rather
than fixture metrics when a source is absent.

The demo does not enable or call Groq or OpenAI, download an embedding model, reset a database, or
delete Docker resources.
