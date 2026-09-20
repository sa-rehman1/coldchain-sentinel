"""Versioned deterministic temperature-breach policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from coldchain.domain.incidents import require_utc


class BreachDisposition(StrEnum):
    NORMAL = "NORMAL"
    BREACH = "BREACH"
    STALE = "STALE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True, slots=True)
class TemperatureReading:
    event_id: UUID
    occurred_at: datetime
    sequence: int
    temperature_celsius: float


@dataclass(frozen=True, slots=True)
class BreachEvaluation:
    disposition: BreachDisposition
    policy_version: str
    reason_codes: tuple[str, ...]
    inputs: dict[str, str | int | float | list[float]]
    severity: str | None = None


@dataclass(frozen=True, slots=True)
class FreshPerishablePolicy:
    version: str = "fresh-perishable-temperature-1.0"
    upper_threshold_celsius: float = 8.0
    clearly_unsafe_celsius: float = 10.0
    sustained_reading_count: int = 3
    stale_after: timedelta = timedelta(minutes=15)

    def evaluate(
        self,
        current: TemperatureReading,
        history: tuple[TemperatureReading, ...],
        evaluated_at: datetime,
    ) -> BreachEvaluation:
        now = require_utc(evaluated_at)
        occurred_at = require_utc(current.occurred_at)
        inputs: dict[str, str | int | float | list[float]] = {
            "temperatureCelsius": current.temperature_celsius,
            "readingSequence": current.sequence,
            "occurredAt": occurred_at.isoformat(),
            "upperThresholdCelsius": self.upper_threshold_celsius,
            "clearlyUnsafeCelsius": self.clearly_unsafe_celsius,
            "sustainedReadingCount": self.sustained_reading_count,
        }
        if current.sequence < 0:
            return self.fail_closed(inputs, "INVALID_SEQUENCE")
        if occurred_at > now + timedelta(minutes=1):
            return self.fail_closed(inputs, "FUTURE_READING")
        if now - occurred_at > self.stale_after:
            return BreachEvaluation(
                BreachDisposition.STALE, self.version, ("STALE_READING",), inputs
            )
        if history and current.sequence <= max(item.sequence for item in history):
            return BreachEvaluation(
                BreachDisposition.OUT_OF_ORDER,
                self.version,
                ("NON_MONOTONIC_SEQUENCE",),
                inputs,
            )
        if current.temperature_celsius >= self.clearly_unsafe_celsius:
            return BreachEvaluation(
                BreachDisposition.BREACH,
                self.version,
                ("CLEARLY_UNSAFE_TEMPERATURE",),
                inputs,
                "CRITICAL",
            )
        ordered = (*history[-(self.sustained_reading_count - 1) :], current)
        temperatures = [item.temperature_celsius for item in ordered]
        inputs["sustainedTemperatures"] = temperatures
        if len(ordered) >= self.sustained_reading_count and all(
            value > self.upper_threshold_celsius for value in temperatures
        ):
            return BreachEvaluation(
                BreachDisposition.BREACH,
                self.version,
                ("SUSTAINED_HIGH_TEMPERATURE",),
                inputs,
                "HIGH",
            )
        return BreachEvaluation(
            BreachDisposition.NORMAL,
            self.version,
            ("WITHIN_POLICY",),
            inputs,
        )

    def fail_closed(
        self,
        inputs: dict[str, str | int | float | list[float]],
        reason: str,
    ) -> BreachEvaluation:
        return BreachEvaluation(
            BreachDisposition.FAIL_CLOSED,
            self.version,
            (reason,),
            inputs,
        )
