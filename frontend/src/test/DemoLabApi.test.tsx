import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ControlTowerProvider } from '../app/ControlTowerContext';
import { DemoLab } from '../features/demo-lab/DemoLab';

const state = vi.hoisted(() => ({
  internalIncidentId: '6e621ba9-dd68-517e-881f-854688db3b1d',
  run: {
    runId: '00000000-0000-4000-8000-000000000010',
    scenarioId: 'sustained',
    correlationId: '00000000-0000-4000-8000-000000000011',
    shipmentId: '00000000-0000-4000-8000-000000000012',
    eventIds: ['00000000-0000-4000-8000-000000000013'],
    publishCount: 3,
    status: 'INCIDENT_READY' as const,
    processedEventCount: 3,
    dispositions: ['ACCEPTED'],
    incidentId: '6e621ba9-dd68-517e-881f-854688db3b1d',
    incidentReference: 'INC-DEMO-A1B2C3D4',
    shipmentReference: 'CCS-DEMO-E5F6A7B8',
    incidentSeverity: 'HIGH' as const,
    governanceDecision: 'APPROVAL_REQUIRED',
    humanDecisionRecorded: false,
    resultState: 'AWAITING_HUMAN_REVIEW' as const,
    steps: {
      sensorReading: 'COMPLETED' as const,
      policyCheck: 'COMPLETED' as const,
      incidentCreated: 'COMPLETED' as const,
      evidenceCollected: 'COMPLETED' as const,
      aiAdvisory: 'COMPLETED' as const,
      governance: 'COMPLETED' as const,
      humanReview: 'PENDING' as const,
    },
  },
}));

vi.mock('../data/source', () => ({ dataSourceMode: 'api' }));
vi.mock('../hooks/useControlTower', () => ({
  useScenarios: () => ({
    data: [{
      id: 'sustained',
      title: 'Sustained temperature breach',
      demonstrates: 'Three consecutive readings above the safe limit',
      policyOutcome: 'Approval required',
      governanceOutcome: 'Approval required',
      humanAction: 'Approve or reject hold',
      duration: 'Processing time varies',
      variant: 'critical' as const,
    }],
    isError: false,
    error: null,
  }),
  useStartScenario: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ runId: state.run.runId }),
    isPending: false,
  }),
  useDemoRun: (runId: string | null) => ({ data: runId ? state.run : undefined }),
}));

function RouteIdentity() {
  return <p>Internal route: {useParams().incidentId}</p>;
}

function renderPage(initialEntry = '/demo-lab') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ControlTowerProvider>
        <Routes>
          <Route path="/demo-lab" element={<DemoLab />} />
          <Route path="/investigation/:incidentId" element={<RouteIdentity />} />
        </Routes>
      </ControlTowerProvider>
    </MemoryRouter>,
  );
}

describe('Demo Lab authoritative guided result', () => {
  it('shows a friendly pending result while routing with the internal incident identity', async () => {
    const user = userEvent.setup();
    const { container } = renderPage();

    await user.click(await screen.findByRole('button', { name: /Start guided demo/i }));
    await waitFor(() => expect(screen.getAllByText('Awaiting human review').length).toBeGreaterThan(0));

    expect(screen.getByText('INC-DEMO-A1B2C3D4')).toBeInTheDocument();
    expect(screen.getByText('CCS-DEMO-E5F6A7B8')).toBeInTheDocument();
    expect(screen.getByLabelText('Severity: High')).toBeInTheDocument();
    expect(container).not.toHaveTextContent(state.internalIncidentId);
    for (const stage of ['Sensor reading', 'Policy check', 'Incident created', 'Evidence collected', 'AI advisory', 'Governance']) {
      expect(screen.getByLabelText(`${stage}: completed`)).toBeInTheDocument();
    }
    expect(screen.getByLabelText('Human review: pending')).toHaveTextContent(
      'An authorized dispatcher must approve or reject the proposed hold.',
    );
    expect(screen.queryByText(/command created|action completed|simulated execution/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Complete')).not.toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);

    await user.click(screen.getByRole('button', { name: /Open incident investigation/i }));
    expect(screen.getByText(`Internal route: ${state.internalIncidentId}`)).toBeInTheDocument();
  });

  it('resumes an existing authoritative run without starting another scenario', async () => {
    const { container } = renderPage(`/demo-lab?run=${state.run.runId}`);

    await waitFor(() => expect(screen.getAllByText('Awaiting human review').length).toBeGreaterThan(0));
    expect(screen.getByText('INC-DEMO-A1B2C3D4')).toBeInTheDocument();
    expect(screen.getByText('CCS-DEMO-E5F6A7B8')).toBeInTheDocument();
    expect(container).not.toHaveTextContent(state.internalIncidentId);
    expect(screen.getByLabelText('Human review: pending')).toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });
});
