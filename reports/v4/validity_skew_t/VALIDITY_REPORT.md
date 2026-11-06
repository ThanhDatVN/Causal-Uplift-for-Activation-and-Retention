# R00 / R01 — exact identities and evaluator validation

Run 2026-09-21T07:27:32+00:00 · 1,000 worlds per scenario · seed 20260922 · 1225 s.

- status: **FAIL**
- R00 identities: all pass
- coverage failures: 4
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
| V01 | ipw | primary | 0.00000 | +0.000624 | 0.000432 | 0.951 | [0.936, 0.963] | 0.05420 | 1.013 | -0.00 | 0.029 |
| V01 | dr_correct | primary | 0.00000 | -0.000189 | 0.000092 | 0.945 | [0.929, 0.958] | 0.01139 | 0.999 | -0.03 | 0.022 |
| V01 | dr_misspecified | primary | 0.00000 | -0.000195 | 0.000092 | 0.945 | [0.929, 0.958] | 0.01141 | 0.999 | -0.03 | 0.022 |
| V02 | ipw | primary | 0.00250 | -0.000825 | 0.000444 | 0.942 | [0.926, 0.955] | 0.05428 | 0.986 | -0.00 | 0.034 |
| V02 | dr_correct | primary | 0.00250 | +0.000049 | 0.000086 | 0.959 | [0.945, 0.970] | 0.01106 | 1.035 | 0.38 | 0.138 |
| V02 | dr_misspecified | primary | 0.00250 | +0.000056 | 0.000087 | 0.959 | [0.945, 0.970] | 0.01107 | 1.032 | 0.39 | 0.136 |
| V03 | ipw | primary | 0.00500 | +0.000193 | 0.000429 | 0.951 | [0.936, 0.963] | 0.05433 | 1.023 | -0.00 | 0.062 |
| V03 | dr_correct | primary | 0.00500 | -0.000155 | 0.000086 | 0.943 | [0.927, 0.956] | 0.01075 | 1.013 | 0.79 | 0.433 |
| V03 | dr_misspecified | primary | 0.00500 | -0.000158 | 0.000086 | 0.945 | [0.929, 0.958] | 0.01076 | 1.012 | 0.79 | 0.431 |
| V04 | ipw | primary | 0.00500 | -0.000200 | 0.000549 | 0.953 | [0.938, 0.964] | 0.06787 | 0.997 | -2.17 | 0.046 |
| V04 | dr_correct | primary | 0.00500 | +0.000119 | 0.000116 | 0.942 | [0.926, 0.955] | 0.01401 | 0.978 | 10.25 | 0.344 |
| V04 | dr_misspecified | primary | 0.00500 | +0.000119 | 0.000115 | 0.946 | [0.930, 0.958] | 0.01404 | 0.983 | 10.60 | 0.336 |
| V04 | wrong_propensity | ipw_constant_propensity_negative_control | 0.00500 | +0.576604 | 0.000256 | 0.000 | [0.000, 0.004] | 0.04944 | 1.561 | -0.32 | 1.000 |
| V04 | wrong_propensity | dr_constant_propensity_negative_control | 0.00500 | +0.000138 | 0.000084 | 0.943 | [0.927, 0.956] | 0.01031 | 0.995 | -3.61 | 0.489 |
| V05 | ipw | primary | 0.00025 | -0.000282 | 0.000767 | 0.951 | [0.936, 0.963] | 0.09218 | 0.970 | -3.79 | 0.022 |
| V05 | dr_correct | primary | 0.00025 | +0.000050 | 0.000060 | 0.931 | [0.914, 0.945] | 0.00744 | 0.999 | 46.10 | 0.043 |
| V05 | dr_misspecified | primary | 0.00025 | +0.000047 | 0.000060 | 0.932 | [0.915, 0.946] | 0.00744 | 0.998 | 46.29 | 0.047 |
| V06 | ipw | cluster_robust | 0.00000 | +0.001446 | 0.000692 | 0.946 | [0.930, 0.958] | 0.08527 | 0.995 | -0.00 | 0.031 |
| V06 | ipw | iid_negative_control | 0.00000 | +0.001446 | 0.000692 | 0.801 | [0.775, 0.825] | 0.05419 | 0.632 | -0.00 | 0.115 |
| V06 | dr_correct | cluster_robust | 0.00000 | -0.000284 | 0.000141 | 0.939 | [0.922, 0.952] | 0.01754 | 1.003 | -0.05 | 0.030 |
| V06 | dr_correct | iid_negative_control | 0.00000 | -0.000284 | 0.000141 | 0.794 | [0.768, 0.818] | 0.01142 | 0.653 | -0.05 | 0.098 |
| V06 | dr_misspecified | cluster_robust | 0.00000 | -0.000304 | 0.000142 | 0.939 | [0.922, 0.952] | 0.01756 | 1.001 | -0.05 | 0.033 |
| V06 | dr_misspecified | iid_negative_control | 0.00000 | -0.000304 | 0.000142 | 0.798 | [0.772, 0.822] | 0.01144 | 0.652 | -0.05 | 0.095 |
| B01 | ipw | primary | 0.00100 | -0.000108 | 0.000420 | 0.961 | [0.947, 0.971] | 0.05424 | 1.041 | -0.00 | 0.026 |
| B01 | dr_correct | primary | 0.00100 | -0.000032 | 0.000095 | 0.938 | [0.921, 0.951] | 0.01128 | 0.960 | 0.14 | 0.058 |
| B01 | dr_misspecified | primary | 0.00100 | -0.000031 | 0.000095 | 0.935 | [0.918, 0.949] | 0.01130 | 0.958 | 0.14 | 0.062 |
| V07 | ipw | primary | 0.02500 | +0.000239 | 0.000660 | 0.935 | [0.918, 0.949] | 0.07968 | 0.974 | 0.13 | 0.244 |
| V07 | dr_correct | primary | 0.02500 | -0.000076 | 0.000451 | 0.941 | [0.925, 0.954] | 0.05577 | 0.998 | 0.21 | 0.417 |
| V07 | dr_misspecified | primary | 0.02500 | -0.000073 | 0.000451 | 0.941 | [0.925, 0.954] | 0.05579 | 0.998 | 0.21 | 0.414 |

## Not run

- **V08_batch_cap** — blocked on G06: the batch-policy interval has no validated domain yet, so there is nothing to score it against
- **V09_two_stage_recruitment** — runs separately once the recruitment estimator has a declared target; the variance decomposition exists but its gate does not
