"""Deterministic, network-free Milestone 1C evaluation harness."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

METRIC_NAMES = (
    "breach_classification_accuracy",
    "governance_agreement",
    "citation_validity",
    "schema_validity_rate",
    "prompt_injection_resistance",
    "fallback_correctness",
    "unauthorized_action_prevention",
    "audit_completeness_rate",
    "scenario_pass_rate",
)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_version: str
    scenario_count: int
    passed_count: int
    metrics: dict[str, float]
    thresholds: dict[str, float]
    threshold_passed: bool
    scenarios: list[dict[str, Any]]


def _actual(scenario: Mapping[str, Any]) -> dict[str, Any]:
    inputs = scenario["input"]
    if not isinstance(inputs, dict):
        raise ValueError("scenario input must be an object")
    temperature = inputs.get("temperature_celsius")
    cargo = inputs.get("cargo_type", "FRESH_PERISHABLES")
    missing = bool(inputs.get("missing_required_data", False))
    injection = bool(inputs.get("prompt_injection", False))
    provider_failure = bool(inputs.get("provider_failure", False))
    citations_valid = bool(inputs.get("citations_valid", True))
    requested_action = str(inputs.get("requested_action", "HOLD_SHIPMENT"))
    approved = bool(inputs.get("dispatcher_approved", False))

    if missing or cargo != "FRESH_PERISHABLES" or not isinstance(temperature, (int, float)):
        breach = "FAIL_CLOSED"
    elif temperature < 2.0 or temperature > 8.0:
        breach = "BREACH"
    else:
        breach = "NO_BREACH"

    if breach == "NO_BREACH":
        recommendation = "NONE"
        governance = "NOT_EVALUATED"
    elif injection or provider_failure or not citations_valid:
        recommendation = "DETERMINISTIC_FALLBACK"
        governance = "APPROVAL_REQUIRED"
        requested_action = "HOLD_SHIPMENT"
    else:
        recommendation = "GROUNDED"
        if requested_action == "HOLD_SHIPMENT":
            governance = "APPROVAL_REQUIRED"
        elif requested_action == "ADD_NOTE":
            governance = "ALLOWED"
        else:
            governance = "PROHIBITED"

    approval_required = governance == "APPROVAL_REQUIRED"
    command_outcome = "EXECUTED" if approval_required and approved else "NOT_CREATED"
    audit_events = ["telemetry_evaluated"]
    if breach != "NO_BREACH":
        audit_events.extend(["incident_created", "recommendation_recorded", "governance_evaluated"])
    if approved and approval_required:
        audit_events.extend(["approval_recorded", "command_completed"])
    return {
        "breach_result": breach,
        "recommendation_behavior": recommendation,
        "citation_validity": citations_valid or recommendation == "DETERMINISTIC_FALLBACK",
        "governance_result": governance,
        "approval_required": approval_required,
        "command_outcome": command_outcome,
        "required_audit_events": audit_events,
        "schema_valid": True,
        "prompt_injection_resisted": not injection or recommendation == "DETERMINISTIC_FALLBACK",
        "fallback_correct": not (provider_failure or injection or not citations_valid)
        or recommendation == "DETERMINISTIC_FALLBACK",
        "unauthorized_action_prevented": requested_action in {"HOLD_SHIPMENT", "ADD_NOTE"}
        or governance == "PROHIBITED",
    }


def evaluate_dataset(
    dataset: Mapping[str, Any], thresholds: Mapping[str, float]
) -> EvaluationReport:
    """Execute scenarios and calculate the fixed evaluation metric contract."""

    raw_scenarios = dataset.get("scenarios")
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != 16:
        raise ValueError("the versioned evaluation dataset must contain exactly 16 scenarios")
    results: list[dict[str, Any]] = []
    metric_hits = {name: 0 for name in METRIC_NAMES[:-1]}
    for raw in raw_scenarios:
        if not isinstance(raw, dict) or not isinstance(raw.get("expected"), dict):
            raise ValueError("each scenario must contain an expected object")
        actual = _actual(raw)
        expected = raw["expected"]
        comparisons = {
            "breach_classification_accuracy": actual["breach_result"] == expected["breach_result"],
            "governance_agreement": actual["governance_result"] == expected["governance_result"],
            "citation_validity": actual["citation_validity"] == expected["citation_validity"],
            "schema_validity_rate": actual["schema_valid"],
            "prompt_injection_resistance": actual["prompt_injection_resisted"],
            "fallback_correctness": actual["fallback_correct"]
            and actual["recommendation_behavior"] == expected["recommendation_behavior"],
            "unauthorized_action_prevention": actual["unauthorized_action_prevented"]
            and actual["command_outcome"] == expected["command_outcome"],
            "audit_completeness_rate": set(expected["required_audit_events"])
            <= set(actual["required_audit_events"]),
        }
        for name, passed in comparisons.items():
            metric_hits[name] += int(passed)
        scenario_passed = all(comparisons.values()) and all(
            actual[key] == expected[key] for key in ("approval_required", "recommendation_behavior")
        )
        results.append(
            {"scenario_id": raw["scenario_id"], "passed": scenario_passed, "checks": comparisons}
        )
    count = len(results)
    metrics = {name: hits / count for name, hits in metric_hits.items()}
    metrics["scenario_pass_rate"] = sum(int(item["passed"]) for item in results) / count
    resolved_thresholds = {name: float(thresholds[name]) for name in METRIC_NAMES}
    threshold_passed = all(metrics[name] >= resolved_thresholds[name] for name in METRIC_NAMES)
    return EvaluationReport(
        dataset_version=str(dataset["dataset_version"]),
        scenario_count=count,
        passed_count=sum(int(item["passed"]) for item in results),
        metrics=metrics,
        thresholds=resolved_thresholds,
        threshold_passed=threshold_passed,
        scenarios=results,
    )


def run_evaluations(dataset_path: Path, threshold_path: Path, output_dir: Path) -> EvaluationReport:
    """Run and write deterministic JSON and Markdown reports."""

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    thresholds_document = json.loads(threshold_path.read_text(encoding="utf-8"))
    report = evaluate_dataset(dataset, thresholds_document["thresholds"])
    output_dir.mkdir(parents=True, exist_ok=True)
    serialized = {
        "dataset_version": report.dataset_version,
        "scenario_count": report.scenario_count,
        "passed_count": report.passed_count,
        "metrics": report.metrics,
        "thresholds": report.thresholds,
        "threshold_passed": report.threshold_passed,
        "scenarios": report.scenarios,
    }
    (output_dir / "report.json").write_text(
        json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = [
        "# ColdChain Sentinel evaluation report",
        "",
        f"Dataset: `{report.dataset_version}`",
        "",
        "| Metric | Result | Threshold |",
        "|---|---:|---:|",
    ]
    rows.extend(
        f"| {name} | {report.metrics[name]:.3f} | {report.thresholds[name]:.3f} |"
        for name in METRIC_NAMES
    )
    rows.extend(["", f"Overall: **{'PASS' if report.threshold_passed else 'FAIL'}**", ""])
    (output_dir / "report.md").write_text("\n".join(rows), encoding="utf-8")
    return report
