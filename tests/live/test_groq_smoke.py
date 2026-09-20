"""Explicit opt-in, one-call Groq smoke test."""

import os
from datetime import UTC, datetime, timedelta

import pytest

from coldchain.ai.provider import OpenAICompatibleRecommendationProvider, ProviderConfig


@pytest.mark.live_groq
def test_one_bounded_live_groq_recommendation() -> None:
    if os.getenv("RUN_LIVE_GROQ_SMOKE") != "true" or not os.getenv("GROQ_API_KEY"):
        pytest.skip("requires RUN_LIVE_GROQ_SMOKE=true and GROQ_API_KEY")
    provider = OpenAICompatibleRecommendationProvider(
        ProviderConfig(
            "groq",
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            "openai/gpt-oss-20b",
            15,
            1200,
            0,
            "low",
            True,
            "free_tier",
        )
    )
    output, provenance = provider.request(
        incident_facts="incident_id=demo evidence_id=evidence-1 temperature excursion",
        deterministic_result="HOLD_SHIPMENT requires dispatcher approval",
        retrieved_context="[chunk=chunk-1] A hold requires dispatcher approval.",
        allowed_chunk_ids={"chunk-1"},
        allowed_incident_evidence_ids={"evidence-1"},
        correlation_id="live-smoke",
        sop_corpus_version="1.0.0",
    )
    assert output.recommendation_expiry > datetime.now(UTC) - timedelta(seconds=1)
    assert provenance.model == "openai/gpt-oss-20b"
