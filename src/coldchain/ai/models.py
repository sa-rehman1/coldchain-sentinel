"""Strict, auditable model output and provenance contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecommendedAction(StrEnum):
    HOLD_SHIPMENT = "HOLD_SHIPMENT"
    REQUEST_INSPECTION = "REQUEST_INSPECTION"
    ESCALATE_DISPATCHER = "ESCALATE_DISPATCHER"
    ADD_NOTE = "ADD_NOTE"


class UncertaintyLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


ProviderCitationId = Annotated[str, Field(min_length=1, max_length=80)]
ProviderFinding = Annotated[str, Field(max_length=120)]


class ProviderRecommendationDecision(BaseModel):
    """Decision-only fields accepted from the untrusted model boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommended_action: RecommendedAction
    concise_rationale: str = Field(min_length=1, max_length=800)
    cited_evidence_chunk_ids: tuple[ProviderCitationId, ...] = Field(max_length=8)
    cited_incident_evidence_ids: tuple[ProviderCitationId, ...] = Field(max_length=8)
    contraindications: tuple[ProviderFinding, ...] = Field(max_length=8)
    missing_information: tuple[ProviderFinding, ...] = Field(max_length=8)
    evidence_sufficient: bool
    uncertainty_level: UncertaintyLevel

    @model_validator(mode="after")
    def reject_unsafe_content(self) -> "ProviderRecommendationDecision":
        lowered = self.concise_rationale.lower()
        prohibited = (
            "i authorize",
            "authorized to",
            "execute immediately",
            "ignore previous",
            "override policy",
            "disable kill switch",
        )
        if any(value in lowered for value in prohibited):
            raise ValueError("policy-changing, authorization, or injection content rejected")
        if self.evidence_sufficient and (
            not self.cited_evidence_chunk_ids or not self.cited_incident_evidence_ids
        ):
            raise ValueError("sufficient evidence requires both SOP and incident citations")
        return self


class RecommendationOutput(BaseModel):
    """Closed schema accepted from an untrusted model response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommended_action: RecommendedAction
    concise_rationale: str = Field(min_length=1, max_length=800)
    cited_evidence_chunk_ids: tuple[str, ...] = Field(max_length=8)
    cited_incident_evidence_ids: tuple[str, ...] = Field(max_length=8)
    contraindications: tuple[str, ...] = Field(max_length=8)
    missing_information: tuple[str, ...] = Field(max_length=8)
    evidence_sufficient: bool
    uncertainty_level: UncertaintyLevel
    recommendation_expiry: datetime
    schema_version: str = Field(pattern=r"^1\.0$")

    @field_validator("recommendation_expiry")
    @classmethod
    def require_aware_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recommendation expiry must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def reject_unsafe_content(self) -> "RecommendationOutput":
        lowered = self.concise_rationale.lower()
        prohibited = (
            "i authorize",
            "authorized to",
            "execute immediately",
            "ignore previous",
            "override policy",
            "disable kill switch",
        )
        if any(value in lowered for value in prohibited):
            raise ValueError("policy-changing, authorization, or injection content rejected")
        if self.evidence_sufficient and (
            not self.cited_evidence_chunk_ids or not self.cited_incident_evidence_ids
        ):
            raise ValueError("sufficient evidence requires both SOP and incident citations")
        return self


class RecommendationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    api_family: str = "openai-compatible"
    base_url_identifier: str
    model: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    response_schema_version: str = "1.0"
    allowed_action_version: str = "1.0"
    sop_corpus_version: str
    cited_document_ids: tuple[str, ...] = ()
    cited_section_ids: tuple[str, ...] = ()
    cited_chunk_ids: tuple[str, ...] = ()
    retrieved_chunk_ids: tuple[str, ...] = ()
    cited_incident_evidence_ids: tuple[str, ...] = ()
    correlation_id: str
    provider_request_id: str | None = None
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    billing_mode: str
    cost_estimation_basis: str
    estimated_cost: float = Field(ge=0)
    retry_count: int = Field(ge=0, le=1)
    fallback_used: bool
    fallback_reason: str | None = None
    validation_result: str
    evidence_sufficient: bool
    uncertainty_level: str
    recommendation_expiry: datetime
