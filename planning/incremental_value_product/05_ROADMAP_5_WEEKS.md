# 05 — Lộ trình 5 Tuần (5-Week Roadmap)

> Timeline chính bắt đầu sau khi causal được freeze/tag `causal-v0.1`.
>
> Nhịp đề xuất: 6 ngày/tuần; Chủ nhật làm buffer/review nhẹ. Mỗi ngày gồm 60–90 phút research,
> 4–5 giờ build/experiment và 60 phút viết test/report/decision log.

## Tuần 1 — Nền tảng CLV Xác suất (Probabilistic CLV Foundation)

**Mục tiêu:** biến benchmark probabilistic cũ thành package có temporal validation và output tái lập.

| Ngày (Day) | Việc chính | Artifact/kết quả chạy |
|---|---|---|
| Day 1 | Freeze source audit, schema/data contract, manifest; dependency groups; loader + parquet cache | data card, contracts, environment lock |
| Day 2 | Cleaning audit: cancellation, missing customer, quantity/price, duplicate, wholesale, revenue-vs-margin definition | data quality report |
| Day 3 | RFM + temporal calibration/holdout; leakage tests | `rfm.py`, split tests |
| Day 4 | Cohort/repeat/interpurchase/order-value EDA | EDA notebook + figures |
| Day 5 | BG/NBD baseline + purchase/probability-alive calibration | model artifact + metrics |
| Day 6 | Gamma-Gamma + independence check + CLV 90/180/365d | customer CLV table + model card |

Thí nghiệm:

- xlsx vs parquet load time;
- raw vs flag/exclude wholesale;
- ít nhất hai temporal cutoffs;
- calibration theo frequency cohort;
- purchase-count MAE/RMSE/deviance;
- holdout value error/rank correlation.

**DoD:**

- một lệnh sinh `customer_clv_predictions.parquet`;
- temporal leakage tests pass;
- mỗi customer có `p_alive`, expected purchases/value/CLV;
- giá trị chỉ được gọi là **forecasted customer revenue/CLV**; không gọi là observed CLV hoặc margin nếu không có cost data.

## Tuần 2 — CLV Vững chắc và Bất định (Robust CLV and Uncertainty)

**Mục tiêu:** đủ chiều sâu xác suất để show kỹ năng, nhưng không để MCMC chiếm toàn dự án.

| Ngày (Day) | Việc chính | Artifact/kết quả chạy |
|---|---|---|
| Day 7 | Viết model specification + assumptions BG/NBD/Gamma-Gamma | `CLV_MODEL_SPEC.md` |
| Day 8 | Rolling-origin evaluation 2–3 cutoffs/horizons | rolling validation |
| Day 9 | Sensitivity: penalizer, time unit, wholesale, one-time buyer | ablation table |
| Day 10 | PyMC-Marketing smoke/benchmark Bayesian BG/NBD hoặc Pareto/NBD | time/convergence report |
| Day 11 | Posterior/MAP diagnostics, predictive interval/calibration | uncertainty plots |
| Day 12 | Chốt champion/challenger; persist; batch scoring CLI | registry + `score-clv` |

Priority:

- P0: BG/NBD + Gamma-Gamma rolling validation.
- P1: một Bayesian challenger có uncertainty.
- P2: full Pareto/NBD.

**DoD:**

- champion chọn bằng out-of-time metrics;
- artifact load/scoring được;
- uncertainty được dùng hoặc scope-out rõ;
- model card có assumptions/failure modes.

## Tuần 3 — Giá trị Tiền tệ Nhân quả và Cầu nối iCLV (Causal Monetary Value and iCLV Bridge)

**Mục tiêu:** kết hợp hai nền tảng với estimand, identification assumptions và evaluation
protocol được xác định trước.

| Ngày (Day) | Việc chính | Artifact/kết quả chạy |
|---|---|---|
| Day 13 | Hillstrom load; freeze Mens-vs-control hoặc Womens-vs-control; randomization/spend/final holdout | data card + contrast spec |
| Day 14 | Random/response/predicted-spend + T/DR monetary uplift | model comparison |
| Day 15 | Cost-aware value curve + direct/IPW/DR policy value + overlap audit | policy evaluator |
| Day 16 | Semi-synthetic longitudinal RCT DGP từ retail distributions | DGP spec |
| Day 17 | Sinh `Y(0)`, `Y(1)` qua purchase/dropout/order-value effect | truth dataset + tests |
| Day 18 | T/DR/forest + business baselines; PEHE/regret/value | experiment report |

Baselines bắt buộc:

- random;
- conversion propensity;
- predicted spend;
- predicted CLV;
- conversion CATE;
- `CATE × CLV` heuristic;
- direct iCV;
- oracle semi-synthetic policy.

**DoD:**

- có real short-horizon monetary uplift evidence;
- có semi-synthetic long-horizon ground-truth evidence;
- mọi chart gắn nhãn provenance;
- không có fake join Criteo/Online Retail.

## Tuần 4 — Nền tảng Giá trị Tăng thêm (Incremental Value Studio)

**Mục tiêu:** sản phẩm demo được trong phỏng vấn.

| Ngày (Day) | Việc chính | Artifact/kết quả chạy |
|---|---|---|
| Day 19 | Product requirements, user flow, wireframe, artifact schema, persona acceptance test | product spec |
| Day 20 | Decision Overview + budget optimizer | page 1 |
| Day 21 | Customer Strategy + reason code + CSV export | page 2 |
| Day 22 | Model Evidence + Scenario Lab + governance/provenance panel | page 3–5 |
| Day 23 | UI/domain separation, Pydantic validation, cache, error states, structured logs | hardened app |
| Day 24 | Docker, CI, sample data, smoke tests, deployment; FastAPI thin API only if core is green | staging URL |

Stack P0: Streamlit + independent `src/` domain layer + Docker. FastAPI/React chỉ là stretch.

**DoD:**

- workflow hoàn thành trong dưới 60 giây;
- number provenance đầy đủ;
- real/semi-synthetic labels rõ;
- app đổi policy theo cost/margin/budget;
- CSV export;
- one-command startup.
- `/health` pass trong Docker và provenance hiển thị trong app.

## Tuần 5 — Kiểm định, Kể chuyện và Phát hành (Validation, Storytelling and Release)

**Mục tiêu:** biến demo thành release artifact có bằng chứng.

| Ngày (Day) | Việc chính | Artifact/kết quả chạy |
|---|---|---|
| Day 25 | Freeze model/config; final holdout một lần | immutable metrics |
| Day 26 | Bootstrap, seed/cutoff, cost/margin/horizon sensitivity | robustness report |
| Day 27 | Technical report, data/model cards, source citations, limitations | report |
| Day 28 | Decision case study, architecture, README quickstart | README |
| Day 29 | Demo video 2–3 phút, slide 8–10 trang, Q&A | video + deck |
| Day 30 | Fresh-environment reproduction, clean repo, tag/release | `v1.0` |

**Final DoD:**

- public demo URL;
- GitHub release `v1.0`;
- one-command reproducibility;
- CI xanh;
- no placeholder/TODO trong public docs;
- headline metrics trace về run/artifact;
- demo video, slide, model/data cards;

## Cắt phạm vi nếu trễ (Scope Cut)

Cắt theo thứ tự:

1. full Pareto/NBD;
2. batch API;
3. multi-treatment;
4. advanced Bayesian UI;
5. extra models.

Không cắt:

- temporal validation;
- real/semi-synthetic provenance;
- policy evaluation;
- cost/budget optimizer;
- app;
- report/reproducibility.

## Câu hỏi hoàn tất hằng ngày (Daily Completion Questions)

1. Artifact mới hôm nay là gì?
2. Số nào lấy từ artifact của run đã hoàn thành?
3. Quyết định nào được ghi vào decision log?
4. Có claim nào vượt quá data không?
5. Việc ngày mai có trực tiếp đẩy tới release không?
