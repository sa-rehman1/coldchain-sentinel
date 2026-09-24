# Screenshot plan

Do not capture credentials, `.env`, terminal history, browser extensions, personal bookmarks, provider consoles, database connection strings, or real names. Use fictional demo data and a clean 1440 × 900 browser window at 100% zoom.

| Priority | Route and state | Must be visible | Filename | Later placement |
|---:|---|---|---|---|
| 1 | `/` after a sustained-breach run | Command Center header, critical incident, operational summary, service health | `coldchain-command-center.png` | README hero and portfolio card |
| 2 | `/investigation/:incidentId` before approval | Temperature excursion, shipment context, trusted evidence identifiers, recommendation | `coldchain-investigation-evidence.png` | README workflow and blog evidence section |
| 3 | `/investigation/:incidentId` governance section | Validation checks, `APPROVAL_REQUIRED`, human decision controls, no executed command yet | `coldchain-governed-approval.png` | README governance and blog human-authority section |
| 4 | Same investigation after approval | Final approval, one command, simulated action result, audit timeline | `coldchain-audit-outcome.png` | Blog audit/idempotency section |
| 5 | `/observability` with local services healthy | Bounded metrics summary plus Grafana/Jaeger links; no payload content | `coldchain-observability.png` | README observability section and blog |
| 6 | `/demo-lab` | Scenario catalog including fallback, injection, expiry, unauthorized, and kill switch | `coldchain-demo-lab.png` | README evaluation section |

Before publishing, inspect every image at full resolution and remove metadata if the capture tool embeds account or device information.
