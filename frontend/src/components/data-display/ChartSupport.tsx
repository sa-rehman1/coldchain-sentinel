import type { ReactNode } from 'react';

// Shared with chart components so every operational series keeps the same meaning.
// eslint-disable-next-line react-refresh/only-export-components
export const CHART_COLORS = {
  primary: '#3478F6',
  healthy: '#38A878',
  warning: '#D58A28',
  critical: '#DC5B5B',
  informational: '#5F78A6',
  muted: '#90989F',
} as const;

interface TooltipEntry {
  color?: string;
  dataKey?: string | number;
  name?: string | number;
  value?: string | number | readonly (string | number)[];
}

export function ChartTooltip({ active, label, payload, units = {} }: { active?: boolean; label?: ReactNode; payload?: readonly TooltipEntry[]; units?: Record<string, string> }) {
  if (!active || !payload?.length) return null;
  const entries = payload.filter((entry) => entry.value !== null && entry.value !== undefined);
  if (!entries.length) return null;
  return <div className="chart-tooltip"><span className="chart-tooltip-label">{label}</span>{entries.map((entry) => {
    const key = String(entry.dataKey ?? entry.name ?? 'value');
    const value = Array.isArray(entry.value) ? entry.value.join('–') : String(entry.value);
    return <div key={key}><i style={{ backgroundColor: entry.color ?? CHART_COLORS.muted }} /><span>{entry.name ?? key}</span><strong>{value}{units[key] ?? ''}</strong></div>;
  })}</div>;
}

export function ChartLegend({ items }: { items: Array<{ label: string; color: string; detail?: string }> }) {
  return <div className="custom-chart-legend" aria-label="Chart legend">{items.map((item) => <span key={item.label}><i style={{ backgroundColor: item.color }} /><span>{item.label}</span>{item.detail && <small>{item.detail}</small>}</span>)}</div>;
}
