import type { ControlTowerDataSource, DashboardData, Incident, InvestigationData, Scenario } from '../contracts';
import { dashboard, incidents, investigationFor, scenarios } from '../fixtures';

const clone = <T,>(value: T): T => structuredClone(value);

export class MockControlTowerDataSource implements ControlTowerDataSource {
  async getDashboard(): Promise<DashboardData> { return Promise.resolve(clone(dashboard)); }
  async getIncidents(): Promise<Incident[]> { return Promise.resolve(clone(incidents)); }
  async getInvestigation(id: string): Promise<InvestigationData> { return Promise.resolve(clone(investigationFor(id))); }
  async getScenarios(): Promise<Scenario[]> { return Promise.resolve(clone(scenarios)); }
}

export const controlTowerDataSource: ControlTowerDataSource = new MockControlTowerDataSource();
