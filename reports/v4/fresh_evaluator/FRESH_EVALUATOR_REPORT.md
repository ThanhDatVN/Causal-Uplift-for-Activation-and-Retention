# Fresh-family evaluator diagnostic

> **Current tier note:** This report's run-time decision to keep tier `NONE` preceded the later repair of the local research dependency lock. The refreshed [evidence index](../EVIDENCE_INDEX.md) computes `ENGINEERING_FOUNDATION` from engineering gates; independent causal evaluator confirmation remains `NOT_MET`. The results below are still diagnostic.

**Run date:** 29 September 2026  
**Command:** `python -m telco_churn.fresh_evaluator --worlds 2000 --n-units 4000 --output-dir reports/v4/fresh_evaluator`  
**Machine-readable result:** [FRESH_EVALUATOR.json](FRESH_EVALUATOR.json)

The run now covers two generated binary-outcome families with independent random seeds: a smooth logistic family (F01–F03) and a preregistered piecewise family with a harmful-treatment subgroup (F04–F06; see [protocol](../../../docs/EVALUATOR_FAMILY2_PROTOCOL_EN.md)). It uses the same production DR score and paired-contrast code as the benchmark. The interval was **already selected after earlier results**: `skewness_adjusted_t`, effective degree-of-freedom floor `1`. The normal DR interval is a reference only. No model learner, campaign, or business effect was trained or measured in this run.

| Scenario | Assignment and effect | Selected DR coverage | 95% Wilson interval for coverage | Normal DR coverage | Selected DR false promotion |
|---|---|---:|---:|---:|---:|
| F01 | Constant `e=0.85`, true null | 0.948 | [0.937, 0.956] | 0.938 | 0.025; Wilson upper 0.033 |
| F02 | Constant `e=0.85`, heterogeneous benefit | 0.955 | [0.945, 0.963] | 0.941 | Not a null test |
| F03 | Covariate-dependent `e(X)` bounded in (0.1, 0.9), heterogeneous benefit | 0.951 | [0.940, 0.959] | 0.949 | Not a null test |
| F04 | Piecewise risk, sharp null, stratified `e=0.12/0.88` | 0.954 | [0.943, 0.962] | 0.933 | 0.024; Wilson upper 0.031 |
| F05 | Piecewise harm/benefit, constant `e=0.85` | 0.944 | [0.933, 0.953] | 0.923 | Not a null test |
| F06 | Piecewise harm/benefit, stratified `e=0.12/0.88` | 0.957 | [0.947, 0.965] | 0.928 | Not a null test |

**Interpretation.** The selected interval clears the existing cellwise Wilson coverage floor of `0.92` in all six conditions. Both null false-promotion Wilson upper bounds are below `0.05`. The normal reference's Wilson lower coverage bounds fall below `0.92` in F05 and F06; this supports the selected method for these constructed conditions, not universal superiority. The preregistered family false-failure **upper bound is 0.001119** under ideal 95% coverage and 2.5% one-sided null promotion, below the proposed `0.05` calibration limit. This controls the chance of rejecting an ideal evaluator because of Monte Carlo noise in these eight gate readouts; it is not a bound on false business launch or a validation of every prior design.

**Decision.** Keep release tier `NONE` and the Hillstrom confirmation split closed. The [evidence index](../EVIDENCE_INDEX.md) still requires independent validation of the full licensed region and a selection-safe confirmation procedure. Next, test a declared batch-cap/clustered design and reconcile this diagnostic with the existing evidence gate. Do not alter this result after inspecting it and call the revision independent confirmation.

**Compute.** CPU only. The generator creates all data in memory; no raw dataset or GPU is needed. A quick syntax and integration check is `python -m telco_churn.fresh_evaluator --worlds 100 --output-dir reports/v4/fresh_evaluator_smoke`, which reports `SMOKE_ONLY` and cannot promote evidence.
