# Benchmark Report — Frozen Test

> Test set was opened after model, hyperparameter, calibration and complexity-gate rules were fixed. IBM sample has no timestamps; this is not out-of-time validation.

## Decision

- Champion: **logistic + none calibration**.
- Complexity gate: **logistic retained; complex model did not clear the predeclared gate**.
- Frozen test: 1,409 rows; development: 5,634 rows.
- Test Average Precision: **0.6444**; logistic reference **0.6444**.
- Test ROC-AUC: **0.8505**; Brier: **0.1343**.

## Model matrix

| Model | CV AP mean±sd | Test AP | Test ROC-AUC | Test Brier | Test log loss |
|---|---:|---:|---:|---:|---:|
| dummy_prior | 0.2654±0.0003 | 0.2654 | 0.5000 | 0.1950 | 0.5787 |
| dummy_most_frequent | 0.2654±0.0003 | 0.2654 | 0.5000 | 0.2654 | 9.5673 |
| logistic | 0.6565±0.0285 | 0.6444 | 0.8505 | 0.1343 | 0.4126 |
| logistic_no_sensitive | 0.6557±0.0321 | 0.6512 | 0.8503 | 0.1343 | 0.4126 |
| hist_gradient_boosting | 0.6606±0.0318 | 0.6703 | 0.8540 | 0.1331 | 0.4072 |
| catboost | 0.6654±0.0326 | 0.6777 | 0.8549 | 0.1642 | 0.4887 |
| logistic_calibrated | 0.6565±0.0285 | 0.6444 | 0.8505 | 0.1343 | 0.4126 |
| champion_calibrated | 0.6565±0.0285 | 0.6444 | 0.8505 | 0.1343 | 0.4126 |

## Calibration candidates on development OOF predictions

| Model | Method | AP | Brier | Log loss | Selected for model |
|---|---|---:|---:|---:|---:|
| logistic | none | 0.6551 | 0.1361 | 0.4196 | True |
| logistic | sigmoid | 0.6551 | 0.1362 | 0.4195 | False |
| catboost | none | 0.6682 | 0.1586 | 0.4732 | False |
| catboost | sigmoid | 0.6649 | 0.1347 | 0.4169 | True |

## Budget matrix on frozen test

| Budget | Contacts | Captured churners | Precision | Recall | Lift |
|---:|---:|---:|---:|---:|---:|
| 5% | 71 | 57 | 80.3% | 15.2% | 3.02× |
| 10% | 141 | 104 | 73.8% | 27.8% | 2.78× |
| 20% | 282 | 192 | 68.1% | 51.3% | 2.57× |
| 30% | 423 | 249 | 58.9% | 66.6% | 2.22× |

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
| base | 10% | 140/140 | 100.0% | 1215.47 |
| optimistic | 20% | 140/140 | 100.0% | 6336.10 |

The value table is scenario analysis, not measured retention uplift or revenue saved. The dataset has no treatment/control outcomes.

## Artifact inventory

- `benchmark_table.csv`, `calibration_candidates.csv`, `calibration_diagnostics.csv`, `budget_metrics.csv`
- `bootstrap_delta.csv`, `slice_metrics.csv`, `permutation_importance.csv`
- `error_cases.csv` (15 anonymized cases), `scenario_summary.csv`
- `test_predictions.csv`, `reliability_table.csv`, `figures/`
- immutable model bundle and `model_metadata.json` under `artifacts/models/`
