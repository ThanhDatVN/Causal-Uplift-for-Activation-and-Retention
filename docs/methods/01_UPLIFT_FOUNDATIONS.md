# Nền tảng uplift — đại lượng đích, họ model và khung đánh giá

- **Vòng sinh ra tài liệu:** Sprint 1 — nền tảng causal và bảng xếp hạng đầu tiên
- **Hiện thực:** [`../../src/baselines.py`](../../src/baselines.py),
  [`../../src/evaluation.py`](../../src/evaluation.py)
- **Kết quả:** [`../../report/01_SPRINT_1_FOUNDATION.md`](../../report/01_SPRINT_1_FOUNDATION.md)
- **Đọc tiếp:** [`02_CALIBRATION_AND_POLICY_VALUE.md`](02_CALIBRATION_AND_POLICY_VALUE.md)

Đây là tài liệu vào cửa của `docs/`. Nó dựng đại lượng đích, điều kiện nhận dạng, năm họ
model của bảng release đầu tiên và khung metric mà mọi vòng sau đều dùng lại.

## 1. Predicted conversion khác uplift thế nào?

Conversion model học:

\[
P(Y=1\mid X=x)
\]

Uplift model cần học:

\[
\tau(x)=E[Y(1)-Y(0)\mid X=x]
\]

Một người có xác suất mua cao vẫn có thể mua dù không nhận quảng cáo. Target họ có thể
không tạo incremental conversion nhưng vẫn phát sinh treatment cost. Uplift hỏi quảng cáo
**làm thay đổi** xác suất mua bao nhiêu.

Không thể quan sát đồng thời `Y(1)` và `Y(0)` cho một người. Đây là *fundamental problem
of causal inference*. Vì vậy project đánh giá ranking/policy ở mức nhóm trên holdout,
không tuyên bố quan sát được individual treatment effect.

## 2. Vì sao RCT quan trọng?

Nếu treatment được gán ngẫu nhiên:

\[
(Y(1),Y(0)) \perp T
\]

thì chênh lệch outcome trung bình giữa hai arm ước lượng ATE. Để diễn giải CATE còn cần:

- **Consistency/SUTVA:** treatment quan sát khớp treatment đã định nghĩa; không có
  interference đáng kể giữa các đơn vị.
- **Positivity:** mỗi vùng feature cần có xác suất nhận cả treatment và control.
- **Random assignment:** không có confounding trong cơ chế gán treatment.

Balance table và propensity AUC gần 0,5 là diagnostic, không thay cho provenance của RCT.

## 3. Năm họ model của bảng release Sprint 1

Causal Forest là họ thứ sáu, thêm ở một vòng sau và mô tả riêng ở
[`04_CAUSAL_FOREST.md`](04_CAUSAL_FOREST.md); các estimator cho outcome hiếm nằm ở
[`06_RARE_OUTCOME_LEARNERS.md`](06_RARE_OUTCOME_LEARNERS.md).

### Response model

Học conversion propensity rồi dùng nó để xếp hạng. Đây là baseline không ước lượng CATE,
nhưng không tách `Y(1)` và `Y(0)`, không nên diễn giải score như CATE đã hiệu chỉnh.

### S-Learner

Một mô hình:

\[
\hat\mu(x,t)=E[Y\mid X=x,T=t]
\]

Sau đó:

\[
\hat\tau(x)=\hat\mu(x,1)-\hat\mu(x,0)
\]

Ưu điểm: gọn, chia sẻ thông tin giữa hai arm. Nhược: model có thể bỏ qua treatment khi
tín hiệu treatment nhỏ so với tín hiệu outcome.

### T-Learner

Học hai mô hình:

\[
\hat\mu_1(x)=E[Y\mid X=x,T=1],\quad
\hat\mu_0(x)=E[Y\mid X=x,T=0]
\]

rồi lấy hiệu. Linh hoạt nhưng control arm nhỏ và positive hiếm khiến variance cao.

### X-Learner

X-Learner bắt đầu từ hai outcome model, impute effect cho từng arm, học hai effect
model rồi kết hợp theo propensity. Cấu trúc này cho phép kiểm tra nó khi kích thước arm
mất cân bằng; không có định lý rằng nó luôn thắng T-Learner.

### DR-Learner

Với propensity \(e(x)=P(T=1\mid X=x)\), pseudo-outcome dạng AIPW là:

\[
\phi =
\hat\mu_1(x)-\hat\mu_0(x)
+\frac{T(Y-\hat\mu_1(x))}{\hat e(x)}
-\frac{(1-T)(Y-\hat\mu_0(x))}{1-\hat e(x)}
\]

Sau đó regress \(\phi\) lên `X`. "Doubly robust" nói về tính chất của nuisance
estimators dưới điều kiện lý thuyết; nó không có nghĩa model luôn tốt hơn trong finite
sample. Project dùng propensity prior của RCT, tránh học thêm nhiễu không cần thiết.

## 4. Outcome hiếm và under-sampling

Conversion chỉ khoảng 0,29%; metric classification thông thường dễ bị chi phối bởi
negative. Nyberg et al. đề xuất giữ positive và lấy mẫu negative riêng theo treatment arm:

\[
r_t=\frac{1/k-\bar p_t}{1-\bar p_t}
\]

Trong đó `k` là hệ số mong muốn và \(\bar p_t=P(Y=1\mid T=t)\). Với outcome hiếm:

\[
\tilde p_t \approx k p_t,\qquad
\tilde\tau(x)\approx k\tau(x)
\]

Hai biểu thức sau chỉ là xấp xỉ. Xác suất sau case-control sampling không tự còn
calibrated. Project hiện dùng outcome classifier, fixed propensity và chia effect score
cho `k` theo xấp xỉ rare-outcome; đây chưa phải hiệu chỉnh xác suất chính xác. Kết quả
ranking: biến thể X-Learner `k=7` vượt baseline ở test; T-Learner không vượt. Vì Qini
không đổi dưới positive constant rescaling, kết luận ranking không phụ thuộc phép chia
`1/k`; còn calibration phải được xem là giới hạn cần cải thiện.

## 5. Vì sao dùng ba validation seed?

Một split duy nhất có thể cho thứ hạng candidate khác do conversion hiếm. Quy tắc Sprint 1:

- tính Qini trên validation seed 43, 44, 45;
- yêu cầu median improvement tối thiểu 0,005;
- yêu cầu thắng baseline ít nhất 2/3 seed;
- sau đó mới mở test.

Response và S regularized đạt điều kiện trên validation nhưng không duy trì chênh lệch trên test. Đây là
minh họa trực tiếp rằng chọn bằng một bảng validation không bảo đảm generalization.

## 6. Hiểu đúng metric

### Qini

Sắp score giảm dần. Tại mỗi prefix, ước lượng incremental outcome bằng chênh lệch đã
chuẩn hóa theo treatment/control. Qini đo phần gain của ranking so với đường random.
Implementation của project dùng cùng convention với `sklift.metrics.qini_curve`.

Qini cao trả lời "model xếp đúng nhóm có uplift cao không?", không trả lời score có
calibrated như xác suất hay không.

### AUUC

Diện tích dưới uplift curve. Cần ghi rõ convention/normalization vì thư viện có thể
định nghĩa khác nhau.

### EUCE

Chia score thành bin, so predicted effect trung bình với uplift quan sát trong từng bin.
EUCE thấp hơn thường tốt hơn, nhưng rất nhạy với số bin và noise trong arm.

### Policy value

Với top `q%`, project ước lượng:

\[
\widehat{ATE}_{top-q}
=\bar Y_{T=1,top-q}-\bar Y_{T=0,top-q}
\]

và nhân với kích thước segment để biểu diễn incremental conversions chuẩn hóa. Muốn ra
profit phải thêm margin và treatment cost; không được gọi conversion estimate là revenue.
CI policy hiện là normal approximation cho difference-in-proportions sau khi policy đã
freeze, chưa bao gồm model-selection uncertainty.

## 7. Vì sao paired bootstrap?

Hai model được đánh giá trên cùng khách hàng nên điểm số tương quan. Bootstrap độc lập
rồi nhìn hai CI riêng lẻ không trực tiếp kiểm định chênh lệch. Project resample cùng
indices/weights cho hai model, tính:

\[
\Delta_b=Qini_A^{(b)}-Qini_B^{(b)}
\]

rồi lấy percentile CI của \(\Delta\). Code tối ưu bằng multinomial weights sau một lần
sort; unit test kiểm tra kết quả đúng với bootstrap expanded-sample chuẩn.

## 8. Diễn giải kết quả đúng

- Response có Qini cao nhất trong bảng đánh giá, nhưng không phải CATE estimator.
- Chỉ X-Learner cải tiến vượt baseline ở ablation test.
- CI chênh lệch Response–S và Response–X chứa 0: chưa đủ bằng chứng để phân biệt các ranking.
- Top 10% theo Response giữ khoảng 72,7% uplift toàn holdout, không phải 85%.
- Score âm không xác định principal stratum "Sleeping Dogs" của từng người.
- Kết quả là retrospective policy evaluation trên một RCT; chưa phải online lift.

## 9. Nguồn tham khảo

- Criteo, [bộ dữ liệu uplift](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)
- Künzel và cộng sự,
  [*Metalearners for estimating heterogeneous treatment effects*](https://doi.org/10.1073/pnas.1804597116),
  PNAS 2019
- Kennedy,
  [*Towards Optimal Doubly Robust Estimation of Heterogeneous Causal Effects*](https://arxiv.org/abs/2004.14497)
- Nyberg và cộng sự,
  [*Uplift modeling with high class imbalance*](https://proceedings.mlr.press/v157/nyberg21a.html),
  ACML 2021
- Wager & Athey,
  [*Estimation and Inference of Heterogeneous Treatment Effects using Random Forests*](https://doi.org/10.1080/01621459.2017.1319839),
  JASA 2018
- scikit-uplift,
  [quy ước Qini](https://www.uplift-modeling.com/en/v0.3.2/api/metrics/qini_curve.html)
- Efron & Tibshirani,
  [*An Introduction to the Bootstrap*](https://doi.org/10.1201/9780429246593)

## 10. Backlog Sprint 1 và kết cục của nó

Bốn hướng dưới đây được sàng lọc ở cuối Sprint 1. Cả bốn đều đã chạy, nên mục này giữ lại
để đối chiếu ý định ban đầu với kết quả, không phải để mô tả việc còn phải làm.

| Hướng đã đăng ký | Nguồn | Nơi nó được chạy | Kết cục |
|---|---|---|---|
| Calibration sau under-sampling | [Nyberg & Klami 2023](https://doi.org/10.1007/s10618-023-00917-9) | [`02_CALIBRATION_AND_POLICY_VALUE.md`](02_CALIBRATION_AND_POLICY_VALUE.md) | τ-isotonic giảm EUCE nhưng ΔQini có CI chứa 0; giữ làm ablation |
| R-Learner | [Nie & Wager 2021](https://doi.org/10.1093/biomet/asaa076) | [`06_RARE_OUTCOME_LEARNERS.md`](06_RARE_OUTCOME_LEARNERS.md) | Anchored R không qua gate hai fold seed |
| Policy learning theo ngân sách | [Athey & Wager 2021](https://doi.org/10.3982/ECTA15732) | [`03_EVALUATION_PROTOCOL.md`](03_EVALUATION_PROTOCOL.md) | thành metric chính `policy_area_dr` |
| Causal Forest | [Wager & Athey 2018](https://doi.org/10.1080/01621459.2017.1319839) | [`04_CAUSAL_FOREST.md`](04_CAUSAL_FOREST.md) | hai vòng, cả hai hòa với Response theo paired CI |

Deep uplift (TARNet, DragonNet) không được mở: dữ liệu tabular 12 đặc trưng, outcome hiếm,
và trần phân giải của phép đo — đo ở
[`../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md`](../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md)
mục 5 — nằm dưới chênh lệch cần phân biệt, nên thêm kiến trúc mới không đổi được kết luận.
Hướng còn mở ghi ở [`../../planning/README.md`](../../planning/README.md).
