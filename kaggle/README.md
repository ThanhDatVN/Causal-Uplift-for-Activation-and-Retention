# Kaggle CPU kit: R4 nested learner, full Lenta development

**Status:** prepared and locally audited; the full Lenta run has not been executed. This is a compute extension of an **exploratory** public-data comparison, not a GPU experiment or a measured telecom effect. The 60,000-row comparison [was reproduced locally](../reports/v4/learner_reproduction_20261002/REPRODUCTION_REPORT.md) with a completed provenance manifest.

## Inputs and role boundary

Build the upload ZIP locally with `python kaggle/build_bundle.py`. It contains the exact local wheel, both checksum-pinned public input files, the runner, requirements, and a notebook. The ZIP SHA-256 is printed by the builder. Upload it as a **private** Kaggle Dataset unless you have separately checked redistribution rights and attribution. Kaggle extracts uploaded ZIP files for Notebook input; use `Add Input` to attach that Dataset. The raw Lenta file is 144,735,744 bytes. The runner checks its SHA-256 before parsing.

| Input | SHA-256 | Role |
|---|---|---|
| `data/raw/lenta.csv.gz` | `b531544f6c072d22f232d91e20ffcaca265acf224e02687502a40e6d56135682` | Raw public source; hashed split yields 549,867 development and 137,162 confirmation rows. Only development labels are indexed. |
| `data/raw/hillstrom.csv` | `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece` | Used only by the optional local reproduction. |
| Project wheel | `9d9f0476cb619f40b5cb64915cc7ce71dae2cc699555d384c74d724086a3362e` | Unchanged core source from the verified portfolio build. |

The Lenta `e=0.75` propensity is a working assumption inferred from observed assignment proportions. It is **not** a logged randomizer probability. The raw CSV parser reads all rows before role filtering, so the holdout is procedural rather than cryptographically sealed. Do not use this run to open confirmation outcomes, promote a causal claim, or claim measured ROI.

The [local full-development preflight](../reports/v4/full_lenta_preflight_20261002/RUN_MANIFEST.json) passed with 549,867 development rows, 137,162 held-back confirmation rows, 191 feature columns, and development-ID SHA-256 `f5d392917ee0aa133c9449b20599a688377efb30a93b38867fc507f0f4e3c9bc`. The fit has **not** run; this is a role/input check.

## Kaggle steps

1. Create a private Dataset from `dist/kaggle_nested_learner_cpu_20261002.zip`. Open `full_lenta_cpu.ipynb` as a Kaggle Notebook and attach the Dataset using `Add Input`.
2. Select **CPU / no accelerator**. Enable Internet if the pinned packages need installation. GPU does not accelerate the sklearn logistic/ridge pipeline used here. Kaggle's [Notebook guide](https://www.kaggle.com/docs/notebooks) describes inputs, `/kaggle/working`, Internet, and accelerator settings; the [Dataset guide](https://www.kaggle.com/docs/datasets) describes private datasets and ZIP uploads.
3. Run all notebook cells. The notebook verifies package versions, installs the bundled wheel, checks raw and source hashes, runs a label-free preflight, then executes one full-development nested comparison. If a prerequisite or hash fails, fix the environment/input and start a new run. Keep the failed manifest too.
4. Download `/kaggle/working/r4_full_lenta/RUN_MANIFEST.json` and `lenta_sms.json`; also keep Kaggle's notebook version/log. Copy artifacts to a new dated directory under `reports/v4/`; never overwrite the archived 60k result. Then run `python kaggle/verify_return.py reports/v4/<dated-directory> --study full-lenta` to check status, role, split, source and runner hashes, all outer folds, and the result SHA-256.

In a Kaggle code cell, if you use the script directly, the equivalent command after wheel installation is:

```bash
python /kaggle/input/<your-dataset>/run_learner.py preflight --study full-lenta --input-root /kaggle/input/<your-dataset> --output /kaggle/working/r4_full_lenta_preflight
python /kaggle/input/<your-dataset>/run_learner.py run --study full-lenta --input-root /kaggle/input/<your-dataset> --output /kaggle/working/r4_full_lenta
```

The `run` output directory must be empty. The wrapper writes a `RUNNING` manifest before fitting and updates it with the actual finish time, elapsed time, environment, per-domain result SHA-256, or an explicit Python failure. A process killed by an out-of-memory limit may leave `RUNNING`; retain that manifest and Kaggle's execution log as failure evidence. Only one frozen full-development comparison is intended. A changed package or configuration is a new protocol.

## Local reproduction of the 60k study

With the project installed in the local research environment and both raw files present:

```bash
python kaggle/run_learner.py preflight --study local-reproduction --input-root . --output reports/v4/learner_reproduction_preflight_20261002
python kaggle/run_learner.py run --study local-reproduction --input-root . --output reports/v4/learner_reproduction_20261002
```

This is a provenance repair for an already inspected development experiment. It is not independent confirmation. Compare every domain result with the archived 60k report and document any numeric drift. For exact local dependency pins see `locks/research.lock.txt`; Kaggle's smaller `requirements.txt` pins the numerical/modeling libraries and records the installed environment in the output manifest.

## What remains outside Kaggle

R1 evaluator repair requires a new estimator, a frozen protocol, and unseen synthetic worlds; it is CPU work and is not part of this kit. Real assignment logs, partner outcomes, hosted CI, and human usability/screen-reader sessions require external inputs or participants. Kaggle compute cannot supply those forms of evidence.
