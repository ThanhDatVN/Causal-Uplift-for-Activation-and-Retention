# R4 exact allocator: known-truth synthetic comparison

**Role:** synthetic method study; no telecom uplift or ROI claim.
**Run:** 90 independent worlds, 4,500 paired batches, 13.7 CPU wall seconds.

M07 DR-Ridge was fitted independently in each world on 10,000 randomized training units. The 5,000-unit selection role was reserved and unused. Each allocator saw identical frozen scores and costs on 50 new batches of 20 units. Oracle probabilities were read only after decisions. Value is true expected synthetic net currency per 1,000 eligible units, with 100 currency units per prevented adverse event and assumed contact prices 0.2/1.2.

| Mechanism | Exact minus rank | 95% world-t interval | MCSE | Disagreement | Violations |
|---|---:|---:|---:|---:|---:|
| aligned | 0.000 | [0.000, 0.000] | 0.000 | 0.000% | 0 |
| opposed | 0.000 | [0.000, 0.000] | 0.000 | 0.000% | 0 |
| sharp_null | 0.000 | [0.000, 0.000] | 0.000 | 0.000% | 0 |

**Predeclared decision:** `RETAIN_FEASIBLE_RANK_OR_INCONCLUSIVE`. The practical margin is 1 synthetic currency unit per 1,000 eligible customers in the opposed mechanism. The sharp-null mechanism is a negative control and must not be promoted as a gain.

The exact two-price solver maximizes the same predicted objective as the feasible rank rule under four contacts and a 2-unit money cap. Algorithmic controls include brute-force optimality on tiny batches, homogeneous prices, zero money, all-negative scores, ties, and infeasible actions. Under these particular constraints two expensive contacts exceed the money cap, while one expensive plus three cheap contacts fits. Sorting by positive net score and skipping unaffordable expensive contacts is therefore already exact: each feasible top-four set can contain at most one expensive contact. The exhaustive two-price count search has a zero solver gap by construction. Both policies have zero recorded hard-cap violations. The table above is the primary readout; exact and rank cannot separate in this frozen constraint geometry.

**Limits:** 30 worlds per mechanism give a descriptive t interval for this generator. They do not validate interval coverage, other cost grids, a real customer's offer response, or a deployed economic return. The synthetic price and value scale are assumptions. The comparison is conditional on M07 and this frozen generator. The current cost geometry cannot distinguish the two allocators. A 1.2-unit cap with these same prices could create a real tradeoff between one expensive and several cheap contacts, but it is only a prospective design suggestion, not a result here. It requires a new frozen protocol and new worlds.
