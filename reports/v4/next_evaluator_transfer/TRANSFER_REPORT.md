# R1 next evaluator transfer - development diagnostic

**Status:** `UNVALIDATED_DIAGNOSTIC`. Causal promotion: **no**. The batch and cluster bootstrap is a new candidate, not an already licensed method.

The fixed-rule T1/T2 results target population reward contrast and use oracle nuisance means and logged assignment probabilities. All outcomes are generated. The chosen interval had been selected after earlier work; this run cannot turn it into an independently licensed real-data evaluator.

| Cell | Method | Truth | Bias | Coverage | Wilson lower | Null promotion (Wilson upper) | Mean width | MCSE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | selected_dr | +0.000000 | -0.000006 | 0.937 | 0.925 | 0.032 (0.040) | 0.009148 | 0 |
| T1 | normal_dr_reference | +0.000000 | -0.000006 | 0.950 | 0.940 | 0.018 (0.025) | 0.008838 | 0 |
| T2 | selected_dr | +0.000188 | +0.000020 | 0.882 | 0.867 | 0.059 (0.071) | 0.005082 | 0 |
| T2 | normal_dr_reference | +0.000188 | +0.000020 | 0.941 | 0.930 | 0.015 (0.022) | 0.004242 | 0 |
| T3 | batch_reallocation_candidate | +0.000000 | +0.000090 | 0.907 | 0.893 | 0.009 (0.014) | 0.010696 | 0 |
| T3 | selected_fixed_interval_out_of_domain | +0.000000 | +0.000090 | 0.894 | 0.880 | 0.028 (0.036) | 0.012845 | 0 |
| T4 | batch_reallocation_candidate | +0.000150 | +0.000004 | 0.828 | 0.810 | 0.035 (0.043) | 0.003796 | 1.2e-08 |
| T5 | batch_reallocation_candidate | +0.000000 | -0.000042 | 0.943 | 0.932 | 0.027 (0.035) | 0.007850 | 0 |
| T6 | batch_reallocation_candidate | +0.000600 | -0.000058 | 0.950 | 0.939 | 0.045 (0.056) | 0.007609 | 7.1e-08 |

## Method and scope

The current `batch_policy_contrast` fills the cap for both policies. This runner instead compares a capped policy against no-contact. It resamples customers and recalculates top-K within each draw; T5/T6 aggregate two records before scoring and bootstrap whole customers. The interval is percentile bootstrap. Its support and coverage must be validated for this DGP; an old V08 pass cannot be transferred by name.

The dry-run manifest and machine-readable results record all six cell statuses. The declared wrong-propensity, row-IID-cluster, and outcome-leakage negative controls remain to be executed. Until then the full protocol is incomplete even if every coverage gate passes. No uplift or ROI claim follows from this synthetic diagnostic.
