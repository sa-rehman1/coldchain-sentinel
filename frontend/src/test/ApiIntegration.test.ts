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

afterEach(() => vi.unstubAllGlobals());

describe('authoritative API boundary', () => {
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
