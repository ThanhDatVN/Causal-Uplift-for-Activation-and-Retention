# Tuần 5 — Vòng cải tiến model có đăng ký trước: evaluation stack, OOF và challenger

**Sprint:** 3
**Trọng tâm theo kế hoạch cũ:** Docker/runbook/CI, bản nháp báo cáo và slide
**Trọng tâm thực tế:** Giao thức đăng ký trước, evaluation stack mới, 12 candidate, ensemble
**Trạng thái:** Đạt phạm vi mới; phạm vi cũ chưa làm

---

## 5.1 Vì sao đổi phạm vi — đọc mục này trước

Kế hoạch gốc cho Tuần 5 là Docker/CI và bản nháp báo cáo. Phạm vi thực tế khác, và lý do
cần được nêu thẳng chứ không giấu.

**Vấn đề còn tồn ở cuối Tuần 4:**

1. Ba model đầu bảng (Response, S, X) có CI của chênh lệch đều **chứa 0**. Ba sprint chưa
   tách được model nào khỏi model nào.
2. Metric chính là Qini — một đại lượng đã chuẩn hóa, **không** trả lời "ở budget 10% được
   bao nhiêu conversion tăng thêm". Nhưng quyết định sản phẩm luôn gắn với một budget.
3. Chọn model dùng một validation split cố định, chưa dùng hết dữ liệu development.

**Đánh đổi:** đóng gói một kết quả chưa tách được bằng Docker và slide sẽ cho một sản phẩm
đẹp về hình thức nhưng không mạnh hơn về bằng chứng. Ngược lại, một vòng cải tiến có giao
thức chặt sẽ hoặc tìm ra model tốt hơn, hoặc **chứng minh được rằng không có** — cả hai đều
là kết quả dùng được.

**Cái mất:** Docker, CI và slide deck chưa làm. Ghi rõ trong mục 6 và trong
`report/SPRINT_3_FINAL_REPORT.md` mục 11.

---

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Giao thức đăng ký trước | `configs/sprint3_improvement_protocol.json` |
| Evaluation stack mới | `src/ranking_metrics.py`, `src/policy_evaluation.py` |
| Hạ tầng cross-fitting | `src/experiment.py`, registry 43 cột |
| Danh mục candidate | `src/candidates.py` |
| Rank-Learner (ICLR 2026) | `src/rank_learner.py` |
| Ensemble | `src/ensemble.py` |
| Runner | `scripts/run_oof_experiment.py` |
| Smoke → screen → finalist | 3 stage, 12 → 6 candidate |

## 3. Cách hoạt động

### 3.1 Đăng ký trước — thứ tự không được đảo

`configs/sprint3_improvement_protocol.json` được viết và khóa **trước khi chạy dòng code
đầu tiên**. Nó ghi: estimand, vai trò từng tập dữ liệu, sơ đồ cross-fitting, metric chính,
lưới budget, danh sách metric phụ, comparator, promotion rule, quy tắc early-stop, resource
gate, và toàn bộ 12 candidate kèm **giả thuyết cho từng cái**.

Vì sao thứ tự quan trọng: nếu chọn metric sau khi xem kết quả, việc chọn metric **chính là**
việc chọn kết luận. Tuần 6 gặp đúng tình huống đó và giao thức đã cứu.

### 3.2 Metric chính mới — `policy_area_dr`

```
G(b) = E[ 1{score thuộc top-b} · Γ ]
policy_area_dr = (∫ G(b) db trên dải budget) / độ rộng dải
```

Lưới budget: `{0,01 0,02 0,05 0,10 0,15 0,20 0,25 0,30}`, tích phân trapezoid.

Ba lựa chọn thiết kế và lý do:

1. **Kỳ vọng trên toàn population**, không trên riêng nhóm được target. Nhờ vậy giá trị ở
   các budget cộng gộp được, và policy "không target ai" đúng bằng 0.
2. **`Γ` là DR signal**, không phải IPW thuần — variance thấp hơn nhiều với outcome hiếm.
3. **Đơn vị là conversion tăng thêm**, không phải tiền. Metric chọn model không được gắn
   giá tiền giả định.

**Kiểm chứng độc lập:** hàm này tái lập đúng cột DR đã phát hành ở Sprint 2 với sai khác
tối đa `2,6e-08` — bậc `1/n` do nội suy ở biên ngân sách thay vì cắt cứng. Đã khóa thành
test trong `tests/test_release_consistency.py`.

### 3.3 TOC / RATE / AUTOC — và hai lỗi thật bị test bắt

```
TOC(q) = mean(Γ | top-q) − mean(Γ)
RATE   = ∫ α(q)·TOC(q) dq
```

`α(q)=1` cho AUTOC; `α(q)=q` cho biến thể trọng số kiểu Qini.

**Lỗi 1 — tie không được gộp.** Lần chạy test đầu tiên, `test_constant_score_gives_zero_rate`
fail: score hằng số cho RATE = 0,0036 thay vì 0. Nguyên nhân: mỗi dòng được coi là một
điểm cắt riêng, nên "top-q" của một score hằng số lại là q dòng đầu theo thứ tự tuỳ ý.

Sửa: gộp các quan sát cùng score thành **một** điểm cắt. Một quy tắc ưu tiên không phân
biệt được chúng thì không được hưởng lợi từ thứ tự ngẫu nhiên bên trong nhóm. Cùng lỗi tồn
tại trong đường cong policy value và được sửa cùng lúc.

**Lỗi 2 — khẳng định sai của chính tôi.** Test ban đầu giả định AUTOC đổi dấu khi đảo
ngược ranking. Nó fail, và kiểm tra lại cho thấy giả định sai. Từ đồng nhất thức

```
TOC_rev(1−q) = −q·TOC(q)/(1−q)
```

suy ra `∫ q·TOC_rev = −∫ q·TOC` nhưng `∫ TOC_rev ≠ −∫ TOC`. Chỉ biến thể `α(q)=q` mới phản
đối xứng. Test được viết lại để khẳng định đúng tính chất này.

### 3.4 Outcome adjustment — giảm variance mà không đổi estimand

```
R_adj = (Y − m(X))·(T − p)/(p(1−p))
```

Với `p` hằng và bất kỳ `m(X)` nào không phụ thuộc `T`, `Y`:

```
E[R_adj | X] = (mu1 − m) − (mu0 − m) = tau(X)
```

Adjustment không đổi estimand, chỉ giảm variance khi `m` xấp xỉ tốt `E[Y|X]`.

**Ranh giới nguồn:** repo chỉ đọc được abstract của Bokelmann & Lessmann (EJOR 2024), không
đọc được công thức đầy đủ. Vì vậy hàm này là dạng regression-adjusted quen thuộc **được suy
ra và kiểm chứng tại chỗ**, không phải bản sao công thức của paper. Điều này ghi trong
docstring.

Kiểm chứng: đo trên 5 khối seed độc lập, tỷ lệ variance AUTOC nằm trong 0,84–0,91. Test
dùng dạng paired của Pitman–Morgan (`Cov(a+b, a−b) = Var(a) − Var(b)`) vì hai chuỗi tương
quan khoảng 0,92 — dạng paired có lực kiểm định cao hơn nhiều. 24 lần lặp là không đủ; 120
lần mới ổn định.

### 3.5 Cross-fitting — điểm thiết kế quan trọng nhất của Sprint 3

```
1. build_sprint3_splits()      tái dựng + đối chiếu hash, dừng nếu lệch
2. make_folds(3, seed)         StratifiedKFold trên treatment*2 + outcome
3. cross_fit_nuisance()        MỘT LẦN: mu0, mu1 out-of-fold
4. dựng dr_signal              dùng CHUNG cho mọi candidate
5. mỗi candidate × mỗi fold:   fit trên train_idx → predict test_idx
6. paired bootstrap            trên cùng OOF rows
```

**Bước 3–4 là mấu chốt.** Nếu mỗi candidate có tín hiệu đánh giá riêng, chênh lệch giữa hai
model sẽ **lẫn** với chênh lệch giữa hai thước đo, và paired bootstrap mất ý nghĩa. Nuisance
được fit một lần và dùng chung.

Nuisance dùng chung bộ fold với candidate. Đây là cross-fitting chuẩn: mỗi dòng vẫn được
chấm bởi cả nuisance lẫn model không fit trên nó.

### 3.6 Rank-Learner — hiện thực một phương pháp 2026

Nguồn: arXiv 2602.03517 (ICLR 2026). Ý tưởng: xếp hạng là bài toán dễ hơn ước lượng chính
xác CATE, nên tối ưu trực tiếp một pairwise loss Neyman-orthogonal.

Thành phần lấy từ paper:

```
φ(W)      = T/e·(Y − μ₁) − (1−T)/(1−e)·(Y − μ₀) + μ₁ − μ₀
t_τ(X,X′) = σ((τ(X) − τ(X′))/κ)
ω_τ       = (1/κ)·t_τ·(1 − t_τ)
t̃         = t_τ + ω_τ·([φ(W) − τ(X)] − [φ(W′) − τ(X′)])
```

Hai lựa chọn **không** lấy từ paper, ghi rõ trong docstring:

1. `ℓ` chọn là squared loss trên `σ(g_i − g_j)`; gradient `2(σ(d) − t̃)·σ′(d)` và
   Gauss–Newton Hessian `2·σ′(d)²` đưa vào LightGBM qua custom objective.
2. Tập cặp là **ghép cặp hoàn hảo ngẫu nhiên** mỗi vòng boosting: xáo trộn toàn bộ chỉ số
   rồi ghép vị trí liền kề. Mỗi dòng đúng một gradient khác 0, chi phí `O(n)`.

`κ = kappa_scale × std(τ̂_plugin)` để tự thích ứng với thang CATE. Screening ba giá trị
`kappa_scale ∈ {0,5; 1; 2}`.

### 3.7 Registry — ghi cả run thất bại

43 cột, mỗi run một dòng, **kể cả run bị dừng sớm**: run ID, commit SHA, timestamp UTC,
checksum dữ liệu, split hash, fold/seed, config hash, số dòng và conversion theo arm, thời
gian fit/predict, peak RSS, toàn bộ metric, status, lý do dừng.

Vì sao ghi cả thất bại: nếu chỉ ghi run thành công, bảng kết quả mang publication bias ngay
bên trong dự án.

Quy tắc early-stop **đã kích hoạt thật** ở smoke 1%: undersampling `k=7` trên mẫu quá nhỏ
khiến `min_child_samples=1000` chặn mọi split, model trả hằng số. X-Renormalized và
S-Under7 được ghi `failure_reason = constant_score`.

### 3.8 Causal Q-Aggregation

Với squared loss và pseudo-outcome `Γ`, đồng nhất thức

```
Σ_m w_m ‖Γ − f_m‖² = ‖Γ − f_w‖² + Σ_m w_m ‖f_m − f_w‖²
```

biến mục tiêu thành `Q(w) = ‖Γ − f_w‖² + nu · Σ_m w_m ‖f_m − f_w‖²`, lồi trên simplex với
`nu ∈ [0,1)`. Tối ưu bằng SLSQP.

Hai ràng buộc: weights chỉ học trên OOF; và DR loss chỉ có nghĩa cho score **có scale CATE**
— Response và Rank-Learner không được đưa vào.

## 4. Kết quả

**Screening 20%** (1.118.367 dòng, 325 conversion ở control):

| Candidate | policy_area_dr | AUTOC | Qini | Fit (giây) |
|---|---:|---:|---:|---:|
| Response | 0,000766 | 0,002729 | 0,176841 | 13,0 |
| Rank-K05 | 0,000698 | 0,002110 | 0,169579 | 108,5 |
| X-Renormalized | 0,000693 | 0,002201 | 0,151600 | 6,5 |
| S-Under7 | 0,000671 | 0,002190 | 0,129375 | 3,1 |
| DR-Regression | 0,000570 | 0,001862 | 0,076844 | 103,1 |
| R-Regression | 0,000522 | 0,001763 | 0,058726 | 81,3 |
| T-Under7 | 0,000519 | 0,001617 | 0,044794 | 3,0 |

Ở stage này paired CI của **mọi** challenger so với Response đều nằm hoàn toàn dưới 0. Họ
DR/R-Learner bị dominate ở mọi budget 5–20% → dừng theo quy tắc early-stop.

Kết quả outcome-adjusted xếp hạng **giống hệt** raw ở mọi candidate — cross-check quan
trọng: kết luận không phụ thuộc lựa chọn kỹ thuật của metric.

**Full development OOF** (5.591.836 dòng, hai fold seed, 3.067 giây mỗi seed):

| Model | Trung bình | Seed 101 | Seed 202 |
|---|---:|---:|---:|
| Response | 0,000861 | 0,000852 | 0,000870 |
| Ensemble-QAgg | 0,000835 | 0,000835 | 0,000834 |
| X-Renormalized | 0,000835 | 0,000826 | 0,000844 |
| S-Under7 | 0,000814 | 0,000829 | 0,000799 |
| Rank-K1 | 0,000787 | 0,000771 | 0,000802 |

`oof_seeds_won` của mọi challenger bằng **0**: không challenger nào thắng Response ở bất kỳ
seed nào.

Ghi chú về S-Under7: seed 101 có CI chứa 0 (`[-0,000052; +0,000007]`), seed 202 CI nằm hoàn
toàn dưới 0 (`[-0,000101; -0,000044]`). Đây là lý do promotion rule kiểm tra **theo từng
seed** thay vì so hai giá trị đã gộp.

## 5. Quyết định và lý do

1. **Dừng họ DR/R-Learner sau screening** theo quy tắc early-stop đã đăng ký, không chạy
   tiếp lên full development.
2. **Không đổi metric chính** dù Qini và `policy_area_dr` cho thứ hạng khác nhau ở một số
   candidate. Giao thức đã khóa.
3. **Rank-Learner không bị loại vì "mới"** mà vì số: nó tụt hạng khi có nhiều dữ liệu hơn
   và chậm gấp 19–59 lần.

## 6. Chưa xong và rủi ro

- Docker, CI, slide deck: **chưa làm**, lệch khỏi kế hoạch gốc.
- Resource gate chỉ kiểm tra trước khi chạy; RAM khả dụng đã tụt xuống 1,55 GB, dưới ngưỡng
  2,0 GB đã đăng ký, mà không có gì dừng lại. *(Đã sửa ở Tuần 6.)*
- Chưa chạy confirmation — cố ý, để không xem trước khi khóa shortlist.

## 7. Chuẩn bị cho tuần sau

Tuần 6: chốt shortlist trên OOF, chạy confirmation **đúng một lần**, áp promotion rule, và
đóng gói thành sản phẩm.

## 8. Câu hỏi cần mentor phản biện

Nếu không challenger nào đạt promotion rule, kết quả "không cải thiện" có được coi là một
kết quả hợp lệ để báo cáo không, hay cần nới rule?

*Rule không được nới. Xem Tuần 6.*
