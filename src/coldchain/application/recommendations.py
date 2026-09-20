"""Provider-neutral recommendation orchestration and offline fallback."""

import os
from datetime import timedelta
from typing import Any
from uuid import uuid4

from coldchain.ai.provider import (
    OpenAICompatibleRecommendationProvider,
    ProviderConfig,
    ProviderFailure,
)
from coldchain.config import Settings
from coldchain.domain import EvidenceSnapshot, Incident, Recommendation
from coldchain.domain.incidents import utc_now
from coldchain.retrieval.core import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    QdrantVectorStore,
    SopChunk,
    VectorStore,
)


class DeterministicLocalRecommendationProvider:
    """Generate a typed recommendation without network access or model inference."""

    identity = "provider:deterministic-local-v1"
    version = "deterministic-local-1.0"

    def recommend(self, incident: Incident, evidence: EvidenceSnapshot) -> Recommendation:
        now = utc_now()
        return Recommendation(
            recommendation_id=uuid4(),
            incident_id=incident.incident_id,
            evidence_ids=(evidence.evidence_id,),
            action_type="HOLD_SHIPMENT",
            parameters={"shipmentId": str(incident.shipment_id), "reason": "temperature_breach"},
            provider=self.version,
            author_identity=self.identity,
            rationale=(
                "Place the shipment on simulated hold pending dispatcher review because the "
                "versioned temperature policy detected a breach. This is not authorization."
            ),
            expires_at=now + timedelta(minutes=30),
            non_authoritative=True,
            provenance={
                "provider": "deterministic",
                "apiFamily": "local",
                "model": self.version,
                "fallbackUsed": False,
                "validationResult": "deterministic",
                "recommendationExpiry": (now + timedelta(minutes=30)).isoformat(),
            },
        )


class RetrievalGroundedRecommendationProvider:
    """Retrieve evidence, call an untrusted model once, and fail to deterministic output."""

    identity = "provider:retrieval-grounded-v1"

    def __init__(
        self,
        provider: OpenAICompatibleRecommendationProvider,
        vector_store: VectorStore,
        embeddings: EmbeddingProvider,
        fallback: DeterministicLocalRecommendationProvider | None = None,
        sop_corpus_version: str = "1.0.0",
    ) -> None:
        self._provider = provider
        self._store = vector_store
        self._embeddings = embeddings
        self._fallback = fallback or DeterministicLocalRecommendationProvider()
        self._corpus_version = sop_corpus_version
        self._attempted_incidents: set[str] = set()

    def recommend(self, incident: Incident, evidence: EvidenceSnapshot) -> Recommendation:
        incident_key = str(incident.incident_id)
        if incident_key in self._attempted_incidents:
            return self._fallback_result(incident, evidence, "live_call_limit_reached")
        self._attempted_incidents.add(incident_key)
        try:
            query = f"{incident.severity} temperature excursion {evidence.summary}"
            vector = self._embeddings.embed([query])[0]
            matches = self._store.search(
                vector, as_of=incident.created_at.date(), top_k=5, threshold=0.05
            )
            if not matches:
                raise ProviderFailure("insufficient_retrieval_evidence")
            chunks = [item[0] for item in matches]
            context = self._context(chunks)
            output, provenance = self._provider.request(
                incident_facts=self._incident_facts(incident, evidence),
                deterministic_result="HOLD_SHIPMENT requires dispatcher approval",
                retrieved_context=context,
                allowed_chunk_ids={chunk.chunk_id for chunk in chunks},
                allowed_incident_evidence_ids={str(evidence.evidence_id)},
                correlation_id=str(incident.correlation_id),
                sop_corpus_version=self._corpus_version,
            )
            cited = [chunk for chunk in chunks if chunk.chunk_id in output.cited_evidence_chunk_ids]
            provenance_data = provenance.model_dump(mode="json")
            provenance_data["cited_document_ids"] = sorted({item.document_id for item in cited})
            provenance_data["cited_section_ids"] = sorted({item.section_id for item in cited})
            return Recommendation(
                recommendation_id=uuid4(),
                incident_id=incident.incident_id,
                evidence_ids=(evidence.evidence_id,),
                action_type=output.recommended_action.value,
                parameters={"shipmentId": str(incident.shipment_id)},
                provider=f"{self._provider.config.provider}:{self._provider.config.model}",
                author_identity=self.identity,
                rationale=output.concise_rationale,
                expires_at=output.recommendation_expiry,
                non_authoritative=True,
                provenance=provenance_data,
            )
        except (ProviderFailure, ValueError, RuntimeError) as exc:
            reason = (
                str(exc) if isinstance(exc, ProviderFailure) else "retrieval_or_validation_failure"
            )
            return self._fallback_result(incident, evidence, reason)

    def _fallback_result(
        self, incident: Incident, evidence: EvidenceSnapshot, reason: str
    ) -> Recommendation:
        recommendation = self._fallback.recommend(incident, evidence)
        provenance: dict[str, Any] = dict(recommendation.provenance or {})
        provenance.update({"fallbackUsed": True, "fallbackReason": reason})
        return Recommendation(
            recommendation_id=recommendation.recommendation_id,
            incident_id=recommendation.incident_id,
            evidence_ids=recommendation.evidence_ids,
            action_type=recommendation.action_type,
            parameters=recommendation.parameters,
            provider=recommendation.provider,
            author_identity=recommendation.author_identity,
            rationale=recommendation.rationale,
            expires_at=recommendation.expires_at,
            non_authoritative=True,
            provenance=provenance,
        )

    @staticmethod
    def _context(chunks: list[SopChunk]) -> str:
        return "\n\n".join(
            f"[document={item.document_id} section={item.section_id} "
            f"chunk={item.chunk_id}]\n{item.text}"
            for item in chunks
        )

    @staticmethod
    def _incident_facts(incident: Incident, evidence: EvidenceSnapshot) -> str:
        return (
            f"incident_id={incident.incident_id}\nshipment_id={incident.shipment_id}\n"
            f"severity={incident.severity}\nevidence_id={evidence.evidence_id}\n"
            f"evidence_hash={evidence.content_hash}\nsummary={evidence.summary}"
        )


def build_recommendation_provider(
    settings: Settings,
) -> DeterministicLocalRecommendationProvider | RetrievalGroundedRecommendationProvider:
    """Build without network activity; disabled or unconfigured always means local fallback."""

    fallback = DeterministicLocalRecommendationProvider()
    if not settings.llm_live_calls_enabled or not os.getenv(settings.llm_api_key_env, ""):
        return fallback
    embeddings = DeterministicEmbeddingProvider()
    store = QdrantVectorStore(
        settings.qdrant_url,
        settings.qdrant_collection,
        embeddings.dimensions,
    )
    provider = OpenAICompatibleRecommendationProvider(
        ProviderConfig(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key_env=settings.llm_api_key_env,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
            reasoning_effort=settings.llm_reasoning_effort,
            live_calls_enabled=settings.llm_live_calls_enabled,
            billing_mode=settings.llm_billing_mode,
        )
    )
    return RetrievalGroundedRecommendationProvider(provider, store, embeddings, fallback)
