"""Readiness use case independent of the web framework."""

from dataclasses import dataclass
from typing import Protocol


class DatabaseProbe(Protocol):
    async def ping(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, str]


class ReadinessService:
    def __init__(self, database_probe: DatabaseProbe | None) -> None:
        self._database_probe = database_probe

    async def check(self) -> ReadinessResult:
        if self._database_probe is None:
            return ReadinessResult(ready=False, checks={"database": "not_configured"})
        try:
            await self._database_probe.ping()
        except Exception:
            return ReadinessResult(ready=False, checks={"database": "unavailable"})
        return ReadinessResult(ready=True, checks={"database": "ready"})
