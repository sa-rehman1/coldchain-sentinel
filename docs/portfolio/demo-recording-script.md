# Demo recording script — 5 to 7 minutes

## Pre-recording checklist

- Use a 1440 × 900 or 1920 × 1080 browser window at 100% zoom.
- Close email, chat, password managers, terminals containing environment output, and unrelated tabs.
- Confirm `.env` is ignored, `LLM_PROVIDER=deterministic`, and `LLM_LIVE_CALLS_ENABLED=false`.
- Run `.\scripts\demo.ps1 -Action Start -Observability` and confirm every printed URL opens.
- Select the **Dispatcher** local identity and run one sustained-breach scenario before recording if a known incident is preferred.
- Keep the recording path deterministic. Optional Groq is a bonus, never a dependency.

## Recording plan

| Time | Click / show | What to say | What it proves |
|---:|---|---|---|
| 0:00–0:35 | Command Center `/` | “A cold-chain alert is not enough. Operators need trusted evidence, the applicable procedure, policy enforcement, and an accountable decision.” | Business framing and operational focus |
| 0:35–1:00 | Summary metrics and service health | “This is an integrated local control tower backed by FastAPI, Kafka, PostgreSQL, and Qdrant—not a static dashboard.” | End-to-end integration and truthful local scope |
| 1:00–1:25 | Incident Queue `/incidents` | “Incidents are prioritized from authoritative API state. API mode never silently substitutes fixtures.” | Durable state and honest failure behavior |
| 1:25–2:05 | Open an investigation; show temperature chart | “The worker applies a deterministic breach policy and freezes the readings and policy inputs into an immutable evidence snapshot.” | Deterministic detection and evidence integrity |
| 2:05–2:35 | Trusted SOP evidence | “Only effective, authored ColdChain Sentinel SOP chunks are retrieved. Model citations must resolve to retrieved identifiers.” | Grounded retrieval and citation allowlists |
| 2:35–3:10 | Recommendation panel | “The provider can choose only eight advisory fields. The application owns expiry, provenance, prompt hash, timing, and validation.” | Bounded AI and trusted metadata |
| 3:10–3:40 | Governance checks / Governed AI route | “The model recommends; deterministic policy decides whether the action is allowed, prohibited, or requires approval.” | Separation of AI and policy authority |
| 3:40–4:20 | Enter rationale and approve | “An authorized dispatcher makes the consequential decision. The idempotency key prevents duplicate commands.” | Human-in-the-loop and idempotency |
| 4:20–4:45 | Command/action result | “Approval creates one command. The adapter is intentionally simulated; no carrier or warehouse is contacted.” | Controlled execution and honest limitation |
| 4:45–5:15 | Audit timeline | “Every transition records actor, correlation, causation, versions, and a hash link to the prior event.” | Auditability and traceability |
| 5:15–5:45 | Observability `/observability`, then Grafana/Jaeger | “Metrics use bounded labels, traces propagate context, and logs exclude prompts, SOP text, credentials, and payloads.” | Operational visibility with privacy controls |
| 5:45–6:15 | Demo Lab `/demo-lab` | “Scenarios exercise healthy, breach, stale, duplicate, injection, fallback, expiry, unauthorized, and kill-switch behavior.” | Failure-oriented evaluation |
| 6:15–6:45 | README architecture diagram | “Kafka carries events, PostgreSQL owns workflow state, Qdrant supplies trusted procedures, and React exposes the governed lifecycle.” | System-design clarity |
| 6:45–7:00 | Return to Command Center | “ColdChain Sentinel shows how to use AI inside an accountable operational system: recommendations are useful, but policy and people stay in control.” | Closing value proposition |

## Recovery plan

If optional Groq fails, do not retry during the recording. State that external providers are optional, stop the Groq-enabled stack, and restart with `.\scripts\demo.ps1 -Action Start -Observability`. The deterministic fallback preserves the complete workflow, including governance, approval, simulated execution, and auditability.
