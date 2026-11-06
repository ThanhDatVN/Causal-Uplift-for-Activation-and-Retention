# R08 — sampling design and its economics

1,000 worlds per cell · frame 10,000 · target recruitment 20% · 218 s

One generator, one frame size, one capacity-free contrast. Costs are declared prices, so the output is a cost ratio at matched precision and not a profit claim. Comparing designs at equal recruited N would flatter the enriched one; this compares them at equal precision.

Each interval is scored against **the truth its own variance targets**. The finite-frame variance treats the frame's scores as fixed, so it targets the census value; the superpopulation variance adds the score noise that survives a census, so it targets the effect.

| d | design | readout | q_D | q_agree | recruited | in D | coverage | half width | |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | uniform | `finite_vs_census` | 0.200 | 0.200 | 2,001 | 99 | 0.941 [0.925] | 0.00387 |  |
| 0.05 | uniform | `super_vs_effect` | 0.200 | 0.200 | 2,001 | 99 | 0.953 [0.938] | 0.00434 |  |
| 0.05 | uniform | `finite_vs_effect` | 0.200 | 0.200 | 2,001 | 99 | 0.922 [0.904] | 0.00387 | control did not fire |
| 0.05 | enriched | `finite_vs_census` | 0.800 | 0.168 | 2,001 | 399 | 0.943 [0.927] | 0.00099 |  |
| 0.05 | enriched | `super_vs_effect` | 0.800 | 0.168 | 2,001 | 399 | 0.952 [0.937] | 0.00222 |  |
| 0.05 | enriched | `finite_vs_effect` | 0.800 | 0.168 | 2,001 | 399 | 0.612 [0.581] | 0.00099 | **fired** |
| 0.20 | uniform | `finite_vs_census` | 0.200 | 0.200 | 2,002 | 401 | 0.945 [0.929] | 0.00782 |  |
| 0.20 | uniform | `super_vs_effect` | 0.200 | 0.200 | 2,002 | 401 | 0.940 [0.923] | 0.00873 |  |
| 0.20 | uniform | `finite_vs_effect` | 0.200 | 0.200 | 2,002 | 401 | 0.902 [0.882] | 0.00782 | **fired** |
| 0.20 | enriched | `finite_vs_census` | 0.794 | 0.051 | 2,000 | 1,589 | 0.948 [0.932] | 0.00201 |  |
| 0.20 | enriched | `super_vs_effect` | 0.794 | 0.051 | 2,000 | 1,589 | 0.941 [0.925] | 0.00442 |  |
| 0.20 | enriched | `finite_vs_effect` | 0.794 | 0.051 | 2,000 | 1,589 | 0.628 [0.598] | 0.00201 | **fired** |
| 0.50 | uniform | `finite_vs_census` | 0.200 | 0.200 | 1,999 | 998 | 0.951 [0.936] | 0.01196 |  |
| 0.50 | uniform | `super_vs_effect` | 0.200 | 0.200 | 1,999 | 998 | 0.941 [0.925] | 0.01338 |  |
| 0.50 | uniform | `finite_vs_effect` | 0.200 | 0.200 | 1,999 | 998 | 0.906 [0.886] | 0.01196 | control did not fire |
| 0.50 | enriched | `finite_vs_census` | 0.350 | 0.050 | 2,000 | 1,750 | 0.959 [0.945] | 0.00816 |  |
| 0.50 | enriched | `super_vs_effect` | 0.350 | 0.050 | 2,000 | 1,750 | 0.958 [0.944] | 0.01013 |  |
| 0.50 | enriched | `finite_vs_effect` | 0.350 | 0.050 | 2,000 | 1,750 | 0.896 [0.875] | 0.00816 | **fired** |

`finite_vs_effect` is a **declared negative control**: the narrow interval read as though it said something about the underlying effect. It is expected to under-cover and is never gated on.

## Cost at matched precision

Each design is costed for the sample it would need to reach a **common** target half-width, with screening counted, using the superpopulation interval -- the one a forward-looking claim would actually report. Comparing raw recruited N would reward whichever design recruits more.

| d | target half width | uniform cost | enriched cost | ratio | cheaper |
|---|---|---|---|---|---|
| 0.05 | 0.00434 | 3,150 | 818 | 0.260 | enriched |
| 0.20 | 0.00873 | 3,053 | 798 | 0.261 | enriched |
| 0.50 | 0.01338 | 3,032 | 1,781 | 0.587 | enriched |

Costs use **declared prices in reward units, not postings**: cost_per_screened = 0.01, cost_per_recruited = 1.0, cost_per_outcome = 0.5.

At `d = 0.50` the formula can barely enrich -- `q_D` is pushed only a little above the uniform 0.2 -- so the two designs are expected to converge there. Reporting only the smallest `d` would overstate what the design buys.
