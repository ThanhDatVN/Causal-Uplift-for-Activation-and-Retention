# R00 / R01 — exact identities and evaluator validation

Run 2026-09-21T10:23:17+00:00 · 2,000 worlds per scenario · seed 20260925 · 3082 s.

- status: **PASS**
- R00 identities: all pass
- coverage failures: 0
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
| V01 | ipw | primary | 0.00000 | +0.000032 | 0.000307 | 0.952 | [0.942, 0.961] | 0.05422 | 1.007 | -0.00 | 0.024 |
| V01 | dr_correct | primary | 0.00000 | +0.000070 | 0.000067 | 0.941 | [0.929, 0.950] | 0.01140 | 0.975 | 0.01 | 0.033 |
| V01 | dr_misspecified | primary | 0.00000 | +0.000069 | 0.000067 | 0.939 | [0.928, 0.949] | 0.01142 | 0.976 | 0.01 | 0.034 |
| V02 | ipw | primary | 0.00250 | +0.000099 | 0.000306 | 0.955 | [0.945, 0.963] | 0.05429 | 1.012 | -0.00 | 0.035 |
| V02 | dr_correct | primary | 0.00250 | -0.000017 | 0.000063 | 0.946 | [0.935, 0.955] | 0.01108 | 0.999 | 0.36 | 0.138 |
| V02 | dr_misspecified | primary | 0.00250 | -0.000018 | 0.000063 | 0.947 | [0.936, 0.956] | 0.01109 | 0.998 | 0.37 | 0.136 |
| V03 | ipw | primary | 0.00500 | +0.000205 | 0.000311 | 0.950 | [0.940, 0.959] | 0.05436 | 0.998 | -0.00 | 0.053 |
| V03 | dr_correct | primary | 0.00500 | +0.000092 | 0.000060 | 0.953 | [0.942, 0.961] | 0.01078 | 1.029 | 0.82 | 0.463 |
| V03 | dr_misspecified | primary | 0.00500 | +0.000092 | 0.000060 | 0.951 | [0.941, 0.960] | 0.01078 | 1.029 | 0.83 | 0.464 |
| V04 | ipw | primary | 0.00500 | +0.000109 | 0.000383 | 0.951 | [0.941, 0.960] | 0.06784 | 1.010 | -2.17 | 0.043 |
| V04 | dr_correct | primary | 0.00500 | +0.000013 | 0.000081 | 0.943 | [0.932, 0.952] | 0.01400 | 0.985 | 10.24 | 0.322 |
| V04 | dr_misspecified | primary | 0.00500 | +0.000017 | 0.000081 | 0.944 | [0.933, 0.953] | 0.01403 | 0.987 | 10.59 | 0.321 |
| V04 | wrong_propensity | ipw_constant_propensity_negative_control | 0.00500 | +0.576621 | 0.000188 | 0.000 | [0.000, 0.002] | 0.04943 | 1.503 | -0.32 | 1.000 |
| V04 | wrong_propensity | dr_constant_propensity_negative_control | 0.00500 | +0.000008 | 0.000060 | 0.948 | [0.937, 0.957] | 0.01032 | 0.982 | -3.62 | 0.479 |
| V05 | ipw | primary | 0.00025 | +0.000580 | 0.000523 | 0.952 | [0.942, 0.961] | 0.09213 | 1.005 | -3.79 | 0.027 |
| V05 | dr_correct | primary | 0.00025 | -0.000028 | 0.000040 | 0.944 | [0.933, 0.953] | 0.00846 | 1.191 | 46.21 | 0.035 |
| V05 | dr_misspecified | primary | 0.00025 | -0.000029 | 0.000041 | 0.945 | [0.934, 0.954] | 0.00847 | 1.192 | 46.39 | 0.036 |
| V05B | ipw | primary | 0.00025 | -0.000064 | 0.000318 | 0.949 | [0.938, 0.958] | 0.05527 | 0.990 | -0.00 | 0.028 |
| V05B | dr_correct | primary | 0.00025 | -0.000038 | 0.000024 | 0.951 | [0.940, 0.959] | 0.00442 | 1.042 | 0.61 | 0.036 |
| V05B | dr_misspecified | primary | 0.00025 | -0.000038 | 0.000024 | 0.952 | [0.941, 0.960] | 0.00442 | 1.041 | 0.62 | 0.035 |
| V06 | ipw | cluster_robust | 0.00000 | -0.000013 | 0.000488 | 0.947 | [0.936, 0.956] | 0.08531 | 0.996 | 0.00 | 0.027 |
| V06 | ipw | iid_negative_control | 0.00000 | -0.000013 | 0.000488 | 0.800 | [0.782, 0.817] | 0.05421 | 0.633 | 0.00 | 0.101 |
| V06 | dr_correct | cluster_robust | 0.00000 | +0.000081 | 0.000099 | 0.942 | [0.931, 0.951] | 0.01753 | 1.009 | 0.01 | 0.028 |
| V06 | dr_correct | iid_negative_control | 0.00000 | +0.000081 | 0.000099 | 0.803 | [0.786, 0.820] | 0.01141 | 0.656 | 0.01 | 0.096 |
| V06 | dr_misspecified | cluster_robust | 0.00000 | +0.000083 | 0.000099 | 0.944 | [0.933, 0.953] | 0.01755 | 1.009 | 0.01 | 0.026 |
| V06 | dr_misspecified | iid_negative_control | 0.00000 | +0.000083 | 0.000099 | 0.803 | [0.786, 0.820] | 0.01142 | 0.657 | 0.01 | 0.095 |
| B01 | ipw | primary | 0.00100 | -0.000123 | 0.000301 | 0.953 | [0.943, 0.961] | 0.05423 | 1.027 | -0.00 | 0.025 |
| B01 | dr_correct | primary | 0.00100 | -0.000056 | 0.000064 | 0.954 | [0.943, 0.962] | 0.01127 | 1.012 | 0.13 | 0.051 |
| B01 | dr_misspecified | primary | 0.00100 | -0.000056 | 0.000064 | 0.953 | [0.942, 0.961] | 0.01128 | 1.012 | 0.13 | 0.050 |
| V07 | ipw | primary | 0.02500 | +0.000032 | 0.000461 | 0.944 | [0.933, 0.953] | 0.07942 | 0.982 | -0.08 | 0.249 |
| V07 | dr_correct | primary | 0.02500 | -0.000000 | 0.000314 | 0.955 | [0.945, 0.963] | 0.05559 | 1.011 | -0.15 | 0.423 |
| V07 | dr_misspecified | primary | 0.02500 | +0.000004 | 0.000314 | 0.957 | [0.947, 0.965] | 0.05562 | 1.011 | -0.15 | 0.426 |

## Not run

- **V08_batch_cap** — blocked on G06: the batch-policy interval has no validated domain yet, so there is nothing to score it against
- **V09_two_stage_recruitment** — runs separately once the recruitment estimator has a declared target; the variance decomposition exists but its gate does not
