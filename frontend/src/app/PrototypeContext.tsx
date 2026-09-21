import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { AuditEvent, Incident } from '../data/contracts';

export type Persona = 'Quality reviewer' | 'Operations lead' | 'Read-only auditor';
type DisplayMode = 'default' | 'empty' | 'disconnected' | 'permission-denied';
export type DecisionVariant = 'success' | 'conflict' | 'expiry' | 'authorization-failure' | 'uncertain-timeout';
export type NotificationSeverity = 'critical' | 'warning' | 'informational';

export interface PrototypeNotification {
  id: string;
  title: string;
  message: string;
  time: string;
  severity: NotificationSeverity;
  action: string;
  href: string;
  read: boolean;
}

const createNotifications = (): PrototypeNotification[] => [
  { id: 'critical-temperature', title: 'Critical temperature breach', message: 'Shipment CCS-CHI-1842 has remained above its safe range for 47 minutes.', time: '2 minutes ago', severity: 'critical', action: 'Open incident', href: '/investigation/INC-2481', read: false },
  { id: 'approval-expiring', title: 'Approval expiring soon', message: 'The hold recommendation for INC-2481 expires in 9 minutes.', time: 'Just now', severity: 'warning', action: 'Review decision', href: '/investigation/INC-2481#decision', read: false },
  { id: 'fallback-used', title: 'Fallback recommendation used', message: 'The model provider was unavailable for INC-2478. Deterministic safety rules requested an inspection.', time: '1 hour ago', severity: 'informational', action: 'View details', href: '/investigation/INC-2478', read: false },
];

interface PrototypeState {
  persona: Persona;
  setPersona: (persona: Persona) => void;
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  decisionVariant: DecisionVariant;
  setDecisionVariant: (variant: DecisionVariant) => void;
  simulatedIncidents: Incident[];
  addSimulatedIncident: (incident: Incident) => void;
  auditEvents: AuditEvent[];
  addAuditEvent: (event: AuditEvent) => void;
  restore: () => void;
  toast: string | null;
  notify: (message: string) => void;
  notifications: PrototypeNotification[];
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
}

const PrototypeContext = createContext<PrototypeState | null>(null);
const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });

export function PrototypeProvider({ children, initialPersona = 'Quality reviewer', initialDisplayMode = 'default' }: { children: ReactNode; initialPersona?: Persona; initialDisplayMode?: DisplayMode }) {
  const [persona, setPersona] = useState<Persona>(initialPersona);
  const [displayMode, setDisplayMode] = useState<DisplayMode>(initialDisplayMode);
  const [decisionVariant, setDecisionVariant] = useState<DecisionVariant>('success');
  const [simulatedIncidents, setSimulatedIncidents] = useState<Incident[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<PrototypeNotification[]>(createNotifications);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3200);
  };

  const value = useMemo<PrototypeState>(() => ({
    persona, setPersona, displayMode, setDisplayMode, decisionVariant, setDecisionVariant, simulatedIncidents,
    addSimulatedIncident: (incident) => setSimulatedIncidents((items) => [incident, ...items]),
    auditEvents, addAuditEvent: (event) => setAuditEvents((items) => [...items, event]),
    restore: () => { setSimulatedIncidents([]); setAuditEvents([]); setDisplayMode('default'); setDecisionVariant('success'); setNotifications(createNotifications()); notify('Prototype fixtures restored'); },
    toast, notify, notifications,
    markNotificationRead: (id) => setNotifications((items) => items.map((item) => item.id === id ? { ...item, read: true } : item)),
    markAllNotificationsRead: () => setNotifications((items) => items.map((item) => ({ ...item, read: true }))),
  }), [persona, displayMode, decisionVariant, simulatedIncidents, auditEvents, toast, notifications]);

  return <QueryClientProvider client={queryClient}><PrototypeContext.Provider value={value}>{children}</PrototypeContext.Provider></QueryClientProvider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePrototype() {
  const context = useContext(PrototypeContext);
  if (!context) throw new Error('usePrototype must be used within PrototypeProvider');
  return context;
}
