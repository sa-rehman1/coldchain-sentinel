import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Bell, Search, ShieldCheck, UserRound } from 'lucide-react';
import { useState, type FormEvent, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { localIdentities, useControlTowerContext, type ControlTowerNotification } from '../../app/ControlTowerContext';
import { dataSourceMode } from '../../data/source';
import { useIncidents } from '../../hooks/useControlTower';
import { Button, Menu, MenuItem, Modal, StatusDot } from '../ui/Primitives';
import { Brand } from './Brand';

const navigation = [
  { to: '/', label: 'Command Center' },
  { to: '/incidents', label: 'Incidents' },
  { to: '/governed-ai', label: 'Governed AI' },
  { to: '/observability', label: 'Observability' },
  { to: '/demo-lab', label: 'Demo Lab' },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState('');
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const { persona, setPersona, toast, notifications, readNotificationIds, markNotificationRead, markAllNotificationsRead } = useControlTowerContext();
  const { data: incidents = [] } = useIncidents();
  const navigate = useNavigate();
  const displayedNotifications = dataSourceMode === 'api' ? deriveNotifications(incidents, readNotificationIds) : notifications;
  const unreadCount = displayedNotifications.filter((item) => !item.read).length;
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const normalized = query.trim().toUpperCase();
    if (/^INC-\d{4}$/.test(normalized)) void navigate(`/investigation/${normalized}`);
    else void navigate('/incidents');
    setMobileSearchOpen(false);
  };
  const initials = persona.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase();

  return <div className="app-shell light-shell">
    <header className="app-header">
      <div className="app-header-inner">
        <div className="header-brand"><Brand /><span><StatusDot state="healthy" />{dataSourceMode === 'api' ? 'Local demo · API' : 'Local demo · Mock'}</span></div>
        <nav className="top-navigation" aria-label="Primary navigation">{navigation.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}</nav>
        <div className="header-actions">
          <form className="header-search" onSubmit={submitSearch}><Search size={17} aria-hidden="true" /><input aria-label="Global incident search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search incidents" /></form>
          <button className="header-icon-button mobile-search-trigger" onClick={() => setMobileSearchOpen(true)} aria-label="Open incident search"><Search size={18} /></button>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild><button className="header-icon-button notification-trigger" aria-label={`Notifications, ${unreadCount} unread`}><Bell size={18} />{unreadCount > 0 && <span className="notification-count" aria-hidden="true">{unreadCount}</span>}</button></DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content className="notification-popover" align="end" sideOffset={10} collisionPadding={12} aria-label="Notifications">
              <div className="notification-header"><div><strong>Notifications</strong><span>{unreadCount} unread</span></div><button type="button" onClick={() => dataSourceMode === 'api' ? displayedNotifications.forEach((item) => markNotificationRead(item.id)) : markAllNotificationsRead()} disabled={unreadCount === 0}>Mark all as read</button></div>
              <div className="notification-list">{displayedNotifications.map((item) => <DropdownMenu.Item className={`notification-item ${item.read ? 'read' : 'unread'}`} key={item.id} onSelect={() => { markNotificationRead(item.id); void navigate(item.href); }} aria-label={`${item.title}. ${item.message}. ${item.time}. ${item.action}`}>
                <span className={`notification-severity notification-${item.severity}`} aria-label={`Severity: ${item.severity}`} />
                <span className="notification-copy"><strong>{item.title}</strong><span>{item.message}</span><small>{item.time}</small><em>{item.action}</em></span>
                {!item.read && <span className="notification-unread" aria-label="Unread" />}
              </DropdownMenu.Item>)}</div>
              <DropdownMenu.Arrow className="notification-arrow" />
            </DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>
          <div className="header-system-status" title="All local demonstration services available"><StatusDot state="healthy" /><span>Operational</span></div>
          <Menu label={<><span className="reviewer-avatar" aria-hidden="true">{initials}</span><span className="reviewer-name"><small>Local demonstration identity</small>{persona}</span><UserRound className="reviewer-fallback" size={17} /></>}>
            {(Object.keys(localIdentities) as Array<keyof typeof localIdentities>).map((role) => <MenuItem className="dropdown-item" key={role} onSelect={() => setPersona(role)}>{role}{role === persona && <ShieldCheck size={15} />}</MenuItem>)}
          </Menu>
        </div>
      </div>
    </header>
    <main className="app-main">{children}</main>
    <Modal open={mobileSearchOpen} onOpenChange={setMobileSearchOpen} title="Search incidents" description="Enter an incident ID or search the incident queue."><form className="mobile-search-form" onSubmit={submitSearch}><label htmlFor="mobile-incident-search">Incident or shipment</label><div><Search size={17} aria-hidden="true" /><input id="mobile-incident-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search incidents" autoFocus /></div><Button variant="primary" type="submit">Search</Button></form></Modal>
    {toast && <div className="toast" role="status"><span className="toast-check">✓</span>{toast}</div>}
  </div>;
}

function deriveNotifications(incidents: import('../../data/contracts').Incident[], readIds: ReadonlySet<string>): ControlTowerNotification[] {
  return incidents.flatMap((incident) => {
    const items: ControlTowerNotification[] = [];
    if (incident.severity === 'critical' && incident.state !== 'completed') items.push({ id: `critical-${incident.id}`, title: 'Critical temperature breach', message: `Shipment ${incident.shipment} requires attention.`, time: `${incident.createdMinutesAgo} minutes ago`, severity: 'critical', action: 'Open incident', href: `/investigation/${incident.id}`, read: readIds.has(`critical-${incident.id}`) });
    const expiry = incident.recommendationExpiresAt ? Date.parse(incident.recommendationExpiresAt) - Date.now() : Number.POSITIVE_INFINITY;
    if (expiry > 0 && expiry <= 10 * 60_000) items.push({ id: `expiry-${incident.id}`, title: 'Approval expiring soon', message: `The recommendation for ${incident.id} expires soon.`, time: 'Current', severity: 'warning', action: 'Review decision', href: `/investigation/${incident.id}#decision`, read: readIds.has(`expiry-${incident.id}`) });
    if (incident.governance === 'fallback') items.push({ id: `fallback-${incident.id}`, title: 'Fallback recommendation used', message: `Deterministic fallback handled ${incident.id}.`, time: `${incident.createdMinutesAgo} minutes ago`, severity: 'informational', action: 'View details', href: `/investigation/${incident.id}`, read: readIds.has(`fallback-${incident.id}`) });
    if (incident.state === 'completed' || incident.state === 'rejected') items.push({ id: `decision-${incident.id}`, title: 'Decision recorded', message: `${incident.id} reached ${incident.state}.`, time: `${incident.createdMinutesAgo} minutes ago`, severity: 'informational', action: 'View audit trail', href: `/investigation/${incident.id}`, read: readIds.has(`decision-${incident.id}`) });
    return items;
  });
}
