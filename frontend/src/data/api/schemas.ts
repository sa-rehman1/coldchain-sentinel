import { z } from 'zod';

const uuid = z.string().uuid();
const record = z.record(z.string(), z.unknown());
const object = z.strictObject;

export const telemetrySchema = object({ eventId: uuid, occurredAt: z.string(), readingSequence: z.number().int(), temperatureCelsius: z.number(), cargoType: z.string(), disposition: z.string(), policyInputs: record, reasonCodes: z.array(z.string()) });
export const evidenceSchema = object({ evidenceId: uuid, evidenceReference: z.string().nullable().optional(), telemetryEventIds: z.array(uuid), policyInputs: record, summary: z.string(), contentHash: z.string(), capturedAt: z.string() });
const recommendationActionabilitySchema = object({ state: z.enum(['AWAITING_HUMAN_REVIEW', 'EXPIRED', 'DECIDED']), approvalAllowed: z.boolean(), rejectionAllowed: z.boolean(), status: z.string(), explanation: z.string(), expiresInMinutes: z.number().int().nonnegative().nullable() });
export const recommendationSchema = object({ recommendationId: uuid, evidenceIds: z.array(uuid), actionType: z.string(), parameters: record, provider: z.string(), authorIdentity: z.string(), rationale: z.string(), expiresAt: z.string(), nonAuthoritative: z.boolean(), provenance: record, actionability: recommendationActionabilitySchema });
export const sopEvidenceSchema = object({ chunkId: z.string(), documentId: z.string(), documentTitle: z.string(), documentVersion: z.string(), sectionId: z.string(), sectionTitle: z.string(), effectiveDate: z.string(), excerpt: z.string(), whyApplicable: z.string(), validationStatus: z.string() });
export const governanceCheckSchema = object({ name: z.string(), state: z.string(), detail: z.string() });
export const governanceSchema = object({ evaluationId: uuid, recommendationId: uuid, decision: z.string(), policyVersion: z.string(), reasonCodes: z.array(z.string()), inputs: record, evaluatedAt: z.string(), authority: z.string().nullable().optional(), checks: z.array(governanceCheckSchema).default([]) });
export const approvalSchema = object({ approvalId: uuid, recommendationId: uuid, actorId: z.string(), actorRole: z.string(), decision: z.string(), rationale: z.string(), decidedAt: z.string() });
export const actionResultSchema = object({ resultId: uuid, status: z.string(), adapter: z.string(), detail: z.string(), completedAt: z.string() });
export const commandSchema = object({ commandId: uuid, incidentId: uuid, actionType: z.string(), status: z.string(), adapter: z.string().nullable(), detail: z.string().nullable(), actionResult: actionResultSchema.nullable().optional() });
export const incidentEvidenceProfileSchema = object({ sensorHealth: z.string(), calibration: z.string(), sampleIntervalMinutes: z.number().int().positive(), readingQuality: z.string(), productSensitivity: z.string(), custodyVerification: z.string(), complete: z.boolean() });
export const incidentSchema = object({ incidentId: uuid, shipmentId: uuid, incidentReference: z.string().nullable().optional(), shipmentReference: z.string().nullable().optional(), route: object({ origin: z.string(), via: z.string(), destination: z.string(), progress: z.number().int().min(0).max(100) }).nullable().optional(), productLabel: z.string().nullable().optional(), sensorLabel: z.string().nullable().optional(), reviewerLabel: z.string().nullable().optional(), evidenceProfile: incidentEvidenceProfileSchema.nullable().optional(), state: z.string(), severity: z.string(), policyVersion: z.string(), sourceEventIds: z.array(uuid), correlationId: uuid, createdAt: z.string(), updatedAt: z.string(), recommendationId: uuid.nullable().optional(), recommendedAction: z.string().nullable().optional(), recommendationExpiresAt: z.string().nullable().optional(), recommendationProvenance: record.nullable().optional(), sopEvidence: z.array(sopEvidenceSchema).default([]), telemetry: z.array(telemetrySchema).default([]), evidence: evidenceSchema.nullable().optional(), recommendation: recommendationSchema.nullable().optional(), governance: governanceSchema.nullable().optional(), approval: approvalSchema.nullable().optional(), command: commandSchema.nullable().optional() });
export const incidentsSchema = z.array(incidentSchema);
export const timelineSchema = z.array(object({ sequence: z.number().int(), auditEventId: uuid, eventType: z.string(), actorId: z.string(), correlationId: uuid, causationId: uuid.nullable(), componentVersion: z.string(), schemaVersion: z.string(), payload: record, occurredAt: z.string(), previousEventHash: z.string().nullable(), eventHash: z.string(), hashChainVerified: z.boolean() }));
export const decisionSchema = object({ approvalId: uuid, decision: z.enum(['APPROVED', 'REJECTED']), idempotentReplay: z.boolean(), commandId: uuid.nullable().optional(), status: z.string().nullable().optional(), actionResult: actionResultSchema.nullable().optional() });
export const scenarioSchema = object({ scenarioId: z.string(), title: z.string(), description: z.string(), expectedOutcome: z.string(), humanAction: z.string() });
export const scenariosSchema = z.array(scenarioSchema);
const demoStageStateSchema = z.enum(['PENDING', 'COMPLETED', 'NOT_REQUIRED', 'BLOCKED', 'FAILED']);
export const demoRunSchema = object({ runId: uuid, scenarioId: z.string(), correlationId: uuid, shipmentId: uuid, eventIds: z.array(uuid), publishCount: z.number().int(), startedAt: z.string().optional(), status: z.enum(['ACCEPTED', 'PROCESSING', 'INCIDENT_READY', 'COMPLETED_WITHOUT_INCIDENT']), processedEventCount: z.number().int().default(0), dispositions: z.array(z.string()).default([]), incident: incidentSchema.nullable().optional(), incidentId: uuid.nullable().default(null), incidentReference: z.string().nullable().default(null), shipmentReference: z.string().nullable().default(null), incidentSeverity: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']).nullable().default(null), governanceDecision: z.string().nullable().default(null), humanDecisionRecorded: z.boolean().default(false), resultState: z.enum(['PROCESSING', 'COMPLETE', 'AWAITING_HUMAN_REVIEW', 'BLOCKED', 'FAILED']).default('PROCESSING'), steps: object({ sensorReading: demoStageStateSchema, policyCheck: demoStageStateSchema, incidentCreated: demoStageStateSchema, evidenceCollected: demoStageStateSchema, aiAdvisory: demoStageStateSchema, governance: demoStageStateSchema, humanReview: demoStageStateSchema }).default({ sensorReading: 'PENDING', policyCheck: 'PENDING', incidentCreated: 'PENDING', evidenceCollected: 'PENDING', aiAdvisory: 'PENDING', governance: 'PENDING', humanReview: 'PENDING' }) });
export const liveHealthSchema = object({ status: z.literal('alive') });
export const aiHealthSchema = object({ selected_provider: z.string(), selected_model: z.string(), provider_configured: z.boolean(), live_calls_enabled: z.boolean(), qdrant_readiness: z.string(), embedding_provider_readiness: z.string(), fallback_available: z.boolean() });
const dashboardRouteSchema = object({ origin: z.string(), via: z.string(), destination: z.string(), progress: z.number().int().min(0).max(100) });
const dashboardShipmentSchema = object({
  incidentId: uuid,
  incidentReference: z.string(),
  shipmentId: uuid,
  shipmentReference: z.string(),
  route: dashboardRouteSchema,
  product: z.string(),
  currentTemperatureCelsius: z.number(),
  permittedMinCelsius: z.number(),
  permittedMaxCelsius: z.number(),
  state: z.string(),
  severity: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  lastReadingAt: z.string(),
  ageMinutes: z.number().int().nonnegative(),
  trendCelsius: z.array(z.number()),
  reasonCodes: z.array(z.string()),
  recommendedAction: z.string().nullable().optional(),
  governanceDecision: z.string().nullable().optional(),
  recommendationExpiresAt: z.string().nullable().optional(),
});
export const dashboardSchema = object({
  generatedAt: z.string(),
  scope: z.literal('canonical-showcase'),
  metrics: object({ affectedShipments: z.number().int().nonnegative(), openIncidents: z.number().int().nonnegative(), awaitingHumanReview: z.number().int().nonnegative() }),
  severityDistribution: object({ critical: z.number().int().nonnegative(), warning: z.number().int().nonnegative(), normal: z.number().int().nonnegative() }),
  latestShipments: z.array(dashboardShipmentSchema).max(5),
  approvalQueue: object({ pending: z.number().int().nonnegative(), oldestWaitingMinutes: z.number().int().nonnegative(), expiringWithin15Minutes: z.number().int().nonnegative() }),
  humanDecisions: z.array(object({ incidentId: uuid, incidentReference: z.string(), decision: z.string(), reviewerRole: z.string(), decidedAt: z.string() })),
  activity: z.array(object({ label: z.string(), startsAt: z.string(), critical: z.number().int().nonnegative(), warning: z.number().int().nonnegative(), resolved: z.number().int().nonnegative() })),
});
const observabilityPointSchema = object({ timestamp: z.string(), value: z.number() });
export const observabilitySummarySchema = object({
  generatedAt: z.string(),
  overallStatus: z.enum(['HEALTHY', 'DEGRADED']),
  healthyServices: z.number().int().nonnegative(),
  totalServices: z.number().int().nonnegative(),
  activeAlerts: z.number().int().nonnegative(),
  autoRefreshSeconds: z.number().int().min(10).max(15),
  services: z.array(object({ name: z.string(), status: z.enum(['HEALTHY', 'DEGRADED', 'UNAVAILABLE', 'OPTIONAL_NOT_STARTED']), signal: z.string(), measurement: z.number().nullable(), measurementUnit: z.string().nullable(), checkedAt: z.string(), inspectionUrl: z.string().url().nullable() })),
  metrics: z.array(object({ key: z.string(), label: z.string(), value: z.number().nullable(), unit: z.string(), state: z.enum(['AVAILABLE', 'NO_SAMPLES', 'UNAVAILABLE']), source: z.string() })),
  series: object({ apiRequestRate: z.array(observabilityPointSchema), apiP95Latency: z.array(observabilityPointSchema), workerThroughput: z.array(observabilityPointSchema), dlqActivity: z.array(observabilityPointSchema) }),
  alerts: object({ state: z.enum(['AVAILABLE', 'UNAVAILABLE']), rules: z.array(object({ name: z.string(), state: z.string(), severity: z.string(), summary: z.string() })).max(20) }),
  traces: object({ state: z.enum(['AVAILABLE', 'NO_SAMPLES', 'UNAVAILABLE']), items: z.array(object({ traceId: z.string(), operation: z.string(), durationMs: z.number().nonnegative(), spanCount: z.number().int().nonnegative(), startedAt: z.string() })).max(5) }),
  privacyNotice: z.string(),
});

export type ApiIncident = z.infer<typeof incidentSchema>;
export type ApiTimeline = z.infer<typeof timelineSchema>;
export type ApiDecision = z.infer<typeof decisionSchema>;
export type ApiDemoRun = z.infer<typeof demoRunSchema>;
export type ApiDashboard = z.infer<typeof dashboardSchema>;
