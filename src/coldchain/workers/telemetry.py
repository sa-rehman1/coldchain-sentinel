"""Kafka telemetry worker with durable-before-commit processing."""

import asyncio
import base64
import hashlib
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import OffsetAndMetadata, TopicPartition
from prometheus_client import start_http_server
from pydantic import ValidationError

from coldchain.application.recommendations import build_recommendation_provider
from coldchain.application.workflow import TemperatureBreachWorkflow
from coldchain.config import get_settings
from coldchain.contracts.models import FailureEnvelope, TelemetryEvent
from coldchain.infrastructure.database import Database
from coldchain.infrastructure.kafka import (
    KafkaConfig,
    consumer_options,
    producer_options,
)
from coldchain.infrastructure.repositories import SqlWorkflowRepository
from coldchain.observability.logging import configure_logging
from coldchain.observability.metrics import metrics
from coldchain.observability.tracing import (
    configure_tracing,
    extract_kafka_context,
    inject_kafka_headers,
    span,
)

logger = logging.getLogger(__name__)


def get_kafka_config() -> KafkaConfig:
    settings = get_settings()
    return KafkaConfig(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        telemetry_topic=settings.kafka_telemetry_topic,
        consumer_group=settings.kafka_consumer_group,
        security_protocol=settings.kafka_security_protocol,
        dead_letter_topic=settings.kafka_dead_letter_topic,
    )


class TelemetryWorker:
    def __init__(
        self,
        config: KafkaConfig,
        workflow: TemperatureBreachWorkflow,
        consumer: AIOKafkaConsumer | None = None,
        producer: AIOKafkaProducer | None = None,
    ) -> None:
        self._config = config
        self._workflow = workflow
        self._consumer = consumer or AIOKafkaConsumer(
            config.telemetry_topic, **consumer_options(config)
        )
        self._producer = producer or AIOKafkaProducer(**producer_options(config))

    async def run(self) -> None:
        await self._consumer.start()
        await self._producer.start()
        try:
            while True:
                batches = await self._consumer.getmany(timeout_ms=1000, max_records=100)
                for partition, messages in batches.items():
                    for message in messages:
                        await self.process_message(
                            message.value,
                            partition,
                            message.offset,
                            datetime.now(UTC),
                            message.headers,
                        )
                        await self._consumer.commit(
                            {partition: OffsetAndMetadata(message.offset + 1, "")}
                        )
        finally:
            await self._consumer.stop()
            await self._producer.stop()

    async def process_message(
        self,
        value: bytes,
        partition: TopicPartition,
        offset: int,
        received_at: datetime,
        headers: Sequence[tuple[str, bytes]] | None = None,
    ) -> None:
        started = time.perf_counter()
        outcome = "processed"
        metrics.worker_events.labels(outcome="received").inc()
        context = extract_kafka_context(headers)
        with span(
            "kafka.consume",
            context=context,
            attributes={
                "messaging.destination.name": partition.topic,
                "messaging.operation.name": "process",
            },
        ):
            try:
                event = TelemetryEvent.model_validate_json(value)
            except (ValidationError, ValueError):
                outcome = "validation_failure"
                await self._publish_failure(value, partition, offset, received_at)
                metrics.worker_events.labels(outcome=outcome).inc()
                metrics.worker_events.labels(outcome="dlq").inc()
                metrics.structured_errors.labels(
                    component="worker", error_type="contract_validation"
                ).inc()
                logger.warning(
                    "invalid_telemetry_sent_to_dlq",
                    extra={
                        "component": "worker",
                        "eventName": "telemetry_validation_failed",
                        "partition": partition.partition,
                        "offset": offset,
                        "outcome": "dlq",
                        "errorType": "contract_validation",
                    },
                )
                metrics.worker_duration.labels(outcome=outcome).observe(
                    time.perf_counter() - started
                )
                return
            try:
                result = await self._workflow.process(event, received_at)
            except Exception:
                outcome = "retryable_failure"
                metrics.worker_events.labels(outcome=outcome).inc()
                metrics.structured_errors.labels(
                    component="worker", error_type="workflow_failure"
                ).inc()
                metrics.worker_duration.labels(outcome=outcome).observe(
                    time.perf_counter() - started
                )
                logger.exception(
                    "telemetry_processing_failed",
                    extra={
                        "component": "worker",
                        "eventName": "telemetry_processing_failed",
                        "partition": partition.partition,
                        "offset": offset,
                        "outcome": outcome,
                        "errorType": "workflow_failure",
                    },
                )
                raise
            outcome = "duplicate" if result.duplicate else "processed"
            metrics.worker_events.labels(outcome=outcome).inc()
            logger.info(
                "telemetry_processed",
                extra={
                    "component": "worker",
                    "eventName": "telemetry_processed",
                    "partition": partition.partition,
                    "offset": offset,
                    "outcome": outcome,
                },
            )
        metrics.worker_duration.labels(outcome=outcome).observe(time.perf_counter() - started)

    async def _publish_failure(
        self,
        value: bytes,
        partition: TopicPartition,
        offset: int,
        received_at: datetime,
    ) -> None:
        payload_hash = hashlib.sha256(value).hexdigest()
        envelope = FailureEnvelope(
            event_id=uuid5(NAMESPACE_URL, f"{partition.topic}:{partition.partition}:{offset}"),
            correlation_id=uuid4(),
            occurred_at=received_at,
            producer="coldchain-telemetry-worker",
            failed_topic=partition.topic,
            failed_partition=partition.partition,
            failed_offset=offset,
            failure_type="INVALID_MESSAGE",
            reason_code="CONTRACT_VALIDATION_FAILED",
            payload_hash=payload_hash,
            encoded_payload_base64=base64.b64encode(value).decode(),
        )
        await self._producer.send_and_wait(
            self._config.dead_letter_topic,
            key=envelope.event_id.hex.encode(),
            value=envelope.model_dump_json(by_alias=True).encode(),
            headers=inject_kafka_headers(),
        )


async def run_worker() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database URL is required")
    configure_logging(settings.log_level, "coldchain-telemetry-worker")
    tracer_provider = configure_tracing(
        "coldchain-telemetry-worker",
        enabled=settings.otel_tracing_enabled,
        endpoint=settings.otel_exporter_otlp_endpoint,
        timeout_seconds=settings.otel_export_timeout_seconds,
    )
    if settings.metrics_enabled:
        try:
            start_http_server(settings.worker_metrics_port, addr=settings.worker_metrics_host)
        except OSError:
            logger.exception(
                "worker_metrics_server_failed",
                extra={"component": "worker", "eventName": "metrics_server_failed"},
            )
    database = Database(
        settings.database_url.get_secret_value(), settings.database_connect_timeout_seconds
    )
    repository = SqlWorkflowRepository(database)
    workflow = TemperatureBreachWorkflow(
        repository,
        build_recommendation_provider(settings),
        kill_switch_active=settings.governance_kill_switch_active,
    )
    try:
        await TelemetryWorker(get_kafka_config(), workflow).run()
    finally:
        await database.dispose()
        if tracer_provider is not None:
            tracer_provider.shutdown()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
