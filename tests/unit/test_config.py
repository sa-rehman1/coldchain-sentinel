import pytest
from pydantic import ValidationError

from coldchain.config import Settings


def test_local_environment_may_start_without_external_services() -> None:
    settings = Settings(environment="local", database_url=None)
    assert settings.database_url is None


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
