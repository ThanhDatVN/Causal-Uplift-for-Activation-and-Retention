# Hướng dẫn phương pháp và sản phẩm Sprint 2

## 1. Sprint 2 bổ sung điều gì?

Sprint 1 trả lời: model nào xếp hạng khách hàng tốt theo uplift? Sprint 2 tiến thêm một
bước: biến ranking thành policy `target top-k%`, đo uncertainty, kiểm tra chi phí hòa vốn
và đóng gói thành dashboard.

Sprint 2 không mở lại final test Sprint 1. Phần bù chính xác của sample 50% Sprint 1
được dùng làm pool mới, rồi chia:

- fit: 4.193.877 dòng (60%);
- validation: 1.397.959 dòng (20%);
- confirmation: 1.397.959 dòng (20%).

Các source-index hash nằm trong `output/sprint2/protocol_manifest.json`.

## 2. Vì sao cần xử lý rare conversion?

Conversion Criteo chỉ khoảng 0,29%. Stratified undersampling giữ toàn bộ positive và giữ
negative riêng trong mỗi treatment arm với:

\[
s_t = \frac{1/k-p_t}{1-p_t},
\]

trong đó \(p_t=P(Y=1\mid T=t)\), \(k=7\). Đây là công thức từ Nyberg & Klami
(2023), Eq. 4, áp dụng riêng từng arm.

### X‑Learner renormalized

Với stratified undersampling cùng \(k\) ở hai arm và outcome hiếm:

\[
\tau^*(x) \approx k\tau(x), \qquad
\widehat\tau(x)=\widehat\tau^*(x)/k.
\]

Phép chia \(k\) là **xấp xỉ**, không phải đẳng thức tổng quát. Bài gốc gọi đây là
renormalization và ghép nó với stratified undersampling.

### Local-neighborhood exact restoration

Nếu một classifier trực tiếp ước lượng xác suất sau undersampling \(q=p^*\), xác suất
gốc được khôi phục bằng:

\[
p = \frac{s q}{1-q(1-s)}.
\]

Công thức phải áp dụng riêng cho treatment/control, sau đó mới lấy \(p_1-p_0\). Vì vậy
release dùng nó với T‑Learner/double-classifier (`T-LocalExact`). Việc nhúng correction
vào các bước imputation của X‑Learner không được bài gốc kiểm chứng; ablation 10% của dự
án cho kết quả xấu nên không được promote.

### τ-isotonic

Revert label:

\[
R=\frac{TY}{e}-\frac{(1-T)Y}{1-e}, \qquad E[R\mid X]=\tau(X).
\]

Isotonic regression fit ánh xạ đơn điệu từ score sang \(R\) trên validation. Candidate
giảm EUCE confirmation từ `0,000462` xuống `0,000240`, nhưng Qini giảm nhẹ do tạo nhiều
ties; ΔQini so với X‑Renormalized có CI chứa 0. Candidate được giữ như calibration
ablation, không được dùng để tuyên bố ranking tốt hơn.

Nguồn chính: Nyberg & Klami,
[Exploring uplift modeling with high class imbalance](https://link.springer.com/article/10.1007/s10618-023-00917-9),
đặc biệt các mục 3.1–3.3. Bài ghi rõ S/X compatibility chưa được đánh giá trong thí
nghiệm của họ; tài liệu dự án không mở rộng claim đó.

## 3. Đánh giá model

- **Qini chuẩn hóa:** metric ranking chính; implementation được cross-check với
  `scikit-uplift`.
- **AUUC chuẩn hóa:** metric ranking phụ.
- **Transformed-outcome MSE:** scale-aware nhưng variance cao.
- **EUCE:** calibration theo equal-frequency bins. Code dùng 10 bins; bài Nyberg dùng
  100 bins. Hai con số không được so trực tiếp vì confirmation control chỉ có khoảng vài
  trăm conversion và 100 bins sẽ rất nhiễu.
- **Paired percentile bootstrap:** 500 resamples, cùng weights cho mọi model; báo CI của
  chính chênh lệch Qini.

## 4. Đánh giá policy

IPW signal:

\[
\phi_{IPW}=\frac{TY}{e}-\frac{(1-T)Y}{1-e}.
\]

DR/AIPW signal:

\[
\phi_{DR}=\mu_1-\mu_0+
\frac{T(Y-\mu_1)}{e}-
\frac{(1-T)(Y-\mu_0)}{1-e}.
\]

Model/policy được fit từ fit/validation; confirmation chỉ dùng để tính
\(\frac1n\sum\pi(X_i)\phi_i\). Release báo DR làm headline và IPW làm sensitivity. DR
không có nghĩa “luôn đúng”; trong RCT này propensity được biết/ước lượng ổn định, còn
outcome models hỗ trợ giảm variance.

Nguồn: Dudík et al.
[ICML 2011](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/)
và Athey & Wager
[Econometrica 2021](https://doi.org/10.3982/ECTA15732).

## 5. Đọc kết quả chính

| Model | Qini confirmation | EUCE |
|---|---:|---:|
| X‑Renormalized | 0,191557 | 0,000462 |
| X‑Calibrated | 0,188528 | 0,000240 |
| Response | 0,182789 | không áp dụng |
| T‑LocalExact | 0,117668 | 0,000957 |

X‑Renormalized có point estimate cao nhất, nhưng hơn Response chưa có ý nghĩa theo paired
CI. Champion vẫn là Response vì được chọn trước trên validation.

Ở budget 10%, `value=1`, `cost=0,0005`:

- Response DR net/customer = `0,000799`;
- 95% CI = `[0,000608; 0,000977]`;
- Δ so với random CI = `[0,000582; 0,000928]`.

Đây là **conversion-equivalent scenario**, không phải tiền.

## 6. Dashboard

`output/dashboard.html` là self-contained, đọc dữ liệu inlined từ
`output/dashboard_data.json`. Nó có:

- budget checkpoints 0/1/5/10/20/30%;
- population, value/conversion và cost/contact;
- DR gross + 95% CI;
- break-even cost;
- model evidence và provenance;
- low/high/no-target acceptance scenarios;
- CSV export có assumption fields.

Build và test:

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

## 7. Causal Forest

Profile `kaggle-safe` dùng 200 trees, CV=2, `max_samples=0.25`,
`inference=False`. Vì inference tắt để giảm tài nguyên, `effect_interval()` không phải
Definition of Done của profile này. Local 0,1% chỉ là code-path smoke; kết quả nghiên cứu
chỉ tồn tại sau Kaggle gates 20% → 30% → 50%.

Xem [KAGGLE_CAUSAL_FOREST.md](KAGGLE_CAUSAL_FOREST.md).
