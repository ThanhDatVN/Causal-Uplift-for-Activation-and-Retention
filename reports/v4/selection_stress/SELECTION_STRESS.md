# R06 — selection stress

300 worlds per mechanism · 4 frozen recipes · N = 20,000 per sample · 185 s

**This is not a gate.** a 5% false-promotion gate cannot be scored on 300 null worlds: the 95% binomial interval there is about +-0.025, wider than the quantity being gated. This stage reports sensitivity to selection, not a certified rate.

One generator family, four frozen recipes, one capacity. The comparison is one-versus-four candidates on identical predictions, so it isolates the cost of selecting rather than of modelling.

| mechanism | arm | promotion | 95% CI | coverage | mean regret | bias |
|---|---|---|---|---|---|---|
| null_effect | one_candidate | 0.043 | [0.025, 0.073] | 0.917 | +0.000000 | +0.000077 |
| null_effect | four_candidates | 0.023 | [0.011, 0.047] | 0.950 | +0.000000 | -0.000005 |
| weak_heterogeneous | one_candidate | 0.580 | [0.523, 0.634] | 0.957 | +0.000000 | -0.000010 |
| weak_heterogeneous | four_candidates | 0.567 | [0.510, 0.622] | 0.967 | +0.000115 | -0.000004 |

## What selection cost

| mechanism | promotion inflation | coverage loss | mean regret |
|---|---|---|---|
| null_effect | -0.020 | -0.033 | +0.000000 |
| weak_heterogeneous | -0.013 | -0.010 | +0.000115 |

Under `null_effect` no recipe is better than any other, so every promotion is a false one and any regret above zero is the selector paying for noise. The one-candidate arm is committed to `x1_only` in advance, so its promotion rate carries no selection at all and the difference between the arms is the price of looking at four.
