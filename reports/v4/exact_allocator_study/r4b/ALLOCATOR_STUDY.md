# R4b exact allocator: 1.2-unit budget exploratory follow-up

**Role:** post-R4 design revision and exploratory synthetic method study; no independent confirmation, telecom uplift, or ROI claim.
**Run:** 90 independent worlds, 4,500 paired batches, 12.6 CPU wall seconds.

M07 DR-Ridge was fitted independently in each world on 10,000 randomized training units. The 5,000-unit selection role was reserved and unused. Each allocator saw identical frozen scores and costs on 50 new batches of 20 units. Oracle probabilities were read only after decisions. Value is true expected synthetic net currency per 1,000 eligible units, with 100 currency units per prevented adverse event, assumed contact prices 0.2/1.2, and a 1.2-unit money cap. This revision was chosen after R4 showed the 2.0-unit cap made the methods structurally equivalent. New seeds were frozen before this run.

| Mechanism | True net gain | 95% world-t interval | MCSE | Predicted gain | Gross effect gain | Cost saving | Disagreement | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| aligned | 15.420 | [1.821, 29.019] | 6.649 | 6.134 | 13.000 | 2.420 | 2.360% | 0 |
| opposed | 10.653 | [0.396, 20.911] | 5.015 | 3.501 | 8.967 | 1.687 | 1.677% | 0 |
| sharp_null | 0.947 | [0.216, 1.677] | 0.357 | 1.503 | 0.000 | 0.947 | 0.787% | 0 |

All gain columns use synthetic currency units per 1,000 eligible customers. The 95% Student-t interval and MCSE use 30 paired independent worlds, not 1,500 batches, within each mechanism. Predicted gain is the optimization objective; true net gain is the primary known-truth endpoint. True net equals gross prevented-event value plus contact-cost saving. In sharp null, any net difference can arise only from contact-cost saving, never treatment benefit.

**Predeclared exploratory decision:** `EXPLORATORY_ONLY_NO_POLICY_PROMOTION`. The opposed-mechanism lower interval bound did not clear the 1-unit planning margin. This signal only prioritizes a future independent protocol; it does not select a deployed allocator. The sharp-null row is a negative control for causal benefit, with its gross-effect column fixed at zero.

The exact solver enumerates feasible counts in each of two price groups and takes the top-scoring prefix within each group. This yields the optimum for the frozen additive proxy, and tiny-batch brute-force controls check the implementation. A separate fixture confirms that the revised budget can distinguish the methods. No capacity or money-cap violations were observed.

**Limits:** This revision was motivated by the R4 null, so the 30-world intervals describe this selected synthetic scenario; they are not independent confirmation. They do not establish interval coverage, behavior under other prices or cost grids, a real customer's offer response, or a deployed economic return. The value and price scale remain assumptions. Any next confirmatory comparison needs a new prespecified protocol and unseen worlds.
