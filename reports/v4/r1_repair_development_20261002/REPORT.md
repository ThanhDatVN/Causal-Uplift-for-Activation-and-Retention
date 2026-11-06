# R1 evaluator repair: unseen synthetic validation

**Status:** `DEVELOPMENT_DIAGNOSTIC`. No real-data or causal promotion.

| Cell | Truth | Coverage | Wilson lower | Null promotion upper | Mean width | Failures |
|---|---:|---:|---:|---:|---:|---:|
| F1_fixed_null | +0.000000 | 0.780 | 0.689 | 0.054 | 0.013953 | 0 |
| F2_fixed_rare | +0.000189 | 0.950 | 0.888 | 0.054 | 0.006103 | 0 |
| B1_batch_null | +0.000000 | 0.600 | 0.502 | 0.070 | 0.015481 | 0 |
| B2_batch_rare | +0.000189 | 0.700 | 0.604 | 0.162 | 0.014356 | 0 |
| C1_cluster_null | +0.000000 | 0.920 | 0.850 | 0.098 | 0.010351 | 0 |
| C2_cluster_effect | +0.000540 | 0.880 | 0.802 | 0.137 | 0.009758 | 0 |

The fixed-rule candidate uses the production paired DR normal interval. The batch candidate resamples whole customers, reallocates the top 20% on every bootstrap draw, and studentizes by the selected-contribution standard error. C1 also compares customer and deliberately invalid row-IID normal intervals for one frozen unique-customer decision set.

Each cell has a closed-form or exact binomial truth. Failed intervals count against coverage. This report is a synthetic method check, not evidence of real campaign benefit or a reason to open the Hillstrom confirmation split.
