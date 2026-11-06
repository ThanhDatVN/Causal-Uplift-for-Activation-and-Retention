# Frozen second-family evaluator protocol

**Registered:** 29 September 2026, before generating F04–F06 results. The F01–F03 smooth-family outcomes were already inspected. This is an additional prospective stress test, not a claim that the whole research program was chosen without looking at prior results.

## Generator and estimand

Each world draws 4,000 independent units with `X ~ Uniform(-1, 1)`. Baseline churn is piecewise: `0.003` for `X < -0.3`, `0.008` for `-0.3 <= X < 0.3`, `0.025` for `0.3 <= X < 0.75`, and `0.060` otherwise. The policy contacts units with `X > 0`; the comparator contacts nobody. The reward is `1 - churn`, and the truth is the realized-frame mean of `effect(X) * 1{X > 0}`.

The heterogeneous effect is **harmful** (`-0.003` prevented churn) for `0 < X < 0.5` and beneficial (`+0.008`) for `X >= 0.5`; it is zero for `X <= 0`. Observed churn is Bernoulli with probability `baseline_churn - treatment * effect(X)`. The null version sets the effect to zero everywhere. This family differs from F01–F03's smooth logistic baseline and smooth positive effect; it tests a policy that contacts both harmful and beneficial subgroups.

| ID | Effect | Assignment probability |
|---|---|---|
| F04 | Sharp null | `0.12` when `X < 0`, `0.88` otherwise |
| F05 | Piecewise harm/benefit | Constant `0.85` |
| F06 | Piecewise harm/benefit | `0.12` when `X < 0`, `0.88` otherwise |

The evaluator uses the logged assignment probabilities, analytic conditional means, production DR scores, and the existing paired-contrast implementation. Primary interval: `skewness_adjusted_t` with effective degree-of-freedom floor `1`. Reference: ordinary normal DR. No model fitting or hyperparameter search enters this protocol. The new RNG namespace is keyed by scenario ID, with base seed `40637`; each world index gets an independent seed sequence. Compute: 2,000 worlds per scenario. The code and report retain this specification and seed.

## Acceptance and reporting

For each of the six scenarios F01–F06, calculate empirical coverage against finite-frame truth and its two-sided 95% Wilson interval. The selected interval clears the **cellwise** rule if the Wilson lower bound is at least `0.92`. On the two sharp-null scenarios F01 and F04, false promotion means the selected interval's lower endpoint exceeds zero; its Wilson upper bound must be at most `0.05`.

Also calculate a conservative **family false-failure upper bound** under an ideal 95% covering interval with a nominal 2.5% one-sided null false-promotion rate. Use the exact binomial probability that one coverage readout fails its Wilson rule, times six, plus the corresponding one-null-promotion failure probability times two (union bound). This calibration must be at most `0.05`; with 2,000 worlds, the pre-run calculation is approximately `0.00112`. This calibrates false *gate failure* under ideal behavior, not probability of a false business launch. Report all normal-reference readouts and all negative results.

Even if these criteria pass, label the run `DIAGNOSTIC` and leave the release tier unchanged. It does not validate clustered interference, repeated actions, cost uncertainty, batch-resampled allocation, or the full prior licensed region, and the interval had been chosen after earlier results.
