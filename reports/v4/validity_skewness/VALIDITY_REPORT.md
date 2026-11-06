# R00 / R01 — exact identities and evaluator validation

Run 2026-09-21T06:39:17+00:00 · 1,000 worlds per scenario · seed 20260921 · 916 s.

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
| V01 | ipw | primary | 0.00000 | -0.000619 | 0.000443 | 0.950 | [0.935, 0.962] | 0.05420 | 0.986 | 0.00 | 0.026 |
| V01 | dr_correct | primary | 0.00000 | -0.000116 | 0.000092 | 0.947 | [0.931, 0.959] | 0.01136 | 0.999 | -0.01 | 0.023 |
| V01 | dr_misspecified | primary | 0.00000 | -0.000113 | 0.000092 | 0.950 | [0.935, 0.962] | 0.01138 | 0.997 | -0.01 | 0.023 |
| V02 | ipw | primary | 0.00250 | +0.000047 | 0.000444 | 0.943 | [0.927, 0.956] | 0.05427 | 0.986 | -0.00 | 0.045 |
| V02 | dr_correct | primary | 0.00250 | +0.000042 | 0.000089 | 0.951 | [0.936, 0.963] | 0.01107 | 1.008 | 0.37 | 0.147 |
| V02 | dr_misspecified | primary | 0.00250 | +0.000042 | 0.000089 | 0.950 | [0.935, 0.962] | 0.01109 | 1.007 | 0.38 | 0.148 |
| V03 | ipw | primary | 0.00500 | +0.000424 | 0.000437 | 0.953 | [0.938, 0.964] | 0.05434 | 1.004 | -0.00 | 0.059 |
| V03 | dr_correct | primary | 0.00500 | +0.000015 | 0.000084 | 0.949 | [0.934, 0.961] | 0.01073 | 1.030 | 0.81 | 0.456 |
| V03 | dr_misspecified | primary | 0.00500 | +0.000012 | 0.000084 | 0.951 | [0.936, 0.963] | 0.01074 | 1.028 | 0.82 | 0.451 |
| V04 | ipw | primary | 0.00500 | +0.000664 | 0.000543 | 0.953 | [0.938, 0.964] | 0.06781 | 1.008 | -2.17 | 0.054 |
| V04 | dr_correct | primary | 0.00500 | +0.000082 | 0.000118 | 0.933 | [0.916, 0.947] | 0.01390 | 0.949 | 10.22 | 0.339 |
| V04 | dr_misspecified | primary | 0.00500 | +0.000073 | 0.000118 | 0.934 | [0.917, 0.948] | 0.01393 | 0.949 | 10.57 | 0.337 |
| V04 | wrong_propensity | ipw_constant_propensity_negative_control | 0.00500 | +0.576629 | 0.000258 | 0.000 | [0.000, 0.004] | 0.04942 | 1.544 | -0.32 | 1.000 |
| V04 | wrong_propensity | dr_constant_propensity_negative_control | 0.00500 | -0.000016 | 0.000086 | 0.954 | [0.939, 0.965] | 0.01034 | 0.973 | -3.60 | 0.474 |
| V05 | ipw | primary | 0.00025 | +0.000738 | 0.000760 | 0.947 | [0.931, 0.959] | 0.09204 | 0.977 | -3.79 | 0.028 |
| V05 | dr_correct | primary | 0.00025 | -0.000046 | 0.000059 | 0.923 | [0.905, 0.938] | 0.00701 | 0.961 | 44.92 | 0.038 |
| V05 | dr_misspecified | primary | 0.00025 | -0.000046 | 0.000059 | 0.923 | [0.905, 0.938] | 0.00701 | 0.959 | 45.08 | 0.038 |
| V06 | ipw | cluster_robust | 0.00000 | +0.000105 | 0.000657 | 0.959 | [0.945, 0.970] | 0.08528 | 1.048 | -0.00 | 0.019 |
| V06 | ipw | iid_negative_control | 0.00000 | +0.000105 | 0.000657 | 0.807 | [0.781, 0.830] | 0.05420 | 0.666 | -0.00 | 0.102 |
| V06 | dr_correct | cluster_robust | 0.00000 | +0.000054 | 0.000142 | 0.944 | [0.928, 0.957] | 0.01751 | 0.992 | 0.01 | 0.026 |
| V06 | dr_correct | iid_negative_control | 0.00000 | +0.000054 | 0.000142 | 0.788 | [0.762, 0.812] | 0.01136 | 0.644 | 0.01 | 0.109 |
| V06 | dr_misspecified | cluster_robust | 0.00000 | +0.000060 | 0.000143 | 0.944 | [0.928, 0.957] | 0.01752 | 0.989 | 0.01 | 0.025 |
| V06 | dr_misspecified | iid_negative_control | 0.00000 | +0.000060 | 0.000143 | 0.784 | [0.757, 0.808] | 0.01137 | 0.642 | 0.01 | 0.110 |
| B01 | ipw | primary | 0.00100 | -0.000125 | 0.000452 | 0.945 | [0.929, 0.958] | 0.05422 | 0.969 | -0.00 | 0.037 |
| B01 | dr_correct | primary | 0.00100 | +0.000004 | 0.000090 | 0.957 | [0.943, 0.968] | 0.01124 | 1.011 | 0.14 | 0.052 |
| B01 | dr_misspecified | primary | 0.00100 | +0.000001 | 0.000090 | 0.956 | [0.941, 0.967] | 0.01125 | 1.011 | 0.14 | 0.055 |
| V07 | ipw | primary | 0.02500 | +0.000378 | 0.000633 | 0.961 | [0.947, 0.971] | 0.07925 | 1.010 | 0.13 | 0.243 |
| V07 | dr_correct | primary | 0.02500 | +0.000198 | 0.000456 | 0.933 | [0.916, 0.947] | 0.05520 | 0.977 | 0.27 | 0.436 |
| V07 | dr_misspecified | primary | 0.02500 | +0.000198 | 0.000455 | 0.935 | [0.918, 0.949] | 0.05522 | 0.979 | 0.27 | 0.436 |

## Not run

- **V08_batch_cap** — blocked on G06: the batch-policy interval has no validated domain yet, so there is nothing to score it against
- **V09_two_stage_recruitment** — runs separately once the recruitment estimator has a declared target; the variance decomposition exists but its gate does not
