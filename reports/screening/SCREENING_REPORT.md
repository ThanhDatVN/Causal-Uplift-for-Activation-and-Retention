# R02 — model screening

hillstrom Mens E-Mail vs No E-Mail (development) · 34,092 units · 302 events · e = 0.4987 · 3 outer folds · cap 20% · 7 s

Gate: reports/v4/validity_confirm/validity_suite.json: FAIL at 2000 worlds with the skewness_adjusted_t interval (2 undercovering), but this cohort's design imbalance is 0.0013, inside the region validated by V01, V02, V03, V04, V05B, V06, B01, V07 (up to 0.30); the failing scenarios sit at 0.40 and above

Development shortlist only. These are not confirmatory results and the ranking may not be read as evidence that one method beats another; the intervals are over three outer folds of one dataset.

| ID | Candidate | Family | Score kind | Mean value | Δ vs M01 | 95% over folds | Status |
|---|---|---|---|---:|---:|---|---|
| M01 | Control-outcome Logistic ranking | outcome_ranking | outcome_ranking | +0.00265 | +0.00000 | — | COMPLETED |
| M02 | Control-outcome HGB ranking | outcome_ranking | outcome_ranking | +0.00122 | -0.00143 | [-0.00171, -0.00116] | COMPLETED |
| M03 | S-Logistic | s_learner | reward_difference | +0.00199 | -0.00066 | [-0.00184, +0.00051] | COMPLETED |
| M04 | S-HGB | s_learner | reward_difference | +0.00123 | -0.00142 | [-0.00312, +0.00028] | COMPLETED |
| M05 | T-Logistic | t_learner | reward_difference | +0.00100 | -0.00165 | [-0.00250, -0.00080] | COMPLETED |
| M06 | T-HGB | t_learner | reward_difference | +0.00177 | -0.00088 | [-0.00205, +0.00028] | COMPLETED |
| M07 | DR-Ridge | dr_learner | reward_difference | +0.00087 | -0.00179 | [-0.00239, -0.00119] | COMPLETED |
| M08 | DR-HGB | dr_learner | reward_difference | +0.00083 | -0.00183 | [-0.00218, -0.00147] | COMPLETED |

**Shortlist:** M01, M03, M07 (one representative per family, best mean value).

The interval is over three outer folds of one dataset. It describes fold variation, not population uncertainty, and it is not a confirmation result.
