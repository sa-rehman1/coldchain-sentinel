import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../app/App';
import { PrototypeProvider, type Persona } from '../app/PrototypeContext';
import { ChartLegend, ChartTooltip } from '../components/data-display/ChartSupport';
import { ServiceHealthTable } from '../components/data-display/ServiceHealthTable';
import { GovernanceIndicator, SeverityIndicator } from '../components/ui/StatusIndicators';
import { MockControlTowerDataSource } from '../data/adapters/MockControlTowerDataSource';
import { dashboard, incidents, scenarios } from '../data/fixtures';
import { deriveIncidentSummary } from '../data/selectors/incidents';

function renderApp(route = '/', persona: Persona = 'Quality reviewer', initialDisplayMode: 'default' | 'empty' | 'disconnected' | 'permission-denied' = 'default') {
  return render(<MemoryRouter initialEntries={[route]}><PrototypeProvider initialPersona={persona} initialDisplayMode={initialDisplayMode}><App /></PrototypeProvider></MemoryRouter>);
}

describe('control tower prototype', () => {
  it('renders the application shell and command center', async () => {
    const { container } = renderApp();
    expect(screen.getByText('ColdChain Sentinel')).toBeInTheDocument();
    expect(screen.getByText('Local demo')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Cold-chain operations', level: 1 })).toBeInTheDocument();
    expect(container.querySelector('.light-shell')).toBeInTheDocument();
  });

  it('has no automated accessibility violations on the command center', async () => {
    const { container } = renderApp();
    await screen.findByText('Incident activity');
    expect((await axe(container)).violations).toEqual([]);
  });

  it.each(['/incidents', '/governed-ai', '/observability', '/demo-lab', '/investigation/INC-2481'])('has no automated accessibility violations on %s', async (route) => {
    const { container } = renderApp(route);
    await waitFor(() => expect(container.querySelector('.page')).toBeInTheDocument());
    expect((await axe(container)).violations).toEqual([]);
  });

  it('navigates between primary workflows', async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('link', { name: 'Incidents' }));
    expect(await screen.findByRole('heading', { name: 'Incident Queue', level: 2 })).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: /Governed AI/i }));
    expect(await screen.findByRole('heading', { name: 'Recommendation lifecycle' })).toBeInTheDocument();
  });

  it('uses the compact five-item top navigation without a permanent investigation link', () => {
    renderApp();
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(within(navigation).getAllByRole('link')).toHaveLength(5);
    expect(within(navigation).getByRole('link', { name: 'Command Center' })).toHaveAttribute('aria-current', 'page');
    expect(within(navigation).queryByRole('link', { name: 'Investigation' })).not.toBeInTheDocument();
  });

  it('uses the complete brand as a real home link', async () => {
    const user = userEvent.setup();
    renderApp('/incidents');
    const brand = screen.getByRole('link', { name: 'Go to Command Center' });
    expect(brand).toHaveAttribute('href', '/');
    await user.click(brand);
    expect(await screen.findByRole('heading', { name: 'Cold-chain operations', level: 1 })).toBeInTheDocument();
  });

  it('supports keyboard navigation through the brand link', async () => {
    const user = userEvent.setup();
    renderApp('/incidents');
    const brand = screen.getByRole('link', { name: 'Go to Command Center' });
    brand.focus();
    expect(brand).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('heading', { name: 'Cold-chain operations', level: 1 })).toBeInTheDocument();
  });

  it('shows the complete global search immediately without requiring focus', () => {
    renderApp();
    const search = screen.getByPlaceholderText('Search incidents');
    expect(search).toBeVisible();
    expect(search).toHaveAccessibleName('Global incident search');
  });

  it('shows shipment distribution, priority incidents, and the urgent investigation action', async () => {
    const user = userEvent.setup();
    renderApp();
    expect(await screen.findByLabelText('Shipment status distribution')).toBeInTheDocument();
    expect(screen.getByText('Shipments monitored')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Priority incidents' })).toBeInTheDocument();
    expect(screen.getByText('Reviewer')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Most urgent shipment' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Investigate/i }));
    expect(await screen.findByRole('heading', { name: 'Sustained thermal excursion', level: 1 })).toBeInTheDocument();
  });

  it('keeps priority State and Age in separate accessible cells with a responsive reviewer fallback', async () => {
    renderApp();
    const table = await screen.findByRole('table', { name: 'Priority incidents' });
    expect(within(table).getByRole('columnheader', { name: 'State' })).toBeInTheDocument();
    expect(within(table).getByRole('columnheader', { name: 'Age' })).toBeInTheDocument();
    const firstRow = within(table).getAllByRole('row')[1]!;
    const stateCell = firstRow.querySelector('.priority-state-cell');
    const ageCell = firstRow.querySelector('.priority-age-cell');
    expect(stateCell).toHaveAccessibleName('Workflow: Awaiting review');
    expect(ageCell).toHaveAccessibleName('Age: 52 minutes');
    expect(stateCell).not.toBe(ageCell);
    expect(firstRow.querySelector('.priority-reviewer-secondary')).toHaveTextContent('Reviewer: Maya Chen');
  });

  it('derives distinct critical and approval counts from the incident fixtures', async () => {
    renderApp();
    await screen.findByText('Critical incidents');
    const summary = deriveIncidentSummary(incidents);
    expect(summary).toEqual({ criticalCount: 3, approvalQueueCount: 2, oldestWaitingMinutes: 52, sustainedBreachCount: 2, immediateBreachCount: 1 });
    expect(screen.getByText('2 sustained · 1 immediate')).toBeInTheDocument();
    expect(screen.getByText('1 expires in 9 min')).toBeInTheDocument();
  });

  it('replaces the decorative network with useful live telemetry', async () => {
    renderApp();
    expect(await screen.findByRole('region', { name: 'Live telemetry' })).toBeInTheDocument();
    expect(screen.getByText('Chicago → Denver')).toBeInTheDocument();
    expect(screen.getByText('Seattle → Chicago')).toBeInTheDocument();
    expect(screen.getByText('Boston → New York')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Conceptual shipment/i)).not.toBeInTheDocument();
  });

  it('uses the consistent Chicago to Denver primary fixture without unfamiliar routes', () => {
    expect(incidents[0]).toMatchObject({ id: 'INC-2481', shipment: 'CCS-CHI-1842', product: 'mRNA vaccine', route: { from: 'Chicago', to: 'Denver' } });
    expect(JSON.stringify({ incidents, dashboard })).not.toMatch(/Reykjavík|Madrid|Calgary/);
  });

  it('renders the aligned investigation summary and advisory authority boundary', async () => {
    const { container } = renderApp('/investigation/INC-2481');
    expect(await screen.findByText('Current temperature')).toBeInTheDocument();
    for (const label of ['Allowed range', 'Breach duration', 'Incident age', 'Evidence status']) expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(/AI recommendation is advisory/i)).toBeInTheDocument();
    expect(screen.getByText(/authorized reviewer makes the final decision/i)).toBeInTheDocument();
    expect(container.querySelector('.human-decision-rail')).toBeInTheDocument();
  });

  it('filters incidents and opens an investigation preview', async () => {
    const user = userEvent.setup();
    renderApp('/incidents');
    const search = await screen.findByRole('textbox', { name: 'Search incidents' });
    await user.type(search, 'INC-2481');
    expect(screen.getByText('Sustained thermal excursion')).toBeInTheDocument();
    expect(screen.queryByText('Cooling recovery delayed')).not.toBeInTheDocument();
    await user.click(screen.getByText('Sustained thermal excursion'));
    expect(screen.getByRole('complementary', { name: 'Investigation preview' })).toBeInTheDocument();
    expect(screen.getByText('Preview only')).toBeInTheDocument();
  });

  it('opens the consequential approval dialog and records a prototype decision', async () => {
    const user = userEvent.setup();
    renderApp('/investigation/INC-2481');
    await user.click(await screen.findByRole('button', { name: 'Approve hold' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Confirm shipment hold')).toBeInTheDocument();
    expect(within(dialog).getByText(/idempotent simulated command/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Confirm prototype decision' }));
    expect(await screen.findByText('Approved for simulated execution')).toBeInTheDocument();
  });

  it('requires a reason to reject', async () => {
    const user = userEvent.setup();
    renderApp('/investigation/INC-2481');
    await user.click(await screen.findByRole('button', { name: 'Reject' }));
    const confirm = screen.getByRole('button', { name: 'Confirm prototype decision' });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/concise operational rationale/i), 'Sensor conflict needs review');
    expect(confirm).toBeEnabled();
  });

  it('hides decision authority from the read-only persona', async () => {
    renderApp('/investigation/INC-2481', 'Read-only auditor');
    await screen.findByText('Approval required');
    expect(screen.getByRole('button', { name: 'Approve hold' })).toBeDisabled();
    expect(screen.getByText(/cannot make operational decisions/i)).toBeInTheDocument();
  });

  it('runs and resets a deterministic scenario', async () => {
    const user = userEvent.setup();
    renderApp('/demo-lab');
    const card = (await screen.findByText('Immediate critical breach')).closest('article')!;
    await user.click(within(card).getByRole('button', { name: 'Run' }));
    expect(screen.getByText('Guided simulation')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Restore prototype data' }));
    expect(screen.queryByText('Guided simulation')).not.toBeInTheDocument();
  });

  it('presents a readable service health table', () => {
    render(<ServiceHealthTable services={dashboard.services} />);
    expect(screen.getByText('Operational signal')).toBeInTheDocument();
    expect(screen.getByText('Latency / lag')).toBeInTheDocument();
    expect(screen.getByText('Last check')).toBeInTheDocument();
  });

  it('groups the investigation decision and uses concise evidence tabs', async () => {
    renderApp('/investigation/INC-2481');
    expect(await screen.findByText('Human decision')).toBeInTheDocument();
    expect(screen.getByText('Proposed action')).toBeInTheDocument();
    expect(screen.getByText('Operational impact')).toBeInTheDocument();
    expect(screen.getByText('Policy result')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'SOP Evidence' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'AI Recommendation' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Audit Trail' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Temperature' })).not.toBeInTheDocument();
  });

  it('shows a compact selectable governed AI lifecycle and stage details', async () => {
    const user = userEvent.setup();
    renderApp('/governed-ai');
    expect(await screen.findByRole('heading', { name: 'Recommendation lifecycle' })).toBeInTheDocument();
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getAllByText(/model recommends\. policy governs\. humans authorize/i)).toHaveLength(2);
    expect(screen.getByText('Evidence bundle ready')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: /Governance/i }));
    expect(screen.getByText('Citations valid')).toBeInTheDocument();
    expect(screen.getAllByText('Approval required').length).toBeGreaterThan(0);
  });

  it('explains the governed workflow and advances the current example without autoplay', async () => {
    const user = userEvent.setup();
    renderApp('/governed-ai');
    expect(await screen.findByRole('heading', { name: 'How a recommendation becomes a safe action' })).toBeInTheDocument();
    for (const principle of ['AI suggests', 'Rules verify', 'A human decides']) expect(screen.getByRole('heading', { name: principle })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Current example · INC-2481/ })).toBeInTheDocument();
    expect(screen.getByText('Six sensor readings and two trusted SOP sections were collected.')).toBeInTheDocument();
    expect(screen.getByLabelText('Stage 1 of 4: Evidence')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Previous/i })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Next stage/i }));
    expect(screen.getByText('AI recommends holding the shipment for inspection.')).toBeInTheDocument();
    expect(screen.getByLabelText('Stage 2 of 4: Recommendation')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Previous/i }));
    expect(screen.getByText('Six sensor readings and two trusted SOP sections were collected.')).toBeInTheDocument();
  });

  it('opens the current example investigation from Governed AI', async () => {
    const user = userEvent.setup();
    renderApp('/governed-ai');
    await user.click(await screen.findByRole('button', { name: /Open incident investigation/i }));
    expect(await screen.findByRole('heading', { name: 'Sustained thermal excursion', level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText('CCS-CHI-1842').length).toBeGreaterThan(0);
  });

  it('shows three accessible deterministic notifications and marks them all read', async () => {
    const user = userEvent.setup();
    const { container } = renderApp();
    const trigger = screen.getByRole('button', { name: 'Notifications, 3 unread' });
    expect(trigger).toHaveTextContent('3');
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByText('3 unread')).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem')).toHaveLength(3);
    expect(screen.getByText('Critical temperature breach')).toBeInTheDocument();
    expect(screen.getByText('Approval expiring soon')).toBeInTheDocument();
    expect(screen.getByText('Fallback recommendation used')).toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
    await user.click(screen.getByRole('button', { name: 'Mark all as read' }));
    await user.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Notifications, 0 unread' })).toBeInTheDocument();
  });

  it('navigates from a notification and records its read state', async () => {
    const user = userEvent.setup();
    renderApp();
    screen.getByRole('button', { name: 'Notifications, 3 unread' }).focus();
    await user.keyboard('{Enter}');
    await user.click(screen.getByRole('menuitem', { name: /Critical temperature breach/ }));
    expect(await screen.findByRole('heading', { name: 'Sustained thermal excursion', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Notifications, 2 unread' })).toBeInTheDocument();
  });

  it('restoring prototype fixtures resets notification state', async () => {
    const user = userEvent.setup();
    renderApp('/demo-lab');
    screen.getByRole('button', { name: 'Notifications, 3 unread' }).focus();
    await user.keyboard('{Enter}');
    await user.click(screen.getByRole('button', { name: 'Mark all as read' }));
    await user.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Notifications, 0 unread' })).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'Restore prototype data' })[0]!);
    expect(screen.getByRole('button', { name: 'Notifications, 3 unread' })).toBeInTheDocument();
  });

  it('switches between observability overview and service inventory', async () => {
    const user = userEvent.setup();
    renderApp('/observability');
    expect(await screen.findByRole('tabpanel', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByText('API traffic and latency')).toBeInTheDocument();
    expect(screen.queryByText('PostgreSQL')).not.toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Services' }));
    expect(screen.getByRole('tabpanel', { name: 'Services' })).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
  });

  it('guides the recommended demo through completion and investigation', async () => {
    const user = userEvent.setup();
    renderApp('/demo-lab');
    expect((await screen.findAllByRole('heading', { name: 'Sustained temperature breach' })).length).toBeGreaterThan(0);
    expect(screen.getByText(/best end-to-end demonstration/i)).toBeInTheDocument();
    expect(screen.getByText('Sensor report')).toBeInTheDocument();
    expect(screen.getByText(/affects only this browser’s in-memory fixture state/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Start guided demo/i }));
    await waitFor(() => expect(screen.getByText('Incident created')).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByRole('button', { name: /Open incident investigation/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run again' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Restore prototype data' }).length).toBeGreaterThan(0);
  });

  it('renders shared severity and governance indicators with visible accessible text', () => {
    render(<><SeverityIndicator severity="critical" /><SeverityIndicator severity="warning" /><GovernanceIndicator decision="approval-required" /><GovernanceIndicator decision="fallback" /></>);
    expect(screen.getByLabelText('Severity: Critical')).toHaveTextContent('Critical');
    expect(screen.getByLabelText('Severity: High')).toHaveTextContent('High');
    expect(screen.getByLabelText('Governance: Approval required')).toHaveTextContent('Approval required');
    expect(screen.getByLabelText('Governance: Fallback')).toHaveTextContent('Fallback');
  });

  it('previews an idempotency conflict without executing a command', async () => {
    const user = userEvent.setup();
    renderApp('/demo-lab');
    await user.selectOptions(await screen.findByLabelText('Decision response variant'), 'conflict');
    const globalSearch = screen.getByRole('textbox', { name: 'Global incident search' });
    await user.type(globalSearch, 'INC-2481{Enter}');
    await user.click(await screen.findByRole('button', { name: 'Approve hold' }));
    await user.click(screen.getByRole('button', { name: 'Confirm prototype decision' }));
    expect((await screen.findAllByText(/idempotent command already exists/i)).length).toBeGreaterThan(0);
  });

  it('blocks approval for an expired recommendation', async () => {
    renderApp('/investigation/INC-2474');
    expect(await screen.findByText('Expired')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve hold' })).toBeDisabled();
  });

  it('supports empty and disconnected fixture states', async () => {
    const user = userEvent.setup();
    renderApp('/demo-lab');
    const healthy = (await screen.findByText('Healthy shipment')).closest('article')!;
    await user.click(within(healthy).getByRole('button', { name: 'Run' }));
    await waitFor(() => expect(screen.getByText(/completed · local simulation/i)).toBeInTheDocument(), { timeout: 3000 });
    await user.click(screen.getByRole('link', { name: 'Incidents' }));
    expect(await screen.findByText('No incidents found')).toBeInTheDocument();
  });

  it('renders the disconnected state without contacting a network', async () => {
    renderApp('/incidents', 'Quality reviewer', 'disconnected');
    expect(await screen.findByText('Data source disconnected')).toBeInTheDocument();
  });
});

describe('prototype safety and data boundary', () => {
  it('renders differentiated high-contrast chart tooltip values and legend labels', () => {
    render(<><ChartLegend items={[{ label: 'Active incidents', color: '#5BA7A7' }, { label: 'Temperature breaches', color: '#E16464' }, { label: 'Awaiting review', color: '#E6A64C' }]} /><ChartTooltip active label="12:00" payload={[{ dataKey: 'incidents', name: 'Active incidents', value: 8, color: '#5BA7A7' }, { dataKey: 'breaches', name: 'Temperature breaches', value: 3, color: '#E16464' }, { dataKey: 'awaitingReview', name: 'Awaiting review', value: 2, color: '#E6A64C' }]} /></>);
    const legend = screen.getByLabelText('Chart legend');
    expect(within(legend).getByText('Active incidents')).toBeInTheDocument();
    expect(within(legend).getByText('Temperature breaches')).toBeInTheDocument();
    expect(within(legend).getByText('Awaiting review')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('keeps service health structurally tabular without exposing payload data', () => {
    render(<ServiceHealthTable services={dashboard.services} />);
    expect(screen.getByText('Service')).toBeInTheDocument();
    expect(screen.getByText('Operational signal')).toBeInTheDocument();
    expect(screen.getAllByText('Just now').length).toBeGreaterThan(0);
    expect(screen.queryByText(/prompt|SOP text|authorization/i)).not.toBeInTheDocument();
  });

  it('contains no secret-like fixture content', () => {
    const renderedFixtures = JSON.stringify({ dashboard, incidents, scenarios });
    expect(renderedFixtures).not.toMatch(/(?:gsk_|sk-[A-Za-z0-9]{16,}|authorization\s*:|bearer\s+[A-Za-z0-9._-]+)/i);
  });

  it('does not perform network activity at import or data-source use', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const source = new MockControlTowerDataSource();
    expect((await source.getDashboard()).incidents.length).toBeGreaterThan(0);
    expect(await source.getScenarios()).toHaveLength(12);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('returns defensive copies through the data-source abstraction', async () => {
    const source = new MockControlTowerDataSource();
    const first = await source.getIncidents();
    first[0]!.title = 'changed locally';
    const second = await source.getIncidents();
    expect(second[0]!.title).toBe('Sustained thermal excursion');
  });
});
