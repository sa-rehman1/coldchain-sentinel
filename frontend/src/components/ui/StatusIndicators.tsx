import { CheckCircle2, CircleAlert, Clock3, RotateCcw, ShieldX, UserCheck } from 'lucide-react';
import type { GovernanceDecision, Severity, WorkflowState } from '../../data/contracts';

const severityConfig: Record<Severity, { label: string; icon: typeof CircleAlert; tone: string }> = {
  critical: { label: 'Critical', icon: CircleAlert, tone: 'critical' },
  warning: { label: 'High', icon: CircleAlert, tone: 'high' },
  normal: { label: 'Normal', icon: CheckCircle2, tone: 'normal' },
};

const governanceConfig: Record<GovernanceDecision | 'pending', { label: string; icon: typeof CircleAlert; tone: string }> = {
  'approval-required': { label: 'Approval required', icon: UserCheck, tone: 'approval' },
  allowed: { label: 'Allowed', icon: CheckCircle2, tone: 'allowed' },
  blocked: { label: 'Blocked', icon: ShieldX, tone: 'blocked' },
  fallback: { label: 'Fallback', icon: RotateCcw, tone: 'fallback' },
  pending: { label: 'Pending', icon: Clock3, tone: 'pending' },
};

const workflowLabels: Record<WorkflowState, string> = {
  triage: 'Triage',
  investigating: 'Investigating',
  'awaiting-review': 'Awaiting review',
  rejected: 'Rejected',
  completed: 'Completed',
};

export function SeverityIndicator({ severity }: { severity: Severity }) {
  const config = severityConfig[severity];
  const Icon = config.icon;
  return <span className={`state-indicator severity-indicator indicator-${config.tone}`} aria-label={`Severity: ${config.label}`}><Icon size={14} aria-hidden="true" /><span>{config.label}</span></span>;
}

export function GovernanceIndicator({ decision }: { decision: GovernanceDecision | 'pending' }) {
  const config = governanceConfig[decision];
  const Icon = config.icon;
  return <span className={`state-indicator governance-indicator indicator-${config.tone}`} aria-label={`Governance: ${config.label}`}><Icon size={14} aria-hidden="true" /><span>{config.label}</span></span>;
}

export function WorkflowIndicator({ state }: { state: WorkflowState }) {
  return <span className="state-indicator workflow-indicator" aria-label={`Workflow: ${workflowLabels[state]}`}><Clock3 size={14} aria-hidden="true" /><span>{workflowLabels[state]}</span></span>;
}
