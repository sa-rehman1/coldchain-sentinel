"""Read-only dashboard projection for the local control tower."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coldchain.api.dependencies import get_repository
from coldchain.api.schemas import DashboardView
from coldchain.application.interfaces import DashboardReader

router = APIRouter()


@router.get("/dashboard", response_model=DashboardView)
async def get_dashboard(
    repository: Annotated[DashboardReader, Depends(get_repository)],
) -> dict[str, object]:
    """Return reconciled showcase metrics without mutating workflow state."""

    return await repository.dashboard()
