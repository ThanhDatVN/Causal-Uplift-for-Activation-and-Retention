# Notebook pipeline and experiment registry

Mỗi notebook có một decision boundary. Notebook không được vừa khám phá test, vừa tune, vừa viết kết
luận production. Training logic nằm trong package; notebook gọi/đọc versioned artifacts để tránh hai
implementation khác nhau giữa demo và pipeline.

## Thứ tự chạy

| ID | Notebook | Mục tiêu | Trạng thái |
|---:|---|---|---|
| 00 | `00_problem_and_experiment_contract.ipynb` | entity/action/outcome/horizon/cost/gates | thiết kế trong docs; tạo khi có company schema |
| 01 | `01_data_audit_eda.ipynb` | IBM provenance, schema, missing, associations/cohorts | executed |
| 02 | `02_leak_free_processing.ipynb` | frozen split, in-fold transforms, unknown category, parity | executed |
| 03 | `03_orange_causal_audit.ipynb` | RCT integrity, ATE, MDE, OOF, locked holdout | executed |
| 04 | `04_temporal_policy_lab.ipynb` | point-in-time panel, drift, true CATE/value/regret | executed |
| 05 | `05_model_stability_and_tuning.ipynb` | repeated seeds, X-learner, ablations, one-SE tuning | executed |
| 06 | `06_policy_value_and_failure_analysis.ipynb` | IPW/DR disagreement, break-even, no-contact, harm | executed |
| 07 | `07_external_validation.ipynb` | UCI Iranian/KKBox adapters và OOT transfer | planned, cần fetch/terms |
| 08 | `08_batch_api_data_contract.ipynb` | bundle/schema/batch/API/golden/perf | predictive path implemented; notebook planned |
| 09 | `09_monitoring_and_rolling_experiments.ipynb` | SRM, drift, delayed OPE, challenger gates | rolling mock implemented; production data needed |
| 10 | `10_executive_decision_report.ipynb` | claim ledger, go/no-go, demo/CV evidence | report docs implemented; notebook optional |

## 00 — Problem and experiment contract

Inputs cần có trước code: randomization unit, eligible population, `snapshot_at`, actions/offer IDs,
propensity, primary/guardrail outcomes, label maturity, value horizon, cost owner và kill criteria.

Không train nếu thiếu một trong: treatment semantics, control definition, outcome availability hoặc
decision sẽ thay đổi theo kết quả. Output: signed Markdown/YAML contract, estimand table và DAG.

## 01 — IBM data audit/EDA

### Xử lý dữ liệu

- khóa raw SHA-256, exact schema và unique `customerID`;
- parse `TotalCharges`; 11 blank phải hiện thành semantic new-tenure cases, không silently fill;
- audit impossible service combinations và target distribution;
- associations báo effect size/CI/q-value, không causal language.

### Thử nghiệm

- churn rate theo contract/tenure/internet/payment;
- numeric distributions theo target;
- missing mechanism và duplicate tests;
- cohort `tenure × contract`, minimum N gate.

Exit: data card + schema tests + EDA report; không chọn feature bằng full-data p-value cho model.

## 02 — Leak-free processing and predictive baseline

### Candidates

Dummy prior/most-frequent, Logistic, Logistic bỏ sensitive fields, HistGB, CatBoost.

### Tuning

Pipeline/ColumnTransformer fit trong fold; repeated 5×3 CV; randomized search development-only;
calibration none/sigmoid/isotonic bằng OOF; complexity gate đòi CV AP +0,01 và Brier không xấu >0,005.

### Metrics/gates

Primary AP; Brier skill/calibration; ROC-AUC supporting; precision/recall/lift@5/10/20/30%; paired
bootstrap vs logistic. Frozen test chỉ mở sau champion. Output: immutable model bundle + MLflow lineage.

## 03 — Orange causal audit

### Data processing

- ARFF parser, MD5, 160 PC/18 factors, binary `t/y`, 0 missing;
- joint `(t,y)` frozen split; no time/customer IDs nên limitation bắt buộc;
- treatment/control arm rates, SMD/category balance, event counts.

### Experiments

- risk Logistic/RF;
- S-HGB, T-Logistic/RF/HGB, DR-HGB, X-HGB;
- common cross-fitted Logistic nuisance for DR evaluation;
- IPW sensitivity; AUUC/Qini convention riêng được khóa;
- model/capacity chọn trên OOF, one locked holdout.

### Gate

DR và IPW lower CI >0, Qini >0, ≥20 churn events mỗi selected arm. Hiện tại fail → `NO_LAUNCH`.

## 04 — Temporal known-counterfactual lab

### Generator/data handling

Customer-month snapshot trước action; 18 months; randomized propensity 0,5; churned customer rời risk
set; price/outage/offer-fatigue drift; `true_*` nằm audit-only.

### Experiments

- invalid mixed-time row random vs valid out-of-time;
- risk/S/T/DR/X policies, value-aware versions, random/no-contact/oracles;
- PEHE/bias/Spearman vì true CATE biết được;
- policy truth: prevented churn, net value, harm share, regret;
- train 0–11, validation 12–14, locked test 15–17 và monthly rolling refit.

### Gate

DR-estimated value lower cluster-robust CI >0; nếu không, no-contact. Không dùng oracle để select.

## 05 — Stability and tuning

### Hypotheses

- H1: X-learner giảm variance do 75/25 arm imbalance.
- H2: causal model phải thắng risk-logistic ở phần lớn repeated seeds.
- H3: feature compression/regularization cải thiện ổn định thay vì lucky Qini.

### Implemented matrix

- 5 repeats × 3 folds, development-only: risk/T/S/DR/X + random;
- full tournament: 14 candidates gồm risk/S/T/TO/DR/R/X với Logistic/RF/HGB/CatBoost/ExtraTrees;
- component ablation: common nuisance Logistic/HGB/CatBoost, worst-evaluator Qini robustness;
- metrics: Qini DR/IPW mean/std, positive rate, mean rank, uplift@20 stability, beats-risk rate;
- risk Logistic tuning: 4 feature sets × 6 C × 3 repeats × 3 folds = 24 configurations;
- one-standard-error rule chọn simplest config còn trong tolerance.

### Current decision

Risk-logistic mean Qini-DR 0,002668, dương 5/5, rank 1,0. X-HGB mean 0,000008, dương 2/5 và thắng
risk 0/5. S-HGB có IPW mean dương nhưng DR mean âm: reject vì estimator disagreement. Tuning giữ
`all_178, C=0.3` theo one-SE; không đổi locked champion vì holdout đã mở, challenger cần future campaign.
Chi tiết protocol và stop rule nằm trong `docs/archive/MODEL_TOURNAMENT.md`.

## 06 — Policy value and failure analysis

### Câu hỏi

- Model ranking tốt có tạo value ở capacity thực tế không?
- IPW, DR và raw arm difference có cùng dấu không?
- contact cost tối đa theo uncertainty là bao nhiêu?
- no-contact có thắng khi lower bound âm không?
- policy chọn harmful segments bao nhiêu trong known-truth lab?

### Outputs

Budget-by-model matrix; estimator disagreement flags; break-even sensitivity theo `V`; true marginal
value/harm/regret trên mock; failure taxonomy: low events, sign flip, calibration drift, effect drift,
cost domination, oracle gap.

## 07 — External validation

### Dataset order

1. UCI Iranian: 3.150 rows, 9-month aggregates, 3-month planning gap; predictive external probe.
2. Criteo unbiased: 13,98M; causal rare-event/scale probe, không telco claim.
3. KKBox: temporal transaction/user logs nếu Kaggle terms cho phép.

Mỗi adapter phải trả feature list, treatment/outcome (optional), unit/time, propensity (optional),
license/source hash. Không map metric giữa dataset nếu estimand/horizon khác.

## 08 — Batch/API/data contract

Tests: invalid schema/enums/ranges, unknown category, 1/100/1000 payloads, batch/API/Docker golden parity,
artifact metadata, non-root image, p50/p95/p99 với concurrency/hardware. Không benchmark model training
trong request path. API chỉ preview/score, không tự action.

## 09 — Monitoring and continuous experiments

Mỗi window: SRM/propensity/delivery, feature/score/selection drift, calibration, ATE/IPW/DR, uplift/value,
guardrails, event counts/effective N. Ba trạng thái: promote challenger, keep current/continue exploration,
no-launch/rollback. PSI chỉ triage; outcome/policy degradation mới quyết định.

## 10 — Executive decision report

Một trang phải có: decision, population/action/horizon, data period, model/policy version, capacity,
primary estimate + CI/events, value/break-even, guardrails, stability, limitations, next experiment and
owner. Claim ledger liên kết mọi số tới CSV/JSON; không copy số thủ công từ notebook output.

## Quy tắc tuning chung

1. Viết hypothesis và primary metric trước khi chạy.
2. Preprocessing/nuisance/calibration fit trong training fold.
3. Tuning dùng development OOF hoặc inner temporal folds; test không được search.
4. Báo distribution qua seeds/folds/months, không chỉ best mean.
5. Dùng one-SE/complexity gate khi performance tương đương.
6. Không promote nếu IPW/DR khác dấu hoặc value/guardrail không pass.
7. Sau khi holdout mở, mọi tuning mới là future challenger; cần new future holdout/campaign.
8. Log rejected configs và lý do, không chỉ winner.
