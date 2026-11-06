# Local portfolio release verification

> **Update (29 September 2026):** The [completion implementation record](portfolio_completion/IMPLEMENTATION_REPORT.md) contains the later 644-test full-suite result, reproduced-bundle Chrome/Edge verification, updated wheel, and source-hash manifest. The refreshed [evidence index](EVIDENCE_INDEX.md) computes `ENGINEERING_FOUNDATION` from engineering gates while causal confirmation and a partner trial remain unmet. The older scope notes below describe the earlier pass and are retained for history.

**Date:** 29 September 2026. **Host:** Windows, Python 3.11.9. This is a local engineering and research demonstration, not a production deployment.

## Reproduction

The IBM dataset checksum was `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91`; the frozen split manifest checksum was `08a34a4e87b8fbf143299650fad0fecb459552336db34587c47a5ca376950630`. `python -m telco_churn.train --quick --output reports/v4/quick_reproduction --model-dir artifacts/quick_reproduction` completed without touching the deployed champion bundle. The [quick benchmark](quick_reproduction/BENCHMARK_REPORT.md) selected logistic regression under the declared complexity gate. Its frozen-test AP was `0.6444`, ROC-AUC `0.8505`, Brier `0.1343`; the top 10% selected 141 customers and captured 104 of 374 churn cases. These are a smoke reproduction with reduced search, not an improvement claim against the archived full benchmark.

The quick bundle SHA-256 is `188aa17ee42f3f7ca3cab6fa6d284504e5535f08c3d0098ba887f27effb2e4d0`; the existing champion SHA-256 is `7e14cf28518edf4494ae039fba9a29eea4d11f510946865023c5d6a48746caa7`. Both carry version `1.0.0`, so the preview response and evidence packet now include the actual bundle hash.

## Product and package

The [fictional packet replay](planner_replay/REPLAY_REPORT.md) returned `MATCH` with the existing champion and `MISMATCH` with the quick bundle. The input SHA-256 agreed with Node's `JSON.stringify` byte encoding. A Python wheel built successfully with SHA-256 `5c1e0ef0b647bd307f0bff9298c64405a9e06da7e509e1c2ff7134fbe9c2564d`; inspection confirmed the planner HTML/CSS/JavaScript, dashboard HTML, evaluator, replay module, and CLI entry point are present.

The current research-lock check reports `SATISFIED`: 180 pinned packages present at the declared versions, zero missing and zero changed. Fifty-three extra packages were reported and are allowed by the check. Lint and formatting pass for `src`, `tests`, and `scripts`; JavaScript syntax passes. The full Python suite passed before the final model-hash addition. After that addition, all 12 focused API/replay tests passed; a second full run was stopped during its long Monte Carlo cases because those cases were unaffected by the hash change. The current checkout collects 644 tests. No visual browser or first-user usability session was conducted in this pass.

## Evidence boundary

The [fresh evaluator diagnostic](fresh_evaluator/FRESH_EVALUATOR_REPORT.md) does not promote the evidence tier; the current tier is `NONE`. The IBM sample has no validated time horizon or treatment outcomes. All planner money values and offer responses are assumptions. A measured business claim needs a real partner experiment with randomized control, actual costs, and mature outcomes.
