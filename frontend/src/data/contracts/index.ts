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
  product: string | null;
  sensor: string | null;
  temperature: number | null;
  allowedMin: number | null;
  allowedMax: number | null;
  breachMinutes: number | null;
  state: WorkflowState;
  governance: GovernanceDecision;
  createdMinutesAgo: number;
  reviewer: string | null;
  route: { from: string; via: string; to: string; progress: number } | null;
  productSensitivity: string | null;
  sensorHealth: string | null;
  recommendationId?: string;
  recommendedAction?: Action;
  recommendationExpiresAt?: string;
  correlationId?: string;
  stale?: boolean;
  duplicate?: boolean;
  breachKind?: 'sustained' | 'immediate' | 'none';
}

export interface LiveTelemetryRow {
  id: string;
  route: string;
  product: string;
  temperature: number;
  allowedMin: number | null;
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
  score: number | null;
  excerpt: string;
  trusted: boolean;
}

export interface Recommendation {
  action: Action;
  rationale: string;
  evidenceSufficient: boolean;
  uncertainty: 'low' | 'medium' | 'high';
  missingInformation: string[] | null;
  contraindications: string[] | null;
  evidenceIds: string[];
  incidentEvidenceIds: string[];
  fallback: boolean;
  provider: string;
  model: string;
  promptVersion: string;
  schemaVersion: string;
  latencyMs: number | null;
  tokens: number | null;
  estimatedCost: string | null;
  expiresInMinutes: number | null;
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
  mode: 'mock' | 'api';
  incidents: Incident[];
  services: ServiceHealth[];
  trend: Array<{ hour: string; incidents: number; breaches: number; awaitingReview: number }>;
  recommendations: Array<{ time: string; incident: string; action: Action; outcome: string }>;
  liveTelemetry: LiveTelemetryRow[];
  generatedAt: string;
}

export interface InvestigationData {
  incident: Incident;
  readings: TemperaturePoint[];
  evidence: EvidenceChunk[];
  recommendation: Recommendation;
  governanceChecks: GovernanceCheck[];
  audit: AuditEvent[];
  decision?: DecisionResult;
}

export interface LocalIdentity {
  label: 'Dispatcher' | 'Senior Reviewer' | 'Administrator' | 'Read-only Auditor';
  actorId: string;
  roles: string[];
}

export interface DecisionResult {
  approvalId: string;
  decision: 'APPROVED' | 'REJECTED';
  idempotentReplay: boolean;
  commandId: string | null;
  status: string | null;
  actionResult: { resultId: string; status: string; adapter: string; detail: string; completedAt: string } | null;
}

export interface DemoRun {
  runId: string;
  scenarioId: string;
  correlationId: string;
  shipmentId: string;
  eventIds: string[];
  publishCount: number;
  status: 'ACCEPTED' | 'PROCESSING' | 'INCIDENT_READY' | 'COMPLETED_WITHOUT_INCIDENT';
  processedEventCount: number;
  dispositions: string[];
  incidentId: string | null;
  steps: {
    telemetrySubmitted: boolean;
    eventAccepted: boolean;
    policyEvaluated: boolean;
    evidenceCollected: boolean;
    recommendationCreated: boolean;
    governanceCompleted: boolean;
    incidentReady: boolean;
  };
}

export interface PlatformHealth {
  api: ServiceState;
  ai: ServiceState;
  provider: string;
  providerConfigured: boolean;
  liveCallsEnabled: boolean;
  fallbackAvailable: boolean;
  qdrant: string;
}

export interface ControlTowerDataSource {
  readonly mode: 'mock' | 'api';
  getDashboard(signal?: AbortSignal): Promise<DashboardData>;
  getIncidents(signal?: AbortSignal): Promise<Incident[]>;
  getInvestigation(id: string, signal?: AbortSignal): Promise<InvestigationData>;
  getScenarios(identity?: LocalIdentity, signal?: AbortSignal): Promise<Scenario[]>;
  getHealth(signal?: AbortSignal): Promise<PlatformHealth>;
  decide(id: string, recommendationId: string, decision: 'approve' | 'reject', rationale: string, idempotencyKey: string, identity: LocalIdentity): Promise<DecisionResult>;
  startScenario(id: string, identity: LocalIdentity): Promise<DemoRun>;
  getDemoRun(runId: string, identity: LocalIdentity, signal?: AbortSignal): Promise<DemoRun>;
}
