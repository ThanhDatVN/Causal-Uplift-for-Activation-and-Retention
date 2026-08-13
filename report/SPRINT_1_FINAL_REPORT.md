# Báo cáo Sprint 1 — Nền tảng dữ liệu, mô hình uplift và khung đánh giá

**Trạng thái:** Hoàn thành bản release ngày 29/07/2026
**Bài toán:** Nhắm mục tiêu khuyến mãi bằng hiệu ứng tăng thêm do can thiệp (*Causal Uplift Targeting*)
**Kết quả chính thức:** `output/sprint1/` và `output/optimization/*sprint1_release*`

> Đây là nguồn kết quả chính thức của Sprint 1. Điểm số đời đầu còn lại trong
> `output/legacy/` là kết quả thăm dò trước khi chạy lại và **không** được dùng làm kết quả
> chính thức — xem [`../output/README.md`](../output/README.md) mục "Artifact đời đầu" để
> biết chỗ dễ trích nhầm nhất.

## 1. Sprint 1 giải quyết điều gì?

Mục tiêu không phải dự đoán ai sẽ mua, mà là xếp hạng khách hàng theo:

\[
\tau(x)=E[Y(1)-Y(0)\mid X=x]
\]

Trong đó `Y(1)` và `Y(0)` là kết quả tiềm năng nếu cùng một khách hàng lần lượt được
và không được nhận quảng cáo. Ta không quan sát đồng thời hai kết quả này, vì vậy không
đánh giá bằng accuracy/RMSE của CATE cá nhân. Sprint dùng dữ liệu thử nghiệm ngẫu nhiên
Criteo, Qini/AUUC trên holdout và ước lượng policy theo nhóm để đánh giá khả năng xếp hạng.

**Estimand đã chốt:** hiệu ứng tăng thêm của treatment lên `conversion` trong quần thể
Criteo v2.1. `visit` và `exposure` là biến sau treatment nên không được dùng làm feature.

## 2. Kiểm toán dữ liệu

| Hạng mục | Kết quả |
|---|---:|
| Kích thước | 13.979.592 dòng × 16 cột |
| SHA-256 | `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc` |
| Thiếu dữ liệu / feature không hữu hạn | 0 / 0 |
| Tỷ lệ treatment | 85,0000% |
| Tỷ lệ conversion | 0,2917% |
| Conversion treated / control | 0,3089% / 0,1938% |
| ATE thô | 0,11519 điểm phần trăm |
| 95% CI của ATE thô | [0,10845%; 0,12192%] |
| Holdout propensity AUC, audit 5% | 0,5074 |
| Median / max \|SMD\| | 0,0177 / 0,0490 |

Schema, kiểu dữ liệu, nhãn nhị phân, feature hữu hạn và checksum đều được kiểm tra.
Balance tốt là bằng chứng chẩn đoán phù hợp với randomization, nhưng **không tự chứng
minh** randomization; nguồn xác nhận thiết kế thử nghiệm là tài liệu chính thức của Criteo.

### 2.1 Nhận xét — hiệu ứng có thật, nhưng nhỏ tuyệt đối

Ba con số ở trên định hình toàn bộ phần còn lại của dự án, nên cần đọc kỹ hơn một bảng
kiểm toán thông thường.

**Hiệu ứng trung bình là có thật và được đo rất chính xác.** ATE `0,11519` điểm phần trăm
với CI `[0,10845%; 0,12192%]` không chứa 0, `z = 33,5`. Trên thang tương đối, risk ratio là
`1,594` với CI `[1,544; 1,647]` — treatment làm tăng conversion khoảng **59%** so với
control. Đây không phải hiệu ứng yếu về mặt thống kê.

**Nhưng nó nhỏ về giá trị tuyệt đối**, và đó mới là đại lượng mà policy targeting làm việc
cùng: `0,3089%` so với `0,1938%`. Chênh lệch tuyệt đối `0,00115` chính là ngân sách tín
hiệu mà mọi CATE learner phải chia nhỏ tiếp theo `x`.

**Đây là căng thẳng trung tâm của dự án.** Ước lượng *trung bình* thì thừa power; ước
lượng *heterogeneity* thì không. Phân tích công suất ở `output/eda/power_analysis.csv` cho
thấy ranh giới: phát hiện được hiệu ứng bằng `1/10` ATE cần `8,97e06` dòng — vừa đủ trong
`13,98` triệu dòng của Criteo; nhưng `1/100` ATE cần `8,97e08`, tức **64 lần** toàn bộ
dataset.

Nói cách khác, ngay từ bước kiểm toán dữ liệu đã đọc được rằng dự án có thể trả lời chắc
chắn câu "treatment có tác dụng không", còn câu "tác dụng với ai nhiều hơn" chỉ trả lời
được ở mức phân giải thô. Kết quả của Sprint 3 và bốn vòng cải tiến sau đó là hệ quả của
ràng buộc này, không phải của việc chọn sai model.

Artifacts:

- `output/sprint1/data_manifest.json`
- `output/sprint1/arm_outcome_summary.csv`
- `output/sprint1/balance_smd.csv`

## 3. Protocol chống “tune vào test”

1. Lấy stratified sample 50% của full data. Trong sample này, seed 42 tách final
   train/test 70/30; phần train tiếp tục tách fit/validation 80/20 cho tuning. Vì vậy
   tỷ lệ fit/validation/test là 56/14/30 **trong sample 50%**, tương đương khoảng
   28/7/15% full data. Tất cả đều stratify theo treatment–outcome.
2. Candidate chỉ được so trên validation.
3. Độ bền validation được kiểm tra trên ba seed 43, 44, 45.
4. Chỉ chọn cải tiến nếu median ΔQini ≥ 0,005 và thắng baseline ít nhất 2/3 seed.
5. Final test 30% của sample (2.096.940 dòng) chỉ được mở sau khi khóa cấu hình.
6. Nếu cải tiến không vượt baseline trên paired-bootstrap test, release quay về baseline.

Protocol này giảm rủi ro một cấu hình thắng do nhiễu của một validation split. Nó không
biến test thành bằng chứng ngoài mẫu độc lập nếu tiếp tục dùng test cho nhiều vòng sau;
Sprint 2 phải giữ test này đóng hoặc tạo một holdout mới.

## 4. Nền tảng phương pháp

Năm mô hình local:

- **Response model:** dự đoán conversion trực tiếp; là baseline xếp hạng, không phải
  CATE estimator.
- **S-Learner:** một mô hình outcome nhận thêm treatment làm feature.
- **T-Learner:** hai mô hình outcome riêng cho treatment và control.
- **X-Learner:** impute treatment effect theo hai arm rồi kết hợp; hữu ích để thử khi
  kích thước hai arm mất cân bằng.
- **DR-Learner:** dùng pseudo-outcome doubly robust với propensity của RCT.

Conversion rate khoảng 0,29%. Under-sampling giữ toàn bộ positive và lấy mẫu negative riêng
trong từng arm theo Nyberg và cộng sự:

\[
r_t=\frac{1/k-\bar p(Y=1\mid T=t)}{1-\bar p(Y=1\mid T=t)}
\]

Với rare outcome, xác suất sau sampling xấp xỉ tăng `k` lần và treatment effect xấp xỉ
được scale `k` lần. Đây là **xấp xỉ**, không phải đẳng thức; vì vậy project thử cả hiệu
chỉnh xác suất và chỉ nhận cấu hình nếu validation/test ủng hộ.

## 5. Thử nghiệm cải tiến và ablation

Tuning chạy trên 50% toàn bộ dữ liệu, ba validation seed. Cấu hình thắng validation:
Response regularized, S regularized, T baseline, X under-sampling `k=7` dùng outcome
classifier, fixed propensity và rescale `1/k` theo xấp xỉ rare-outcome,
DR baseline.

Khi mở test, kết quả ablation:

| Model | Cấu hình thử | Test Qini | Δ so baseline | 95% CI của Δ | Quyết định |
|---|---|---:|---:|---:|---|
| Response | regularized | 0,1844 | -0,0035 | [-0,0276; 0,0174] | Quay về baseline |
| S | regularized | 0,1756 | -0,0016 | [-0,0137; 0,0106] | Quay về baseline |
| T | baseline | 0,1420 | — | — | Giữ baseline |
| X | under7 + classifier + fixed propensity + rescale `1/k` | 0,1672 | +0,0258 | [0,0001; 0,0539] | Giữ cải tiến |
| DR | baseline | 0,1540 | — | — | Giữ baseline |

Kết quả trên test cho thấy chỉ X-Learner duy trì chênh lệch so với baseline. Hai
regularization candidate đạt điều kiện trên validation nhưng không duy trì chênh lệch trên test.

**Nhận xét.** Hai candidate regularized đã qua một gate không dễ: median ΔQini ≥ `0,005` và
thắng baseline ít nhất 2/3 seed validation. Trên test chúng cho `−0,0035` và `−0,0016`, tức
**đổi dấu**. Đây không phải lỗi hiện thực mà là hành vi kỳ vọng khi chọn ra cực đại của
nhiều candidate trên một mẫu hữu hạn: phần thắng trên validation gồm cả tín hiệu lẫn nhiễu,
và chỉ phần tín hiệu đi tiếp sang test.

Ba điều rút ra, cả ba đều định hình các sprint sau:

1. **Multi-seed validation vẫn chưa đủ.** Ba seed 43/44/45 cùng chia trên một pool nên
   không độc lập; chúng lọc được nhiễu của một lần chia, không lọc được nhiễu chung của
   pool. Sprint 3 vì thế chuyển sang cross-fitting OOF trên toàn bộ development pool và
   dùng **hai fold seed** làm điều kiện bắt buộc thay vì lấy trung bình.
2. **Gate bằng ngưỡng độ lớn cần đi kèm khoảng tin cậy.** `median ΔQini ≥ 0,005` là một
   ngưỡng point estimate; ngay cả X-Learner — candidate duy nhất giữ được chênh lệch — có
   CI `[0,0001; 0,0539]` gần chạm 0. Từ Sprint 2 trở đi mọi claim "A hơn B" đều bắt buộc
   kèm paired CI.
3. **Quyết định quay về baseline phải được định trước.** Quy tắc 6 của protocol mục 3 đã
   viết sẵn điều này trước khi mở test, nên khi hai candidate trượt thì không có tranh luận
   hậu nghiệm nào về việc có nên giữ chúng hay không.

Chi phí của bài học này là hai candidate bị loại. Giá trị của nó là toàn bộ khung
promotion rule đăng ký trước dùng ở Sprint 3 và bốn vòng cải tiến sau.

## 6. Bảng 5 mô hình release

Mỗi model được chấm trên cùng 2.096.940 dòng test; CI dùng 500 bootstrap resamples.

| Hạng | Model | Qini | 95% CI | AUUC | EUCE |
|---:|---|---:|---:|---:|---:|
| 1 | Response baseline | 0,1879 | [0,1535; 0,2262] | 0,006084 | — |
| 2 | S-Learner baseline | 0,1772 | [0,1418; 0,2182] | 0,005740 | 0,000174 |
| 3 | X-Learner cải tiến | 0,1672 | [0,1318; 0,2058] | 0,005405 | 0,000381 |
| 4 | DR-Learner baseline | 0,1540 | [0,1179; 0,1904] | 0,004974 | 0,000530 |
| 5 | T-Learner baseline | 0,1420 | [0,1068; 0,1755] | 0,004591 | 0,000773 |

Không được kết luận thứ hạng chỉ từ CI riêng lẻ. Paired bootstrap cho thấy:

- Response cao hơn T: ΔQini 0,0459; 95% CI [0,0144; 0,0778].
- Response cao hơn DR: ΔQini 0,0339; 95% CI [0,0040; 0,0626].
- Response so với S và X: CI của chênh lệch chứa 0, chưa đủ bằng chứng phân biệt.
- S, T, X, DR còn lại cũng có nhiều cặp chưa tách biệt rõ.

### 6.1 Nhận xét — các model xếp hạng khác nhau nhưng đo ra gần bằng nhau

Bảng Qini ở trên nói model nào tốt hơn. Nó không nói các model có **đồng ý với nhau về ai
là khách hàng ưu tiên** hay không. Tương quan Spearman giữa các bộ điểm trên cùng holdout,
từ `output/sprint1/score_spearman_release.csv`:

| | Response | S | T | X | DR |
|---|---:|---:|---:|---:|---:|
| Response | 1,000 | 0,824 | 0,734 | 0,439 | 0,679 |
| S-Learner | 0,824 | 1,000 | 0,607 | 0,429 | 0,636 |
| T-Learner | 0,734 | 0,607 | 1,000 | 0,474 | 0,598 |
| X-Learner | 0,439 | 0,429 | 0,474 | 1,000 | 0,424 |
| DR-Learner | 0,679 | 0,636 | 0,598 | 0,424 | 1,000 |

Đọc bảng này cùng bảng Qini cho một quan sát đáng chú ý:

**X-Learner xếp hạng khách hàng rất khác Response** — Spearman chỉ `0,439`, thấp nhất
trong mọi cặp có Response — **nhưng chênh lệch Qini giữa hai model vẫn có CI chứa 0**
(`0,0207`, CI `[−0,0038; 0,0456]`). Hai thứ tự ưu tiên khác nhau đáng kể lại cho chất
lượng xếp hạng tổng hợp không phân biệt được.

Điều đó nói lên giới hạn của phép đo chứ không phải sự tương đương của hai model. Nếu
metric đủ phân giải, hai cách sắp xếp khác nhau tới mức đó phải cho kết quả khác nhau. Ở
đây chúng không, vì mặt mục tiêu quá phẳng so với nhiễu — cùng cơ chế mà Sprint 3 gặp lại
khi DR loss chỉ chênh nhau `7e-6` giữa hai candidate.

Ngược lại, S-Learner tương quan `0,824` với Response, tức gần như cùng một thứ tự, và cũng
không phân biệt được về Qini. Trường hợp này thì kết luận "không phân biệt được" là bình
thường và không đáng ngại.

Hệ quả thực hành: **"CI chứa 0" phải được đọc kèm mức tương quan thứ hạng.** Hai model
giống nhau mà hoà là một chuyện; hai model khác hẳn nhau mà vẫn hoà là dấu hiệu phép đo
đang hết độ phân giải. Đây là lý do các sprint sau bổ sung `policy_area_dr` và AUTOC thay
vì tiếp tục chỉ dựa vào Qini.

### 6.2 Causal Forest trên cùng holdout

Ngoài bốn meta-learner và baseline, một thuật toán chuyên dụng được chấm trên **đúng cùng
holdout** — `Y` và `T` đã kiểm chứng giống hệt từng phần tử. Sáu model vì thế đặt chung
một bảng:

| Model | `policy_area_dr` | Qini |
|---|---:|---:|
| **Causal Forest** | **0,001006** | 0,174678 |
| Response baseline | 0,001005 | **0,187886** |
| S-Learner baseline | 0,000999 | 0,177204 |
| X-Learner cải tiến | 0,000975 | 0,167168 |
| DR-Learner baseline | 0,000925 | 0,153967 |
| T-Learner baseline | 0,000897 | 0,142021 |

Causal Forest đứng đầu theo `policy_area_dr` và thứ ba theo Qini. Cả hai chênh lệch so
với Response đều có CI chứa 0 — `[−6,0e-05; 5,8e-05]` và `[−0,0370; 0,0107]` — nên đây
là **hoà**, không phải thắng. Champion không đổi.

Hai điều phải ghi kèm khi trích bảng này:

- **Cách chọn cấu hình khác nhau.** Bốn meta-learner đi qua ablation trên validation
  (mục 5); Causal Forest dùng cấu hình cố định `n_estimators=200`,
  `min_samples_leaf=500`, `max_samples=0,25`, `honest=True`, `inference=False`. Nó so
  được vì dùng chung holdout.
- **`policy_area_dr` được tính bổ sung** cho cả sáu model trên holdout này, dùng IPW
  signal với propensity hằng số. Cột Qini là metric gốc của Sprint 1.

Chi tiết, learning curve ba mốc và biểu đồ: `report/CAUSAL_FOREST_REPORT.md`.

Response đứng đầu về ranking không chứng minh nó ước lượng đúng CATE cá nhân. Model
release cho sản phẩm cần được chọn đồng thời theo ranking, calibration, độ ổn định và
giá trị policy.

Artifacts:

- `output/optimization/final_test_results_sprint1_release_5models.csv`
- `output/legacy/qini_comparison_sprint1.csv`
- `output/sprint1/model_pairwise_bootstrap_release.csv`
- `output/sprint1/model_qini_bootstrap_draws_release.csv`

## 7. Góc nhìn policy/kinh doanh

Nếu chuẩn hóa holdout thành 2.096.940 khách hàng và target top 10%:

| Model | Incremental conversions ước tính | 95% CI | Tỷ trọng uplift toàn tập |
|---|---:|---:|---:|
| Response | 1.754,7 | [1.412,4; 2.096,9] | 72,7% |
| S | 1.740,9 | [1.384,0; 2.097,9] | 72,2% |
| X | 1.623,6 | [1.258,7; 1.988,5] | 67,3% |
| DR | 1.596,4 | [1.261,9; 1.930,9] | 66,2% |
| T | 1.508,9 | [1.177,7; 1.840,2] | 62,6% |

Đây là estimate từ randomized holdout, không phải doanh thu hay profit thực. Muốn chuyển
thành profit cần cost per treatment, margin/conversion và guardrail vận hành.
CI ở bảng policy là Wald normal approximation cho chênh lệch hai tỷ lệ, có điều kiện
trên policy/model đã freeze; nó chưa cộng thêm uncertainty do model selection.

Tỷ lệ score âm khác nhau giữa model (Response 0%; S 0,38%; T 53,96%; X 24,15%;
DR 0,65%). Không được gọi trực tiếp các dòng score âm là “Sleeping Dogs”: đó là nhãn
model-dependent, còn principal stratum cá nhân không quan sát được.

Artifacts:

- `output/sprint1/policy_deciles_release.csv`
- `output/sprint1/policy_summary.json`
- `output/sprint1/score_diagnostics_release.csv`
- `output/sprint1/score_spearman_release.csv`

## 8. Causal Forest: có chạy Kaggle Free được không?

Benchmark profile research trên máy hiện tại:

| Fraction | Thời gian | Peak RAM |
|---:|---:|---:|
| 1% | 126 giây | 2,10 GB |
| 5% | 528 giây | 3,11 GB |
| 10% | 1.052 giây | 4,80 GB |
| 20% | 2.200 giây | 8,16 GB |

Ước lượng 50%: khoảng 17,5 GB theo fit tuyến tính, đặt ngân sách bảo thủ 24 GB. Runtime
phụ thuộc CPU; quy đổi bảo thủ cho 4 CPU khoảng 4,5 giờ. GPU P100 **không làm tăng tốc
trực tiếp** cho `econml.CausalForestDML`; nút thắt là CPU và system RAM.

**Kết luận:** 50% **chưa được duyệt** tại thời điểm chốt Sprint 1. Research-profile envelope
24 GB cần ít nhất 32 GB system RAM để giữ peak dưới 75%; giả định 30 GB không qua gate. Kaggle
Free chỉ được thử theo resource gate và preflight, không bắt đầu trực tiếp ở 50%. Quy trình
gate ba mốc rút ra từ kết luận này được ghi ở
[`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 8.

Kết quả ba mốc sau khi chạy: [`CAUSAL_FOREST_REPORT.md`](CAUSAL_FOREST_REPORT.md). Bằng chứng
số của benchmark: `output/sprint1/causal_forest_feasibility.json`.

## 9. Giới hạn và phạm vi suy luận

Những điều bảng kết quả ở trên **không** chứng minh:

- **Response không phải CATE estimator.** Nó xếp hạng theo `P(conversion)` và có 0% điểm
  âm, nên về nguyên tắc không biểu diễn được hiệu ứng âm. Nó đứng đầu theo Qini/AUUC, tức
  theo *khả năng xếp hạng*, không theo *độ chính xác của ước lượng hiệu ứng cá nhân*. Hai
  điều này khác nhau và không suy ra nhau.
- **Không quan sát được principal stratum.** Tỷ lệ điểm âm chênh nhau rất lớn giữa các
  model (Response 0%, T-Learner 53,96%) cho thấy đó là đại lượng phụ thuộc model, không
  phải một tầng có thật đếm được. Không được gọi các dòng điểm âm là "Sleeping Dogs".
- **Balance diagnostics không chứng minh randomization.** Propensity AUC `0,5074` và
  max `|SMD|` `0,0490` phù hợp với randomization nhưng không thay thế được provenance từ
  phía Criteo.
- **Test 30% chỉ ngoài mẫu đúng một lần.** Nó đã được mở ở Sprint 1. Mọi vòng sau phải giữ
  nó đóng hoặc tạo holdout mới; Sprint 2 tạo confirmation set riêng chính vì ràng buộc này.
- **Con số policy là conversion-equivalent, không phải tiền.** Criteo không có doanh thu,
  biên lợi nhuận hay chi phí liên hệ. Bảng mục 7 là phép quy đổi có điều kiện trên policy
  đã đóng băng và chưa cộng uncertainty do model selection.
- **Cấu hình Causal Forest không đi qua ablation.** Nó dùng một điểm cấu hình cố định
  (mục 6.2), nên so sánh với nó là so sánh với một cấu hình cụ thể, không phải với họ
  Causal Forest nói chung.

Một giới hạn về phạm vi dữ liệu cần nhắc riêng: kết luận chỉ áp dụng cho quần thể Criteo
v2.1 với outcome `conversion` ở tỷ lệ `0,29%`. Chưa có bằng chứng portability sang dataset
thứ hai; đó vẫn là hướng nghiên cứu ưu tiên số một ở
[`../planning/README.md`](../planning/README.md).

## 10. Nguồn gốc phải đọc

- Criteo AI Lab, dataset và thiết kế thử nghiệm:
  https://ailab.criteo.com/criteo-uplift-prediction-dataset/
- Künzel et al., S/T/X-Learner, PNAS 2019:
  https://doi.org/10.1073/pnas.1804597116
- Kennedy, DR-Learner:
  https://arxiv.org/abs/2004.14497
- Nyberg et al., rare outcome imbalance:
  https://proceedings.mlr.press/v157/nyberg21a.html
- Nyberg & Klami, undersampling/calibration mở rộng:
  https://doi.org/10.1007/s10618-023-00917-9
- Nie & Wager, R-Learner:
  https://doi.org/10.1093/biomet/asaa076
- Athey & Wager, policy learning:
  https://doi.org/10.3982/ECTA15732
- Wager & Athey, Causal Forest:
  https://doi.org/10.1080/01621459.2017.1319839
- Efron & Tibshirani, bootstrap:
  https://doi.org/10.1201/9780429246593
