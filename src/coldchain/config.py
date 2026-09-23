"""Typed application configuration loaded exclusively from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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
    demo_mode_enabled: bool = False
    llm_provider: Literal["deterministic", "groq", "openai"] = Field(
        default="deterministic",
        validation_alias=AliasChoices("LLM_PROVIDER", "COLDCHAIN_LLM_PROVIDER"),
    )
    llm_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "COLDCHAIN_LLM_BASE_URL"),
    )
    llm_api_key_env: str = Field(
        default="GROQ_API_KEY",
        validation_alias=AliasChoices("LLM_API_KEY_ENV", "COLDCHAIN_LLM_API_KEY_ENV"),
    )
    llm_model: str = Field(
        default="openai/gpt-oss-20b",
        validation_alias=AliasChoices("LLM_MODEL", "COLDCHAIN_LLM_MODEL"),
    )
    llm_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        le=60,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "COLDCHAIN_LLM_TIMEOUT_SECONDS"),
    )
    llm_max_output_tokens: int = Field(
        default=1200,
        ge=64,
        le=2000,
        validation_alias=AliasChoices("LLM_MAX_OUTPUT_TOKENS", "COLDCHAIN_LLM_MAX_OUTPUT_TOKENS"),
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0,
        le=1,
        validation_alias=AliasChoices("LLM_TEMPERATURE", "COLDCHAIN_LLM_TEMPERATURE"),
    )
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = Field(
        default="low",
        validation_alias=AliasChoices("LLM_REASONING_EFFORT", "COLDCHAIN_LLM_REASONING_EFFORT"),
    )
    llm_live_calls_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LLM_LIVE_CALLS_ENABLED", "COLDCHAIN_LLM_LIVE_CALLS_ENABLED"),
    )
    llm_billing_mode: str = Field(
        default="free_tier",
        validation_alias=AliasChoices("LLM_BILLING_MODE", "COLDCHAIN_LLM_BILLING_MODE"),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "COLDCHAIN_OPENAI_BASE_URL"),
    )
    openai_model: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_MODEL", "COLDCHAIN_OPENAI_MODEL"),
    )
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "coldchain_sop_v1"
    embedding_provider: str = "deterministic"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    metrics_enabled: bool = True
    worker_metrics_host: str = "127.0.0.1"
    worker_metrics_port: int = Field(default=9100, ge=1024, le=65535)
    otel_tracing_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318/v1/traces"
    otel_export_timeout_seconds: float = Field(default=2.0, gt=0, le=10)

    @field_validator(
        "service_name",
        "kafka_telemetry_topic",
        "kafka_dead_letter_topic",
        "kafka_consumer_group",
        "worker_metrics_host",
        "otel_exporter_otlp_endpoint",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_non_local_security(self) -> "Settings":
        if (
            self.llm_provider == "openai"
            and self.openai_base_url.rstrip("/") != "https://api.openai.com/v1"
        ):
            raise ValueError("OpenAI credentials may be sent only to the official API base URL")
        if self.demo_mode_enabled and self.environment not in {"local", "test"}:
            raise ValueError("demo mode is available only in local/test environments")
        if self.environment in {"staging", "production"}:
            if self.database_url is None:
                raise ValueError("database URL is required outside local/test environments")
            url = self.database_url.get_secret_value().lower()
            if "sslmode=verify-full" not in url:
                raise ValueError("database URL must use sslmode=verify-full outside local/test")
            if self.kafka_security_protocol == "PLAINTEXT":
                raise ValueError("Kafka encryption is required outside local/test")
        return self

    @property
    def selected_llm_base_url(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_base_url
        return self.llm_base_url

    @property
    def selected_llm_api_key_env(self) -> str:
        if self.llm_provider == "openai":
            return "OPENAI_API_KEY"
        if self.llm_provider == "groq":
            return self.llm_api_key_env
        return ""

    @property
    def selected_llm_model(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_model.strip()
        if self.llm_provider == "groq":
            return self.llm_model
        return "deterministic-local-1.0"

    @property
    def selected_llm_reasoning_effort(self) -> Literal["low", "medium", "high"] | None:
        # Model support varies. The OpenAI request omits this optional field unless a
        # later, model-specific adapter verifies support.
        if self.llm_provider == "openai":
            return None
        return self.llm_reasoning_effort

    @property
    def selected_llm_billing_mode(self) -> str:
        if self.llm_provider == "openai":
            return "provider_billed"
        return self.llm_billing_mode


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings snapshot per process."""

    return Settings()
