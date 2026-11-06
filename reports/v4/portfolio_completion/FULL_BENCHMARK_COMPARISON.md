# Full IBM benchmark reproduction comparison

**Protocol:** [agreement rules declared before the new report](../../../docs/FULL_BENCHMARK_REPRODUCTION_PROTOCOL_EN.md).  
**Runs compared:** [archived full report](../../benchmark/BENCHMARK_REPORT.md) and [reproduced full manifest](../reproduced_full/RUN_MANIFEST.json). Both use the pinned 7,043-row IBM CSV and the same frozen 1,409-row test split. This comparison evaluates predictive reproducibility, not causal impact.

The 30 September final-source run took about 6 minutes 43 seconds on the local Windows CPU, satisfied all 180 pinned research-lock packages, and recorded producer source SHA-256 `828b3d284469537aed8ea23dfc9912408a386950ac0e69a697dedc125ee79ec5`. The model bundle SHA-256 is `289c7af82c574f23d92fe59d21197b76b6ee860b2b4a7c12fa0caf0de609e896`.

| Predeclared readout | Archived full | Reproduced full | Decision |
|---|---:|---:|---|
| Champion and calibration | logistic, none | logistic, none | Match |
| Frozen-test AP | 0.6396 | 0.6396 | Within 0.005 |
| Frozen-test ROC-AUC | 0.8499 | 0.8499 | Within 0.005 |
| Frozen-test Brier | 0.1345 | 0.1345 | Within 0.005 |
| Test rows | 1,409 | 1,409 | Exact |
| Complexity decision | logistic retained | logistic retained | Match |

The eight model rows in `benchmark_table.csv` have **zero absolute difference across all numeric metric columns** after excluding fit time; the selected parameter JSON also matches. The 1,409 test-prediction rows have the same IDs and numeric values, and `test_predictions.csv` has the same SHA-256 in both runs: `6f306820f2266a94b0b110b3c230a50a180d3acf8390f4ee2543a2ea3fbf265d`. These checks are stronger than the rounded table above. Model bundle bytes differ because each run records creation and tracking metadata; use each manifest's bundle digest for replay.

## Visible scenario difference

The archived scenario table selected 141/141 contacts at a nominal 10% budget; the current scenario table selects 140/140. The current [hard capacity rule](../../../src/telco_churn/allocation.py) uses `floor(0.10 × 1,409) = 140`, which cannot exceed a 10% contact envelope. The published ranking diagnostic in `budget_metrics.csv` preserves its historical `ceil` convention, giving 141 rows. Consequently, the current base-case illustrative value is 1,214.07 versus archived 1,219.46, and the optimistic value is 6,332.84 versus 6,370.40. This is a policy-cap convention change, not a predictive-model improvement or failure. The new benchmark report states both conventions beside the tables.

**Decision:** predictive agreement passes the declared rules. The scenario difference remains visible and explained. No measured save rate, offer response, or return on investment can be inferred from IBM's static labels.
