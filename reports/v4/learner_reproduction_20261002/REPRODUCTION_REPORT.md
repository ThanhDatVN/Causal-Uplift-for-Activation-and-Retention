# R4 nested learner: completed local provenance reproduction

**Role:** already inspected public development data. This run repairs the earlier manifest's pre-fit runtime/result-hash omission. It is not independent confirmation.

`python kaggle/run_learner.py run --study local-reproduction --input-root . --output reports/v4/learner_reproduction_20261002` completed with `status: COMPLETE` in **395.626 seconds** on the local Python 3.11.9 research environment. [RUN_MANIFEST.json](RUN_MANIFEST.json) records the finished UTC time, package versions, raw/source/split hashes, parameters, result SHA-256 values, and an explicit `confirmation_labels_accessed: false` role boundary. [Preflight](../learner_reproduction_preflight_20261002/RUN_MANIFEST.json) passed before this run. `python kaggle/verify_return.py reports/v4/learner_reproduction_20261002 --study local-reproduction` passed.

| Development branch | Selected recipes | Selected minus M01, conversions/1,000 | Scientific comparison with archived result |
|---|---|---:|---|
| Hillstrom Mens | M07, M03, M05 | -1.3730259867401156 | Exact match excluding timing fields. |
| Hillstrom Womens | M03, M03, M03 | +0.6810860697840502 | Exact match excluding timing fields. |
| Lenta SMS, 60k development sample | M07, M07, M03 | +1.3892726103317408 | Exact match excluding timing fields. |

The comparison recursively removed only `fit_seconds` and `elapsed_seconds`; all other JSON fields, including each fold's value, selected recipe, capacity, event count, and policy disagreement, matched the [archived run](../learner_comparison/LEARNER_REPORT.md). The reproducible decision remains to retain M01 for the primary Hillstrom Mens scope. Lenta is exploratory because its `e=0.75` is an assumed rather than logged assignment probability.

The [Kaggle CPU kit](../../../kaggle/README.md) is prepared for a **separate, unrun** full-development Lenta comparison. It must not overwrite this 60k reproduction or be described as a completed result.
