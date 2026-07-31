# Hướng dẫn lý thuyết và phương pháp Sprint 1

Tài liệu này giúp đọc code và giải thích dự án bằng tiếng Việt. Kết quả số chính thức
nằm ở `report/SPRINT_1_FINAL_REPORT.md`.

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

## 3. Năm mô hình đang dùng

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

Sau đó regress \(\phi\) lên `X`. “Doubly robust” nói về tính chất của nuisance
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

Qini cao trả lời “model xếp đúng nhóm có uplift cao không?”, không trả lời score có
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
- Score âm không xác định principal stratum “Sleeping Dogs” của từng người.
- Kết quả là retrospective policy evaluation trên một RCT; chưa phải online lift.

## 9. Câu hỏi phải trả lời được khi phỏng vấn

1. Tại sao propensity model không đủ để target campaign?
2. Vì sao không thể đo RMSE của CATE cá nhân trên dữ liệu quan sát?
3. `visit` và `exposure` gây leakage ra sao?
4. S/T/X/DR khác nhau ở nuisance model và pseudo-outcome nào?
5. “Doubly robust” bảo đảm điều gì dưới các giả định của estimator?
6. Vì sao under-sampling làm sai calibration nếu không correction?
7. Vì sao phải dùng paired bootstrap?
8. Response thắng Qini có mâu thuẫn với mục tiêu causal không?
9. Policy top 10% được ước lượng thế nào và cần giả định gì?
10. Điều gì cần thêm để biến uplift thành incremental profit?

## 10. Nguồn phải đọc

- Criteo dataset: https://ailab.criteo.com/criteo-uplift-prediction-dataset/
- Künzel et al., meta-learners: https://doi.org/10.1073/pnas.1804597116
- Kennedy, DR-Learner: https://arxiv.org/abs/2004.14497
- Nyberg et al., rare outcomes: https://proceedings.mlr.press/v157/nyberg21a.html
- Wager & Athey, causal forests:
  https://doi.org/10.1080/01621459.2017.1319839
- scikit-uplift, Qini convention:
  https://www.uplift-modeling.com/en/v0.3.2/api/metrics/qini_curve.html
- Efron & Tibshirani, bootstrap:
  https://doi.org/10.1201/9780429246593

## 11. Research backlog đã sàng lọc

Không thêm model chỉ để tăng số lượng. Thứ tự thử trong Sprint 2:

1. **Calibration sau under-sampling:** đọc bản mở rộng của Nyberg & Klami (2023), triển
   khai inverse probability mapping/isotonic calibration đúng protocol rồi so EUCE và
   policy value. Đây là ưu tiên cao nhất vì candidate X hiện chỉ rescale `1/k`.
   Nguồn: https://doi.org/10.1007/s10618-023-00917-9
2. **R-Learner:** challenger orthogonalized phù hợp để kiểm tra xem residualization có
   ổn định hơn meta-learners khi outcome signal lớn hơn treatment signal hay không. Chỉ
   mở test mới sau khi khóa cấu hình trên validation.
   Nguồn: https://doi.org/10.1093/biomet/asaa076
3. **Policy learning theo budget/cost:** sau khi CATE/ranking ổn định, tối ưu decision
   rule trực tiếp dưới constraint thay vì mặc định chọn top-q.
   Nguồn: https://doi.org/10.3982/ECTA15732
4. **Causal Forest:** chạy learning curve theo runbook, không ưu tiên hơn calibration và
   policy chỉ vì model phức tạp.

Deep uplift/TARNet/DragonNet chưa ưu tiên trong sáu tuần: dữ liệu tabular 12 feature,
outcome hiếm và mục tiêu portfolio cần evaluation/policy/deployment chắc hơn là thêm
neural architecture tốn compute nhưng chưa có hypothesis cụ thể.
