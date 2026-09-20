"""Kafka telemetry worker with durable-before-commit processing."""

import asyncio
import base64
import hashlib
import logging
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import OffsetAndMetadata, TopicPartition
from pydantic import ValidationError

from coldchain.application.recommendations import DeterministicLocalRecommendationProvider
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
                            message.value, partition, message.offset, datetime.now(UTC)
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
    ) -> None:
        try:
            event = TelemetryEvent.model_validate_json(value)
        except (ValidationError, ValueError):
            await self._publish_failure(value, partition, offset, received_at)
            logger.warning(
                "invalid_telemetry_sent_to_dlq",
                extra={
                    "topic": partition.topic,
                    "partition": partition.partition,
                    "offset": offset,
                    "reasonCode": "CONTRACT_VALIDATION_FAILED",
                },
            )
            return
        result = await self._workflow.process(event, received_at)
        logger.info(
            "telemetry_processed",
            extra={
                "eventId": str(event.event_id),
                "shipmentId": str(event.shipment_id),
                "duplicate": result.duplicate,
                "disposition": result.disposition,
                "incidentId": str(result.incident_id) if result.incident_id else None,
            },
        )

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
        )


async def run_worker() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database URL is required")
    configure_logging(settings.log_level)
    database = Database(
        settings.database_url.get_secret_value(), settings.database_connect_timeout_seconds
    )
    repository = SqlWorkflowRepository(database)
    workflow = TemperatureBreachWorkflow(
        repository,
        DeterministicLocalRecommendationProvider(),
        kill_switch_active=settings.governance_kill_switch_active,
    )
    try:
        await TelemetryWorker(get_kafka_config(), workflow).run()
    finally:
        await database.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
