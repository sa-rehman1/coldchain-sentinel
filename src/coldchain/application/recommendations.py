"""Provider-neutral recommendation boundary and offline implementation."""

from datetime import timedelta
from uuid import uuid4

from coldchain.domain import EvidenceSnapshot, Incident, Recommendation
from coldchain.domain.incidents import utc_now


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
        )
