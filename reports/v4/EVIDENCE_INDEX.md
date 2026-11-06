# Evidence index

Generated 2026-10-02T01:15:48+00:00 from artifacts on disk. `NOT_MET` means the gate was defined and has not been satisfied; it is not a failure, and it is not a pass either.

- release tier: **ENGINEERING_FOUNDATION**
- failing gates: 0
- claim ledger tokens: OBSERVED 57, CONDITIONAL 6, PLANNED 5

## Gates

| Gate | Status | Summary | Blocker |
|---|---|---|---|
| Problem contracts validated | `PASS` | 4 contract revision(s) load and validate; 2 promotable, 2 declared negative control(s) | — |
| Declared mutations are caught | `PASS` | 21/21 critical mutations detected across 24 declared cases; 0 clean fixture(s) blocked. Covers declared faults only. | — |
| Runner propagates failure | `PASS` | last smoke run is COMPLETE over 5 stage(s); run_id 8e5775bc724842e3 | — |
| Dependency lock is present and satisfied | `PASS` | 180 packages locked for the research environment (3 lock file(s): research, api, console); live interpreter matches | — |
| Estimator coverage gate (R00/R01) | `NOT_MET` | reports/v4/validity_unshrunk/validity_suite.json: 9/9 declared scenarios at 2,000 worlds each; R00 identities pass; 0 undercovering mode(s), 0 false-promotion failure(s); negative controls fired: 4; independent confirmation: required; valid over: measured design region: asymmetry index up to 0.100 for the skewness_adjusted_t interval (measured over 18 cells at 1000 worlds each, but tightened from 0.584 because the transfer study saw a design fail at A = 0.100, its lowest clean level, so the licence stops strictly below that (28 out-of-sample designs at 1000 worlds each)); scenario-level region (coarse; ignores event rate and frame size): propensity imbalance up to 0.40 (V01, V02, V03, V04, V05, V05B, V06, B01, V07); no scenario failed | mechanical coverage passed, but the interval was selected after equally powered runs disagreed; independent confirmation is missing |
| Independent-domain replication (R10) | `PASS` | lenta SMS campaign (development): 60,000 units, 6,498 events, stages R02, R03, R05; 2/3 registered predictions held | registered predictions falsified: P2_configurations_stabilise; R04 not transferable: its representation factor is defined by Hillstrom's own columns and its cost model keys on a channel column Lenta lacks; running a different factorial under the same name would be a quiet substitution |
| Real-domain assignment diagnostics | `PASS` | Orange: AUC 0.6355, p 0.0099, ESS kept 0.0%; Hillstrom: AUC 0.4975, p 0.6832, ESS kept 99.9%; Lenta: AUC 0.5037, p 0.1765, ESS kept 97.9%. Assignment diagnostics passed: Hillstrom, Lenta; verify design probabilities separately | — |
| Declared candidates screened (R02) | `PASS` | 8 candidates completed, 0 failed on hillstrom Mens E-Mail vs No E-Mail (development); shortlist M01, M03, M07 | — |
| Deployment agrees with the host | `PASS` | 12/12 checks passed on 2026-09-21T02:40:23+00:00; host/container score gap 1.1e-16 | — |
| Prospective partner trial | `NOT_RUN` | no partner, no live campaign, no cost ledger | business validation needs an owner, a budget and a mature follow-up window |

## Artifacts

| Key | Path | Modified | Fresh vs code |
|---|---|---|---|
| contracts | `reports/v4/contracts.json` | 2026-09-21T08:54:14+00:00 | stale: src/telco_churn/problem_contract.py |
| challenge_suite | `reports/v4/challenge_suite.json` | 2026-09-21T06:56:18+00:00 | stale: src/telco_churn/challenge_suite.py |
| hillstrom_manifest | `reports/hillstrom/dataset_manifest.json` | 2026-09-21T05:41:19+00:00 | ok |
| screening | `reports/screening/screening.json` | 2026-09-21T08:54:22+00:00 | stale: src/telco_churn/screening.py, src/telco_churn/candidates.py |
| environment_lock | `locks/research.lock.txt` | 2026-09-21T02:57:54+00:00 | stale: src/telco_churn/environment.py |
| lenta_manifest | `reports/v4/lenta_manifest.json` | 2026-09-21T11:39:22+00:00 | stale: src/telco_churn/lenta_data.py |
| external_replication | `reports/v4/replication_lenta/external_replication.json` | 2026-09-21T12:30:14+00:00 | stale: src/telco_churn/external_replication.py, src/telco_churn/screening.py |
| assignment_audit_lenta | `reports/v4/assignment_audit_lenta.json` | 2026-09-21T11:55:34+00:00 | stale: src/telco_churn/assignment_audit.py |
| temporal_replay | `reports/v4/temporal_replay/temporal_replay.json` | 2026-09-21T11:32:41+00:00 | stale: src/telco_churn/temporal_replay.py |
| learning_curves | `reports/v4/learning_curves/learning_curves.json` | 2026-09-21T11:28:43+00:00 | stale: src/telco_churn/learning_curves.py |
| sampling_economics | `reports/v4/sampling_economics/sampling_economics.json` | 2026-09-21T11:33:24+00:00 | stale: src/telco_churn/sampling_economics.py, src/telco_churn/policy_comparison.py |
| selection_stress | `reports/v4/selection_stress/selection_stress.json` | 2026-09-21T11:28:17+00:00 | stale: src/telco_churn/selection_stress.py |
| component_factorial | `reports/v4/factorial/component_factorial.json` | 2026-09-21T11:23:52+00:00 | stale: src/telco_churn/component_factorial.py, src/telco_churn/candidates.py |
| bounded_tuning | `reports/v4/tuning/bounded_tuning.json` | 2026-09-21T11:21:43+00:00 | stale: src/telco_churn/bounded_tuning.py, src/telco_churn/candidates.py |
| validity_v08 | `reports/v4/validity_v08/v08_batch_cap.json` | 2026-09-21T11:39:49+00:00 | stale: src/telco_churn/batch_validation.py, src/telco_churn/policy_comparison.py |
| asymmetry_transfer | `reports/v4/asymmetry_transfer/asymmetry_transfer.json` | 2026-09-21T11:04:38+00:00 | stale: src/telco_churn/asymmetry_transfer.py, src/telco_churn/policy_comparison.py |
| figures | `reports/v4/figures/figures.json` | 2026-09-21T10:36:49+00:00 | stale: src/telco_churn/figures.py |
| overlap_boundary | `reports/v4/overlap_boundary/overlap_boundary.json` | 2026-09-21T10:35:56+00:00 | stale: src/telco_churn/overlap_boundary.py, src/telco_churn/policy_comparison.py |
| validity_v09 | `reports/v4/validity_v09/v09_recruitment.json` | 2026-09-21T07:33:02+00:00 | stale: src/telco_churn/recruitment_validation.py, src/telco_churn/policy_comparison.py |
| validity_suite | `reports/v4/validity/validity_suite.json` | 2026-09-21T06:38:29+00:00 | stale: src/telco_churn/validity_suite.py, src/telco_churn/policy_comparison.py |
| fresh_evaluator_diagnostic | `reports/v4/fresh_evaluator/FRESH_EVALUATOR.json` | 2026-09-28T17:44:44+00:00 | stale: src/telco_churn/policy_comparison.py |
| next_evaluator_transfer | `reports/v4/next_evaluator_transfer/TRANSFER_RESULT.json` | 2026-09-30T00:51:11+00:00 | ok |
| r1_repair_validation | `reports/v4/r1_repair_20261002/RESULT.json` | 2026-10-01T18:16:22+00:00 | ok |
| next_evaluator_negative_controls | `reports/v4/next_evaluator_transfer/NEGATIVE_CONTROL_RESULT.json` | 2026-09-30T01:10:03+00:00 | ok |
| r4_learner_mens | `reports/v4/learner_comparison/hillstrom_mens.json` | 2026-09-30T00:47:03+00:00 | ok |
| r4_learner_womens | `reports/v4/learner_comparison/hillstrom_womens.json` | 2026-09-30T00:47:14+00:00 | ok |
| r4_learner_lenta | `reports/v4/learner_comparison/lenta_sms.json` | 2026-09-30T00:55:40+00:00 | ok |
| r4_allocator | `reports/v4/exact_allocator_study/RESULT.json` | 2026-09-30T00:42:38+00:00 | ok |
| r4b_allocator_exploratory | `reports/v4/exact_allocator_study/r4b/RESULT.json` | 2026-09-30T00:45:40+00:00 | ok |
| inference_smoke | `reports/v4/inference_smoke.json` | 2026-09-21T06:57:42+00:00 | stale: src/telco_churn/inference_smoke.py, src/telco_churn/policy_comparison.py |
| inference_smoke_misspecified | `reports/v4/inference_smoke_misspecified.json` | 2026-09-21T01:07:13+00:00 | stale: src/telco_churn/inference_smoke.py |
| assignment_audit | `reports/v4/assignment_audit.json` | 2026-09-20T15:30:08+00:00 | stale: src/telco_churn/assignment_audit.py |
| assignment_audit_hillstrom | `reports/v4/assignment_audit_hillstrom.json` | 2026-09-21T07:05:44+00:00 | stale: src/telco_churn/assignment_audit.py |
| run_report | `reports/v4/run_report.json` | 2026-09-21T06:56:20+00:00 | stale: src/telco_churn/research_runner.py |
| orange_policy_decision | `reports/uplift/locked_policy_decision.json` | 2026-09-14T04:39:20+00:00 | stale: src/telco_churn/orange_benchmark.py |
| temporal_lab | `reports/temporal_lab/summary.json` | 2026-09-14T04:39:49+00:00 | stale: src/telco_churn/temporal_lab.py, src/telco_churn/simulation.py |
| predictive_benchmark | `reports/benchmark/BENCHMARK_REPORT.md` | 2026-09-13T13:31:15+00:00 | stale: src/telco_churn/train.py |
| planner_v2_browser | `reports/v4/browser_smoke_v2_20261002/result.json` | 2026-10-02T01:15:39+00:00 | ok |
| api_latency | `reports/api/latency.json` | 2026-09-21T01:03:32+00:00 | stale: src/telco_churn/api.py |
| deployment_smoke | `reports/deployment/deployment_smoke.json` | 2026-09-21T02:40:25+00:00 | stale: src/telco_churn/deployment_smoke.py |
| claim_ledger | `docs/CLAIM_LEDGER_V4.md` | 2026-09-21T12:31:12+00:00 | ok |

## What the next tier needs

- **RESEARCH_INTERIM** / `inference_coverage`: mechanical coverage passed, but the interval was selected after equally powered runs disagreed; independent confirmation is missing
