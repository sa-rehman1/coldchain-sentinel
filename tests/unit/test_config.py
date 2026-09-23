import pytest
from pydantic import ValidationError

from coldchain.config import Settings


def test_local_environment_may_start_without_external_services() -> None:
    settings = Settings(environment="local", database_url=None)
    assert settings.database_url is None


def test_provider_selection_defaults_to_offline_and_resolves_openai_safely() -> None:
    offline = Settings(_env_file=None)
    assert offline.llm_provider == "deterministic"
    assert offline.selected_llm_model == "deterministic-local-1.0"
    assert offline.selected_llm_api_key_env == ""

    openai = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_model="test-structured-output-model",
    )
    assert openai.selected_llm_base_url == "https://api.openai.com/v1"
    assert openai.selected_llm_api_key_env == "OPENAI_API_KEY"
    assert openai.selected_llm_model == "test-structured-output-model"
    assert openai.selected_llm_reasoning_effort is None
    assert openai.selected_llm_billing_mode == "provider_billed"


def test_provider_selection_rejects_unknown_provider_and_openai_key_exfiltration() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="unknown")
    with pytest.raises(ValidationError, match="official API base URL"):
        Settings(
            _env_file=None,
            llm_provider="openai",
            openai_base_url="https://example.invalid/v1",
        )


def test_production_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="database URL is required"):
        Settings(
            environment="production",
            database_url=None,
            kafka_security_protocol="SSL",
        )


def test_demo_mode_fails_closed_outside_local_and_test() -> None:
    with pytest.raises(ValueError, match="demo mode"):
        Settings(environment="staging", demo_mode_enabled=True)


def test_production_requires_verified_database_tls() -> None:
    with pytest.raises(ValidationError, match="sslmode=verify-full"):
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://user:placeholder@db/coldchain",
            kafka_security_protocol="SSL",
        )


def test_production_requires_encrypted_kafka() -> None:
    with pytest.raises(ValidationError, match="Kafka encryption"):
        Settings(
            environment="production",
            database_url=("postgresql+asyncpg://user:placeholder@db/coldchain?sslmode=verify-full"),
            kafka_security_protocol="PLAINTEXT",
        )
