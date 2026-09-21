import { ArrowRight, CheckCircle2, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePrototype } from '../../app/PrototypeContext';
import { Button } from '../../components/ui/Primitives';
import { GovernanceIndicator, SeverityIndicator } from '../../components/ui/StatusIndicators';
import type { Incident, Scenario } from '../../data/contracts';
import { useScenarios } from '../../hooks/useControlTower';

const progressSteps = [
  ['Sensor report', 'Unsafe temperature received'],
  ['Policy', 'Safety rules created an incident'],
  ['Evidence', 'Sensor evidence was saved and trusted instructions were found'],
  ['AI advisory', 'Recommendation validated locally'],
  ['Governance', 'Human approval required'],
  ['Reviewer', 'Simulated shipment hold ready'],
] as const;
const groups = [
  { name: 'Operations', ids: ['healthy', 'critical', 'sustained', 'stale', 'duplicate', 'conflict'] },
  { name: 'AI safety', ids: ['insufficient', 'injection', 'fallback'] },
  { name: 'Governance', ids: ['expired', 'unauthorized', 'kill-switch'] },
] as const;

export function DemoLab() {
  const { data = [] } = useScenarios();
  const { addSimulatedIncident, restore, setDisplayMode, decisionVariant, setDecisionVariant, notify } = usePrototype();
  const [running, setRunning] = useState<Scenario | null>(null);
  const [completed, setCompleted] = useState<Scenario | null>(null);
  const [progress, setProgress] = useState(0);
  const [category, setCategory] = useState<(typeof groups)[number]['name']>('Operations');
  const navigate = useNavigate();
  const recommended = data.find((scenario) => scenario.id === 'sustained');

  const run = (scenario: Scenario) => {
    setRunning(scenario); setCompleted(null); setProgress(1);
    progressSteps.slice(1).forEach((_, index) => window.setTimeout(() => setProgress(index + 2), 260 * (index + 1)));
    window.setTimeout(() => {
      const generated = scenarioIncident(scenario);
      if (scenario.variant === 'healthy') setDisplayMode('empty');
      else if (scenario.variant === 'unauthorized') setDisplayMode('permission-denied');
      else { setDisplayMode('default'); addSimulatedIncident(generated); }
      setCompleted(scenario); notify(`${scenario.title} completed · local simulation`);
    }, 260 * progressSteps.length);
  };
  const restoreAll = () => { restore(); setRunning(null); setCompleted(null); setProgress(0); };
  const openIncident = () => { if (completed) void navigate(completed.variant === 'healthy' ? '/incidents' : `/investigation/SIM-${completed.id.toUpperCase()}`); };
  const activeGroup = groups.find((group) => group.name === category)!;

  return <div className="page demo-page demo-polished">
    <div className="page-intro compact"><div><p>Guided product demonstration</p><h1>Demo Lab</h1><span>Show the governed workflow with deterministic, browser-local data</span></div><Button variant="ghost" onClick={restoreAll}><RotateCcw size={15} />Restore prototype data</Button></div>

    {recommended && <section className="recommended-demo polished"><div className="recommended-copy"><span className="recommended-label">Recommended demo</span><h2>Sustained temperature breach</h2><h3>The best end-to-end demonstration of ColdChain Sentinel</h3><div className="demo-meta"><span><strong>~30 sec</strong>Estimated duration</span><span><strong>Shipment hold</strong>Expected result</span><span><strong>Required</strong>Human action</span><span><strong>Disabled</strong>External AI</span></div><Button variant="primary" onClick={() => run(recommended)} disabled={running?.id === recommended.id && !completed}><Play size={16} />Start guided demo</Button></div><ol className="guided-sequence">{progressSteps.map(([title, detail], index) => <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><small>{detail}</small></div>{index < progressSteps.length - 1 && <ArrowRight size={15} aria-hidden="true" />}</li>)}</ol></section>}

    {running && <section className="run-progress polished" aria-live="polite"><div className="run-title"><div><span>Guided simulation</span><strong>{running.title}</strong></div><strong>{completed ? 'Complete' : `Step ${Math.min(progress, progressSteps.length)} of ${progressSteps.length}`}</strong></div><div className="guided-progress">{progressSteps.map(([title, detail], index) => <div className={progress > index ? 'complete' : progress === index ? 'active' : ''} key={title}><span>{progress > index ? <CheckCircle2 size={16} /> : index + 1}</span><div><strong>{title}</strong><small>{progress > index ? detail : 'Waiting'}</small></div></div>)}</div>{completed && <div className="scenario-result polished"><div><small>Incident created</small><strong className="mono">SIM-{completed.id.toUpperCase()}</strong></div><div><small>Severity</small><SeverityIndicator severity={completed.variant === 'critical' || completed.variant === 'conflict' ? 'critical' : 'warning'} /></div><div><small>Recommended action</small><strong>{completed.variant === 'healthy' ? 'Continue monitoring' : 'Hold shipment'}</strong></div><div><small>Governance result</small><GovernanceIndicator decision={completed.governanceOutcome.toLowerCase().includes('approval') ? 'approval-required' : completed.governanceOutcome.toLowerCase().includes('block') ? 'blocked' : 'allowed'} /></div><div><small>Human review</small><strong>{requiresHuman(completed) ? 'Required' : 'Not required'}</strong></div><div className="result-actions"><Button variant="primary" onClick={openIncident}>Open incident investigation <ArrowRight size={15} /></Button><Button variant="secondary" onClick={() => run(completed)}>Run again</Button><Button variant="ghost" onClick={restoreAll}>Restore prototype data</Button></div></div>}</section>}

    <section className="scenario-library"><header><div><span>Scenario library</span><h2>Explore additional safeguards</h2></div><div className="internal-tabs" role="tablist" aria-label="Scenario categories">{groups.map((group) => <button role="tab" aria-selected={category === group.name} key={group.name} onClick={() => setCategory(group.name)}>{group.name}</button>)}</div></header><div className="scenario-rows">{data.filter((scenario) => (activeGroup.ids as readonly string[]).includes(scenario.id)).map((scenario) => <ScenarioRow key={scenario.id} scenario={scenario} run={run} running={running?.id === scenario.id && !completed} />)}</div></section>

    <section className="fixture-controls" aria-label="Prototype state controls"><div><span>Design-review states</span><strong>Preview exceptional interface states</strong></div><Button variant="ghost" onClick={() => setDisplayMode('empty')}>Empty queue</Button><Button variant="ghost" onClick={() => setDisplayMode('disconnected')}>Disconnected</Button><Button variant="ghost" onClick={() => setDisplayMode('permission-denied')}>Permission denied</Button><label>Decision response<select aria-label="Decision response variant" value={decisionVariant} onChange={(event) => setDecisionVariant(event.target.value as typeof decisionVariant)}><option value="success">Success</option><option value="conflict">Idempotency conflict</option><option value="expiry">Expired recommendation</option><option value="authorization-failure">Authorization failure</option><option value="uncertain-timeout">Uncertain timeout</option></select></label></section>
    <p className="fixture-reset-note"><strong>Restore prototype data</strong> affects only this browser’s in-memory fixture state. It never modifies databases, containers, or Docker volumes.</p>
  </div>;
}

function ScenarioRow({ scenario, run, running }: { scenario: Scenario; run: (scenario: Scenario) => void; running: boolean }) { return <article className="scenario-row"><div><h3>{scenario.title}</h3><p>{scenario.demonstrates}.</p></div><div><span>Expected outcome</span><strong>{scenario.policyOutcome}</strong></div><div><span>Human review</span><strong>{requiresHuman(scenario) ? 'Yes' : 'No'}</strong></div><Button variant="secondary" onClick={() => run(scenario)} disabled={running}><Play size={14} />Run</Button></article>; }

const requiresHuman = (scenario: Scenario) => !['healthy', 'duplicate'].includes(scenario.id);

function scenarioIncident(scenario: Scenario): Incident {
  return { id: `SIM-${scenario.id.toUpperCase()}`, severity: scenario.variant === 'critical' || scenario.variant === 'conflict' ? 'critical' : 'warning', title: scenario.title, shipment: 'CCS-DEMO-2048', product: 'Synthetic vaccine payload', sensor: 'SEN-DEMO-01', temperature: scenario.variant === 'critical' ? 12.4 : 8.7, allowedMin: 2, allowedMax: 8, breachMinutes: 22, state: 'awaiting-review', governance: scenario.variant === 'fallback' ? 'fallback' : scenario.variant === 'insufficient' || scenario.variant === 'kill-switch' ? 'blocked' : 'approval-required', createdMinutesAgo: 0, reviewer: null, route: { from: 'Chicago', via: 'In transit', to: 'Denver', progress: 50 }, productSensitivity: 'Synthetic fixture', sensorHealth: scenario.variant === 'stale' ? 'Degraded · stale' : 'Nominal · simulated', breachKind: scenario.variant === 'critical' ? 'sustained' : 'none' };
}
