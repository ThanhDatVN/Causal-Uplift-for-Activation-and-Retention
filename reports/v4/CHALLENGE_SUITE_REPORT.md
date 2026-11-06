# E28 challenge suite

Each row builds a clean fixture and a deliberately broken copy of it. `clean_passes` is the false-block check; `mutant_detected` is the falsification check. A pass means the declared fault was caught, not that the pipeline is safe against faults nobody wrote down.

- declared mutations: 24
- executed: 24
- critical detection: 21/21 (100%)
- false blocks: 0
- gate: PASS

| ID | Node | Severity | Mutation | Detector | Clean | Detected |
|---|---|---|---|---|---|---|
| Q01 | N05 | critical | Churn-prevention sign inverted or arms swapped | `hand_computed_ate_identity` | ok | yes |
| Q02 | N01 | critical | Constant propensity under a stratified design | `design_probability_vs_known_truth` | ok | yes |
| Q03 | N03 | critical | Feature event before the snapshot, available after it | `point_in_time_gate` | ok | yes |
| Q04 | N03 | major | Imputer fitted on the evaluation batch | `batch_chunk_invariance` | ok | yes |
| Q05 | N08 | critical | Duplicate assignment after an export retry | `posting_idempotency_gate` | ok | yes |
| Q06 | N02 | critical | Immature or missing outcome recorded as zero | `maturity_and_adjudication_gate` | ok | yes |
| Q07 | N02 | critical | Delivered-only filter applied after randomization | `itt_cohort_reconciliation` | ok | yes |
| Q08 | N07 | critical | Offer cost subtracted twice | `ledger_identity_tiny_example` | ok | yes |
| Q09 | N06 | critical | Identical policies given a positive contrast SE | `paired_contrast_identity` | ok | yes |
| Q10 | N06 | major | Customer-months pooled as independent accounts | `unit_manifest_and_cluster_variance` | ok | yes |
| Q11 | N06 | critical | Enriched sampling without the inclusion weight | `sampling_contract_known_truth` | ok | yes |
| Q12 | N05 | critical | Candidate selects an action with no logged support | `support_gate` | ok | yes |
| Q13 | N06 | critical | Candidates tuned against the confirmation split | `data_role_access_ledger` | ok | yes |
| Q14 | N03 | critical | Future or oracle column propagated through a rename | `column_lineage_gate` | ok | yes |
| Q15 | N10 | major | Tie-break depends on row order | `stable_tie_break_reproducibility` | ok | yes |
| Q16 | N07 | critical | Allocation breaches capacity or cooldown at a boundary | `independent_feasibility_checker` | ok | yes |
| Q17 | N08 | critical | Subprocess exits non-zero but the runner reports success | `stage_failure_propagation` | ok | yes |
| Q18 | N10 | critical | Stale bundle loaded against a moved contract | `bundle_compatibility_gate` | ok | yes |
| Q19 | N01 | critical | Known design probability silently replaced by a floor | `propensity_support_contract` | ok | yes |
| Q20 | N06 | critical | Nuisance frames joined by position after a row shuffle | `row_key_join_contract` | ok | yes |
| Q21 | N06 | critical | Census recruitment reported as zero uncertainty | `recruitment_variance_decomposition` | ok | yes |
| Q22 | N08 | critical | Artifact from an earlier run certifies this one | `artifact_freshness_gate` | ok | yes |
| Q23 | N08 | critical | Stage timeout loses the run manifest | `timeout_manifest_contract` | ok | yes |
| Q24 | N00 | critical | Currency reward attached to an event endpoint | `endpoint_unit_contract` | ok | yes |

## Evidence per mutation

### Q01 — Churn-prevention sign inverted or arms swapped

- clean: prevented-churn ATE +0.5000 matches the hand calculation
- mutant: swapped arms give -0.5000, opposite sign

### Q02 — Constant propensity under a stratified design

- clean: design propensities recover the true zero effect (+4.4e-17)
- mutant: a constant 0.5 propensity reports -0.2400 where truth is 0

### Q03 — Feature event before the snapshot, available after it

- clean: clean fixture accepted
- mutant: 1 feature rows were not available at the decision instant; first offenders:
account_id    feature_name                 reason
        a1 arrears_balance available_after_cutoff

### Q04 — Imputer fitted on the evaluation batch

- clean: fit-time fill values give an identical transform (gap 0)
- mutant: batch-fitted medians move an imputed value by 49.5

### Q05 — Duplicate assignment after an export retry

- clean: clean fixture accepted
- mutant: posting 'p1' was already recorded; an export retry must be idempotent, not a second charge

### Q06 — Immature or missing outcome recorded as zero

- clean: 5 immature rows stay missing, none become zero
- mutant: the naive label turns 5 immature rows into survivors

### Q07 — Delivered-only filter applied after randomization

- clean: clean fixture accepted
- mutant: 3 accounts with informative labels were dropped from a promotable analysis cohort; the ITT denominator no longer reconciles

### Q08 — Offer cost subtracted twice

- clean: clean fixture accepted
- mutant: ledger total 70.0 does not match the independently computed 80.0

### Q09 — Identical policies given a positive contrast SE

- clean: paired delta 0 with SE 0
- mutant: unpaired analysis reports SE 0.1000 for a zero contrast

### Q10 — Customer-months pooled as independent accounts

- clean: cluster-robust SE 0.2143 over 20 clusters
- mutant: pooling customer-months shrinks the SE by 3.2x

### Q11 — Enriched sampling without the inclusion weight

- clean: Horvitz-Thompson delta 0.5000 equals the frame truth
- mutant: dropping 1/q gives 0.4250 against a truth of 0.5000

### Q12 — Candidate selects an action with no logged support

- clean: clean fixture accepted
- mutant: policy_1_actions selects actions ['grace_extension'] that have no column in the score frame; an action without support may not be scored by imputation

### Q13 — Candidates tuned against the confirmation split

- clean: clean fixture accepted
- mutant: purpose 'model_selection' selects on outcomes and may not touch the confirmation split 'holdout'

### Q14 — Future or oracle column propagated through a rename

- clean: clean fixture accepted
- mutant: forbidden lineage reached the model: cust_score <- ['outcome_ledger']

### Q15 — Tie-break depends on row order

- clean: id-stable tie break selects ['a00', 'a01', 'a02'] under both orderings
- mutant: score-only ordering selects ['a00', 'a01', 'a02'] then ['a02', 'a07', 'a09']

### Q16 — Allocation breaches capacity or cooldown at a boundary

- clean: the feasible plan raises no constraint violation
- mutant: detected ['capacity_exceeded', 'cooldown_breached']

### Q17 — Subprocess exits non-zero but the runner reports success

- clean: a clean stage list reports COMPLETE with exit code 0
- mutant: exit code 3 propagates: status FAILED, 1 stage(s) recorded as skipped

### Q18 — Stale bundle loaded against a moved contract

- clean: clean fixture accepted
- mutant: bundle targets revision 1, contract is at revision 2; explicit migration and re-evaluation required

### Q19 — Known design probability silently replaced by a floor

- clean: unmodified design probability gives weight 2000.0 and reports ESS 1.00
- mutant: clipping moves the score to 1000.0 on 1 cell(s); the support contract refuses it: 1 realised action(s) have propensity below the declared support floor 0.001 at row key(s) 2; the contrast is out of support here and may not be estimated by clipping the design probability

### Q20 — Nuisance frames joined by position after a row shuffle

- clean: clean fixture accepted; an explicit row_key join restores the honest scores
- mutant: predicted_reward and propensity carry the same keys in a different order; align them with align_by_row_key(...) instead of relying on position

### Q21 — Census recruitment reported as zero uncertainty

- clean: under q=0.5 recruitment SE 0.0768 and total SE 0.1075 are both positive
- mutant: at q=1 the recruitment term is exactly 0 but the reported total SE stays 0.0760; a census removes sampling noise, not outcome noise

### Q22 — Artifact from an earlier run certifies this one

- clean: a stage that writes its declared artifact is SUCCESS
- mutant: a stage that exits 0 without rewriting it is STALE_ARTIFACT: ['leftover.json']

### Q23 — Stage timeout loses the run manifest

- clean: a stage inside its timeout completes normally
- mutant: the killed child is recorded as TIMED_OUT and the run manifest still lists it (timed out after 0.5s; partial output is not published)

### Q24 — Currency reward attached to an event endpoint

- clean: clean fixture accepted with a declared currency reward endpoint
- mutant: reward_unit 'net_contribution_currency_units' is not produced by any declared endpoint (['cancellation_events']); a currency reward on an event endpoint mixes two different measurements under one cont
