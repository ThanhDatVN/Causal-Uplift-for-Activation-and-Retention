# Portfolio completion implementation record

**Date:** 30 September 2026  
**Scope:** local reproducibility and planner usability work for the English [case study](../../../docs/PORTFOLIO_CASE_STUDY_EN.md). The refreshed [evidence index](../EVIDENCE_INDEX.md) computes `ENGINEERING_FOUNDATION`; causal evaluator confirmation remains `NOT_MET` and the partner trial `NOT_RUN`.

## 30 September final-source checkpoint

- One complete Python suite: **644 tests, 0 failures, 0 errors, 0 skipped**, 472.185 seconds; [JUnit XML](pytest_post_research.xml). Ruff lint and format checks on `src`, `tests`, and `scripts`, plus JavaScript syntax check, passed after the research modules and evidence-index edits.
- The [full](../reproduced_full/RUN_MANIFEST.json), [quick](../reproduced_quick/RUN_MANIFEST.json), and [Hillstrom development](../screening_reproduction/RUN_MANIFEST.json) reproductions share final producer fingerprint `828b3d284469537aed8ea23dfc9912408a386950ac0e69a697dedc125ee79ec5` and report a satisfied 180-package research lock. Full IBM selected logistic with AP 0.6396005899; all eight archived metric rows match exactly after excluding fit time, and the 1,409 prediction CSV bytes match. Full bundle SHA-256: `289c7af82c574f23d92fe59d21197b76b6ee860b2b4a7c12fa0caf0de609e896`. Quick smoke bundle SHA-256: `6e408e2beb7c442e93f0473c52a8d63f1a1ac59c24dc807897bb78960f19419d`.
- The [Chrome full-bundle browser run](../browser_smoke_post_research/result.json) passed all ten checks with no page errors; the earlier Chrome/Edge runs and [CSV-template keyboard roundtrip](../template_flow/result.json) remain separate evidence. The [current wheel](../../../dist/portfolio_20260930/telcochurn_decision_system-0.1.0-py3-none-any.whl) has SHA-256 `9d9f0476cb619f40b5cb64915cc7ce71dae2cc699555d384c74d724086a3362e` and contains planner HTML/CSS/JS plus the new research modules. A [wheel-target import smoke](WHEEL_SMOKE.json) loaded the API from installed wheel code with the existing dependency environment.
- The [R1/R4 research execution summary](../../../docs/RESEARCH_EXECUTION_2026_EN.md) records failed evaluator transfer cells, an inconclusive row-IID negative control, a development-only learner comparison retaining M01 for Hillstrom Mens, structural R4 allocator equivalence, and a non-promoted exploratory R4b revision. The [evidence index](../EVIDENCE_INDEX.md) lists these artifacts and remains at `ENGINEERING_FOUNDATION`; independent causal confirmation is `NOT_MET` and a partner trial is `NOT_RUN`.

## Completed engineering work

| Area | Change | Evidence |
|---|---|---|
| Clean local reproduction | Added `scripts/reproduce_benchmark.py`: verifies the IBM SHA-256, frozen split, producer source digest, research lock, model bundle, report, command, role, and timestamps in a JSON manifest. | [Quick run manifest](../reproduced_quick/RUN_MANIFEST.json); [release guide](../../../docs/PORTFOLIO_RELEASE_2026_EN.md) |
| Causal development reproduction | Added `scripts/reproduce_screening.py` to rerun the eight Hillstrom methods on the development role and record source, data, split, gate, report and environment hashes. | [Development manifest](../screening_reproduction/RUN_MANIFEST.json); [screening report](../screening_reproduction/SCREENING_REPORT.md) |
| Planner input | CSV schema and first-five-row preview; actionable line/field errors; category, range, cross-field, duplicate-ID, quote and file-size checks. Invalid uploads clear old drafts. | [Browser verification](BROWSER_VERIFICATION.md) |
| Planner state | A revision counter invalidates late scoring responses when rows or assumptions change, and prevents stale packet export after an asynchronous digest. | [Chrome](../browser_smoke_reproduced_chrome/result.json) and [Edge](../browser_smoke_reproduced_edge/result.json) smoke results |
| Replay and packaging | Browser-downloaded packet matches deterministic replay against its model SHA-256. Optional pinned Playwright dependency and CI browser job added. | [Browser smoke script](../../../scripts/browser_smoke.py); [CI workflow](../../../.github/workflows/ci.yml) |
| Interview path | Concise English case study, local setup, architecture, model choice, negative research result, limitations, and interview FAQ. | [Case study](../../../docs/PORTFOLIO_CASE_STUDY_EN.md) |

## 29 September verification checkpoint (archived)

- Final full Python suite: **644 tests, 0 failures, 0 errors, 0 skipped**; [JUnit XML](pytest_full_final.xml), 456.604 seconds. This run completed after all source edits.
- `ruff check src tests scripts`, `ruff format --check src tests scripts`, and `node --check src/telco_churn/planner/app.js` passed after the implementation edits.
- Chrome and Edge passed the reproduced-bundle browser flow, including the delayed-response race, malformed CSV, no-contact case, packet download and replay. No uncaught page errors were recorded.
- The [final local wheel](../../../dist/portfolio_final/telcochurn_decision_system-0.1.0-py3-none-any.whl) built with SHA-256 `6b4bb6769e75dfd004faf70577f45a8419389777ef80ff4588b0c115dbf7cd96`; inspection confirmed the planner HTML, CSS, and JavaScript are packaged. An older wheel remains in the top-level `dist/` directory and has a different checksum. A package build initially exposed that generated `.egg-info` files could affect the producer source digest; the reproduction script now excludes generated package metadata.
- The quick IBM run selected logistic regression and had frozen-test AP **0.6444**, ROC-AUC **0.8505**, and Brier **0.1343**. It is a smoke run with reduced search; it is not an improvement over the archived full protocol.
- Hillstrom development screening completed **8/8** methods on 34,092 development units and 302 events. The shortlist was M01/M03/M07. Its gate text explicitly says the selected interval was **chosen after looking** and needs independent confirmation. Three outer folds do not provide a population interval or license a causal launch claim; [the manifest](../screening_reproduction/RUN_MANIFEST.json) records this role and the input hashes.
- The [full IBM benchmark](../reproduced_full/RUN_MANIFEST.json) completed in about 6 minutes 14 seconds under the final producer source digest `85220388da8374be4dcf2331c41e76fdc293078b13eaa7fcc66757f363192dfe`; the research lock was satisfied. All eight model metric rows and all 1,409 frozen-test predictions match the archived full run numerically. The [comparison](FULL_BENCHMARK_COMPARISON.md) records the hard-cap convention difference in scenario values. The final full bundle SHA-256 is `f5de243ac584e69d6d6fee17b80f2d6416a8f09c94d1468e9b246e0ae565dfeb`.
- Holdout handling is procedural, not cryptographic: the Hillstrom loader parses the raw CSV before filtering to development rows. Confirmation rows are excluded before learner fitting and value scoring, but the code does not enforce an inaccessible outcome vault. A future one-use confirmation should be run in a sealed data path with a signed analysis manifest.

## Boundaries and next gates

- Hosted GitHub Actions is configured but unobserved. This local workspace has no `.git` directory, so there is no commit ID, remote workflow URL, or clean-checkout proof here. The source digest in the manifest identifies the local producer files.
- The full IBM and Hillstrom development-only reproductions are complete locally. They have different evidence roles, and neither provides a real telecom treatment effect. Hillstrom confirmation outcomes have not been used for model comparison.
- No screen-reader pass or five first-time-user sessions have been conducted. Automated browser checks cannot establish either.
- No real contact delivery, randomized telco action/control outcomes, cost ledger, or measured ROI is available. Any pilot or causal launch claim requires the [external evidence gates](../../../docs/REMAINING_GAPS_AND_COMPLETION_PLAN_2026_EN.md).
