# Nền tảng causal learner cho binary outcome hiếm

Tài liệu này mô tả ba estimator được thêm trong protocol `causal-foundation-v1`, điều kiện nhận
dạng, cách kiểm thử và những giới hạn đã quan sát. Kết quả số nằm ở
[báo cáo thực nghiệm](../report/CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md); research review được khóa
trước khi chạy nằm ở [planning](../planning/CAUSAL_FOUNDATION_RESEARCH.md).

## 1. Bài toán cần giải

Criteo v2.1 có ba đặc điểm làm CATE khó hơn outcome prediction:

- conversion hiếm, khoảng 0,29%;
- xác suất treatment là `e=0,85`, nên nhánh control có ít dòng và ít event hơn;
- EDA cho thấy absolute treatment effect gần đồng biến với baseline risk.

Điểm thứ ba giải thích vì sao Response có ranking mạnh: nếu `tau(x)` gần tỷ lệ thuận với `p0(x)`,
xếp hạng risk gần giống xếp hạng uplift. Một causal learner muốn thắng phải học được residual
heterogeneity đủ lớn để bù variance phát sinh khi dùng treatment contrast.

Feature contract không đổi: chỉ `f0..f11` có mặt lúc quyết định. `visit` và `exposure` là biến hậu
can thiệp nên không được dùng làm feature. Propensity là hằng số của randomized design, không fit
`e(X)` từ covariate.

## 2. Binary DINA-CATE

Gao và Hastie đề xuất Difference in Natural Parameters. Với Bernoulli outcome, natural parameter
là log odds và treatment effect nội bộ là conditional log odds ratio `delta(x)`.

Cho `mu_w(x)=P(Y=1|X=x,W=w)`, đặt:

```text
Vw(x) = mu_w(x) [1-mu_w(x)]
a(x)  = e V1(x) / [e V1(x) + (1-e) V0(x)]
nu(x) = a(x) logit(mu1(x)) + [1-a(x)] logit(mu0(x))
eta_w(x) = nu(x) + [w-a(x)] delta(x)
```

`mu0` và `mu1` được cross-fit bên trong mỗi outer-train fold. LightGBM học `delta(x)` bằng
Bernoulli negative log-likelihood với offset `nu` và regressor `z=W-a`:

```text
gradient = z [expit(nu + z delta) - Y]
hessian  = z^2 p(1-p)
```

Deployment và policy evaluation vẫn cần absolute CATE. Một control-risk model được fit trong
outer-train, rồi đổi thang:

```text
p1(x) = expit[logit p0(x) + delta(x)]
CATE(x) = p1(x) - p0(x)
```

Xác suất nuisance được clip ở `1e-5`; log-odds effect được clip trong `[-3,3]`. Đây là guard số
học đã đăng ký trước, không được tune sau khi xem screen.

Nguồn phương pháp: Gao & Hastie,
[*Estimating Heterogeneous Treatment Effects for General Responses*](https://arxiv.org/abs/2103.04277),
Biometrics 2025. Paper cho phép mở rộng non-parametric function class; việc dùng LightGBM ở đây là
một implementation của gợi ý đó, không phải kết quả đã được paper chứng minh riêng cho boosting.

## 3. Anchored R-Learner

R-Learner dùng Robinson residualization:

```text
Y - m(X) = [W-e] tau(X) + epsilon,
m(X) = E[Y|X].
```

Với randomized design, `e=0,85` đã biết. `m(X)` được cross-fit trong outer-train. Thay vì cho
`tau` hoàn toàn tự do, protocol dùng risk anchor:

```text
tau(x) = alpha m(x) + 0,25 g(x).
```

`alpha` tối thiểu hóa R-loss của anchor. LightGBM học residual target:

```text
target_i = {Y_i-m_i-(W_i-e) alpha m_i} / (W_i-e)
weight_i = (W_i-e)^2.
```

Shrinkage `0,25` là hằng số khóa trước. Ablation Sentinel chỉ đưa flags vào residual model; risk
anchor và nuisance vẫn dùng raw `f0..f11`.

R-loss là đúng về kỳ vọng, nhưng treatment imbalance làm đóng góp hiệu dụng của hai arm rất khác
và rare control events làm residual target có variance lớn ở finite sample. Đây là lý do
cross-fitting và shrinkage cần thiết nhưng không bảo đảm ranking sẽ tốt hơn Response.

Nguồn: Nie & Wager,
[*Quasi-Oracle Estimation of Heterogeneous Treatment Effects*](https://arxiv.org/abs/1712.04912),
và Kennedy,
[*Towards Optimal Doubly Robust Estimation of Heterogeneous Causal Effects*](https://arxiv.org/abs/2004.14497).

## 4. Anchored Pattern R

Estimator này giữ cùng anchor nhưng thay flexible residual model bằng partial pooling theo sentinel
pattern. Với pattern `k`:

```text
g_k = sum_i weight_i target_i 1(pattern_i=k)
      / [sum_i weight_i 1(pattern_i=k) + 1000].
```

Pattern chưa thấy nhận residual 0. Công thức là ridge shrinkage closed-form về 0; repo không diễn
giải nó như Bayesian posterior. Mục tiêu là giảm interaction variance so với cây tự do.

Sentinel mode được fit chỉ từ `X` của outer-train. Tên “sentinel” là mô tả point mass, không phải
claim rằng Criteo xác nhận đó là missing value.

## 5. Kiểm thử tính đúng

Ba tầng test được dùng trước khi đọc kết quả Criteo:

1. công thức: gradient và Hessian của DINA khớp sai phân hữu hạn;
2. DGP tổng hợp: DINA và Anchored R phải khôi phục ranking của true CATE; Pattern R phải tách đúng
   moderator sentinel;
3. contract: invalid clip/shrink/prior bị từ chối, diagnostic ensemble không được advance, hai run
   khác source rows không được ghép.

Compact sentinel representation dùng raw `float32`, flags `bool` và count `uint8`. Test xác nhận
giá trị, thứ tự cột và prediction LightGBM giống tuyệt đối với dense float32 representation. OOF
component chỉ được ghép khi source index, treatment, outcome, `mu0`, `mu1`, DR signal và adjusted
signal trùng từng phần tử.

## 6. Thiết kế thực nghiệm

```text
research review
  -> protocol khóa trước
  -> unit/synthetic tests
  -> smoke code path
  -> screen 15%, seed 101 và 202
  -> gate: thắng Response ở cả hai seed
  -> full-development chỉ cho finalist
  -> randomized confirmation mới nếu muốn promote
```

Metric chính là diện tích trung bình của gross DR policy value trên budget 1–30%.
Qini, AUTOC, calibration và DR risk là bằng chứng phụ, không được override metric chính sau khi
thấy kết quả. Paired bootstrap giữ cùng OOF rows và cùng resample weights cho hai model.

## 7. Cách đọc failure mode đã quan sát

- Anchored R thắng Response ở cả bốn so sánh budget 1–2% của screen nhưng thua rõ khi tích phân
  tới 30%. Residual causal có thể giúp extreme top ranking mà làm hỏng phần rộng hơn.
- Pattern R và DINA đổi dấu giữa fold seed. Đây là variance/partition sensitivity, không phải bằng
  chứng để chọn seed có lợi.
- DINA có AUTOC trung bình cao nhưng `policy_area_dr` và Qini thấp hơn Response; score effect có
  dispersion và calibration error lớn hơn Anchored R. Natural-parameter scale giải quyết ràng
  buộc Bernoulli, không tự giải quyết finite-sample ranking variance.
- Response-Sentinel thắng screen bằng point estimate nhưng không tái lập trên full seed 202.
  Screen advancement không đồng nghĩa promotion.

Các nhận định về learner phụ thuộc DGP phù hợp với Curth & van der Schaar,
[*Nonparametric Estimation of Heterogeneous Treatment Effects*](https://proceedings.mlr.press/v130/curth21a.html).
Việc baseline-risk model có thể phản ánh absolute benefit heterogeneity được thảo luận trong
[*PATH Statement*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7531587/); interaction model có thể
overfit/mistarget khi tín hiệu interaction yếu trong nghiên cứu của
[van Klaveren và cộng sự](https://pubmed.ncbi.nlm.nih.gov/31195109/).

## 8. Backlog có căn cứ cho protocol mới

Đây là giả thuyết sinh ra sau khi xem kết quả, nên mỗi mục cần protocol ID và screen mới:

- đăng ký metric riêng cho budget 1–2% nếu đó là ràng buộc kinh doanh thật; bốn causal candidate
  đều thắng Response ở cả hai budget và cả hai seed screen, nhưng quan sát này hiện là hậu nghiệm;
- dùng shrinkage/calibration riêng cho log-odds effect của DINA, đánh giá trước trên DGP tổng hợp
  và không tune trên screen hiện tại;
- event-aware inner folds và moderator pooling theo số positive từng arm;
- tách risk anchor và residual ranking objective để residual chỉ được phép thay đổi extreme top;
- đưa Causal Forest về cùng artifact contract, thêm event-aware minimum leaf, balanced/honest
  sampling và leaf-effect shrinkage trước lần chạy Kaggle tiếp theo.

Causal Forest không được sửa hoặc chạy lại trong protocol này.

## 9. Follow-up top-tail và research 2026

Backlog trên đã được chuyển thành protocol/audit riêng. Paired simultaneous inference, exact hard-k,
event-support và overlap contract nằm trong
[`TOP_TAIL_POLICY_INFERENCE_GUIDE.md`](TOP_TAIL_POLICY_INFERENCE_GUIDE.md). Thứ tự model mới dựa trên
literature 2024–2026—hybrid prognostic–causal trước, pretraining/direct ranking sau và forest để vòng
Kaggle tiếp theo—nằm ở
[`LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md`](../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md).
