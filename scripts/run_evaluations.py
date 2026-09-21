"""Run the deterministic local evaluation dataset without network access."""

from pathlib import Path

from coldchain.evaluation import run_evaluations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = run_evaluations(
        root / "evaluations" / "scenarios.v1.json",
        root / "evaluations" / "thresholds.v1.json",
        root / "artifacts" / "evaluations",
    )
    print(
        f"Evaluation={'PASS' if report.threshold_passed else 'FAIL'} "
        f"scenarios={report.passed_count}/{report.scenario_count}"
    )
    for name, value in report.metrics.items():
        print(f"{name}={value:.3f}")
    return 0 if report.threshold_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
