"""Offline OpenAI selection and boundary tests; every HTTP exchange is mocked."""

import json
from dataclasses import replace
from typing import Any

import httpx
import pytest

from coldchain.ai.models import RecommendationOutput, RecommendationProvenance
from coldchain.ai.provider import (
    MAX_PROVIDER_REQUEST_BYTES,
    OpenAICompatibleRecommendationProvider,
    ProviderConfig,
    ProviderFailure,
)
from coldchain.application.recommendations import (
    DeterministicLocalRecommendationProvider,
    RetrievalGroundedRecommendationProvider,
    build_recommendation_provider,
)
from coldchain.config import Settings


def openai_config(*, enabled: bool = True, max_retries: int = 1) -> ProviderConfig:
    return ProviderConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="test-structured-output-model",
        timeout_seconds=2,
        max_output_tokens=1200,
        temperature=0,
        reasoning_effort=None,
        live_calls_enabled=enabled,
        billing_mode="provider_billed",
        max_retries=max_retries,
    )


def decision(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "recommended_action": "HOLD_SHIPMENT",
        "concise_rationale": "Synthetic evidence supports a dispatcher-reviewed hold.",
        "cited_evidence_chunk_ids": ["chunk-1"],
        "cited_incident_evidence_ids": ["evidence-1"],
        "contraindications": [],
        "missing_information": [],
        "evidence_sufficient": True,
        "uncertainty_level": "LOW",
    }
    value.update(overrides)
    return value


def response(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 17, "completion_tokens": 9, "total_tokens": 26},
        },
        headers={"x-request-id": "req-offline-safe"},
    )


def request(
    provider: OpenAICompatibleRecommendationProvider,
) -> tuple[RecommendationOutput, RecommendationProvenance]:
    return provider.request(
        incident_facts="synthetic incident",
        deterministic_result="HOLD_SHIPMENT requires dispatcher approval",
        retrieved_context="[chunk=chunk-1] synthetic SOP",
        allowed_chunk_ids={"chunk-1"},
        allowed_incident_evidence_ids={"evidence-1"},
        correlation_id="offline-correlation",
        sop_corpus_version="1.0.0",
    )


def test_openai_reuses_strict_chat_completions_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    captured: list[httpx.Request] = []

    def handler(value: httpx.Request) -> httpx.Response:
        captured.append(value)
        return response(decision())

    provider = OpenAICompatibleRecommendationProvider(
        openai_config(), httpx.Client(transport=httpx.MockTransport(handler))
    )
    output, provenance = request(provider)
    payload = json.loads(captured[0].content)
    assert captured[0].url == "https://api.openai.com/v1/chat/completions"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert set(payload["response_format"]["json_schema"]["schema"]["required"]) == set(
        payload["response_format"]["json_schema"]["schema"]["properties"]
    )
    assert payload["max_completion_tokens"] == 1200
    assert "reasoning_effort" not in payload
    assert output.recommended_action == "HOLD_SHIPMENT"
    assert provenance.provider == "openai"
    assert provenance.model == "test-structured-output-model"
    assert provenance.total_tokens == 26
    assert provenance.estimated_cost is None
    assert provenance.cost_estimation_basis == "not_estimated"


@pytest.mark.parametrize(
    ("enabled", "key", "model", "reason"),
    [
        (False, "unit-test-secret-placeholder", "test-model", "live_calls_disabled"),
        (True, "", "test-model", "api_key_not_configured"),
        (True, "unit-test-secret-placeholder", "", "provider_model_not_configured"),
    ],
)
def test_openai_incomplete_or_disabled_configuration_never_calls_network(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    key: str,
    model: str,
    reason: str,
) -> None:
    if key:
        monkeypatch.setenv("OPENAI_API_KEY", key)
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(decision())

    provider_config = replace(openai_config(enabled=enabled), model=model)
    provider = OpenAICompatibleRecommendationProvider(
        provider_config, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderFailure, match=reason):
        request(provider)
    assert calls == 0


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"not": "the schema"}, "invalid_provider_response"),
        (decision(recommended_action="RELEASE_SHIPMENT"), "invalid_provider_response"),
        (decision(cited_evidence_chunk_ids=["invented"]), "unknown_sop_citation"),
        (decision(cited_incident_evidence_ids=["invented"]), "unknown_incident_evidence_citation"),
        (
            decision(evidence_sufficient=True, cited_evidence_chunk_ids=[]),
            "invalid_provider_response",
        ),
    ],
)
def test_openai_rejects_invalid_output_offline(
    monkeypatch: pytest.MonkeyPatch, payload: object, reason: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    provider = OpenAICompatibleRecommendationProvider(
        openai_config(),
        httpx.Client(transport=httpx.MockTransport(lambda _: response(payload))),
    )
    with pytest.raises(ProviderFailure, match=reason):
        request(provider)


@pytest.mark.parametrize(
    ("status", "reason"),
    [(400, "bad_request"), (401, "authentication"), (403, "permission")],
)
def test_openai_nonretryable_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, status: int, reason: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    sensitive = "never retain unrestricted provider response content"
    provider = OpenAICompatibleRecommendationProvider(
        openai_config(),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    status,
                    json={
                        "error": {
                            "message": sensitive,
                            "type": "invalid_request_error",
                            "code": "safe_code",
                            "param": "response_format",
                        }
                    },
                )
            )
        ),
    )
    with pytest.raises(ProviderFailure, match=reason) as caught:
        request(provider)
    assert caught.value.status_code == status
    assert caught.value.error_type == "invalid_request_error"
    assert sensitive not in repr(caught.value.__dict__)
    assert "unit-test-secret-placeholder" not in repr(caught.value.__dict__)


@pytest.mark.parametrize("status", [429, 500])
def test_openai_retry_is_bounded(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    monkeypatch.setattr("coldchain.ai.provider.time.sleep", lambda _: None)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, headers={"Retry-After": "0.25"})
        return response(decision())

    provider = OpenAICompatibleRecommendationProvider(
        openai_config(), httpx.Client(transport=httpx.MockTransport(handler))
    )
    _, provenance = request(provider)
    assert calls == 2
    assert provenance.retry_count == 1


def test_openai_timeout_circuit_size_limit_and_factory_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret-placeholder")
    calls = 0

    def timeout(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic timeout")

    provider = OpenAICompatibleRecommendationProvider(
        openai_config(max_retries=0),
        httpx.Client(transport=httpx.MockTransport(timeout)),
        circuit_failure_threshold=1,
    )
    with pytest.raises(ProviderFailure, match="provider_network_failure"):
        request(provider)
    with pytest.raises(ProviderFailure, match="provider_circuit_open"):
        request(provider)
    assert calls == 1

    size_calls = 0

    def should_not_run(_: httpx.Request) -> httpx.Response:
        nonlocal size_calls
        size_calls += 1
        return response(decision())

    bounded = OpenAICompatibleRecommendationProvider(
        openai_config(), httpx.Client(transport=httpx.MockTransport(should_not_run))
    )
    with pytest.raises(ProviderFailure, match="provider_request_too_large"):
        bounded.request(
            incident_facts="x" * MAX_PROVIDER_REQUEST_BYTES,
            deterministic_result="x",
            retrieved_context="x",
            allowed_chunk_ids=set(),
            allowed_incident_evidence_ids=set(),
            correlation_id="x",
            sop_corpus_version="1",
        )
    assert size_calls == 0

    deterministic = build_recommendation_provider(
        Settings(_env_file=None, llm_provider="deterministic")
    )
    assert isinstance(deterministic, DeterministicLocalRecommendationProvider)
    selected = build_recommendation_provider(
        Settings(
            _env_file=None,
            llm_provider="openai",
            openai_model="test-structured-output-model",
            llm_live_calls_enabled=False,
        )
    )
    assert isinstance(selected, RetrievalGroundedRecommendationProvider)
