import type { Action, AuditEvent, GovernanceCheck, Incident, InvestigationData, Recommendation } from '../contracts';
import type { ApiIncident, ApiTimeline } from './schemas';

const actions = new Set<Action>(['HOLD_SHIPMENT', 'CONTINUE_MONITORING', 'REQUEST_INSPECTION', 'RELEASE_SHIPMENT']);
const provenanceValue = (provenance: Record<string, unknown>, camel: string, snake: string): unknown => provenance[camel] ?? provenance[snake];
const strings = (value: unknown): string[] | null => Array.isArray(value) && value.every((item) => typeof item === 'string') ? value : null;
const text = (value: unknown, fallback = 'Not reported'): string => typeof value === 'string' && value ? value : fallback;
const numberValue = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const uncertainty = (value: unknown): Recommendation['uncertainty'] => value === 'low' || value === 'high' ? value : 'medium';
const checkState = (value: string): GovernanceCheck['state'] => value === 'pass' || value === 'warning' ? value : 'failure';
const actorLabel = (actorId: string): string => {
  const prefix = actorId.split(/[:_-]/, 1)[0]?.toLowerCase();
  if (prefix === 'dispatcher') return 'Dispatcher';
  if (prefix === 'auditor') return 'Auditor';
  if (prefix === 'administrator') return 'Administrator';
  if (prefix === 'service' || prefix === 'worker') return 'ColdChain Sentinel service';
  return 'System actor';
};

export function mapIncident(source: ApiIncident): Incident {
  const latest = source.telemetry.at(-1);
  const threshold = numberValue(latest?.policyInputs.upperThresholdCelsius);
  const lowerThreshold = numberValue(latest?.policyInputs.lowerThresholdCelsius);
  const unsafe = numberValue(latest?.policyInputs.clearlyUnsafeCelsius);
  const temperatures = source.telemetry.filter((item) => threshold !== null && item.temperatureCelsius > threshold);
  const firstUnsafe = temperatures.at(0);
  const lastUnsafe = temperatures.at(-1);
  const breachMinutes = firstUnsafe && lastUnsafe ? Math.max(0, Math.round((Date.parse(lastUnsafe.occurredAt) - Date.parse(firstUnsafe.occurredAt)) / 60_000)) : null;
  const reasonCodes = latest?.reasonCodes ?? [];
  const state = source.state === 'AWAITING_APPROVAL' ? 'awaiting-review' : source.state === 'REJECTED' ? 'rejected' : source.state === 'RESOLVED' ? 'completed' : source.state === 'OPEN' || source.state === 'EVIDENCE_COLLECTED' ? 'investigating' : source.state === 'APPROVED' || source.state === 'EXECUTING' ? 'investigating' : 'triage';
  const decision = source.governance?.decision;
  const governance = decision === 'APPROVAL_REQUIRED' ? 'approval-required' : decision === 'ALLOWED' ? 'allowed' : decision === 'PROHIBITED' || decision === 'KILL_SWITCH_ACTIVE' ? 'blocked' : 'fallback';
  return {
    id: source.incidentId,
    ...(source.incidentReference ? { reference: source.incidentReference } : {}),
    severity: source.severity === 'CRITICAL' ? 'critical' : source.severity === 'HIGH' ? 'warning' : 'normal',
    title: reasonCodes.includes('CLEARLY_UNSAFE_TEMPERATURE') ? 'Immediate critical temperature breach' : 'Sustained temperature breach',
    shipment: source.shipmentReference ?? source.shipmentId,
    product: source.productLabel ?? (latest?.cargoType === 'FRESH_PERISHABLES' ? 'Fresh perishables' : latest?.cargoType ?? null),
    sensor: source.sensorLabel ?? null,
    temperature: latest?.temperatureCelsius ?? null,
    allowedMin: lowerThreshold,
    allowedMax: threshold,
    breachMinutes,
    state,
    governance,
    createdMinutesAgo: Math.max(0, Math.round((Date.now() - Date.parse(source.createdAt)) / 60_000)),
    reviewer: source.reviewerLabel ?? null,
    route: source.route ? { from: source.route.origin, via: source.route.via, to: source.route.destination, progress: source.route.progress } : null,
    productSensitivity: source.evidenceProfile?.productSensitivity ?? null,
    sensorHealth: source.evidenceProfile?.sensorHealth ?? null,
    evidenceProfile: source.evidenceProfile ?? null,
    stale: latest?.disposition === 'STALE',
    duplicate: false,
    breachKind: reasonCodes.includes('CLEARLY_UNSAFE_TEMPERATURE') || unsafe !== null && latest && latest.temperatureCelsius >= unsafe ? 'immediate' : reasonCodes.includes('SUSTAINED_HIGH_TEMPERATURE') ? 'sustained' : 'none',
    ...((source.recommendation?.recommendationId ?? source.recommendationId) ? { recommendationId: (source.recommendation?.recommendationId ?? source.recommendationId)! } : {}),
    ...(actions.has((source.recommendation?.actionType ?? source.recommendedAction) as Action) ? { recommendedAction: (source.recommendation?.actionType ?? source.recommendedAction) as Action } : {}),
    ...((source.recommendation?.expiresAt ?? source.recommendationExpiresAt) ? { recommendationExpiresAt: (source.recommendation?.expiresAt ?? source.recommendationExpiresAt)! } : {}),
    correlationId: source.correlationId,
  };
}

function mapRecommendation(source: ApiIncident): Recommendation {
  const record = source.recommendation;
  if (!record || !actions.has(record.actionType as Action)) throw new Error('Unsupported or missing recommendation action');
  const provenance = record.provenance;
  const fallback = provenanceValue(provenance, 'fallbackUsed', 'fallback_used') === true;
  return {
    action: record.actionType as Action,
    rationale: record.rationale,
    evidenceSufficient: provenanceValue(provenance, 'evidenceSufficient', 'evidence_sufficient') === true || record.evidenceIds.length > 0,
    uncertainty: uncertainty(provenanceValue(provenance, 'uncertaintyLevel', 'uncertainty_level')),
    missingInformation: strings(provenanceValue(provenance, 'missingInformation', 'missing_information')),
    contraindications: strings(provenanceValue(provenance, 'contraindications', 'contraindications')),
    evidenceIds: strings(provenanceValue(provenance, 'citedChunkIds', 'cited_chunk_ids')) ?? [],
    incidentEvidenceIds: record.evidenceIds,
    evidenceBundleReference: source.evidence?.evidenceReference ?? null,
    fallback,
    provider: text(provenanceValue(provenance, 'provider', 'provider'), record.provider),
    model: text(provenanceValue(provenance, 'model', 'model'), record.provider),
    promptVersion: text(provenanceValue(provenance, 'promptVersion', 'prompt_version')),
    schemaVersion: text(provenanceValue(provenance, 'responseSchemaVersion', 'response_schema_version'), '1.0'),
    latencyMs: numberValue(provenanceValue(provenance, 'latencyMs', 'latency_ms')),
    tokens: numberValue(provenanceValue(provenance, 'totalTokens', 'total_tokens')),
    estimatedCost: numberValue(provenanceValue(provenance, 'estimatedCost', 'estimated_cost'))?.toString() ?? null,
    expiresInMinutes: record.actionability.expiresInMinutes,
    validation: record.actionability.state === 'EXPIRED' ? 'expired' : 'valid',
    actionability: record.actionability,
  };
}

export function mapInvestigation(source: ApiIncident, timeline: ApiTimeline): InvestigationData {
  const incident = mapIncident(source);
  const recommendation = mapRecommendation(source);
  const evidence = source.sopEvidence.map((item) => ({ id: item.chunkId, documentId: item.documentId, title: item.documentTitle, section: `${item.sectionTitle} (${item.sectionId})`, version: `${item.documentId} · v${item.documentVersion}`, effectiveDate: item.effectiveDate, score: null, excerpt: item.excerpt, trusted: item.validationStatus === 'trusted', whyApplicable: item.whyApplicable, validationStatus: item.validationStatus }));
  const governanceChecks: GovernanceCheck[] = (source.governance?.checks ?? []).map((check) => ({ name: check.name, state: checkState(check.state), detail: check.detail }));
  const readings = source.telemetry.map((item) => {
    const upper = numberValue(item.policyInputs.upperThresholdCelsius);
    const clearlyUnsafe = numberValue(item.policyInputs.clearlyUnsafeCelsius);
    const status = clearlyUnsafe !== null && item.temperatureCelsius >= clearlyUnsafe ? 'critical' as const : upper !== null && item.temperatureCelsius > upper ? 'warning' as const : 'normal' as const;
    return { minute: Math.round((Date.parse(item.occurredAt) - Date.now()) / 60_000), temperature: item.temperatureCelsius, status, stale: item.disposition === 'STALE', outOfOrder: item.disposition === 'OUT_OF_ORDER' };
  });
  const audit: AuditEvent[] = timeline.map((item) => ({ id: item.auditEventId, offsetMinutes: Math.round((Date.parse(item.occurredAt) - Date.now()) / 60_000), actor: actorLabel(item.actorId), type: item.eventType.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase()), summary: auditSummary(item.eventType, item.payload), correlationId: item.correlationId, traceId: 'Not reported', occurredAt: item.occurredAt, context: item.causationId ? 'Correlation and causation links recorded' : 'Correlation link recorded', hashChainVerified: item.hashChainVerified }));
  return { incident, readings, evidence, recommendation, governanceChecks, audit, ...(source.governance ? { governanceSummary: { decision: source.governance.decision, policyVersion: source.governance.policyVersion, evaluatedAt: source.governance.evaluatedAt, authority: source.governance.authority ?? 'deterministic-governance' } } : {}), ...(source.approval ? { decision: { approvalId: source.approval.approvalId, decision: source.approval.decision as 'APPROVED' | 'REJECTED', idempotentReplay: false, commandId: source.command?.commandId ?? null, status: source.command?.status ?? null, actionResult: source.command?.actionResult ?? null } } : {}) };
}

const auditSummary = (type: string, payload: Record<string, unknown>): string => {
  if (type === 'TELEMETRY_RECEIVED') return 'Valid telemetry entered the durable workflow.';
  if (type === 'BREACH_POLICY_EVALUATED') return `Safety policy result: ${text(payload.outcome)}.`;
  if (type === 'EVIDENCE_SNAPSHOT_CREATED') return 'Sensor evidence was saved and locked.';
  if (type === 'RECOMMENDATION_CREATED') return `Recommendation created: ${text(payload.actionType)}.`;
  if (type === 'GOVERNANCE_EVALUATED') return `Governance result: ${text(payload.decision)}.`;
  if (type === 'HUMAN_DECISION_RECORDED') return `Human decision: ${text(payload.decision)}.`;
  if (type === 'COMMAND_CREATED') return `One ${text(payload.actionType)} command was created.`;
  if (type === 'SIMULATED_ACTION_COMPLETED') return `Simulated action result: ${text(payload.status)}.`;
  return 'Workflow event recorded.';
};
