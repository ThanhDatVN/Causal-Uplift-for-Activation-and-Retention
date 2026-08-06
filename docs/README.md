# Chỉ mục tài liệu

`docs/` chứa **cách làm** — phương pháp, hợp đồng quyết định, runbook. Kết quả nằm ở
[`../report/`](../report/); kế hoạch ở [`../planning/`](../planning/).

## Cấu trúc

```text
docs/
├── SPRINT_1_THEORY_AND_METHOD_GUIDE.md   lý thuyết nền, năm model, metric
├── SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md  undersampling, calibration, policy value
├── SPRINT_3_METHOD_GUIDE.md              policy_area_dr, RATE/AUTOC, cross-fitting
├── DECISION_CONTRACT.md                  policy phát hành, công thức, guardrail
├── KAGGLE_RUNBOOK_COMPLETE.md            runbook Causal Forest trên Kaggle
├── NOTEBOOK_GUIDE.md                     notebook nào chạy ở đâu
├── WEBAPP.md                             kiến trúc và kiểm thử web app
├── COMPONENT_REVIEW_GUIDE.md             quy trình tự rà soát từng thành phần
├── data_cards/                           nguồn gốc, schema, giới hạn dữ liệu
├── model_cards/                          model card champion
└── archive/                              lịch sử — một trang, không còn file rời
```

Ba file `GUIDE_01_BAI_TOAN.md`, `GUIDE_02_PHUONG_PHAP.md`, `GUIDE_03_KET_QUA.md` là tài
liệu học tạm thời, không nằm trong repo và không được liệt kê ở đây.

## Bắt đầu từ đâu

| Bạn muốn | Đọc |
|---|---|
| Hiểu lý thuyết nền và năm model | [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) |
| Hiểu cách biến xếp hạng thành quyết định | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| Hiểu metric chính hiện hành | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| Xem kết quả mới nhất | [../report/SPRINT_3_FINAL_REPORT.md](../report/SPRINT_3_FINAL_REPORT.md) |
| Xem kết quả Causal Forest | [../report/CAUSAL_FOREST_REPORT.md](../report/CAUSAL_FOREST_REPORT.md) |
| Đọc tiến độ theo tuần | [../report/weekly/](../report/weekly/) |
| Biết quy tắc ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Chạy web app | [WEBAPP.md](WEBAPP.md) |
| Chạy lại Causal Forest trên Kaggle | [KAGGLE_RUNBOOK_COMPLETE.md](KAGGLE_RUNBOOK_COMPLETE.md) |
| Tự rà soát từng thành phần | [COMPONENT_REVIEW_GUIDE.md](COMPONENT_REVIEW_GUIDE.md) |
| Biết làm gì tiếp theo | [../planning/NEXT_ROUND_PLAN.md](../planning/NEXT_ROUND_PLAN.md) |
| Mở hướng nghiên cứu mới | [../planning/RESEARCH_LANDSCAPE_2026.md](../planning/RESEARCH_LANDSCAPE_2026.md) |

## Phương pháp — một tài liệu cho mỗi sprint

| Tài liệu | Nội dung |
|---|---|
| [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Uplift khác dự đoán thế nào, vì sao cần RCT, năm model, outcome hiếm, metric, paired bootstrap |
| [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) | Undersampling và khôi phục xác suất, calibration, policy value IPW/DR, dashboard |
| [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) | Vì sao đổi metric chính, `policy_area_dr`, RATE/AUTOC, cross-fitting, Rank-Learner, Q-aggregation |

## Vận hành

| Tài liệu | Nội dung |
|---|---|
| [DECISION_CONTRACT.md](DECISION_CONTRACT.md) | Hợp đồng quyết định: policy phát hành, công thức, guardrail |
| [KAGGLE_RUNBOOK_COMPLETE.md](KAGGLE_RUNBOOK_COMPLETE.md) | Runbook Causal Forest: chuẩn bị session, từng cell, danh mục lỗi, cách đọc kết quả |
| [NOTEBOOK_GUIDE.md](NOTEBOOK_GUIDE.md) | Notebook nào chạy ở đâu, và trạng thái phần code còn lại |
| [WEBAPP.md](WEBAPP.md) | Kiến trúc, endpoint và kiểm thử web application |
| [COMPONENT_REVIEW_GUIDE.md](COMPONENT_REVIEW_GUIDE.md) | Quy trình rà soát từng thành phần: đọc gì, chạy lệnh gì, dấu hiệu sai |

## Thẻ dữ liệu và model

| Tài liệu | Nội dung |
|---|---|
| [data_cards/CRITEO_V2_1.md](data_cards/CRITEO_V2_1.md) | Nguồn gốc, schema, giới hạn của Criteo v2.1 |
| [model_cards/SPRINT_2_POLICY_RELEASE.md](model_cards/SPRINT_2_POLICY_RELEASE.md) | Model card champion, có mục cập nhật sau Sprint 3 |

## Lịch sử

[archive/README.md](archive/README.md) — một trang duy nhất. Bốn file stub trước đây đã
được gộp vào đó; nội dung gốc nằm trong lịch sử git.

Tài liệu lịch sử khác: [`../report/archive/`](../report/archive/),
[`../planning/RUN_PLAN.md`](../planning/RUN_PLAN.md),
[`../planning/CAUSAL_UPLIFT_PLAN.md`](../planning/CAUSAL_UPLIFT_PLAN.md), `notebooks/`.

## Chỉ mục thư mục khác

| Thư mục | Chỉ mục |
|---|---|
| `scripts/` | [../scripts/README.md](../scripts/README.md) |
| `output/` | [../output/README.md](../output/README.md) |
| `planning/` | [../planning/README.md](../planning/README.md) |
| `report/` | [../report/README.md](../report/README.md) |

## Quy tắc viết tài liệu

Ghi trong `CLAUDE.md`. Tóm tắt: dùng metric, split, interval, runtime hoặc trạng thái
artifact thay cho tính từ tự đánh giá; không emoji, không câu hỏi tu từ, không giọng
quảng bá; viết "đạt/không đạt gate", "CI chứa/không chứa 0", "đã/chưa có artifact";
phân biệt rõ biến quan sát, estimate, input kịch bản và kết quả semi-synthetic.
