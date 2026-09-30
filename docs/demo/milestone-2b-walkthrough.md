# Integrated local demonstration

Start the integrated deterministic demo. The launcher validates configuration, starts Compose,
applies migrations through the existing one-shot service, loads the SOP corpus, waits for health,
and prints the local URLs:

```powershell
.\scripts\demo.ps1 -Action Start -Observability
```

Open `http://127.0.0.1:4173`, confirm the header says `Local demo · API`, and select
`Dispatcher`. The Command Center is populated by the idempotent `showcase-seed` service and reads
only its stable fictional shipment namespace. Existing integration and ad-hoc demo records remain
stored but are excluded from this portfolio view. In Demo Lab, start **Sustained temperature
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

To refresh only the canonical showcase timestamps and values without deleting unrelated data, run:

```powershell
docker compose --env-file .env --profile demo run --rm showcase-seed
```

The stable shipment, telemetry, incident, evidence, recommendation, and governance identifiers make
the preparation idempotent. It creates no approval or operational command.

Validate an already-running stack with `.\scripts\demo.ps1 -Action Validate -Observability`. Stop
it safely with `.\scripts\demo.ps1 -Action Stop -Observability`; this preserves containers,
volumes, and data. Optional Groq requires the explicit `-EnableGroq` switch and is never required
for a successful walkthrough. OpenAI is never enabled by the launcher.
