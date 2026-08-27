# Giao thức đánh giá — metric chính, cross-fitting và promotion rule

- **Vòng sinh ra tài liệu:** Sprint 3 — vòng cải tiến đầu tiên có đăng ký trước
- **Protocol:** [`../../configs/sprint3_improvement_protocol.json`](../../configs/sprint3_improvement_protocol.json)
- **Hiện thực:** [`../../src/policy_evaluation.py`](../../src/policy_evaluation.py),
  [`../../src/ranking_metrics.py`](../../src/ranking_metrics.py),
  [`../../src/rank_learner.py`](../../src/rank_learner.py),
  [`../../src/ensemble.py`](../../src/ensemble.py)
- **Kết quả:** [`../../report/03_SPRINT_3_IMPROVEMENT.md`](../../report/03_SPRINT_3_IMPROVEMENT.md)
- **Đọc trước:** [`02_CALIBRATION_AND_POLICY_VALUE.md`](02_CALIBRATION_AND_POLICY_VALUE.md) —
  **đọc tiếp:** [`04_CAUSAL_FOREST.md`](04_CAUSAL_FOREST.md)

Đây là tài liệu định nghĩa **metric chính hiện hành** và **luật promote** mà mọi vòng sau
đều chạy dưới. Nó cũng ghi rõ ranh giới giữa phần lấy từ nguồn và phần tự hiện thực.

## 1. Vì sao đổi metric chính

Sprint 1–2 dùng Qini làm metric ranking chính. Hai lý do để không giữ nó ở vị trí
đó:

1. Qini là một đại lượng ranking đã chuẩn hóa; nó không nói policy tại một mức
   ngân sách cụ thể tạo ra bao nhiêu conversion tăng thêm. Quyết định sản phẩm lại
   luôn gắn với một ngân sách.
2. Nghiên cứu 2026 về độ ổn định metric (arXiv 2603.20775) báo Qini kém ổn định hơn
   Uplift/AUUC khi có selection bias hoặc unobserved confounding. Criteo là RCT nên
   hai bias đó không phải kịch bản chính, nhưng kết luận đủ để không dựa vào một
   metric duy nhất.

Metric chính đăng ký trước của Sprint 3 là `policy_area_dr`. Qini và AUUC vẫn được
tính và báo cáo đầy đủ để so sánh với hai sprint trước.

## 2. `policy_area_dr`

Với effect signal `Γ` thỏa `E[Γ | X] = τ(X)` và score ưu tiên `S`:

```text
G(b) = E[ 1{S(X) thuộc top-b} · Γ ]
policy_area_dr = ( ∫ G(b) db trên dải budget ) / độ rộng dải
```

Lưới budget đăng ký trước: `{0,01; 0,02; 0,05; 0,10; 0,15; 0,20; 0,25; 0,30}`, tích
phân bằng trapezoid.

Ba lựa chọn định nghĩa và lý do:

- **Lấy kỳ vọng trên toàn population, không trên riêng nhóm được target.** Nhờ đó
  giá trị ở các budget khác nhau cộng gộp và so sánh trực tiếp được, và policy
  "không target ai" có giá trị đúng bằng 0.
- **`Γ` là doubly robust signal**, không phải IPW thuần, để giảm variance khi
  outcome hiếm. Nuisance `mu0`/`mu1` được cross-fit và **dùng chung cho mọi
  candidate**, nên chênh lệch giữa hai model không lẫn với chênh lệch giữa hai tín
  hiệu đánh giá khác nhau.
- **Đơn vị là conversion tăng thêm trên mỗi khách hàng**, không phải tiền. Criteo
  không có monetary outcome nên metric chọn model không được gắn giá tiền giả định.

Nguồn khung giá trị/regret: Athey & Wager, Econometrica 2021; doubly robust policy
evaluation: Dudík, Langford & Li, ICML 2011.

Hiện thực: `src/policy_evaluation.py`. Kiểm chứng: `tests/test_policy_evaluation.py`
so đường cong nội suy với phép cắt top-k trực tiếp, và
`tests/test_release_consistency.py` so với đúng cột DR đã phát hành ở Sprint 2 (lệch
tối đa `2,6e-08`, đúng bậc `1/n` do nội suy ở biên ngân sách thay vì cắt cứng).

## 3. RATE và AUTOC

Theo Yadlowsky, Fleming, Shah, Brunskill & Wager, JASA 2025
(DOI 10.1080/01621459.2024.2393466):

```text
TOC(q) = mean(Γ trên top-q theo S) - mean(Γ)
RATE   = ∫₀¹ α(q) · TOC(q) dq
```

`α(q) = 1` cho AUTOC; `α(q) = q` cho biến thể trọng số kiểu Qini. Paper yêu cầu
score được fit trên dữ liệu tách biệt với dữ liệu chấm; module không tự bảo đảm
điều đó, caller phải truyền prediction out-of-fold.

Hai chi tiết hiện thực đáng ghi:

- **Tie phải được gộp thành một điểm cắt.** Một prioritization rule không phân biệt
  được các quan sát cùng score, nên không được hưởng lợi từ thứ tự ngẫu nhiên bên
  trong nhóm. Không gộp thì score hằng số cho RATE khác 0 — chính là lỗi mà
  `tests/test_ranking_metrics.py::test_constant_score_gives_zero_rate` bắt được
  trong lần chạy đầu.
- **AUTOC không phản đối xứng khi đảo ngược ranking.** Từ đồng nhất thức
  `TOC_rev(1-q) = -q·TOC(q)/(1-q)` suy ra `∫ q·TOC_rev = -∫ q·TOC`, tức chỉ biến
  thể `α(q)=q` mới đổi dấu chính xác. Điều này được khẳng định bằng test riêng.

## 4. Outcome adjustment giảm variance

Bokelmann & Lessmann, EJOR 2024 (bản arXiv 2210.02152) đề xuất điều chỉnh outcome
để giảm variance của metric đánh giá uplift trên RCT. Repo **chỉ đọc được
abstract/metadata** của nguồn này, không đọc được phần công thức đầy đủ. Vì vậy
hàm trong repo là dạng regression-adjusted quen thuộc, **được suy ra và kiểm chứng
tại chỗ**, không phải bản sao công thức của paper:

```text
R_adj = (Y - m(X)) · (T - p) / (p(1 - p))
```

Với propensity hằng `p` và bất kỳ `m(X)` nào không phụ thuộc `T` hay `Y`:

```text
E[R_adj | X] = (μ₁ - m) - (μ₀ - m) = τ(X)
```

nên adjustment không đổi estimand. Variance giảm khi `m(X)` xấp xỉ tốt `E[Y | X]`
gộp hai arm. `m` bắt buộc phải fit ngoài mẫu đang chấm; trong pipeline nó là
`p·mu1 + (1-p)·mu0` từ nuisance đã cross-fit.

Kiểm chứng: hai test riêng cho tính bất biến kỳ vọng và cho việc giảm variance.
Test giảm variance dùng dạng paired của Pitman–Morgan
(`Cov(a+b, a-b) = Var(a) - Var(b)`) vì hai chuỗi AUTOC tương quan khoảng 0,92; đo
trên 5 khối seed độc lập, tỷ lệ variance nằm trong 0,84–0,91.

Mức giảm variance của AUTOC yếu hơn nhiều so với mức giảm variance của signal từng
dòng, vì phần variance bị loại phần lớn đã tự triệt tiêu giữa `mean(top-q)` và
`mean(toàn bộ)`.

## 5. Giao thức cross-fitting

Development pool = `fit + validation` của Sprint 2. Cross-fitting 3 fold, stratify
theo `(treatment, conversion)`, fold seed chính 101 và seed thứ hai 202.

- Mỗi dòng chỉ được chấm bởi model không fit trên dòng đó.
- Nuisance dùng chung bộ fold với candidate. Đây là cross-fitting chuẩn; mỗi dòng
  vẫn được chấm bởi nuisance không fit trên nó.
- Confirmation Sprint 2 không được đọc ở bước OOF.

Vì confirmation Sprint 2 đã được quan sát và báo cáo ở Sprint 2, mọi kết quả mới
trên tập đó phải gọi là **retrospective confirmation**, không phải prospective test.
Muốn có bằng chứng hoàn toàn mới cần một randomized campaign log mới.

## 5bis. Hai họ challenger của vòng này: R-Learner và DR-Learner

Năm candidate của vòng thuộc hai họ chưa được mô tả ở
[`01_UPLIFT_FOUNDATIONS.md`](01_UPLIFT_FOUNDATIONS.md). Chúng bị dừng ở bước sàng lọc 20%
nên không xuất hiện trong bảng confirmation, nhưng vẫn thuộc phạm vi vòng này.

### R-Learner — trực giao hóa theo phân rã Robinson

Nguồn: Nie & Wager,
[*Quasi-Oracle Estimation of Heterogeneous Treatment Effects*](https://doi.org/10.1093/biomet/asaa076),
Biometrika 2021. Với `m(x) = E[Y | X = x]`, phân rã Robinson cho:

```text
Y - m(X) = [T - e(X)] · τ(X) + ε
```

Thay vì học `μ₁` và `μ₀` rồi lấy hiệu, R-Learner **trực giao hóa trước**: bỏ phần của `Y`
giải thích được bởi `X` và phần của `T` dự đoán được từ `X`, rồi mới hồi quy phần dư này lên
phần dư kia. Tối thiểu hóa R-loss `E{[Y - m(X)] - [T - e(X)]·τ(X)}²`.

Lợi thế lý thuyết: sai số của `m` và `e` chỉ ảnh hưởng bậc hai lên `τ̂`. Trên RCT thì `e = 0,85`
đã biết chính xác nên chỉ còn `m` phải ước lượng.

### DR-Learner — hồi quy pseudo-outcome

Đã mô tả ở [`01_UPLIFT_FOUNDATIONS.md`](01_UPLIFT_FOUNDATIONS.md) mục 3. Vòng này thêm hai
biến thể nuisance so với bản Sprint 1.

### Năm cấu hình đã chạy

| Candidate | Họ | Khác biệt | `policy_area_dr` sàng lọc |
|---|---|---|---:|
| `DR-Regression` | dr_learner | nuisance là regressor | 0,000570 |
| `DR-Binary` | dr_learner | nuisance là classifier | 0,000554 |
| `DR-Binary-MC2` | dr_learner | classifier, `mc_iters = 2` | 0,000569 |
| `R-Regression` | r_learner | nuisance là regressor | 0,000522 |
| `R-Binary` | r_learner | nuisance là classifier | 0,000552 |

So với Response `0,000766` ở cùng bước sàng lọc, cả năm cách một khoảng lớn — `0,00052` đến
`0,00057` so với `0,00067`–`0,00077` của nhóm meta-learner đơn giản. Paired CI của cả năm nằm
**hoàn toàn dưới 0**, và cả năm bị Response lẫn X-Renormalized dominate ở mọi mức ngân sách
5–20%, nên early-stop đã đăng ký kích hoạt và không candidate nào lên full development.

Đổi nuisance từ regressor sang classifier — thay đổi được kỳ vọng giúp nhiều nhất với outcome
nhị phân hiếm — **không** đảo được thứ hạng ở cả hai họ. Đó là bằng chứng rằng vấn đề không
nằm ở đặc tả nuisance.

Vòng 6 quay lại họ R-Learner theo một hướng khác: giữ neo tiên lượng và chỉ học phần dư đã co
lại, xem [`06_RARE_OUTCOME_LEARNERS.md`](06_RARE_OUTCOME_LEARNERS.md) mục 3. Kết quả vẫn không
qua gate hai fold seed.

## 6. Rank-Learner (ICML 2026)

Nguồn: *Rank-Learner: Orthogonal Ranking of Treatment Effects*, arXiv 2602.03517.
Ý tưởng: xếp hạng treatment effect là bài toán dễ hơn ước lượng chính xác CATE, nên
tối ưu trực tiếp một pairwise loss Neyman-orthogonal thay vì ước lượng magnitude.

Các thành phần lấy từ paper:

```text
φ(W)      = T/e·(Y - μ₁) - (1-T)/(1-e)·(Y - μ₀) + μ₁ - μ₀
t_τ(X,X′) = σ( (τ(X) - τ(X′)) / κ )
ω_τ(X,X′) = (1/κ)·t_τ·(1 - t_τ)
Δ_η(W,W′) = [φ(W) - τ(X)] - [φ(W′) - τ(X′)]
t̃         = t_τ + ω_τ·Δ_η
L         = E[ ℓ( σ(g(X) - g(X′)), t̃ ) ]
```

Hai lựa chọn hiện thực khác paper được ghi rõ:

1. Paper dùng mạng feed-forward/Adam; repo dùng LightGBM custom objective. Loss
   vẫn là binary cross-entropy của paper: với `p=σ(g_i-g_j)`, gradient theo
   pair difference là `p-t̃` và Hessian là `p(1-p)`. Pseudo-label được clip vào
   `(10⁻⁶, 1-10⁻⁶)` để objective hữu hạn.
2. Paper dùng "một tập con ngẫu nhiên các cặp rút đều ở mỗi epoch". Ở đây tập con
   đó là **ghép cặp hoàn hảo ngẫu nhiên**: mỗi vòng boosting xáo trộn toàn bộ chỉ
   số rồi ghép các vị trí liền kề. Cách này giữ tính rút đều theo từng cặp, cho mỗi
   dòng đúng một gradient khác 0 mỗi vòng, và có chi phí `O(n)`.

`κ` được đặt bằng `kappa_scale × std(τ̂_plugin)` để tự thích ứng với thang của CATE
trên dữ liệu outcome hiếm; `kappa_scale` là hyperparameter được screening với ba giá
trị 0,5 / 1 / 2.

Score trả về là điểm ưu tiên, **không** có scale CATE. Vì vậy EUCE và DR risk không
áp dụng cho model này, giống Response.

Ghi chú so sánh: paper báo AUUC ×10³ trên Criteo test 1M là `5,90 ± 0,40` so với
DR-Learner `5,17 ± 1,13`, ở thiết lập induced confounding khi train và randomized
khi test. Thiết lập đó khác thiết lập randomized-train của repo này, nên kết quả
paper không được dùng làm dự đoán cho kết quả ở đây.

Hiện thực: `src/rank_learner.py`. Kiểm chứng: `tests/test_rank_learner.py` xác nhận
DR score cross-fit khôi phục đúng ATE, và model học được ranking tương quan dương
với `tau` thật trên holdout tổng hợp.

## 7. Causal Q-Aggregation

Nguồn: Lan & Syrgkanis, AISTATS 2024 (arXiv 2310.16945). Với squared loss và
pseudo-outcome `Γ`, đồng nhất thức

```text
Σ_m w_m ‖Γ - f_m‖² = ‖Γ - f_w‖² + Σ_m w_m ‖f_m - f_w‖²
```

biến mục tiêu Q-aggregation thành

```text
Q(w) = ‖Γ - f_w‖² + nu · Σ_m w_m ‖f_m - f_w‖²
     = const - 2·wᵀb + (1 - nu)·wᵀAw + nu·wᵀd
```

Với `nu ∈ [0, 1)` hàm lồi trên simplex; `nu = 0` cho stacking thuần, `nu = 1/2` là
mặc định của paper. Tối ưu bằng SLSQP với ràng buộc `Σw = 1, w ≥ 0`.

Hai ràng buộc protocol:

1. Weights chỉ học trên prediction out-of-fold. `cross_fitted_weight_ensemble_score`
   tách thêm một lớp để điểm ensemble là out-of-sample so với **bước học weights**.
   Base predictions không được refit theo lớp ngoài này, vì vậy đây không phải
   fully nested stacking; artifact ghi rõ `validation_scope` và
   `nested_base_models=false`.
2. DR loss chỉ có nghĩa cho score có scale CATE. Response và Rank-Learner không
   được đưa vào Q-aggregation; với chúng chỉ có `rank_average_score`, một heuristic
   không có bảo đảm lý thuyết nào ở đây.

Hiện thực: `src/ensemble.py`. Kiểm chứng: `tests/test_ensemble.py` xác nhận nghiệm
nằm trên simplex, `nu = 0` không tệ hơn model đơn tốt nhất, và weights hội tụ về
model đúng khi các candidate còn lại là nhiễu.

## 8. Registry và promotion rule

Mỗi run ghi một dòng vào `output/improvement/registry.csv`, **kể cả run bị dừng
sớm**, với run ID, commit SHA, timestamp UTC, checksum dữ liệu, split hash,
fold/seed, config hash, số dòng và số conversion theo arm, thời gian fit/predict,
peak RSS, toàn bộ metric đã đăng ký, status và lý do dừng.

Early stop tự động khi score không hữu hạn hoặc gần hằng số. Quy tắc này đã kích
hoạt thật ở stage smoke 1%: undersampling `k = 7` trên mẫu quá nhỏ khiến
`min_child_samples = 1000` chặn mọi split và model trả về hằng số.

Promotion rule được khóa trước khi chạy confirmation:

1. `policy_area_dr` OOF của challenger lớn hơn Response **ở từng fold seed**, kiểm
   tra theo từng seed chứ không so hai giá trị đã gộp;
2. point estimate trên retrospective confirmation cùng dấu;
3. paired 95% CI của chênh lệch `policy_area_dr` có lower bound lớn hơn 0;
4. không regression về runtime gate, calibration hoặc guardrail.

Không đạt điều kiện 3 thì giữ champion đơn giản hơn và phát hành challenger kèm CI.

## 9. Vòng kế tiếp chạy dưới giao thức này

Protocol `data_optimization_protocol_v1` là vòng development riêng, **không** sửa protocol
Sprint 3 đã đóng băng: nó giữ nguyên metric chính, cross-fitting và luật promote ở trên,
chỉ đổi giả thuyết được kiểm. Gate shortlist còn được siết thêm — lọt top-N không đủ để đi
tiếp, challenger phải thắng Response theo `policy_area_dr` ở **từng** fold seed.

Phương pháp: [`05_DATA_REPRESENTATION.md`](05_DATA_REPRESENTATION.md). Kết quả:
[`../../report/05_DATA_OPTIMIZATION.md`](../../report/05_DATA_OPTIMIZATION.md).
