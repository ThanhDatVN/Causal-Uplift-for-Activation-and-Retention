# Giáo trình 14 tuần — causal retention decision engineering

Khối lượng: 10–12 giờ/tuần. “Xong” nghĩa là artifact, test và oral defense đạt; xem video hoặc chạy lại
notebook không tính. Mục tiêu cuối không phải nhớ API mà tự thiết kế một decision system trung thực khi
model mới không thắng hoặc dữ liệu chưa đủ power.

| Tuần | Phải học | Lab/deliverable | Exit criteria đo được |
|---:|---|---|---|
| 0 | Python package, Git, env lock, seeds, pytest/Ruff | clean install + CLI + smoke CI | clone sạch chạy test; giải thích artifact lineage |
| 1 | Decision framing, entity/action/outcome/horizon, risk vs CATE vs value | one-page decision contract | vẽ timeline; nêu 3 estimands và prohibited claims |
| 2 | Data cards, checksum/license/schema, missing/duplicate semantics | IBM + Orange data cards | raw hash và license đúng; fail-fast corrupt file |
| 3 | Point-in-time joins, event/available time, label delay, planning gap | SQL customer-month view | test không feature nào available sau snapshot |
| 4 | EDA, effect size, multiple comparisons, rare outcomes | executed EDA notebooks | CI/effect size cạnh rate; không gọi association là cause |
| 5 | Logistic/tree/boosting, Pipeline, calibration, AP/Brier | IBM baseline/challengers | frozen test, complexity gate, calibration diagnostics |
| 6 | Randomized experiments, potential outcomes, ATE/ITT, SRM/balance | Orange integrity audit | tính ATE/SE/CI bằng tay; phân biệt assignment/delivery |
| 7 | Power/MDE, arm allocation, cluster/interference, non-compliance | experiment design memo | sample size từ minimum business effect, không post-hoc |
| 8 | S/T/X/R/DR learners, cross-fitting, overlap | OOF causal candidates | đúng sign `Y0-Y1`; nuisance không fit validation outcome |
| 9 | AUUC/Qini/uplift@K, IPW/DR, bootstrap/ESS | locked Orange benchmark | công thức/convention ghi rõ; uncertainty + event counts |
| 10 | Incremental value, break-even, knapsack, no-contact policy | policy engine | chọn 0 khi lower value CI ≤ 0; test tie/cost constraint |
| 11 | Temporal drift, survival/risk set, rolling-origin | synthetic temporal lab | row-random vs OOT; churned customer rời risk set |
| 12 | Batch/API/SQL/Docker/MLflow, parity/idempotency | decision bundle + service | batch/API parity; audit decision → data/model/policy |
| 13 | Monitoring, shadow/pilot/promotion, guardrails/rollback | monthly experiment playbook | SRM/drift/value/guardrail gates + rollback drill |
| 14 | Research writing, model card, demo/CV defense | final evidence pack | mọi claim trace tới artifact; no-launch được bảo vệ |

## Module 1 — thống kê dự báo

Phải nắm: conditional probability, log odds, regularization, bias/variance, stratified/group/temporal
split, cross-validation, class weights, AP vs ROC, Brier/log loss, calibration intercept/slope, bootstrap.

Bài tập bắt buộc:

1. Với prevalence 3%, chứng minh accuracy 97% có thể vô dụng.
2. So sánh AP 0,09 ở prevalence 0,04 và AP 0,12 ở prevalence 0,06 bằng AP lift; không kết luận từ AP thô.
3. Tạo leakage bằng fit encoder/imputer toàn data, sau đó viết test bắt lỗi.
4. Tính Brier skill so với constant-prevalence predictor.

Tài liệu: [ISLP](https://www.statlearning.com/),
[scikit-learn MOOC](https://inria.github.io/scikit-learn-mooc/),
[common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html), và Saito & Rehmsmeier về
[PR vs ROC](https://doi.org/10.1371/journal.pone.0118432).

## Module 2 — causal inference và experiment

Phải nắm: potential outcomes, consistency, SUTVA/interference, exchangeability/randomization, positivity,
ITT/ATT/TOT, ATE/CATE, confounding, propensity, SRM, blocking, power, non-compliance.

Bài tập:

1. Từ Orange counts 105/2.886 và 303/9.010, tính ATE prevented churn, SE và 95% CI.
2. Giải thích tại sao campaign randomize trong high-risk pool không external-valid cho full base.
3. Viết DAG cho assignment → delivery → acceptance → churn; chỉ ra biến post-treatment không được làm feature.
4. Thiết kế household cluster-RCT khi peer spillover tồn tại.

Tài liệu: Hernán & Robins,
[Causal Inference: What If](https://www.hsph.harvard.edu/miguel-hernan/causal-inference-book/);
Künzel et al., [meta-learners](https://doi.org/10.1073/pnas.1804597116);
Fernández-Loría & Provost, [causal classification](https://www.jmlr.org/papers/v23/19-480.html).

## Module 3 — uplift và off-policy evaluation

Phải tự suy ra đúng dấu:

```text
tau(x) = E[Y(0)-Y(1)|X=x]                     # churn prevented
IPW_i  = (1-T_i)Y_i/(1-e_i) - T_iY_i/e_i
DR_i   = m0-m1 + (1-T)(Y-m0)/(1-e) - T(Y-m1)/e
```

Phải biết AUUC/Qini là ranking proxy, không phải individual causal accuracy. Khi counterfactual thật chỉ
có trong simulation mới dùng PEHE. Với real RCT, báo curve + uplift@K + CI + stability; không gọi từng
customer là “persuadable” như ground truth.

Bài tập: đảo sign một lần để test phải fail; so IPW/DR; làm propensity extreme để thấy effective sample
size giảm; so outcome-risk với T/S/DR trên cùng OOF folds.

Tài liệu: Orange dataset paper,[^1] JMLR causal classification,[^2] và Kallus et al. về
[DR distributionally robust OPE](https://proceedings.mlr.press/v162/kallus22a.html).

## Module 4 — decision economics

Phải phân biệt revenue, gross margin, CLV, retained margin, offer redemption cost, call cost, capacity và
opportunity cost. Policy score phải phản ánh action-specific incremental value, không chỉ churn risk.

Bài tập:

- tính break-even contact cost khi uplift CI là [−1%, 4%]; giải thích vì sao không có cost dương được bảo đảm;
- tạo example high-risk/lost-cause và medium-risk/persuadable;
- giải top-K và knapsack khi cost heterogeneous;
- thêm `no_contact` và chứng minh nó thắng khi mọi lower CI âm.

Tài liệu: Lemmens & Gupta về
[profit-maximizing churn management](https://doi.org/10.1287/mksc.2020.1229) và Gubela & Lessmann về
[value-driven uplift metrics](https://doi.org/10.1016/j.dss.2021.113648).

## Module 5 — temporal ML và survival

Phải học snapshot/risk-set, censoring, discrete-time hazard, rolling-origin validation, feature/outcome
availability, retraining cadence, population/outcome/treatment-effect drift. Không chọn random split cho
customer-month.

Bài tập: reproduce mock regime change; kiểm tra churned user không còn row tương lai; so calibration
theo month; rolling refit; viết rollback trigger khi CATE sign flip.

UCI Iranian có 9 tháng feature aggregation + 3 tháng planning gap, là bài tập nhỏ tốt để bảo vệ timeline
contract.[^3]

## Module 6 — ML engineering và governance

Phải học data/model/policy versioning, immutable artifacts, schema evolution, batch idempotency, API
validation, SQL keys/transactions/window functions, Docker non-root, CI, latency methodology, privacy,
human approval, rollback.

Deliverable cuối:

- one-command data acquisition + checksum;
- executed notebooks;
- tests cho data/sign/leakage/policy/parity;
- model/data/policy cards;
- decision log replay;
- demo nêu cả kết quả âm và limitation.

Tài liệu: [PostgreSQL tutorial](https://www.postgresql.org/docs/current/tutorial.html),
[MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[Docker build best practices](https://docs.docker.com/build/building/best-practices/),
[Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml).

## Oral defense 15 câu

1. Tại sao risk, uplift và value có thể cho ba ranking khác nhau?
2. Orange estimate generalize tới population nào?
3. Tại sao treatment 75,74% làm control events trở thành bottleneck?
4. MDE khác CI thế nào? Tại sao không power từ observed effect trước experiment?
5. Tại sao AUUC convention phải ghi công thức?
6. Vì sao DR không đảm bảo finite-sample tốt hơn IPW?
7. OOF score bảo vệ model selection thế nào?
8. Vì sao report test mọi model chỉ được gọi exploratory sau khi lock một policy?
9. Khi outcome model có AP cao nhưng value policy âm, deploy gì?
10. `no_contact` là model hay action? Vì sao bắt buộc?
11. Mock ground truth chứng minh được gì và không chứng minh được gì?
12. Raw AP tăng sau drift có thể che vấn đề gì?
13. Assignment, contact và acceptance khác nhau ra sao trong causal graph?
14. Thiết kế cluster bootstrap theo unit nào?
15. Chỉ ra một headline number và truy nó về source hash/split/predictions/config.

## Mastery rubric

| Mức | Bằng chứng |
|---|---|
| Chưa đạt | chỉ notebook classifier/AUC, random split, simulated ROI gọi là thật |
| Fresher tốt | reproducible risk pipeline, calibration, API/tests, limitations đúng |
| Fresher nổi bật | real RCT uplift + OPE/CI/power + temporal mock + no-launch gate |
| Junior-ready | experiment/data contracts, rolling validation, value/guardrails, audit replay |
| Chưa được claim | production uplift/ROI cho tới khi có governed company RCT và real economics |

[^1]: Verhelst et al., “[A churn prediction dataset from the telecom sector](https://arxiv.org/abs/2312.07206).”
[^2]: Fernández-Loría & Provost, “[Causal Classification](https://www.jmlr.org/papers/v23/19-480.html),” JMLR 2022.
[^3]: UCI, “[Iranian Churn](https://archive.ics.uci.edu/dataset/563/iranian%2Bchurn%2Bdataset),” CC BY 4.0.
