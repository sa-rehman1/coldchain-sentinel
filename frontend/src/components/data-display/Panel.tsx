import type { ReactNode } from 'react';

export function Panel({ title, eyebrow, action, children, className = '' }: { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><header className="panel-header"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>{action}</header><div className="panel-body">{children}</div></section>;
}

export function Metric({ label, value, detail, tone = 'default' }: { label: string; value: string | number; detail: string; tone?: 'default' | 'critical' | 'warning' | 'success' }) {
  return <article className={`metric metric-${tone}`}><span className="metric-label">{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

export function KeyValue({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return <div className="key-value"><span>{label}</span><strong className={mono ? 'mono' : ''}>{value}</strong></div>;
}
