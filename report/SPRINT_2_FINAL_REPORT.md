# Báo cáo Sprint 2 — Từ mô hình causal đến policy và dashboard

- **Run ID:** `sprint2-local-exact-calibration-v1`
- **Ngày:** 31/07/2026
- **Nguồn số chính thức:** `output/sprint2/`
- **Trạng thái:** hoàn thành pipeline local và dashboard; Causal Forest trên Kaggle còn treo
  tại thời điểm chốt báo cáo

## 1. Kết quả điều hành

Sprint 2 đã biến nghiên cứu uplift thành sản phẩm quyết định chạy được:

- tạo confirmation set mới 1.397.959 dòng, không tái sử dụng final test Sprint 1;
- thử X-Learner renormalization, τ-isotonic và exact local restoration;
- khóa Response top-k làm operational champion từ validation;
- chấm policy bằng IPW/DR và 500 paired bootstrap;
- tạo dashboard self-contained, 11/11 browser acceptance checks pass;
- đóng gói gate Causal Forest cho Kaggle, nhưng không claim cloud result khi chưa chạy.

Kết quả model: X-Renormalized có Qini confirmation cao nhất (`0,191557`),
nhưng hơn Response `0,008768` với CI `[-0,018626; 0,038772]`. Chưa đủ bằng chứng đổi
champion đã chọn trên validation.

## 2. Data protocol và chống leakage

Sprint 1 đã dùng stratified 50%, seed 42. Sprint 2 tái dựng đúng sample đó và chỉ lấy
phần bù:

| Split | Rows | Treatment rate | Conversion rate |
|---|---:|---:|---:|
| fit | 4.193.877 | 0,850000 | 0,002917 |
| validation | 1.397.959 | 0,850000 | 0,002916 |
| confirmation | 1.397.959 | 0,850001 | 0,002916 |

Hash của ba source-index được lưu trong manifest. Pipeline Sprint 2 không đọc prediction
hay Y/T của final test Sprint 1.

**Vì sao lấy phần bù thay vì lấy mẫu mới.** Một sample ngẫu nhiên mới trên toàn bộ 13,98
triệu dòng gần như chắc chắn chồng lấn với test Sprint 1. Chồng lấn đó không gây lỗi chạy
và cũng không hiện ra trong bất kỳ metric nào — nó chỉ âm thầm biến "confirmation" thành
một phần dữ liệu đã được nhìn. Lấy đúng phần bù của sample 50% seed 42 là cách duy nhất
loại trừ khả năng đó một cách kiểm chứng được, và đó là lý do
`src/data.py::stratified_complement` tồn tại thay vì gọi lại `stratified_sample` với seed
khác.

Ba split có conversion rate `0,002917 / 0,002916 / 0,002916` và treatment rate `0,85` gần
như trùng khít nhau. Đây là kiểm tra bắt buộc chứ không phải trang trí: nếu phép chia làm
lệch tỷ lệ outcome hiếm giữa các split thì mọi so sánh giữa validation và confirmation sẽ
lẫn hiệu ứng của split vào hiệu ứng của model.

## 3. Phương pháp và evidence audit

| Thành phần | Nguồn đã đọc | Phạm vi dùng |
|---|---|---|
| Stratified undersampling, renormalization, τ-isotonic, exact restoration | Nyberg & Klami 2023, mục 3.1–3.3 | Công thức và giới hạn compatibility |
| S/T/X learner | Künzel et al. 2019 | Cấu trúc meta-learner |
| DR policy value | Dudík et al. 2011 | Outcome + propensity correction |
| Statistical policy learning | Athey & Wager 2021 | Policy value/uncertainty framing |
| CausalForestDML API | EconML 0.16 docs | cross-validation, honest forest, inference/resource profile |
| Dataset provenance | Criteo AI Lab | Randomized incrementality source |

Nguồn trực tiếp:

- Nyberg & Klami,
  [Data Mining and Knowledge Discovery 2023](https://link.springer.com/article/10.1007/s10618-023-00917-9).
- Künzel et al.,
  [PNAS 2019](https://doi.org/10.1073/pnas.1804597116).
- Dudík et al.,
  [ICML 2011](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/).
- Athey & Wager,
  [Econometrica 2021](https://doi.org/10.3982/ECTA15732).
- [EconML CausalForestDML 0.16](https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html).
- [Criteo dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/).

Không có claim nào rằng Nyberg đã empirical-validate exact correction bên trong
X-Learner. Ablation ở mẫu 10% không vượt baseline; release chuyển exact restoration sang
T-Learner/double-classifier đúng phạm vi Eq. 12.

## 4. Kết quả model

| Model | Qini | AUUC | EUCE |
|---|---:|---:|---:|
| X-Renormalized | 0,191557 | 0,006189 | 0,000462 |
| X-Calibrated | 0,188528 | 0,006084 | 0,000240 |
| Response | 0,182789 | 0,005912 | không áp dụng |
| T-LocalExact | 0,117668 | 0,003798 | 0,000957 |

Paired Qini:

| A - B | Δ | 95% CI | Kết luận |
|---|---:|---:|---|
| X-Renormalized - Response | 0,008768 | [-0,018626; 0,038772] | chưa phân biệt |
| X-Calibrated - X-Renormalized | -0,003029 | [-0,010774; 0,004700] | chưa phân biệt |
| T-LocalExact - X-Renormalized | -0,073889 | [-0,107381; -0,035891] | CI nằm hoàn toàn dưới 0 |

Calibration cải thiện scale EUCE nhưng không chứng minh ranking tốt hơn. Kết quả cho thấy
phương pháp “exact” không tự động cải thiện ranking so với phép xấp xỉ đang dùng cho rare
outcome.

### 4.1 Nhận xét — calibration và ranking là hai trục độc lập

Bảng trên chứa một kết quả dễ bị đọc sai, nên cần tách bạch rõ.

**X-Calibrated cải thiện calibration gần gấp đôi** — EUCE giảm từ `0,000462` xuống
`0,000240` — **nhưng ranking lại kém đi một chút**: Qini `0,188528` so với `0,191557`, và
CI của chênh lệch `[-0,010774; 0,004700]` chứa 0 — đưa điểm số về đúng thang CATE không
làm thứ tự ưu tiên tốt hơn.

Điều này đúng về mặt toán học chứ không phải nghịch lý: τ-isotonic là một phép biến đổi
**đơn điệu tăng**, mà Qini chỉ phụ thuộc thứ hạng. Phần chênh lệch quan sát được đến từ
cách xử lý tie sau khi isotonic gộp các đoạn hằng, không từ một sự sắp xếp lại có ý nghĩa.

Hệ quả cho sản phẩm: **chọn calibration theo nhu cầu diễn giải, không theo kỳ vọng nó cải
thiện targeting.** Nếu chỉ cần biết "target ai" thì calibration không cần thiết; nếu cần
trả lời "hiệu ứng ước tính bao nhiêu" cho bên kinh doanh thì cần, và cái giá phải trả là
gần như bằng 0 về ranking.

**T-LocalExact là kết quả âm rõ ràng nhất của Sprint 2** và đáng ghi lại: Qini `0,117668`,
thấp hơn X-Renormalized `0,073889` với CI `[-0,107381; -0,035891]` nằm hoàn toàn dưới 0.
Đây là candidate duy nhất trong sprint bị tách biệt rõ ràng. Bài học không phải "exact
restoration sai" mà là phạm vi áp dụng của nó hẹp: công thức đúng trong phạm vi Eq. 12 của
Nyberg & Klami cho double-classifier, và việc ghép nó vào một kiến trúc khác không được
paper bảo chứng. Dự án ghi rõ điều này ở mục 3 thay vì trình bày kết quả âm như một thất
bại của nguồn.

## 5. Kết quả policy

Main scenario: budget 10%, value/conversion = 1, cost/contact = 0,0005.

| Policy | DR net/customer | 95% CI | Δ vs random 95% CI |
|---|---:|---:|---:|
| Response top-k | 0,000799 | [0,000608; 0,000977] | [0,000582; 0,000928] |
| X-Renormalized top-k | 0,000825 | [0,000649; 0,001001] | [0,000611; 0,000951] |
| X-Calibrated top-k | 0,000826 | [0,000652; 0,001004] | [0,000611; 0,000953] |
| T-LocalExact top-k | 0,000671 | [0,000501; 0,000829] | [0,000464; 0,000777] |
| Random top-k | 0,000040 | [-0,000017; 0,000096] | — |

Policy point estimates không được dùng để đổi champion sau confirmation. Product dùng
Response vì selection contract đã khóa.

Với một triệu khách hàng, Response top 10% tương ứng khoảng `848,9` incremental
conversions gross, 95% CI `[657,8; 1.027,0]`. Đây là phép scale với assumption population
tương tự confirmation, không phải forecast đã deploy.

### 5.1 Vì sao giữ Response khi hai model khác có point estimate cao hơn

Đây là quyết định gây tranh cãi nhất của Sprint 2, nên lý do phải được ghi đầy đủ.

Trên confirmation, X-Renormalized (`0,000825`) và X-Calibrated (`0,000826`) đều cao hơn
Response (`0,000799`). Nếu chỉ nhìn bảng này, đổi champion là lựa chọn hiển nhiên. Dự án
không đổi, vì ba lý do xếp theo mức ràng buộc:

1. **Selection contract đã khóa trước.** Champion được chọn trên validation, và
   confirmation tồn tại để *kiểm định* lựa chọn đó chứ không phải để chọn lại. Đổi champion
   sau khi nhìn confirmation biến confirmation thành một validation split thứ hai, và khi
   đó dự án không còn tập nào chưa quan sát để kiểm định.
2. **Chênh lệch không vượt được nhiễu.** X-Renormalized - Response trên Qini là `0,008768`
   với CI `[-0,018626; 0,038772]` — rộng gấp hơn bốn lần chênh lệch và chứa 0. Point
   estimate cao hơn ở đây không phải bằng chứng model tốt hơn.
3. **Chi phí của một quyết định sai không đối xứng.** Giữ baseline khi challenger thực sự
   tốt hơn làm mất một phần cải thiện nhỏ và đo được. Đổi sang challenger dựa trên nhiễu
   làm hỏng chính cơ chế mà mọi kết luận sau này dựa vào.

Điểm đáng chú ý là quyết định này **được xác nhận về sau bằng dữ liệu độc lập**. Ở Sprint 3
với metric chính mới và cross-fitting OOF trên `5.591.836` dòng, X-Renormalized xếp dưới
Response ở cả hai fold seed, và chênh lệch trên confirmation là `-0,0000226`. Nếu Sprint 2
đã đổi champion theo point estimate, dự án đã phải đảo ngược quyết định đó một sprint sau.

Đây là bằng chứng cụ thể cho giá trị của việc khóa selection contract, và là lý do quy tắc
"mọi claim A hơn B phải kèm paired CI" được nâng thành quy tắc bắt buộc của
[`README.md`](README.md) từ đây trở đi.

## 6. Sản phẩm

- `output/product/dashboard.html`: app demo self-contained.
- `output/product/dashboard_data.json`: schema release.
- `output/product/screenshots/dashboard_screenshot.png`: bằng chứng visual.
- `scripts/smoke_dashboard_browser.mjs`: replay bốn scenario.
- `docs/DECISION_CONTRACT.md`: rule, formula và guardrails.
- data/model cards trong `docs/data_cards/` và `docs/model_cards/`.

Dashboard chỉ dùng artifact freeze, không train/download implicit.

## 7. Hạ tầng

Full local Sprint 2:

- model/policy pipeline runtime `395,9` giây; nâng Qini inference từ 300 lên 500
  resamples bằng frozen predictions cần thêm `302,6` giây;
- 6 physical / 12 logical CPUs;
- total RAM 15,19 GB;
- peak process RSS 2,74 GB;
- minimum system available RAM 1,81 GB.

Causal Forest local smoke 0,1% pass. Kaggle run vẫn cần external session/dataset
attachment; runbook đầy đủ ở [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 8 và kết
quả ba mốc ở [`CAUSAL_FOREST_REPORT.md`](CAUSAL_FOREST_REPORT.md). `inference=False` của safe
profile có nghĩa không yêu cầu `effect_interval()`.

## 8. Bằng chứng chất lượng

- formula inversion tests cho undersampling;
- synthetic truth tests cho IPW/DR;
- split disjoint/exhaustive test;
- clone/finite tests cho exact outcome adapters;
- multi-model paired bootstrap pairing test;
- dashboard 11/11 headless-browser acceptance;
- full pytest `49/49` pass ở release audit cuối.

## 9. Tái lập

Lệnh đầy đủ: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 3.

## 10. Hạng mục chưa hoàn thành và phạm vi không được suy rộng

- Causal Forest Kaggle 20/30/50 chưa chạy. *(Cập nhật 06/08/2026: đã chạy xong sau khi
  báo cáo này chốt. Kết quả và giới hạn diễn giải ở `report/CAUSAL_FOREST_REPORT.md`;
  kết luận của Sprint 2 giữ nguyên vì nó phản ánh bằng chứng có tại thời điểm chốt.)*
- Chưa có production A/B test của learned policy.
- Chưa có actual monetary outcome hoặc long-term CLV.
- Report này được tạo trước commit đầu tiên; trạng thái repository hiện tại đọc từ lịch sử git
  và từ [`../output/README.md`](../output/README.md).
- Random comparator là một ranking cố định bằng seed 42; CI hiện tại chưa tích hợp biến
  thiên qua nhiều random-policy seed.
- Demo video/GIF thuộc Sprint 3 packaging.
