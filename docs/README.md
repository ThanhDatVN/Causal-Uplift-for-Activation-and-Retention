# Chỉ mục tài liệu

`docs/` chứa **phương pháp** — cách từng thành phần hoạt động và vì sao chọn như vậy.
Kết quả đã chạy nằm ở [`../report/`](../report/); bối cảnh nghiên cứu và hướng chưa mở
nằm ở [`../planning/`](../planning/).

```text
docs/
├── PROJECT_OVERVIEW.md      bản đầy đủ của README: chín giai đoạn, chi tiết từng vòng
├── END_TO_END_WORKFLOW.md   mạch phát triển toàn dự án, từ câu hỏi tới sản phẩm
├── GLOSSARY.md              89 thuật ngữ, xếp theo 11 chủ đề
├── DECISION_CONTRACT.md     policy phát hành, công thức giá trị, guardrail
├── REPRODUCTION.md          runbook tái lập cho mọi vòng thí nghiệm
├── methods/                 bảy method guide, đánh số theo thứ tự nên đọc
├── cards/                   data card và model card
└── assets/                  ảnh chụp web app dùng trong README
```

## Năm cửa vào

| Cần gì | Mở |
|---|---|
| Toàn cảnh dự án, chi tiết chín giai đoạn | [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) |
| Hiểu dự án làm gì và vì sao đi theo thứ tự đó | [END_TO_END_WORKFLOW.md](END_TO_END_WORKFLOW.md) |
| Tra một thuật ngữ | [GLOSSARY.md](GLOSSARY.md) |
| Biết luật ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
| Chạy lại một vòng thí nghiệm | [REPRODUCTION.md](REPRODUCTION.md) |

## Bảy method guide

Đánh số theo thứ tự nên đọc, cũng là thứ tự các vòng thí nghiệm đã chạy. Mỗi guide gắn với
báo cáo cùng số trong [`../report/`](../report/): guide nói **cách làm**, báo cáo nói **kết
quả ra sao**.

| # | Guide | Nội dung | Kết quả |
|---|---|---|---|
| 01 | [Nền tảng uplift](methods/01_UPLIFT_FOUNDATIONS.md) | uplift khác dự đoán thế nào, vì sao cần RCT, năm họ model, outcome hiếm, Qini/AUUC/EUCE, paired bootstrap | [báo cáo 01](../report/01_SPRINT_1_FOUNDATION.md) |
| 02 | [Calibration và giá trị policy](methods/02_CALIBRATION_AND_POLICY_VALUE.md) | undersampling và khôi phục thang xác suất, τ-isotonic, policy value IPW/DR, đường cong ngân sách | [báo cáo 02](../report/02_SPRINT_2_POLICY.md) |
| 03 | [Giao thức đánh giá](methods/03_EVALUATION_PROTOCOL.md) | **`policy_area_dr`**, RATE/AUTOC, cross-fitting, Rank-Learner, Q-aggregation, registry và promotion rule | [báo cáo 03](../report/03_SPRINT_3_IMPROVEMENT.md) |
| 04 | [Causal Forest](methods/04_CAUSAL_FOREST.md) | honest splitting, số học sự kiện mỗi lá, ba profile, độ nhạy của tín hiệu chấm điểm, ràng buộc tài nguyên | [báo cáo 04](../report/04_CAUSAL_FOREST.md) và [08](../report/08_CAUSAL_FOREST_RARE_OUTCOME.md) |
| 05 | [Biểu diễn dữ liệu](methods/05_DATA_REPRESENTATION.md) | xử lý dữ liệu như một can thiệp, sentinel augmentation, funnel S-learner, thiết kế ablation | [báo cáo 05](../report/05_DATA_OPTIMIZATION.md) |
| 06 | [Estimator cho outcome hiếm](methods/06_RARE_OUTCOME_LEARNERS.md) | DINA, Anchored R-Learner, Pattern R và partial pooling, kiểm thử tổng hợp, failure mode | [báo cáo 06](../report/06_CAUSAL_FOUNDATION.md) |
| 07 | [Suy luận top-tail](methods/07_TOP_TAIL_INFERENCE.md) | hard top-k chính xác, khoảng tin cậy ghép cặp và đồng thời, event support, giới hạn của frozen-score inference | [báo cáo 07](../report/07_TOP_TAIL_RESEARCH.md) |

## Tra theo chủ đề

Khi biết khái niệm nhưng chưa biết nó nằm ở guide nào.

| Chủ đề | Đọc ở |
|---|---|
| Một thuật ngữ bất kỳ | [GLOSSARY.md](GLOSSARY.md) |
| Potential outcome, ATE, CATE, điều kiện nhận dạng | [01](methods/01_UPLIFT_FOUNDATIONS.md) mục 1–2 |
| Cơ chế từng họ meta-learner | [01](methods/01_UPLIFT_FOUNDATIONS.md) mục 3 |
| Undersampling và khôi phục thang xác suất | [02](methods/02_CALIBRATION_AND_POLICY_VALUE.md) mục 2 |
| Calibration, τ-isotonic, EUCE | [02](methods/02_CALIBRATION_AND_POLICY_VALUE.md) mục 2–3 |
| Policy value, đường cong ngân sách, break-even | [02](methods/02_CALIBRATION_AND_POLICY_VALUE.md) mục 4–5 |
| **`policy_area_dr`** — metric chính | [03](methods/03_EVALUATION_PROTOCOL.md) mục 2 |
| RATE, AUTOC, TOC | [03](methods/03_EVALUATION_PROTOCOL.md) mục 3 |
| Cross-fitting, OOF, nuisance dùng chung | [03](methods/03_EVALUATION_PROTOCOL.md) mục 5 |
| Promotion rule và registry | [03](methods/03_EVALUATION_PROTOCOL.md) mục 8 |
| Honest splitting, `min_samples_leaf` cho outcome hiếm | [04](methods/04_CAUSAL_FOREST.md) mục 2–4 |
| Vì sao tín hiệu chấm điểm đổi thứ hạng | [04](methods/04_CAUSAL_FOREST.md) mục 6 |
| Resource gate và ngân sách RAM | [04](methods/04_CAUSAL_FOREST.md) mục 8 |
| Vì sao xử lý dữ liệu phải qua gate | [05](methods/05_DATA_REPRESENTATION.md) mục 1 |
| Sentinel augmentation, funnel S-learner | [05](methods/05_DATA_REPRESENTATION.md) mục 2–3 |
| DINA, Anchored R, partial pooling | [06](methods/06_RARE_OUTCOME_LEARNERS.md) mục 2–4 |
| Simultaneous band, familywise, hard top-k | [07](methods/07_TOP_TAIL_INFERENCE.md) mục 1–4 |
| Giới hạn của frozen-score inference | [07](methods/07_TOP_TAIL_INFERENCE.md) mục 5 |
| Chẩn đoán: SMD, propensity AUC, proxy-ordering, overlap | [GLOSSARY.md](GLOSSARY.md) mục 8bis |
| Cấu trúc thật của 12 đặc trưng | [cards/DATA_CARD_CRITEO_V2_1.md](cards/DATA_CARD_CRITEO_V2_1.md) mục 4 |
| Protocol đăng ký trước, gate, registry | [../configs/README.md](../configs/README.md) |
| Chạy trong Docker | [REPRODUCTION.md](REPRODUCTION.md) mục 11 |

## Candidate và họ model

Bảng kết quả liệt kê **candidate**, tài liệu phương pháp mô tả **họ model**. Một candidate
là một cấu hình cụ thể đã đăng ký để chạy: **họ + tiền xử lý + siêu tham số**. Dự án đã chạy
**31 candidate** thuộc **12 họ**, cộng ba ensemble (ensemble không phải một họ — nó tổ hợp
điểm của các candidate đã có).

### Giải mã tên candidate

Hậu tố trong tên mã hóa đúng phần cấu hình khác biệt so với bản gốc của họ:

| Hậu tố | Nghĩa |
|---|---|
| `-Under7` | undersampling giữ toàn bộ positive, `k = 7` |
| `-Renormalized` | undersampling `k = 7` rồi chia lại điểm cho `k` |
| `-Calibrated` | thêm τ-isotonic trên validation |
| `-LocalExact` | khôi phục xác suất chính xác theo từng nhánh thay vì chia `1/k` |
| `-Binary` / `-Regression` | nuisance là classifier / regressor |
| `-MC2` | `mc_iters = 2`, trung bình hai lần cross-fit để giảm phương sai |
| `-K05` / `-K1` / `-K2` | `kappa_scale` = `0,5` / `1,0` / `2,0` của Rank-Learner |
| `-Sentinel` | thêm cờ nhị phân `x_j == mode_j` |
| `-R25` | shrinkage phần dư `0,25` của Anchored R |

### Toàn bộ 31 candidate

Cột **Vòng** là vòng candidate được đăng ký chạy; một số candidate chạy lại ở nhiều vòng.

| Họ | Guide | Candidate | Vòng |
|---|:-:|---|:-:|
| `response` | [01](methods/01_UPLIFT_FOUNDATIONS.md) | `Response` | 1–8 |
| | [05](methods/05_DATA_REPRESENTATION.md) | `Response-Sentinel` | 5, 6 |
| `s_learner` | [01](methods/01_UPLIFT_FOUNDATIONS.md) | `S-Learner`, `S-Under7` | 1, 3 |
| | [05](methods/05_DATA_REPRESENTATION.md) | `S-Sentinel-Under7` | 5 |
| `t_learner` | [01](methods/01_UPLIFT_FOUNDATIONS.md) | `T-Learner`, `T-Under7` | 1, 3 |
| | [02](methods/02_CALIBRATION_AND_POLICY_VALUE.md) | `T-LocalExact` | 2 |
| `x_learner` | [01](methods/01_UPLIFT_FOUNDATIONS.md) | `X-Learner` | 1 |
| | [02](methods/02_CALIBRATION_AND_POLICY_VALUE.md) | `X-Renormalized`, `X-Calibrated` | 2, 3, 5 |
| `dr_learner` | [01](methods/01_UPLIFT_FOUNDATIONS.md) | `DR-Learner`, `DR-Regression`, `DR-Binary`, `DR-Binary-MC2` | 1, 3 |
| `r_learner` | [03](methods/03_EVALUATION_PROTOCOL.md) mục 5bis | `R-Regression`, `R-Binary` | 3 |
| `rank_learner` | [03](methods/03_EVALUATION_PROTOCOL.md) mục 6 | `Rank-K05`, `Rank-K1`, `Rank-K2` | 3 |
| `causal_forest` | [04](methods/04_CAUSAL_FOREST.md) | `Causal-Forest-kaggle-safe`, `Causal-Forest-rare-outcome` | 4, 8 |
| `funnel_s_learner` | [05](methods/05_DATA_REPRESENTATION.md) | `Funnel-S`, `Funnel-S-Sentinel` | 5 |
| `anchored_r_learner` | [06](methods/06_RARE_OUTCOME_LEARNERS.md) mục 3 | `Anchored-R25`, `Anchored-R25-Sentinel` | 6 |
| `anchored_pattern_r_learner` | [06](methods/06_RARE_OUTCOME_LEARNERS.md) mục 4 | `Anchored-Pattern-R` | 6 |
| `binary_dina_learner` | [06](methods/06_RARE_OUTCOME_LEARNERS.md) mục 2 | `DINA-CATE-Sentinel` | 6 |
| *(tổ hợp)* | [03](methods/03_EVALUATION_PROTOCOL.md) mục 7 | `Ensemble-QAgg`, `Ensemble-BestSingle`, `Ensemble-RankAverage` | 3 |

Nguồn của bảng: trường `family` trong [`../configs/`](../configs/) và cột `candidate_family`
của `output/improvement/registry.csv`. Kết cục từng candidate:
[`../report/README.md`](../report/README.md) mục "Toàn bộ thử nghiệm đã chạy".

## Thẻ

| Thẻ | Nội dung |
|---|---|
| [cards/DATA_CARD_CRITEO_V2_1.md](cards/DATA_CARD_CRITEO_V2_1.md) | nguồn gốc, schema, hợp đồng chất lượng, cấu trúc đặc trưng và giới hạn của Criteo v2.1 |
| [cards/MODEL_CARD_RESPONSE_TOPK.md](cards/MODEL_CARD_RESPONSE_TOPK.md) | champion đang phát hành, kết quả, giới hạn đã biết, hạng mục giám sát |

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

Mỗi tài liệu mở bằng một khối metadata dạng danh sách `- **Nhãn:**` ghi vòng sinh ra nó,
protocol, hiện thực, kết quả và tài liệu đọc kèm — người đọc biết ngay tài liệu thuộc về đâu
trước khi đọc nội dung.

Quy ước hình thức, thống nhất trên toàn repo:

| Hạng mục | Quy ước | Vì sao |
|---|---|---|
| Gạch nối và dấu trừ | chỉ dùng `-` ASCII | tên candidate viết bằng gạch nối U+2011 hiển thị y hệt nhưng là **chuỗi khác** với `X-Renormalized` trong `configs/`, nên `grep` và Ctrl+F không tìm ra. Test `tests/test_documentation_integrity.py` chặn U+2011 và U+2212 |
| Dấu ngoặc kép | chỉ dùng `"` thẳng | cùng lý do với gạch nối: ngoặc cong không tìm được bằng cùng một chuỗi |
| Số thập phân | dấu phẩy: `0,000912` | thống nhất với toàn bộ văn bản tiếng Việt trong repo |
| Ngày tháng | `dd/mm/yyyy` | trước đây trộn `dd/mm/yyyy` với ISO giữa các báo cáo |
| Dấu thanh | `hòa`, `hóa`, `khóa`, `thỏa` | repo từng trộn hai lối đặt dấu cho cùng một từ |
| Xuống dòng trong đoạn | không dùng hai dấu cách cuối dòng | vừa vô hình vừa bị `git diff --check` báo lỗi |

Viết tiếng Việt trước; chỉ giữ nguyên tiếng Anh cho tên riêng, tên định danh trong code và
thuật ngữ chưa có tương đương ổn định (`policy_area_dr`, `fold seed`, `confirmation`). Những
từ như *full*, *rows*, *family*, *point*, *audit* thì dịch.
