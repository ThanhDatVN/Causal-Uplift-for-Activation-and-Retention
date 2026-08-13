# Research foundation — causal learner cho binary outcome hiếm

> **Trạng thái 2026-08-09:** research/protocol đã được hiện thực và chạy xong. Không causal
> candidate nào qua screen stability gate; Response-Sentinel qua screen nhưng thất bại full seed
> stability. Xem [báo cáo](../report/CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md) và
> [method guide](../docs/CAUSAL_FOUNDATION_METHOD_GUIDE.md). Các giả thuyết mới sinh sau kết quả
> phải dùng protocol ID mới.

Ngày chốt research: 2026-08-09  
Phạm vi: nền tảng lý thuyết và thiết kế thực nghiệm sau `data-optimization-v1`  
Ngoài phạm vi vòng này: sửa/chạy lại Causal Forest trên Kaggle

## 1. Câu hỏi nghiên cứu

Kết quả hiện tại không cho phép kết luận “causal learner không cải thiện được”. Nó cho thấy một
bài toán hẹp hơn:

```text
conversion hiếm + treatment/control lệch 85/15
+ tau(x) gần tỷ lệ với baseline risk
→ phần treatment residual nhỏ hơn nhiều phần prognostic
→ CATE learner tự do có variance lớn và dễ làm hỏng ranking vốn đã tốt của Response
```

Vòng kế tiếp cần kiểm tra ba giả thuyết đã có cơ sở lý thuyết trước khi đọc kết quả mới:

1. học treatment effect trên natural-parameter scale phù hợp binary outcome;
2. anchor effect learner quanh outcome-risk model và shrink phần causal residual;
3. partial-pool moderator sentinel thay vì fit interaction tự do.

## 2. Bằng chứng nguồn

### 2.1 DINA cho binary response

Gao và Hastie đề xuất DINA — difference in natural parameters. Với Bernoulli outcome, estimand
là conditional log odds ratio. Paper nêu ba điểm liên quan trực tiếp:

- natural parameter không bị ràng buộc vào `[0,1]` như xác suất;
- với rare outcome, odds ratio xấp xỉ relative risk;
- thuật toán dùng nuisance function, cross-fitting và một likelihood score được thiết kế trực
  giao với nuisance error.

Thuật toán Bernoulli dùng:

```text
Vw(x) = muw(x) [1 - muw(x)]
a(x)  = e V1(x) / [e V1(x) + (1-e) V0(x)]
nu(x) = a(x) eta1(x) + [1-a(x)] eta0(x)
eta_w(x) = nu(x) + [w-a(x)] delta(x)
```

Trong đó `eta=logit(mu)` và `delta(x)` là log odds ratio. Bản non-parametric trong phần thảo
luận thay linear predictor bằng một function class bất kỳ và tối ưu cùng likelihood. Vòng này
dùng LightGBM làm function class; đây là hiện thực của extension được paper đề xuất, không phải
claim rằng paper đã chứng minh riêng cho boosting implementation này.

Nguồn:

- Gao & Hastie, *Estimating Heterogeneous Treatment Effects for General Responses*,
  Biometrics 2025 / arXiv 2103.04277:
  https://arxiv.org/abs/2103.04277
- Bản journal:
  https://academic.oup.com/biometrics/article/81/4/ujaf162/8403946

### 2.2 R-Learner và orthogonal residualization

R-Learner viết lại outcome model:

```text
Y - m(X) = [T - e(X)] tau(X) + epsilon
```

rồi tối ưu residual loss. Với randomized design của Criteo, `e(X)=0,85` đã biết; không cần học
propensity giả từ feature. Nie–Wager cho thấy cách tách nuisance và treatment component này có
quasi-oracle behavior dưới các điều kiện của paper.

EDA của project bổ sung cấu trúc cụ thể: phần lớn `tau(x)` đã được baseline-risk score giải thích.
Vì vậy ta không fit `tau` tự do mà đăng ký:

```text
tau(x) = alpha m(x) + lambda g(x),  lambda ∈ {0,25}
```

`alpha` được fit bằng R-loss trên nuisance prediction cross-fitted; `g(x)` học phần residual.
`lambda=0,25` là shrinkage cố định trước khi chạy, không chọn hậu nghiệm.

Nguồn:

- Nie & Wager, *Quasi-Oracle Estimation of Heterogeneous Treatment Effects*, Biometrika 2021:
  https://arxiv.org/abs/1712.04912
- Kennedy, *Towards Optimal Doubly Robust Estimation of Heterogeneous Causal Effects*, EJS 2023:
  https://arxiv.org/abs/2004.14497
- Curth & van der Schaar, *Nonparametric Estimation of Heterogeneous Treatment Effects:
  From Theory to Learning Algorithms*, AISTATS 2021:
  https://proceedings.mlr.press/v130/curth21a.html

### 2.3 Risk modeling và giới hạn của interaction model

PATH phân biệt risk modeling với effect modeling. Risk modeling có thể phát hiện absolute-effect
heterogeneity khi relative effect ổn định nhưng baseline risk khác mạnh — đúng pattern EDA của
Criteo. Tuy nhiên model vẫn phải được đánh giá trên absolute policy value, không đổi estimand
sản phẩm sang odds ratio.

Simulation của van Klaveren và cộng sự cho thấy effect models có interaction dễ overfit và
mistarget khi interaction thật yếu; penalization làm giảm miscalibration. Điều này là lý do vòng
này giữ Response làm anchor và shrink mọi residual thay vì thêm interaction không giới hạn.

Nguồn:

- PATH Statement, *Annals of Internal Medicine* 2020:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7531587/
- van Klaveren et al., *Models with interactions overestimated heterogeneity of treatment
  effects and were prone to treatment mistargeting*, JCE 2019:
  https://pubmed.ncbi.nlm.nih.gov/31195109/
- Tian et al., *A Simple Method for Estimating Interactions between a Treatment and a Large
  Number of Covariates*, JASA 2014:
  https://pubmed.ncbi.nlm.nih.gov/25729117/

### 2.4 Không có learner thắng mọi data-generating process

Curth–van der Schaar phân tích rằng lựa chọn meta-learner phải dựa trên cấu trúc DGP; two-step
learner có thể regularize first-stage bias nhưng cũng phải ước lượng nhiều thành phần hơn và có
thể tăng variance ở finite sample. Alaa–van der Schaar cũng chỉ ra bottleneck thay đổi theo sample
size. Vì vậy protocol dùng stage gate thay vì mặc định model phức tạp hơn sẽ tốt hơn.

Nguồn:

- https://proceedings.mlr.press/v130/curth21a.html
- https://proceedings.mlr.press/v80/alaa18a.html

## 3. Ba estimator được đăng ký

### Binary DINA-CATE

1. internal cross-fit `mu0`, `mu1` trong outer-train;
2. tạo `a(x)`, `nu(x)` theo Bernoulli DINA;
3. fit non-parametric log-odds treatment effect bằng custom likelihood;
4. fit `p0(x)` trên toàn outer-train control;
5. đổi về absolute CATE:

```text
p1(x) = expit[logit p0(x) + delta(x)]
CATE(x) = p1(x) - p0(x)
```

### Anchored R-25

1. internal cross-fit `m(x)=E[Y|X]`;
2. fit `alpha` bằng R-loss;
3. fit LightGBM cho residual `g(x)` với R-loss weights;
4. output `alpha m(x) + 0,25 g(x)`.

Một ablation thêm sentinel flags chỉ từ outer-train `X`.

### Anchored Pattern R

Dùng cùng R-loss nhưng `g(x)` là lookup trên sentinel pattern. Mỗi pattern residual có nghiệm
ridge closed-form:

```text
g_k = sum_i w_i target_i 1(pattern_i=k)
      / [sum_i w_i 1(pattern_i=k) + prior_weight]
```

Đây là partial pooling về 0, không phải Bayesian posterior claim. Pattern chưa thấy nhận residual 0.

## 4. Những gì không được làm sau khi thấy kết quả

- không đổi shrinkage 0,25;
- không thêm/bớt candidate trên cùng screen;
- không chọn lại `min_child_samples`, pattern prior hay effect clip;
- không dùng Qini/DR risk để override `policy_area_dr`;
- không đọc confirmation Sprint 2;
- không chạy Causal Forest trong protocol này.

Nếu các giả thuyết thất bại, đó là kết quả cần lưu lại. Vòng sau phải có protocol ID mới.

## 5. Causal Forest backlog

Chỉ ghi lại để chạy Kaggle sau khi code nền tảng ổn định:

- event-aware minimum leaf theo positive count từng arm;
- honest/balanced treatment-control subsampling;
- leaf-effect shrinkage;
- dùng sentinel augmentation nhất quán với local protocol;
- export OOF/holdout prediction theo cùng artifact contract;
- chấm bằng cùng `policy_area_dr`, AUTOC, Qini và paired bootstrap.

Không mục nào ở trên được dùng để diễn giải kết quả của protocol hiện tại.
