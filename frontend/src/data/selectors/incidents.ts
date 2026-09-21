import type { Incident } from '../contracts';

export function selectCriticalIncidents(incidents: Incident[]) {
  return incidents.filter((incident) => incident.severity === 'critical' && incident.state !== 'completed');
}

export function selectApprovalQueue(incidents: Incident[]) {
  return incidents.filter((incident) => incident.governance === 'approval-required' && incident.state !== 'completed');
}

export function deriveIncidentSummary(incidents: Incident[]) {
  const critical = selectCriticalIncidents(incidents);
  const approvalQueue = selectApprovalQueue(incidents);
  return {
    criticalCount: critical.length,
    approvalQueueCount: approvalQueue.length,
    oldestWaitingMinutes: Math.max(0, ...approvalQueue.map((incident) => incident.createdMinutesAgo)),
    sustainedBreachCount: critical.filter((incident) => incident.breachKind === 'sustained').length,
    immediateBreachCount: critical.filter((incident) => incident.breachKind === 'immediate').length,
  };
}
