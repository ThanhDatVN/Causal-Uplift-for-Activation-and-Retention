# Tutorial — hiểu dự án Causal Uplift từ số 0

## 1. Câu hỏi kinh doanh

Model conversion thông thường trả lời: **ai có khả năng mua?**

Dự án này hỏi: **treatment có làm một nhóm khách hàng mua nhiều hơn so với khi không
treatment không?**

\[
\tau(x)=E[Y(1)-Y(0)\mid X=x].
\]

Đây là CATE (*Conditional Average Treatment Effect*) hay uplift.

## 2. Vì sao không quan sát treatment effect của từng cá nhân?

Với cùng một người, chỉ quan sát một trong hai potential outcomes:

- \(Y(1)\): kết quả nếu nhận treatment;
- \(Y(0)\): kết quả nếu không nhận treatment.

Randomized experiment cho phép ước lượng hiệu ứng trung bình/conditional effect, nhưng
không biến principal stratum của từng cá nhân thành nhãn quan sát được.

Persuadable, Sure Thing, Lost Cause và Sleeping Dog là **khung counterfactual khái niệm**.
Không được nhìn dấu của một score rồi tuyên bố đã biết một người thuộc nhóm nào. Dashboard
release dùng operational policy “target top-k%”, không hiển thị bốn nhãn cá nhân.

## 3. Dữ liệu

Criteo có 13.979.592 quan sát từ randomized incrementality test:

- feature ẩn danh `f0`–`f11`;
- `treatment`;
- outcomes `conversion`, `visit`, `exposure`.

Dự án dùng `conversion`; không dùng `visit`/`exposure` làm feature vì chúng có thể nằm
sau treatment. Treatment rate khoảng 85%, conversion rate khoảng 0,29%.

Xem [data card](data_cards/CRITEO_V2_1.md).

## 4. Các model

### Response baseline

Học \(P(Y=1\mid X)\), bỏ qua treatment. Nó không phải CATE estimator nhưng có thể tạo
ranking policy có thể đạt Qini cao khi response propensity tương quan với observed uplift.

### S‑Learner

Một model học \(Y=f(X,T)\):

\[
\widehat\tau(x)=\widehat f(x,1)-\widehat f(x,0).
\]

### T‑Learner

Hai response models:

\[
\widehat\tau(x)=\widehat\mu_1(x)-\widehat\mu_0(x).
\]

### X‑Learner

Ước lượng response surfaces, impute effects trong từng arm, fit effect models rồi kết
hợp theo propensity. Nó có thể hữu ích khi treatment/control size mất cân bằng.

### DR‑Learner

Dùng outcome nuisance và propensity để tạo doubly robust pseudo-outcome. “Doubly robust”
không bảo đảm model luôn thắng ở finite sample.

### Causal Forest

Học local treatment-effect heterogeneity bằng honest forest. Cloud release chưa tồn tại;
local code-path smoke 0,1% đã pass.

## 5. Đánh giá

Không có ground-truth individual CATE nên dự án kết hợp:

- Qini/AUUC cho ranking;
- EUCE cho calibration;
- transformed-outcome MSE làm metric phụ;
- paired percentile bootstrap cho uncertainty;
- IPW/DR policy value cho quyết định top-k.

Model A có Qini point estimate cao hơn model B chưa đủ; phải xem CI của
**Qini(A) − Qini(B)** trên cùng bootstrap resamples.

## 6. Sprint 2 không tái dùng test Sprint 1

Sprint 2 loại toàn bộ sample 50% đã dùng trong Sprint 1, lấy phần bù và chia
fit/validation/confirmation.

| Model | Qini confirmation |
|---|---:|
| X‑Renormalized | 0,191557 |
| X‑Calibrated | 0,188528 |
| Response | 0,182789 |
| T‑LocalExact | 0,117668 |

X‑Renormalized hơn Response `0,008768`, nhưng paired 95% CI
`[-0,018626; 0,038772]`; chưa phân biệt được. Response được chọn trên validation nên vẫn
là champion.

## 7. Từ score sang policy

Policy top-k:

1. tính score;
2. sort giảm dần;
3. target top k%;
4. dùng randomized confirmation để ước lượng incremental value.

Ở top 10%, value=1 và cost/contact=0,0005, Response policy có DR net/customer
`0,000799`, 95% CI `[0,000608; 0,000977]`.

Criteo không có tiền; đây là conversion-equivalent scenario, không phải actual profit.

## 8. Dashboard

Mở `output/dashboard.html`. Dashboard cho chọn budget, population, value và cost; nó hiển
thị incremental conversions, CI, break-even, model evidence và limitations.

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

## 9. Thứ tự đọc tiếp

1. [Báo cáo Sprint 2](../report/SPRINT_2_FINAL_REPORT.md)
2. [Hướng dẫn phương pháp](SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md)
3. [Decision contract](DECISION_CONTRACT.md)
4. [Model card](model_cards/SPRINT_2_POLICY_RELEASE.md)
5. [Kaggle Causal Forest runbook](KAGGLE_CAUSAL_FOREST.md)
