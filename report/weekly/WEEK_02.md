# Tuần 2 — Đóng băng pipeline causal và chốt bảng so sánh Sprint 1

**Sprint:** 1
**Trọng tâm theo kế hoạch:** Freeze data/run, Causal Forest preflight, sửa claim, bảng so sánh 5/6 model
**Deliverable đã chốt:** Manifest + evidence audit + comparison table
**Trạng thái:** Đạt, trừ Causal Forest — đóng bằng resource gate đúng như kế hoạch dự phòng

---

## 1. Kế hoạch tuần

Biến kết quả 5 model thành một causal release **có thể audit**: chạy lại từ đầu với giao
thức chọn model rõ ràng, ghi manifest đầy đủ, sửa mọi claim chưa có bằng chứng, và quyết
định có đưa Causal Forest vào release hay không **mà không làm chậm sản phẩm**.

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Audit dữ liệu | `output/sprint1/data_manifest.json`, `balance_smd.csv`, `arm_outcome_summary.csv` |
| Tuning có giới hạn | `scripts/tune_five_models.py`, validation seed 43/44/45 |
| Final test một lần | `scripts/evaluate_selected_five_models.py` |
| Paired bootstrap | `scripts/compare_release_models.py` |
| Policy decile | `scripts/build_sprint1_artifacts.py` |
| Causal Forest feasibility | `scripts/assess_causal_forest_feasibility.py`, benchmark 1/5/10/20% |
| Sửa claim | Báo cáo Sprint 1 thay các claim cũ |

## 3. Cách hoạt động

### 3.1 Giao thức chia dữ liệu — đóng băng trước khi chạy

```
Criteo 13.979.592
  └── stratified_sample(frac=0.50, seed=42)   ≈ 6.989.796
        ├── train  70%  = 4.892.856
        │     ├── fit         80% của train  = 56% pool
        │     └── validation  20% của train  = 14% pool
        └── FINAL TEST  30%  = 2.096.940      ← đóng vĩnh viễn
```

Ba quy tắc được đóng băng trước khi chạy:

1. **Tuning chỉ chạm validation.** Final test được chấm đúng một lần cho cấu hình đã chọn.
2. **Cùng một final test cho mọi model.** Không model nào có test riêng.
3. **Không đổi `frac`, `seed`, `test_size` sau khi đã xem kết quả.**

Quy tắc 3 là quy tắc dễ vi phạm nhất và khó phát hiện nhất: đổi seed rồi chọn kết quả đẹp
hơn là một dạng p-hacking không để lại dấu vết trong code.

### 3.2 Chọn cấu hình bằng nhiều seed validation

`tune_five_models.py` chấm mỗi candidate trên validation với **ba seed** 43/44/45 rồi lấy
trung bình. Lý do: với conversion 0,29%, một seed validation duy nhất có variance đủ lớn
để đảo thứ hạng giữa hai cấu hình gần nhau. Trung bình ba seed giảm rủi ro chọn nhầm vì
may mắn.

Search space bị giới hạn trước: mỗi model tối đa vài cấu hình, chỉ thay `num_leaves`,
`min_child_samples`, learning rate/trees, L1/L2 và subsampling. Không grid search mù.

### 3.3 Undersampling rare outcome — công thức và cái bẫy

X-Learner thắng nhờ cấu hình `under7_probability_fixed`. Cơ chế:

```
s_t = (1/k − p_t) / (1 − p_t)     với p_t = conversion rate của arm t
```

Giữ **toàn bộ** positive, giữ negative của **mỗi arm** với xác suất riêng `s_t`.

Cái bẫy: dùng **chung một tỷ lệ** negative cho hai arm. Vì hai arm có `p_t` khác nhau
(control 0,194%, treated 0,309%), dùng chung tỷ lệ sẽ làm conversion rate hai arm tăng
**không đồng đều**, tức làm đổi uplift. Đây là lỗi im lặng: model vẫn chạy, số vẫn ra,
nhưng estimand đã khác.

Sau undersampling với hệ số `k`, uplift trong dữ liệu sampled xấp xỉ `k` lần uplift gốc,
nên score được chia cho `k`. Nyberg et al. dùng **xấp xỉ** `tau_sampled ≈ k · tau_goc`,
không phải đẳng thức — điều này được ghi rõ trong docstring. Qini chỉ phụ thuộc thứ hạng
nên phép chia không đổi ranking; nó chỉ ảnh hưởng scale.

### 3.4 Propensity cố định cho RCT

X-Learner và DR-Learner dùng `DummyClassifier(strategy="prior")` thay vì một classifier
học `e(X)` từ feature.

Lý do: đây là RCT, propensity là **hằng số thiết kế** ≈ 0,85. Fit một model linh hoạt cho
`e(X)` chỉ học được nhiễu, và nhiễu đó đi thẳng vào mẫu số của pseudo-outcome, làm tăng
variance mà không giảm bias.

### 3.5 Paired bootstrap — sửa lỗi phương pháp của tuần 1

Tuần 1 dùng `paired_bootstrap_compare()` trả một heuristic tail. Tuần 2 thay bằng
`paired_bootstrap_difference_ci` và `paired_qini_bootstrap_matrix`.

Cơ chế: mỗi vòng bootstrap dùng **cùng một bộ index** cho mọi model, và đường "perfect"
được tính **một lần** cho mỗi resample rồi dùng chung làm mẫu số.

Vì sao pairing quan trọng: hai model được chấm trên cùng holdout nên phần lớn nhiễu là
**nhiễu chung** (mẫu này tình cờ có nhiều/ít conversion). Resample cùng index làm nhiễu
chung triệt tiêu trong hiệu, và CI của chênh lệch hẹp hơn nhiều so với khi so hai CI riêng.

`paired_bootstrap_compare()` cũ được giữ lại nhưng docstring ghi rõ **không dùng làm
p-value headline**.

### 3.6 Causal Forest — quyết định bằng số đo, không bằng mong muốn

`assess_causal_forest_feasibility.py` chạy benchmark tăng dần và đo peak RSS thật:

| Fraction | Wall time | Peak RSS |
|---:|---:|---:|
| 1% | 126 giây | 2,10 GB |
| 5% | 528 giây | 3,11 GB |
| 10% | 1.052 giây | 4,80 GB |
| 20% | 2.200 giây | 8,16 GB |

Ngoại suy tuyến tính cho 50%: 17,5 GB; envelope bảo thủ 24 GB. Máy local có 15,19 GB.

Kết luận: **không chạy 50% local**. Đây là ngoại suy chứ không phải runtime đã đo, và điều
đó được ghi rõ. Causal Forest chuyển sang gate Kaggle với profile `kaggle-safe`.

## 4. Kết quả

Final test 2.096.940 dòng, 500 bootstrap:

| Model | Cấu hình | Qini | CI 95% |
|---|---|---:|---:|
| Response | baseline | 0,187886 | [0,153453; 0,226227] |
| S-Learner | baseline | 0,177204 | [0,141847; 0,218151] |
| X-Learner | under7, classifier, fixed propensity | 0,167168 | [0,131828; 0,205766] |
| DR-Learner | baseline | 0,153967 | [0,117901; 0,190431] |
| T-Learner | baseline | 0,142021 | [0,106793; 0,175477] |

Paired so với Response:

| So sánh | Δ Qini | CI 95% | Kết luận |
|---|---:|---:|---|
| Response − S | 0,010682 | [-0,014606; 0,033674] | CI chứa 0 |
| Response − X | 0,020718 | [-0,003807; 0,045626] | CI chứa 0 |
| Response − DR | — | — | CI không chứa 0 |
| Response − T | 0,045865 | [0,014414; 0,077777] | CI không chứa 0 |

**Chỉ X-Learner vượt baseline của chính nó** trong final ablation: `Δ = 0,025791`,
CI `[0,000058; 0,053916]` so với X-Learner mặc định.

Tỷ lệ score âm theo model: Response 0% · S 0,38% · T 53,96% · X 24,15% · DR 0,65%. Con số
này **không** được gọi là tỷ lệ "Sleeping Dog"; nó là đặc tính dự đoán model-dependent.

Top 10% theo Response giữ **72,7%** ước lượng incremental conversion trên holdout.

## 5. Quyết định và lý do

1. **Release năm model, Causal Forest ghi trạng thái pending.** Gate tài nguyên không qua,
   và kế hoạch đã dự phòng đúng tình huống này. Không nâng hạ tầng chỉ để đủ "6 model".
2. **Bỏ claim "top 10% giữ 85% uplift"** của tài liệu cũ. Số đúng theo release là 72,7%.
3. **Bỏ p-value khỏi mọi headline.** Chỉ báo CI của chênh lệch.
4. **Không gọi ba nhóm CATE là principal strata.** Gọi là operational segments.

## 6. Chưa xong và rủi ro

- Causal Forest chưa có kết quả thật ở bất kỳ quy mô nào ngoài benchmark.
- Response đứng đầu nhưng CI so với S và X đều chứa 0 → chưa tách được ba model đầu bảng.
- Chưa có policy value: Qini là metric ranking, chưa trả lời "target bao nhiêu phần trăm".

## 7. Chuẩn bị cho tuần sau

Tuần 3 cần một **tập dữ liệu mới hoàn toàn** để Sprint 2 không tái dùng final test Sprint
1, và cần chuyển từ metric ranking sang policy value có ngân sách.

## 8. Câu hỏi cần mentor phản biện

Có chấp nhận release 5 model nếu Causal Forest không qua feasibility gate không?

*Đã được chấp nhận; đây là lý do Sprint 2 không bị chặn.*
