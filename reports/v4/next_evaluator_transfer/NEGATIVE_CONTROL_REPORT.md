# R1 negative controls - separate synthetic suite

**Status:** negative controls only; no method promotion. The suite uses 500 worlds per stochastic control, 4,000 rows, and 300 bootstrap resamples.

Wrong logged propensity: **REJECTED_BY_CONTROL_HARNESS**. The check is inside this harness; the production score API cannot verify a self-declared design probability against an external assignment log.

Outcome-derived ranking provenance: **REJECTED_BY_CONTROL_HARNESS**. The forbidden rank is evaluated below only to expose its statistical failure.

| Control | Coverage | Wilson lower | Positive lower bound | Wilson upper | Mean bias | Mean width |
|---|---:|---:|---:|---:|---:|---:|
| T5_customer_cluster_bootstrap | 0.948 | 0.925 | 0.032 | 0.051 | -0.000013 | 0.007743 |
| T5_invalid_row_iid_bootstrap | 0.946 | 0.923 | 0.032 | 0.051 | -0.000013 | 0.007745 |
| T3_clean_feature_rank | 0.916 | 0.888 | 0.010 | 0.023 | +0.000093 | 0.010702 |
| T3_forbidden_outcome_rank | 0.000 | 0.000 | 1.000 | 1.000 | +0.019665 | 0.018443 |

The row-IID bootstrap deliberately treats correlated records as independent. The customer bootstrap resamples the actual decision units. Both use the same null generator; their comparison is a diagnostic, not another candidate-search round. The outcome-rank control reads the evaluation scores when choosing contacts, violating the pre-treatment policy contract.
