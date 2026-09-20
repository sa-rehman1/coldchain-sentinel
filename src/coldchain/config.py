"""Typed application configuration loaded exclusively from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with production safety validation."""

    model_config = SettingsConfigDict(
        env_prefix="COLDCHAIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "coldchain-control-plane"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr | None = None
    database_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_telemetry_topic: str = "coldchain.telemetry.v1"
    kafka_dead_letter_topic: str = "coldchain.telemetry.dlq.v1"
    kafka_consumer_group: str = "coldchain-telemetry-worker-v1"
    kafka_security_protocol: Literal["PLAINTEXT", "SSL", "SASL_SSL"] = "PLAINTEXT"
    governance_kill_switch_active: bool = False

    @field_validator(
        "service_name",
        "kafka_telemetry_topic",
        "kafka_dead_letter_topic",
        "kafka_consumer_group",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_non_local_security(self) -> "Settings":
        if self.environment in {"staging", "production"}:
            if self.database_url is None:
                raise ValueError("database URL is required outside local/test environments")
            url = self.database_url.get_secret_value().lower()
            if "sslmode=verify-full" not in url:
                raise ValueError("database URL must use sslmode=verify-full outside local/test")
            if self.kafka_security_protocol == "PLAINTEXT":
                raise ValueError("Kafka encryption is required outside local/test")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings snapshot per process."""

    return Settings()
