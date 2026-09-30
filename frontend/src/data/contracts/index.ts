export type Severity = 'critical' | 'warning' | 'normal';
export type WorkflowState = 'triage' | 'investigating' | 'awaiting-review' | 'rejected' | 'completed';
export type GovernanceDecision = 'approval-required' | 'allowed' | 'blocked' | 'fallback';
export type Action = 'HOLD_SHIPMENT' | 'CONTINUE_MONITORING' | 'REQUEST_INSPECTION' | 'RELEASE_SHIPMENT';
export type ServiceState = 'healthy' | 'degraded' | 'offline';

export interface IncidentEvidenceProfile {
  sensorHealth: string;
  calibration: string;
  sampleIntervalMinutes: number;
  readingQuality: string;
  productSensitivity: string;
  custodyVerification: string;
  complete: boolean;
}

export interface Incident {
  id: string;
  reference?: string;
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
  evidenceProfile?: IncidentEvidenceProfile | null;
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
  documentId?: string;
  title: string;
  section: string;
  version: string;
  effectiveDate: string;
  score: number | null;
  excerpt: string;
  trusted: boolean;
  whyApplicable?: string;
  validationStatus?: string;
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
  evidenceBundleReference?: string | null;
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
  actionability: {
    state: 'AWAITING_HUMAN_REVIEW' | 'EXPIRED' | 'DECIDED';
    approvalAllowed: boolean;
    rejectionAllowed: boolean;
    status: string;
    explanation: string;
  };
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
  occurredAt?: string;
  context?: string;
  hashChainVerified?: boolean;
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
  metrics: { affectedShipments: number; openIncidents: number; awaitingHumanReview: number };
  severityDistribution: { critical: number; warning: number; normal: number };
  approvalQueue: { pending: number; oldestWaitingMinutes: number; expiringWithin15Minutes: number };
  trend: Array<{ hour: string; critical: number; warning: number; resolved: number }>;
  recommendations: Array<{ time: string; incident: string; action: Action; outcome: string }>;
  humanDecisions: Array<{ incidentId: string; incidentReference: string; decision: string; reviewerRole: string; decidedAt: string }>;
  liveTelemetry: LiveTelemetryRow[];
  generatedAt: string;
}

export interface InvestigationData {
  incident: Incident;
  readings: TemperaturePoint[];
  evidence: EvidenceChunk[];
  recommendation: Recommendation;
  governanceChecks: GovernanceCheck[];
  governanceSummary?: {
    decision: string;
    policyVersion: string;
    evaluatedAt: string;
    authority: string;
  };
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
  incidentReference: string | null;
  shipmentReference: string | null;
  incidentSeverity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
  governanceDecision: string | null;
  humanDecisionRecorded: boolean;
  resultState: 'PROCESSING' | 'COMPLETE' | 'AWAITING_HUMAN_REVIEW' | 'BLOCKED' | 'FAILED';
  steps: {
    sensorReading: DemoStageState;
    policyCheck: DemoStageState;
    incidentCreated: DemoStageState;
    evidenceCollected: DemoStageState;
    aiAdvisory: DemoStageState;
    governance: DemoStageState;
    humanReview: DemoStageState;
  };
}

export type DemoStageState = 'PENDING' | 'COMPLETED' | 'NOT_REQUIRED' | 'BLOCKED' | 'FAILED';

export interface PlatformHealth {
  api: ServiceState;
  ai: ServiceState;
  provider: string;
  model: string;
  providerConfigured: boolean;
  liveCallsEnabled: boolean;
  fallbackAvailable: boolean;
  qdrant: string;
}

export type ObservabilityAvailability = 'AVAILABLE' | 'NO_SAMPLES' | 'UNAVAILABLE';
export type ObservabilityServiceStatus = 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'OPTIONAL_NOT_STARTED';

export interface ObservabilitySummary {
  generatedAt: string;
  overallStatus: 'HEALTHY' | 'DEGRADED';
  healthyServices: number;
  totalServices: number;
  activeAlerts: number;
  autoRefreshSeconds: number;
  services: Array<{ name: string; status: ObservabilityServiceStatus; signal: string; measurement: number | null; measurementUnit: string | null; checkedAt: string; inspectionUrl: string | null }>;
  metrics: Array<{ key: string; label: string; value: number | null; unit: string; state: ObservabilityAvailability; source: string }>;
  series: { apiRequestRate: Array<{ timestamp: string; value: number }>; apiP95Latency: Array<{ timestamp: string; value: number }>; workerThroughput: Array<{ timestamp: string; value: number }>; dlqActivity: Array<{ timestamp: string; value: number }> };
  alerts: { state: 'AVAILABLE' | 'UNAVAILABLE'; rules: Array<{ name: string; state: string; severity: string; summary: string }> };
  traces: { state: ObservabilityAvailability; items: Array<{ traceId: string; operation: string; durationMs: number; spanCount: number; startedAt: string }> };
  privacyNotice: string;
}

export interface ControlTowerDataSource {
  readonly mode: 'mock' | 'api';
  getDashboard(signal?: AbortSignal): Promise<DashboardData>;
  getIncidents(signal?: AbortSignal): Promise<Incident[]>;
  getInvestigation(id: string, signal?: AbortSignal): Promise<InvestigationData>;
  getScenarios(identity?: LocalIdentity, signal?: AbortSignal): Promise<Scenario[]>;
  getHealth(signal?: AbortSignal): Promise<PlatformHealth>;
  getObservabilitySummary(signal?: AbortSignal): Promise<ObservabilitySummary>;
  decide(id: string, recommendationId: string, decision: 'approve' | 'reject', rationale: string, idempotencyKey: string, identity: LocalIdentity): Promise<DecisionResult>;
  startScenario(id: string, identity: LocalIdentity): Promise<DemoRun>;
  getDemoRun(runId: string, identity: LocalIdentity, signal?: AbortSignal): Promise<DemoRun>;
}
