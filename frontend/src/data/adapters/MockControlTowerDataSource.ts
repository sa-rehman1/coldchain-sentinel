import type { ControlTowerDataSource, DashboardData, DecisionResult, DemoRun, Incident, InvestigationData, ObservabilitySummary, PlatformHealth, Scenario } from '../contracts';
import { dashboard, incidents, investigationFor, liveTelemetry, scenarios } from '../fixtures';

const clone = <T,>(value: T): T => structuredClone(value);

export class MockControlTowerDataSource implements ControlTowerDataSource {
  readonly mode = 'mock' as const;
  async getDashboard(): Promise<DashboardData> { return Promise.resolve(clone({ ...dashboard, mode: 'mock' as const, liveTelemetry, generatedAt: new Date(0).toISOString() })); }
  async getIncidents(): Promise<Incident[]> { return Promise.resolve(clone(incidents)); }
  async getInvestigation(id: string): Promise<InvestigationData> { return Promise.resolve(clone(investigationFor(id))); }
  async getScenarios(): Promise<Scenario[]> { return Promise.resolve(clone(scenarios)); }
  async getHealth(): Promise<PlatformHealth> { return Promise.resolve({ api: 'healthy', ai: 'healthy', provider: 'Deterministic', model: 'deterministic-local-1.0', providerConfigured: true, liveCallsEnabled: false, fallbackAvailable: true, qdrant: 'ready' }); }
  async getObservabilitySummary(): Promise<ObservabilitySummary> { return Promise.resolve({ generatedAt: new Date(0).toISOString(), overallStatus: 'HEALTHY', healthyServices: 9, totalServices: 9, activeAlerts: 0, autoRefreshSeconds: 12, services: [], metrics: [], series: { apiRequestRate: [], apiP95Latency: [], workerThroughput: [], dlqActivity: [] }, alerts: { state: 'AVAILABLE', rules: [] }, traces: { state: 'NO_SAMPLES', items: [] }, privacyNotice: 'Demonstration data contains no sensitive payloads.' }); }
  async decide(_id: string, _recommendationId: string, decision: 'approve' | 'reject'): Promise<DecisionResult> { return Promise.resolve({ approvalId: 'fixture-approval', decision: decision === 'approve' ? 'APPROVED' : 'REJECTED', idempotentReplay: false, commandId: decision === 'approve' ? 'fixture-command' : null, status: decision === 'approve' ? 'SUCCEEDED' : null, actionResult: decision === 'approve' ? { resultId: 'fixture-result', status: 'SUCCEEDED', adapter: 'fixture', detail: 'simulated shipment hold applied', completedAt: new Date(0).toISOString() } : null }); }
  async startScenario(id: string): Promise<DemoRun> {
    const requiresReview = ['critical', 'sustained', 'fallback'].includes(id);
    return Promise.resolve({
      runId: `mock-${id}`,
      scenarioId: id,
      correlationId: 'mock-correlation',
      shipmentId: 'CCS-DEMO-2048',
      eventIds: ['mock-event'],
      publishCount: 1,
      status: requiresReview ? 'INCIDENT_READY' : 'COMPLETED_WITHOUT_INCIDENT',
      processedEventCount: 1,
      dispositions: requiresReview ? ['BREACH'] : ['ACCEPTED'],
      incidentId: requiresReview ? `SIM-${id.toUpperCase()}` : null,
      incidentReference: requiresReview ? `SIM-${id.toUpperCase()}` : null,
      shipmentReference: requiresReview ? 'CCS-DEMO-2048' : null,
      incidentSeverity: id === 'critical' ? 'CRITICAL' : requiresReview ? 'HIGH' : null,
      governanceDecision: requiresReview ? 'APPROVAL_REQUIRED' : null,
      humanDecisionRecorded: false,
      resultState: requiresReview ? 'AWAITING_HUMAN_REVIEW' : 'COMPLETE',
      steps: {
        sensorReading: 'COMPLETED',
        policyCheck: 'COMPLETED',
        incidentCreated: requiresReview ? 'COMPLETED' : 'NOT_REQUIRED',
        evidenceCollected: requiresReview ? 'COMPLETED' : 'NOT_REQUIRED',
        aiAdvisory: requiresReview ? 'COMPLETED' : 'NOT_REQUIRED',
        governance: requiresReview ? 'COMPLETED' : 'NOT_REQUIRED',
        humanReview: requiresReview ? 'PENDING' : 'NOT_REQUIRED',
      },
    });
  }
  async getDemoRun(runId: string): Promise<DemoRun> { return this.startScenario(runId.replace('mock-', '')); }
}
