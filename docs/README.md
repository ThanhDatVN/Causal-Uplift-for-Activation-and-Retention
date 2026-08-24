# Chỉ mục tài liệu

`docs/` chứa **phương pháp** — cách từng thành phần hoạt động và vì sao chọn như vậy.
Kết quả nằm ở [`../report/`](../report/); bối cảnh nghiên cứu ở
[`../planning/`](../planning/).

```text
docs/
├── END_TO_END_WORKFLOW.md                mạch phát triển toàn dự án, từ đầu tới sản phẩm
├── GLOSSARY.md                           89 thuật ngữ, xếp theo 11 chủ đề
├── SPRINT_1_THEORY_AND_METHOD_GUIDE.md   lý thuyết nền, sáu model, metric
├── SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md  undersampling, calibration, policy value
├── SPRINT_3_METHOD_GUIDE.md              policy_area_dr, RATE/AUTOC, cross-fitting
├── CAUSAL_FOUNDATION_METHOD_GUIDE.md     DINA, Anchored R, partial pooling, experiment gate
├── CAUSAL_FOREST_METHOD_GUIDE.md         honest splitting, ba profile, ràng buộc outcome hiếm
├── DATA_OPTIMIZATION_METHOD_GUIDE.md     sentinel augmentation, funnel S-learner, ablation
├── TOP_TAIL_POLICY_INFERENCE_GUIDE.md    hard top-k, paired/simultaneous CI, event support
├── DECISION_CONTRACT.md                  policy phát hành, công thức, guardrail
├── REPRODUCTION.md                       runbook tái lập cho mọi vòng thí nghiệm
├── data_cards/                           nguồn gốc, schema, giới hạn dữ liệu
└── model_cards/                          model card champion
```

**Tên file theo sprint, nội dung theo chủ đề.** Bảy method guide được đặt tên theo vòng
viết ra chúng, nên tìm theo tên file sẽ khó. Dùng bảng tra theo chủ đề ngay dưới thay vì
đoán từ tên.

## Tra theo chủ đề

Cột trái là **khái niệm**, không phải tên file. Đây là cách tìm nhanh nhất.

| Chủ đề | Đọc ở |
|---|---|
| Một thuật ngữ bất kỳ | [GLOSSARY.md](GLOSSARY.md) |
| Potential outcomes, ATE, CATE | [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) |
| Sáu họ model và cơ chế từng cái | [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) |
| Undersampling và khôi phục thang xác suất | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| Calibration, τ-isotonic, EUCE | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| Policy value, đường cong ngân sách, break-even | [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) |
| **`policy_area_dr`** — metric chính | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| RATE, AUTOC, TOC | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| Cross-fitting, OOF, nuisance dùng chung | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| DR signal và vì sao nó thay IPW | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| Ensemble: Q-aggregation, rank average | [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) |
| DINA, Anchored R, partial pooling | [CAUSAL_FOUNDATION_METHOD_GUIDE.md](CAUSAL_FOUNDATION_METHOD_GUIDE.md) |
| Simultaneous band, familywise, hard top-k | [TOP_TAIL_POLICY_INFERENCE_GUIDE.md](TOP_TAIL_POLICY_INFERENCE_GUIDE.md) |
| Giới hạn của frozen-score inference | [TOP_TAIL_POLICY_INFERENCE_GUIDE.md](TOP_TAIL_POLICY_INFERENCE_GUIDE.md) |
| **Causal Forest**, honest splitting, `min_samples_leaf` | [CAUSAL_FOREST_METHOD_GUIDE.md](CAUSAL_FOREST_METHOD_GUIDE.md) |
| Sentinel augmentation, funnel S-learner | [DATA_OPTIMIZATION_METHOD_GUIDE.md](DATA_OPTIMIZATION_METHOD_GUIDE.md) |
| Vì sao xử lý dữ liệu phải qua gate | [DATA_OPTIMIZATION_METHOD_GUIDE.md](DATA_OPTIMIZATION_METHOD_GUIDE.md) mục 1 |
| Vì sao tín hiệu chấm điểm đổi thứ hạng | [CAUSAL_FOREST_METHOD_GUIDE.md](CAUSAL_FOREST_METHOD_GUIDE.md) mục 6 |
| Resource gate và ngân sách RAM | [CAUSAL_FOREST_METHOD_GUIDE.md](CAUSAL_FOREST_METHOD_GUIDE.md) mục 8 |
| Chẩn đoán: SMD, propensity AUC, proxy-ordering, overlap | [GLOSSARY.md](GLOSSARY.md) mục 8bis |
| **Chạy lại một vòng thí nghiệm** | [REPRODUCTION.md](REPRODUCTION.md) |
| Chạy trong Docker | [REPRODUCTION.md](REPRODUCTION.md) mục 11 |
| Promotion rule và luật quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Protocol đăng ký trước, gate, registry | [../configs/README.md](../configs/README.md) |
| Nguồn gốc và giới hạn dữ liệu | [data_cards/CRITEO_V2_1.md](data_cards/CRITEO_V2_1.md) |
| Vì sao dự án đi theo thứ tự đó | [END_TO_END_WORKFLOW.md](END_TO_END_WORKFLOW.md) |

## Bảy method guide — mô tả đầy đủ

Bảng trên tra theo khái niệm; bảng này mô tả **toàn bộ nội dung** của từng file, dùng khi
cần biết một guide có gì trước khi mở.

| Tài liệu | Nội dung |
|---|---|
| [SPRINT_1_THEORY_AND_METHOD_GUIDE.md](SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Uplift khác dự đoán thế nào, vì sao cần RCT, sáu model, outcome hiếm, metric, paired bootstrap |
| [SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md) | Undersampling và khôi phục xác suất, calibration, policy value IPW/DR |
| [SPRINT_3_METHOD_GUIDE.md](SPRINT_3_METHOD_GUIDE.md) | Vì sao đổi metric chính, `policy_area_dr`, RATE/AUTOC, cross-fitting, Rank-Learner, Q-aggregation |
| [CAUSAL_FOUNDATION_METHOD_GUIDE.md](CAUSAL_FOUNDATION_METHOD_GUIDE.md) | Binary DINA, risk-anchored R-Learner, sentinel partial pooling, synthetic validation và failure modes |
| [TOP_TAIL_POLICY_INFERENCE_GUIDE.md](TOP_TAIL_POLICY_INFERENCE_GUIDE.md) | Exact hard-k, factual DR value, paired bootstrap, simultaneous family band, support/overlap và giới hạn frozen-score inference |
| [CAUSAL_FOREST_METHOD_GUIDE.md](CAUSAL_FOREST_METHOD_GUIDE.md) | Chia nhánh theo hiệu ứng, honest splitting, số học sự kiện mỗi lá, ba profile, hai split, độ nhạy của tín hiệu chấm điểm, ràng buộc tài nguyên |
| [DATA_OPTIMIZATION_METHOD_GUIDE.md](DATA_OPTIMIZATION_METHOD_GUIDE.md) | Xử lý dữ liệu như một can thiệp, sentinel augmentation và ba ràng buộc của nó, phân rã funnel qua `visit`, thiết kế ablation bảy candidate |

## Hợp đồng và thẻ

| Tài liệu | Nội dung |
|---|---|
| [DECISION_CONTRACT.md](DECISION_CONTRACT.md) | Policy phát hành, công thức tính giá trị, guardrail |
| [data_cards/CRITEO_V2_1.md](data_cards/CRITEO_V2_1.md) | Nguồn gốc, schema, giới hạn của Criteo v2.1 |
| [model_cards/SPRINT_2_POLICY_RELEASE.md](model_cards/SPRINT_2_POLICY_RELEASE.md) | Model card champion, có mục cập nhật sau Sprint 3 |

## Chỉ mục thư mục khác

| Thư mục | Chỉ mục | Nội dung |
|---|---|---|
| `src/` | [../src/README.md](../src/README.md) | thư viện, xếp theo tầng pipeline |
| `scripts/` | [../scripts/README.md](../scripts/README.md) | script điều phối, theo vòng |
| `configs/` | [../configs/README.md](../configs/README.md) | sáu protocol đăng ký trước |
| `notebooks/` | [../notebooks/README.md](../notebooks/README.md) | bốn notebook, theo giai đoạn |
| `output/` | [../output/README.md](../output/README.md) | artifact, đâu là nguồn số chính thức |
| `report/` | [../report/README.md](../report/README.md) | tám báo cáo kết quả |
| `planning/` | [../planning/README.md](../planning/README.md) | nghiên cứu và hướng chưa mở |
| `tests/` | [../tests/README.md](../tests/README.md) | 294 test, xếp theo bất biến được bảo vệ |
| `webapp/` | [../webapp/README.md](../webapp/README.md) | sản phẩm, API và ranh giới |
| `benchmarks/` | [../benchmarks/README.md](../benchmarks/README.md) | đo tài nguyên, không phải kết quả khoa học |

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
