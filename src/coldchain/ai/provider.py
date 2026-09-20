"""OpenAI-compatible provider with strict validation and bounded failure behavior."""

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import SecretStr, ValidationError

from coldchain.ai.models import (
    ProviderRecommendationDecision,
    RecommendationOutput,
    RecommendationProvenance,
    RecommendedAction,
    UncertaintyLevel,
)
from coldchain.ai.prompting import build_messages, load_prompt


class ProviderFailure(RuntimeError):
    """Sanitized provider failure safe for persistence and logs."""

    def __init__(
        self,
        reason: str,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        parameter: str | None = None,
        safe_message: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code
        self.error_type = error_type
        self.error_code = error_code
        self.parameter = parameter
        self.safe_message = safe_message


MAX_PROVIDER_REQUEST_BYTES = 65_536
TRUSTED_RECOMMENDATION_TTL = timedelta(minutes=30)
TRUSTED_RESPONSE_SCHEMA_VERSION = "1.0"
_SAFE_METADATA = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")


def _provider_output_schema() -> dict[str, Any]:
    """Return only the documented Groq strict-JSON-schema subset.

    Full length, datetime, and policy validation remains authoritative in the
    Pydantic response model after the provider returns.
    """
    return {
        "type": "object",
        "properties": {
            "recommended_action": {
                "type": "string",
                "enum": [item.value for item in RecommendedAction],
            },
            "concise_rationale": {"type": "string"},
            "cited_evidence_chunk_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cited_incident_evidence_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
            "contraindications": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
            "evidence_sufficient": {"type": "boolean"},
            "uncertainty_level": {
                "type": "string",
                "enum": [item.value for item in UncertaintyLevel],
            },
        },
        "required": list(ProviderRecommendationDecision.model_fields),
        "additionalProperties": False,
    }


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider: str
    base_url: str
    api_key_env: str
    model: str
    timeout_seconds: float
    max_output_tokens: int
    temperature: float
    reasoning_effort: Literal["low", "medium", "high"] | None
    live_calls_enabled: bool
    billing_mode: str


class OpenAICompatibleRecommendationProvider:
    """Provider-neutral OpenAI chat-completions boundary."""

    api_family = "openai-compatible"

    def __init__(
        self,
        config: ProviderConfig,
        client: httpx.Client | None = None,
        circuit_failure_threshold: int = 2,
        circuit_cooldown_seconds: float = 60.0,
    ) -> None:
        self.config = config
        self._key = SecretStr(os.getenv(config.api_key_env, ""))
        timeout = httpx.Timeout(
            config.timeout_seconds,
            connect=min(5.0, config.timeout_seconds),
            read=config.timeout_seconds,
        )
        self._client = client or httpx.Client(timeout=timeout)
        self._failures = 0
        self._opened_at: float | None = None
        self._failure_threshold = circuit_failure_threshold
        self._cooldown = circuit_cooldown_seconds

    @property
    def configured(self) -> bool:
        return bool(self._key.get_secret_value())

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={self.config.provider!r}, "
            f"model={self.config.model!r}, api_key=**********)"
        )

    def request(
        self,
        *,
        incident_facts: str,
        deterministic_result: str,
        retrieved_context: str,
        allowed_chunk_ids: set[str],
        allowed_incident_evidence_ids: set[str],
        correlation_id: str,
        sop_corpus_version: str,
    ) -> tuple[RecommendationOutput, RecommendationProvenance]:
        if not self.config.live_calls_enabled:
            raise ProviderFailure("live_calls_disabled")
        if not self.configured:
            raise ProviderFailure("api_key_not_configured")
        if self._opened_at is not None and time.monotonic() - self._opened_at < self._cooldown:
            raise ProviderFailure("provider_circuit_open")

        schema = _provider_output_schema()
        messages = build_messages(
            incident_facts,
            deterministic_result,
            retrieved_context,
            json.dumps(schema, sort_keys=True),
        )
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_completion_tokens": self.config.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "recommendation", "strict": True, "schema": schema},
            },
        }
        if self.config.reasoning_effort is not None:
            payload["reasoning_effort"] = self.config.reasoning_effort
        request_bytes = len(json.dumps(payload, separators=(",", ":")).encode())
        if request_bytes > MAX_PROVIDER_REQUEST_BYTES:
            raise ProviderFailure(
                "provider_request_too_large",
                safe_message="provider request exceeded the local size limit",
            )
        started = datetime.now(UTC)
        begin = time.monotonic()
        response, retries = self._post_with_retry(payload, correlation_id)
        try:
            body = response.json()
            decision = ProviderRecommendationDecision.model_validate_json(
                body["choices"][0]["message"]["content"]
            )
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            self._record_failure()
            raise ProviderFailure("invalid_provider_response") from exc
        if not set(decision.cited_evidence_chunk_ids) <= allowed_chunk_ids:
            raise ProviderFailure("unknown_sop_citation")
        if not set(decision.cited_incident_evidence_ids) <= allowed_incident_evidence_ids:
            raise ProviderFailure("unknown_incident_evidence_citation")
        self._failures = 0
        self._opened_at = None
        completed = datetime.now(UTC)
        output = RecommendationOutput(
            **decision.model_dump(),
            recommendation_expiry=completed + TRUSTED_RECOMMENDATION_TTL,
            schema_version=TRUSTED_RESPONSE_SCHEMA_VERSION,
        )
        usage = body.get("usage", {})
        asset = load_prompt()
        provenance = RecommendationProvenance(
            provider=self.config.provider,
            base_url_identifier=self._safe_base_url(),
            model=self.config.model,
            prompt_id=asset.prompt_id,
            prompt_version=asset.version,
            prompt_hash=asset.sha256,
            sop_corpus_version=sop_corpus_version,
            cited_chunk_ids=output.cited_evidence_chunk_ids,
            retrieved_chunk_ids=tuple(sorted(allowed_chunk_ids)),
            cited_incident_evidence_ids=output.cited_incident_evidence_ids,
            correlation_id=correlation_id,
            provider_request_id=response.headers.get("x-request-id"),
            started_at=started,
            completed_at=completed,
            latency_ms=max(0, int((time.monotonic() - begin) * 1000)),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            billing_mode=self.config.billing_mode,
            cost_estimation_basis="configured_free_tier_mode"
            if self.config.billing_mode == "free_tier"
            else "configured_mode",
            estimated_cost=0.0,
            retry_count=retries,
            fallback_used=False,
            validation_result="valid",
            evidence_sufficient=output.evidence_sufficient,
            uncertainty_level=output.uncertainty_level.value,
            recommendation_expiry=output.recommendation_expiry,
        )
        return output, provenance

    def _post_with_retry(
        self, payload: dict[str, Any], correlation_id: str
    ) -> tuple[httpx.Response, int]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._key.get_secret_value()}",
            "X-Correlation-ID": correlation_id,
        }
        for attempt in range(2):
            try:
                response = self._client.post(url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 0:
                    continue
                self._record_failure()
                raise ProviderFailure("provider_network_failure") from exc
            if response.status_code == 401:
                raise self._response_failure(response, "provider_authentication_failure")
            if response.status_code == 403:
                raise self._response_failure(response, "provider_permission_failure")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            time.sleep(min(float(retry_after), 1.0))
                        except ValueError:
                            pass
                    continue
                self._record_failure()
                reason = (
                    "provider_rate_limit_failure"
                    if response.status_code == 429
                    else "provider_unavailable_failure"
                )
                raise self._response_failure(response, reason)
            if response.status_code >= 400:
                reasons = {
                    400: "provider_bad_request",
                    404: "provider_endpoint_or_model_not_found",
                    413: "provider_payload_too_large",
                    422: "provider_validation_failure",
                }
                raise self._response_failure(
                    response, reasons.get(response.status_code, "provider_request_rejected")
                )
            return response, attempt
        raise ProviderFailure("provider_failure")

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._opened_at = time.monotonic()

    @staticmethod
    def _response_failure(response: httpx.Response, reason: str) -> ProviderFailure:
        """Extract allowlisted metadata without retaining provider message content."""
        error: dict[str, Any] = {}
        try:
            body = response.json()
            candidate = body.get("error") if isinstance(body, dict) else None
            if isinstance(candidate, dict):
                error = candidate
        except (ValueError, TypeError):
            pass

        def safe_field(name: str) -> str | None:
            value = error.get(name)
            text = str(value) if isinstance(value, (str, int)) else ""
            return text if _SAFE_METADATA.fullmatch(text) else None

        safe_messages = {
            400: "provider rejected the request shape",
            401: "provider rejected the API credential",
            403: "provider denied account or model access",
            404: "provider endpoint or model was not found",
            413: "provider rejected the request size",
            422: "provider rejected request validation",
            429: "provider rate limit was reached",
        }
        return ProviderFailure(
            reason,
            status_code=response.status_code,
            error_type=safe_field("type"),
            error_code=safe_field("code"),
            parameter=safe_field("param"),
            safe_message=safe_messages.get(
                response.status_code, "provider request failed without retained response content"
            ),
        )

    def _safe_base_url(self) -> str:
        parsed = httpx.URL(self.config.base_url)
        return f"{parsed.scheme}://{parsed.host}{parsed.path}"
