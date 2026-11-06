# R03 — bounded tuning

hillstrom Mens E-Mail vs No E-Mail (development) · 34,092 units · 302 events · 3 outer x 3 inner · 237 candidate fits · 36 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only, three outer folds of one dataset. A tuned score here is not a confirmation, and the fold-to-fold instability of the chosen configuration is reported rather than averaged away.

| candidate | family | tuned value | vs baseline | gain from tuning | config stable | distinct configs |
|---|---|---|---|---|---|---|
| M01 | outcome_ranking | +0.00163 | -0.00102 | -0.00102 | **no** | 8/8 |
| M03 | s_learner | +0.00207 | -0.00058 | +0.00008 | **no** | 8/8 |
| M07 | dr_learner | +0.00091 | -0.00175 | +0.00004 | **no** | 4/8 |

`gain from tuning` is the tuned configuration minus the runbook default on the *same* outer folds, which is the question this stage exists to answer. `vs baseline` is against M01, paired on the same folds as R02.

`distinct configs` is how many of the grid points actually produced different allocations. Where it is below the grid size the search was narrower than it looks: a dimension the allocator cannot see is not a dimension.

### M01

Chosen per outer fold: {"C": 1.0}; {"C": 1.0}; {"C": 0.01}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.

### M03

Chosen per outer fold: {"C": 0.03}; {"C": 3.0}; {"C": 0.03}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.

### M07

Chosen per outer fold: {"alpha": 0.1, "shrinkage": 0.5}; {"alpha": 100.0, "shrinkage": 0.5}; {"alpha": 0.1, "shrinkage": 0.5}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.
