# R1 evaluator repair: unseen synthetic validation

**Status:** `SYNTHETIC_GATE_FAILED`. No real-data or causal promotion.

| Cell | Truth | Candidate coverage | Wilson lower | Old-method coverage | Bounded coverage | Bounded half-width / 1k | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| F1_fixed_null | +0.000000 | 0.755 | 0.736 | 0.680 | 1.000 | 465.6 | 0 |
| F2_fixed_rare | +0.000189 | 0.956 | 0.946 | 0.891 | 1.000 | 240.3 | 0 |
| B1_batch_null | +0.000000 | 0.683 | 0.663 | 0.726 | 1.000 | 465.6 | 0 |
| B2_batch_rare | +0.000189 | 0.758 | 0.739 | 0.791 | 1.000 | 240.3 | 0 |
| C1_cluster_null | +0.000000 | 0.892 | 0.878 | 0.930 | 1.000 | 182.2 | 0 |
| C2_cluster_effect | +0.000540 | 0.893 | 0.879 | 0.934 | 1.000 | 182.2 | 0 |

The fixed-rule candidate uses the production paired DR normal interval. The batch candidate resamples whole customers, reallocates the top 20% on every bootstrap draw, and studentizes by the selected-contribution standard error. C1 also compares customer and deliberately invalid row-IID normal intervals for one frozen unique-customer decision set.

Cluster control: customer coverage 0.955; invalid row-IID coverage 0.844; declared discrimination gate `True`.

The bounded-difference reference is conservative under this oracle synthetic design and is reported with its very large half-width. Its coverage is not a usable campaign decision interval or an alternative promotion path.

Each cell has a closed-form or exact binomial truth. Failed intervals count against coverage. This report is a synthetic method check, not evidence of real campaign benefit or a reason to open the Hillstrom confirmation split.
