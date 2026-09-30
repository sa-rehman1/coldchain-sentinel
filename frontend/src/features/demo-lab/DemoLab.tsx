import { ArrowRight, CheckCircle2, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { localIdentities, useControlTowerContext } from '../../app/ControlTowerContext';
import { Button } from '../../components/ui/Primitives';
import { GovernanceIndicator, SeverityIndicator } from '../../components/ui/StatusIndicators';
import type { DemoStageState, Incident, Scenario } from '../../data/contracts';
import { dataSourceMode } from '../../data/source';
import { useDemoRun, useScenarios, useStartScenario } from '../../hooks/useControlTower';

const progressSteps = [
  ['Sensor reading', 'Synthetic temperature readings are received'],
  ['Policy check', 'Deterministic rules detect an unsafe breach'],
  ['Incident created', 'A reviewable incident is stored'],
  ['Evidence collected', 'Sensor facts and trusted SOP guidance are frozen'],
  ['AI advisory', 'A bounded recommendation is produced'],
  ['Governance', 'Deterministic controls decide what is permitted'],
  ['Human review', 'An authorized dispatcher approves or rejects the action'],
] as const;
const groups = [
  { name: 'Operations', ids: ['healthy', 'critical', 'sustained', 'stale', 'duplicate'] },
  { name: 'AI safety', ids: ['fallback'] },
] as const;
const stageKeys = ['sensorReading', 'policyCheck', 'incidentCreated', 'evidenceCollected', 'aiAdvisory', 'governance', 'humanReview'] as const;
const humanReviewPendingText = 'An authorized dispatcher must approve or reject the proposed hold.';

export function DemoLab() {
  const { persona, addSimulatedIncident, restore, setDisplayMode, decisionVariant, setDecisionVariant, notify } = useControlTowerContext();
  const identity = localIdentities[persona];
  const { data = [], isError, error } = useScenarios(identity);
  const starter = useStartScenario();
  const [running, setRunning] = useState<Scenario | null>(null);
  const [completed, setCompleted] = useState<Scenario | null>(null);
  const [mockProgress, setMockProgress] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const [runId, setRunId] = useState<string | null>(() => dataSourceMode === 'api' ? searchParams.get('run') : null);
  const [category, setCategory] = useState<(typeof groups)[number]['name']>('Operations');
  const { data: runStatus } = useDemoRun(runId, identity);
  const navigate = useNavigate();
  const recommended = data.find((scenario) => scenario.id === 'sustained');
  const activeScenario = running ?? data.find((scenario) => scenario.id === runStatus?.scenarioId) ?? null;
  const activeGroup = groups.find((group) => group.name === category)!;
  const authoritativeFinished = Boolean(runStatus && runStatus.resultState !== 'PROCESSING');
  const completedScenario = dataSourceMode === 'api' && authoritativeFinished ? activeScenario : completed;
  const mockRequiresHumanReview = Boolean(
    completedScenario
    && completedScenario.humanAction !== 'None'
    && completedScenario.governanceOutcome.toLowerCase().includes('approval'),
  );
  const awaitingHumanReview = dataSourceMode === 'api'
    ? runStatus?.resultState === 'AWAITING_HUMAN_REVIEW'
    : mockRequiresHumanReview;
  const mockStageStates: DemoStageState[] = progressSteps.map((_, index) => {
    if (completedScenario) {
      if (index === progressSteps.length - 1 && awaitingHumanReview) return 'PENDING';
      if (index === progressSteps.length - 1 && completedScenario.humanAction === 'None') return 'NOT_REQUIRED';
      return 'COMPLETED';
    }
    return index < mockProgress ? 'COMPLETED' : 'PENDING';
  });
  const stageStates = dataSourceMode === 'api' && runStatus
    ? stageKeys.map((key) => runStatus.steps[key])
    : mockStageStates;
  const completedStepCount = stageStates.filter((state) => state === 'COMPLETED' || state === 'NOT_REQUIRED').length;
  const resultLabel = !completedScenario
    ? `Step ${Math.min(completedStepCount + 1, progressSteps.length)} of ${progressSteps.length}`
    : runStatus?.resultState === 'BLOCKED'
      ? 'Blocked'
      : runStatus?.resultState === 'FAILED'
        ? 'Failed'
        : awaitingHumanReview
          ? 'Awaiting human review'
          : 'Complete';

  const run = async (scenario: Scenario) => {
    setRunning(scenario); setCompleted(null); setMockProgress(0); setRunId(null);
    if (dataSourceMode === 'api') {
      try {
        const startedRunId = (await starter.mutateAsync({ id: scenario.id, identity })).runId;
        setRunId(startedRunId);
        setSearchParams({ run: startedRunId }, { replace: true });
      }
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
  const restoreAll = () => { restore(); setRunning(null); setCompleted(null); setMockProgress(0); setRunId(null); setSearchParams({}, { replace: true }); };
  const openIncident = () => {
    if (!completedScenario) return;
    if (runStatus?.incidentId) void navigate(`/investigation/${runStatus.incidentId}`);
    else void navigate(completedScenario.variant === 'healthy' ? '/incidents' : `/investigation/SIM-${completedScenario.id.toUpperCase()}`);
  };

  return <div className="page demo-page demo-polished">
    <div className="page-intro compact"><div><p>Guided product demonstration</p><h1>Demo Lab</h1><span>{dataSourceMode === 'api' ? 'Synthetic telemetry flows through Kafka and the authoritative local workflow' : 'Deterministic browser-local fixture data'}</span></div>{dataSourceMode === 'mock' && <Button variant="ghost" onClick={restoreAll}><RotateCcw size={15} />Restore demo fixtures</Button>}</div>
    {isError && <section className="run-progress polished"><strong>Demo API unavailable</strong><p>{error instanceof Error ? error.message : 'The backend could not be reached.'}</p></section>}
    {recommended && <section className="recommended-demo polished"><div className="recommended-copy"><span className="recommended-label">Recommended demo</span><h2>{recommended.title}</h2><h3>The best end-to-end demonstration of ColdChain Sentinel</h3><p className="recommended-explanation">This demo sends synthetic sensor readings through the real local workflow. It creates no real shipment action and makes no external AI call.</p><div className="demo-meta"><span><strong>Kafka</strong><small>Carries synthetic sensor events</small></span><span><strong>PostgreSQL</strong><small>Stores the authoritative workflow record</small></span><span><strong>Human review</strong><small>Required before a shipment hold</small></span><span><strong>External AI</strong><small>Disabled for this deterministic demo</small></span></div><Button variant="primary" onClick={() => void run(recommended)} disabled={starter.isPending || Boolean(running && !completedScenario)}><Play size={16} />Start guided demo</Button></div><ol className="guided-sequence" aria-label="Recommended demo workflow">{progressSteps.map(([title, detail], index) => <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><small>{detail}</small></div></li>)}</ol></section>}
    {activeScenario && <section className="run-progress polished" aria-live="polite"><div className="run-title"><div><span>{dataSourceMode === 'api' ? 'Authoritative local run' : 'Guided simulation'}</span><strong>{activeScenario.title}</strong></div><strong className={awaitingHumanReview ? 'pending-result' : ''}>{resultLabel}</strong></div><div className="guided-progress">{progressSteps.map(([title, detail], index) => {
      const state = stageStates[index] ?? 'PENDING';
      const className = state === 'COMPLETED' ? 'complete' : state.toLowerCase().replace('_', '-');
      const description = state === 'COMPLETED'
        ? detail
        : state === 'NOT_REQUIRED'
          ? 'Not required for this workflow result'
          : title === 'Human review' && awaitingHumanReview
            ? humanReviewPendingText
            : state === 'BLOCKED'
              ? 'Stopped by authoritative controls'
              : state === 'FAILED'
                ? 'The workflow stage failed'
                : 'Waiting for authoritative state';
      return <div className={className} aria-label={`${title}: ${formatStageState(state)}`} key={title}><span>{state === 'COMPLETED' ? <CheckCircle2 size={16} /> : index + 1}</span><div><strong>{title}</strong><small>{description}</small></div></div>;
    })}</div>{completedScenario && <div className="scenario-result polished"><div><small>{runStatus?.incidentReference || dataSourceMode === 'mock' ? 'Incident created' : 'Workflow result'}</small><strong className="mono">{runStatus?.incidentReference ?? (dataSourceMode === 'api' ? 'No unsafe incident' : `SIM-${completedScenario.id.toUpperCase()}`)}</strong>{runStatus?.shipmentReference && <span className="scenario-shipment-reference">{runStatus.shipmentReference}</span>}</div><div><small>Severity</small><SeverityIndicator severity={runStatus?.incidentSeverity === 'CRITICAL' ? 'critical' : runStatus?.incidentSeverity === 'HIGH' || runStatus?.incidentSeverity === 'MEDIUM' ? 'warning' : completedScenario.variant === 'critical' ? 'critical' : 'normal'} /></div><div><small>Expected outcome</small><strong>{completedScenario.policyOutcome}</strong></div><div><small>Governance</small><GovernanceIndicator decision={(runStatus?.governanceDecision ?? completedScenario.governanceOutcome).toLowerCase().includes('approval') ? 'approval-required' : 'allowed'} /></div><div className="workflow-result"><small>Workflow status</small><strong className={awaitingHumanReview ? 'pending-result' : ''}>{resultLabel}</strong>{awaitingHumanReview && <span>{humanReviewPendingText}</span>}</div><div className="result-actions"><Button variant="primary" onClick={openIncident}>{runStatus?.incidentId || dataSourceMode === 'mock' ? 'Open incident investigation' : 'View incident queue'} <ArrowRight size={15} /></Button><Button variant="secondary" onClick={() => void run(completedScenario)}>Run again</Button>{dataSourceMode === 'mock' && <Button variant="ghost" onClick={restoreAll}>Restore demo fixtures</Button>}</div></div>}</section>}
    <section className="scenario-library"><header><div><span>Scenario library</span><h2>Test operational and AI safety scenarios</h2></div><div className="internal-tabs" role="tablist" aria-label="Scenario categories">{groups.map((group) => <button role="tab" aria-selected={category === group.name} key={group.name} onClick={() => setCategory(group.name)}>{group.name}</button>)}</div></header><div className="scenario-rows">{data.filter((scenario) => (activeGroup.ids as readonly string[]).includes(scenario.id)).map((scenario) => <ScenarioRow key={scenario.id} scenario={scenario} run={(selected) => void run(selected)} running={activeScenario?.id === scenario.id && !completedScenario} />)}</div></section>
    {dataSourceMode === 'mock' && <section className="fixture-controls" aria-label="Fixture state controls"><div><span>Design-review states</span><strong>Preview exceptional interface states</strong></div><Button variant="ghost" onClick={() => setDisplayMode('empty')}>Empty queue</Button><Button variant="ghost" onClick={() => setDisplayMode('disconnected')}>Disconnected</Button><Button variant="ghost" onClick={() => setDisplayMode('permission-denied')}>Permission denied</Button><label>Decision response<select aria-label="Decision response variant" value={decisionVariant} onChange={(event) => setDecisionVariant(event.target.value as typeof decisionVariant)}><option value="success">Success</option><option value="conflict">Idempotency conflict</option><option value="expiry">Expired recommendation</option><option value="authorization-failure">Authorization failure</option><option value="uncertain-timeout">Uncertain timeout</option></select></label></section>}
    {dataSourceMode === 'mock' && <p className="fixture-reset-note"><strong>Restore demo fixtures</strong> affects only this browser’s in-memory fixture state. It never modifies databases, containers, or Docker volumes.</p>}
  </div>;
}

function ScenarioRow({ scenario, run, running }: { scenario: Scenario; run: (scenario: Scenario) => void; running: boolean }) { return <article className="scenario-row"><div><h3>{scenario.title}</h3><p>{scenario.demonstrates}.</p></div><div><span>Expected outcome</span><strong>{scenario.policyOutcome}</strong></div><div><span>Human action</span><strong>{scenario.humanAction}</strong></div><Button variant="secondary" onClick={() => run(scenario)} disabled={running}><Play size={14} />Run</Button></article>; }

function formatStageState(state: DemoStageState): string {
  return state.toLowerCase().replace('_', ' ');
}

function scenarioIncident(scenario: Scenario): Incident {
  return { id: `SIM-${scenario.id.toUpperCase()}`, severity: scenario.variant === 'critical' ? 'critical' : 'warning', title: scenario.title, shipment: 'CCS-DEMO-2048', product: 'Synthetic demo cargo', sensor: 'SEN-DEMO-01', temperature: scenario.variant === 'critical' ? 12.4 : 8.7, allowedMin: 2, allowedMax: 8, breachMinutes: 22, state: 'awaiting-review', governance: scenario.variant === 'fallback' ? 'fallback' : 'approval-required', createdMinutesAgo: 0, reviewer: null, route: { from: 'Chicago', via: 'In transit', to: 'Denver', progress: 50 }, productSensitivity: 'Synthetic fixture', sensorHealth: 'Nominal · simulated', breachKind: scenario.variant === 'critical' ? 'immediate' : 'sustained' };
}
