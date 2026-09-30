import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ControlTowerProvider } from '../app/ControlTowerContext';
import type { InvestigationData } from '../data/contracts';
import { investigationFor } from '../data/fixtures';
import { Investigation } from '../features/investigation/Investigation';

const hookState = vi.hoisted<{ data: unknown }>(() => ({ data: undefined }));

vi.mock('../hooks/useControlTower', () => ({
  useInvestigation: () => ({ data: hookState.data, isLoading: false, isError: false, error: null }),
  useDecision: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));
vi.mock('../data/source', () => ({ dataSourceMode: 'api' }));

const internalId = '00000000-0000-4000-8000-000000000001';
const base = investigationFor('INC-2481');
const canonical: InvestigationData = {
  ...base,
  incident: {
    ...base.incident,
    id: internalId,
    reference: 'INC-1001',
    shipment: 'CCS-1001',
    reviewer: null,
    sensor: 'Probe 01',
    sensorHealth: 'Healthy',
    productSensitivity: 'High',
    evidenceProfile: {
      sensorHealth: 'Healthy',
      calibration: 'Verified',
      sampleIntervalMinutes: 10,
      readingQuality: 'No quality flags',
      productSensitivity: 'High',
      custodyVerification: 'Complete',
      complete: true,
    },
  },
  evidence: [
    { id: 'sopch_d588f16a238697434d818d2b', documentId: 'CCS-SOP-TEMP-001', title: 'Fresh and Perishable Temperature Excursions', section: 'Evidence-preserving shipment hold (TEMP-001-S2)', version: 'CCS-SOP-TEMP-001 · v1.0.0', effectiveDate: '2026-09-19', score: null, excerpt: 'When evidence is sufficient, recommend a shipment hold pending dispatcher review.', trusted: true, whyApplicable: 'This section defines how to respond to a sustained fresh-product temperature breach and requires preserving the shipment pending review.', validationStatus: 'trusted' },
    { id: 'sopch_evidence', documentId: 'CCS-SOP-EVID-001', title: 'Evidence and Sensor Integrity', section: 'Required immutable evidence (EVID-001-S1)', version: 'CCS-SOP-EVID-001 · v1.0.0', effectiveDate: '2026-09-19', score: null, excerpt: 'The evidence bundle preserves telemetry and sensor integrity facts.', trusted: true, whyApplicable: 'This section defines the telemetry, sensor, timing, sequence, and integrity evidence required before a decision.', validationStatus: 'trusted' },
    { id: 'sopch_4c0e122c8d5338ae03c9f879', documentId: 'CCS-SOP-HOLD-001', title: 'Shipment Hold, Inspection, and Release', section: 'Dispatcher authorization boundary (HOLD-001-S1)', version: 'CCS-SOP-HOLD-001 · v1.0.0', effectiveDate: '2026-09-19', score: null, excerpt: 'HOLD_SHIPMENT always requires authenticated dispatcher approval.', trusted: true, whyApplicable: 'This section requires authenticated dispatcher authorization for HOLD_SHIPMENT and prevents the recommendation engine from executing it directly.', validationStatus: 'trusted' },
  ],
  recommendation: {
    ...base.recommendation,
    action: 'HOLD_SHIPMENT',
    evidenceSufficient: true,
    uncertainty: 'low',
    missingInformation: [],
    contraindications: [],
    evidenceIds: ['sopch_d588f16a238697434d818d2b', 'sopch_evidence', 'sopch_4c0e122c8d5338ae03c9f879'],
    incidentEvidenceIds: ['00000000-0000-4000-8000-000000000002'],
    evidenceBundleReference: 'EVD-DEMO-12AB34CD',
    fallback: false,
    provider: 'deterministic',
    model: 'deterministic-local-1.0',
    validation: 'valid',
    actionability: {
      state: 'AWAITING_HUMAN_REVIEW',
      approvalAllowed: true,
      rejectionAllowed: true,
      status: 'Awaiting human review',
      explanation: 'The recommendation is current and an authorized dispatcher may approve or reject it.',
    },
  },
  governanceChecks: [
    { name: 'Schema check', state: 'pass', detail: 'Recommendation schema is valid.' },
    { name: 'Evidence check', state: 'pass', detail: 'The immutable evidence snapshot is complete.' },
    { name: 'Citation check', state: 'pass', detail: '3 cited SOP chunks are recognized, effective, and trusted.' },
    { name: 'Policy check', state: 'pass', detail: 'The proposed action is allowed by deterministic policy.' },
    { name: 'Expiry check', state: 'pass', detail: 'The recommendation was current when governance evaluated it.' },
    { name: 'Kill-switch state', state: 'pass', detail: 'The kill switch is inactive.' },
    { name: 'Human approval', state: 'warning', detail: 'Authenticated dispatcher approval is required before any command.' },
  ],
  governanceSummary: { decision: 'APPROVAL_REQUIRED', policyVersion: 'governance-policy-v1', evaluatedAt: '2026-09-27T12:00:00Z', authority: 'deterministic-governance' },
  audit: ['Telemetry received', 'Breach policy evaluated', 'Evidence snapshot created', 'Recommendation created', 'Governance evaluated'].map((type, index) => ({ id: `audit-${index}`, offsetMinutes: -5 + index, actor: 'ColdChain Sentinel service', type, summary: `${type}.`, correlationId: 'internal', traceId: 'Not reported', occurredAt: `2026-09-27T12:0${index}:00Z`, context: 'Correlation and causation links recorded', hashChainVerified: true })),
};

function renderInvestigation(data: InvestigationData) {
  hookState.data = data;
  return render(
    <MemoryRouter initialEntries={[`/investigation/${internalId}`]}>
      <ControlTowerProvider>
        <Routes><Route path="/investigation/:incidentId" element={<Investigation />} /></Routes>
      </ControlTowerProvider>
    </MemoryRouter>,
  );
}

describe('canonical investigation presentation', () => {
  beforeEach(() => { hookState.data = canonical; });

  it('uses friendly references, separates assignment from authority, and reconciles complete evidence', async () => {
    const { container } = renderInvestigation(canonical);

    expect(await screen.findByText('INC-1001')).toBeInTheDocument();
    expect(screen.getAllByText('CCS-1001').length).toBeGreaterThan(0);
    expect(container.textContent).not.toContain(internalId);
    expect(screen.getByText('Assigned reviewer').parentElement).toHaveTextContent('Unassigned');
    const decisionRail = screen.getByText('Human decision').closest('aside')!;
    expect(within(decisionRail).getByText('Authorized role').parentElement).toHaveTextContent('Dispatcher');
    expect(within(decisionRail).queryByText('Reviewer')).not.toBeInTheDocument();
    expect(screen.getByText('Evidence status').parentElement).toHaveTextContent('Complete');
    expect(screen.getByText('Evidence completeness').parentElement).toHaveTextContent('Complete');
    expect(screen.getByText('Calibration').parentElement).toHaveTextContent('Verified');
    expect(screen.getByText('Sample interval').parentElement).toHaveTextContent('10 minutes');
    expect(screen.getByText('Reading quality').parentElement).toHaveTextContent('No quality flags');
    expect(screen.getByText('Sensor health').parentElement).toHaveTextContent('Healthy');
    expect(screen.getByText('Product sensitivity').parentElement).toHaveTextContent('High');
    expect(screen.getByText('Custody verification').parentElement).toHaveTextContent('Complete');
    for (const tab of ['SOP Evidence', 'AI Recommendation', 'Governance', 'Audit Trail']) {
      expect(screen.getByRole('tab', { name: tab })).toBeInTheDocument();
    }
    expect((await axe(container)).violations).toEqual([]);
  });

  it('keeps unavailable general evidence explicitly incomplete', async () => {
    const generalIncident = { ...canonical.incident };
    delete generalIncident.reference;
    const general: InvestigationData = {
      ...canonical,
      incident: {
        ...generalIncident,
        evidenceProfile: null,
        sensorHealth: null,
        productSensitivity: null,
      },
    };
    renderInvestigation(general);

    expect(await screen.findByText('Reference not provided')).toBeInTheDocument();
    expect(screen.getByText('Evidence status').parentElement).toHaveTextContent('Incomplete');
    expect(screen.getByText('Evidence completeness').parentElement).toHaveTextContent('Incomplete');
    expect(screen.getByText('Calibration').parentElement).toHaveTextContent('Unavailable');
    expect(screen.getByText('Sensor health').parentElement).toHaveTextContent('Unavailable');
    expect(screen.getByText('Custody verification').parentElement).toHaveTextContent('Unavailable');
  });

  it('renders complete server-owned SOP, recommendation, governance, and audit content', async () => {
    const user = userEvent.setup();
    const { container } = renderInvestigation(canonical);

    await user.click(screen.getByRole('tab', { name: 'SOP Evidence' }));
    expect(await screen.findByText('Fresh and Perishable Temperature Excursions')).toBeInTheDocument();
    expect(screen.getByText('Evidence and Sensor Integrity')).toBeInTheDocument();
    expect(screen.getByText('Shipment Hold, Inspection, and Release')).toBeInTheDocument();
    expect(screen.getAllByText('trusted').length).toBe(3);
    const applicability = screen.getAllByText('Why it applies:').map((label) => label.parentElement?.textContent);
    expect(applicability).toEqual([
      'Why it applies: This section defines how to respond to a sustained fresh-product temperature breach and requires preserving the shipment pending review.',
      'Why it applies: This section defines the telemetry, sensor, timing, sequence, and integrity evidence required before a decision.',
      'Why it applies: This section requires authenticated dispatcher authorization for HOLD_SHIPMENT and prevents the recommendation engine from executing it directly.',
    ]);
    expect(new Set(applicability).size).toBe(3);
    expect(container).not.toHaveTextContent(/governs the synthetic temperature breach, evidence bundle, or dispatcher hold boundary/i);

    await user.click(screen.getByRole('tab', { name: 'AI Recommendation' }));
    expect(screen.getByText('Missing information').parentElement).toHaveTextContent('None');
    expect(screen.getByText('Contraindications').parentElement).toHaveTextContent('None identified');
    expect(screen.getByText('Fallback used').parentElement).toHaveTextContent('No');
    expect(screen.getByText(/cannot execute a command/i)).toBeInTheDocument();
    expect(screen.getByText('Evidence bundle').parentElement).toHaveTextContent('EVD-DEMO-12AB34CD');
    expect(screen.getByText('Uncertainty').parentElement).toHaveTextContent('Low');
    expect(screen.queryByText(/Evidence …/)).not.toBeInTheDocument();
    expect(container).not.toHaveTextContent('00000000-0000-4000-8000-000000000002');

    await user.click(screen.getByRole('tab', { name: 'Governance' }));
    expect(screen.getByText('Deterministic governance is authoritative')).toBeInTheDocument();
    expect(screen.getByText('Current actionability: Awaiting human review')).toBeInTheDocument();
    expect(screen.getByText(/Final disposition APPROVAL_REQUIRED/)).toBeInTheDocument();
    for (const name of ['Schema check', 'Evidence check', 'Citation check', 'Policy check', 'Expiry check', 'Kill-switch state', 'Human approval']) expect(screen.getByText(name)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Audit Trail' }));
    for (const name of ['Telemetry received', 'Breach policy evaluated', 'Evidence snapshot created', 'Recommendation created', 'Governance evaluated']) expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.queryByText('Human decision recorded')).not.toBeInTheDocument();
    expect(screen.queryByText('Command created')).not.toBeInTheDocument();
    expect(screen.queryByText('Simulated action completed')).not.toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });

  it('keeps historical expiry truth while independently blocking an expired recommendation', async () => {
    const user = userEvent.setup();
    const expired: InvestigationData = {
      ...canonical,
      recommendation: {
        ...canonical.recommendation,
        expiresInMinutes: 0,
        validation: 'expired',
        actionability: {
          state: 'EXPIRED',
          approvalAllowed: false,
          rejectionAllowed: false,
          status: 'Expired — approval blocked',
          explanation: 'The historical governance evaluation remains unchanged, but a new human decision cannot be recorded after recommendation expiry.',
        },
      },
    };
    const { container } = renderInvestigation(expired);

    expect(await screen.findByRole('button', { name: 'Approve hold' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled();
    expect(screen.getByText('Recommendation expired')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Governance' }));
    expect(screen.getByText('Current actionability: Expired — approval blocked')).toBeInTheDocument();
    expect(screen.getByText('The historical governance evaluation remains unchanged, but a new human decision cannot be recorded after recommendation expiry.')).toBeInTheDocument();
    expect(screen.getByText(/Final disposition APPROVAL_REQUIRED/)).toBeInTheDocument();
    expect(screen.getByText('Expiry check').parentElement).toHaveTextContent('The recommendation was current when governance evaluated it.');
    expect(screen.queryByText('Human decision recorded')).not.toBeInTheDocument();
    expect(screen.queryByText('Command created')).not.toBeInTheDocument();
    expect(screen.queryByText('Simulated action completed')).not.toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });

  it('renders a coherent guided-demo incident without exposing internal UUIDs', async () => {
    const user = userEvent.setup();
    const demo: InvestigationData = {
      ...canonical,
      incident: {
        ...canonical.incident,
        reference: 'INC-DEMO-A1B2C3D4',
        shipment: 'CCS-DEMO-E5F6A7B8',
        severity: 'warning',
        temperature: 9.4,
        allowedMin: null,
        allowedMax: 8,
        breachMinutes: 2,
        sensor: 'Probe DEMO-01',
        product: 'Synthetic fresh perishables',
        route: { from: 'Chicago, IL', via: 'Des Moines, IA', to: 'Denver, CO', progress: 55 },
        evidenceProfile: { ...canonical.incident.evidenceProfile!, sampleIntervalMinutes: 1 },
      },
    };
    const { container } = renderInvestigation(demo);

    expect(await screen.findByText('INC-DEMO-A1B2C3D4')).toBeInTheDocument();
    expect(screen.getAllByText('CCS-DEMO-E5F6A7B8').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Severity: High')).toBeInTheDocument();
    expect(screen.getByText('Allowed range').parentElement).toHaveTextContent('≤8°C');
    expect(screen.getByText('Sample interval').parentElement).toHaveTextContent('1 minute');
    expect(screen.getByText('Chicago, IL')).toBeInTheDocument();
    expect(screen.getByText('Des Moines, IA')).toBeInTheDocument();
    expect(screen.getByText('Denver, CO')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve hold' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeEnabled();

    for (const tab of ['SOP Evidence', 'AI Recommendation', 'Governance', 'Audit Trail']) {
      await user.click(screen.getByRole('tab', { name: tab }));
      expect(container).not.toHaveTextContent(internalId);
      expect(container).not.toHaveTextContent('00000000-0000-4000-8000-000000000002');
    }
    expect(screen.queryByText('Human decision recorded')).not.toBeInTheDocument();
    expect(screen.queryByText('Command created')).not.toBeInTheDocument();
    expect(screen.queryByText('Simulated action completed')).not.toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });
});
