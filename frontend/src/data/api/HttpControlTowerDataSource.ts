import type {
  Action,
  ControlTowerDataSource,
  DashboardData,
  DecisionResult,
  DemoRun,
  Incident,
  InvestigationData,
  LocalIdentity,
  ObservabilitySummary,
  PlatformHealth,
  Scenario,
} from '../contracts';
import { ApiClient } from './client';
import { mapIncident, mapInvestigation } from './mappers';
import {
  aiHealthSchema,
  dashboardSchema,
  decisionSchema,
  demoRunSchema,
  incidentSchema,
  incidentsSchema,
  liveHealthSchema,
  observabilitySummarySchema,
  scenariosSchema,
  timelineSchema,
} from './schemas';

const providerLabel = (provider: string): string => ({ openai: 'OpenAI', groq: 'Groq', deterministic: 'Deterministic' })[provider] ?? provider;

const hasRecommendation = (incident: Incident): incident is Incident & { recommendationId: string; recommendedAction: Action } =>
  typeof incident.recommendationId === 'string' && incident.recommendedAction !== undefined;

const action = (value: string | null | undefined): Action | undefined =>
  value === 'HOLD_SHIPMENT' || value === 'CONTINUE_MONITORING' || value === 'REQUEST_INSPECTION' || value === 'RELEASE_SHIPMENT' ? value : undefined;

const workflowState = (value: string): Incident['state'] => {
  if (value === 'AWAITING_APPROVAL') return 'awaiting-review';
  if (value === 'REJECTED') return 'rejected';
  if (value === 'RESOLVED') return 'completed';
  if (value === 'OPEN' || value === 'EVIDENCE_COLLECTED' || value === 'APPROVED' || value === 'EXECUTING') return 'investigating';
  return 'triage';
};

const governanceDecision = (value: string | null | undefined): Incident['governance'] => {
  if (value === 'APPROVAL_REQUIRED') return 'approval-required';
  if (value === 'ALLOWED') return 'allowed';
  if (value === 'PROHIBITED' || value === 'KILL_SWITCH_ACTIVE') return 'blocked';
  return 'fallback';
};

const minutesAgo = (timestamp: string, generatedAt: string): string => {
  const elapsed = Math.max(0, Math.floor((Date.parse(generatedAt) - Date.parse(timestamp)) / 60_000));
  if (elapsed < 1) return 'Just now';
  return `${elapsed} min ago`;
};

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
    incidentId: run.incidentId ?? run.incident?.incidentId ?? null,
    incidentReference: run.incidentReference,
    shipmentReference: run.shipmentReference,
    incidentSeverity: run.incidentSeverity,
    governanceDecision: run.governanceDecision,
    humanDecisionRecorded: run.humanDecisionRecorded,
    resultState: run.resultState,
    steps: run.steps,
  };
};

export class HttpControlTowerDataSource implements ControlTowerDataSource {
  readonly mode = 'api' as const;

  constructor(private readonly client = new ApiClient()) {}

  async getIncidents(signal?: AbortSignal): Promise<Incident[]> {
    const values = await this.client.request('/incidents?scope=canonical-showcase', incidentsSchema, { signal });
    return values.map(mapIncident);
  }

  async getDashboard(signal?: AbortSignal): Promise<DashboardData> {
    const [dashboard, health] = await Promise.all([
      this.client.request('/dashboard', dashboardSchema, { signal }),
      this.getHealth(signal),
    ]);
    const incidents: Incident[] = dashboard.latestShipments.map((item) => {
      const recommendedAction = action(item.recommendedAction);
      return {
        id: item.incidentId,
        reference: item.incidentReference,
        shipment: item.shipmentReference,
        title: item.reasonCodes.includes('CLEARLY_UNSAFE_TEMPERATURE') ? 'Immediate critical temperature breach' : item.state === 'RESOLVED' ? 'Temperature excursion resolved' : 'Sustained temperature excursion',
        product: item.product,
        sensor: null,
        temperature: item.currentTemperatureCelsius,
        allowedMin: item.permittedMinCelsius,
        allowedMax: item.permittedMaxCelsius,
        breachMinutes: null,
        state: workflowState(item.state),
        severity: item.severity === 'CRITICAL' ? 'critical' : item.severity === 'HIGH' || item.severity === 'MEDIUM' ? 'warning' : 'normal',
        governance: governanceDecision(item.governanceDecision),
        createdMinutesAgo: item.ageMinutes,
        reviewer: null,
        route: { from: item.route.origin, via: item.route.via, to: item.route.destination, progress: item.route.progress },
        productSensitivity: null,
        sensorHealth: null,
        ...(recommendedAction ? { recommendedAction } : {}),
        ...(item.recommendationExpiresAt ? { recommendationExpiresAt: item.recommendationExpiresAt } : {}),
        breachKind: item.reasonCodes.includes('CLEARLY_UNSAFE_TEMPERATURE') ? 'immediate' : 'sustained',
      };
    });
    return {
      mode: 'api',
      incidents,
      services: [
        { name: 'FastAPI', state: health.api, latency: 'Not reported', detail: 'Local application API' },
        { name: 'Recommendation provider', state: health.ai, latency: 'Not reported', detail: health.liveCallsEnabled ? health.provider : 'Deterministic fallback active' },
        { name: 'Qdrant', state: health.qdrant === 'ready' ? 'healthy' : 'degraded', latency: 'Not reported', detail: health.qdrant },
      ],
      metrics: dashboard.metrics,
      severityDistribution: dashboard.severityDistribution,
      approvalQueue: dashboard.approvalQueue,
      trend: dashboard.activity.map((item) => ({ hour: item.label, critical: item.critical, warning: item.warning, resolved: item.resolved })),
      recommendations: incidents.filter(hasRecommendation).map((item) => ({ time: `${item.createdMinutesAgo}m ago`, incident: item.reference ?? item.id, action: item.recommendedAction, outcome: item.state === 'completed' ? 'Completed' : item.governance === 'approval-required' ? 'Awaiting review' : item.governance })),
      humanDecisions: dashboard.humanDecisions,
      liveTelemetry: dashboard.latestShipments.map((item) => ({ id: item.shipmentReference, route: `${item.route.origin} → ${item.route.destination}`, product: item.product, temperature: item.currentTemperatureCelsius, allowedMin: item.permittedMinCelsius, allowedMax: item.permittedMaxCelsius, state: item.severity === 'CRITICAL' ? 'critical' : item.severity === 'HIGH' || item.severity === 'MEDIUM' ? 'warning' : 'normal', lastReading: minutesAgo(item.lastReadingAt, dashboard.generatedAt), trend: item.trendCelsius })),
      generatedAt: dashboard.generatedAt,
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
    return { api: live.status === 'alive' ? 'healthy' : 'offline', ai: ai.fallback_available ? 'healthy' : 'degraded', provider: providerLabel(ai.selected_provider), model: ai.selected_model, providerConfigured: ai.provider_configured, liveCallsEnabled: ai.live_calls_enabled, fallbackAvailable: ai.fallback_available, qdrant: ai.qdrant_readiness };
  }

  async getObservabilitySummary(signal?: AbortSignal): Promise<ObservabilitySummary> {
    return this.client.request('/observability/summary', observabilitySummarySchema, { signal });
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
