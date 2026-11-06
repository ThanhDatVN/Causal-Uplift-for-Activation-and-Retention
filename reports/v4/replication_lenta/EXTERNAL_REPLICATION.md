# R10 — external replication on Lenta

lenta SMS campaign (development) · 60,000 units · 6,498 events · e = 0.7501 · A = 0.0321 · 2689 s

**different company, country, channel (SMS not e-mail), outcome and population, and a response rate two orders of magnitude above Hillstrom's. The Womens arm is reported separately and is not this.**

One replication domain, a declared subsample of its development split, three outer folds. Two datasets under one protocol is the minimum that can be called replication, not a settled answer.

## Registered predictions

These were written into the module docstring before the run.

| prediction | held? | evidence |
|---|---|---|
| **P1_a_causal_learner_wins** — at least one causal learner beats the M01 baseline | **yes** | candidates_beating_the_baseline: ['M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08'] |
| **P2_configurations_stabilise** — with more events, at least one family agrees on a configuration across folds | **NO** | families_with_a_stable_configuration: [] |
| **P3_a_learning_curve_appears** — at least one finalist improves from 25% to 100% of the training rows | **yes** | finalists_improving_with_data: ['M02', 'M06', 'M08'] |

## R02 on Lenta

| candidate | value | vs baseline |
|---|---|---|
| M06 | +0.002270 | +0.003334 |
| M03 | +0.001463 | +0.002528 |
| M08 | +0.000898 | +0.001962 |
| M05 | +0.000882 | +0.001946 |
| M07 | +0.000059 | +0.001123 |
| M04 | -0.000366 | +0.000698 |
| M02 | -0.000488 | +0.000577 |
| M01 | -0.001064 | +0.000000 |

## R03 on Lenta

| candidate | gain from tuning | config stable |
|---|---|---|
| M02 | -0.000499 | **no** |
| M06 | +0.000179 | **no** |
| M08 | -0.001947 | **no** |

## R05 on Lenta

| candidate | 25% | 50% | 100% |
|---|---|---|---|
| M02 | -0.002372 | -0.000036 | -0.000488 |
| M06 | +0.001691 | +0.001504 | +0.002270 |
| M08 | +0.001590 | +0.000336 | +0.001776 |

**R04 is not run here.** its representation factor is defined by Hillstrom's own columns and its cost model keys on a channel column Lenta lacks; running a different factorial under the same name would be a quiet substitution.
