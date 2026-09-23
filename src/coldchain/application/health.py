"""Readiness use case independent of the web framework."""

from dataclasses import dataclass
from typing import Protocol

from coldchain.config import Settings


class DatabaseProbe(Protocol):
    async def ping(self) -> None: ...


class ReadyProbe(Protocol):
    def ready(self) -> bool: ...


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


@dataclass(frozen=True, slots=True)
class AiHealthResult:
    selected_provider: str
    selected_model: str
    provider_configured: bool
    live_calls_enabled: bool
    qdrant_readiness: str
    embedding_provider_readiness: str
    fallback_available: bool


class AiHealthService:
    """Safe configuration status; never invokes a model or returns a secret."""

    def __init__(self, settings: Settings, qdrant_probe: ReadyProbe | None = None) -> None:
        self._settings = settings
        self._qdrant_probe = qdrant_probe

    def check(self) -> AiHealthResult:
        import os

        qdrant = "not_checked"
        if self._qdrant_probe is not None:
            try:
                qdrant = "ready" if self._qdrant_probe.ready() else "unavailable"
            except Exception:
                qdrant = "unavailable"
        return AiHealthResult(
            selected_provider=self._settings.llm_provider,
            selected_model=self._settings.selected_llm_model,
            provider_configured=(
                True
                if self._settings.llm_provider == "deterministic"
                else bool(
                    os.getenv(self._settings.selected_llm_api_key_env, "")
                    and self._settings.selected_llm_model
                )
            ),
            live_calls_enabled=self._settings.llm_live_calls_enabled,
            qdrant_readiness=qdrant,
            embedding_provider_readiness=(
                "ready"
                if self._settings.embedding_provider == "deterministic"
                else "optional_not_loaded"
            ),
            fallback_available=True,
        )
