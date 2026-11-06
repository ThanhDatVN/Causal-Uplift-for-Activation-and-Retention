# Orange assignment-integrity audit

Resolves, within the sources that can be checked from the repository, the question left open by finding F01 of the V3 review: is the pooled treatment indicator predictable from the supplied pre-treatment covariates?

- rows: 42,613, features: 8, treatment share: 50.0012%
- cross-fitted out-of-fold ROC-AUC: **0.4975**
- out-of-fold log loss 0.6935 versus 0.6931 for a constant propensity (improvement -0.0003)
- Brier skill against the constant propensity: -0.0007
- permutation null (100 refits): mean AUC 0.4995, 95th percentile 0.5067
- permutations at or above the observed AUC: 68; add-one p-value **0.6832**

## Positivity and support

Estimated `e(X)` spans [0.4670, 0.5553] with median 0.4997.

| Minimum action propensity | Units outside support | Share |
|---|---:|---:|
| 0.025 | 0 | 0.00% |
| 0.050 | 0 | 0.00% |
| 0.100 | 0 | 0.00% |

Inverse-probability effective sample size: 42,592 with the estimated propensity against 42,613 with the constant one. Effective sample size is not a substitute for the number of churn events or the number of independent clusters.

**Reweighting by the estimated propensity retains a usable effective sample size, but positivity and ignorability remain assumptions.**

## Verdict

- out-of-fold treatment ROC-AUC 0.4975, permutation p = 0.6832
- pooled-IID exchangeability rejected at alpha 0.05: **False**
- evidence state: EXPLORATORY
- decision: No pooled dependence detected at this sample size; a constant propensity remains an assumption, not a verified design probability.

## What this cannot settle

- Diagnostic on a pooled frame. Campaign and customer identifiers are absent, so campaign-level variation in treatment rates, post-randomization preselection, a non-pre-treatment covariate and non-uniform assignment are not distinguishable here.
- The permutation null assumes exchangeable rows. Repeated customers would break it, and the file does not let that be checked.
- An estimated propensity strictly inside (0, 1) does not demonstrate positivity or ignorability; it is a fitted value, not a design probability.
- Rejecting the pooled-IID null does not certify any particular alternative, and does not show the dataset paper's per-campaign randomization was wrong.