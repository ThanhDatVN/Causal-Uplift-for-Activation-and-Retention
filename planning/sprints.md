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

## Sprint 3 — Vòng cải tiến model và web application (Tuần 5–6)

**Trạng thái 05/08/2026:** đã chạy. Bằng chứng: `report/SPRINT_3_FINAL_REPORT.md`,
`output/sprint3/`, `output/improvement/`. Kế hoạch chi tiết:
`planning/SPRINT_3_EXECUTION_AND_WEB_PLAN.md`.

**Đã hoàn thành:**

- protocol đăng ký trước với metric chính `policy_area_dr`, gate và promotion rule;
- evaluation stack mới: TOC/RATE/AUTOC, outcome-adjusted variant, DR policy curve,
  expected-random và multi-seed random sensitivity, đều có synthetic-truth test;
- 3-fold cross-fitting OOF trên 5.591.836 dòng ở hai fold seed;
- 12 candidate screening gồm R-Learner, DR ablation và Rank-Learner (ICLR 2026);
- causal Q-aggregation và hai ensemble baseline;
- experiment registry ghi cả run bị dừng sớm;
- retrospective confirmation và áp promotion rule đúng một lần;
- web application có API, batch scoring, export và acceptance test;
- pytest 51 → 118, toàn bộ pass.

**Kết quả quyết định:** không challenger nào đạt promotion rule; champion giữ nguyên
Response.

**Chưa hoàn thành:** Causal Forest Kaggle, pROCini (không tiếp cận được công thức
gốc), external validity Hillstrom, production A/B test, resource gate kiểm tra liên tục.

## Sprint 3 — kế hoạch packaging ban đầu (giữ để đối chiếu)

Phần dưới là kế hoạch packaging viết ngày 31/07/2026. Work package 1–3 được thay
bằng vòng cải tiến model ở trên; work package 4–5 vẫn còn hiệu lực.

**Mục tiêu:** đóng gói artifact thành một release có thể chạy lại, kiểm tra và bàn giao.

### Work package 1 — Clean release

- tạo commit history/release tag sau khi user xác nhận;
- thêm CI test tối thiểu;
- clean-environment runbook hoặc Docker;
- link/source audit tự động;
- không còn stale claim trong notebook/report cũ.

**DoD:** clone → install → tests → build dashboard bằng command rõ ràng.

### Work package 2 — Tài liệu và demo

- video demo 60–90 giây;
- 6–8 slides: problem → identification → methods → evidence → policy → limitation;
- README 5-minute path;
- Q&A kỹ thuật về Response thắng, kết quả không cải thiện và leakage.

**DoD:** mọi con số trong video/slide link được về CSV/manifest.

### Work package 3 — Production thinking

- monitoring/data drift contract;
- production randomized holdout design;
- input/output schema cho batch scoring;
- latency/cost envelope;
- privacy/fairness/use limitation.

**DoD:** architecture/runbook mô tả đủ cách vận hành và giới hạn hệ thống; không cần dựng
backend phức tạp nếu chưa có giả thuyết và tiêu chí đánh giá xác định trước.

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
| Sprint 3 | Hoàn thành local; CF cloud vẫn pending | vòng cải tiến model có promotion rule + web application |
