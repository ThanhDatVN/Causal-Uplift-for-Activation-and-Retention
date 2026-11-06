# Benchmark Report — Frozen Test

> Test set was opened after model, hyperparameter, calibration and complexity-gate rules were fixed. IBM sample has no timestamps; this is not out-of-time validation.

## Decision

- Champion: **logistic + none calibration**.
- Complexity gate: **logistic retained; complex model did not clear the predeclared gate**.
- Frozen test: 1,409 rows; development: 5,634 rows.
- Test Average Precision: **0.6396**; logistic reference **0.6396**.
- Test ROC-AUC: **0.8499**; Brier: **0.1345**.

## Model matrix

| Model | CV AP mean±sd | Test AP | Test ROC-AUC | Test Brier | Test log loss |
|---|---:|---:|---:|---:|---:|
| dummy_prior | 0.2654±0.0001 | 0.2654 | 0.5000 | 0.1950 | 0.5787 |
| dummy_most_frequent | 0.2654±0.0001 | 0.2654 | 0.5000 | 0.2654 | 9.5673 |
| logistic | 0.6592±0.0243 | 0.6396 | 0.8499 | 0.1345 | 0.4134 |
| logistic_no_sensitive | 0.6593±0.0248 | 0.6489 | 0.8502 | 0.1344 | 0.4129 |
| hist_gradient_boosting | 0.6659±0.0302 | 0.6646 | 0.8547 | 0.1328 | 0.4063 |
| catboost | 0.6680±0.0269 | 0.6766 | 0.8557 | 0.1315 | 0.4048 |
| logistic_calibrated | 0.6592±0.0243 | 0.6396 | 0.8499 | 0.1345 | 0.4134 |
| champion_calibrated | 0.6592±0.0243 | 0.6396 | 0.8499 | 0.1345 | 0.4134 |

## Calibration candidates on development OOF predictions

| Model | Method | AP | Brier | Log loss | Selected for model |
|---|---|---:|---:|---:|---:|
| logistic | none | 0.6570 | 0.1357 | 0.4182 | True |
| logistic | sigmoid | 0.6573 | 0.1357 | 0.4182 | False |
| logistic | isotonic | 0.6516 | 0.1359 | 0.4348 | False |
| catboost | none | 0.6630 | 0.1337 | 0.4126 | False |
| catboost | sigmoid | 0.6663 | 0.1342 | 0.4190 | False |
| catboost | isotonic | 0.6647 | 0.1335 | 0.4246 | True |

## Budget matrix on frozen test

| Budget | Contacts | Captured churners | Precision | Recall | Lift |
|---:|---:|---:|---:|---:|---:|
| 5% | 71 | 56 | 78.9% | 15.0% | 2.97× |
| 10% | 141 | 101 | 71.6% | 27.0% | 2.70× |
| 20% | 282 | 193 | 68.4% | 51.6% | 2.58× |
| 30% | 423 | 250 | 59.1% | 66.8% | 2.23× |

The ranking diagnostic uses `ceil(fraction * N)` to preserve the published budget curve. The hard campaign scenario below uses `floor(fraction * N)` so contacts cannot exceed the stated cap.

## Paired stratified bootstrap: champion minus logistic

| Delta metric | Mean | 95% CI |
|---|---:|---:|
| average_precision_delta | 0.0000 | [0.0000, 0.0000] |
| brier_score_delta | 0.0000 | [0.0000, 0.0000] |
| recall_at_10pct_delta | 0.0000 | [0.0000, 0.0000] |

## Simulated business scenarios at 10% capacity

| Scenario | Save-rate assumption | Selected/capacity | Budget use | Simulated EV |
|---|---:|---:|---:|---:|
| conservative | 5% | 0/140 | 0.0% | 0.00 |
| base | 10% | 140/140 | 100.0% | 1214.07 |
| optimistic | 20% | 140/140 | 100.0% | 6332.84 |

The value table is scenario analysis, not measured retention uplift or revenue saved. The dataset has no treatment/control outcomes.

## Artifact inventory

- `benchmark_table.csv`, `calibration_candidates.csv`, `calibration_diagnostics.csv`, `budget_metrics.csv`
- `bootstrap_delta.csv`, `slice_metrics.csv`, `permutation_importance.csv`
- `error_cases.csv` (15 anonymized cases), `scenario_summary.csv`
- `test_predictions.csv`, `reliability_table.csv`, `figures/`
- immutable model bundle and `model_metadata.json` under `artifacts/models/`
