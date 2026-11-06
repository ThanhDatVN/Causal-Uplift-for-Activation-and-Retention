# Retention Decision Lab: review, experiments, and product roadmap

> **Implementation update, 29 September 2026:** The local planner now has eligibility, cooldown, a total money cap, sensitivity scenarios, a full decision audit, and a replayable evidence packet. Source/tests/scripts formatting has been normalized and CI scopes its checks accordingly. See the [current release guide](PORTFOLIO_RELEASE_2026_EN.md) and [implementation note](NEXT_ITERATION_2026_EN.md). The dated findings below document the review at the time it was written.

> **Evidence-index update:** The earlier environment mismatch described below was repaired locally. The refreshed [index](../reports/v4/EVIDENCE_INDEX.md) computes `ENGINEERING_FOUNDATION`; independent causal confirmation and a partner trial remain unmet. The historical review text is retained as an audit trail.

**Reviewed:** 28 September 2026  
**Audience:** junior ML Engineer, AI Engineer, and Data Scientist applicants  
**Evidence rule:** “Implemented” means code exists and a stated check ran. “Archived result” means a prior report, not a fresh replication. “Proposed” means no result is claimed.

**Further reading:** [Deep research map and experiment protocols](DEEP_RESEARCH_METHODS_EN.md) critically compares primary papers, data readiness, and seven proposed studies.

## Executive assessment

This is already a stronger research portfolio than a churn-classification notebook. It connects risk prediction, treatment-effect estimation, constrained allocation, simulation, an API, and an evidence console. Its most convincing result is methodological honesty: the Orange policy remains `NO_LAUNCH`, the Hillstrom comparison changes across branches, and the synthetic lab exposes harmful targeting under drift. The project should become a **reviewable retention-planning product** while preserving those limitations.

The first local product slice is now implemented at `/planner/`. An analyst can load eight fictional customers or a CSV, vary capacity and assumed economics, preview a ranked list, compare it with no contact, and export selected rows plus an evidence packet. This is a **risk plus assumptions** demo. It does not estimate a customer's causal response, measure ROI, or send a campaign. The separate research console remains the place to inspect causal studies.

## What the current evidence supports

| Track | Existing artifact | Supported claim | Limit |
|---|---|---|---|
| IBM predictive | [Benchmark report](../reports/benchmark/BENCHMARK_REPORT.md) | The frozen logistic model reported AP 0.6396, ROC-AUC 0.8499, Brier 0.1345; the top 10% risk group captured 27% of observed churners. | Static sample without timestamps or treatment. The API's historical `risk_30d` field name does not establish a validated 30-day horizon. |
| Orange treatment | [Locked policy](../reports/uplift/locked_policy_decision.json), [assignment audit](../reports/v4/ORANGE_ASSIGNMENT_AUDIT.md) | A small, uncertain effect and poor pooled assignment integrity justify `NO_LAUNCH`. | No campaign keys, actual contact costs, or credible individual effect truth. |
| Hillstrom | [Screening report](../reports/screening/SCREENING_REPORT.md), [R09 decision](R09_CONFIRMATION_DECISION.md) | Development comparisons can rank simple and causal learners on a randomized three-arm dataset. | Selection is unstable and the confirmation split remains unopened. |
| Lenta | [External replication](../reports/v4/replication_lenta/EXTERNAL_REPLICATION.md) | A larger, different retail domain changes the learner ranking. | One domain cannot establish a universal event-count threshold or telecom effect. |
| Synthetic temporal lab | [Temporal report](../reports/temporal_lab/TEMPORAL_LAB_REPORT.md) | Known counterfactuals permit direct regret and harmful-contact measurement under designed drift. | Simulated mechanisms are not observed business behavior. |

### Review findings and changes made in this pass

| Priority | Finding | Current action / exit criterion |
|---|---|---|
| P0 | A whole-suite validity PASS bypassed a supplied cohort's design boundary. | **Fixed** in `screening.gate_status`. A cohort now needs the measured design boundary even when the suite passed. The first transfer level that failed is excluded rather than accepted at equality. Regression cases cover out-of-region and licensed cohorts. This does not independently confirm the selected interval method. |
| P0 | The passing interval was selected after observing equally powered, disagreeing runs. | **Promotion fixed; research open.** The evidence gate now reports `NOT_MET` and blocks release-tier promotion when equal-power runs disagree. Freeze an interval recipe, then run new seeds before claiming independent confirmation. |
| P1 | Research console was useful to experts but did not let a new visitor complete a decision flow. | **First slice implemented:** local planner, CSV validation, assumptions, comparison, review, CSV/JSON exports. Next: moderated usability checks, eligibility/cooldown controls, and a reproducible product demo. |
| P1 | CI's repository-wide `ruff format --check .` fails on 65 existing files, including generated notebooks. | **Open.** Choose a canonical formatting scope and regenerate notebooks or exclude generated cells; then check from a clean checkout. A focused lint and test pass is not a CI pass. |
| P1 | Some evidence artifacts are older than their producer code, and the active environment may disagree with a research lock. | **Open.** Rebuild affected artifacts in a locked environment, record code and input digests, and show a visible “historical” label until rebuilt. |
| P2 | A single-record localhost latency result is narrower than a service-level promise. | **Open.** Measure cold start, batch sizes, concurrency, memory and p95/p99 on a named machine before stating operational targets. |

## Expanded decision problem

**User:** a retention analyst preparing a proposed contact list for human approval.  
**Unit and time zero:** an eligible, active customer at a documented snapshot cutoff.  
**Action:** no contact or one feasible retention offer.  
**Objective:** incremental retained margin minus delivery and offer costs subject to contact, money, eligibility, and fatigue limits.  
**Abstention:** no action when estimated incremental value is non-positive or identification, support, uncertainty, or data-integrity gates fail.

The current public data support separate demonstrations of risk, randomized treatment evaluation, and synthetic temporal behavior. They do **not** provide a single dataset containing telecom timestamps, randomized offers, actual costs, and mature outcomes. A real partner study would need those fields, plus consent, delivery logs, repeat-customer keys, and an untouched control group. Survival or delayed-outcome methods should wait for genuine event and censoring times; [scikit-survival's evaluation guide](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html) specifies time-dependent and censoring-aware metrics.

## Experiment contract for every new study

Before fitting, write a versioned registration with population, feature cutoff, treatment and outcome definitions, assignment mechanism, data roles, primary contrast, budget cap, cost provenance, seed, candidate list, compute limit, and stop rule. Fit all candidates on the same folds and rows. Keep one confirmation role untouched until the full selection algorithm and interval recipe are frozen. Report failed fits and negative results.

**Primary causal readout:** paired, whole-cohort policy-value difference at one fixed contact cap, with uncertainty for the *difference*, known propensity where available, treatment-arm event counts, effective sample size, and a no-action baseline. Report IPW as sensitivity to DR. Uplift curves and [RATE](https://grf-labs.github.io/grf/articles/rate.html) are secondary ranking diagnostics; a useful ranking score is not automatically a calibrated individual effect. For predictive work, report AP, Brier, log loss, reliability curve, precision/recall at cap, slice stability, runtime, and training/serving parity. Calibrate on data independent of model fitting, following [scikit-learn guidance](https://scikit-learn.org/stable/modules/calibration.html).

### Bounded experiment queue

| ID | Question and method | Data and comparator | Advance only if… |
|---|---|---|---|
| X01 · P0 | **Independent evaluator validation.** Freeze the interval recipe; test variable propensity, rare outcomes, repeated customers, batch caps, and deliberately broken negative controls on unseen generator seeds/families. | Known-truth simulator; current interval vs stratified/batch alternatives. | Coverage and false-promotion limits hold in the claimed design region; otherwise narrow the region. |
| X02 · P0 | **Reproducibility audit.** Rebuild one IBM run and one Hillstrom development result from pinned inputs. | Archived reports and hashes. | An independent clean environment reproduces declared metrics within tolerance and a complete manifest identifies code, inputs, model, and runtime. |
| X03 · P0 | **Simple vs complex effect ranking.** Compare M01 risk/control-outcome, S/T/DR learners with equal folds and compute. Add an X-learner only for a predeclared arm-imbalance condition; [EconML documents the relevant learner families](https://www.pywhy.org/EconML/reference.html). | Hillstrom and Lenta development sets; no action and M01. | A paired policy-value advantage survives uncertainty and domain/branch sensitivity. Publish inconclusive rank sets otherwise. |
| X04 · P1 | **Sample efficiency.** Cross total sample size, event count, treatment balance, and effect heterogeneity independently. | Known-effect simulation; M01, S/T/DR, optional X learner. | Complexity improves true regret in a measured region with acceptable variance and training cost. |
| X05 · P1 | **Direct allocation.** Compare positive-value ranking, exact optimization on small batches, and a shallow policy tree under contact/money/eligibility constraints. | Known-reward simulator first; randomized data only with valid design. | Constraint violations are zero and paired net-value gain covers implementation cost. |
| X06 · P1 | **Honest forest challenger.** One fixed honest causal-forest recipe, with no broad tuning sweep. [GRF documents honesty and RATE evaluation](https://grf-labs.github.io/grf/reference/causal_forest.html). | Higher-event randomized development data vs the best simple learner. | Value gain, uncertainty, and runtime all justify the model. |
| X07 · P1 | **Drift and refresh.** Freeze a model, simulate covariate/effect drift, then compare recalibration, retraining, and conservative abstention. | Synthetic temporal panel; no action and risk-only. | Lower true regret without unacceptable harmful contacts across predeclared mechanisms. |
| X08 · P2 | **Larger randomized stress test.** Inspect license, corrected data release and compute before adding Criteo; [the publisher documents leakage in the original release](https://ailab.criteo.com/criteo-uplift-prediction-dataset/). | Corrected Criteo release vs simple and causal policies. | Independent-domain ranking remains stable; report advertising units separately from telecom and retail. |
| X09 · P2 | **Grounded evidence assistant.** Use only versioned local reports and a fixed question set. Compare deterministic templates with retrieval plus generation. | Existing evidence index; human-graded answers. | Zero tested causal/ROI overclaims, valid source references, good refusal behavior, and acceptable latency/cost. |

Start with X01–X04 and X05. Add X06/X08 only after the simple baselines and evaluation are trustworthy. A larger model zoo without a fixed estimand and evaluation rule would make the portfolio harder to defend.

## Product plan and UX acceptance

**Now:** the planner runs with `python -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000` and opens at `http://127.0.0.1:8000/planner/`. It uses the deployed risk bundle and current scenario policy. It accepts at most 1,000 CSV rows and a 2 MB file. The evidence packet records source type, input hash, model version, assumptions, summary, and selected rows. The CSV is processed in the browser and sent to the local API for scoring. There is no authentication or public upload service.

**Next product iteration:** add a field-level schema preview, exclusion rules, total-money cap, sensitivity range over save-rate assumptions, and plain-language reasons a customer is skipped. Integrate artifact freshness and design-gate states into a typed study-result contract. Show a causal policy card only for a prevalidated experimental cohort, with endpoint, split role, uncertainty and launch gate visible. Run five first-time-user sessions and measure completion time, errors, and false interpretations. Keep keyboard focus, status messages, labels, and mobile layout aligned with [W3C form-feedback guidance](https://www.w3.org/WAI/tutorials/forms/notifications/).

**Later partner pilot:** prospective assignment and immutable control, action delivery records, cost ledger, mature outcomes, review/approval, monitoring and rollback. This is the condition for a measured business claim.

## What a junior portfolio release must demonstrate

| Hiring path | Five-minute proof | Interview-level discussion |
|---|---|---|
| ML Engineer | Clean install, one-command reproduction, versioned model and data, parity test, local API/planner, meaningful CI and latency context. | Why logistic remained the declared deployment choice despite a stronger archived CatBoost test AP; how invalid input or out-of-region cohorts fail closed. |
| Data Scientist | Exact estimand, immutable split roles, power/event counts, paired baselines, confidence intervals, negative controls, and a written result that rejects a favorite hypothesis. | Why churn risk differs from treatment response; why Hillstrom branches disagree and why Lenta is an external check rather than proof of a general rule. |
| AI Engineer | A narrow, cited evidence assistant only if X09 passes, alongside the current deterministic decision path. | Retrieval allowlist, artifact versioning, refusal tests, adversarial prompts, and why generated prose cannot promote simulated value into measured ROI. |

**Portfolio release gate:** a stranger can finish the fictional demo in under five minutes; current metrics link to artifacts and their split roles; one predictive and one causal-development report reproduce from a documented clean setup; CI is green; the evaluator refuses an out-of-region cohort; the exported plan can be regenerated from its packet; no interface suggests a causal or business-impact claim from the risk demo. Show a three-minute walkthrough, architecture diagram, model/data cards, and one honest failure case on the landing page.

## Suggested six-sprint sequence

1. **Correctness:** independent interval validation, evidence-tier separation, and CI formatting policy.
2. **Reproduction:** pinned data and environment, one IBM and one Hillstrom development run, current artifact registry.
3. **Planner usability:** schema preview, explanation, sensitivity ranges, export replay and five user sessions.
4. **Methods:** X03/X04 with fixed folds, compute and paired intervals; publish all contenders.
5. **Decision policy:** X05, drift replay, operational checks and explicit abstention.
6. **Portfolio:** concise English README, product walkthrough, screenshots, cards and optional X09 only after its evaluation gate.

### Verification of this update

Targeted API, screening, and evidence-index tests passed (67 tests); source lint and JavaScript syntax checks passed. A real-bundle local API preview returned HTTP 200, and a built wheel contained all three planner assets. Dashboard/deployment/environment checks had one failure: the active Python has setuptools 78.1.0 while `locks/research.lock.txt` pins 65.5.0. The current evidence index therefore reports release tier `NONE`; its coverage gate is `NOT_MET` because the selected interval lacks independent confirmation. The full research suite and model runs were not rerun in this pass. Browser interaction testing was unavailable in the current tool environment, so visual and usability acceptance remains open. The existing repository-wide format gate still fails on historical files; do not describe CI as green.
