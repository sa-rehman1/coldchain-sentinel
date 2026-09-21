"""Prometheus exposition endpoint with no dependency readiness coupling."""

from fastapi import APIRouter, Response

from coldchain.observability.metrics import render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    payload, media_type = render_metrics()
    return Response(content=payload, media_type=media_type)
