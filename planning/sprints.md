# Lộ trình 3 Sprint — 6 tuần

Tuần 1 đã qua trước khi kế hoạch này được chốt. Trạng thái dưới đây phản ánh artifact
được ghi trong artifact ngày 31/07/2026.

## Sprint 1 — Khóa nền tảng causal (Tuần 1–2)

**Mục tiêu:** xác định estimand, kiểm toán dữ liệu, xây baseline/meta-learners và một
evaluation protocol có thể audit.

**Đã hoàn thành:**

- Criteo data contract/checksum/provenance;
- loại `visit`/`exposure` khỏi feature;
- Response, S/T/X, DR;
- multi-seed validation;
- Qini/AUUC/EUCE/transformed outcome;
- 500 paired bootstrap;
- policy decile và Causal Forest feasibility.

**Kết quả cần giữ khi diễn giải:** Response có Qini cao nhưng không phải CATE estimator; model comparison
phải dùng CI của chênh lệch, không nhìn thứ hạng điểm.

**Bằng chứng:** `report/SPRINT_1_FINAL_REPORT.md`.

## Sprint 2 — Chuyển model thành policy và dashboard (Tuần 3–4)

**Mục tiêu:** trả lời “target bao nhiêu, evidence offline là gì, cost nào không còn hợp
lý?” bằng một ứng dụng chạy được.

**Đã hoàn thành local:**

- untouched complementary 50% và fit/validation/confirmation 60/20/20;
- exact probability restoration + τ-isotonic ablation;
- Response top-k decision contract;
- IPW/DR policy evaluation, budget/cost sensitivity;
- 500 paired bootstrap;
- dashboard self-contained + 11/11 browser acceptance;
- data/model card và một-lệnh pipeline;
- Kaggle gate script + local 0,1% smoke.

**Chưa hoàn thành bên ngoài:**

- Kaggle Causal Forest 20% → 30% → 50%;
- Git release tag vì repository chưa có commit.

**Quyết định cắt scope:** Causal Forest pending không chặn product release. Không mua
Colab Pro trước khi Kaggle 20–30% chứng minh nhu cầu/tính khả thi.

**Bằng chứng:** `report/SPRINT_2_FINAL_REPORT.md`, `output/sprint2/`,
`output/dashboard.html`.

## Sprint 3 — Portfolio/release engineering (Tuần 5–6)

**Mục tiêu:** đóng gói artifact để thể hiện các năng lực DA, DS và AI Engineer bằng kết quả
có thể chạy lại.

### Work package 1 — Clean release

- tạo commit history/release tag sau khi user xác nhận;
- thêm CI test tối thiểu;
- clean-environment runbook hoặc Docker;
- link/source audit tự động;
- không còn stale claim trong notebook/report cũ.

**DoD:** clone → install → tests → build dashboard bằng command rõ ràng.

### Work package 2 — Portfolio communication

- video demo 60–90 giây;
- 6–8 slides: problem → identification → methods → evidence → policy → limitation;
- README 5-minute path;
- CV bullets riêng cho DA/DS/AIE;
- interview Q&A về Response thắng, negative result và leakage.

**DoD:** mọi con số trong video/slide link được về CSV/manifest.

### Work package 3 — Production thinking

- monitoring/data drift contract;
- production randomized holdout design;
- input/output schema cho batch scoring;
- latency/cost envelope;
- privacy/fairness/use limitation.

**DoD:** architecture/runbook đủ để thảo luận AI Engineering, không cần dựng backend
phức tạp nếu chưa có giả thuyết và tiêu chí đánh giá xác định trước.

### Work package 4 — Causal Forest checkpoint

- chạy Kaggle gates khi session sẵn sàng;
- nếu 20/30 fail: đóng learning-curve limitation;
- nếu 50 pass: chấm đúng locked protocol một lần, không retune final test.

### Work package 5 — Handoff sang Incremental CLV

Chỉ mở sau causal release:

- data card Online Retail II;
- temporal split;
- BG/NBD + Gamma-Gamma assumptions;
- randomized monetary campaign source hoặc simulation contract;
- tách predicted CLV khỏi incremental CLV estimand.

Không ghép Online Retail II với Criteo rồi gọi là observed incremental CLV.

## Trạng thái gửi mentor

| Sprint | Trạng thái | Deliverable |
|---|---|---|
| Sprint 1 | Hoàn thành | causal release/evidence |
| Sprint 2 | Local/product hoàn thành; CF cloud pending | dashboard + policy report |
| Sprint 3 | Chưa bắt đầu | portfolio/release package |
