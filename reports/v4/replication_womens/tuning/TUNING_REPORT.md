# R03 — bounded tuning

hillstrom Womens E-Mail vs No E-Mail (development) · 34,174 units · 251 events · 3 outer x 3 inner · 237 candidate fits · 48 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only, three outer folds of one dataset. A tuned score here is not a confirmation, and the fold-to-fold instability of the chosen configuration is reported rather than averaged away.

| candidate | family | tuned value | vs baseline | gain from tuning | config stable | distinct configs |
|---|---|---|---|---|---|---|
| M01 | outcome_ranking | +0.00088 | +0.00045 | +0.00045 | **no** | 8/8 |
| M03 | s_learner | +0.00110 | +0.00067 | -0.00075 | **no** | 8/8 |
| M07 | dr_learner | +0.00119 | +0.00076 | +0.00005 | **no** | 3/8 |

`gain from tuning` is the tuned configuration minus the runbook default on the *same* outer folds, which is the question this stage exists to answer. `vs baseline` is against M01, paired on the same folds as R02.

`distinct configs` is how many of the grid points actually produced different allocations. Where it is below the grid size the search was narrower than it looks: a dimension the allocator cannot see is not a dimension.

### M01

Chosen per outer fold: {"C": 0.3}; {"C": 0.01}; {"C": 0.03}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.

### M03

Chosen per outer fold: {"C": 10.0}; {"C": 0.1}; {"C": 0.003}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.

### M07

Chosen per outer fold: {"alpha": 10.0, "shrinkage": 0.5}; {"alpha": 100.0, "shrinkage": 0.5}; {"alpha": 100.0, "shrinkage": 0.5}

The inner search did not agree across folds. That instability is the finding: a configuration this dataset cannot pin down is not a setting to carry into confirmation.
