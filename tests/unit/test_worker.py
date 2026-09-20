from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition

from coldchain.application.interfaces import ProcessingResult
from coldchain.contracts.models import FailureEnvelope, TelemetryEvent
from coldchain.infrastructure.kafka import KafkaConfig
from coldchain.workers.telemetry import TelemetryWorker


def event() -> TelemetryEvent:
    return TelemetryEvent(
        event_id=uuid4(),
        correlation_id=uuid4(),
        occurred_at=datetime.now(UTC),
        producer="worker-test",
        shipment_id=uuid4(),
        vehicle_id="v1",
        sensor_id="s1",
        latitude=1,
        longitude=1,
        temperature_celsius=10.5,
        cargo_type="FRESH_PERISHABLES",
        reading_sequence=1,
    )


class FakeWorkflow:
    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    async def process(self, item: TelemetryEvent, now: datetime | None = None) -> ProcessingResult:
        self.events.append(item)
        return ProcessingResult(False, "BREACH", uuid4())


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bytes, bytes]] = []
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def send_and_wait(self, topic: str, *, key: bytes, value: bytes) -> None:
        self.messages.append((topic, key, value))


class StopWorker(Exception):
    pass


class FakeConsumer:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0
        self.commits: list[dict[Any, Any]] = []
        self.stopped = False

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self.stopped = True

    async def getmany(self, **_: object) -> dict[TopicPartition, list[SimpleNamespace]]:
        self.calls += 1
        if self.calls > 1:
            raise StopWorker
        partition = TopicPartition("coldchain.telemetry.v1", 0)
        return {partition: [SimpleNamespace(value=self.payload, offset=4)]}

    async def commit(self, offsets: dict[Any, Any]) -> None:
        self.commits.append(offsets)


def config() -> KafkaConfig:
    return KafkaConfig("unused:9092", "coldchain.telemetry.v1", "test", "PLAINTEXT")


async def test_worker_validates_and_processes_valid_message() -> None:
    workflow = FakeWorkflow()
    producer = FakeProducer()
    worker = TelemetryWorker(
        config(),
        cast(Any, workflow),
        cast(AIOKafkaConsumer, FakeConsumer(b"unused")),
        cast(AIOKafkaProducer, producer),
    )
    item = event()
    await worker.process_message(
        item.model_dump_json(by_alias=True).encode(),
        TopicPartition("coldchain.telemetry.v1", 0),
        1,
        datetime.now(UTC),
    )
    assert workflow.events == [item]
    assert producer.messages == []


async def test_invalid_message_is_versioned_and_sent_to_dlq() -> None:
    workflow = FakeWorkflow()
    producer = FakeProducer()
    worker = TelemetryWorker(
        config(),
        cast(Any, workflow),
        cast(AIOKafkaConsumer, FakeConsumer(b"unused")),
        cast(AIOKafkaProducer, producer),
    )
    await worker.process_message(
        b'{"not":"telemetry"}',
        TopicPartition("coldchain.telemetry.v1", 2),
        9,
        datetime.now(UTC),
    )
    assert workflow.events == []
    assert producer.messages[0][0] == "coldchain.telemetry.dlq.v1"
    envelope = FailureEnvelope.model_validate_json(producer.messages[0][2])
    assert envelope.failed_offset == 9
    assert envelope.reason_code == "CONTRACT_VALIDATION_FAILED"


async def test_run_commits_only_after_successful_processing_and_stops() -> None:
    item = event()
    consumer = FakeConsumer(item.model_dump_json(by_alias=True).encode())
    producer = FakeProducer()
    worker = TelemetryWorker(
        config(),
        cast(Any, FakeWorkflow()),
        cast(AIOKafkaConsumer, consumer),
        cast(AIOKafkaProducer, producer),
    )
    with pytest.raises(StopWorker):
        await worker.run()
    assert len(consumer.commits) == 1
    assert consumer.stopped is True
    assert producer.started is False
