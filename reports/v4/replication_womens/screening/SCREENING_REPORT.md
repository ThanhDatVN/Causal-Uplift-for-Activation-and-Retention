# R02 — model screening

hillstrom Womens E-Mail vs No E-Mail (development) · 34,174 units · 251 events · e = 0.4999 · 3 outer folds · cap 20% · 9 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development shortlist only. These are not confirmatory results and the ranking may not be read as evidence that one method beats another; the intervals are over three outer folds of one dataset.

| ID | Candidate | Family | Score kind | Mean value | Δ vs M01 | 95% over folds | Status |
|---|---|---|---|---:|---:|---|---|
| M01 | Control-outcome Logistic ranking | outcome_ranking | outcome_ranking | +0.00043 | +0.00000 | — | COMPLETED |
| M02 | Control-outcome HGB ranking | outcome_ranking | outcome_ranking | +0.00093 | +0.00050 | [-0.00129, +0.00228] | COMPLETED |
| M03 | S-Logistic | s_learner | reward_difference | +0.00184 | +0.00141 | [-0.00013, +0.00296] | COMPLETED |
| M04 | S-HGB | s_learner | reward_difference | +0.00024 | -0.00019 | [-0.00133, +0.00094] | COMPLETED |
| M05 | T-Logistic | t_learner | reward_difference | +0.00121 | +0.00078 | [-0.00090, +0.00246] | COMPLETED |
| M06 | T-HGB | t_learner | reward_difference | +0.00060 | +0.00017 | [-0.00137, +0.00171] | COMPLETED |
| M07 | DR-Ridge | dr_learner | reward_difference | +0.00102 | +0.00059 | [-0.00127, +0.00245] | COMPLETED |
| M08 | DR-HGB | dr_learner | reward_difference | +0.00060 | +0.00017 | [-0.00130, +0.00163] | COMPLETED |

**Shortlist:** M02, M03, M07 (one representative per family, best mean value).

The interval is over three outer folds of one dataset. It describes fold variation, not population uncertainty, and it is not a confirmation result.
