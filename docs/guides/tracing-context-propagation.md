# Tracing and context propagation

The API and worker emit OTLP/HTTP spans only when `COLDCHAIN_OTEL_TRACING_ENABLED=true`. The
default is false. The configured exporter timeout is two seconds and exporter setup or delivery
failure cannot fail startup, readiness, message processing, governance, or persistence.

The API starts `http.request`. Kafka producers inject W3C Trace Context into message headers;
consumers extract it before starting `kafka.consume`. Application spans cover policy, persistence,
retrieval, provider, governance, approval, command, and simulated-action boundaries.

Span attributes are allowlisted. They may contain normalized component, outcome, breach type,
severity, action, governance decision, configured provider/model, normalized route, status code,
and messaging destination. Payloads, SOP text, prompts, model responses, credentials, authorization
headers, and database URLs are prohibited.

Trace and span identifiers are added to JSON logs automatically while a span is active. Kafka
header injection preserves application headers and replaces only propagation keys.
