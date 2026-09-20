from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coldchain.domain import (
    BreachDisposition,
    FreshPerishablePolicy,
    TemperatureReading,
)

NOW = datetime(2026, 9, 19, 20, 0, tzinfo=UTC)


def reading(
    sequence: int, temperature: float, occurred_at: datetime | None = None
) -> TemperatureReading:
    return TemperatureReading(uuid4(), occurred_at or NOW, sequence, temperature)


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (7.9, BreachDisposition.NORMAL),
        (8.0, BreachDisposition.NORMAL),
        (10.0, BreachDisposition.BREACH),
        (12.5, BreachDisposition.BREACH),
    ],
)
def test_normal_edge_and_clearly_unsafe_boundaries(
    temperature: float, expected: BreachDisposition
) -> None:
    result = FreshPerishablePolicy().evaluate(reading(3, temperature), (), NOW)
    assert result.disposition is expected


def test_three_ordered_high_readings_are_sustained_breach() -> None:
    history = (reading(1, 8.1), reading(2, 8.2))
    result = FreshPerishablePolicy().evaluate(reading(3, 8.3), history, NOW)
    assert result.disposition is BreachDisposition.BREACH
    assert result.reason_codes == ("SUSTAINED_HIGH_TEMPERATURE",)
    assert result.inputs["sustainedTemperatures"] == [8.1, 8.2, 8.3]


def test_stale_and_out_of_order_are_not_processed_as_breaches() -> None:
    policy = FreshPerishablePolicy()
    stale = policy.evaluate(reading(4, 12, NOW - timedelta(minutes=16)), (), NOW)
    out_of_order = policy.evaluate(reading(2, 12), (reading(3, 5),), NOW)
    assert stale.disposition is BreachDisposition.STALE
    assert out_of_order.disposition is BreachDisposition.OUT_OF_ORDER


def test_invalid_or_future_readings_fail_closed() -> None:
    policy = FreshPerishablePolicy()
    invalid = policy.evaluate(reading(-1, 5), (), NOW)
    future = policy.evaluate(reading(1, 5, NOW + timedelta(minutes=2)), (), NOW)
    assert invalid.disposition is BreachDisposition.FAIL_CLOSED
    assert future.disposition is BreachDisposition.FAIL_CLOSED
