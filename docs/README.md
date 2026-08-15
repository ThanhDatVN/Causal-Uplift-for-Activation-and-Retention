# Chỉ mục tài liệu

`docs/` chứa **phương pháp** — cách từng thành phần hoạt động và vì sao chọn như vậy.
Kết quả nằm ở [`../report/`](../report/); bối cảnh nghiên cứu ở
[`../planning/`](../planning/).

```text
docs/
├── SPRINT_1_THEORY_AND_METHOD_GUIDE.md   lý thuyết nền, sáu model, metric
├── SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md  undersampling, calibration, policy value
├── SPRINT_3_METHOD_GUIDE.md              policy_area_dr, RATE/AUTOC, cross-fitting
├── CAUSAL_FOUNDATION_METHOD_GUIDE.md     DINA, Anchored R, partial pooling, experiment gate
├── TOP_TAIL_POLICY_INFERENCE_GUIDE.md     hard top-k, paired/simultaneous CI, event support
├── DECISION_CONTRACT.md                  policy phát hành, công thức, guardrail
├── REPRODUCTION.md                       runbook tái lập cho mọi vòng thí nghiệm
├── data_cards/                           nguồn gốc, schema, giới hạn dữ liệu
└── model_cards/                          model card champion
```

## Bắt đầu từ đâu

| Bạn muốn | Đọc |
|---|---|
| Hiểu lý thuyết nền và sáu model | [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) |
| Hiểu cách biến xếp hạng thành quyết định | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| Hiểu metric chính hiện hành | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| Hiểu inference cho policy 1–2% | [TOP_TAIL_POLICY_INFERENCE_GUIDE.md](TOP_TAIL_POLICY_INFERENCE_GUIDE.md) |
| Biết quy tắc ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Chạy lại một vòng thí nghiệm | [REPRODUCTION.md](REPRODUCTION.md) |
| Xem kết quả mới nhất | [../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md](../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md) |
| Xem ba mốc Causal Forest trên Kaggle | [../report/CAUSAL_FOREST_REPORT.md](../report/CAUSAL_FOREST_REPORT.md) |
| Hiểu vì sao tín hiệu chấm điểm đổi thứ hạng | [../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md](../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md) mục 5 |
| Đọc deep research sau thí nghiệm | [../planning/CAUSAL_DEEP_RESEARCH_2026.md](../planning/CAUSAL_DEEP_RESEARCH_2026.md) |
| Hiểu bối cảnh nghiên cứu | [../planning/RESEARCH_LANDSCAPE_2026.md](../planning/RESEARCH_LANDSCAPE_2026.md) |

## Phương pháp — một tài liệu cho mỗi sprint

| Tài liệu | Nội dung |
|---|---|
| [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Uplift khác dự đoán thế nào, vì sao cần RCT, sáu model, outcome hiếm, metric, paired bootstrap |
| [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) | Undersampling và khôi phục xác suất, calibration, policy value IPW/DR |
| [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) | Vì sao đổi metric chính, `policy_area_dr`, RATE/AUTOC, cross-fitting, Rank-Learner, Q-aggregation |
| [CAUSAL_FOUNDATION_METHOD_GUIDE.md](CAUSAL_FOUNDATION_METHOD_GUIDE.md) | Binary DINA, risk-anchored R-Learner, sentinel partial pooling, synthetic validation và failure modes |
| [TOP_TAIL_POLICY_INFERENCE_GUIDE.md](TOP_TAIL_POLICY_INFERENCE_GUIDE.md) | Exact hard-k, factual DR value, paired bootstrap, simultaneous family band, support/overlap và giới hạn frozen-score inference |

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

Quy ước hình thức, thống nhất trên toàn repo:

| Hạng mục | Quy ước | Vì sao |
|---|---|---|
| Gạch nối và dấu trừ | chỉ dùng `-` ASCII | tên candidate viết bằng gạch nối U+2011 hiển thị y hệt nhưng là **chuỗi khác** với `X-Renormalized` trong `configs/`, nên `grep` và Ctrl+F không tìm ra. Test `tests/test_documentation_integrity.py` chặn U+2011 và U+2212 |
| Số thập phân | dấu phẩy: `0,000912` | thống nhất với toàn bộ văn bản tiếng Việt trong repo |
| Ngày tháng | `dd/mm/yyyy` | trước đây trộn `dd/mm/yyyy` với ISO giữa các báo cáo |
| Dấu thanh | `hòa`, `hóa`, `khóa`, `thỏa` | repo từng trộn hai lối đặt dấu cho cùng một từ |
| Đầu mỗi báo cáo | danh sách `- **Nhãn:**` | xuống dòng bằng hai dấu cách cuối dòng vừa vô hình vừa bị `git diff --check` báo lỗi |

Viết tiếng Việt trước; chỉ giữ nguyên tiếng Anh cho tên riêng, tên định danh trong code và
thuật ngữ chưa có tương đương ổn định (`policy_area_dr`, `fold seed`, `confirmation`). Những
từ như *full*, *rows*, *family*, *point*, *audit* thì dịch.
