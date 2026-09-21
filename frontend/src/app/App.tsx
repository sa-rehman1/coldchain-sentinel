import * as Tooltip from '@radix-ui/react-tooltip';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { CommandCenter } from '../features/command-center/CommandCenter';
import { DemoLab } from '../features/demo-lab/DemoLab';
import { GovernedAI } from '../features/governance/GovernedAI';
import { IncidentQueue } from '../features/incidents/IncidentQueue';
import { Investigation } from '../features/investigation/Investigation';
import { Observability } from '../features/observability/Observability';

export function App() {
  return <Tooltip.Provider delayDuration={250}><AppShell><Routes>
    <Route path="/" element={<CommandCenter />} />
    <Route path="/incidents" element={<IncidentQueue />} />
    <Route path="/investigation/:incidentId" element={<Investigation />} />
    <Route path="/governed-ai" element={<GovernedAI />} />
    <Route path="/observability" element={<Observability />} />
    <Route path="/demo-lab" element={<DemoLab />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></AppShell></Tooltip.Provider>;
}
