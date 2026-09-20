"""Simulated, idempotent cold-chain action adapter."""

from uuid import uuid4

from coldchain.application.interfaces import ActionAdapter
from coldchain.domain import ActionResult, Command
from coldchain.domain.incidents import utc_now


class SimulatedColdChainActionAdapter(ActionAdapter):
    identity = "adapter:simulated-cold-chain-v1"

    def __init__(self) -> None:
        self._results: dict[str, ActionResult] = {}

    async def execute(self, command: Command) -> ActionResult:
        existing = self._results.get(command.idempotency_key)
        if existing is not None:
            return existing
        result = ActionResult(
            result_id=uuid4(),
            command_id=command.command_id,
            status="SUCCEEDED",
            adapter=self.identity,
            detail="simulated shipment hold applied",
            completed_at=utc_now(),
        )
        self._results[command.idempotency_key] = result
        return result
