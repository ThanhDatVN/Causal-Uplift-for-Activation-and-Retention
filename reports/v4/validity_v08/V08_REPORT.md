# V08 — inference for a capped batch policy

500 worlds per regime · N = 3,000 · cap 600 (20%) · 600 resamples · 1419 s

**PASS**

One mechanism, one cap, one balanced design. This scores the capped batch interval's coverage; it says nothing about capped inference under an imbalanced design, which the asymmetry index governs separately.

A capped policy re-allocates when the batch changes, so the contrast carries variation a fixed policy does not. Whether that variation is *material* depends on the regime, and the scenario runs one either side of the line rather than assuming it.

## noisy_outcome (reward noise 0.25)

Superpopulation truth 0.15930 (± 0.00040 Monte Carlo on a 400,000-row reference frame). The finite truth moves 0.00461 between batches.

| readout | target | scored against | coverage | width | materiality | |
|---|---|---|---|---|---|---|
| `future_vs_super` | future_batch | superpopulation | 0.946 [0.923, 0.963] | 0.02704 | 0.34 |  |
| `finite_vs_finite` | finite_batch | finite_frame | 0.946 [0.923, 0.963] | 0.02024 | 0.46 |  |
| `finite_vs_super` | finite_batch | superpopulation | 0.848 [0.814, 0.877] | 0.02024 | 0.46 | nothing to detect |

## predictable_outcome (reward noise 0.04)

Superpopulation truth 0.15930 (± 0.00040 Monte Carlo on a 400,000-row reference frame). The finite truth moves 0.00412 between batches.

| readout | target | scored against | coverage | width | materiality | |
|---|---|---|---|---|---|---|
| `future_vs_super` | future_batch | superpopulation | 0.964 [0.944, 0.977] | 0.01812 | 0.45 |  |
| `finite_vs_finite` | finite_batch | finite_frame | 0.960 [0.939, 0.974] | 0.00324 | 2.55 |  |
| `finite_vs_super` | finite_batch | superpopulation | 0.302 [0.263, 0.344] | 0.00324 | 2.55 | **fired** |

## Reading the control

`finite_vs_super` is a **declared negative control**: the narrow, batch-conditional interval reported as though it were a forward-looking guarantee. It is never gated on directly.

**Materiality** is how far the truth moves between batches, over the mean interval half-width. Below 1 the two targets are indistinguishable *at this width*, so misreporting one as the other could not mislead anyone and an unfired control is evidence of nothing. The gate therefore requires a control to fire only where materiality reaches 1 — anything else would be an instruction to tune the generator until the control cooperated.

- noisy_outcome:finite_vs_super (materiality 0.46, below 1)
