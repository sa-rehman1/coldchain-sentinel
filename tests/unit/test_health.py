import pytest

from coldchain.application.health import AiHealthService, ReadinessService
from coldchain.config import Settings


class FailingProbe:
    async def ping(self) -> None:
        raise ConnectionError("internal detail must not leave the service")


async def test_readiness_hides_probe_exception() -> None:
    result = await ReadinessService(FailingProbe()).check()
    assert result.ready is False
    assert result.checks == {"database": "unavailable"}


def test_openai_health_is_configuration_only_and_secret_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_model="test-structured-output-model",
        llm_live_calls_enabled=False,
    )
    result = AiHealthService(settings).check()
    assert result.selected_provider == "openai"
    assert result.selected_model == "test-structured-output-model"
    assert result.provider_configured is True
    assert result.live_calls_enabled is False
    assert "unit-test-secret-placeholder" not in repr(result)
