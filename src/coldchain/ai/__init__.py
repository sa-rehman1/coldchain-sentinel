"""Provider-neutral recommendation capabilities."""

from coldchain.ai.models import RecommendationOutput, RecommendationProvenance
from coldchain.ai.provider import (
    OpenAICompatibleRecommendationProvider,
    ProviderConfig,
    ProviderFailure,
)

__all__ = [
    "OpenAICompatibleRecommendationProvider",
    "ProviderConfig",
    "ProviderFailure",
    "RecommendationOutput",
    "RecommendationProvenance",
]
