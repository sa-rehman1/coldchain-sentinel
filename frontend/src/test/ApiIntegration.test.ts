import { z } from 'zod';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../data/api/client';
import { HttpControlTowerDataSource } from '../data/api/HttpControlTowerDataSource';
import { mapIncident } from '../data/api/mappers';
import { incidentSchema } from '../data/api/schemas';
import type { LocalIdentity } from '../data/contracts';

const identity: LocalIdentity = { label: 'Dispatcher', actorId: 'dispatcher:test', roles: ['dispatcher'] };
const incidentPayload = {
  incidentId: '00000000-0000-4000-8000-000000000001',
  shipmentId: '00000000-0000-4000-8000-000000000002',
  state: 'AWAITING_APPROVAL',
  severity: 'CRITICAL',
  policyVersion: 'temperature-v1',
  sourceEventIds: ['00000000-0000-4000-8000-000000000003'],
  correlationId: '00000000-0000-4000-8000-000000000004',
  createdAt: '2026-09-21T12:00:00Z',
  updatedAt: '2026-09-21T12:00:00Z',
  telemetry: [],
};
const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'X-Correlation-ID': '00000000-0000-4000-8000-000000000009' } });
const dashboardPayload = {
  generatedAt: '2026-09-24T12:00:00Z',
  scope: 'canonical-showcase',
  metrics: { affectedShipments: 1, openIncidents: 1, awaitingHumanReview: 1 },
  severityDistribution: { critical: 1, warning: 0, normal: 0 },
  latestShipments: [{
    incidentId: '00000000-0000-4000-8000-000000000001', incidentReference: 'INC-1001', shipmentId: '00000000-0000-4000-8000-000000000002', shipmentReference: 'CCS-1001',
    route: { origin: 'Austin', via: 'Waco', destination: 'Dallas', progress: 68 }, product: 'mRNA vaccines', currentTemperatureCelsius: 12.4, permittedMinCelsius: 2, permittedMaxCelsius: 8,
    state: 'AWAITING_APPROVAL', severity: 'CRITICAL', createdAt: '2026-09-24T11:42:00Z', updatedAt: '2026-09-24T11:42:00Z', lastReadingAt: '2026-09-24T11:58:00Z', ageMinutes: 18,
    trendCelsius: [4.2, 6.1, 9.7, 12.4], reasonCodes: ['CLEARLY_UNSAFE_TEMPERATURE'], recommendedAction: 'HOLD_SHIPMENT', governanceDecision: 'APPROVAL_REQUIRED', recommendationExpiresAt: '2026-09-24T12:12:00Z',
  }],
  approvalQueue: { pending: 1, oldestWaitingMinutes: 18, expiringWithin15Minutes: 1 },
  humanDecisions: [],
  activity: [{ label: '11:50', startsAt: '2026-09-24T11:50:00Z', critical: 1, warning: 0, resolved: 0 }],
};
const observabilityPayload = {
  generatedAt: '2026-09-27T12:00:00Z', overallStatus: 'HEALTHY', healthyServices: 9, totalServices: 9, activeAlerts: 0, autoRefreshSeconds: 12,
  services: [{ name: 'Prometheus', status: 'HEALTHY', signal: 'Targets queried', measurement: null, measurementUnit: null, checkedAt: '2026-09-27T12:00:00Z', inspectionUrl: 'http://127.0.0.1:19090' }],
  metrics: [{ key: 'request_rate', label: 'Request rate', value: null, unit: 'requests/second', state: 'NO_SAMPLES', source: 'Prometheus' }],
  series: { apiRequestRate: [], apiP95Latency: [], workerThroughput: [], dlqActivity: [] },
  alerts: { state: 'AVAILABLE', rules: [] }, traces: { state: 'NO_SAMPLES', items: [] },
  privacyNotice: 'Sensitive content is excluded.',
};

afterEach(() => vi.unstubAllGlobals());

describe('authoritative API boundary', () => {
  it('validates the observability summary and forwards cancellation to the same-origin request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(observabilityPayload));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();
    const summary = await new HttpControlTowerDataSource().getObservabilitySummary(controller.signal);
    expect(summary.services[0]?.inspectionUrl).toBe('http://127.0.0.1:19090');
    expect(summary.metrics[0]).toMatchObject({ unit: 'requests/second', state: 'NO_SAMPLES' });
    const forwardedSignal = (fetchMock.mock.calls[0]?.[1] as RequestInit).signal;
    expect(forwardedSignal).toBeDefined();
    expect(forwardedSignal?.aborted).toBe(false);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/observability/summary');
  });

  it('validates responses and sends safe correlation and identity headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    await new ApiClient('/api/v1').request('/demo', z.object({ ok: z.literal(true) }), { identity });
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.headers).toMatchObject({ 'X-Actor-ID': 'dispatcher:test', 'X-Actor-Roles': 'dispatcher' });
    expect((init.headers as Record<string, string>)['X-Correlation-ID']).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('decodes structured errors and never retries a mutation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'workflow_conflict', message: 'Decision already finalized.', correlation_id: '00000000-0000-4000-8000-000000000009' } }, 409));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new ApiClient().request('/decision', z.object({ ok: z.boolean() }), { method: 'POST', body: {}, identity })).rejects.toMatchObject({ status: 409, code: 'workflow_conflict', message: 'Decision already finalized.' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('retries one safe read after a transient failure', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new ApiClient().request('/health', z.object({ ok: z.literal(true) }))).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('rejects schema drift and maps absent values without fabrication', () => {
    expect(() => incidentSchema.parse({ ...incidentPayload, unexpected: true })).toThrow();
    const mapped = mapIncident(incidentSchema.parse(incidentPayload));
    expect(mapped.temperature).toBeNull();
    expect(mapped.allowedMin).toBeNull();
    expect(mapped.route).toBeNull();
    expect(mapped.product).toBeNull();
    expect(mapped.evidenceProfile).toBeNull();
    expect(mapped.sensorHealth).toBeNull();
    expect(mapped.productSensitivity).toBeNull();
  });

  it('uses server-owned showcase labels and route metadata in incident views', () => {
    const mapped = mapIncident(incidentSchema.parse({
      ...incidentPayload,
      incidentReference: 'INC-1001',
      shipmentReference: 'CCS-1001',
      route: { origin: 'Austin', via: 'Waco', destination: 'Dallas', progress: 68 },
      productLabel: 'mRNA vaccines',
      sensorLabel: 'Probe 01',
      reviewerLabel: 'Dispatcher',
      evidenceProfile: {
        sensorHealth: 'Healthy',
        calibration: 'Verified',
        sampleIntervalMinutes: 10,
        readingQuality: 'No quality flags',
        productSensitivity: 'High',
        custodyVerification: 'Complete',
        complete: true,
      },
      approval: {
        approvalId: '00000000-0000-4000-8000-000000000007',
        recommendationId: '00000000-0000-4000-8000-000000000006',
        actorId: 'dispatcher:e2e',
        actorRole: 'dispatcher',
        decision: 'APPROVED',
        rationale: 'Reviewed',
        decidedAt: '2026-09-21T12:05:00Z',
      },
    }));
    expect(mapped).toMatchObject({
      id: incidentPayload.incidentId,
      reference: 'INC-1001',
      shipment: 'CCS-1001',
      product: 'mRNA vaccines',
      sensor: 'Probe 01',
      reviewer: 'Dispatcher',
      sensorHealth: 'Healthy',
      productSensitivity: 'High',
      evidenceProfile: { complete: true, calibration: 'Verified', sampleIntervalMinutes: 10 },
      route: { from: 'Austin', via: 'Waco', to: 'Dallas', progress: 68 },
    });
    expect(mapped.reviewer).not.toContain('dispatcher:');
  });

  it('requests and maps only the explicit canonical showcase incident scope', async () => {
    const payload = Array.from({ length: 4 }, (_, offset) => ({
      ...incidentPayload,
      incidentId: `00000000-0000-4000-8000-00000000000${offset + 1}`,
      shipmentId: `10000000-0000-4000-8000-00000000000${offset + 1}`,
      incidentReference: `INC-100${offset + 1}`,
      shipmentReference: `CCS-100${offset + 1}`,
      productLabel: `Showcase product ${offset + 1}`,
      sensorLabel: `Probe 0${offset + 1}`,
      reviewerLabel: offset === 3 ? 'Dispatcher' : 'Unassigned',
      evidenceProfile: {
        sensorHealth: 'Healthy', calibration: 'Verified', sampleIntervalMinutes: 10,
        readingQuality: 'No quality flags', productSensitivity: 'High',
        custodyVerification: 'Complete', complete: true,
      },
    }));
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal('fetch', fetchMock);

    const incidents = await new HttpControlTowerDataSource().getIncidents();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/incidents?scope=canonical-showcase');
    expect(incidents.map((item) => item.reference)).toEqual(['INC-1001', 'INC-1002', 'INC-1003', 'INC-1004']);
    expect(incidents.map((item) => item.shipment)).toEqual(['CCS-1001', 'CCS-1002', 'CCS-1003', 'CCS-1004']);
    expect(incidents.map((item) => item.sensor)).toEqual(['Probe 01', 'Probe 02', 'Probe 03', 'Probe 04']);
    expect(JSON.stringify(incidents.map(({ reference, shipment, sensor, reviewer }) => ({ reference, shipment, sensor, reviewer })))).not.toMatch(/dispatcher:|null|00000000-/);
  });

  it('maps the typed demo result without using the internal incident identity as its label', async () => {
    const incidentId = '6e621ba9-dd68-517e-881f-854688db3b1d';
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      runId: '00000000-0000-4000-8000-000000000010',
      scenarioId: 'sustained',
      correlationId: '00000000-0000-4000-8000-000000000011',
      shipmentId: '00000000-0000-4000-8000-000000000012',
      eventIds: ['00000000-0000-4000-8000-000000000013'],
      publishCount: 1,
      startedAt: '2026-09-28T12:00:00Z',
      status: 'INCIDENT_READY',
      processedEventCount: 1,
      dispositions: ['BREACH'],
      incident: null,
      incidentId,
      incidentReference: 'INC-DEMO-A1B2C3D4',
      shipmentReference: 'CCS-DEMO-E5F6A7B8',
      incidentSeverity: 'HIGH',
      governanceDecision: 'APPROVAL_REQUIRED',
      humanDecisionRecorded: false,
      resultState: 'AWAITING_HUMAN_REVIEW',
      steps: {
        sensorReading: 'COMPLETED', policyCheck: 'COMPLETED', incidentCreated: 'COMPLETED',
        evidenceCollected: 'COMPLETED', aiAdvisory: 'COMPLETED', governance: 'COMPLETED', humanReview: 'PENDING',
      },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await new HttpControlTowerDataSource().getDemoRun(
      '00000000-0000-4000-8000-000000000010',
      identity,
    );

    expect(result).toMatchObject({
      incidentId,
      incidentReference: 'INC-DEMO-A1B2C3D4',
      shipmentReference: 'CCS-DEMO-E5F6A7B8',
      incidentSeverity: 'HIGH',
      governanceDecision: 'APPROVAL_REQUIRED',
      humanDecisionRecorded: false,
      resultState: 'AWAITING_HUMAN_REVIEW',
      steps: { humanReview: 'PENDING' },
    });
    expect(result.incidentReference).not.toContain(incidentId);
  });

  it('submits decisions with the caller-provided stable idempotency key', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ approvalId: '00000000-0000-4000-8000-000000000005', decision: 'APPROVED', idempotentReplay: true, commandId: null, status: null, actionResult: null }));
    vi.stubGlobal('fetch', fetchMock);
    await new HttpControlTowerDataSource().decide(incidentPayload.incidentId, '00000000-0000-4000-8000-000000000006', 'approve', 'Reviewed evidence', 'stable-idempotency-key', identity);
    const rawBody = (fetchMock.mock.calls[0]![1] as RequestInit).body;
    expect(typeof rawBody).toBe('string');
    const body = JSON.parse(rawBody as string) as Record<string, unknown>;
    expect(body).toEqual({ rationale: 'Reviewed evidence', idempotencyKey: 'stable-idempotency-key' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('never substitutes mock incidents when the API is disconnected', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('offline'));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpControlTowerDataSource().getIncidents()).rejects.toMatchObject({ code: 'network_unavailable' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('uses the reconciled dashboard read model without exposing UUIDs as labels', async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith('/dashboard')) return Promise.resolve(jsonResponse(dashboardPayload));
      if (url.endsWith('/health/live')) return Promise.resolve(jsonResponse({ status: 'alive' }));
      return Promise.resolve(jsonResponse({ selected_provider: 'deterministic', selected_model: 'deterministic-local-1.0', provider_configured: true, live_calls_enabled: false, qdrant_readiness: 'ready', embedding_provider_readiness: 'ready', fallback_available: true }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const dashboard = await new HttpControlTowerDataSource().getDashboard();

    expect(dashboard.metrics).toEqual({ affectedShipments: 1, openIncidents: 1, awaitingHumanReview: 1 });
    expect(dashboard.humanDecisions).toEqual([]);
    expect(dashboard.incidents[0]).toMatchObject({ id: dashboardPayload.latestShipments[0]!.incidentId, reference: 'INC-1001', shipment: 'CCS-1001' });
    expect(dashboard.liveTelemetry[0]).toMatchObject({ id: 'CCS-1001', route: 'Austin → Dallas', lastReading: '2 min ago' });
    expect(dashboard.trend).toEqual([{ hour: '11:50', critical: 1, warning: 0, resolved: 0 }]);
    expect(JSON.stringify({ incidents: dashboard.incidents.map((item) => item.reference), telemetry: dashboard.liveTelemetry })).not.toContain(dashboardPayload.latestShipments[0]!.shipmentId);
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/incidents'))).toBe(false);
  });

  it('maps OpenAI health metadata without exposing credentials', async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith('/health/live')) return Promise.resolve(jsonResponse({ status: 'alive' }));
      return Promise.resolve(jsonResponse({ selected_provider: 'openai', selected_model: 'configured-model-id', provider_configured: true, live_calls_enabled: false, qdrant_readiness: 'ready', embedding_provider_readiness: 'ready', fallback_available: true }));
    });
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpControlTowerDataSource().getHealth()).resolves.toMatchObject({ provider: 'OpenAI', model: 'configured-model-id', providerConfigured: true, liveCallsEnabled: false, fallbackAvailable: true });
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain('api_key');
  });
});
