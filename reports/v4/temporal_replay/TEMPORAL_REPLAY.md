# R07 — temporal replay of refresh strategies

40 worlds per mechanism · 3,000 accounts · 12 training + 12 decision months · 6 s

**each strategy drives its own trajectory: its contacts change churn, contact history and who is still active, so two strategies face different cohorts within a few months. No strategy is re-scored on another's log.**

A mock world, not evidence about any operator. 40 worlds per mechanism is a sensitivity study; the paired standard errors are reported so nobody reads a small difference as an established one. The reward is prevented churn, not money: there is no cost ledger.

Ledger reconciliation: **balanced**

| mechanism | strategy | prevented (all) | vs frozen | prevented (late) | late vs frozen | se | refits |
|---|---|---|---|---|---|---|---|
| covariate_shift | frozen | 31.0 | +0.0 | 6.7 | +0.0 | 0.0 | 0 |
| covariate_shift | calibration_only | 31.1 | +0.1 | 6.7 | +0.0 | 0.0 | 12 |
| covariate_shift | full_expanding | 31.1 | +0.1 | 6.7 | +0.0 | 0.0 | 12 |
| covariate_shift | rolling_6 | 33.5 | +2.5 | 9.2 | +2.5 | 0.5 | 12 |
| effect_reversal | frozen | 2.6 | +0.0 | -10.5 | +0.0 | 0.0 | 0 |
| effect_reversal | calibration_only | 2.7 | +0.1 | -10.4 | +0.1 | 0.1 | 12 |
| effect_reversal | full_expanding | 8.7 | +6.0 | -4.4 | +6.1 | 0.5 | 12 |
| effect_reversal | rolling_6 | 6.2 | +3.5 | -6.2 | +4.3 | 0.5 | 12 |
| ingestion_delay | frozen | 33.4 | +0.0 | 9.3 | +0.0 | 0.0 | 0 |
| ingestion_delay | calibration_only | 33.2 | -0.1 | 9.2 | -0.1 | 0.0 | 12 |
| ingestion_delay | full_expanding | 33.3 | -0.1 | 9.3 | +0.0 | 0.0 | 12 |
| ingestion_delay | rolling_6 | 28.9 | -4.4 | 7.7 | -1.6 | 0.6 | 12 |

The **late** columns cover the second half of the horizon only. The whole-horizon total is dominated by the early months, when every strategy is still using the same freshly fitted model and the active pool is largest, so it hides the degradation this stage exists to measure.

`vs frozen` is paired within each world, because the worlds differ in difficulty and an unpaired mean would mix that in. Under `effect_reversal` the offer eventually becomes harmful, so a strategy that keeps contacting on a stale lift estimate should lose ground -- and `calibration_only` refits the level while leaving the lift where training put it, which is why recalibration is not a fix for effect drift.
