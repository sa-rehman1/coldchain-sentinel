import { z } from 'zod';

const uuid = z.string().uuid();
const record = z.record(z.string(), z.unknown());
const object = z.strictObject;

export const telemetrySchema = object({ eventId: uuid, occurredAt: z.string(), readingSequence: z.number().int(), temperatureCelsius: z.number(), cargoType: z.string(), disposition: z.string(), policyInputs: record, reasonCodes: z.array(z.string()) });
export const evidenceSchema = object({ evidenceId: uuid, telemetryEventIds: z.array(uuid), policyInputs: record, summary: z.string(), contentHash: z.string(), capturedAt: z.string() });
export const recommendationSchema = object({ recommendationId: uuid, evidenceIds: z.array(uuid), actionType: z.string(), parameters: record, provider: z.string(), authorIdentity: z.string(), rationale: z.string(), expiresAt: z.string(), nonAuthoritative: z.boolean(), provenance: record });
export const governanceSchema = object({ evaluationId: uuid, recommendationId: uuid, decision: z.string(), policyVersion: z.string(), reasonCodes: z.array(z.string()), inputs: record, evaluatedAt: z.string() });
export const approvalSchema = object({ approvalId: uuid, recommendationId: uuid, actorId: z.string(), actorRole: z.string(), decision: z.string(), rationale: z.string(), decidedAt: z.string() });
export const actionResultSchema = object({ resultId: uuid, status: z.string(), adapter: z.string(), detail: z.string(), completedAt: z.string() });
export const commandSchema = object({ commandId: uuid, incidentId: uuid, actionType: z.string(), status: z.string(), adapter: z.string().nullable(), detail: z.string().nullable(), actionResult: actionResultSchema.nullable().optional() });
export const incidentSchema = object({ incidentId: uuid, shipmentId: uuid, state: z.string(), severity: z.string(), policyVersion: z.string(), sourceEventIds: z.array(uuid), correlationId: uuid, createdAt: z.string(), updatedAt: z.string(), recommendationId: uuid.nullable().optional(), recommendedAction: z.string().nullable().optional(), recommendationExpiresAt: z.string().nullable().optional(), recommendationProvenance: record.nullable().optional(), telemetry: z.array(telemetrySchema).default([]), evidence: evidenceSchema.nullable().optional(), recommendation: recommendationSchema.nullable().optional(), governance: governanceSchema.nullable().optional(), approval: approvalSchema.nullable().optional(), command: commandSchema.nullable().optional() });
export const incidentsSchema = z.array(incidentSchema);
export const timelineSchema = z.array(object({ sequence: z.number().int(), auditEventId: uuid, eventType: z.string(), actorId: z.string(), correlationId: uuid, causationId: uuid.nullable(), componentVersion: z.string(), schemaVersion: z.string(), payload: record, occurredAt: z.string(), previousEventHash: z.string().nullable(), eventHash: z.string() }));
export const decisionSchema = object({ approvalId: uuid, decision: z.enum(['APPROVED', 'REJECTED']), idempotentReplay: z.boolean(), commandId: uuid.nullable().optional(), status: z.string().nullable().optional(), actionResult: actionResultSchema.nullable().optional() });
export const scenarioSchema = object({ scenarioId: z.string(), title: z.string(), description: z.string(), expectedOutcome: z.string(), humanAction: z.string() });
export const scenariosSchema = z.array(scenarioSchema);
export const demoRunSchema = object({ runId: uuid, scenarioId: z.string(), correlationId: uuid, shipmentId: uuid, eventIds: z.array(uuid), publishCount: z.number().int(), startedAt: z.string().optional(), status: z.enum(['ACCEPTED', 'PROCESSING', 'INCIDENT_READY', 'COMPLETED_WITHOUT_INCIDENT']), processedEventCount: z.number().int().default(0), dispositions: z.array(z.string()).default([]), incident: incidentSchema.nullable().optional(), steps: object({ telemetrySubmitted: z.boolean(), eventAccepted: z.boolean(), policyEvaluated: z.boolean(), evidenceCollected: z.boolean(), recommendationCreated: z.boolean(), governanceCompleted: z.boolean(), incidentReady: z.boolean() }).default({ telemetrySubmitted: true, eventAccepted: true, policyEvaluated: false, evidenceCollected: false, recommendationCreated: false, governanceCompleted: false, incidentReady: false }) });
export const liveHealthSchema = object({ status: z.literal('alive') });
export const aiHealthSchema = object({ selected_provider: z.string(), selected_model: z.string(), provider_configured: z.boolean(), live_calls_enabled: z.boolean(), qdrant_readiness: z.string(), embedding_provider_readiness: z.string(), fallback_available: z.boolean() });

export type ApiIncident = z.infer<typeof incidentSchema>;
export type ApiTimeline = z.infer<typeof timelineSchema>;
export type ApiDecision = z.infer<typeof decisionSchema>;
export type ApiDemoRun = z.infer<typeof demoRunSchema>;
