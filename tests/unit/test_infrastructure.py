from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from pytest import MonkeyPatch

from coldchain.contracts.models import TelemetryEvent
from coldchain.infrastructure.database import Database, build_database
from coldchain.infrastructure.kafka import (
    KafkaConfig,
    KafkaTelemetryPublisher,
    consumer_options,
    producer_options,
)


def test_database_factory_can_disable_database() -> None:
    assert build_database(None, 5) is None


async def test_database_construction_is_lazy() -> None:
    database = Database("postgresql+asyncpg://user:placeholder@localhost/db")
    assert database.is_initialized is False
    await database.dispose()


def test_kafka_defaults_are_idempotent_and_manual_commit() -> None:
    config = KafkaConfig(
        bootstrap_servers="kafka:29092",
        telemetry_topic="coldchain.telemetry.v1",
        consumer_group="worker-v1",
        security_protocol="PLAINTEXT",
    )
    assert producer_options(config)["enable_idempotence"] is True
    assert producer_options(config)["acks"] == "all"
    assert consumer_options(config)["enable_auto_commit"] is False
    assert consumer_options(config)["group_id"] == "worker-v1"


class FakeKafkaProducer:
    instances: ClassVar[list["FakeKafkaProducer"]] = []

    def __init__(self, **options: object) -> None:
        self.options = options
        self.messages: list[tuple[str, bytes, bytes]] = []
        self.started = False
        self.instances.append(self)

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def send_and_wait(
        self,
        topic: str,
        *,
        value: bytes,
        key: bytes,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        self.messages.append((topic, key, value))


async def test_kafka_publisher_lifecycle_and_message_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("coldchain.infrastructure.kafka.AIOKafkaProducer", FakeKafkaProducer)
    config = KafkaConfig("kafka:29092", "telemetry", "worker", "PLAINTEXT")
    publisher = KafkaTelemetryPublisher(config)
    item = TelemetryEvent(
        event_id=uuid4(),
        correlation_id=uuid4(),
        occurred_at=datetime.now(UTC),
        producer="test",
        shipment_id=uuid4(),
        vehicle_id="v",
        sensor_id="s",
        latitude=1,
        longitude=1,
        temperature_celsius=5,
        cargo_type="FRESH_PERISHABLES",
        reading_sequence=1,
    )
    try:
        await publisher.publish(item)
    except RuntimeError as exc:
        assert "not started" in str(exc)
    await publisher.start()
    await publisher.publish(item)
    producer: Any = FakeKafkaProducer.instances[-1]
    assert producer.messages[0][1] == str(item.shipment_id).encode()
    await publisher.stop()
    assert producer.started is False
