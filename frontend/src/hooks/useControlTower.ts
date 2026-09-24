import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LocalIdentity } from '../data/contracts';
import { controlTowerDataSource } from '../data/source';

export const useDashboard = () => useQuery({ queryKey: ['dashboard'], queryFn: ({ signal }) => controlTowerDataSource.getDashboard(signal), refetchInterval: controlTowerDataSource.mode === 'api' ? 5_000 : false });
export const useIncidents = () => useQuery({ queryKey: ['incidents'], queryFn: ({ signal }) => controlTowerDataSource.getIncidents(signal), refetchInterval: controlTowerDataSource.mode === 'api' ? 5_000 : false });
export const useInvestigation = (id: string) => useQuery({ queryKey: ['investigation', id], queryFn: ({ signal }) => controlTowerDataSource.getInvestigation(id, signal), refetchInterval: controlTowerDataSource.mode === 'api' ? 3_000 : false });
export const useScenarios = (identity?: LocalIdentity) => useQuery({ queryKey: ['scenarios', identity?.actorId], queryFn: ({ signal }) => controlTowerDataSource.getScenarios(identity, signal) });
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: ({ signal }) => controlTowerDataSource.getHealth(signal), refetchInterval: controlTowerDataSource.mode === 'api' ? 10_000 : false });
export const useDemoRun = (runId: string | null, identity: LocalIdentity) => useQuery({
  queryKey: ['demo-run', runId],
  queryFn: ({ signal }) => {
    if (runId === null) throw new Error('A demo run identifier is required.');
    return controlTowerDataSource.getDemoRun(runId, identity, signal);
  },
  enabled: runId !== null,
  refetchInterval: (query) => query.state.data?.status === 'ACCEPTED' || query.state.data?.status === 'PROCESSING' ? 750 : false,
});
export const useStartScenario = () => useMutation({ mutationFn: ({ id, identity }: { id: string; identity: LocalIdentity }) => controlTowerDataSource.startScenario(id, identity) });
export const useDecision = (incidentId: string) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ recommendationId, decision, rationale, idempotencyKey, identity }: { recommendationId: string; decision: 'approve' | 'reject'; rationale: string; idempotencyKey: string; identity: LocalIdentity }) => controlTowerDataSource.decide(incidentId, recommendationId, decision, rationale, idempotencyKey, identity),
    onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: ['investigation', incidentId] }), client.invalidateQueries({ queryKey: ['incidents'] }), client.invalidateQueries({ queryKey: ['dashboard'] })]); },
  });
};
