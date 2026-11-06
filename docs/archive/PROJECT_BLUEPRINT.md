# TelcoChurn Decision System Blueprint

## Executive decisions

1. Dùng IBM 21-column sample, không train bản 33-column có leakage-prone fields.
2. Product chính là **monthly batch decision support**; FastAPI là integration/demo surface, không
   phải lý do giả tạo để biến churn thành real-time problem.
3. Tách ba lớp đánh giá: ranking, calibrated probability, budget/cost decision.
4. Không dùng external score thiếu cùng split/protocol; khóa internal benchmark và báo uncertainty.
5. Churn propensity không phải uplift. Revenue/retention impact của sample luôn gắn nhãn simulated.
6. Logistic thắng mặc định; model phức tạp chỉ thắng khi AP tăng đủ và calibration không regression.
7. Toàn bộ benchmark v1 đã hoàn tất; Logistic được giữ làm champion theo gate đã khóa trước khi mở test.

IBM công bố một code pattern bao gồm load/visualize, preprocess, build/test và deploy model.[^1]
Blueprint này mở rộng pattern thành decision system có data/model cards, budget policy, uncertainty,
testing, lineage và causal guardrails.

## Outcome cần đạt

### Data Scientist Fresher evidence

- problem framing có entity, prediction point, horizon và action;
- data card/leakage audit/split protocol có thể bảo vệ;
- Dummy + Logistic baseline và champion comparison đúng CV;
- metric hierarchy gồm AP, ROC-AUC, Brier/calibration và top-K/lift;
- ≥15 case error analysis, importance stability, slice audit;
- cost simulation có assumptions và break-even, không claim causal ROI.

### ML Engineer Fresher evidence

- shared preprocessing/model bundle cho train/batch/API;
- MLflow lineage gồm code/data/split/config/model;
- Postgres audit schema và idempotent campaign decision;
- FastAPI validation, Docker compose, unit/integration/golden/container tests;
- GitHub Actions, one-command run, p95 có load/hardware context, rollback/model versioning.

### Portfolio value

Demo phải trả lời được: “Với ngân sách X, hệ thống chọn ai, vì sao, dựa trên model/version nào, bắt
được bao nhiêu churners trên test, xác suất có đáng tin không, và business claim nào chưa thể nói?”

## Work breakdown and gates

| Phase | Công việc | Required artifacts | Exit gate | Status |
|---|---|---|---|---|
| 0. Frame/research | dataset/benchmark/product/metric study | Blueprint, data card, benchmark, product design, curriculum | Scope và limitations nhất quán | Done |
| 1. Data/EDA | fetch+hash, schema/quality, cohorts/associations | EDA CLI/report/tables/figures/tests | 7.043 rows; known issues explained | Done |
| 2. Split/baseline | frozen manifest, Dummy, Logistic Pipeline | split hash, baseline MLflow run, metric table | no leakage; reproducible scores | Done |
| 3. Champion | HistGB/CatBoost, bounded tuning, ablations | CV runs, tuning plots, champion decision note | complexity gate applied | Done |
| 4. Calibration/policy | OOF calibration, top-K/cost engine | reliability/gains curves, scenario table, unit tests | no test tuning; assumptions versioned | Done |
| 5. Explain/audit | permutation/SHAP, errors, slices | ≥15 cases, stability and sensitive ablation | limitations/slice regressions published | Done |
| 6. Productize | Postgres, batch, API, MLflow bundle | migrations, API, tests, Docker, perf report | batch/API parity; p95 target | Done |
| 7. Communicate | README/model card/benchmark/demo/CV | one-command run, video, final CV bullet | clean-machine reproduction | Code/docs done; video pending |

Ước lượng 100–120 giờ theo giáo trình 10 tuần. Nếu chỉ có 6 tuần, giữ phases 0–5 + batch scorer; bỏ
UI và CatBoost trước khi bỏ leakage/calibration/tests.

## Deliverable tree cuối kỳ

```text
.
├── data/                         # raw ignored; manifests/version metadata tracked
├── docs/
│   ├── DATA_CARD.md
│   ├── BENCHMARK_PROTOCOL.md
│   ├── PRODUCT_DESIGN.md
│   ├── CURRICULUM.md
│   └── MODEL_CARD.md
├── reports/
│   ├── eda/
│   ├── benchmark/
│   ├── errors/
│   └── performance/
├── src/telco_churn/
│   ├── data.py
│   ├── features.py
│   ├── train.py
│   ├── evaluate.py
│   ├── calibrate.py
│   ├── policy.py
│   ├── batch.py
│   └── api/
├── sql/                          # migrations + analytical queries
├── tests/                        # unit/data/model/integration/golden
├── Dockerfile
├── compose.yaml
├── Makefile / scripts/*.ps1
└── .github/workflows/ci.yml
```

## Refined CV-ready checklist

| # | Evidence, không chỉ checkbox | Pass condition | Hiện tại |
|---:|---|---|---|
| 1 | Problem/prediction point/cost model | Timeline + action + simulation label | Pass |
| 2 | Data card/schema/split/leakage | source/hash/license, manifest, point-in-time audit | Pass |
| 3 | Dummy + Logistic baseline | Pipeline, CV distribution, frozen config | Pass |
| 4 | Main model + tuning | bounded search, no outer-fold leakage, complexity gate | Pass |
| 5 | Calibration + budget policy | OOF calibrator, Brier/reliability, top-K/EV tests | Pass |
| 6 | Explainability + ≥15 errors | held-out/stability, anonymized taxonomy | Pass |
| 7 | FastAPI + tests | typed contract, 422 cases, batch/API golden parity | Pass |
| 8 | Docker + CI + one-command | clean build/smoke and Actions green | Pass locally; workflow defined |
| 9 | README/model card/benchmark | traceable metrics, limitations, scenario labels | Pass |
| 10 | Demo + CV bullet số thật | 3–5 min video; no placeholder/unqualified claim | Script + bullet pass; recording pending |

EDA không tự nâng CV-ready score vì checklist yêu cầu end-to-end evidence. Điều này tránh báo tiến độ
đẹp nhưng thiếu product completeness.

## Concrete success criteria

- Raw/schema: exact checksum; 0 silent coercions; data tests fail đúng input xấu.
- Reproducibility: metric rerun cùng code/data/split chênh ≤ `1e-12` nếu deterministic.
- Model: report all folds; champion gate AP ≥ logistic +0,01 CV mean và Brier regression ≤0,005.
- Policy: report Recall/Precision/Lift tại 5/10/20/30%; cost sensitivity và break-even.
- Reliability: paired 95% bootstrap CI; slice n và uncertainty.
- Engineering: 100% tests cho critical policy functions; batch/API score parity; container smoke.
- Performance: warm p95 <100 ms single-row trên declared local setup; no error/1.000 valid requests.
- Communication: mọi số trong README/CV link được tới machine-readable artifact.

Các threshold là project-level quality gates, không phải industry standards. Scikit-learn khuyến nghị
chọn scoring theo ultimate goal và tách prediction khỏi decision.[^2]

## EDA outcome and decisions

EDA tái lập đã tìm thấy 26,54% churn; Dummy most-frequent vì vậy có accuracy 73,46% nhưng recall 0.
Đây là bằng chứng trực tiếp để không dùng accuracy làm primary. `Contract` có Cramér's V 0,410;
cohort 0–6 tháng + month-to-month có churn 55,2% (n=1.413). Các số này sinh hypothesis cho modeling,
không chứng minh đổi contract hay discount sẽ giảm churn.

11 `TotalCharges` blanks đều ở tenure 0, nên giữ và fill 0 có điều kiện trong pipeline; xóa chúng sẽ
loại đúng cohort khách mới. Dataset không có timestamp/treatment; out-of-time và uplift vẫn là
production gaps bắt buộc ghi trong model card.

## Major risks and mitigations

| Risk | Consequence | Mitigation / evidence |
|---|---|---|
| Snapshot fictional, no time | optimistic generalization | random split labeled proxy; require real temporal data next. |
| No treatment/control | false “retention saved” claim | scenario-only EV; design outcome table/RCT future. |
| Small n | noisy model/slice results | repeated CV, bootstrap, limit tuning/model complexity. |
| Public benchmark contamination | inflated comparison | own frozen protocol; no cross-repo score claim. |
| Sensitive/proxy features | inequitable targeting/reason codes | ablation, slice calibration/selection, allowlisted reasons. |
| Training-serving skew | API differs from notebook | shared bundle, golden parity, schema version; monitor skew.[^3] |
| Portfolio overengineering | unfinished project | batch MVP first; logistic can be champion; UI/K8s excluded. |

## Final artifact standards

Data card follows the transparency purpose of Datasheets for Datasets.[^4] Model card ghi intended
use, out-of-scope uses, evaluation conditions, subgroup results và limitations theo Model Cards for
Model Reporting.[^5] CI/testing/container guides dùng nguồn chính thức. Research references ưu tiên
IBM, SIGKDD, papers gốc và official documentation.

## CV bullet đã đo

> Built a leak-free churn decision system on 7,043 IBM sample customer records; benchmarked six model
> variants with repeated 5×3 CV and a frozen test, retained a simpler Logistic model at 0.640 Average
> Precision and 0.134 Brier score under a predeclared complexity gate, captured 27.0% of churners at a
> 10% contact budget (2.70× lift), and served identical batch/Docker FastAPI predictions at localhost
> p95 22.79 ms over 1,000 requests with zero errors. Business value was scenario-based, not causal.

## Sources

[^1]: IBM, “[Predict Customer Churn using Watson Machine Learning and Jupyter Notebooks on Cloud Pak for Data](https://github.com/IBM/telco-customer-churn-on-icp4d).”
[^2]: scikit-learn, “[Metrics and scoring: Which scoring function should I use?](https://scikit-learn.org/stable/modules/model_evaluation.html#which-scoring-function-should-i-use).”
[^3]: Martin Zinkevich, “[Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml),” Google for Developers.
[^4]: Timnit Gebru et al., “[Datasheets for Datasets](https://arxiv.org/abs/1803.09010),” Communications of the ACM, 2021.
[^5]: Margaret Mitchell et al., “[Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993),” FAccT, 2019.
