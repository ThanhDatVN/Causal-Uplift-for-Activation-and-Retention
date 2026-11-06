# Retention Decision Lab: 2 October 2026 verification

## Result

The local engineering prototype is ready for a reproducible interview walkthrough. The [evidence index](../EVIDENCE_INDEX.md) reports `ENGINEERING_FOUNDATION` when generated with the research-lock virtual environment. Its causal evaluator gate remains `NOT_MET`, and its prospective partner trial remains `NOT_RUN`. No measured telecom campaign effect or return on investment is claimed.

The [R1 prospective repair](../r1_repair_20261002/REPORT.md) completed six synthetic cells with 2,000 new worlds per cell and no failed fits or intervals. Five candidate coverage gates failed. The stronger cluster negative control discriminated between customer-level and invalid row-level inference, but it does not rescue candidate coverage. The bounded safety reference covered every world and was too wide to support the declared decision precision. Keep `NO_LAUNCH`.

## Final local checks

| Check | Result |
|---|---|
| Full Python suite, `.venv/Scripts/python.exe -m pytest -q` | Passed on the final source and fixtures. |
| Ruff lint, `src tests scripts kaggle` | Passed. |
| Ruff format, `src tests scripts` | 105 files already formatted. The frozen Kaggle kit was excluded from this format gate; its lint passed. |
| JavaScript syntax, `node --check src/telco_churn/planner/app.js` | Passed. |
| [Chrome desktop/mobile smoke](../browser_smoke_v2_20261002/result.json) | Ten checks passed, zero page errors, and the exported v2 packet replayed against the real model bundle. No human or screen-reader session is implied. |
| Research environment lock | [180 locked packages satisfied](../environment_current_venv.json). The system Python has a different `setuptools` version and must not regenerate the evidence index. |
| Built wheel | [Current application wheel](../../../dist/portfolio_20261002/telcochurn_decision_system-0.1.0-py3-none-any.whl), SHA-256 `1f444f78017faec60cc252c606deb34c19620e8eb5174949b06da9e5c3ac64cb`. An isolated target install imported `api.py` and `r1_repair.py` from the wheel and found the planner favicon. |

The first full-suite attempt exposed a real fixture error: sorting nested JSON keys changed the order-sensitive `input_sha256` without changing the apparent customer values. The two frozen fictional packets were regenerated in export order. Their replay tests and then the full suite passed. The [migration contract](../../../docs/RISK_FIELD_MIGRATION_EN.md) now documents that packets should retain their original serialization.

The evidence ledger still marks some historical artifacts older than their producer modules. Those artifacts retain their dated provenance and are not presented as reruns of the final source. The current v2 browser artifact was rerun after the final API formatting and is fresh in the ledger.

## Work that needs external compute or evidence

The [Kaggle CPU kit](../../../kaggle/README.md) remains a separately frozen R4 source/wheel snapshot for the full-development Lenta nested learner run. Its ZIP was not rebuilt with the current application wheel. The local 60,000-row reproduction and full-Lenta label-free preflight are complete; the full 549,867-row development fit has not run. Return and verify its manifest, result JSON, and notebook log before interpreting it.

Hosted CI, first-user and screen-reader sessions, and an independent real campaign evaluation still require external services, participants, or partner data. A new causal interval candidate needs a new frozen protocol and unseen validation worlds before any promotion. The current planner remains a local decision-support demonstration with assumed offer response.
