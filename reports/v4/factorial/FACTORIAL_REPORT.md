# R04 — component factorial

hillstrom Mens E-Mail vs No E-Mail (development) · 34,092 units · 302 events · 3 outer folds · 12 effect fits · 6 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only, three outer folds of one dataset. Main effects are paired across folds but three folds are not three datasets, and the contact costs are declared prices rather than postings.

Contact costs are **assumed, not measured; Hillstrom has no cost ledger**.

## Cost regime: homogeneous

*every contact costs the same; C is a null fixture here*

| representation | final stage | allocator | mean value |
|---|---|---|---|
| base_plus_interactions | hgb | net_value | +0.001312 |
| base_plus_interactions | hgb | rank | +0.001312 |
| base_plus_interactions | ridge | net_value | +0.000829 |
| base_plus_interactions | ridge | rank | +0.000829 |
| base | hgb | net_value | +0.001080 |
| base | hgb | rank | +0.001080 |
| base | ridge | net_value | +0.000864 |
| base | ridge | rank | +0.000864 |

| factor | from | to | paired effect | se |
|---|---|---|---|---|
| representation | base | base_plus_interactions | +0.000098 | 0.000209 |
| final_stage | ridge | hgb | +0.000349 | 0.000256 |
| allocator | rank | net_value | +0.000000 | 0.000000 |

## Cost regime: heterogeneous

*contact cost varies by channel, so net value reranks*

| representation | final stage | allocator | mean value |
|---|---|---|---|
| base_plus_interactions | hgb | net_value | +0.001215 |
| base_plus_interactions | hgb | rank | +0.001312 |
| base_plus_interactions | ridge | net_value | +0.000775 |
| base_plus_interactions | ridge | rank | +0.000829 |
| base | hgb | net_value | +0.001062 |
| base | hgb | rank | +0.001080 |
| base | ridge | net_value | +0.001348 |
| base | ridge | rank | +0.000864 |

| factor | from | to | paired effect | se |
|---|---|---|---|---|
| representation | base | base_plus_interactions | -0.000056 | 0.000229 |
| final_stage | ridge | hgb | +0.000213 | 0.000294 |
| allocator | rank | net_value | +0.000079 | 0.000109 |

## The null fixture

with a homogeneous cost, net value is the score minus a constant, so a rank allocator must contact exactly the same accounts.

**Held**

Under a homogeneous cost the allocator factor is expected to do nothing, and it is run precisely so that a difference under the heterogeneous cost can be read as the allocation rule rather than as noise in the pipeline.
