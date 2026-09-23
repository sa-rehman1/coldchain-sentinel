import { MockControlTowerDataSource } from './adapters/MockControlTowerDataSource';
import type { ControlTowerDataSource } from './contracts';
import { HttpControlTowerDataSource } from './api/HttpControlTowerDataSource';

const configuredMode = import.meta.env.VITE_CONTROL_TOWER_DATA_SOURCE;
export const dataSourceMode: 'mock' | 'api' = configuredMode === 'api' ? 'api' : 'mock';
export const controlTowerDataSource: ControlTowerDataSource = dataSourceMode === 'api'
  ? new HttpControlTowerDataSource()
  : new MockControlTowerDataSource();
