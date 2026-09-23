"""Local-only scenario API that exercises the normal telemetry workflow."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from coldchain.api.auth import local_identity
from coldchain.api.dependencies import get_demo_service
from coldchain.api.schemas import DemoRunStarted, DemoRunStatus, DemoScenarioView
from coldchain.application.demo import DemoScenarioService
from coldchain.application.interfaces import Identity
from coldchain.application.workflow import AuthorizationError

router = APIRouter(prefix="/demo", tags=["local-demo"])


@router.get("/scenarios", response_model=list[DemoScenarioView])
async def list_scenarios(
    _: Annotated[Identity, Depends(local_identity)],
    service: Annotated[DemoScenarioService, Depends(get_demo_service)],
) -> list[DemoScenarioView]:
    return [
        DemoScenarioView.model_validate(item, from_attributes=True) for item in service.scenarios()
    ]


@router.post(
    "/scenarios/{scenario_id}",
    response_model=DemoRunStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_scenario(
    scenario_id: str,
    identity: Annotated[Identity, Depends(local_identity)],
    service: Annotated[DemoScenarioService, Depends(get_demo_service)],
) -> dict[str, object]:
    if not ({"dispatcher", "administrator"} & identity.roles):
        raise AuthorizationError("dispatcher or administrator role is required")
    try:
        run = await service.start(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="demo scenario not found") from exc
    return {
        "runId": str(run.run_id),
        "scenarioId": run.scenario_id,
        "correlationId": str(run.correlation_id),
        "shipmentId": str(run.shipment_id),
        "eventIds": [str(item) for item in run.event_ids],
        "publishCount": run.publish_count,
        "status": "ACCEPTED",
    }


@router.get("/runs/{run_id}", response_model=DemoRunStatus)
async def get_run(
    run_id: UUID,
    _: Annotated[Identity, Depends(local_identity)],
    service: Annotated[DemoScenarioService, Depends(get_demo_service)],
) -> dict[str, object]:
    result = await service.status(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="demo run not found")
    return result
