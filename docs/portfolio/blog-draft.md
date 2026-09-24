# Building ColdChain Sentinel: Governed AI That Recommends, Policy That Decides, and Humans Who Authorize

Generative AI is easy to demonstrate in a chat window. It is much harder to place it responsibly inside an operational workflow where evidence can be incomplete, actions have consequences, and somebody must remain accountable.

I built ColdChain Sentinel as a portfolio-scale answer to that harder problem. It is a local cold-chain control tower that turns synthetic temperature telemetry into an auditable incident, retrieves trusted operating procedures, creates a bounded recommendation, applies deterministic policy, requires human authorization, and executes only a simulated action.

## The operational problem

A temperature alert for sensitive cargo raises several questions at once. Was the reading fresh and correctly ordered? Does the excursion meet a defined policy threshold? Which procedure was effective at the time? Is the proposed response supported by evidence? Who is allowed to approve it? Can a retry accidentally perform the action twice?

An ordinary chatbot does not answer those questions reliably. A plausible paragraph is not workflow state, a citation is not trustworthy merely because it looks precise, and model confidence is not authorization.

## Designing around authority

The central design decision was to separate recommendation, governance, authorization, and execution.

The recommendation provider is non-authoritative. It may return only eight fields: action, concise rationale, SOP citations, incident-evidence citations, contraindications, missing information, evidence sufficiency, and uncertainty. Application code supplies expiry, identity, prompt and schema versions, timestamps, token usage, correlation, and validation metadata.

Deterministic governance then evaluates the proposed action under versioned policy. `HOLD_SHIPMENT` requires human approval. The kill switch takes precedence. Only an authorized approval can create an idempotent command, and the current command adapter is deliberately simulated.

This structure makes failure safe. If a provider is disabled, times out, rate-limits, rejects the request, returns invalid JSON, invents a citation, or trips its circuit breaker, the workflow uses a deterministic fallback recommendation. The model is useful, but it is not structurally necessary for safety or demo completion.

## From telemetry to evidence

Synthetic telemetry is published to Kafka and processed by a Python worker. A deterministic policy classifies each reading and detects a breach. PostgreSQL stores authoritative workflow state, while an immutable evidence snapshot freezes the readings and policy inputs used for the decision.

This snapshot matters because an operator should be able to explain what was known when a recommendation was produced. The system does not ask a model to reconstruct facts later from a mutable screen.

## RAG with trusted procedures

ColdChain Sentinel includes six authored SOP documents. They are chunked deterministically and indexed in Qdrant. Retrieval filters out procedures that were not yet effective or were already superseded.

Retrieved text remains untrusted prompt context. System instructions explicitly isolate it, and output citations must match the chunk and evidence allowlists supplied for that request. This addresses two common RAG failures: treating retrieved text as instructions and accepting fabricated citations.

## Provider-neutral AI

The recommendation boundary uses an OpenAI-compatible Chat Completions contract with strict structured output. Groq is available for an explicitly enabled local demonstration. OpenAI support is implemented and tested entirely with mocked HTTP boundaries; no live OpenAI request was made.

The default remains deterministic and free of external model calls. Provider choice changes configuration—not domain types, governance rules, approval semantics, or persistence.

## Idempotency and auditability

Human decisions include a stable idempotency key. Repeating the exact decision returns the original result. Reusing the key with conflicting content fails rather than creating another command.

The audit timeline is append-only and hash-linked. It captures actors, correlations, causation, component and schema versions, timestamps, and the prior event hash. This is useful tamper evidence for the demo, although a production system would still need stronger immutable storage and retention controls.

## Observability without leaking evidence

Prometheus metrics use bounded, low-cardinality labels. Structured logs allowlist fields and redact credential-shaped values. OpenTelemetry propagates correlation through HTTP and Kafka, but excludes prompts, SOP text, unrestricted model responses, headers, credentials, and incident payloads. Grafana and Jaeger are optional localhost-only services.

The goal is not simply to make the system observable. It is to make the right operational state observable without turning telemetry into another data-leak path.

## Evaluation as an engineering artifact

The deterministic evaluation harness contains 16 scenarios covering classification, governance agreement, citation validity, schema validity, injection resistance, fallback correctness, unauthorized-action prevention, and audit completeness. Reports are reproducible and ignored by Git.

The final development checks recorded 109 passing non-live backend tests at 86.96% coverage, 50 passing frontend and accessibility tests, and 16/16 passing evaluation scenarios. These are development-validation results, not production service metrics.

## What I learned

1. The most important AI decision is often what the model is not allowed to decide.
2. Provenance should be generated by trusted code, not requested from a model.
3. RAG needs temporal filtering and citation verification, not only vector similarity.
4. Human-in-the-loop requires identity, expiry, idempotency, and an explicit command boundary.
5. Deterministic fallback is both a safety feature and a practical demonstration strategy.
6. Observability schemas deserve the same privacy review as API schemas.

## Honest limitations

ColdChain Sentinel uses synthetic data, local identities, deterministic embeddings, single-node infrastructure, and a simulated action adapter. It is not deployed and controls no real shipment. Production work would include enterprise IAM, managed secrets, TLS and network isolation, real telemetry and TMS integrations, transactional delivery guarantees, privacy and retention policy, immutable audit storage, load and recovery testing, HA/DR, SLOs, provider qualification, cost controls, and deployment-specific regulatory validation.

## Closing thought

The interesting question is not whether a model can recommend holding a shipment. It is whether the surrounding system can prove which evidence supported that recommendation, reject unsafe output, apply policy independently, keep a human accountable, prevent duplicate execution, and explain the result later. ColdChain Sentinel is my implementation of that governed boundary.
