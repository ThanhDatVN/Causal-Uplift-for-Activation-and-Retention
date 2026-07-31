# 07 — Định hướng Portfolio và CV (Portfolio and CV Direction)

## Nội dung trình bày portfolio

Không kể thành ba dự án rời:

1. causal uplift;
2. probabilistic CLV;
3. một dashboard.

Kể thành một quá trình phát triển quyết định:

> “Từ conversion uplift ngắn hạn → customer value forecast → cost-aware incremental value policy
> → sản phẩm ra quyết định có uncertainty và audit trail.”

## Artifact công khai (Public Artifacts)

### GitHub

- README business-first có screenshot/GIF;
- architecture diagram;
- measured result table;
- quickstart;
- `pyproject.toml` + lock;
- unit/integration tests + CI;
- Dockerfile;
- data/model cards;
- experiment protocol;
- releases `causal-v0.1`, `clv-v0.2`, `v1.0`.

### Demo

- public Incremental Value Studio;
- sample mode;
- scenario sliders;
- model evidence;
- CSV export;
- banner provenance.

### Communication

- executive case study 4–6 trang;
- technical report 10–15 trang;
- slide 8–10 trang;
- demo video 2–3 phút;
- Q&A sheet.

## Cấu trúc README (README Structure)

1. One-line problem.
2. Product screenshot/GIF.
3. Why propensity/predicted CLV is insufficient.
4. Data/evidence modes.
5. Architecture.
6. Measured results with CI.
7. Demo workflow.
8. Reproducibility.
9. Limitations.

Phần result đứng trước danh sách model.

## Dàn ý video demo (Demo Video Outline)

1. 0:00–0:20 — business problem.
2. 0:20–0:45 — compare propensity/CLV/iCV policies.
3. 0:45–1:30 — budget/cost/horizon scenario.
4. 1:30–2:00 — policy value + uncertainty.
5. 2:00–2:30 — provenance/limitations.
6. 2:30–3:00 — architecture/reproducibility.

## Phần trình bày phỏng vấn 90 giây (90-Second Interview Summary)

> “Tôi bắt đầu từ uplift modeling trên một RCT gần 14 triệu dòng và nhận ra Qini tốt không đồng
> nghĩa với quyết định có giá trị dài hạn. Tôi xây thêm probabilistic CLV trên transaction data
> với temporal holdout, rồi thiết kế policy layer tối ưu expected incremental net value thay vì
> predicted CLV. Public data không có một bộ vừa randomized vừa longitudinal đầy đủ, nên tôi tách
> bằng chứng thành real causal, real CLV, real monetary RCT ngắn hạn và semi-synthetic integration
> có ground truth. Sản phẩm cuối cho marketer chọn horizon, cost và budget, so sánh policy, xem CI
> và export campaign list. Tôi có thể chỉ rõ phần nào là causal evidence, projection và simulation.”

## Gạch đầu dòng cho CV (CV Bullets)

Chỉ điền `[X]` sau final run.

### Causal hiện có

> Built a reproducible uplift-modeling pipeline on a 14.0M-row randomized advertising dataset,
> benchmarking five CATE/response models with Qini, AUUC and 500× bootstrap inference; the top
> decile captured approximately 85% of observed incremental conversions.

### Probabilistic + causal value

> Developed a temporally validated probabilistic CLV pipeline on 1.07M retail transactions using
> BG/NBD and Gamma-Gamma, then optimized treatment allocation by estimated incremental customer
> value rather than predicted CLV, improving held-out policy value by `[X%]` over `[baseline]`.

### Sản phẩm/kỹ thuật (Product/Engineering)

> Productized the research as an interactive decision engine with budget/cost sensitivity,
> doubly robust offline policy evaluation, uncertainty intervals and batch campaign export;
> shipped a Dockerized, CI-tested public demo reproducible from a single command.

Không ghi “increased production revenue by X%”.

## Chỉ số headline cần thu được (Headline Metrics)

- CLV temporal holdout error/calibration;
- policy value gain vs predicted CLV;
- incremental net value at a fixed budget;
- bootstrap CI;
- policy regret vs oracle trên semi-synthetic;
- seed/cutoff stability;
- runtime/reproducibility.

## Checklist cho nhà tuyển dụng (Recruiter Checklist)

- Mở README 30 giây thấy problem/result/demo.
- Click demo không cần data riêng.
- Có link report và architecture.
- Có CI badge/test.
- Không có notebook-only production logic.
- Không có data lớn trong Git.
- Không có claim giả về dataset join/CLV/revenue.
- CV number khớp README và artifact.

## Hỏi đáp cần chuẩn bị (Q&A)

1. Vì sao predicted CLV không đủ để target?
2. iCV khác `CATE × CLV` thế nào?
3. Vì sao không join Criteo và Online Retail?
4. Offline policy value được ước lượng ra sao?
5. Vì sao dùng semi-synthetic?
6. Làm sao tránh temporal/post-treatment leakage?
7. Nếu causal model không hơn predicted CLV thì kết luận gì?
8. BG/NBD/Gamma-Gamma giả định gì và fail khi nào?
9. Tại sao không dùng Qini làm metric duy nhất?
10. Bước tiếp theo nếu có campaign log từ hệ thống triển khai là gì?
