import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GovernedAI } from '../features/governance/GovernedAI';

const state = vi.hoisted(() => ({
  dashboard: {
    mode: 'api' as const,
    incidents: [{
      id: '6e621ba9-dd68-517e-881f-854688db3b1d',
      reference: 'INC-1001',
      shipment: 'CCS-1001',
      title: 'Immediate critical temperature breach',
      product: 'mRNA vaccines',
      sensor: null,
      temperature: 12.4,
      allowedMin: 2,
      allowedMax: 8,
      breachMinutes: null,
      state: 'awaiting-review' as const,
      severity: 'critical' as const,
      governance: 'approval-required' as const,
      createdMinutesAgo: 22,
      reviewer: null,
      route: { from: 'Austin', via: 'Waco', to: 'Dallas', progress: 68 },
      productSensitivity: 'High',
      sensorHealth: 'Healthy',
    }],
    services: [],
    metrics: { affectedShipments: 4, openIncidents: 3, awaitingHumanReview: 2 },
    severityDistribution: { critical: 2, warning: 2, normal: 0 },
    approvalQueue: { pending: 2, oldestWaitingMinutes: 22, expiringWithin15Minutes: 1 },
    trend: [],
    recommendations: [],
    humanDecisions: [] as Array<{ incidentId: string; incidentReference: string; decision: string; reviewerRole: string; decidedAt: string }>,
    liveTelemetry: [],
    generatedAt: '2026-09-27T12:00:00Z',
  },
  health: {
    api: 'healthy' as const,
    ai: 'healthy' as const,
    provider: 'Deterministic',
    model: 'deterministic-local-1.0',
    providerConfigured: true,
    liveCallsEnabled: false,
    fallbackAvailable: true,
    qdrant: 'ready',
  },
}));

vi.mock('../data/source', () => ({ dataSourceMode: 'api' }));
vi.mock('../hooks/useControlTower', () => ({
  useDashboard: () => ({ data: state.dashboard }),
  useHealth: () => ({ data: state.health }),
}));

function RouteIdentity() {
  const { incidentId } = useParams();
  return <p>Internal route: {incidentId}</p>;
}

const renderPage = () => render(<MemoryRouter initialEntries={['/governed-ai']}><Routes>
  <Route path="/governed-ai" element={<GovernedAI />} />
  <Route path="/investigation/:incidentId" element={<RouteIdentity />} />
</Routes></MemoryRouter>);

describe('Governed AI authoritative API presentation', () => {
  beforeEach(() => { state.dashboard.humanDecisions = []; });

  it('uses friendly identifiers, readable states, truthful provider health, and the internal route identity', async () => {
    const user = userEvent.setup();
    const { container } = renderPage();

    expect(screen.getByRole('heading', { name: 'INC-1001' })).toBeInTheDocument();
    expect(screen.getByText('CCS-1001')).toBeInTheDocument();
    expect(screen.getByText('Awaiting review')).toBeInTheDocument();
    expect(screen.queryByText('6e621ba9-dd68-517e-881f-854688db3b1d')).not.toBeInTheDocument();
    expect(screen.getByText('Recommendations are generated locally by the deterministic engine. No external model call is made.')).toBeInTheDocument();
    expect(screen.queryByText(/the model recommends/i)).not.toBeInTheDocument();
    expect(screen.getByText('Deterministic')).toBeInTheDocument();
    expect(screen.getByText('deterministic-local-1.0')).toBeInTheDocument();
    expect(screen.getByText('Disabled')).toBeInTheDocument();
    expect(screen.getByText('No human decisions recorded yet.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Recent human decisions' })).toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);

    await user.click(screen.getByRole('button', { name: /Open incident investigation/i }));
    expect(screen.getByText('Internal route: 6e621ba9-dd68-517e-881f-854688db3b1d')).toBeInTheDocument();
  });

  it('renders a structured human-decision row without exposing an internal actor identity', () => {
    state.dashboard.humanDecisions = [{
      incidentId: '6e621ba9-dd68-517e-881f-854688db3b1d',
      incidentReference: 'INC-1001',
      decision: 'APPROVED',
      reviewerRole: 'Dispatcher',
      decidedAt: '2026-09-27T12:00:00Z',
    }];
    const { container } = renderPage();

    const list = container.querySelector('.human-decision-list');
    expect(list).not.toBeNull();
    expect(list).toHaveTextContent('INC-1001');
    expect(list).toHaveTextContent('Approved');
    expect(list).toHaveTextContent('Dispatcher');
    expect(list).not.toHaveTextContent('dispatcher:');
    expect(screen.queryByText('No human decisions recorded yet.')).not.toBeInTheDocument();
  });
});
