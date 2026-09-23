import type { Action, AuditEvent, GovernanceCheck, Incident, InvestigationData, Recommendation } from '../contracts';
import type { ApiIncident, ApiTimeline } from './schemas';

const actions = new Set<Action>(['HOLD_SHIPMENT', 'CONTINUE_MONITORING', 'REQUEST_INSPECTION', 'RELEASE_SHIPMENT']);
const provenanceValue = (provenance: Record<string, unknown>, camel: string, snake: string): unknown => provenance[camel] ?? provenance[snake];
const strings = (value: unknown): string[] | null => Array.isArray(value) && value.every((item) => typeof item === 'string') ? value : null;
const text = (value: unknown, fallback = 'Not reported'): string => typeof value === 'string' && value ? value : fallback;
const numberValue = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const uncertainty = (value: unknown): Recommendation['uncertainty'] => value === 'low' || value === 'high' ? value : 'medium';

export function mapIncident(source: ApiIncident): Incident {
  const latest = source.telemetry.at(-1);
  const threshold = numberValue(latest?.policyInputs.upperThresholdCelsius);
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
    severity: source.severity === 'CRITICAL' ? 'critical' : source.severity === 'HIGH' ? 'warning' : 'normal',
    title: reasonCodes.includes('CLEARLY_UNSAFE_TEMPERATURE') ? 'Immediate critical temperature breach' : 'Sustained temperature breach',
    shipment: source.shipmentId,
    product: latest?.cargoType === 'FRESH_PERISHABLES' ? 'Fresh perishables' : latest?.cargoType ?? null,
    sensor: null,
    temperature: latest?.temperatureCelsius ?? null,
    allowedMin: null,
    allowedMax: threshold,
    breachMinutes,
    state,
    governance,
    createdMinutesAgo: Math.max(0, Math.round((Date.now() - Date.parse(source.createdAt)) / 60_000)),
    reviewer: source.approval?.actorId ?? null,
    route: null,
    productSensitivity: null,
    sensorHealth: null,
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
  const expiry = Date.parse(record.expiresAt);
  const expiresInMinutes = Number.isFinite(expiry) ? Math.max(0, Math.round((expiry - Date.now()) / 60_000)) : null;
  return {
    action: record.actionType as Action,
    rationale: record.rationale,
    evidenceSufficient: provenanceValue(provenance, 'evidenceSufficient', 'evidence_sufficient') === true || record.evidenceIds.length > 0,
    uncertainty: uncertainty(provenanceValue(provenance, 'uncertaintyLevel', 'uncertainty_level')),
    missingInformation: strings(provenanceValue(provenance, 'missingInformation', 'missing_information')),
    contraindications: strings(provenanceValue(provenance, 'contraindications', 'contraindications')),
    evidenceIds: strings(provenanceValue(provenance, 'citedChunkIds', 'cited_chunk_ids')) ?? [],
    incidentEvidenceIds: record.evidenceIds,
    fallback,
    provider: text(provenanceValue(provenance, 'provider', 'provider'), record.provider),
    model: text(provenanceValue(provenance, 'model', 'model'), record.provider),
    promptVersion: text(provenanceValue(provenance, 'promptVersion', 'prompt_version')),
    schemaVersion: text(provenanceValue(provenance, 'responseSchemaVersion', 'response_schema_version'), '1.0'),
    latencyMs: numberValue(provenanceValue(provenance, 'latencyMs', 'latency_ms')),
    tokens: numberValue(provenanceValue(provenance, 'totalTokens', 'total_tokens')),
    estimatedCost: numberValue(provenanceValue(provenance, 'estimatedCost', 'estimated_cost'))?.toString() ?? null,
    expiresInMinutes,
    validation: expiry <= Date.now() ? 'expired' : 'valid',
  };
}

export function mapInvestigation(source: ApiIncident, timeline: ApiTimeline): InvestigationData {
  const incident = mapIncident(source);
  const recommendation = mapRecommendation(source);
  const provenance = source.recommendation?.provenance ?? {};
  const chunkIds = strings(provenanceValue(provenance, 'citedChunkIds', 'cited_chunk_ids')) ?? strings(provenanceValue(provenance, 'retrievedChunkIds', 'retrieved_chunk_ids')) ?? [];
  const documentIds = strings(provenanceValue(provenance, 'citedDocumentIds', 'cited_document_ids')) ?? [];
  const sectionIds = strings(provenanceValue(provenance, 'citedSectionIds', 'cited_section_ids')) ?? [];
  const evidence = chunkIds.map((id, index) => ({ id, title: documentIds[index] ?? 'Trusted ColdChain Sentinel SOP', section: sectionIds[index] ?? 'Not reported', version: text(provenanceValue(provenance, 'sopCorpusVersion', 'sop_corpus_version')), effectiveDate: 'Not reported', score: null, excerpt: 'SOP content is not returned by the operational API.', trusted: true }));
  const governanceChecks: GovernanceCheck[] = [
    { name: 'Evidence check', state: source.evidence ? 'pass' : 'failure', detail: source.evidence ? 'Sensor evidence was saved and locked.' : 'Evidence was not reported.' },
    { name: 'Citation check', state: evidence.length > 0 ? 'pass' : 'warning', detail: evidence.length > 0 ? `${evidence.length} trusted SOP citation(s) recorded.` : 'No SOP citations were reported.' },
    { name: 'Schema check', state: 'pass', detail: `Response schema ${recommendation.schemaVersion}.` },
    { name: 'Provider identity', state: recommendation.fallback ? 'warning' : 'pass', detail: recommendation.fallback ? 'Deterministic fallback was used.' : recommendation.provider },
    { name: 'Expiry check', state: recommendation.validation === 'valid' ? 'pass' : 'failure', detail: recommendation.validation === 'valid' ? 'Recommendation is current.' : 'Recommendation expired.' },
    { name: 'Policy check', state: source.governance?.decision === 'APPROVAL_REQUIRED' ? 'warning' : source.governance?.decision === 'ALLOWED' ? 'pass' : 'failure', detail: source.governance?.decision ?? 'Not reported' },
    { name: 'Kill-switch state', state: source.governance?.reasonCodes.includes('KILL_SWITCH_ACTIVE') ? 'failure' : 'pass', detail: source.governance?.reasonCodes.includes('KILL_SWITCH_ACTIVE') ? 'Active' : 'Inactive' },
    { name: 'Human approval', state: source.approval ? 'pass' : 'warning', detail: source.approval ? `${source.approval.decision} by ${source.approval.actorId}` : 'Pending authorized reviewer.' },
  ];
  const readings = source.telemetry.map((item) => {
    const upper = numberValue(item.policyInputs.upperThresholdCelsius);
    const clearlyUnsafe = numberValue(item.policyInputs.clearlyUnsafeCelsius);
    const status = clearlyUnsafe !== null && item.temperatureCelsius >= clearlyUnsafe ? 'critical' as const : upper !== null && item.temperatureCelsius > upper ? 'warning' as const : 'normal' as const;
    return { minute: Math.round((Date.parse(item.occurredAt) - Date.now()) / 60_000), temperature: item.temperatureCelsius, status, stale: item.disposition === 'STALE', outOfOrder: item.disposition === 'OUT_OF_ORDER' };
  });
  const audit: AuditEvent[] = timeline.map((item) => ({ id: item.auditEventId, offsetMinutes: Math.round((Date.parse(item.occurredAt) - Date.now()) / 60_000), actor: item.actorId, type: item.eventType.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase()), summary: auditSummary(item.eventType, item.payload), correlationId: item.correlationId, traceId: 'Not reported' }));
  return { incident, readings, evidence, recommendation, governanceChecks, audit, ...(source.approval ? { decision: { approvalId: source.approval.approvalId, decision: source.approval.decision as 'APPROVED' | 'REJECTED', idempotentReplay: false, commandId: source.command?.commandId ?? null, status: source.command?.status ?? null, actionResult: source.command?.actionResult ?? null } } : {}) };
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
