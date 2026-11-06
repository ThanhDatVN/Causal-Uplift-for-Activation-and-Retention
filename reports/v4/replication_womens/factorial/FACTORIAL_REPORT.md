# R04 — component factorial

hillstrom Womens E-Mail vs No E-Mail (development) · 34,174 units · 251 events · 3 outer folds · 12 effect fits · 5 s

Gate: reports/v4/validity_unshrunk/validity_suite.json: PASS at 2000 worlds with the skewness_adjusted_t interval -- SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (reports/v4/validity_confirm/validity_suite.json (skewness_adjusted_t: FAIL)), so this verdict is a post-hoc choice of interval method and needs independent confirmation

Development only, three outer folds of one dataset. Main effects are paired across folds but three folds are not three datasets, and the contact costs are declared prices rather than postings.

Contact costs are **assumed, not measured; Hillstrom has no cost ledger**.

## Cost regime: homogeneous

*every contact costs the same; C is a null fixture here*

| representation | final stage | allocator | mean value |
|---|---|---|---|
| base_plus_interactions | hgb | net_value | +0.000601 |
| base_plus_interactions | hgb | rank | +0.000601 |
| base_plus_interactions | ridge | net_value | +0.000722 |
| base_plus_interactions | ridge | rank | +0.000722 |
| base | hgb | net_value | +0.000413 |
| base | hgb | rank | +0.000413 |
| base | ridge | net_value | +0.001135 |
| base | ridge | rank | +0.001135 |

| factor | from | to | paired effect | se |
|---|---|---|---|---|
| representation | base | base_plus_interactions | -0.000112 | 0.000127 |
| final_stage | ridge | hgb | -0.000421 | 0.000153 |
| allocator | rank | net_value | +0.000000 | 0.000000 |

## Cost regime: heterogeneous

*contact cost varies by channel, so net value reranks*

| representation | final stage | allocator | mean value |
|---|---|---|---|
| base_plus_interactions | hgb | net_value | +0.000548 |
| base_plus_interactions | hgb | rank | +0.000601 |
| base_plus_interactions | ridge | net_value | +0.000927 |
| base_plus_interactions | ridge | rank | +0.000722 |
| base | hgb | net_value | +0.000346 |
| base | hgb | rank | +0.000413 |
| base | ridge | net_value | +0.001091 |
| base | ridge | rank | +0.001135 |

| factor | from | to | paired effect | se |
|---|---|---|---|---|
| representation | base | base_plus_interactions | -0.000047 | 0.000134 |
| final_stage | ridge | hgb | -0.000492 | 0.000148 |
| allocator | rank | net_value | +0.000010 | 0.000069 |

## The null fixture

with a homogeneous cost, net value is the score minus a constant, so a rank allocator must contact exactly the same accounts.

**Held**

Under a homogeneous cost the allocator factor is expected to do nothing, and it is run precisely so that a difference under the heterogeneous cost can be read as the allocation rule rather than as noise in the pipeline.
