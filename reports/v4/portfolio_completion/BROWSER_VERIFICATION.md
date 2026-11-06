# Planner browser verification

## 30 September final-source run

The [Chrome result](../browser_smoke_post_research/result.json) passed ten end-to-end checks against the new full IBM bundle, including keyboard demo activation, CSV feedback, delayed-response invalidation, model-unavailable feedback, no-contact export, packet replay, and narrow mobile layout. No page errors were recorded. The refreshed [desktop](../browser_smoke_post_research/desktop.png) and [mobile](../browser_smoke_post_research/mobile.png) screenshots include the CSV template control. The separate [template roundtrip](../template_flow/result.json) confirms keyboard download and re-upload.

The first invocation of the reusable script omitted `--model`, so its replay step used the archived default bundle and correctly returned `MISMATCH` on `model_sha256`. The completed invocation passed `--model artifacts/reproduced_full/champion.joblib`, matching the server bundle. This is an operator configuration correction, not a model or planner failure. Browser automation still does not substitute for a screen-reader operator or first-time-user sessions.

## 29 September reproduced-quick runs

**Run:** 29 September 2026 against the local API and [final reproduced quick model bundle](../reproduced_quick/RUN_MANIFEST.json), SHA-256 `2a535d7eaf7ef0d6c9e44c5118a636d79cdc35d94fcd5a7bae515fcb2bb67ab9`.

The reusable [browser smoke script](../../../scripts/browser_smoke.py) passed in headless Chrome 154 and Edge 154. Results: [Chrome](../browser_smoke_reproduced_chrome/result.json) and [Edge](../browser_smoke_reproduced_edge/result.json). The [desktop](../browser_smoke_reproduced_chrome/desktop.png) and [mobile](../browser_smoke_reproduced_chrome/mobile.png) screenshots use fictional demo customers; the mobile page had no page-level horizontal overflow.

Both runs checked keyboard activation of the demo, snapshot preview, a real-model plan, visible causal limitation, a late API response after an assumption change, a focused model-unavailable error, invalid CSV line/field and quote feedback, unsupported category and structural conflict, duplicate customer IDs, clearing a stale draft, ignored `Churn` target column, a zero-contact plan including a zero money cap, browser JSON download, and deterministic replay of that downloaded packet. No uncaught page errors were recorded.

The first browser pass on the archived champion bundle is retained at [Chrome](../browser_smoke/result.json) and [Edge](../browser_smoke_edge/result.json). These are separate checks, not evidence that the bundles are equivalent.

This automated check does not establish screen-reader accessibility or first-user comprehension. The [completion plan](../../../docs/REMAINING_GAPS_AND_COMPLETION_PLAN_2026_EN.md) keeps those tasks open.
