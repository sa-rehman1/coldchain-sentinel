import type { ControlTowerDataSource, DashboardData, DecisionResult, DemoRun, Incident, InvestigationData, PlatformHealth, Scenario } from '../contracts';
import { dashboard, incidents, investigationFor, liveTelemetry, scenarios } from '../fixtures';

const clone = <T,>(value: T): T => structuredClone(value);

export class MockControlTowerDataSource implements ControlTowerDataSource {
  readonly mode = 'mock' as const;
  async getDashboard(): Promise<DashboardData> { return Promise.resolve(clone({ ...dashboard, mode: 'mock' as const, liveTelemetry, generatedAt: new Date(0).toISOString() })); }
  async getIncidents(): Promise<Incident[]> { return Promise.resolve(clone(incidents)); }
  async getInvestigation(id: string): Promise<InvestigationData> { return Promise.resolve(clone(investigationFor(id))); }
  async getScenarios(): Promise<Scenario[]> { return Promise.resolve(clone(scenarios)); }
  async getHealth(): Promise<PlatformHealth> { return Promise.resolve({ api: 'healthy', ai: 'healthy', provider: 'Deterministic', model: 'deterministic-local-1.0', providerConfigured: true, liveCallsEnabled: false, fallbackAvailable: true, qdrant: 'ready' }); }
  async decide(_id: string, _recommendationId: string, decision: 'approve' | 'reject'): Promise<DecisionResult> { return Promise.resolve({ approvalId: 'prototype-approval', decision: decision === 'approve' ? 'APPROVED' : 'REJECTED', idempotentReplay: false, commandId: decision === 'approve' ? 'prototype-command' : null, status: decision === 'approve' ? 'SUCCEEDED' : null, actionResult: decision === 'approve' ? { resultId: 'prototype-result', status: 'SUCCEEDED', adapter: 'prototype', detail: 'simulated shipment hold applied', completedAt: new Date(0).toISOString() } : null }); }
  async startScenario(id: string): Promise<DemoRun> { return Promise.resolve({ runId: `mock-${id}`, scenarioId: id, correlationId: 'mock-correlation', shipmentId: 'CCS-DEMO-2048', eventIds: ['mock-event'], publishCount: 1, status: 'INCIDENT_READY', processedEventCount: 1, dispositions: ['BREACH'], incidentId: `SIM-${id.toUpperCase()}`, steps: { telemetrySubmitted: true, eventAccepted: true, policyEvaluated: true, evidenceCollected: true, recommendationCreated: true, governanceCompleted: true, incidentReady: true } }); }
  async getDemoRun(runId: string): Promise<DemoRun> { return this.startScenario(runId.replace('mock-', '')); }
}
