# Frozen IBM benchmark reproduction protocol

**Declared:** 29 September 2026, before reading the new full-run report.  
**Role:** predictive benchmark reproduction on the existing frozen IBM test, not a new external validation or a treatment-effect study.

## Inputs and command

Run `python scripts/reproduce_benchmark.py --full --output reports/v4/reproduced_full --model-dir artifacts/reproduced_full` on the checksum-pinned IBM file and frozen split. The wrapper must write data, split, source, environment, model, and report hashes. The full protocol uses the original five-fold search, repeated five-by-three stability evaluation, and development-only calibration selection. The [archived report](../reports/benchmark/BENCHMARK_REPORT.md) is the fixed comparator; the [quick run](../reports/v4/reproduced_quick/RUN_MANIFEST.json) has a different search budget and is not the comparator.

## Comparison rules set before the new report

| Readout | Archived full value | Agreement rule |
|---|---:|---|
| Champion | logistic, no calibration | Same family and calibration |
| Frozen-test AP | 0.6396 | Absolute difference at most 0.005 |
| Frozen-test ROC-AUC | 0.8499 | Absolute difference at most 0.005 |
| Frozen-test Brier | 0.1345 | Absolute difference at most 0.005 |
| Frozen-test rows | 1,409 | Exact match |
| Complexity decision | Logistic retained | Same decision under the unchanged development gate |

The tolerances allow small numeric and reporting changes while requiring the main result to reproduce. Report each observed value and absolute difference. If any rule fails, mark the reproduction `DISCREPANCY`, inspect environment, split, search and calibration details, and keep both results visible. Do not change the complexity gate or treat a higher test score as an improvement because the test has already been inspected. Record model SHA-256 even when bundle bytes differ because metadata, serialization or timestamps can change.

The IBM file has no treatment assignment, action outcomes or validated 30-day horizon. Passing this protocol supports local predictive reproducibility only.
