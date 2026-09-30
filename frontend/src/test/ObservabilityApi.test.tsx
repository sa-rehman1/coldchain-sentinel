import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Observability } from '../features/observability/Observability';

const state = vi.hoisted(() => ({
  refetch: vi.fn(),
  query: { isLoading: false, isError: false, isFetching: false },
  summary: {
    generatedAt: '2026-09-27T12:00:00Z', overallStatus: 'HEALTHY' as const, healthyServices: 9, totalServices: 9, activeAlerts: 0, autoRefreshSeconds: 12,
    services: ['FastAPI', 'Worker', 'PostgreSQL', 'Kafka', 'Qdrant', 'Prometheus', 'Grafana', 'Jaeger', 'Recommendation provider'].map((name) => ({ name, status: 'HEALTHY' as const, signal: `${name} operational`, measurement: name === 'PostgreSQL' ? 3.2 : null, measurementUnit: name === 'PostgreSQL' ? 'milliseconds' : null, checkedAt: '2026-09-27T12:00:00Z', inspectionUrl: name === 'Prometheus' ? 'http://127.0.0.1:19090' : name === 'Grafana' ? 'http://127.0.0.1:13001' : name === 'Jaeger' ? 'http://127.0.0.1:16687' : null })),
    metrics: [
      ['request_rate', 'Request rate', 1.25, 'requests/second', 'AVAILABLE'], ['p95_latency', 'API P95 latency', 42.5, 'milliseconds', 'AVAILABLE'], ['error_rate', 'API error rate', 0, 'percent', 'AVAILABLE'], ['worker_throughput', 'Worker throughput', 12, 'events/minute', 'AVAILABLE'], ['consumer_lag', 'Consumer lag', null, 'messages', 'NO_SAMPLES'], ['awaiting_review', 'Awaiting review', 2, 'incidents', 'AVAILABLE'], ['recommendation_count', 'Recommendations', 4, 'count/hour', 'AVAILABLE'], ['recommendation_p95', 'Recommendation P95 latency', null, 'milliseconds', 'UNAVAILABLE'], ['fallback_count', 'Fallback activations', 0, 'count/hour', 'AVAILABLE'], ['open_incidents', 'Open incidents', 3, 'incidents', 'AVAILABLE'], ['simulated_actions', 'Simulated action outcomes', 0, 'count/hour', 'AVAILABLE'],
    ].map(([key, label, value, unit, availability]) => ({ key: String(key), label: String(label), value: value as number | null, unit: String(unit), state: availability as 'AVAILABLE' | 'NO_SAMPLES' | 'UNAVAILABLE', source: key === 'open_incidents' || key === 'awaiting_review' ? 'PostgreSQL showcase read model' : 'Prometheus' })),
    series: { apiRequestRate: [{ timestamp: '2026-09-27T12:00:00Z', value: 1.25 }], apiP95Latency: [{ timestamp: '2026-09-27T12:00:00Z', value: 42.5 }], workerThroughput: [{ timestamp: '2026-09-27T12:00:00Z', value: 12 }], dlqActivity: [] },
    alerts: { state: 'AVAILABLE' as const, rules: [
      { name: 'ColdChainApiErrorRate', state: 'INACTIVE', severity: 'warning', summary: 'API error rate is below threshold' },
      { name: 'ColdChainWorkerDelay', state: 'PENDING', severity: 'warning', summary: 'Worker delay is pending' },
      { name: 'ColdChainDeadLetterActivity', state: 'FIRING', severity: 'critical', summary: 'Dead-letter activity detected' },
      { name: 'ColdChainUnknownRule', state: 'UNAVAILABLE', severity: 'warning', summary: 'Rule state unavailable' },
    ] },
    traces: { state: 'NO_SAMPLES' as const, items: [] },
    privacyNotice: 'Metrics and traces exclude incident payloads, prompts, SOP text, credentials, and provider responses.',
  },
}));

vi.mock('../hooks/useControlTower', () => ({
  useDashboard: () => ({ data: { mode: 'api' } }),
  useObservabilitySummary: () => ({ ...state.query, data: state.query.isLoading || state.query.isError ? undefined : state.summary, refetch: state.refetch }),
}));

describe('live observability page', () => {
  beforeEach(() => { state.query.isLoading = false; state.query.isError = false; state.query.isFetching = false; state.refetch.mockReset(); });

  it('renders truthful live service, metric, alert, trace, and privacy states accessibly', async () => {
    const { container } = render(<Observability />);
    expect(screen.getByRole('heading', { name: 'Observability' })).toBeInTheDocument();
    expect(screen.getByText('9/9 healthy')).toBeInTheDocument();
    for (const name of ['FastAPI', 'Worker', 'PostgreSQL', 'Kafka', 'Qdrant', 'Prometheus', 'Grafana', 'Jaeger', 'Recommendation provider']) expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    expect(screen.getByText('1.25 req/s')).toBeInTheDocument();
    expect(screen.getByText('42.5 ms')).toBeInTheDocument();
    expect(screen.getByText('12 events/min')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getAllByText('0/h')).toHaveLength(2);
    expect(screen.getAllByText('No samples').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
    for (const stateLabel of ['Inactive', 'Pending', 'Firing']) expect(screen.getByText(stateLabel)).toBeInTheDocument();
    expect(screen.queryByText('Allowed')).not.toBeInTheDocument();
    expect(screen.getByText('Critical severity')).toBeInTheDocument();
    expect(screen.getByText('No workflow traces were recorded in the last hour.')).toBeInTheDocument();
    expect(screen.getByText(/exclude incident payloads, prompts, SOP text, credentials/i)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Inspect/ })).toHaveLength(3);
    expect((await axe(container)).violations).toEqual([]);
  });

  it('supports manual refresh and explicit loading and error states', async () => {
    const user = userEvent.setup();
    const { unmount } = render(<Observability />);
    await user.click(screen.getByRole('button', { name: 'Refresh' }));
    expect(state.refetch).toHaveBeenCalledOnce();
    unmount();
    state.query.isLoading = true;
    const loading = render(<Observability />);
    expect(screen.getByText('Loading observability')).toBeInTheDocument();
    loading.unmount();
    state.query.isLoading = false;
    state.query.isError = true;
    render(<Observability />);
    expect(screen.getByText('Observability is unavailable')).toBeInTheDocument();
  });
});
