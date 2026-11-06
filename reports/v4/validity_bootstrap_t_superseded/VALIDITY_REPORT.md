# R00 / R01 — exact identities and evaluator validation

Run 2026-09-21T05:40:17+00:00 · 1,000 worlds per scenario · seed 20260921 · 2072 s.

- status: **FAIL**
- R00 identities: all pass
- coverage failures: 6
- false-promotion failures: 0
- negative controls that misbehaved as intended: V04:ipw_constant_propensity_negative_control:biased, V06:iid_negative_control:undercovers, V06:iid_negative_control:undercovers, V06:iid_negative_control:undercovers

Coverage is scored against the finite-frame truth (the conditional value on the realised X); bias is reported against both that and the analytic population value. A gate pass means the evaluator is sound on these declared mechanisms, not on every mechanism.

## R00 — exact identities

| ID | Identity | Result | Evidence |
|---|---|---|---|
| I1 | Identical policies give a zero contrast and a zero standard error | pass | delta=0.0, se=0.0, disagreement units=0 |
| I2 | A no-action policy against itself is exactly zero, with no phantom cost | pass | delta=0.0, delta_net=0.0 |
| I3 | Enumerated tiny design: the DR expectation equals the design truth | pass | truth=0.000000000000000, enumerated DR expectation=-0.000000000000000 |
| I4 | Constant reward: DR is exactly zero per realisation, IPW only in expectation | pass | max |DR contrast| = 0.0; enumerated IPW expectation = -6.18e-16; at least one IPW realisation non-zero = True |
| I5 | Exhaustive tiny allocation is feasible and cost-monotone | pass | cap=2, optimal net value by unit cost: 0->1.3000, 0.2->0.9000, 0.5->0.4000 |
| I6 | Prevented-churn and reward (1 - Y) agree in sign and magnitude | pass | prevented churn = 0.333333333333333, reward uplift = 0.333333333333333 |

## R01 — scenarios

| Scenario | Mechanism | Detects |
|---|---|---|
| V01 | Sharp null, balanced randomised assignment; e = 0.5; tau = 0 | false promotion; sign and interval plumbing |
| V02 | Constant positive effect, balanced assignment; e = 0.5; tau = 0.005 | bias, coverage and power -- not only the null |
| V03 | Heterogeneous effects with marginal ATE = 0; e = 0.5; tau = 0.01 (2X1 - 1) | treating a weak null as a sharp null; the policy value is not zero |
| V04 | Known stratum-varying propensity; e = 0.2 if X1 = 0 else 0.8; tau = 0.01 (2X1 - 1) | an evaluator that assumes a constant propensity |
| V05 | Rare binary outcome, imbalanced assignment; e = 0.9; tau = 0.0005 | interval reliability under event scarcity; no false certainty |
| V06 | Repeated accounts with cluster dependence; e = 0.5, drawn once per cluster; tau = 0 | IID standard errors under clustering |
| B01 | Practical-boundary null at the benchmark margin; e = 0.5; tau = 0.002 | a promotion rule stated against a margin rather than against zero |
| V07 | Heavy-tailed continuous reward; e = 0.5; policy contacts X > 0.5 | tail contributions; finite variance does not give small-sample normality |

### Readouts

| Scenario | Estimator | Variant | Truth | Bias | MCSE | Coverage | Wilson 95% | CI width | Width ratio | Score skew | Promotion |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| V01 | ipw | primary | 0.00000 | -0.000425 | 0.000438 | 0.957 | [0.943, 0.968] | 0.05378 | 0.991 | 0.00 | 0.021 |
| V01 | dr_correct | primary | 0.00000 | -0.000168 | 0.000090 | 0.952 | [0.937, 0.964] | 0.01129 | 1.010 | -0.02 | 0.022 |
| V01 | dr_misspecified | primary | 0.00000 | -0.000163 | 0.000090 | 0.952 | [0.937, 0.964] | 0.01130 | 1.009 | -0.02 | 0.023 |
| V02 | ipw | primary | 0.00250 | -0.000735 | 0.000429 | 0.952 | [0.937, 0.964] | 0.05383 | 1.012 | -0.00 | 0.035 |
| V02 | dr_correct | primary | 0.00250 | -0.000011 | 0.000086 | 0.952 | [0.937, 0.964] | 0.01096 | 1.033 | 0.37 | 0.136 |
| V02 | dr_misspecified | primary | 0.00250 | -0.000006 | 0.000086 | 0.948 | [0.932, 0.960] | 0.01097 | 1.032 | 0.38 | 0.135 |
| V03 | ipw | primary | 0.00500 | +0.000217 | 0.000438 | 0.936 | [0.919, 0.950] | 0.05385 | 0.991 | -0.00 | 0.071 |
| V03 | dr_correct | primary | 0.00500 | -0.000160 | 0.000090 | 0.927 | [0.909, 0.942] | 0.01066 | 0.955 | 0.78 | 0.444 |
| V03 | dr_misspecified | primary | 0.00500 | -0.000160 | 0.000090 | 0.929 | [0.911, 0.943] | 0.01066 | 0.955 | 0.79 | 0.448 |
| V04 | ipw | primary | 0.00500 | -0.000079 | 0.000570 | 0.940 | [0.924, 0.953] | 0.06721 | 0.951 | -2.17 | 0.062 |
| V04 | dr_correct | primary | 0.00500 | +0.000016 | 0.000113 | 0.942 | [0.926, 0.955] | 0.01389 | 0.995 | 10.24 | 0.331 |
| V04 | dr_misspecified | primary | 0.00500 | +0.000019 | 0.000113 | 0.940 | [0.924, 0.953] | 0.01393 | 0.997 | 10.58 | 0.331 |
| V04 | wrong_propensity | ipw_constant_propensity_negative_control | 0.00500 | +0.576302 | 0.000260 | 0.000 | [0.000, 0.004] | 0.04943 | 1.535 | -0.32 | 1.000 |
| V04 | wrong_propensity | dr_constant_propensity_negative_control | 0.00500 | +0.000007 | 0.000085 | 0.941 | [0.925, 0.954] | 0.01032 | 0.982 | -3.61 | 0.465 |
| V05 | ipw | primary | 0.00025 | -0.000552 | 0.000737 | 0.951 | [0.936, 0.963] | 0.09125 | 0.999 | -3.78 | 0.023 |
| V05 | dr_correct | primary | 0.00025 | +0.000107 | 0.000062 | 0.930 | [0.912, 0.944] | 0.00951 | 1.240 | 45.23 | 0.048 |
| V05 | dr_misspecified | primary | 0.00025 | +0.000108 | 0.000062 | 0.930 | [0.912, 0.944] | 0.00955 | 1.246 | 45.38 | 0.045 |
| V06 | ipw | cluster_robust | 0.00000 | +0.000571 | 0.000692 | 0.949 | [0.934, 0.961] | 0.08496 | 0.991 | -0.00 | 0.028 |
| V06 | ipw | iid_negative_control | 0.00000 | +0.000571 | 0.000692 | 0.781 | [0.754, 0.806] | 0.05372 | 0.627 | -0.00 | 0.111 |
| V06 | dr_correct | cluster_robust | 0.00000 | -0.000011 | 0.000143 | 0.937 | [0.920, 0.950] | 0.01736 | 0.979 | -0.01 | 0.025 |
| V06 | dr_correct | iid_negative_control | 0.00000 | -0.000011 | 0.000143 | 0.772 | [0.745, 0.797] | 0.01122 | 0.633 | -0.01 | 0.115 |
| V06 | dr_misspecified | cluster_robust | 0.00000 | -0.000019 | 0.000143 | 0.936 | [0.919, 0.950] | 0.01737 | 0.978 | -0.01 | 0.026 |
| V06 | dr_misspecified | iid_negative_control | 0.00000 | -0.000019 | 0.000143 | 0.776 | [0.749, 0.801] | 0.01123 | 0.632 | -0.01 | 0.110 |
| B01 | ipw | primary | 0.00100 | +0.000095 | 0.000445 | 0.942 | [0.926, 0.955] | 0.05384 | 0.977 | -0.00 | 0.032 |
| B01 | dr_correct | primary | 0.00100 | -0.000031 | 0.000090 | 0.948 | [0.932, 0.960] | 0.01115 | 0.995 | 0.13 | 0.055 |
| B01 | dr_misspecified | primary | 0.00100 | -0.000027 | 0.000091 | 0.952 | [0.937, 0.964] | 0.01116 | 0.993 | 0.14 | 0.059 |
| V07 | ipw | primary | 0.02500 | +0.000994 | 0.000628 | 0.948 | [0.932, 0.960] | 0.07827 | 1.006 | 0.06 | 0.254 |
| V07 | dr_correct | primary | 0.02500 | +0.000455 | 0.000432 | 0.953 | [0.938, 0.964] | 0.05434 | 1.014 | 0.12 | 0.453 |
| V07 | dr_misspecified | primary | 0.02500 | +0.000462 | 0.000433 | 0.953 | [0.938, 0.964] | 0.05437 | 1.013 | 0.12 | 0.459 |

## Not run

- **V08_batch_cap** — blocked on G06: the batch-policy interval has no validated domain yet, so there is nothing to score it against
- **V09_two_stage_recruitment** — runs separately once the recruitment estimator has a declared target; the variance decomposition exists but its gate does not
