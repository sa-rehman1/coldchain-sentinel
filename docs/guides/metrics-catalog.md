# Metrics catalog

All names use the `coldchain_` namespace. Counters are exposed with Prometheus's `_total` suffix.
No event, shipment, incident, command, correlation, trace, span, user, exception-message, prompt,
or document identifier is permitted as a label.

| Area | Metrics | Bounded labels |
|---|---|---|
| API | `api_requests`, `api_request_duration_seconds`, `api_active_requests` | method, normalized route, status class |
| Worker | `worker_events`, `worker_processing_duration_seconds` | outcome |
| Incidents | `incidents_created`, `incidents_current`, `incident_state_transition_failures` | breach type, severity, state, reason |
| Retrieval | `retrieval_duration_seconds`, `retrieval_chunks_returned`, `retrieval_outcomes` | outcome |
| Recommendation | `recommendations`, `recommendation_fallback`, `provider_duration_seconds`, `provider_tokens`, `provider_configured_cost_estimate` | provider, configured model, validation result, direction, reason |
| Governance | `governance_decisions`, `governance_fail_closed`, `approval_decisions`, `recommendations_expired`, `kill_switch_blocks` | decision, reason |
| Actions | `commands_created`, `simulated_actions` | action, outcome |
| Errors | `structured_errors` | component, allowlisted error type |

Unknown dynamic values map to `other`. The cost metric is explicitly a configured estimate and is
not a billing record. API metrics are available at `/metrics`; worker metrics use port 9100 inside
Compose and localhost port 18005 by default.
