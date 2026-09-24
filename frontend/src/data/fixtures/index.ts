import type { AuditEvent, DashboardData, EvidenceChunk, GovernanceCheck, Incident, InvestigationData, LiveTelemetryRow, Scenario, TemperaturePoint } from '../contracts';

export const incidents: Incident[] = [
  { id: 'INC-2481', severity: 'critical', title: 'Sustained thermal excursion', shipment: 'CCS-CHI-1842', product: 'mRNA vaccine', sensor: 'SEN-7A42', temperature: 11.8, allowedMin: 2, allowedMax: 8, breachMinutes: 47, state: 'awaiting-review', governance: 'approval-required', createdMinutesAgo: 52, reviewer: 'Maya Chen', route: { from: 'Chicago', via: 'In transit', to: 'Denver', progress: 68 }, productSensitivity: 'High · freeze and heat sensitive', sensorHealth: 'Nominal · calibrated 12 days ago', breachKind: 'sustained' },
  { id: 'INC-2480', severity: 'warning', title: 'Cooling recovery delayed', shipment: 'CCS-SEA-7741', product: 'Fresh Atlantic salmon', sensor: 'SEN-3D18', temperature: 5.9, allowedMin: 0, allowedMax: 4, breachMinutes: 18, state: 'investigating', governance: 'allowed', createdMinutesAgo: 29, reviewer: 'Jon Bell', route: { from: 'Seattle', via: 'In transit', to: 'Chicago', progress: 43 }, productSensitivity: 'Medium · spoilage risk', sensorHealth: 'Nominal · battery 84%' },
  { id: 'INC-2479', severity: 'critical', title: 'Sustained compartment excursion', shipment: 'CCS-BOS-5510', product: 'Frozen biologics', sensor: 'SEN-9K11', temperature: -8.2, allowedMin: -25, allowedMax: -15, breachMinutes: 31, state: 'awaiting-review', governance: 'approval-required', createdMinutesAgo: 34, reviewer: 'Ari Okafor', route: { from: 'Boston', via: 'In transit', to: 'New York', progress: 81 }, productSensitivity: 'Critical · thaw prohibited', sensorHealth: 'Conflict · 6.4°C divergence', breachKind: 'sustained' },
  { id: 'INC-2478', severity: 'warning', title: 'Intermittent telemetry gap', shipment: 'CCS-MSP-6193', product: 'Cultured dairy', sensor: 'SEN-2B09', temperature: 4.1, allowedMin: 1, allowedMax: 5, breachMinutes: 0, state: 'investigating', governance: 'fallback', createdMinutesAgo: 71, reviewer: 'Ari Okafor', route: { from: 'Minneapolis', via: 'In transit', to: 'Kansas City', progress: 57 }, productSensitivity: 'Medium · short excursion tolerance', sensorHealth: 'Degraded · stale packets detected', stale: true },
  { id: 'INC-2477', severity: 'normal', title: 'Duplicate delivery suppressed', shipment: 'CCS-DAL-9014', product: 'Insulin pens', sensor: 'SEN-5C60', temperature: 5.2, allowedMin: 2, allowedMax: 8, breachMinutes: 0, state: 'completed', governance: 'allowed', createdMinutesAgo: 126, reviewer: 'Maya Chen', route: { from: 'Dallas', via: 'In transit', to: 'Phoenix', progress: 100 }, productSensitivity: 'High · temperature controlled', sensorHealth: 'Nominal · duplicate sequence isolated', duplicate: true },
  { id: 'INC-2476', severity: 'critical', title: 'Immediate critical excursion', shipment: 'CCS-CHI-3388', product: 'Fresh dairy cultures', sensor: 'SEN-8F14', temperature: 13.2, allowedMin: 2, allowedMax: 6, breachMinutes: 4, state: 'rejected', governance: 'blocked', createdMinutesAgo: 188, reviewer: 'Jon Bell', route: { from: 'Chicago', via: 'In transit', to: 'Denver', progress: 74 }, productSensitivity: 'High · viability sensitive', sensorHealth: 'Nominal · custody gap upstream', breachKind: 'immediate' },
  { id: 'INC-2475', severity: 'normal', title: 'Brief threshold warning cleared', shipment: 'CCS-SEA-2290', product: 'Specialty cheese', sensor: 'SEN-4E72', temperature: 3.8, allowedMin: 1, allowedMax: 6, breachMinutes: 0, state: 'completed', governance: 'allowed', createdMinutesAgo: 243, reviewer: 'Ari Okafor', route: { from: 'Seattle', via: 'In transit', to: 'Chicago', progress: 92 }, productSensitivity: 'Low · recovered in policy window', sensorHealth: 'Nominal · battery 71%' },
  { id: 'INC-2474', severity: 'warning', title: 'Recommendation expired', shipment: 'CCS-DAL-4422', product: 'Vaccine adjuvant', sensor: 'SEN-1A08', temperature: 8.6, allowedMin: 2, allowedMax: 8, breachMinutes: 11, state: 'awaiting-review', governance: 'blocked', createdMinutesAgo: 302, reviewer: 'Maya Chen', route: { from: 'Dallas', via: 'In transit', to: 'Phoenix', progress: 61 }, productSensitivity: 'High · limited excursion budget', sensorHealth: 'Nominal · calibrated 4 days ago' },
];

export const liveTelemetry: LiveTelemetryRow[] = [
  { id: 'CCS-CHI-1842', route: 'Chicago → Denver', product: 'mRNA vaccine', temperature: 11.8, allowedMin: 2, allowedMax: 8, state: 'critical', lastReading: '12 sec ago', trend: [5.2, 6.4, 8.3, 9.7, 11.2, 11.8] },
  { id: 'CCS-PNW-3107', route: 'Seattle → Chicago', product: 'Fresh seafood', temperature: 7.2, allowedMin: 0, allowedMax: 4, state: 'warning', lastReading: '28 sec ago', trend: [3.1, 3.6, 4.2, 5.1, 6.4, 7.2] },
  { id: 'CCS-BOS-6620', route: 'Boston → New York', product: 'Frozen biologics', temperature: -18.4, allowedMin: -25, allowedMax: -15, state: 'normal', lastReading: '41 sec ago', trend: [-19.2, -18.9, -18.7, -18.8, -18.5, -18.4] },
];

export const readings: TemperaturePoint[] = [
  { minute: -70, temperature: 4.2, status: 'normal' }, { minute: -60, temperature: 4.4, status: 'normal' },
  { minute: -50, temperature: 5.1, status: 'normal' }, { minute: -45, temperature: 8.4, status: 'warning' },
  { minute: -40, temperature: 9.2, status: 'warning' }, { minute: -35, temperature: 10.5, status: 'critical' },
  { minute: -30, temperature: 11.2, status: 'critical' }, { minute: -25, temperature: 11.8, status: 'critical' },
  { minute: -20, temperature: 11.6, status: 'critical', outOfOrder: true }, { minute: -15, temperature: 11.9, status: 'critical' },
  { minute: -10, temperature: 11.7, status: 'critical' }, { minute: -5, temperature: 11.8, status: 'critical', stale: true },
  { minute: 0, temperature: 11.8, status: 'critical' },
];

export const evidence: EvidenceChunk[] = [
  { id: 'SOP-COLD-004#4.2', title: 'Temperature Excursion Response', section: '4.2 Immediate containment', version: 'v3.4', effectiveDate: '2026-04-01', score: 0.94, excerpt: 'Place temperature-sensitive inventory on quality hold when a continuous upper-bound excursion exceeds thirty minutes.', trusted: true },
  { id: 'SOP-VAX-012#7.1', title: 'Vaccine Shipment Disposition', section: '7.1 Evidence requirements', version: 'v2.1', effectiveDate: '2026-02-15', score: 0.89, excerpt: 'Disposition requires calibrated telemetry, custody confirmation, and a documented quality reviewer decision.', trusted: true },
  { id: 'NOTE-UNVERIFIED#2', title: 'Carrier handling note', section: 'Driver note', version: 'unversioned', effectiveDate: 'Not controlled', score: 0.42, excerpt: 'Cooling unit was inspected during the scheduled stop; no visible package damage was noted.', trusted: false },
];

export const governanceChecks: GovernanceCheck[] = [
  { name: 'Policy check', state: 'pass', detail: '47-minute excursion exceeds mandatory hold threshold.' },
  { name: 'Evidence check', state: 'pass', detail: 'Calibrated readings and custody events are aligned.' },
  { name: 'Citation check', state: 'pass', detail: 'Two trusted SOP chunks support the recommendation.' },
  { name: 'Schema check', state: 'pass', detail: 'All eight advisory fields validated locally.' },
  { name: 'Provider identity', state: 'pass', detail: 'Expected provider and model provenance verified.' },
  { name: 'Expiry check', state: 'pass', detail: 'Recommendation is valid for 08:42 more.' },
  { name: 'Kill-switch state', state: 'pass', detail: 'Operational commands are enabled for simulation.' },
  { name: 'Human approval', state: 'warning', detail: 'HOLD_SHIPMENT cannot execute without reviewer approval.' },
];

export const audit: AuditEvent[] = [
  ['evt-1', -52, 'telemetry-worker', 'Telemetry received', 'Reading 11.8°C accepted with monotonic sequence.'],
  ['evt-2', -51, 'policy-engine', 'Breach policy evaluated', 'Critical sustained-excursion rule matched.'],
  ['evt-3', -50, 'evidence-service', 'Evidence snapshot created', 'Sensor evidence was saved and locked.'],
  ['evt-4', -49, 'retrieval-service', 'SOP retrieval completed', 'Two trusted operating-procedure sections selected.'],
  ['evt-5', -48, 'recommendation-service', 'Recommendation created', 'Advisory HOLD_SHIPMENT recommendation validated.'],
  ['evt-6', -48, 'governance-engine', 'Governance evaluated', 'Safety rules checked the recommendation and required human approval.'],
  ['evt-7', -2, 'Maya Chen', 'Human review pending', 'Reviewer opened the decision workspace.'],
].map(([id, offsetMinutes, actor, type, summary], index) => ({ id: String(id), offsetMinutes: Number(offsetMinutes), actor: String(actor), type: String(type), summary: String(summary), correlationId: 'corr-7b42a1', traceId: `6d8f22a17b3c4e${index}` }));

export const dashboard: DashboardData = {
  mode: 'mock',
  incidents,
  liveTelemetry,
  generatedAt: new Date(0).toISOString(),
  services: [
    { name: 'API', state: 'healthy', latency: '42 ms', detail: 'Ready · 0.2% errors' },
    { name: 'Worker', state: 'healthy', latency: '18 ms', detail: '3 consumers active' },
    { name: 'PostgreSQL', state: 'healthy', latency: '7 ms', detail: 'Pool 4 / 20' },
    { name: 'Kafka', state: 'healthy', latency: '24 ms', detail: 'Consumer lag 3' },
    { name: 'Qdrant', state: 'healthy', latency: '31 ms', detail: 'Collection ready' },
    { name: 'Prometheus', state: 'healthy', latency: '—', detail: 'Targets 5 / 5', url: 'http://localhost:19090' },
    { name: 'Grafana', state: 'healthy', latency: '—', detail: 'Provisioned', url: 'http://localhost:13001' },
    { name: 'Jaeger', state: 'degraded', latency: '—', detail: '2 delayed spans', url: 'http://localhost:16687' },
  ],
  trend: [
    { hour: '00:00', incidents: 3, breaches: 1, awaitingReview: 1 }, { hour: '04:00', incidents: 5, breaches: 2, awaitingReview: 1 },
    { hour: '08:00', incidents: 8, breaches: 4, awaitingReview: 2 }, { hour: '12:00', incidents: 6, breaches: 3, awaitingReview: 1 },
    { hour: '16:00', incidents: 10, breaches: 5, awaitingReview: 3 }, { hour: '20:00', incidents: 7, breaches: 2, awaitingReview: 2 },
    { hour: 'Now', incidents: 8, breaches: 3, awaitingReview: 2 },
  ],
  recommendations: [
    { time: '2m ago', incident: 'INC-2481', action: 'HOLD_SHIPMENT', outcome: 'Awaiting human' },
    { time: '29m ago', incident: 'INC-2480', action: 'CONTINUE_MONITORING', outcome: 'Allowed' },
    { time: '1h ago', incident: 'INC-2478', action: 'REQUEST_INSPECTION', outcome: 'Fallback' },
    { time: '2h ago', incident: 'INC-2477', action: 'RELEASE_SHIPMENT', outcome: 'Completed' },
  ],
};

export const scenarios: Scenario[] = [
  ['healthy', 'Healthy shipment', 'Nominal telemetry and policy pass', 'No incident', 'No intervention', 'Observe', '~10 sec', 'healthy'],
  ['critical', 'Immediate critical breach', 'Hard critical threshold', 'Open critical incident', 'Approval required', 'Review hold', '~20 sec', 'critical'],
  ['sustained', 'Sustained temperature breach', 'Duration-based escalation', 'Create evidence snapshot', 'Approval required', 'Assess shipment', '~30 sec', 'critical'],
  ['stale', 'Stale telemetry', 'Freshness guardrail', 'Quarantine reading', 'Block recommendation', 'Inspect sensor', '~15 sec', 'stale'],
  ['duplicate', 'Duplicate delivery', 'Idempotent ingestion', 'Suppress duplicate', 'No new action', 'None', '~10 sec', 'duplicate'],
  ['conflict', 'Conflicting sensors', 'Cross-sensor validation', 'Escalate discrepancy', 'Block automation', 'Resolve conflict', '~25 sec', 'conflict'],
  ['insufficient', 'Insufficient SOP evidence', 'Retrieval sufficiency', 'Continue evidence search', 'Deterministic fallback', 'Provide evidence', '~20 sec', 'insufficient'],
  ['injection', 'Prompt-injection defense', 'Untrusted text isolation', 'Ignore embedded instruction', 'Block unsafe output', 'Review audit', '~20 sec', 'injection'],
  ['fallback', 'Provider failure & fallback', 'Advisory-provider failure', 'Deterministic recommendation', 'Policy remains authoritative', 'Review fallback', '~20 sec', 'fallback'],
  ['expired', 'Expired recommendation', 'Trusted expiry enforcement', 'Invalidate advice', 'Block approval', 'Request refresh', '~15 sec', 'expired'],
  ['unauthorized', 'Unauthorized approval', 'Role-based authority', 'Reject decision attempt', 'No command created', 'Escalate role', '~10 sec', 'unauthorized'],
  ['kill-switch', 'Kill switch enabled', 'Global execution control', 'Recommendation only', 'Command blocked', 'Investigate switch', '~10 sec', 'kill-switch'],
].map(([id, title, demonstrates, policyOutcome, governanceOutcome, humanAction, duration, variant]) => ({ id, title, demonstrates, policyOutcome, governanceOutcome, humanAction, duration, variant } as Scenario));

export function investigationFor(id: string): InvestigationData {
  const incident = incidents.find((item) => item.id === id) ?? incidents[0]!;
  const expired = incident.id === 'INC-2474';
  return {
    incident,
    readings,
    evidence,
    recommendation: {
      action: incident.severity === 'critical' ? 'HOLD_SHIPMENT' : 'CONTINUE_MONITORING',
      rationale: `Shipment has remained above its safe temperature for ${incident.breachMinutes} minutes. Hold it for inspection until a quality reviewer decides.`,
      evidenceSufficient: incident.governance !== 'blocked' || expired,
      uncertainty: incident.governance === 'fallback' ? 'medium' : 'low',
      missingInformation: incident.id === 'INC-2476' ? ['Upstream custody signature'] : [],
      contraindications: ['Do not release based on advisory output alone'],
      evidenceIds: ['SOP-COLD-004#4.2', 'SOP-VAX-012#7.1'],
      incidentEvidenceIds: ['reading-7a42-0914', 'custody-chi-03'],
      fallback: incident.governance === 'fallback',
      provider: 'Groq', model: 'openai/gpt-oss-20b', promptVersion: 'recommendation.v1', schemaVersion: '1.0.0',
      latencyMs: 842, tokens: 611, estimatedCost: '$0.0002', expiresInMinutes: expired ? 0 : 9, validation: expired ? 'expired' : 'valid',
    },
    governanceChecks: expired ? governanceChecks.map((check) => check.name === 'Expiry check' ? { ...check, state: 'failure', detail: 'Recommendation expired and cannot be approved.' } : check) : governanceChecks,
    audit,
  };
}
