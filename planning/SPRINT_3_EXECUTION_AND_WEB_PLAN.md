# Sprint 3 — Kế hoạch thực hiện, kiểm thử và đóng gói web

**Ngày lập:** 05/08/2026
**Phạm vi:** thực hiện vòng cải tiến model theo
`planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md`, chốt champion bằng promotion rule đã
đăng ký trước, và đóng gói toàn bộ thành một web application có backend/API.
**Điều kiện compute:** laptop 6 CPU vật lý/12 luồng, RAM 15,19 GB. Kaggle Free là compute
phụ cho Causal Forest.

Tài liệu này là plan. Con số đã chạy nằm trong `report/`. Mỗi phase chỉ được đánh dấu
hoàn thành khi có artifact và test tương ứng.

## Trạng thái thực hiện — cập nhật 05/08/2026

| Phase | Trạng thái | Bằng chứng |
|---|---|---|
| 0 — xác minh baseline | Đạt | pytest 51/51; `dashboard_data.json` rebuild byte-identical; ba split hash khớp manifest Sprint 2 |
| 1 — evaluation stack | Đạt | `src/ranking_metrics.py`, `src/policy_evaluation.py`; 28 test mới |
| 2 — protocol OOF và registry | Đạt | `configs/sprint3_improvement_protocol.json`, `src/experiment.py`, `output/improvement/registry.csv` |
| 3 — challenger models | Đạt | smoke 1%, screening 20%, full development OOF hai fold seed |
| 4 — ensemble | Đạt | `src/ensemble.py`; Q-aggregation, best-single, rank average |
| 5 — retrospective confirmation | Đạt | `output/sprint3/`; không challenger nào được promote |
| 6 — web application | Đạt | `webapp/`; 18 contract test, 23/23 browser acceptance |
| 7 — tài liệu | Đạt | báo cáo, method guide, runbook, CLAUDE.md, README |

Kết quả tổng: champion giữ nguyên Response. Chi tiết ở
`report/SPRINT_3_FINAL_REPORT.md`.

Sai lệch so với plan cần ghi:

- **pROCini không được hiện thực.** Kế hoạch xếp nó vào P0 nhưng trang JMLR công khai
  không cung cấp công thức và repo không tiếp cận được bản đầy đủ. Viết theo suy đoán
  sẽ vi phạm quy tắc nguồn của dự án.
- **Screening chạy ở 20% thay vì 10%.** 10% chỉ cho khoảng 163 conversion ở control,
  quá mỏng để xếp hạng candidate; 20% cho 325.
- **Họ DR/R-Learner bị dừng sau screening** theo đúng quy tắc early-stop đã đăng ký,
  nên không có kết quả full development cho hai họ đó.
- **Resource gate chỉ kiểm tra trước khi chạy.** Trong các stage full-data, RAM khả
  dụng của hệ thống tụt xuống 1,55 GB, dưới ngưỡng 2,0 GB đã đăng ký, mà run không bị
  dừng. Cần sửa trước khi thêm model nặng hơn.
- **R-Learner không có file riêng.** Kế hoạch ban đầu dự kiến `src/rlearner.py`; hiện
  thực thực tế đặt nó trong `src/candidates.py::build_r_learner` qua `NonParamDML` của
  EconML, cùng chỗ với mọi candidate khác để dùng chung một feature contract và một
  đường fit/predict. Không có module riêng nào bị thiếu.

## 0. Trạng thái đầu vào đã kiểm tra

| Hạng mục | Trạng thái ngày 05/08/2026 | Bằng chứng |
|---|---|---|
| pytest | 51/51 pass, 49,4 giây | chạy lại `pytest tests -q` |
| Criteo v2.1 | SHA-256 khớp manifest Sprint 2 | `output/sprint2/protocol_manifest.json` |
| Sprint 1 release | 5 model, test 2.096.940 dòng | `output/sprint1/`, `output/optimization/*sprint1_release*` |
| Sprint 2 release | confirmation 1.397.959 dòng | `output/sprint2/` |
| Dashboard | schema `sprint2-dashboard-v1` | `output/dashboard_data.json` |
| Causal Forest | chỉ local smoke 0,1% | `output/causal_forest_gate_smoke/` |
| econml/lightgbm/sklearn | 0.16.0 / 4.7.0 / 1.6.1 | `pip show` trong `.venv` |

Giới hạn kế thừa: confirmation Sprint 2 đã được xem và báo cáo, nên mọi kết quả mới trên
tập đó phải ghi là **retrospective confirmation**.

## 1. Định nghĩa "model tốt nhất" dùng cho vòng này

Giữ nguyên sáu điều kiện ở mục 1 của `SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md`. Bổ sung
cụ thể hoá thành metric có thể tính:

**Primary selection metric (đăng ký trước khi chạy):**
`policy_area_dr` = trung bình theo trapezoid của DR gross policy value trên lưới budget
`{0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30}`, tính trên out-of-fold predictions của
development pool. Đây là conversion tăng thêm trung bình trên toàn population, không gắn
tiền giả định.

**Secondary evidence (báo cáo đầy đủ, không dùng để chọn):**

- AUTOC/RATE theo Yadlowsky et al. với DR score;
- Qini và AUUC để giữ khả năng so sánh với Sprint 1–2;
- outcome-adjusted Qini/AUTOC (giảm variance trên RCT);
- calibration EUCE cho score có scale CATE;
- DR risk (doubly robust loss) cho model selection/ensemble.

**Comparator bắt buộc:** treat-none; expected-random `π(x)=b`; random top-k qua 20 seed;
Response top-k (champion hiện tại); X-Renormalized.

**Promotion rule (khóa trước Phase 5):**

1. `policy_area_dr` OOF của challenger > Response ở cả hai seed cross-fitting;
2. point estimate trên retrospective confirmation cùng dấu;
3. paired 95% CI của chênh lệch `policy_area_dr` có lower bound > 0;
4. không có regression về runtime gate, calibration, hoặc guardrail đã đăng ký.

Nếu điều kiện 3 không đạt, giữ Response và phát hành challenger kèm CI. Không viết
"model mới tốt hơn".

## 2. Kết quả research 2024–2026 và quyết định phạm vi

### 2.1 Đã đọc và áp dụng trong vòng này

| Nguồn | Nội dung dùng | Áp dụng |
|---|---|---|
| Yadlowsky et al., JASA 2025 (RATE/AUTOC) | TOC, RATE, yêu cầu sample-splitting | `src/ranking_metrics.py` |
| Bokelmann & Lessmann, EJOR 2024 (arXiv 2210.02152) | outcome adjustment giảm variance metric trên RCT | `src/ranking_metrics.py`, có test |
| Nie & Wager, Biometrika 2021 (R-Learner) | Robinson residualization, R-loss, cross-fitting | `src/candidates.py::build_r_learner` (qua `NonParamDML`) |
| Kennedy, EJS 2023 (DR-Learner) | pseudo-outcome doubly robust, sample splitting | ablation DR |
| Lan & Syrgkanis, AISTATS 2024 (Causal Q-Aggregation) | DR loss + Q-aggregation cho ensemble | `src/ensemble.py` |
| Dudík et al., ICML 2011; Athey & Wager, Econometrica 2021 | DR policy value, value/regret framing | `src/policy_evaluation.py` |
| Rank-Learner, ICLR 2026 (arXiv 2602.03517) | pairwise Neyman-orthogonal ranking loss | `src/rank_learner.py` |

Ghi chú nguồn Rank-Learner: paper báo AUUC ×10³ trên Criteo test 1M là `5,90 ± 0,40` so
với DR-Learner `5,17 ± 1,13`, ở thiết lập induced confounding khi train và randomized khi
test. Thiết lập đó khác thiết lập randomized-train của dự án này, nên kết quả paper không
được dùng làm dự đoán cho repo.

### 2.2 Đã đọc và ghi nhận nhưng không dùng làm căn cứ chọn model

- **UpliftBench, arXiv 2604.06123 (2026):** so sánh S/T/X-Learner và Causal Forest trên
  chính Criteo v2.1 và báo S-Learner đứng đầu theo Qini (`0,376`). Outcome của họ là
  `visit` (4,7%), không phải `conversion` (0,29%); paper tự ghi rare-outcome cần nghiên cứu
  riêng. Không so trực tiếp số của họ với số của repo này.
- **Structural-bias metric study, arXiv 2603.20775 (2026):** báo Qini kém ổn định hơn
  Uplift/AUUC dưới selection bias và unobserved confounding. Trên RCT randomized của
  Criteo hai bias đó không phải kịch bản chính, nhưng kết luận củng cố quyết định không
  dùng Qini đơn lẻ làm primary metric.
- **Heteroscedasticity-aware sampling (EJOR 2025):** thuộc thiết kế RCT mới, không dùng
  post-hoc trên benchmark đã cố định.
- **Delayed feedback (AAAI 2026), continuous treatment (2026):** Criteo v2.1 không có
  event time và treatment liên tục.

### 2.3 Không đưa vào critical path

PTONet/PUL, TARNet/DragonNet, LambdaMART direct ranking. Chỉ mở nếu P0 hoàn tất và
challenger P0 không đủ tách khỏi Response.

## 3. Phase và điều kiện đạt

### Phase 0 — Xác minh baseline

Bước:

1. `pytest tests -q`;
2. rebuild `dashboard_data.json` từ `output/sprint2/` và so sánh với bản đã commit;
3. kiểm tra checksum dữ liệu và row count từng split.

Điều kiện đạt: test pass; payload dashboard tái lập byte-identical hoặc chênh lệch được
giải thích.

### Phase 1 — Evaluation stack

File mới:

- `src/ranking_metrics.py`: `toc_curve`, `rate_score`, `autoc_score`, DR-score input,
  outcome-adjusted variant, paired bootstrap cho mọi metric;
- `src/policy_evaluation.py`: `dr_policy_value_curve`, `policy_area`,
  `expected_random_policy_value`, multi-seed random sensitivity.

Kiểm thử bắt buộc (`tests/test_ranking_metrics.py`, `tests/test_policy_evaluation.py`):

1. synthetic có ground-truth CATE: model biết đúng `tau` phải có AUTOC và `policy_area_dr`
   cao hơn model random, và cao hơn model ranking ngược;
2. metric bất biến với biến đổi đơn điệu tăng của score;
3. score hằng số cho RATE ≈ 0;
4. rare-outcome sample vẫn trả giá trị hữu hạn;
5. outcome adjustment không đổi kỳ vọng nhưng giảm variance trên mô phỏng lặp;
6. paired bootstrap giữ đúng pairing (cùng index cho mọi model);
7. tie handling và edge case n nhỏ.

Điều kiện đạt: toàn bộ test mới pass, không NaN trên fixture rare-outcome.

### Phase 2 — Protocol OOF và registry

File mới:

- `configs/sprint3_improvement_protocol.json`: split hash, fold/seed, metric hierarchy,
  promotion rule, resource gate;
- `src/experiment.py`: cross-fitting OOF, resource sampler, registry writer;
- `scripts/run_oof_experiment.py`: one-command runner cho một candidate;
- `scripts/compare_improvement_candidates.py`: paired comparison + promotion check.

Development pool = `fit` + `validation` của Sprint 2 (5.591.836 dòng). 3-fold
cross-fitting stratify theo (treatment, conversion), seed 101; seed 202 cho finalist.

Registry `output/improvement/registry.csv` ghi mỗi run: run ID, commit SHA, UTC timestamp,
dataset checksum, split hash, fold/seed, model/config hash, package versions, row/event
counts theo arm, fit/predict time, peak RSS, toàn bộ metric đã đăng ký, status
(`smoke`/`screen`/`finalist`/`retrospective_confirmation`/`failed`) và failure reason.

Điều kiện đạt: một candidate chạy hết vòng smoke và ghi được đủ trường registry.

### Phase 3 — Challenger models

| ID | Model | Giả thuyết | Ngân sách screening |
|---|---|---|---|
| M-RESP | Response (champion hiện tại) | reference | — |
| M-X | X-Renormalized (config release) | reference | — |
| M-R | R-Learner qua `NonParamDML`, propensity hằng 0,85 | orthogonal loss giảm regularization bias | 4 cấu hình final |
| M-DR | DR-Learner `discrete_outcome=True`, `mc_iters=2` | nuisance binary phù hợp outcome hiếm | 2×2×2 |
| M-T | T-Learner classifier + undersampling k=7 | tách ảnh hưởng của outcome model dạng classifier | 2 |
| M-S | S-Learner classifier + undersampling k=7 | UpliftBench báo S mạnh trên Criteo `visit` | 2 |
| M-RANK | Rank-Learner pairwise orthogonal | tối ưu trực tiếp thứ hạng thay vì magnitude | 3 |

Ràng buộc: mọi candidate dùng cùng fold, cùng feature contract (`f0..f11`), cùng estimand
`conversion`. Không dùng `visit`/`exposure`.

Early stop: score gần hằng số, score không hữu hạn, nuisance calibration hỏng, hoặc bị cả
Response và X-Renormalized dominate ở mọi budget 5–20%.

Trình tự: smoke 1% → screen 10% development pool → finalist full development OOF.

### Phase 4 — Ensemble

- best-single theo DR risk đã đăng ký;
- softmax/R-score ensemble làm baseline;
- causal Q-aggregation làm challenger; weights chỉ học trên OOF prediction hợp lệ, không
  học trên confirmation.

### Phase 5 — Retrospective confirmation và quyết định champion

Chạy đúng một lần sau khi freeze shortlist và code:

- refit finalist trên toàn bộ development pool, predict confirmation;
- paired bootstrap 500 cho `policy_area_dr`, AUTOC và Qini so với Response và
  X-Renormalized;
- áp promotion rule;
- ghi quyết định vào `report/SPRINT_3_FINAL_REPORT.md` kể cả khi không đổi champion.

### Phase 6 — Web application

Kiến trúc mục tiêu (không phụ thuộc CDN, chạy offline):

```text
webapp/
  api/            FastAPI: /health, /meta, /models, /policy, /simulate, /segments,
                  /score (batch scoring), /export
  service/        đọc artifact freeze từ output/, không train khi request
  static/         SPA một trang, vanilla JS + canvas, không CDN
  tests/          contract test cho từng endpoint
```

Tính năng bắt buộc:

1. tổng quan release: run ID, split hash, data checksum, trạng thái từng sprint;
2. so sánh model: Qini/AUUC/AUTOC/`policy_area_dr` kèm CI, paired difference matrix;
3. budget/policy explorer: slider budget, input value/cost, DR net + CI, break-even;
4. đường cong: Qini curve, TOC curve, budget-value curve, decile uplift;
5. batch scoring: upload CSV 12 feature, trả score và nhãn top-k theo budget;
6. what-if sensitivity: cost grid, value grid, treat-none/random comparator;
7. evidence panel: limitation, assumption, nguồn artifact cho từng con số;
8. export CSV/JSON có run ID và assumption fields.

Kiểm thử: pytest contract test cho API; headless browser acceptance như Sprint 2; kiểm tra
mọi số hiển thị đều truy được về artifact.

### Phase 7 — Tài liệu

Cập nhật ngay sau khi mỗi phase có artifact được xác minh: `CLAUDE.md`, `README.md`,
`planning/sprints.md`, `planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md` (đánh dấu mục đã
thực hiện), `report/SPRINT_3_FINAL_REPORT.md`, model card và decision contract.

## 4. Gate tài nguyên

- dừng hoặc giảm fraction nếu process + system vượt 75% RAM hoặc available RAM < 2 GB;
- không chạy song song nhiều full-data model;
- ghi peak RSS và wall time cho mọi run vào registry;
- Causal Forest vẫn theo gate Kaggle 20% → 30% → 50%; không chạy 50% local.

## 5. Definition of Done cho Sprint 3

- [ ] Phase 0 xác minh và ghi lại.
- [ ] Metric mới có synthetic-truth test và edge-case test.
- [ ] Expected-random và multi-seed random sensitivity có artifact.
- [ ] Registry OOF đầy đủ cho mọi candidate, gồm cả candidate bị early stop.
- [ ] R-Learner, DR ablation, Rank-Learner chạy trong resource gate.
- [ ] Ensemble weights chỉ học trên OOF hợp lệ.
- [ ] Promotion rule được áp đúng một lần; quyết định champion được ghi kèm CI.
- [ ] Web app chạy được, mọi endpoint có test, mọi số truy được về artifact.
- [ ] Tài liệu và CLAUDE.md phản ánh đúng trạng thái cuối.
- [ ] Không có claim revenue/CLV, principal stratum cá nhân, hoặc "SOTA" không có benchmark.
