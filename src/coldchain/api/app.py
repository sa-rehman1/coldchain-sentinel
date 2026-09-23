"""FastAPI application factory for the control plane."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from coldchain.api.errors import (
    ServiceUnavailableError,
    authorization_error_handler,
    http_exception_handler,
    service_unavailable_handler,
    unhandled_exception_handler,
    validation_exception_handler,
    workflow_conflict_handler,
)
from coldchain.api.middleware import CorrelationIdMiddleware
from coldchain.api.routes.demo import router as demo_router
from coldchain.api.routes.health import router as health_router
from coldchain.api.routes.incidents import router as incidents_router
from coldchain.api.routes.metrics import router as metrics_router
from coldchain.application.actions import SimulatedColdChainActionAdapter
from coldchain.application.demo import DemoRunReader, DemoScenarioService
from coldchain.application.health import AiHealthService, ReadinessService
from coldchain.application.interfaces import (
    ActionAdapter,
    ManagedTelemetryPublisher,
    TelemetryPublisher,
    WorkflowRepository,
)
from coldchain.application.workflow import (
    ApprovalService,
    AuthorizationError,
    WorkflowConflictError,
)
from coldchain.config import Settings, get_settings
from coldchain.infrastructure.database import build_database
from coldchain.infrastructure.repositories import SqlWorkflowRepository
from coldchain.observability.logging import configure_logging
from coldchain.observability.tracing import configure_tracing
from coldchain.retrieval.core import DeterministicEmbeddingProvider, QdrantVectorStore

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    workflow_repository: WorkflowRepository | None = None,
    telemetry_publisher: TelemetryPublisher | None = None,
    action_adapter: ActionAdapter | None = None,
) -> FastAPI:
    """Build an application without connecting to external services."""

    resolved = settings or get_settings()
    configure_logging(resolved.log_level, resolved.service_name)
    tracer_provider = configure_tracing(
        resolved.service_name,
        enabled=resolved.otel_tracing_enabled,
        endpoint=resolved.otel_exporter_otlp_endpoint,
        timeout_seconds=resolved.otel_export_timeout_seconds,
    )
    database = build_database(
        resolved.database_url.get_secret_value() if resolved.database_url else None,
        resolved.database_connect_timeout_seconds,
    )
    repository = workflow_repository
    managed_publisher: ManagedTelemetryPublisher | None = None
    publisher = telemetry_publisher
    if repository is None and database is not None:
        repository = SqlWorkflowRepository(database)
    if publisher is None and database is not None:
        from coldchain.infrastructure.kafka import KafkaConfig, KafkaTelemetryPublisher

        managed_publisher = KafkaTelemetryPublisher(
            KafkaConfig(
                bootstrap_servers=resolved.kafka_bootstrap_servers,
                telemetry_topic=resolved.kafka_telemetry_topic,
                dead_letter_topic=resolved.kafka_dead_letter_topic,
                consumer_group=resolved.kafka_consumer_group,
                security_protocol=resolved.kafka_security_protocol,
            )
        )
        publisher = managed_publisher
    adapter = action_adapter or SimulatedColdChainActionAdapter()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if managed_publisher is not None:
            await managed_publisher.start()
        try:
            yield
        finally:
            if managed_publisher is not None:
                await managed_publisher.stop()
            if database is not None:
                await database.dispose()
            if tracer_provider is not None:
                tracer_provider.shutdown()

    app = FastAPI(
        title="ColdChain Sentinel Control Plane",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.database = database
    app.state.readiness_service = ReadinessService(database)
    app.state.ai_health_service = AiHealthService(
        resolved,
        QdrantVectorStore(
            resolved.qdrant_url,
            resolved.qdrant_collection,
            DeterministicEmbeddingProvider().dimensions,
        ),
    )
    app.state.workflow_repository = repository
    app.state.telemetry_publisher = publisher
    app.state.approval_service = ApprovalService(repository, adapter) if repository else None
    app.state.demo_service = (
        DemoScenarioService(publisher, cast(DemoRunReader, repository))
        if publisher is not None and repository is not None
        else None
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(ServiceUnavailableError, service_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AuthorizationError, authorization_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(WorkflowConflictError, workflow_conflict_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(incidents_router, prefix=API_PREFIX)
    app.include_router(demo_router, prefix=API_PREFIX)
    app.include_router(metrics_router)
    return app


app = create_app()
