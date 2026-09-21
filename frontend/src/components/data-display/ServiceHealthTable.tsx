import { ExternalLink, Search } from 'lucide-react';
import type { ServiceHealth } from '../../data/contracts';
import { Badge, Button, StatusDot } from '../ui/Primitives';

export function ServiceHealthTable({ services }: { services: ServiceHealth[] }) {
  return <div className="service-health-table"><div className="service-health-head"><span>Service</span><span>Status</span><span>Operational signal</span><span>Latency / lag</span><span>Last check</span><span>Action</span></div>{services.map((service) => {
    const action = service.url ? 'Open' : 'Inspect';
    return <div className="service-health-row" key={service.name}><div className="service-name"><StatusDot state={service.state} /><strong>{service.name}</strong></div><Badge tone={service.state === 'healthy' ? 'success' : service.state === 'degraded' ? 'warning' : 'critical'}>{service.state}</Badge><span className="service-signal">{service.detail}</span><span className="service-latency">{service.latency}</span><span className="service-check">{service.state === 'degraded' ? '1 min ago' : 'Just now'}</span><Button variant="ghost" onClick={() => service.url && window.open(service.url, '_blank', 'noopener,noreferrer')}>{action}{service.url ? <ExternalLink size={13} /> : <Search size={13} />}</Button></div>;
  })}</div>;
}
