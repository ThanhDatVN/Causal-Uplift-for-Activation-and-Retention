# R05 — learning curves and seed stability

hillstrom Mens E-Mail vs No E-Mail (development) · 34,092 units · 302 events · 3 outer folds · 45 fits · 12 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only. The curve is over training rows inside three outer folds of one dataset, so it describes this cohort's budget, not a general sample-size law.

## Learning curves

| candidate | fraction | train rows | events treated | events control | value |
|---|---|---|---|---|---|
| M01 | 25% | 5,682 | 34 | 16 | +0.002016 |
| M01 | 50% | 11,364 | 69 | 32 | +0.001791 |
| M01 | 100% | 22,728 | 137 | 64 | +0.002654 |
| M03 | 25% | 5,682 | 34 | 16 | +0.002167 |
| M03 | 50% | 11,364 | 69 | 32 | +0.001546 |
| M03 | 100% | 22,728 | 137 | 64 | +0.001994 |
| M07 | 25% | 5,682 | 34 | 16 | +0.001532 |
| M07 | 50% | 11,364 | 69 | 32 | +0.001458 |
| M07 | 100% | 22,728 | 137 | 64 | +0.000864 |

Nuisances follow the same budget as the candidate, so the 25% row is not scored by an evaluator that saw four times as much data as the model it is scoring.

## Seed spread at the full fraction

**Three learner seeds describe optimiser jitter at one data budget. No confidence interval is formed from them, because it would be read as sampling uncertainty and it is not.**

| candidate | seeds | mean | IQR | min | max | selected-action agreement |
|---|---|---|---|---|---|---|
| M01 | 3 | +0.002654 | 0.000000 | +0.002654 | +0.002654 | 1.000 |
| M03 | 3 | +0.001994 | 0.000000 | +0.001994 | +0.001994 | 1.000 |
| M07 | 3 | +0.000927 | 0.000058 | +0.000864 | +0.000981 | 0.976 |

Selected-action agreement is the Jaccard overlap of the contacted sets between seed pairs. Two seeds that score the same value while contacting different accounts have not reproduced anything anyone could act on, so it is reported beside the value rather than instead of it.
