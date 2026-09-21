# Offline evaluation methodology

Run:

```powershell
uv run python scripts/run_evaluations.py
```

The versioned dataset contains exactly 16 synthetic scenarios spanning safe readings, hot and cold
breaches, boundary conditions, missing or unsupported input, provider failure, invalid citations,
prompt injection, prohibited actions, approval waiting, and authorized simulated execution. Each
scenario declares the expected breach result, recommendation behavior, citation validity,
governance result, approval requirement, command outcome, and required audit events.

The harness reports breach classification accuracy, governance agreement, citation validity,
schema validity, prompt-injection resistance, fallback correctness, unauthorized-action prevention,
audit completeness, and whole-scenario pass rate. Versioned thresholds are all nonzero and currently
require 1.0. Reports are written to ignored `artifacts/evaluations/report.json` and `report.md`; a
threshold failure exits nonzero. The harness performs no HTTP, socket, model, embedding, database,
Kafka, or Qdrant operation.
