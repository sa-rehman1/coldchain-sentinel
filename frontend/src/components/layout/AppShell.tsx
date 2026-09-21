import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Bell, Search, ShieldCheck, UserRound } from 'lucide-react';
import { useState, type FormEvent, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { usePrototype } from '../../app/PrototypeContext';
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
  const { persona, setPersona, toast, notifications, markNotificationRead, markAllNotificationsRead } = usePrototype();
  const navigate = useNavigate();
  const unreadCount = notifications.filter((item) => !item.read).length;
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
        <div className="header-brand"><Brand /><span><StatusDot state="healthy" />Local demo</span></div>
        <nav className="top-navigation" aria-label="Primary navigation">{navigation.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}</nav>
        <div className="header-actions">
          <form className="header-search" onSubmit={submitSearch}><Search size={17} aria-hidden="true" /><input aria-label="Global incident search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search incidents" /></form>
          <button className="header-icon-button mobile-search-trigger" onClick={() => setMobileSearchOpen(true)} aria-label="Open incident search"><Search size={18} /></button>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild><button className="header-icon-button notification-trigger" aria-label={`Notifications, ${unreadCount} unread`}><Bell size={18} />{unreadCount > 0 && <span className="notification-count" aria-hidden="true">{unreadCount}</span>}</button></DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content className="notification-popover" align="end" sideOffset={10} collisionPadding={12} aria-label="Notifications">
              <div className="notification-header"><div><strong>Notifications</strong><span>{unreadCount} unread</span></div><button type="button" onClick={markAllNotificationsRead} disabled={unreadCount === 0}>Mark all as read</button></div>
              <div className="notification-list">{notifications.map((item) => <DropdownMenu.Item className={`notification-item ${item.read ? 'read' : 'unread'}`} key={item.id} onSelect={() => { markNotificationRead(item.id); void navigate(item.href); }} aria-label={`${item.title}. ${item.message}. ${item.time}. ${item.action}`}>
                <span className={`notification-severity notification-${item.severity}`} aria-label={`Severity: ${item.severity}`} />
                <span className="notification-copy"><strong>{item.title}</strong><span>{item.message}</span><small>{item.time}</small><em>{item.action}</em></span>
                {!item.read && <span className="notification-unread" aria-label="Unread" />}
              </DropdownMenu.Item>)}</div>
              <DropdownMenu.Arrow className="notification-arrow" />
            </DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>
          <div className="header-system-status" title="All local prototype services available"><StatusDot state="healthy" /><span>Operational</span></div>
          <Menu label={<><span className="reviewer-avatar" aria-hidden="true">{initials}</span><span className="reviewer-name">{persona}</span><UserRound className="reviewer-fallback" size={17} /></>}>
            {(['Quality reviewer', 'Operations lead', 'Read-only auditor'] as const).map((role) => <MenuItem className="dropdown-item" key={role} onSelect={() => setPersona(role)}>{role}{role === persona && <ShieldCheck size={15} />}</MenuItem>)}
          </Menu>
        </div>
      </div>
    </header>
    <main className="app-main">{children}</main>
    <Modal open={mobileSearchOpen} onOpenChange={setMobileSearchOpen} title="Search incidents" description="Enter an incident ID or search the incident queue."><form className="mobile-search-form" onSubmit={submitSearch}><label htmlFor="mobile-incident-search">Incident or shipment</label><div><Search size={17} aria-hidden="true" /><input id="mobile-incident-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search incidents" autoFocus /></div><Button variant="primary" type="submit">Search</Button></form></Modal>
    {toast && <div className="toast" role="status"><span className="toast-check">✓</span>{toast}</div>}
  </div>;
}
