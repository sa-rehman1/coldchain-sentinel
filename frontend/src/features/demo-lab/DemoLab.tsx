import { ArrowRight, CheckCircle2, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { localIdentities, usePrototype } from '../../app/PrototypeContext';
import { Button } from '../../components/ui/Primitives';
import { GovernanceIndicator, SeverityIndicator } from '../../components/ui/StatusIndicators';
import type { Incident, Scenario } from '../../data/contracts';
import { dataSourceMode } from '../../data/source';
import { useDemoRun, useScenarios, useStartScenario } from '../../hooks/useControlTower';

const progressSteps = [
  ['Sensor report', 'Unsafe temperature received'],
  ['Policy', 'Safety rules evaluated telemetry'],
  ['Evidence', 'Sensor evidence and trusted instructions collected'],
  ['AI advisory', 'Bounded recommendation created'],
  ['Governance', 'Deterministic controls completed'],
  ['Incident', 'Investigation ready when required'],
] as const;
const groups = [
  { name: 'Operations', ids: ['healthy', 'critical', 'sustained', 'stale', 'duplicate'] },
  { name: 'AI safety', ids: ['fallback'] },
] as const;

export function DemoLab() {
  const { persona, addSimulatedIncident, restore, setDisplayMode, decisionVariant, setDecisionVariant, notify } = usePrototype();
  const identity = localIdentities[persona];
  const { data = [], isError, error } = useScenarios(identity);
  const starter = useStartScenario();
  const [running, setRunning] = useState<Scenario | null>(null);
  const [completed, setCompleted] = useState<Scenario | null>(null);
  const [mockProgress, setMockProgress] = useState(0);
  const [runId, setRunId] = useState<string | null>(null);
  const [category, setCategory] = useState<(typeof groups)[number]['name']>('Operations');
  const { data: runStatus } = useDemoRun(runId, identity);
  const navigate = useNavigate();
  const recommended = data.find((scenario) => scenario.id === 'sustained');
  const activeGroup = groups.find((group) => group.name === category)!;
  const progress = dataSourceMode === 'api' && runStatus ? Object.values(runStatus.steps).filter(Boolean).length : mockProgress;
  const authoritativeComplete = runStatus?.status === 'INCIDENT_READY' || runStatus?.status === 'COMPLETED_WITHOUT_INCIDENT';
  const completedScenario = dataSourceMode === 'api' && authoritativeComplete ? running : completed;

  const run = async (scenario: Scenario) => {
    setRunning(scenario); setCompleted(null); setMockProgress(0); setRunId(null);
    if (dataSourceMode === 'api') {
      try { setRunId((await starter.mutateAsync({ id: scenario.id, identity })).runId); }
      catch (runError) { notify(runError instanceof Error ? runError.message : 'Scenario could not be started.'); setRunning(null); }
      return;
    }
    setMockProgress(1);
    progressSteps.slice(1).forEach((_, index) => window.setTimeout(() => setMockProgress(index + 2), 260 * (index + 1)));
    window.setTimeout(() => {
      if (scenario.variant === 'healthy') setDisplayMode('empty');
      else { setDisplayMode('default'); addSimulatedIncident(scenarioIncident(scenario)); }
      setCompleted(scenario); notify(`${scenario.title} completed · local simulation`);
    }, 260 * progressSteps.length);
  };
  const restoreAll = () => { restore(); setRunning(null); setCompleted(null); setMockProgress(0); setRunId(null); };
  const openIncident = () => {
    if (!completedScenario) return;
    if (runStatus?.incidentId) void navigate(`/investigation/${runStatus.incidentId}`);
    else void navigate(completedScenario.variant === 'healthy' ? '/incidents' : `/investigation/SIM-${completedScenario.id.toUpperCase()}`);
  };

  return <div className="page demo-page demo-polished">
    <div className="page-intro compact"><div><p>Guided product demonstration</p><h1>Demo Lab</h1><span>{dataSourceMode === 'api' ? 'Synthetic telemetry flows through Kafka and the authoritative local workflow' : 'Deterministic browser-local prototype data'}</span></div>{dataSourceMode === 'mock' && <Button variant="ghost" onClick={restoreAll}><RotateCcw size={15} />Restore prototype data</Button>}</div>
    {isError && <section className="run-progress polished"><strong>Demo API unavailable</strong><p>{error instanceof Error ? error.message : 'The backend could not be reached.'}</p></section>}
    {recommended && <section className="recommended-demo polished"><div className="recommended-copy"><span className="recommended-label">Recommended demo</span><h2>{recommended.title}</h2><h3>The best end-to-end demonstration of ColdChain Sentinel</h3><div className="demo-meta"><span><strong>Kafka</strong>Telemetry transport</span><span><strong>PostgreSQL</strong>Durable evidence</span><span><strong>Required</strong>Human action</span><span><strong>Disabled</strong>External AI</span></div><Button variant="primary" onClick={() => void run(recommended)} disabled={starter.isPending || Boolean(running && !completedScenario)}><Play size={16} />Start guided demo</Button></div><ol className="guided-sequence">{progressSteps.map(([title, detail], index) => <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><small>{detail}</small></div>{index < progressSteps.length - 1 && <ArrowRight size={15} aria-hidden="true" />}</li>)}</ol></section>}
    {running && <section className="run-progress polished" aria-live="polite"><div className="run-title"><div><span>{dataSourceMode === 'api' ? 'Authoritative local run' : 'Guided simulation'}</span><strong>{running.title}</strong></div><strong>{completedScenario ? 'Complete' : `Step ${Math.min(progress, progressSteps.length)} of ${progressSteps.length}`}</strong></div><div className="guided-progress">{progressSteps.map(([title, detail], index) => <div className={progress > index ? 'complete' : progress === index ? 'active' : ''} key={title}><span>{progress > index ? <CheckCircle2 size={16} /> : index + 1}</span><div><strong>{title}</strong><small>{progress > index ? detail : 'Waiting for authoritative state'}</small></div></div>)}</div>{completedScenario && <div className="scenario-result polished"><div><small>{runStatus?.incidentId || dataSourceMode === 'mock' ? 'Incident created' : 'Workflow result'}</small><strong className="mono">{runStatus?.incidentId ?? (dataSourceMode === 'api' ? 'No unsafe incident' : `SIM-${completedScenario.id.toUpperCase()}`)}</strong></div><div><small>Severity</small><SeverityIndicator severity={completedScenario.variant === 'critical' ? 'critical' : 'warning'} /></div><div><small>Expected outcome</small><strong>{completedScenario.policyOutcome}</strong></div><div><small>Governance</small><GovernanceIndicator decision={completedScenario.governanceOutcome.toLowerCase().includes('approval') ? 'approval-required' : 'allowed'} /></div><div className="result-actions"><Button variant="primary" onClick={openIncident}>{runStatus?.incidentId || dataSourceMode === 'mock' ? 'Open incident investigation' : 'View incident queue'} <ArrowRight size={15} /></Button><Button variant="secondary" onClick={() => void run(completedScenario)}>Run again</Button>{dataSourceMode === 'mock' && <Button variant="ghost" onClick={restoreAll}>Restore prototype data</Button>}</div></div>}</section>}
    <section className="scenario-library"><header><div><span>Scenario library</span><h2>Execute supported safeguards</h2></div><div className="internal-tabs" role="tablist" aria-label="Scenario categories">{groups.map((group) => <button role="tab" aria-selected={category === group.name} key={group.name} onClick={() => setCategory(group.name)}>{group.name}</button>)}</div></header><div className="scenario-rows">{data.filter((scenario) => (activeGroup.ids as readonly string[]).includes(scenario.id)).map((scenario) => <ScenarioRow key={scenario.id} scenario={scenario} run={(selected) => void run(selected)} running={running?.id === scenario.id && !completed} />)}</div></section>
    {dataSourceMode === 'mock' && <section className="fixture-controls" aria-label="Prototype state controls"><div><span>Design-review states</span><strong>Preview exceptional interface states</strong></div><Button variant="ghost" onClick={() => setDisplayMode('empty')}>Empty queue</Button><Button variant="ghost" onClick={() => setDisplayMode('disconnected')}>Disconnected</Button><Button variant="ghost" onClick={() => setDisplayMode('permission-denied')}>Permission denied</Button><label>Decision response<select aria-label="Decision response variant" value={decisionVariant} onChange={(event) => setDecisionVariant(event.target.value as typeof decisionVariant)}><option value="success">Success</option><option value="conflict">Idempotency conflict</option><option value="expiry">Expired recommendation</option><option value="authorization-failure">Authorization failure</option><option value="uncertain-timeout">Uncertain timeout</option></select></label></section>}
    {dataSourceMode === 'mock' && <p className="fixture-reset-note"><strong>Restore prototype data</strong> affects only this browser’s in-memory fixture state. It never modifies databases, containers, or Docker volumes.</p>}
  </div>;
}

function ScenarioRow({ scenario, run, running }: { scenario: Scenario; run: (scenario: Scenario) => void; running: boolean }) { return <article className="scenario-row"><div><h3>{scenario.title}</h3><p>{scenario.demonstrates}.</p></div><div><span>Expected outcome</span><strong>{scenario.policyOutcome}</strong></div><div><span>Human action</span><strong>{scenario.humanAction}</strong></div><Button variant="secondary" onClick={() => run(scenario)} disabled={running}><Play size={14} />Run</Button></article>; }

function scenarioIncident(scenario: Scenario): Incident {
  return { id: `SIM-${scenario.id.toUpperCase()}`, severity: scenario.variant === 'critical' ? 'critical' : 'warning', title: scenario.title, shipment: 'CCS-DEMO-2048', product: 'Synthetic demo cargo', sensor: 'SEN-DEMO-01', temperature: scenario.variant === 'critical' ? 12.4 : 8.7, allowedMin: 2, allowedMax: 8, breachMinutes: 22, state: 'awaiting-review', governance: scenario.variant === 'fallback' ? 'fallback' : 'approval-required', createdMinutesAgo: 0, reviewer: null, route: { from: 'Chicago', via: 'In transit', to: 'Denver', progress: 50 }, productSensitivity: 'Synthetic fixture', sensorHealth: 'Nominal · simulated', breachKind: scenario.variant === 'critical' ? 'immediate' : 'sustained' };
}
