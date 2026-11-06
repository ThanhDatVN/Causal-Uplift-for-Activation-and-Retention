# R4 nested-fold learner comparison

**Evidence role:** inspected public development data only. Hillstrom Mens is the primary development branch, Hillstrom Womens is a sensitivity branch, and the 60,000-row Lenta development subsample is exploratory with an assumed propensity. No confirmation outcome was used for model comparison, no domains were pooled, and no population confidence interval or real telecom uplift is claimed.

The [pre-run amendment](PRE_RUN_AMENDMENT.md) fixed the Lenta subsample, three outer and three inner folds, 20% hard contact cap, M01 comparator, M03/M05/M07 selection pool, deterministic ties, and a planning margin of one conversion per 1,000 eligible customers before the nested comparisons. Inner-fold estimated whole-cohort DR value chose a recipe; each untouched outer fold compared that recipe with M01 on the same rows and train-side nuisance fits. Fold ranges below describe instability within one dataset, not sampling uncertainty.

| Development branch | Selected recipes by outer fold | Mean selected minus M01, conversions/1,000 | Range across three folds | Planning decision |
|---|---|---:|---:|---|
| Hillstrom Mens | M07, M03, M05 | -1.373 | -2.743 to +0.379 | Retain M01 for this scope; selection unstable. |
| Hillstrom Womens | M03, M03, M03 | +0.681 | -0.155 to +1.103 | Retain M01; mean below +1 margin. |
| Lenta SMS subsample | M07, M07, M03 | +1.389 | -0.195 to +2.969 | Exploratory only; propensity is assumed. |

All three branches completed without failed candidate cells. Detailed per-fold values, no-contact references, contact counts, disagreement, event support, and fit time are in [Mens](hillstrom_mens.json), [Womens](hillstrom_womens.json), and [Lenta](lenta_sms.json). The Lenta dataset documentation lists a 0.75 treatment **ratio** but does not supply the campaign randomizer's logged probability in this repository; `e=0.75` is therefore a working assumption, not a verified design probability. See the [dataset documentation](https://www.uplift-modeling.com/en/v0.4.0/api/datasets/fetch_lenta.html). A 60,000-row subsample does not reproduce a full-development Lenta comparison.

## Provenance and limitations

The [dry-run manifest](DRY_RUN_MANIFEST.json) predates the outcome comparison and records source and input hashes. The original producer source was preserved byte-for-byte as [PRODUCER_SOURCE.py](PRODUCER_SOURCE.py), SHA-256 `69b55b108271d64910eb91785b1bc2f6ff8270b3728ee757fd390aad1fa6267c`, matching the run manifest. The working module was subsequently reformatted and received lint-only comments; its non-import Python AST matches the archived producer. Result SHA-256 values are recorded in [POST_RUN_AUDIT.json](POST_RUN_AUDIT.json). The original run manifest wrote `command: run` and elapsed time before fitting; these fields are incomplete provenance and are not treated as the actual total run command or runtime. The audit records a reproducible command, not a recovered shell history.

The CSV loaders parse the full raw files before filtering to hashed development roles, so the holdout is procedural rather than cryptographically sealed. The inspected domains cannot provide new independent confirmation. The selected evaluator also has [failed R1 transfer cells](../next_evaluator_transfer/TRANSFER_REPORT.md); do not use this learner table to open the held-back Hillstrom confirmation split or make a launch claim. A new domain with verified assignment logs, a validated batch evaluator, and a one-use preregistered comparison would be required.
