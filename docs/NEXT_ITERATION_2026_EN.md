# Next implementation iteration: hard caps, scenario sensitivity, and evaluator transfer

> **Finalization update, 29 September 2026:** The planner packet now includes input records and can be checked with `python -m telco_churn.replay --packet PATH --model PATH`. The lock capture handles local distributions that shadow global packages. CI checks formatting for `src`, `tests`, and `scripts`, and runs exact-lock verification separately from the generic test job. For current setup and remaining limits, use the [portfolio release guide](PORTFOLIO_RELEASE_2026_EN.md). The verification list below describes the earlier focused pass.

> **Later release status:** The refreshed [evidence index](../reports/v4/EVIDENCE_INDEX.md) now computes `ENGINEERING_FOUNDATION` from engineering gates. Causal evaluator confirmation and a partner trial remain unmet. Use the [current completion record](../reports/v4/portfolio_completion/IMPLEMENTATION_REPORT.md) for final test and browser evidence.

**Updated:** 29 September 2026. This page records work completed after the [project review](PROJECT_REVIEW_AND_EXPANSION_2026_EN.md). It distinguishes tested code from planned research.

## Shipped locally

The campaign planner now applies `floor(customer_count × contact_fraction)`, matching the repository's [hard-cap allocator](../src/telco_churn/allocation.py). For example, 8 customers at a 20% cap permit **one** contact; 1 customer at a 10% cap permits **zero**. An optional total cost cap further limits contacts using the assumed cost per contact. Zero-cost actions can still be chosen under a zero money cap because they spend nothing.

The preview API scores the snapshot once, then recalculates the policy at the chosen save rate and at five percentage points below and above it. These three values are **assumption sensitivity**, not a statistical confidence interval. The response now includes contact capacity, assumed contact spend, and reason counts. Each candidate has a stable rank and one reason: `selected`, `non_positive_value`, `contact_cap_reached`, or `cost_cap_reached`. Equal scores break ties by customer ID, so row order cannot change the decision. Nonfinite economics are rejected.

The [planner](../src/telco_churn/planner/index.html) displays the sensitivity readouts, skipped-customer reasons, and a full decision-audit CSV. The evidence JSON now includes all ranked candidates and sensitivity values. Its causal warning remains visible: the IBM snapshot does not measure offer response or actual campaign ROI. Historical report numbers created with the former ceiling rule are **archived results**; reproduce them with their original code before comparing totals.

The API and CSV planner now accept optional `contact_eligible` and `days_since_last_contact` fields. An analyst can set a contact cooldown from 0 to 365 days. A row marked ineligible is excluded before ranking; if a positive cooldown is requested, a row with missing contact history is also excluded. The audit distinguishes `not_eligible`, `cooldown_active`, and `missing_contact_history`. These are analyst-supplied fields, not inferred from IBM. When an eligibility flag is absent, no eligibility exclusion is applied; the response counts how many flags and histories were supplied.

## New research artifact

The [fresh evaluator runner](../src/telco_churn/fresh_evaluator.py) creates two distinct known-truth binary-outcome families and checks the already selected DR interval. The second family's specification and family-level gate were [registered](EVALUATOR_FAMILY2_PROTOCOL_EN.md) before running F04–F06. The run used 2,000 worlds per condition, 4,000 units per world, on CPU. The [report](../reports/v4/fresh_evaluator/FRESH_EVALUATOR_REPORT.md) gives selected-interval coverage `0.948`, `0.955`, `0.951`, `0.954`, `0.944`, and `0.957` across six conditions. All clear the project's cellwise coverage floor; both sharp-null false-promotion checks clear their threshold. The calculated family false-failure union bound is `0.001119` under ideal nominal behavior. The diagnostic is now listed in the generated [evidence index](../reports/v4/EVIDENCE_INDEX.md) without changing the release gate. Release tier remains `NONE`; the Hillstrom confirmation split remains closed.

Run it again with `python -m telco_churn.fresh_evaluator --worlds 2000 --n-units 4000`. Its generated data require no download or GPU. A 100-world run is explicitly marked `SMOKE_ONLY`.

## Verification and remaining work

- Relevant tests: `python -m pytest tests/test_batch_policy.py tests/test_inference.py tests/test_deployment.py tests/test_policy.py tests/test_api.py tests/test_fresh_evaluator.py -q` — **54 passed**.
- Evidence/dashboard tests: `python -m pytest tests/test_endpoints_and_evidence.py tests/test_dashboard.py -q` — **30 passed**.
- Ruff check and format check passed on six focused Python files; JavaScript syntax passed with `node --check`.
- The updated wheel contains the evaluator CLI and all planner assets.
- The local API with the real model bundle returned HTTP 200, enforced the cooldown and supplied eligibility flags, and returned all audit reasons. Static checking found no missing or duplicate planner DOM IDs; a Node check validated optional CSV parsing. Browser visual and keyboard interaction were not available in this tool environment.
- Repository-wide formatting and environment-lock gates reported in the [project review](PROJECT_REVIEW_AND_EXPANSION_2026_EN.md) remain open; `evidence.py` passes lint but remains historically unformatted. These focused checks are not a full green CI run.

The next research step is batch-cap/clustered evaluator validation and preregistered learner comparisons on development roles. The next product step is a first-user usability check and a documented campaign contract for the new analyst-supplied eligibility fields. GPU training is unnecessary for the current tabular baselines and evaluator simulations. If a later model comparison truly benefits from GPU, package the pinned source, input checksums, a Kaggle notebook, and a CPU baseline together before using its result as evidence.
