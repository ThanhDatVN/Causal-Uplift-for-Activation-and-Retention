# Orange assignment-integrity audit

Resolves, within the sources that can be checked from the repository, the question left open by finding F01 of the V3 review: is the pooled treatment indicator predictable from the supplied pre-treatment covariates?

- rows: 11,896, features: 178, treatment share: 75.7397%
- cross-fitted out-of-fold ROC-AUC: **0.6355**
- out-of-fold log loss 0.5500 versus 0.5541 for a constant propensity (improvement 0.0041)
- Brier skill against the constant propensity: 0.0222
- permutation null (100 refits): mean AUC 0.5003, 95th percentile 0.5143
- permutations at or above the observed AUC: 0; add-one p-value **0.009901**

## Positivity and support

Estimated `e(X)` spans [0.0000, 1.0000] with median 0.7722.

| Minimum action propensity | Units outside support | Share |
|---|---:|---:|
| 0.025 | 16 | 0.13% |
| 0.050 | 38 | 0.32% |
| 0.100 | 190 | 1.60% |

Inverse-probability effective sample size: 4 with the estimated propensity against 8,743 with the constant one. Effective sample size is not a substitute for the number of churn events or the number of independent clusters.

**Reweighting by the estimated propensity leaves an effective sample size of 4 out of 8,743. A handful of extreme weights would carry the whole estimate, so estimating e(X) is not a repair for the identification problem here; it relocates it into the variance.**

## Verdict

- out-of-fold treatment ROC-AUC 0.6355, permutation p = 0.009901
- pooled-IID exchangeability rejected at alpha 0.05: **True**
- evidence state: EXPLORATORY
- decision: Keep the dataset as a conditional benchmark. Do not promote a causal claim from a constant propensity; report IPW and DR results as sensitivity analyses under stated identification assumptions.

## What this cannot settle

- Diagnostic on a pooled frame. Campaign and customer identifiers are absent, so campaign-level variation in treatment rates, post-randomization preselection, a non-pre-treatment covariate and non-uniform assignment are not distinguishable here.
- The permutation null assumes exchangeable rows. Repeated customers would break it, and the file does not let that be checked.
- An estimated propensity strictly inside (0, 1) does not demonstrate positivity or ignorability; it is a fitted value, not a design probability.
- Rejecting the pooled-IID null does not certify any particular alternative, and does not show the dataset paper's per-campaign randomization was wrong.