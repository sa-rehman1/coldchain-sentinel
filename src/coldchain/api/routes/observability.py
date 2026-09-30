"""Read-only, sanitized local observability summary."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coldchain.api.dependencies import get_observability_service
from coldchain.api.schemas import ObservabilitySummaryView
from coldchain.application.observability import ObservabilitySummaryService

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/summary", response_model=ObservabilitySummaryView)
async def observability_summary(
    service: Annotated[ObservabilitySummaryService, Depends(get_observability_service)],
) -> dict[str, object]:
    """Return bounded local metrics, health, alerts, and trace metadata."""

    return await service.summary()
