# Hợp đồng quyết định (Decision Contract)

**Cập nhật 05/08/2026.** Hợp đồng vẫn có hiệu lực nguyên văn. Sprint 3 chạy lại quyết
định chọn model bằng một protocol chặt hơn và giữ nguyên champion; xem
`report/SPRINT_3_FINAL_REPORT.md`. Hai điểm cần đọc kèm:

1. Metric chính đã đổi từ Qini sang `policy_area_dr` (trung bình DR gross policy value
   trên dải budget 1–30%). Mục 2 dưới đây mô tả lý do chọn Response theo Qini
   validation ở Sprint 2; lý do đó vẫn đúng cho lịch sử, nhưng bằng chứng hiện hành là
   `policy_area_dr` trên development OOF hai fold seed và trên retrospective
   confirmation.
2. Trên confirmation Sprint 3, ba model có Qini cao hơn Response nhưng không model nào
   có paired CI của `policy_area_dr` tách khỏi 0. Quy tắc "giữ champion khi CI chứa 0"
   ở mục 2 chính là quy tắc đã được áp dụng.

## 1. Quyết định sản phẩm

**Câu hỏi:** với ngân sách chỉ cho phép tiếp cận một phần khách hàng, nên target top bao
nhiêu phần trăm để tối đa hóa conversion tăng thêm sau chi phí?

**Đơn vị quyết định:** một khách hàng trong population có phân phối tương tự Criteo
confirmation set.

**Treatment:** can thiệp marketing được gán ngẫu nhiên trong Criteo. Dự án không diễn giải
`exposure` là treatment mới và không dùng `visit`/`exposure` làm feature.

**Outcome chính:** `conversion` nhị phân.

## 2. Policy được phát hành

`Response top-k`: xếp khách hàng theo xác suất conversion dự báo, rồi target đúng top
`k%` theo budget.

Response được chọn vì:

1. model selection chỉ dùng validation mới;
2. Response có Qini validation cao nhất trong ba candidate có thể triển khai;
3. trên confirmation độc lập, X‑Renormalized − Response = `0,008768` Qini, nhưng paired
   bootstrap 95% CI `[-0,018626; 0,038772]`, chưa tách khỏi 0;
4. giữ model có ít thành phần hơn khi paired CI chưa cho thấy challenger cải thiện.

Response là **ranking policy score**, không phải calibrated CATE. Dashboard không dùng
score Response để tuyên bố hiệu ứng cá nhân.

## 3. Giá trị policy

Với policy nhị phân \(\pi(X)\), propensity thí nghiệm \(e=P(T=1)\), outcome model
\(\mu_t(X)\):

\[
\phi_{DR} =
\mu_1(X)-\mu_0(X)
+ \frac{T(Y-\mu_1(X))}{e}
- \frac{(1-T)(Y-\mu_0(X))}{1-e}.
\]

Gross incremental conversions trên mỗi khách hàng đủ điều kiện:

\[
\widehat V_{\text{gross}}(\pi)
= \frac{1}{n}\sum_i \pi(X_i)\phi_{DR,i}.
\]

Scenario net value:

\[
\widehat V_{\text{net}}
= v\widehat V_{\text{gross}}
- c\frac{1}{n}\sum_i\pi(X_i),
\]

trong đó `v` là giá trị giả định trên một conversion và `c` là chi phí giả định trên
một contact. Hai input phải cùng đơn vị.

## 4. Assumption và exclusion

- Criteo không có revenue, margin hoặc treatment cost: không số nào được gọi là actual
  profit/revenue.
- Đây là offline policy evaluation trên RCT, chưa phải production A/B result.
- Không quan sát principal stratum cá nhân; không gán nhãn Persuadable/Sure Thing/Lost
  Cause/Sleeping Dog cho từng người.
- Không extrapolate ra population có phân phối khác mà không monitoring/revalidation.
- Không dùng confirmation để tune model hoặc chọn hyperparameter.

## 5. Guardrail sản phẩm

- UI luôn hiển thị run ID, split, confirmation size và trạng thái Causal Forest.
- API chỉ nhận budget trong **dải** bằng chứng đã đánh giá `[1%; 30%]`, cộng đúng `0%` cho
  trường hợp treat-none. Giá trị nằm **bên trong** dải được nội suy tuyến tính trên budget
  curve — ví dụ `7,5%` hợp lệ dù không phải một điểm của lưới `{1, 2, 5, 10, 15, 20, 25, 30}%`.
  Giá trị **ngoài** dải bị từ chối với HTTP 422; không ngoại suy.
- Nếu `contact_cost / conversion_value > 0,001`, UI cảnh báo ngoài sensitivity grid đã
  kiểm tra.
- Treat-none phải trả về target = 0 và value = 0.
- Batch scoring target đúng `floor(budget × n)` dòng trong chính batch được tải lên;
  percentile tham chiếu population chỉ dùng để hiển thị, không thay thế quota top-k.
- CSV export luôn có `run_id`, assumption fields và
  `monetary_outcome_available=false`.

Nguồn cho policy evaluation: Dudík, Langford & Li,
[Doubly Robust Policy Evaluation and Learning](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/);
Athey & Wager,
[Policy Learning with Observational Data](https://doi.org/10.3982/ECTA15732).
