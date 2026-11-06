# R4b: 1.2-unit allocator follow-up, exploratory revision

**Frozen before R4b evaluation:** 30 September 2026. This design was chosen
after the R4 2.0-unit study revealed a structural equivalence: one expensive
contact plus three cheap contacts fit the 2.0-unit budget, so a feasible rank
rule was already optimal. R4b is a post-result design revision. Its outcomes
must not be presented as independent confirmation of an allocator advantage.

## Fixed question and roles

Can exact allocation improve **true expected synthetic net value** over
feasible rank-with-skip when the 1.2-unit budget creates a choice between one
expensive contact and several cheap contacts? The primary paired contrast is
exact minus rank, in synthetic currency units per 1,000 eligible units.
Predicted-objective gain, true gross prevented-event value, and contact-cost
saving are separate diagnostics. In the sharp-null mechanism the true gross
effect contrast is exactly zero; any net difference is cost saving, not causal
response benefit.

Keep every other R4 design element fixed: independent X1/X2 Bernoulli(0.5),
Z standard normal; R04/V03 baseline adverse-event risk; aligned, opposed and
sharp-null treatment effects; randomized treatment e=0.5; M07 DR-Ridge with
alpha=10 and three-fold cross-fitted logistic nuisances. Fit independently
on 10,000 units per world. Reserve 5,000 separate selection units without
using their outcomes or tuning on them. Evaluate 50 new batches of 20 units
per world, 30 worlds per mechanism, for 90 worlds and 4,500 paired batches.
The new seed base is **940000**, disjoint from R4 base 840000. Within each
mechanism use `base + mechanism_index*10000 + world_index*10`, with role
offsets +1 training features, +2 training assignment/outcomes, +3 selection
features, +4 evaluation features and +5 model.

For each batch allow at most `floor(0.2*20)=4` contacts and **120 cents** of
spend. X2=0 costs 20 cents, X2=1 costs 120 cents. Value is 100 synthetic
currency units per prevented event. Both methods see the same frozen M07
predicted net proxy and customer IDs. Rank-with-skip scans positive predicted
net scores descending with ascending-ID ties. Exact allocation enumerates
the top-k prefixes within each of the two cost groups and all feasible
group-count pairs. Neither rule fills nonpositive-value slots. Oracle effect
probabilities enter only after both action vectors are fixed.

## Analysis and decision

Analyze each mechanism separately. The 30 worlds, not the 1,500 batches per
mechanism, are the uncertainty units. Report mean paired true net gain,
two-sided 95% Student-t interval and MCSE, plus predicted-objective gain,
gross-effect gain, cost saving, disagreement, unused slots, constraint
violations, solver dominance check, and runtime. The 1 synthetic currency
unit per 1,000 eligible planning margin in the opposed mechanism is retained
as a descriptive priority signal: its lower interval bound must exceed 1 and
there must be zero hard-cap violations to prioritize a future protocol. Even
if it clears, **no deployed-policy promotion follows from R4b**. Keep all
three mechanisms and the negative control visible. Do not retune prices,
value, score model, seeds, or generator after evaluating outcomes.

Dry-run must record this protocol and producer SHA-256, lock hash, versions,
RNG namespaces, source-independent resource budget and expected outputs.
Run one complete study at the stated size. Save per-world results, summary,
human report and output hashes. External data and splits are absent because
all roles are generated independently. The study is synthetic and cannot
establish telecom uplift, business ROI or interval coverage.
