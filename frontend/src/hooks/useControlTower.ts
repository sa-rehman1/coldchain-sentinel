import { useQuery } from '@tanstack/react-query';
import { controlTowerDataSource } from '../data/adapters/MockControlTowerDataSource';

export const useDashboard = () => useQuery({ queryKey: ['dashboard'], queryFn: () => controlTowerDataSource.getDashboard() });
export const useIncidents = () => useQuery({ queryKey: ['incidents'], queryFn: () => controlTowerDataSource.getIncidents() });
export const useInvestigation = (id: string) => useQuery({ queryKey: ['investigation', id], queryFn: () => controlTowerDataSource.getInvestigation(id) });
export const useScenarios = () => useQuery({ queryKey: ['scenarios'], queryFn: () => controlTowerDataSource.getScenarios() });
