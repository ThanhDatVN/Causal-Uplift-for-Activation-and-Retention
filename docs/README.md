# Chỉ mục tài liệu

`docs/` chứa **phương pháp** — cách từng thành phần hoạt động và vì sao chọn như vậy.
Kết quả nằm ở [`../report/`](../report/); bối cảnh nghiên cứu ở
[`../planning/`](../planning/).

```text
docs/
├── SPRINT_1_THEORY_AND_METHOD_GUIDE.md   lý thuyết nền, sáu model, metric
├── SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md  undersampling, calibration, policy value
├── SPRINT_3_METHOD_GUIDE.md              policy_area_dr, RATE/AUTOC, cross-fitting
├── DECISION_CONTRACT.md                  policy phát hành, công thức, guardrail
├── data_cards/                           nguồn gốc, schema, giới hạn dữ liệu
└── model_cards/                          model card champion
```

## Bắt đầu từ đâu

| Bạn muốn | Đọc |
|---|---|
| Hiểu lý thuyết nền và sáu model | [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) |
| Hiểu cách biến xếp hạng thành quyết định | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| Hiểu metric chính hiện hành | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| Biết quy tắc ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Xem kết quả mới nhất | [../report/SPRINT_3_FINAL_REPORT.md](../report/SPRINT_3_FINAL_REPORT.md) |
| Xem kết quả Causal Forest | [../report/CAUSAL_FOREST_REPORT.md](../report/CAUSAL_FOREST_REPORT.md) |
| Hiểu bối cảnh nghiên cứu | [../planning/RESEARCH_LANDSCAPE_2026.md](../planning/RESEARCH_LANDSCAPE_2026.md) |

## Phương pháp — một tài liệu cho mỗi sprint

| Tài liệu | Nội dung |
|---|---|
| [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Uplift khác dự đoán thế nào, vì sao cần RCT, sáu model, outcome hiếm, metric, paired bootstrap |
| [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) | Undersampling và khôi phục xác suất, calibration, policy value IPW/DR |
| [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) | Vì sao đổi metric chính, `policy_area_dr`, RATE/AUTOC, cross-fitting, Rank-Learner, Q-aggregation |

## Hợp đồng và thẻ

| Tài liệu | Nội dung |
|---|---|
| [DECISION_CONTRACT.md](DECISION_CONTRACT.md) | Policy phát hành, công thức tính giá trị, guardrail |
| [data_cards/CRITEO_V2_1.md](data_cards/CRITEO_V2_1.md) | Nguồn gốc, schema, giới hạn của Criteo v2.1 |
| [model_cards/SPRINT_2_POLICY_RELEASE.md](model_cards/SPRINT_2_POLICY_RELEASE.md) | Model card champion, có mục cập nhật sau Sprint 3 |

## Chỉ mục thư mục khác

| Thư mục | Chỉ mục |
|---|---|
| `scripts/` | [../scripts/README.md](../scripts/README.md) |
| `output/` | [../output/README.md](../output/README.md) |
| `planning/` | [../planning/README.md](../planning/README.md) |
| `report/` | [../report/README.md](../report/README.md) |

## Quy tắc viết tài liệu

Dùng metric, split, interval, runtime hoặc trạng thái artifact thay cho tính từ tự đánh
giá. Không emoji, không câu hỏi tu từ, không giọng quảng bá. Viết "đạt/không đạt gate",
"CI chứa/không chứa 0", "đã/chưa có artifact". Phân biệt rõ biến quan sát, estimate, input
kịch bản và kết quả semi-synthetic.
