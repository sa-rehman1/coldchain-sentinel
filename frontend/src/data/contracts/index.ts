export type Severity = 'critical' | 'warning' | 'normal';
export type WorkflowState = 'triage' | 'investigating' | 'awaiting-review' | 'rejected' | 'completed';
export type GovernanceDecision = 'approval-required' | 'allowed' | 'blocked' | 'fallback';
export type Action = 'HOLD_SHIPMENT' | 'CONTINUE_MONITORING' | 'REQUEST_INSPECTION' | 'RELEASE_SHIPMENT';
export type ServiceState = 'healthy' | 'degraded' | 'offline';

export interface Incident {
  id: string;
  severity: Severity;
  title: string;
  shipment: string;
  product: string;
  sensor: string;
  temperature: number;
  allowedMin: number;
  allowedMax: number;
  breachMinutes: number;
  state: WorkflowState;
  governance: GovernanceDecision;
  createdMinutesAgo: number;
  reviewer: string | null;
  route: { from: string; via: string; to: string; progress: number };
  productSensitivity: string;
  sensorHealth: string;
  stale?: boolean;
  duplicate?: boolean;
  breachKind?: 'sustained' | 'immediate' | 'none';
}

export interface LiveTelemetryRow {
  id: string;
  route: string;
  product: string;
  temperature: number;
  allowedMin: number;
  allowedMax: number;
  state: Severity;
  lastReading: string;
  trend: number[];
}

export interface TemperaturePoint {
  minute: number;
  temperature: number;
  status: Severity;
  stale?: boolean;
  outOfOrder?: boolean;
}

export interface EvidenceChunk {
  id: string;
  title: string;
  section: string;
  version: string;
  effectiveDate: string;
  score: number;
  excerpt: string;
  trusted: boolean;
}

export interface Recommendation {
  action: Action;
  rationale: string;
  evidenceSufficient: boolean;
  uncertainty: 'low' | 'medium' | 'high';
  missingInformation: string[];
  contraindications: string[];
  evidenceIds: string[];
  incidentEvidenceIds: string[];
  fallback: boolean;
  provider: string;
  model: string;
  promptVersion: string;
  schemaVersion: string;
  latencyMs: number;
  tokens: number;
  estimatedCost: string;
  expiresInMinutes: number;
  validation: 'valid' | 'expired' | 'invalid';
}

export interface GovernanceCheck {
  name: string;
  state: 'pass' | 'warning' | 'failure';
  detail: string;
}

export interface AuditEvent {
  id: string;
  offsetMinutes: number;
  actor: string;
  type: string;
  summary: string;
  correlationId: string;
  traceId: string;
}

export interface ServiceHealth {
  name: string;
  state: ServiceState;
  latency: string;
  detail: string;
  url?: string;
}

export interface Scenario {
  id: string;
  title: string;
  demonstrates: string;
  policyOutcome: string;
  governanceOutcome: string;
  humanAction: string;
  duration: string;
  variant: 'healthy' | 'critical' | 'stale' | 'duplicate' | 'conflict' | 'insufficient' | 'injection' | 'fallback' | 'expired' | 'unauthorized' | 'kill-switch';
}

export interface DashboardData {
  incidents: Incident[];
  services: ServiceHealth[];
  trend: Array<{ hour: string; incidents: number; breaches: number; awaitingReview: number }>;
  recommendations: Array<{ time: string; incident: string; action: Action; outcome: string }>;
}

export interface InvestigationData {
  incident: Incident;
  readings: TemperaturePoint[];
  evidence: EvidenceChunk[];
  recommendation: Recommendation;
  governanceChecks: GovernanceCheck[];
  audit: AuditEvent[];
}

export interface ControlTowerDataSource {
  getDashboard(): Promise<DashboardData>;
  getIncidents(): Promise<Incident[]>;
  getInvestigation(id: string): Promise<InvestigationData>;
  getScenarios(): Promise<Scenario[]>;
}
