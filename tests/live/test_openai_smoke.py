"""Explicit opt-in OpenAI smoke test with exactly one HTTP attempt."""

import os
from datetime import UTC, datetime

import pytest

from coldchain.ai.provider import OpenAICompatibleRecommendationProvider, ProviderConfig


@pytest.mark.live_openai
def test_one_bounded_live_openai_recommendation() -> None:
    model = os.getenv("OPENAI_MODEL", "").strip()
    if os.getenv("RUN_LIVE_OPENAI_SMOKE") != "true" or not os.getenv("OPENAI_API_KEY") or not model:
        pytest.skip("requires explicit smoke flag, OPENAI_API_KEY, and OPENAI_MODEL")
    provider = OpenAICompatibleRecommendationProvider(
        ProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            model=model,
            timeout_seconds=15,
            max_output_tokens=1200,
            temperature=0,
            reasoning_effort=None,
            live_calls_enabled=True,
            billing_mode="provider_billed",
            max_retries=0,
        )
    )
    output, provenance = provider.request(
        incident_facts="incident_id=synthetic evidence_id=evidence-1 temperature excursion",
        deterministic_result="HOLD_SHIPMENT requires dispatcher approval",
        retrieved_context="[chunk=chunk-1] A synthetic hold requires dispatcher approval.",
        allowed_chunk_ids={"chunk-1"},
        allowed_incident_evidence_ids={"evidence-1"},
        correlation_id="openai-live-smoke",
        sop_corpus_version="1.0.0",
    )
    assert output.recommended_action.value in {
        "HOLD_SHIPMENT",
        "REQUEST_INSPECTION",
        "ESCALATE_DISPATCHER",
        "ADD_NOTE",
    }
    assert output.recommendation_expiry > datetime.now(UTC)
    assert provenance.provider == "openai"
    assert provenance.model == model
    assert provenance.retry_count == 0
