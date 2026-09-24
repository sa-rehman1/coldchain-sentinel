import { columnVisibilityFeature, createColumnHelper, createPaginatedRowModel, createSortedRowModel, rowPaginationFeature, rowSortingFeature, tableFeatures, useTable } from '@tanstack/react-table';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ArrowRight, ChevronLeft, ChevronRight, Columns3, Filter, Search, SlidersHorizontal, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useControlTowerContext } from '../../app/ControlTowerContext';
import { Button, EmptyState } from '../../components/ui/Primitives';
import { GovernanceIndicator, SeverityIndicator, WorkflowIndicator } from '../../components/ui/StatusIndicators';
import type { Incident } from '../../data/contracts';
import { minutes, present, range, temperature } from '../../data/presentation';
import { dataSourceMode } from '../../data/source';
import { useIncidents } from '../../hooks/useControlTower';

const features = tableFeatures({
  columnVisibilityFeature,
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  rowPaginationFeature,
  paginatedRowModel: createPaginatedRowModel(),
});
const columnHelper = createColumnHelper<typeof features, Incident>();
const columns = columnHelper.columns([
  columnHelper.display({ id: 'select', header: 'Select', enableSorting: false, cell: ({ row }) => <input type="checkbox" aria-label={`Select ${row.original.id}`} onClick={(event) => event.stopPropagation()} /> }),
  columnHelper.accessor('severity', { header: 'Severity', cell: ({ row }) => <SeverityIndicator severity={row.original.severity} /> }),
  columnHelper.accessor('id', { header: 'Incident', cell: ({ row }) => <div className="table-primary"><strong className="mono">{row.original.id}</strong><span>{row.original.title}</span></div> }),
  columnHelper.accessor('shipment', { header: 'Shipment', cell: ({ getValue }) => <span className="mono">{String(getValue())}</span> }),
  columnHelper.accessor('product', { header: 'Product' }),
  columnHelper.accessor('sensor', { header: 'Sensor', cell: ({ getValue }) => <span className="mono">{String(getValue())}</span> }),
  columnHelper.accessor('temperature', { header: 'Temperature', cell: ({ row }) => <span className="queue-temperature"><strong className={row.original.severity === 'critical' ? 'text-critical' : ''}>{temperature(row.original.temperature)}</strong><small>{range(row.original.allowedMin, row.original.allowedMax)} allowed</small></span> }),
  columnHelper.accessor('breachMinutes', { header: 'Breach', cell: ({ getValue }) => minutes(getValue()) }),
  columnHelper.accessor('state', { header: 'Workflow', cell: ({ row }) => <WorkflowIndicator state={row.original.state} /> }),
  columnHelper.accessor('governance', { header: 'Governance', cell: ({ row }) => <GovernanceIndicator decision={row.original.governance} /> }),
  columnHelper.accessor('createdMinutesAgo', { header: 'Created', cell: ({ getValue }) => `${String(getValue())}m ago` }),
  columnHelper.display({ id: 'age', header: 'Age', enableSorting: false, cell: ({ row }) => `${Math.floor(row.original.createdMinutesAgo / 60)}h ${row.original.createdMinutesAgo % 60}m` }),
  columnHelper.accessor('reviewer', { header: 'Reviewer', cell: ({ getValue }) => String(getValue() ?? 'Unassigned') }),
]);

export function IncidentQueue() {
  const { data = [], isLoading, isError, error } = useIncidents();
  const { simulatedIncidents, displayMode } = useControlTowerContext();
  const [params, setParams] = useSearchParams();
  const [density, setDensity] = useState<'compact' | 'comfortable'>('compact');
  const [selected, setSelected] = useState<Incident | null>(null);
  const navigate = useNavigate();
  const incidents = useMemo(() => displayMode === 'empty' ? [] : [...simulatedIncidents, ...data], [data, displayMode, simulatedIncidents]);
  const query = params.get('q') ?? '';
  const severity = params.get('severity') ?? 'all';
  const state = params.get('state') ?? 'all';
  const governance = params.get('governance') ?? 'all';
  const approvalOnly = params.get('approval') === 'true';

  const filtered = useMemo(() => incidents.filter((incident) => {
    const text = `${incident.id} ${incident.title} ${incident.shipment} ${incident.product} ${incident.sensor}`.toLowerCase();
    return text.includes(query.toLowerCase()) && (severity === 'all' || incident.severity === severity) && (state === 'all' || incident.state === state) && (governance === 'all' || incident.governance === governance) && (!approvalOnly || incident.governance === 'approval-required');
  }), [incidents, query, severity, state, governance, approvalOnly]);

  const table = useTable({ features, data: filtered, columns, initialState: { pagination: { pageIndex: 0, pageSize: 6 }, sorting: [{ id: 'createdMinutesAgo', desc: false }] } });
  const updateParam = (key: string, value: string) => { const next = new URLSearchParams(params); if (value === 'all' || value === '') next.delete(key); else next.set(key, value); void setParams(next); };

  if (displayMode === 'disconnected') return <div className="page"><EmptyState title="Data source disconnected" detail="Fixture mode is showing the network-loss state. Restore fixtures from Demo Lab to reconnect." /></div>;
  if (isError && dataSourceMode === 'api') return <div className="page"><EmptyState title="Incident service disconnected" detail={error instanceof Error ? error.message : 'The local API is unavailable.'} /></div>;

  return <div className={`page queue-page density-${density}`}>
    <div className="page-intro"><div><p>Operational triage</p><h2>Incident Queue</h2><span>{filtered.length} incidents match the current view</span></div><div className="queue-actions"><Button variant="ghost" onClick={() => setDensity(density === 'compact' ? 'comfortable' : 'compact')}><SlidersHorizontal size={15} />{density}</Button><DropdownMenu.Root><DropdownMenu.Trigger asChild><Button variant="secondary"><Columns3 size={15} />Columns</Button></DropdownMenu.Trigger><DropdownMenu.Portal><DropdownMenu.Content className="dropdown-content columns-menu" align="end">{table.getAllLeafColumns().filter((column) => column.id !== 'select').map((column) => <DropdownMenu.CheckboxItem className="dropdown-item" key={column.id} checked={column.getIsVisible()} onCheckedChange={(checked) => column.toggleVisibility(checked === true)}>{column.id.replace(/([A-Z])/g, ' $1')}</DropdownMenu.CheckboxItem>)}</DropdownMenu.Content></DropdownMenu.Portal></DropdownMenu.Root></div></div>
    <div className="filter-bar">
      <label className="filter-search"><Search size={15} /><input aria-label="Search incidents" value={query} onChange={(event) => updateParam('q', event.target.value)} placeholder="Incident, shipment, product, sensor…" /></label>
      <Filter size={15} />
      <select aria-label="Severity filter" value={severity} onChange={(event) => updateParam('severity', event.target.value)}><option value="all">All severities</option>{['critical', 'warning', 'normal'].map((value) => <option key={value}>{value}</option>)}</select>
      <select aria-label="State filter" value={state} onChange={(event) => updateParam('state', event.target.value)}><option value="all">All states</option>{['triage', 'investigating', 'awaiting-review', 'rejected', 'completed'].map((value) => <option key={value}>{value}</option>)}</select>
      <select aria-label="Governance filter" value={governance} onChange={(event) => updateParam('governance', event.target.value)}><option value="all">All governance</option>{['approval-required', 'allowed', 'blocked', 'fallback'].map((value) => <option key={value}>{value}</option>)}</select>
      <label className={`quick-filter ${approvalOnly ? 'active' : ''}`}><input type="checkbox" checked={approvalOnly} onChange={(event) => updateParam('approval', event.target.checked ? 'true' : '')} />Approval required</label>
    </div>
    <div className="table-shell">
      {isLoading ? <div className="skeleton skeleton-table" /> : filtered.length === 0 ? <EmptyState title="No incidents found" detail="Change the current filters or restore the demo fixtures." /> : <div className="table-scroll"><table><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id} onClick={header.column.getToggleSortingHandler()} className={header.column.getCanSort() ? 'sortable' : ''}><table.FlexRender header={header} />{header.column.getIsSorted() === 'asc' ? ' ↑' : header.column.getIsSorted() === 'desc' ? ' ↓' : ''}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map((row) => <tr key={row.id} className={selected?.id === row.original.id ? 'selected' : ''} tabIndex={0} onClick={() => setSelected(row.original)} onKeyDown={(event) => { if (event.key === 'Enter') setSelected(row.original); }}>{row.getVisibleCells().map((cell) => <td key={cell.id}><table.FlexRender cell={cell} /></td>)}</tr>)}</tbody></table></div>}
      <footer className="table-footer"><span>Page {table.state.pagination.pageIndex + 1} of {table.getPageCount()}</span><div><Button variant="ghost" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label="Previous page"><ChevronLeft size={16} /></Button><Button variant="ghost" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label="Next page"><ChevronRight size={16} /></Button></div></footer>
    </div>
    {selected && <div className="drawer-backdrop" onMouseDown={() => setSelected(null)}><aside className="preview-drawer" aria-label="Investigation preview" onMouseDown={(event) => event.stopPropagation()}><header><div><SeverityIndicator severity={selected.severity} /><h2>{selected.id}</h2><p>{selected.title}</p></div><button className="icon-button" onClick={() => setSelected(null)} aria-label="Close preview"><X size={18} /></button></header><div className="drawer-content"><div className="drawer-temp"><strong>{temperature(selected.temperature)}</strong><span>Allowed {range(selected.allowedMin, selected.allowedMax)}</span></div><dl><div><dt>Shipment</dt><dd>{selected.shipment}</dd></div><div><dt>Product</dt><dd>{present(selected.product)}</dd></div><div><dt>Sensor</dt><dd>{present(selected.sensor)}</dd></div><div><dt>Breach duration</dt><dd>{minutes(selected.breachMinutes)}</dd></div><div><dt>Governance</dt><dd><GovernanceIndicator decision={selected.governance} /></dd></div><div><dt>Reviewer</dt><dd>{selected.reviewer ?? 'Unassigned'}</dd></div></dl><div className="drawer-notice"><strong>Preview only</strong><span>Consequential decisions are available only in the full investigation workspace.</span></div></div><footer><Button variant="primary" onClick={() => navigate(`/investigation/${selected.id}`)}>Open investigation <ArrowRight size={15} /></Button><Button variant="ghost" onClick={() => setSelected(null)}>Close</Button></footer></aside></div>}
  </div>;
}
