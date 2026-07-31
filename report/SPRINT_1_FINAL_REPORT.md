# Báo cáo Sprint 1 — Nền tảng dữ liệu, mô hình uplift và khung đánh giá

**Trạng thái:** Hoàn thành bản release ngày 29/07/2026
**Bài toán:** Nhắm mục tiêu khuyến mãi bằng hiệu ứng tăng thêm do can thiệp (*Causal Uplift Targeting*)
**Kết quả chính thức:** `output/sprint1/` và `output/optimization/*sprint1_release*`

> Đây là nguồn kết quả chính thức của Sprint 1. Các báo cáo cũ trong `report/week-01/`,
> notebook hoặc dashboard có thể chứa kết quả thăm dò trước khi chạy lại và không được
> dùng để báo cáo mentor/CV.

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

Lệnh tái lập:

```powershell
.venv\Scripts\python.exe scripts\audit_criteo.py --balance-frac 0.05 --seed 42
```

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

Response đứng đầu về ranking không chứng minh nó ước lượng đúng CATE cá nhân. Model
release cho sản phẩm cần được chọn đồng thời theo ranking, calibration, độ ổn định và
giá trị policy.

Artifacts:

- `output/optimization/final_test_results_sprint1_release_5models.csv`
- `output/optimization/qini_comparison_sprint1.csv`
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

**Kết luận:** 50% **chưa được duyệt**. Research-profile envelope 24 GB cần ít nhất
32 GB system RAM để giữ peak dưới 75%; giả định 30 GB không qua gate. Kaggle Free chỉ
được thử theo resource gate và preflight, không bắt đầu trực tiếp ở 50%.

1. Đọc RAM/CPU live của session.
2. Chạy profile `kaggle-safe` ở 20%; chỉ tiếp tục nếu peak RAM <75% RAM khả dụng.
3. Chạy 30%; lặp lại điều kiện.
4. Mới chạy 50% với `inference=False`, 200 cây, CV=2, `max_samples=0.25`.
5. Nếu không đạt, dừng ở 20–30% và báo cáo learning curve; không mua Colab Pro chỉ để
   ép chạy một model chưa chứng minh mang lại thêm giá trị.

Chi tiết: `docs/KAGGLE_CAUSAL_FOREST.md` và
`output/sprint1/causal_forest_feasibility.json`.

## 9. Definition of Done

- [x] Kiểm toán schema, checksum, missing/finite, prevalence và treatment balance.
- [x] Chốt estimand và loại post-treatment leakage.
- [x] Protocol train/validation/test và multi-seed validation.
- [x] Năm model local chạy lại trên cùng test.
- [x] Ablation cải tiến so với baseline bằng paired bootstrap.
- [x] Qini, AUUC, calibration và policy table.
- [x] Benchmark tài nguyên Causal Forest và Kaggle runbook.
- [x] Unit tests cho schema, balance, metric và bootstrap.
- [x] Tài liệu lý thuyết tiếng Việt và câu lệnh tái lập.
- [ ] Causal Forest final trên Kaggle: thuộc Sprint 2, chỉ chạy sau preflight.
- [ ] Dashboard release đọc artifact mới: thuộc Sprint 2.

## 10. Bước tiếp theo của Sprint 2

1. Chạy Causal Forest learning curve 20% → 30% → tối đa 50% trên Kaggle.
2. Triển khai calibration chính xác sau under-sampling theo Nyberg & Klami (2023);
   candidate hiện tại mới dùng rescale `1/k` xấp xỉ.
3. Chỉ thử R-Learner sau khi xác định trước giả thuyết và tiêu chí đánh giá; không thêm model
   khi chưa có vai trò trong comparison protocol.
4. Không tune lại vào test Sprint 1; tạo validation/holdout mới nếu mở vòng model mới.
5. Thêm policy theo budget và cost-sensitive value, sensitivity analysis cho margin/cost.
6. Chuyển dashboard sang đọc duy nhất artifact `sprint1_release`.
7. Thêm data/model card, pipeline một lệnh và smoke test dashboard.
8. Chỉ sau đó mở hướng **Giá trị vòng đời khách hàng tăng thêm
   (Incremental Customer Lifetime Value)**.

## 11. Nguồn gốc phải đọc

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
