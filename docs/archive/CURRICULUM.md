# TelcoChurn Complete Curriculum

## Cách học và tiêu chuẩn đầu ra

Giáo trình 10 tuần, 10–12 giờ/tuần. Mỗi tuần chỉ “xong” khi artifact và oral defense pass; xem video
hay chạy notebook không tính là hoàn thành. Học viên phải giải thích được prediction point, leakage,
metric, calibration và causal limitation trước khi nói về model score.

| Tuần | Kiến thức phải học | Lab/deliverable | Exit criteria |
|---:|---|---|---|
| 0 | Python env, Git, package layout, typing, pytest, reproducibility | `pyproject`, CLI, test nhỏ, seed/version capture | Clone sạch → install/test được; giải thích package vs notebook. |
| 1 | Business framing, entity/label/horizon, prediction vs decision, cost/benefit, uplift | Problem brief + assumptions register + prediction contract | Vẽ timeline T/T+30; phân biệt churn risk với incremental treatment effect. |
| 2 | pandas, SQL profiling, missing/categorical semantics, data contracts, EDA vs causality | Data card, schema tests, SQL profiling, EDA report | Tìm đúng 11 blanks/0 duplicates; không gọi association là cause. |
| 3 | train/validation/test, stratification, CV, leakage, Pipeline/ColumnTransformer | Frozen split manifest; Dummy + Logistic pipeline | Không có `fit` trước split; reproduce metric từ seed/hash. |
| 4 | confusion matrix, AP/PR, ROC-AUC, Brier/log loss, calibration, top-K/lift, uncertainty | Metric functions + hand calculations + bootstrap | Tính tay một confusion matrix/top-K; giải thích AP ≠ trapezoidal PR-AUC. |
| 5 | trees/boosting, bias-variance, categorical handling, regularization, random search, early stopping | HistGB + CatBoost experiment matrix trong MLflow | Outer validation không dùng early stop/tune; champion rule áp dụng đúng. |
| 6 | probability calibration, OOF predictions, threshold/cost matrix, knapsack, sensitivity | Calibrator comparison + budget decision engine | Policy chọn trên dev OOF, không test; EV/break-even unit tests pass. |
| 7 | permutation/SHAP, correlated features, error taxonomy, slice/fairness audit | Importance stability + 15-case error report + sensitive ablation | Không diễn giải attribution là cause; nêu regression/risk theo slice. |
| 8 | SQL/Postgres design, MLflow lineage, model bundle, batch inference, monitoring | Tables/migrations + registered run + batch scorer | Query lineage từ decision về snapshot/model/assumptions. |
| 9 | FastAPI/Pydantic, Docker, unit/integration/golden/perf tests, CI/CD | API + compose + Actions + latency report | Clean build; invalid payload 422; batch/API parity; CI green. |
| 10 | Model/data cards, README, demo storytelling, CV evidence | Final benchmark, model card, 3–5 min video, CV bullet | Mọi số trace tới artifact; limitations/business simulation nói rõ. |

## Syllabus chi tiết

### Module A — Problem and decision science

Phải học: classification probability; decision theory; false-positive/false-negative cost; contact
capacity vs monetary budget; margin vs revenue; treatment effect/counterfactual; randomized
treatment/control. Bài tập: viết ba policy (threshold, top-K, EV-knapsack), nêu điều kiện để chúng
tương đương và phản ví dụ.

Tự kiểm tra:

- Tại sao rank người dễ churn chưa chắc là rank người có thể cứu?
- Khi nào calibration quan trọng dù ROC-AUC không đổi?
- Một `MonthlyCharges=100` có phải 100 lợi nhuận có nguy cơ mất không?

### Module B — Data engineering and EDA

Phải học: vectorized pandas; groupby/pivot; missing mechanisms; type coercion; keys/duplicates;
structural categories; Wilson interval; chi-square/Cramér's V; standardized mean difference; multiple
comparisons; point-in-time joins. Bài tập SQL: churn rate theo contract, rolling cohort, dedupe latest
snapshot với window function, assertions chống feature `available_at > snapshot_at`.

### Module C — Leak-free supervised learning

Phải học: logistic regression/log-odds/regularization; one-hot + unknown category; tree/boosting;
under/overfitting; CV variance; nested selection; class weights vs sampling; preprocessing trong
Pipeline. Không chọn model vì accuracy hoặc một lucky holdout.

### Module D — Evaluation and decisions

Phải học công thức và failure modes của precision, recall, specificity, F-beta, AP, ROC-AUC, Brier,
log loss, calibration slope/intercept, Recall/Precision/Lift@K, expected value. Thực hành paired
bootstrap và đọc CI như uncertainty, không như “pass p<0,05”. Scikit-learn nhấn mạnh metric phải bắt
đầu từ mục tiêu ứng dụng và tách prediction khỏi decision.[^1]

### Module E — Explainability and responsible ML

Phải học global vs local explanation, permutation importance, SHAP, correlated features, explanation
stability, segment vs individual error, proxy/sensitive features, intended/prohibited uses. Model cards
được thiết kế để ghi intended use, evaluation conditions và subgroup performance.[^2]

### Module F — ML engineering

Phải học experiment lineage (code/data/split/config/model), serialization safety, schema versioning,
idempotency, batch vs online, API validation, SQL transactions/indexes, Docker layers/non-root,
testing pyramid, CI, latency methodology, monitoring/rollback. MLflow autolog có thể ghi parameters,
metrics, models và CV child runs, nhưng custom business metrics/hashes vẫn phải log thủ công.[^3]

## Bài oral defense bắt buộc

1. Vẽ prediction timeline và chỉ ra vì sao IBM sample không chứng minh được timeline đó.
2. Từ 100 khách/20 churn, budget 10, tính Precision@10, Recall@10, Lift@10% bằng tay.
3. Giải thích model A ROC-AUC cao hơn nhưng Brier/Recall@budget thấp hơn thì chọn model nào.
4. Chứng minh một preprocessing fit toàn data gây leakage như thế nào.
5. Giải thích vì sao SMOTE trước split sai và vì sao SMOTE không bắt buộc với prevalence 26,5%.
6. Viết EV equation, liệt kê mọi assumption chưa quan sát trong IBM sample.
7. Phân biệt feature importance, reason code và causal driver.
8. Truy một campaign row về model version, split hash, source hash và assumptions.
9. Mô tả một rollback khi model ready nhưng p95 regression.
10. Bảo vệ CV bullet chỉ bằng số có artifact.

## Tài liệu học theo thứ tự

### Core statistics and ML

1. Gareth James et al., [An Introduction to Statistical Learning with Applications in Python](https://www.statlearning.com/) — classification, resampling, regularization, trees; có Python labs.[^4]
2. Inria/scikit-learn developers, [Machine Learning in Python with scikit-learn MOOC](https://inria.github.io/scikit-learn-mooc/) — tabular pipeline, tuning, nested CV và metrics; free/CC-BY.[^5]
3. scikit-learn, [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) — đọc trước khi viết baseline.
4. scikit-learn, [Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html), [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html), [Threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html).
5. Saito & Rehmsmeier, [Precision-Recall vs ROC](https://doi.org/10.1371/journal.pone.0118432); Davis & Goadrich, [relationship of PR and ROC](https://doi.org/10.1145/1143844.1143874).

### Data and tooling

6. pandas, [10 minutes to pandas](https://pandas.pydata.org/docs/user_guide/10min.html) rồi các phần missing/groupby/merge.[^6]
7. PostgreSQL, [official tutorial](https://www.postgresql.org/docs/current/tutorial.html) — SQL, joins, aggregates, transactions, window functions.
8. pytest, [Get started](https://docs.pytest.org/en/stable/getting-started.html).

### Models, explanation and MLOps

9. CatBoost, [categorical features](https://catboost.ai/docs/en/features/categorical-features) và [parameter tuning](https://catboost.ai/docs/en/concepts/parameter-tuning).
10. scikit-learn, [Permutation importance](https://scikit-learn.org/stable/modules/permutation_importance.html); SHAP, [documentation](https://shap.readthedocs.io/en/latest/).
11. MLflow, [scikit-learn integration](https://mlflow.org/docs/latest/ml/traditional-ml/sklearn) và [tracking](https://mlflow.org/docs/latest/ml/tracking/).
12. FastAPI, [testing](https://fastapi.tiangolo.com/tutorial/testing/) và [Docker deployment](https://fastapi.tiangolo.com/deployment/docker/).
13. Docker, [build best practices](https://docs.docker.com/build/building/best-practices/); GitHub, [building/testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
14. Google, [Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml) và [production monitoring](https://developers.google.com/machine-learning/crash-course/production-ml-systems/monitoring).

### Documentation and causal limitation

15. Gebru et al., [Datasheets for Datasets](https://arxiv.org/abs/1803.09010).[^7]
16. Mitchell et al., [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993).[^2]
17. Berrevoets et al., [Why you should stop predicting customer churn and start using uplift models](https://doi.org/10.1016/j.ins.2019.12.075).

## Definition of mastery

Học viên đạt mức fresher portfolio-ready khi có thể tự tái lập pipeline, phát hiện leakage, chọn metric
theo decision, diễn giải uncertainty, viết tests/API/SQL, và nói “chưa biết” đúng chỗ về causal impact.
Không yêu cầu deep learning, distributed compute hay Kubernetes cho sample 7k; thêm chúng làm tăng
surface area nhưng không tăng bằng chứng giá trị.

## Sources

[^1]: scikit-learn, “[Metrics and scoring: Which scoring function should I use?](https://scikit-learn.org/stable/modules/model_evaluation.html#which-scoring-function-should-i-use).”
[^2]: Margaret Mitchell et al., “[Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993),” FAccT, 2019.
[^3]: MLflow, “[Automatic Logging with MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/autolog).”
[^4]: Gareth James et al., “[An Introduction to Statistical Learning](https://www.statlearning.com/),” Python edition, 2023.
[^5]: Inria, “[Machine Learning in Python with scikit-learn](https://inria.github.io/scikit-learn-mooc/).”
[^6]: pandas, “[10 minutes to pandas](https://pandas.pydata.org/docs/user_guide/10min.html).”
[^7]: Timnit Gebru et al., “[Datasheets for Datasets](https://arxiv.org/abs/1803.09010),” Communications of the ACM 64(12), 2021.

