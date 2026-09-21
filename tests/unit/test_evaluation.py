import json
import socket
from pathlib import Path

import pytest

from coldchain.evaluation import METRIC_NAMES, evaluate_dataset, run_evaluations


def evaluation_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return root / "evaluations" / "scenarios.v1.json", root / "evaluations" / "thresholds.v1.json"


def test_versioned_dataset_has_sixteen_complete_scenarios() -> None:
    dataset_path, _ = evaluation_paths()
    document = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(document["scenarios"]) == 16
    required = {
        "breach_result",
        "recommendation_behavior",
        "citation_validity",
        "governance_result",
        "approval_required",
        "command_outcome",
        "required_audit_events",
    }
    assert all(required <= set(item["expected"]) for item in document["scenarios"])


def test_evaluation_is_offline_deterministic_and_meets_thresholds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_path, threshold_path = evaluation_paths()
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network attempted")),
    )
    first = run_evaluations(dataset_path, threshold_path, tmp_path / "first")
    second = run_evaluations(dataset_path, threshold_path, tmp_path / "second")
    assert first.threshold_passed
    assert first.scenario_count == first.passed_count == 16
    assert first.metrics == second.metrics == {name: 1.0 for name in METRIC_NAMES}
    assert (tmp_path / "first" / "report.json").is_file()
    assert "Overall: **PASS**" in (tmp_path / "first" / "report.md").read_text(encoding="utf-8")


def test_evaluation_rejects_drifted_dataset() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        evaluate_dataset(
            {"dataset_version": "bad", "scenarios": []},
            {name: 1 for name in METRIC_NAMES},
        )
    malformed = {"dataset_version": "bad", "scenarios": [{} for _ in range(16)]}
    with pytest.raises(ValueError, match="expected"):
        evaluate_dataset(malformed, {name: 1 for name in METRIC_NAMES})
