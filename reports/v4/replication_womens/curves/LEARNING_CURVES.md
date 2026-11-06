# R05 — learning curves and seed stability

hillstrom Womens E-Mail vs No E-Mail (development) · 34,174 units · 251 events · 3 outer folds · 45 fits · 8 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only. The curve is over training rows inside three outer folds of one dataset, so it describes this cohort's budget, not a general sample-size law.

## Learning curves

| candidate | fraction | train rows | events treated | events control | value |
|---|---|---|---|---|---|
| M01 | 25% | 5,695 | 26 | 16 | +0.000746 |
| M01 | 50% | 11,391 | 52 | 32 | +0.000477 |
| M01 | 100% | 22,783 | 103 | 64 | +0.000429 |
| M03 | 25% | 5,695 | 26 | 16 | +0.000956 |
| M03 | 50% | 11,391 | 52 | 32 | +0.001142 |
| M03 | 100% | 22,783 | 103 | 64 | +0.001841 |
| M07 | 25% | 5,695 | 26 | 16 | +0.000799 |
| M07 | 50% | 11,391 | 52 | 32 | +0.001382 |
| M07 | 100% | 22,783 | 103 | 64 | +0.001135 |

Nuisances follow the same budget as the candidate, so the 25% row is not scored by an evaluator that saw four times as much data as the model it is scoring.

## Seed spread at the full fraction

**Three learner seeds describe optimiser jitter at one data budget. No confidence interval is formed from them, because it would be read as sampling uncertainty and it is not.**

| candidate | seeds | mean | IQR | min | max | selected-action agreement |
|---|---|---|---|---|---|---|
| M01 | 3 | +0.000429 | 0.000000 | +0.000429 | +0.000429 | 1.000 |
| M03 | 3 | +0.001841 | 0.000000 | +0.001841 | +0.001841 | 1.000 |
| M07 | 3 | +0.001094 | 0.000033 | +0.001069 | +0.001135 | 0.976 |

Selected-action agreement is the Jaccard overlap of the contacted sets between seed pairs. Two seeds that score the same value while contacting different accounts have not reproduced anything anyone could act on, so it is reported beside the value rather than instead of it.
