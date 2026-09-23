import type {
  ControlTowerDataSource,
  DashboardData,
  DecisionResult,
  DemoRun,
  Incident,
  InvestigationData,
  LocalIdentity,
  PlatformHealth,
  Scenario,
} from '../contracts';
import { ApiClient } from './client';
import { mapIncident, mapInvestigation } from './mappers';
import {
  aiHealthSchema,
  decisionSchema,
  demoRunSchema,
  incidentSchema,
  incidentsSchema,
  liveHealthSchema,
  scenariosSchema,
  timelineSchema,
} from './schemas';

const scenarioVariant = (id: string): Scenario['variant'] => {
  if (id === 'critical' || id === 'sustained') return 'critical';
  if (id === 'stale') return 'stale';
  if (id === 'duplicate') return 'duplicate';
  if (id === 'fallback') return 'fallback';
  return 'healthy';
};

const demoRun = (value: unknown): DemoRun => {
  const run = demoRunSchema.parse(value);
  return {
    runId: run.runId,
    scenarioId: run.scenarioId,
    correlationId: run.correlationId,
    shipmentId: run.shipmentId,
    eventIds: run.eventIds,
    publishCount: run.publishCount,
    status: run.status,
    processedEventCount: run.processedEventCount,
    dispositions: run.dispositions,
    incidentId: run.incident?.incidentId ?? null,
    steps: run.steps,
  };
};

export class HttpControlTowerDataSource implements ControlTowerDataSource {
  readonly mode = 'api' as const;

  constructor(private readonly client = new ApiClient()) {}

  async getIncidents(signal?: AbortSignal): Promise<Incident[]> {
    const values = await this.client.request('/incidents', incidentsSchema, { signal });
    return values.map(mapIncident);
  }

  async getDashboard(signal?: AbortSignal): Promise<DashboardData> {
    const [incidents, health] = await Promise.all([this.getIncidents(signal), this.getHealth(signal)]);
    return {
      mode: 'api',
      incidents,
      services: [
        { name: 'FastAPI', state: health.api, latency: 'Not reported', detail: 'Local application API' },
        { name: 'Recommendation provider', state: health.ai, latency: 'Not reported', detail: health.liveCallsEnabled ? health.provider : 'Deterministic fallback active' },
        { name: 'Qdrant', state: health.qdrant === 'ready' ? 'healthy' : 'degraded', latency: 'Not reported', detail: health.qdrant },
      ],
      trend: [],
      recommendations: incidents.filter((item) => item.recommendationId && item.recommendedAction).slice(0, 8).map((item) => ({ time: `${item.createdMinutesAgo}m ago`, incident: item.id, action: item.recommendedAction!, outcome: item.state === 'completed' ? 'Completed' : item.governance === 'approval-required' ? 'Awaiting review' : item.governance })),
      liveTelemetry: incidents.filter((item) => item.temperature !== null && item.allowedMax !== null).slice(0, 6).map((item) => ({ id: item.shipment, route: item.route ? `${item.route.from} → ${item.route.to}` : 'Route not reported', product: item.product ?? 'Not reported', temperature: item.temperature!, allowedMin: item.allowedMin, allowedMax: item.allowedMax!, state: item.severity, lastReading: `${item.createdMinutesAgo}m ago`, trend: [] })),
      generatedAt: new Date().toISOString(),
    };
  }

  async getInvestigation(id: string, signal?: AbortSignal): Promise<InvestigationData> {
    const [incident, timeline] = await Promise.all([
      this.client.request(`/incidents/${encodeURIComponent(id)}`, incidentSchema, { signal }),
      this.client.request(`/incidents/${encodeURIComponent(id)}/timeline`, timelineSchema, { signal }),
    ]);
    return mapInvestigation(incident, timeline);
  }

  async getScenarios(identity?: LocalIdentity, signal?: AbortSignal): Promise<Scenario[]> {
    if (!identity) throw new Error('A local demonstration identity is required.');
    const values = await this.client.request('/demo/scenarios', scenariosSchema, { identity, signal });
    return values.map((item) => ({ id: item.scenarioId, title: item.title, demonstrates: item.description, policyOutcome: item.expectedOutcome, governanceOutcome: item.expectedOutcome, humanAction: item.humanAction, duration: 'Processing time varies', variant: scenarioVariant(item.scenarioId) }));
  }

  async getHealth(signal?: AbortSignal): Promise<PlatformHealth> {
    const [live, ai] = await Promise.all([
      this.client.request('/health/live', liveHealthSchema, { signal }),
      this.client.request('/health/ai', aiHealthSchema, { signal }),
    ]);
    return { api: live.status === 'alive' ? 'healthy' : 'offline', ai: ai.fallback_available ? 'healthy' : 'degraded', provider: ai.selected_provider, providerConfigured: ai.provider_configured, liveCallsEnabled: ai.live_calls_enabled, fallbackAvailable: ai.fallback_available, qdrant: ai.qdrant_readiness };
  }

  async decide(id: string, recommendationId: string, decision: 'approve' | 'reject', rationale: string, idempotencyKey: string, identity: LocalIdentity): Promise<DecisionResult> {
    const result = await this.client.request(`/incidents/${encodeURIComponent(id)}/recommendations/${encodeURIComponent(recommendationId)}/${decision}`, decisionSchema, { method: 'POST', identity, body: { rationale, idempotencyKey } });
    return { approvalId: result.approvalId, decision: result.decision, idempotentReplay: result.idempotentReplay, commandId: result.commandId ?? null, status: result.status ?? null, actionResult: result.actionResult ?? null };
  }

  async startScenario(id: string, identity: LocalIdentity): Promise<DemoRun> {
    return demoRun(await this.client.request(`/demo/scenarios/${encodeURIComponent(id)}`, demoRunSchema, { method: 'POST', identity }));
  }

  async getDemoRun(runId: string, identity: LocalIdentity, signal?: AbortSignal): Promise<DemoRun> {
    return demoRun(await this.client.request(`/demo/runs/${encodeURIComponent(runId)}`, demoRunSchema, { identity, signal }));
  }
}
