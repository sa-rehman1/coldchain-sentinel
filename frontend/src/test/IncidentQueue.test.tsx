import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ControlTowerProvider } from '../app/ControlTowerContext';
import type { Incident } from '../data/contracts';
import { IncidentQueue } from '../features/incidents/IncidentQueue';

const incidents: Incident[] = Array.from({ length: 4 }, (_, offset) => ({
  id: `00000000-0000-4000-8000-00000000000${offset + 1}`,
  reference: `INC-100${offset + 1}`,
  shipment: `CCS-100${offset + 1}`,
  title: offset < 2 ? 'Immediate critical temperature breach' : 'Sustained temperature breach',
  product: `Showcase product ${offset + 1}`,
  sensor: `Probe 0${offset + 1}`,
  temperature: 12.4 - offset,
  allowedMin: 2,
  allowedMax: 8,
  breachMinutes: 10,
  state: offset < 2 ? 'awaiting-review' : offset === 3 ? 'completed' : 'investigating',
  severity: offset < 2 ? 'critical' : 'warning',
  governance: offset < 2 ? 'approval-required' : 'allowed',
  createdMinutesAgo: [18, 34, 27, 49][offset]!,
  reviewer: offset === 3 ? 'Dispatcher' : null,
  route: null,
  productSensitivity: null,
  sensorHealth: null,
}));

vi.mock('../hooks/useControlTower', () => ({
  useIncidents: () => ({ data: incidents, isLoading: false, isError: false, error: null }),
}));
vi.mock('../data/source', () => ({ dataSourceMode: 'api' }));

function Destination() {
  return <div>Routed incident {useParams().incidentId}</div>;
}

function renderQueue() {
  return render(
    <MemoryRouter initialEntries={['/incidents']}>
      <ControlTowerProvider>
        <Routes>
          <Route path="/incidents" element={<IncidentQueue />} />
          <Route path="/investigation/:incidentId" element={<Destination />} />
        </Routes>
      </ControlTowerProvider>
    </MemoryRouter>,
  );
}

describe('canonical incident queue', () => {
  it('renders only friendly showcase labels and routes with the internal identity', async () => {
    const user = userEvent.setup();
    const { container } = renderQueue();

    expect(await screen.findByText('4 incidents match the current view')).toBeInTheDocument();
    for (let index = 1; index <= 4; index += 1) {
      expect(screen.getByText(`INC-100${index}`)).toBeInTheDocument();
      expect(screen.getByText(`CCS-100${index}`)).toBeInTheDocument();
      expect(screen.getByText(`Probe 0${index}`)).toBeInTheDocument();
    }
    expect(container.textContent).not.toMatch(/00000000-|dispatcher:|\bnull\b/);
    expect(screen.getAllByText('Unassigned')).toHaveLength(3);

    await user.click(screen.getByText('INC-1001'));
    expect(screen.getByRole('complementary', { name: 'Investigation preview' })).toHaveTextContent('INC-1001');
    await user.click(screen.getByRole('button', { name: /Open investigation/ }));
    expect(screen.getByText('Routed incident 00000000-0000-4000-8000-000000000001')).toBeInTheDocument();
  });

  it('preserves filtering, sorting, pagination controls, and accessibility', async () => {
    const user = userEvent.setup();
    const { container } = renderQueue();
    await screen.findByText('4 incidents match the current view');

    const table = screen.getByRole('table');
    await user.click(within(table).getByRole('columnheader', { name: /Incident/ }));
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent('INC-1001');
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();

    await user.type(screen.getByRole('textbox', { name: 'Search incidents' }), 'INC-1004');
    expect(screen.getByText('1 incidents match the current view')).toBeInTheDocument();
    expect(screen.getByText('INC-1004')).toBeInTheDocument();
    expect(screen.queryByText('INC-1001')).not.toBeInTheDocument();
    expect((await axe(container)).violations).toEqual([]);
  });
});
