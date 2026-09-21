"""Kafka configuration and lazy producer/consumer boundaries."""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from aiokafka import AIOKafkaProducer

from coldchain.contracts.models import TelemetryEvent
from coldchain.observability.tracing import inject_kafka_headers, span


@dataclass(frozen=True, slots=True)
class KafkaConfig:
    bootstrap_servers: str
    telemetry_topic: str
    consumer_group: str
    security_protocol: str
    dead_letter_topic: str = "coldchain.telemetry.dlq.v1"
    enable_auto_commit: bool = False
    auto_offset_reset: str = "earliest"


class EventProducer(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def publish(self, topic: str, key: bytes, value: bytes) -> None: ...


class EventConsumer(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def get_batch(self) -> dict[Any, list[Any]]: ...


def producer_options(config: KafkaConfig) -> dict[str, object]:
    return {
        "bootstrap_servers": config.bootstrap_servers,
        "security_protocol": config.security_protocol,
        "acks": "all",
        "enable_idempotence": True,
    }


def consumer_options(config: KafkaConfig) -> dict[str, object]:
    return {
        "bootstrap_servers": config.bootstrap_servers,
        "security_protocol": config.security_protocol,
        "group_id": config.consumer_group,
        "enable_auto_commit": config.enable_auto_commit,
        "auto_offset_reset": config.auto_offset_reset,
    }


class KafkaTelemetryPublisher:
    """Publish validated telemetry keyed by shipment for ordered processing."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if self._producer is None:
            self._producer = AIOKafkaProducer(**producer_options(self._config))
            await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, event: TelemetryEvent) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka publisher is not started")
        payload = json.dumps(
            event.model_dump(mode="json", by_alias=True), separators=(",", ":")
        ).encode()
        with span(
            "kafka.publish",
            attributes={
                "messaging.destination.name": self._config.telemetry_topic,
                "messaging.operation.name": "publish",
            },
        ):
            await self._producer.send_and_wait(
                self._config.telemetry_topic,
                value=payload,
                key=str(event.shipment_id).encode(),
                headers=inject_kafka_headers(),
            )
