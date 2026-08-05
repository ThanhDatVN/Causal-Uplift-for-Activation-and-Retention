# 10 — Sổ tay Thực thi Đầu-cuối (End-to-End Execution Playbook)

> **Đây là file vận hành chính.** Làm theo thứ tự từ trên xuống; không chuyển phase chỉ vì “đã viết
> code”. Mỗi phase chỉ hoàn tất khi có artifact, kiểm tra và kết luận gắn với metric hoặc
> evidence cụ thể.
>
> Các file còn lại trong thư mục này là tài liệu tham chiếu: product (`01`), research (`02`), architecture
> (`03`), experiment protocol (`04`), schedule (`05`), reading (`06`), source audit (`08`)
> và feasibility (`11`).

## 0. Đích đến và định nghĩa thành công

### Sản phẩm cuối

**Incremental Value Studio** là web app giúp growth/CRM manager trả lời:

> Với budget, treatment cost, margin assumption và horizon đã chọn, nên tác động lên ai để tối đa hóa
> **giá trị ròng tăng thêm do treatment**?

Không phải một dashboard “dự đoán ai sẽ mua”; không phải một notebook CLV; không phải chatbot tạo số.

### Evidence cuối cần có

| Bằng chứng | Ý nghĩa | Giá trị kiểm chứng |
|---|---|---|
| Data card + SQL/cleaning audit | Hiểu dữ liệu, grain, limitation và metric | Kiểm tra input và data-quality rule |
| Temporal CLV validation | Forecast tương lai mà không leakage | Kiểm tra khả năng dự báo ngoài thời gian |
| Causal/policy evaluation trên RCT | Đo tác động tăng thêm, không nhầm correlation với causation | Kiểm tra policy trên holdout |
| Semi-synthetic recovery | Có ground truth để test integration iCLV | Kiểm tra khả năng khôi phục effect/policy đã biết |
| Dashboard có scenario + CSV export | Biến analysis thành quyết định sử dụng được | Kiểm tra output theo budget/cost/horizon |
| Package, tests, Docker, CI, provenance | Biến model thành software tái lập được | Kiểm tra release trên môi trường khác |
| Report, video, decision log | Giải thích được trade-off và limitation | Kiểm tra claim khớp artifact |

### Thành công là gì?

Sau 5 tuần, một người lạ cần có thể clone repo, chạy demo, đổi budget/cost/horizon, xem policy khác
nhau, tải action list và hiểu chính xác số nào là forecast, causal estimate hay semi-synthetic truth.

Không gọi dự án là production deployment. Gọi là **production-minded, reproducible decisioning
application**.

## 1. Bản đồ tư duy phải nắm trước khi bắt đầu

| Khái niệm | Phải hiểu | Dự án dùng ở đâu | Sai lầm phải tránh |
|---|---|---|---|
| CATE | `E[Y(1)-Y(0) | X=x]`, không phải outcome của một cá nhân | targeting causal | nói “biết chắc khách A sẽ mua vì treatment” |
| CLV | forecast future customer value từ lịch sử transaction | Online Retail II | coi CLV dự báo là causal effect |
| `iCV_H` | value treatment tạo thêm trong horizon hữu hạn, trừ treatment cost | policy optimizer | gọi `H=14/90 ngày` là lifetime value |
| Potential outcomes | mỗi khách chỉ quan sát `Y(0)` hoặc `Y(1)` | causal interpretation | tạo individual ground truth giả từ dữ liệu RCT quan sát |
| RFM/BTYD | recency, frequency, customer age; probability alive và expected purchase | BG/NBD | random split transaction, leakage theo thời gian |
| Policy value | giá trị trung bình khi dùng rule target, không chỉ model score | direct/IPW/DR evaluation | chọn model chỉ vì Qini cao |
| Doubly robust | kết hợp outcome model và propensity; vẫn cần overlap/split đúng | policy evaluation | tin DR tự sửa mọi lỗi data/model |
| Provenance | biết số đến từ data/version/config/run nào | app + report | chart không run ID hoặc hard-code KPI |

**Quy tắc ngôn ngữ:**

- `observed revenue`: số đã xảy ra trong window dữ liệu;
- `forecasted CLV/revenue`: dự đoán tương lai từ transaction history;
- `incremental value`: chênh lệch causal estimate trong horizon quan sát;
- `projected incremental CLV`: ngoại suy, luôn kèm model assumptions;
- `semi-synthetic ground truth`: target do DGP sinh ra, không phải evidence từ campaign triển khai.

## 2. Giai đoạn 0 (Phase 0) — Đóng dự án causal hiện tại (giới hạn 2–3 ngày)

Không bắt đầu probabilistic/iCLV khi causal cũ chưa có release độc lập. Mục tiêu là có một checkpoint
để causal project có thể được đánh giá độc lập mà không phụ thuộc roadmap sau này.

Trước Day C1, đọc [`11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md`](11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md)
và qua remote-compute preflight. Causal Forest 50% không được xem là điều kiện release nếu hạ tầng không
qua gate; scope-out có số đo là quyết định đúng.

### Ngày C1 (Day C1) — Kiểm tra claim và artifact causal

**Làm gì**

1. Chạy toàn bộ test và lưu command/output/version.
2. Mở `README`, dashboard, report, slide; đối chiếu từng metric với file trong `output/`.
3. Sửa claim segmentation: code hiện tại có 3 nhóm CATE, không ghi 4 principal strata nếu chưa có hai
   potential-outcome predictions.
4. Lập `data_manifest` cho Criteo local: source URL, hash, schema, row count, treatment/outcome rate.

**Cần hiểu**

- Qini/AUUC đánh giá ranking uplift, không tự chứng minh revenue gain.
- Response baseline thắng causal learner trên Qini là finding hợp lệ; không chỉnh narrative để model phức
  tạp trông tốt hơn.

**Artifact phải có**

- `causal-v0.1` model/data card;
- report có source path cho mỗi headline metric;
- issue/decision log: Causal Forest `done` hoặc `scope-out` kèm lý do.

**Qua cổng khi**

- test green;
- không còn số không trace được;
- README/report/dashboard không mâu thuẫn.

**Rút ra được**

> Trên Criteo binary benchmark, causal ranking có tín hiệu; business value từ deployment chưa được chứng
> minh vì dataset không có revenue/longitudinal customer history.

### Ngày C2 (Day C2) — Đóng băng và phát hành causal

**Làm gì**

1. Freeze config, seed, output final và source version.
2. Tạo commit/tag `causal-v0.1`; ghi quickstart tái lập.
3. Tạo release note: model lineup, result, limitation, next question.

**Cần hiểu**

- Reproducibility là khả năng tái tạo quyết định/số liệu, không phải chỉ “code chạy”.
- Tag là mốc release: mọi thay đổi kết quả sau tag phải có version và changelog mới.

**Rút ra được**

> Causal v0.1 là product/evidence riêng; iCLV v1.0 là extension có protocol mới, không phải gộp số từ
> hai dataset khác nhau.

## 3. Giai đoạn 1 (Phase 1) — Nền tảng dữ liệu và CLV xác suất (Week 1, Day 1–6)

### Ngày 1 (Day 1) — Hợp đồng dữ liệu, thẻ nguồn và môi trường lập trình local

**Làm gì**

1. Đọc `02`, `03`, `04`, `08`; tạo `docs/data_cards/online_retail_ii.md`.
2. Viết data contract: transaction grain, customer key, timezone/date, currency, return rule, `net_revenue`,
   treatment fields (không có), target fields và PII policy.
3. Tạo package layout, `pyproject.toml`/lock, optional groups, `.env.example` nếu cần.
4. Viết loader xlsx → versioned parquet; tạo `data_manifest.json` với SHA-256 và raw/clean row count.

**Cần hiểu**

- Transaction row khác order row khác customer snapshot. Aggregate sai grain gây double counting.
- Online Retail II có `UnitPrice`, không có COGS: chỉ gọi `revenue` hoặc `revenue proxy`.

**Artifact/verification**

- data card, manifest, loader unit test;
- `validate-artifact`/schema check pass;
- parquet có cùng columns/types/range đã định nghĩa.

**Rút ra được**

> Ta có real retail transaction history cho forecasting, không có experimental evidence về campaign effect.

### Ngày 2 (Day 2) — Kiểm tra làm sạch và từ điển chỉ số

**Làm gì**

1. Quyết định xử lý cancellations, `CustomerID` missing, `Quantity <= 0`, non-positive price, duplicates,
   timezone và refunds.
2. Tạo SQL marts (DuckDB là đủ): `staging_transactions`, `customer_daily`, `customer_rfm`,
   `policy_candidates`.
3. Viết metric dictionary: `net_revenue`, order count, repeat purchase, active customer, calibration period,
   holdout period; mỗi metric có grain/window/exclusion.
4. Chạy sensitivity raw vs net-of-returns vs wholesale-flag/exclude.

**Cần hiểu**

- Cleaning không chỉ là kỹ thuật; nó thay đổi estimand/diễn giải monetary value.
- Wholesale behavior có thể làm CLV distribution khác retail customer; phải report, không che đi.

**Artifact/verification**

- `data_quality_report.md/html`, SQL queries, quality-check results;
- reconciliation: tổng revenue/order/customer trước-sau cleaning có bảng giải thích.

**Rút ra được**

> Bất kỳ forecast nào cũng phụ thuộc definition of value; không thể nói “CLV chính xác” khi return/wholesale
> policy chưa được cố định.

### Ngày 3 (Day 3) — Chia tập theo thời gian và RFM

**Làm gì**

1. Chọn calibration end date và holdout horizon; viết rolling cutoff generator.
2. Tạo RFM theo định nghĩa BTYD: frequency là repeat purchase, recency là first-to-last purchase, `T` là
   customer age tại cutoff.
3. Viết leakage tests: không transaction nào sau cutoff xuất hiện trong train feature.
4. Report số customer first seen trong holdout riêng.

**Cần hiểu**

- Random row split làm future transaction rơi vào train nên forecast giả tạo tốt.
- New customer prediction và existing-customer CLV là hai problem khác nhau.

**Artifact/verification**

- `rfm_train_test.parquet`, split config, test temporal leakage;
- chart calendar timeline cho calibration/holdout.

**Rút ra được**

> Performance có ý nghĩa chỉ khi dự báo sau cutoff; in-sample likelihood không phải business validation.

### Ngày 4 (Day 4) — EDA phục vụ quyết định model

**Làm gì**

1. Cohort chart: acquisition month, repeat rate, revenue distribution, interpurchase time.
2. Kiểm tra one-time buyer, outlier order, country/wholesale mix.
3. Chọn horizon 90/180/365 ngày theo length holdout thực tế.
4. Viết 3–5 finding và implication cho model/sensitivity.

**Cần hiểu**

- EDA phải liên kết mỗi biểu đồ với data-quality check hoặc model assumption; không tạo biểu
  đồ nếu chưa xác định câu hỏi phân tích.
- Distribution tail và cohort shift có thể làm mean CLV misleading; thêm median/quantiles/cohort views.

**Artifact/verification**

- notebook/report có figures từ versioned data;
- mỗi chart có takeaway và next action.

**Rút ra được**

> Chọn model/metric dựa trên data-generating behavior, không theo tên thuật toán phổ biến.

### Ngày 5 (Day 5) — Đường cơ sở BG/NBD (BG/NBD Baseline)

**Làm gì**

1. Fit BG/NBD trên calibration RFM.
2. Predict expected purchase count và probability alive trong holdout.
3. So với historical recency/frequency baseline.
4. Evaluate MAE/RMSE/deviance, calibration theo frequency cohort và temporal cutoff.

**Cần hiểu**

- BG/NBD model purchase process và latent dropout, không biết campaign treatment.
- “Probability alive” là posterior model quantity, không phải nhãn quan sát.

**Artifact/verification**

- `clv_frequency_validation.csv`, model config, fit diagnostics, calibration plots;
- baseline table có cả metric và runtime.

**Rút ra được**

> Ta biết forecast repeat behavior tốt tới đâu, ổn định hay không qua thời gian; chưa biết khách nào nên
> nhận treatment.

### Ngày 6 (Day 6) — Gamma-Gamma và quyết định tuần 1 (Week-1 Decision)

**Làm gì**

1. Kiểm tra frequency–monetary relation; ghi rõ diagnostic và cohort excluded.
2. Fit Gamma-Gamma cho nhóm có repeat purchase; combine với expected purchases.
3. Evaluate holdout revenue/value; rank correlation, WAPE/MAE, cohort calibration.
4. Chọn Week-1 champion baseline hoặc ghi rõ model chưa đủ tốt.

**Cần hiểu**

- Monetary model dùng mean repeat value, không phải total spend.
- Forecasted CLV phải có horizon/currency; nếu no COGS thì không gọi profit.

**Artifact/verification**

- `customer_clv_predictions.parquet`, model card v0.2 draft, Week-1 decision log.

**Rút ra được**

> Predicted future customer value là một business baseline hữu ích, nhưng không đo incremental value do
> intervention.

## 4. Giai đoạn 2 (Phase 2) — CLV vững chắc và bất định (Week 2, Day 7–12)

| Ngày (Day) | Làm gì | Cần hiểu | Artifact / qua cổng | Kết luận được phép rút ra |
|---|---|---|---|---|
| 7 | Viết BG/NBD + Gamma-Gamma specification: assumptions, input, output, failure modes | Model assumption là contract, không phải footnote | `CLV_MODEL_SPEC.md` review được | Kết quả phụ thuộc non-contractual repeat-purchase assumption |
| 8 | Chạy 2–3 rolling origins và horizon; compare baseline | Báo cáo biến thiên theo cutoff thay vì chọn một cutoff sau khi xem kết quả | rolling metrics + plots | Champion có/không ổn định theo time split |
| 9 | Sensitivity: time unit, penalizer, wholesale, one-time buyer, return rule | Sensitivity đo mức thay đổi của estimate theo assumption | ablation table | Scenario nào làm forecast đổi nhiều phải thành limitation |
| 10 | Chạy một Bayesian/Pareto challenger trong time budget | Bayesian thêm uncertainty nhưng không tự thắng point model | convergence/runtime report | Giữ/chặn challenger theo evidence, không theo độ “xịn” |
| 11 | Posterior/MAP diagnostics, interval coverage nếu có | Predictive interval phải được kiểm tra coverage, không chỉ vẽ band | uncertainty figures | Uncertainty có/không calibrated trên holdout |
| 12 | Freeze CLV champion, registry, batch scoring CLI | Champion là policy input có provenance | model registry + `score-clv` + tests | CLV layer đã sẵn sàng làm baseline, không là causal headline |

### Rà soát tuần 2 (Weekly Review)

Chỉ chuyển sang causal monetary value nếu bạn trả lời được bằng artifact:

1. Train/holdout đặt ở đâu, tại sao không leakage?
2. CLV forecast hơn historical baseline bao nhiêu và có CI/stability không?
3. Giá trị là revenue hay margin? Return/wholesale được xử lý ra sao?
4. Customer nào không được model cover, và app sẽ hiện limitation đó ở đâu?

## 5. Giai đoạn 3 (Phase 3) — Giá trị tiền tệ nhân quả và cầu nối iCV (Week 3, Day 13–18)

### Ngày 13 (Day 13) — Thẻ dữ liệu Hillstrom và đối sánh treatment (Treatment Contrast)

**Làm gì**

1. Load Hillstrom; audit 64k rows, covariates, spend/visit/conversion.
2. Chọn trước một contrast: Mens vs control **hoặc** Womens vs control. Nếu multi-arm, viết protocol riêng.
3. Freeze split, known propensity, outcome horizon hai tuần và treatment cost scenarios.
4. Làm randomization/balance check.

**Cần hiểu**

- Random assignment hỗ trợ causal interpretation cho outcome window được quan sát.
- Gộp/loại treatment arm sau khi xem kết quả là analysis flexibility, không phải insight.

**Artifact/verification**

- Hillstrom data card, contrast spec, balance report, leakage test.

**Rút ra được**

> Ta có thể đo causal short-horizon monetary effect của email; không có quyền gọi đó là lifetime value.

### Ngày 14 (Day 14) — Đường cơ sở uplift tiền tệ (Monetary Uplift Baselines)

**Làm gì**

1. Fit random, response/predicted spend, propensity/CLV-style proxy, T-Learner và DR-Learner.
2. Separate train/validation/final holdout; use only pre-treatment X.
3. Build value uplift curve và uplift calibration by bin.

**Cần hiểu**

- Response/predicted spend nói ai có value cao; CATE/iCV hỏi value nào tăng vì treatment.
- Continuous monetary outcome thường zero-inflated/skewed; report robust aggregate/bootstrapped CI.

**Artifact/verification**

- causal monetary comparison table, score schema, calibration plots.

**Rút ra được**

> Policy chỉ được chọn khi vượt business baselines theo held-out policy value và các
> constraint đã xác định; ranking metric không phải criterion duy nhất.

### Ngày 15 (Day 15) — Đánh giá chính sách có xét chi phí (Cost-aware Policy Evaluation)

**Làm gì**

1. Implement policy `treat if predicted iCV > 0`, budget top-k và cost constraint.
2. Evaluate random, propensity, predicted CLV, conversion CATE, `CATE × CLV`, direct iCV.
3. Report direct method, IPW và DR side-by-side; bootstrap paired differences.
4. Log arm count, known propensity, max weight, effective sample size, overlap and runtime.

**Cần hiểu**

- Policy value differs from CATE score: cost/budget can reverse target order.
- DR needs outcome model, propensity and honest evaluation separation.

**Artifact/verification**

- `policy_value_comparison.csv`, sensitivity table, policy evaluator unit tests.

**Rút ra được**

> Dưới contrast/cost/horizon đã freeze, policy nào tạo estimated incremental value cao nhất trên holdout
> cùng uncertainty; không phải production revenue lift.

### Ngày 16–17 (Day 16–17) — RCT bán tổng hợp theo thời gian (Semi-synthetic Longitudinal RCT)

**Làm gì**

1. Viết DGP spec dùng distribution RFM/monetary từ Online Retail II nhưng customer độc lập mới.
2. Randomize treatment; sinh purchase rate, dropout, order value, cost và `Y(0), Y(1)` cho nhiều scenario.
3. Unit test seed, truth, no-effect negative control, sleeping dog, margin trade-off, heterogeneous cost.

**Cần hiểu**

- Semi-synthetic combines realistic covariates/distributions with known counterfactuals; nó kiểm thử method,
  không xác minh business effect ngoài đời.

**Artifact/verification**

- DGP config, generated dataset, truth table, unit tests, scenario card.

**Rút ra được**

> Ta biết estimator/policy có recover iCV và regret bao nhiêu dưới DGP explicit; kết luận chỉ đúng trong
> scenarios đó.

### Ngày 18 (Day 18) — Benchmark tích hợp (Integration Benchmark)

**Làm gì**

1. Chạy candidate policies trên semi-synthetic scenarios.
2. Compare PEHE (nếu cần), policy regret, net value, top-k stability, runtime.
3. Chọn direct iCV candidate/challenger cho app; không add thêm model nếu không thay đổi decision.

**Qua cổng khi**

- policy đang chọn không thua obvious baseline ở most relevant scenarios;
- no-effect negative control không invent value;
- real vs semi-synthetic chart/label hoàn toàn tách biệt.

**Rút ra được**

> Integration between forecasting and causal targeting hoạt động/kém ở đâu; app phải nói rõ evidence
> nào real và evidence nào simulated.

## 6. Giai đoạn 4 (Phase 4) — Xây ứng dụng demo (Week 4, Day 19–24)

### Ngày 19 (Day 19) — Hợp đồng sản phẩm (Product Contract) trước UI

**Làm gì**

1. Viết one-page PRD: primary user, job-to-be-done, non-goals, five screens, user journey 60 giây.
2. Define input contract (`budget`, `cost`, `margin`, `horizon`, `run_id`) và output contract.
3. Wireframe; chọn 1 persona demo: Growth/CRM Manager.
4. Chuẩn bị sample artifacts nhỏ có provenance và no PII.

**Cần hiểu**

- Product demo là “decision interface”, không phải nơi train model.
- Mỗi interaction phải dẫn đến action/reason, không chỉ đổi chart.

**Qua cổng khi**

- có thể mô tả trong 30 giây user vào đâu, chọn gì, quyết định gì và export gì.

### Ngày 20–22 (Day 20–22) — Năm màn hình

| Screen | Phải hiện gì | User hiểu/rút ra gì | Test tối thiểu |
|---|---|---|---|
| Decision Overview | net value, targeted count, cost, CI, budget utilization, main caveat | policy recommendation dưới scenario hiện tại | KPI trace đúng artifact |
| Customer Strategy | segment/reason code, included/excluded count, export action list | tại sao customer được target/bị loại | export filter/cost/budget đúng |
| Evidence Lab | baseline table, policy curve, CI, calibration, runtime | có evidence policy hơn baseline hay không | chart/data table reproducible |
| Scenario Lab | sliders cost/margin/horizon/budget, sensitivity result | recommendation có ổn định không | scenario constraints validated |
| Governance | run ID, data source/hash, model/config, sources, limitations, labels observed/synthetic | số nào là observed, estimated hoặc scenario | manifest hiển thị đúng |

### Ngày 23 (Day 23) — Hoàn thiện độ bền app và trải nghiệm lập trình (Developer Experience)

**Làm gì**

1. Tách UI khỏi `src/` domain logic; validate input bằng Pydantic.
2. Add empty/error/loading states; no hard-coded business KPI.
3. Add structured logs, `run_id`, latency/status; `/health` endpoint hoặc health function.
4. Viết integration test artifact → domain → app/export.

**Rút ra được**

> Dashboard có thể được bảo trì/kiểm thử như software; result không phụ thuộc vào notebook state.

### Ngày 24 (Day 24) — Triển khai (Deployment) và API tùy chọn

**P0 bắt buộc**

1. Docker build/run, health check, sample startup command.
2. GitHub Actions chạy formatting/lint/test/Docker smoke.
3. Public staging/demo (nếu không có cloud: video + reproducible local Docker demo).

**Chỉ khi P0 green**

- FastAPI thin layer với `/health`, `/v1/scenarios/evaluate`, `/v1/customers/export`,
  `/v1/runs/{run_id}/metadata`; Pydantic/OpenAPI/contract tests.

**Không làm**

- retrain model trong HTTP request;
- LLM agent không có evaluation;
- React/Kubernetes rewrite.

## 7. Giai đoạn 5 (Phase 5) — Kiểm định cuối, kể chuyện và phát hành (Week 5, Day 25–30)

| Ngày (Day) | Làm gì | Cần hiểu | Artifact / qua cổng | Rút ra được |
|---|---|---|---|---|
| 25 | Freeze model/config/protocol; mở final holdout đúng một lần | Final holdout là confirmatory, không là tuning set | immutable final run | headline đã được xác nhận hoặc negative result |
| 26 | Bootstrap, paired policy comparison, seed/cutoff/cost/horizon sensitivity | CI không thay effect size; robustness không phải cherry-picking | robustness report | kết quả ổn định hay fragile ở đâu |
| 27 | Viết technical report, data/model cards, source citations, limitations | Claim phải match evidence level | technical report | reader phân biệt real/forecast/synthetic |
| 28 | README, architecture diagram, GIF, decision case study, quickstart | Communication là phần của product | release docs | người đọc hiểu mục tiêu, evidence và giới hạn |
| 29 | Record video 2–3 phút, slide 8–10 trang, prep Q&A | Demo kể decision → evidence → limitation → next action | video/deck/script | bạn giải thích được trade-off thay vì đọc code |
| 30 | Fresh-machine Docker reproduction, release scorecard, tag `v1.0` | “works on my machine” không phải reproducibility | release, checklist, changelog | release có thể review độc lập |

## 8. Checklist phát hành cuối (Final Release Checklist)

### Scientific / analytical

- [ ] Estimand, action, control, horizon, currency, cost và margin/revenue definition rõ.
- [ ] Mọi model/policy so cùng frozen holdout; final holdout không dùng tune.
- [ ] Có baselines business: random, propensity, predicted CLV, conversion CATE, heuristic, direct iCV.
- [ ] Direct/IPW/DR policy value, CI và caveat được report.
- [ ] CLV có temporal/rolling validation; không random split transaction.
- [ ] Semi-synthetic truth và real-data evidence tách label rõ.
- [ ] Mọi candidate không đạt gate được ghi cùng metric và điều kiện dừng.

### Product

- [ ] Dashboard 5 screens chạy với sample mode trong dưới 60 giây workflow.
- [ ] SQL marts, metric dictionary và data-quality audit có trong repo.
- [ ] Scenario changes dẫn đến policy/action list/export thay đổi có kiểm soát.
- [ ] KPI có currency, horizon, run ID và limitation ngay trong UI.

### Engineering

- [ ] `src/` domain layer tách UI; typed/Pydantic contracts.
- [ ] Tests: unit, temporal leakage, policy cost/budget, DGP truth, integration smoke.
- [ ] CI green; Docker build/run/health check pass.
- [ ] Artifact manifest, model registry, config và logs có provenance.
- [ ] Chỉ ghi API/OpenAPI là artifact đã hoàn thành khi FastAPI extension chạy và qua test.

### Documentation / communication

- [ ] README có hero statement, screenshot/GIF, architecture, quickstart, result table, limitation.
- [ ] Case study 1 trang + technical report 10–15 trang.
- [ ] Video 2–3 phút; slide 8–10 trang; Q&A sheet.

## 9. Mẫu nhật ký quyết định (Decision Log Template, dùng mỗi ngày)

```markdown
## YYYY-MM-DD — <decision title>

**Question:** câu hỏi business/technical cần quyết định.
**Evidence:** run_id, dataset version, table/chart/test liên quan.
**Options considered:** A / B / C.
**Decision:** chọn gì, owner và phạm vi.
**Why:** trade-off, assumption và limitation.
**Impact:** artifact/code/report nào thay đổi.
**Next check:** điều gì có thể làm quyết định này sai và khi nào kiểm lại.
```

Ví dụ tốt: “Không dùng Pareto/NBD trong v1.0 vì 3 temporal cutoffs không cải thiện value forecast,
runtime vượt budget; giữ BG/NBD + Gamma-Gamma champion.”

## 10. Khi nào phải dừng hoặc cắt scope

| Tình huống | Hành động đúng |
|---|---|
| Bayesian/Pareto không hội tụ hoặc quá chậm | giữ fast baseline, ghi limitation; không bỏ temporal validation |
| Direct iCV không vượt business baseline | báo cáo negative result, dashboard vẫn show comparison |
| Hillstrom estimate có CI rộng | chỉ báo two-week exploratory result; không gọi là long-horizon iCLV |
| Semi-synthetic recovery kém | sửa DGP/estimator/test trước app polishing |
| Dashboard chậm/chưa ổn | serve precomputed artifacts; không optimize bằng retrain online |
| Trễ tiến độ | cắt Pareto, FastAPI, Copilot trước; không cắt protocol, tests, app core, report |

## 11. Tóm tắt dự án sau khi hoàn thành

> “Tôi bắt đầu từ một causal uplift benchmark và thấy conversion uplift không trả lời được value. Tôi xây
> forecasting layer có temporal validation trên transaction data, nhưng không fake-join nó với causal
> dataset. Với monetary RCT, tôi đánh giá cost-aware policies bằng held-out DR value; với long-horizon
> integration, tôi dùng semi-synthetic truth và gắn nhãn rõ. Sau đó tôi đóng gói evidence thành dashboard
> có scenario, action export, provenance, Docker và CI. Kết quả không chỉ là một model tốt hơn mà là một
> quyết định có thể kiểm tra: target ai, dưới budget nào, dựa trên evidence nào và giới hạn gì.”

Khi dashboard, artifact và báo cáo cùng hỗ trợ được từng câu trong phần tóm tắt trên, dự án
được xem là hoàn thành đúng mục tiêu kỹ thuật.
