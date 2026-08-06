# Chỉ mục tài liệu

Mỗi tài liệu có một trạng thái. Chỉ đọc tài liệu **Hiện hành** khi cần số liệu hoặc
hướng dẫn thực thi; tài liệu **Lịch sử** được giữ để truy vết, không dùng làm nguồn số.

## Bắt đầu từ đâu

| Bạn muốn | Đọc |
|---|---|
| Hiểu dự án từ đầu đến cuối | [PROJECT_GUIDE.md](PROJECT_GUIDE.md) |
| Rà soát và kiểm chứng từng thành phần | [COMPONENT_REVIEW_GUIDE.md](COMPONENT_REVIEW_GUIDE.md) |
| Đọc tiến độ theo tuần | [../report/weekly/](../report/weekly/) |
| Xem kết quả mới nhất | [../report/SPRINT_3_FINAL_REPORT.md](../report/SPRINT_3_FINAL_REPORT.md) |
| Xem kết quả Causal Forest | [../report/CAUSAL_FOREST_REPORT.md](../report/CAUSAL_FOREST_REPORT.md) |
| Chạy web app | [WEBAPP.md](WEBAPP.md) |
| Chạy lại Causal Forest trên Kaggle | [NOTEBOOK_GUIDE.md](NOTEBOOK_GUIDE.md) rồi [KAGGLE_RUNBOOK_COMPLETE.md](KAGGLE_RUNBOOK_COMPLETE.md) |
| Biết làm gì tiếp theo | [../planning/NEXT_ROUND_PLAN.md](../planning/NEXT_ROUND_PLAN.md) |
| Biết quy tắc ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Mở hướng nghiên cứu mới | [../planning/RESEARCH_LANDSCAPE_2026.md](../planning/RESEARCH_LANDSCAPE_2026.md) |

## Hiện hành

| Tài liệu | Nội dung |
|---|---|
| [COMPONENT_REVIEW_GUIDE.md](COMPONENT_REVIEW_GUIDE.md) | Quy trình rà soát từng thành phần: đọc gì, chạy lệnh gì để kiểm chứng, dấu hiệu sai |
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | Hướng dẫn toàn diện: trình tự đọc, kiến trúc split, từng module, metric, model, web app, bẫy khi đọc kết quả, thuật ngữ |
| [NOTEBOOK_GUIDE.md](NOTEBOOK_GUIDE.md) | Chạy notebook nào ở đâu, từng bước trên Kaggle, và bảng trạng thái phần code còn lại |
| [KAGGLE_RUNBOOK_COMPLETE.md](KAGGLE_RUNBOOK_COMPLETE.md) | Runbook đầy đủ cho Causal Forest trên Kaggle: code dán được, danh mục 15 lỗi, checklist |
| [WEBAPP.md](WEBAPP.md) | Kiến trúc, endpoint và kiểm thử của web application |
| [DECISION_CONTRACT.md](DECISION_CONTRACT.md) | Hợp đồng quyết định: policy phát hành, công thức, guardrail |
| [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) | Phương pháp thêm ở Sprint 3 và ranh giới nguồn của từng phần |
| [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) | Phương pháp Sprint 2: undersampling, calibration, policy value |
| [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Lý thuyết nền và phương pháp Sprint 1 |
| [data_cards/CRITEO_V2_1.md](data_cards/CRITEO_V2_1.md) | Data card: nguồn gốc, schema, giới hạn |
| [model_cards/SPRINT_2_POLICY_RELEASE.md](model_cards/SPRINT_2_POLICY_RELEASE.md) | Model card champion, có mục cập nhật sau Sprint 3 |

## Lịch sử

[archive/](archive/) — bốn tài liệu đã bị thay thế, giữ để truy vết đường dẫn trong báo
cáo lịch sử. Xem [archive/README.md](archive/README.md) cho bảng "thay bằng gì, vì sao".

Tài liệu lịch sử khác: [`../report/archive/`](../report/archive/), `planning/RUN_PLAN.md`,
`planning/CAUSAL_UPLIFT_PLAN.md`, `notebooks/`.


## Chỉ mục thư mục khác

| Thư mục | Chỉ mục |
|---|---|
| `scripts/` | [../scripts/README.md](../scripts/README.md) — 27 script nhóm theo vai trò và trạng thái |
| `output/` | [../output/README.md](../output/README.md) — artifact nào là release, artifact nào là phát triển |
| `planning/` | [../planning/README.md](../planning/README.md) |
| `report/` | [../report/README.md](../report/README.md) — ba báo cáo sprint, sáu báo cáo tuần, archive |

## Quy tắc viết tài liệu

Ghi trong `CLAUDE.md`. Tóm tắt: dùng metric, split, interval, runtime hoặc trạng thái
artifact thay cho tính từ tự đánh giá; không emoji, không câu hỏi tu từ, không giọng
quảng bá; viết "đạt/không đạt gate", "CI chứa/không chứa 0", "đã/chưa có artifact";
phân biệt rõ biến quan sát, estimate, input kịch bản và kết quả semi-synthetic.
