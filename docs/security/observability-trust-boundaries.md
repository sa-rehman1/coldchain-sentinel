# Observability trust boundaries

Prometheus, Grafana, and Jaeger are display and diagnostic systems, never control-plane authorities.
Their absence or compromise cannot approve a recommendation or execute a command. Deterministic
policy and governance remain authoritative, and `HOLD_SHIPMENT` still requires an authenticated
dispatcher decision before the simulated adapter can run.

Metrics use fixed labels and exclude identifiers. Logs emit a field allowlist and redact credential
shapes; unrestricted exceptions, headers, prompts, SOP bodies, provider responses, and database URLs
are not serialized. Traces use a separate safe-attribute allowlist. Grafana's anonymous viewer is
acceptable only because its port is bound to localhost in this local demo; it is not a production
authentication design.

The pinned Jaeger v1 all-in-one image is end-of-life and therefore restricted to localhost demo
use with in-memory data. It must not be promoted to a shared or production environment.

Persistent observability volumes contain only local metrics and dashboard state. Jaeger uses memory.
Never place secrets in labels, annotations, dashboard variables, evaluation fixtures, or Compose
configuration.
