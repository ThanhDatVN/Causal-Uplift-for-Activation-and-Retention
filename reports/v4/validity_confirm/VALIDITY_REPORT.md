# R00 / R01 — exact identities and evaluator validation

Run 2026-09-21T08:22:44+00:00 · 2,000 worlds per scenario · seed 20260923 · 1787 s.

- status: **FAIL**
- R00 identities: all pass
- coverage failures: 2
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
| V05B | Rare outcome under a balanced design; e = 0.5; tau = 0.0005 | whether rarity alone breaks the interval, or only rarity plus imbalance |
| V06 | Repeated accounts with cluster dependence; e = 0.5, drawn once per cluster; tau = 0 | IID standard errors under clustering |
| B01 | Practical-boundary null at the benchmark margin; e = 0.5; tau = 0.002 | a promotion rule stated against a margin rather than against zero |
| V07 | Heavy-tailed continuous reward; e = 0.5; policy contacts X > 0.5 | tail contributions; finite variance does not give small-sample normality |

### Readouts

| Scenario | Estimator | Variant | Truth | Bias | MCSE | Coverage | Wilson 95% | CI width | Width ratio | Score skew | Promotion |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| V01 | ipw | primary | 0.00000 | +0.000261 | 0.000308 | 0.947 | [0.936, 0.956] | 0.05421 | 1.004 | -0.00 | 0.032 |
| V01 | dr_correct | primary | 0.00000 | +0.000065 | 0.000065 | 0.946 | [0.935, 0.955] | 0.01140 | 0.999 | 0.01 | 0.028 |
| V01 | dr_misspecified | primary | 0.00000 | +0.000062 | 0.000065 | 0.946 | [0.935, 0.955] | 0.01141 | 1.000 | 0.01 | 0.028 |
| V02 | ipw | primary | 0.00250 | +0.000319 | 0.000315 | 0.951 | [0.940, 0.959] | 0.05428 | 0.984 | -0.00 | 0.041 |
| V02 | dr_correct | primary | 0.00250 | +0.000062 | 0.000061 | 0.962 | [0.953, 0.970] | 0.01107 | 1.042 | 0.37 | 0.136 |
| V02 | dr_misspecified | primary | 0.00250 | +0.000060 | 0.000061 | 0.962 | [0.953, 0.970] | 0.01109 | 1.042 | 0.38 | 0.137 |
| V03 | ipw | primary | 0.00500 | -0.000023 | 0.000309 | 0.950 | [0.940, 0.959] | 0.05436 | 1.005 | -0.00 | 0.054 |
| V03 | dr_correct | primary | 0.00500 | +0.000055 | 0.000060 | 0.950 | [0.939, 0.958] | 0.01075 | 1.023 | 0.82 | 0.461 |
| V03 | dr_misspecified | primary | 0.00500 | +0.000054 | 0.000060 | 0.949 | [0.938, 0.957] | 0.01076 | 1.023 | 0.83 | 0.458 |
| V04 | ipw | primary | 0.00500 | +0.000120 | 0.000376 | 0.955 | [0.945, 0.963] | 0.06785 | 1.030 | -2.17 | 0.044 |
| V04 | dr_correct | primary | 0.00500 | +0.000112 | 0.000080 | 0.942 | [0.930, 0.951] | 0.01401 | 0.996 | 10.25 | 0.323 |
| V04 | dr_misspecified | primary | 0.00500 | +0.000111 | 0.000081 | 0.943 | [0.932, 0.952] | 0.01404 | 0.993 | 10.60 | 0.326 |
| V04 | wrong_propensity | ipw_constant_propensity_negative_control | 0.00500 | +0.576750 | 0.000178 | 0.000 | [0.000, 0.002] | 0.04944 | 1.588 | -0.32 | 1.000 |
| V04 | wrong_propensity | dr_constant_propensity_negative_control | 0.00500 | +0.000123 | 0.000059 | 0.951 | [0.940, 0.959] | 0.01031 | 1.001 | -3.61 | 0.505 |
| V05 | ipw | primary | 0.00025 | +0.000134 | 0.000524 | 0.948 | [0.937, 0.956] | 0.09216 | 1.003 | -3.79 | 0.023 |
| V05 | dr_correct | primary | 0.00025 | -0.000016 | 0.000043 | 0.929 | [0.917, 0.939] | 0.00842 | 1.115 | 44.81 | 0.034 |
| V05 | dr_misspecified | primary | 0.00025 | -0.000016 | 0.000043 | 0.928 | [0.916, 0.939] | 0.00843 | 1.116 | 44.97 | 0.035 |
| V05B | ipw | primary | 0.00025 | -0.000117 | 0.000323 | 0.943 | [0.931, 0.952] | 0.05527 | 0.977 | -0.00 | 0.034 |
| V05B | dr_correct | primary | 0.00025 | +0.000015 | 0.000025 | 0.948 | [0.937, 0.956] | 0.00442 | 1.025 | 0.76 | 0.049 |
| V05B | dr_misspecified | primary | 0.00025 | +0.000015 | 0.000025 | 0.947 | [0.936, 0.956] | 0.00442 | 1.025 | 0.77 | 0.049 |
| V06 | ipw | cluster_robust | 0.00000 | -0.000376 | 0.000488 | 0.951 | [0.941, 0.960] | 0.08535 | 0.998 | 0.00 | 0.025 |
| V06 | ipw | iid_negative_control | 0.00000 | -0.000376 | 0.000488 | 0.787 | [0.769, 0.805] | 0.05421 | 0.634 | 0.00 | 0.100 |
| V06 | dr_correct | cluster_robust | 0.00000 | -0.000037 | 0.000102 | 0.938 | [0.927, 0.948] | 0.01749 | 0.978 | -0.00 | 0.032 |
| V06 | dr_correct | iid_negative_control | 0.00000 | -0.000037 | 0.000102 | 0.783 | [0.764, 0.801] | 0.01138 | 0.636 | -0.00 | 0.107 |
| V06 | dr_misspecified | cluster_robust | 0.00000 | -0.000037 | 0.000102 | 0.936 | [0.924, 0.946] | 0.01751 | 0.977 | -0.00 | 0.032 |
| V06 | dr_misspecified | iid_negative_control | 0.00000 | -0.000037 | 0.000102 | 0.784 | [0.765, 0.801] | 0.01139 | 0.636 | -0.00 | 0.107 |
| B01 | ipw | primary | 0.00100 | +0.000169 | 0.000310 | 0.945 | [0.934, 0.954] | 0.05425 | 1.000 | -0.00 | 0.028 |
| B01 | dr_correct | primary | 0.00100 | +0.000005 | 0.000064 | 0.947 | [0.936, 0.956] | 0.01126 | 0.998 | 0.14 | 0.053 |
| B01 | dr_misspecified | primary | 0.00100 | +0.000002 | 0.000065 | 0.946 | [0.935, 0.955] | 0.01128 | 0.997 | 0.14 | 0.053 |
| V07 | ipw | primary | 0.02500 | +0.000313 | 0.000462 | 0.947 | [0.936, 0.956] | 0.07919 | 0.977 | 0.03 | 0.252 |
| V07 | dr_correct | primary | 0.02500 | -0.000079 | 0.000321 | 0.943 | [0.931, 0.952] | 0.05529 | 0.982 | 0.04 | 0.432 |
| V07 | dr_misspecified | primary | 0.02500 | -0.000063 | 0.000321 | 0.944 | [0.933, 0.953] | 0.05532 | 0.981 | 0.04 | 0.433 |

## Not run

- **V08_batch_cap** — blocked on G06: the batch-policy interval has no validated domain yet, so there is nothing to score it against
- **V09_two_stage_recruitment** — runs separately once the recruitment estimator has a declared target; the variance decomposition exists but its gate does not
