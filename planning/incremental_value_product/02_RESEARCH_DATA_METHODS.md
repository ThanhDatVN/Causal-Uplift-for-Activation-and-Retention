# 02 — Nghiên cứu, Dữ liệu và Phương pháp (Research, Data and Methods)

## Câu hỏi nghiên cứu

> Targeting theo incremental customer value có cho out-of-sample policy value cao hơn targeting
> theo conversion propensity, predicted spend hoặc predicted CLV không?

## Đại lượng mục tiêu (Estimand)

Primary estimand:

```text
iCV_H(x) =
    E[discounted margin trong H ngày | do(T=1), X=x]
  - E[discounted margin trong H ngày | do(T=0), X=x]
  - treatment_cost(x)
```

Trong đó:

- `X` chỉ chứa dữ liệu trước assignment;
- `H` là horizon hữu hạn và phải được ghi rõ;
- `iCV_14d`, `iCV_90d`, `iCV_180d` không đồng nghĩa với lifetime value;
- ngoại suy vượt observed horizon phải gọi là **projected incremental CLV**.

`margin` phải là lợi nhuận đã định nghĩa trước (ví dụ `revenue × gross_margin_rate - variable_cost`),
không tự động suy ra từ `UnitPrice`. Nếu dataset chỉ có doanh thu, outcome và headline phải dùng
**incremental revenue** hoặc **revenue proxy**, không đổi tên thành profit/margin.

### Quy tắc nền tham chiếu (Baseline Heuristic): được phép thử, không được làm headline

```text
conversion_CATE × predicted_CLV
```

Heuristic này ngầm giả định treatment chỉ thay đổi conversion probability và không thay đổi
retention/order value sau conversion. Phải đưa vào ablation như một baseline có giả định mạnh,
không xem là iCLV “đúng”.

## Chiến lược dữ liệu (Dataset Strategy) và phạm vi bằng chứng

| Dataset | Vai trò | Có | Thiếu |
|---|---|---|---|
| Criteo Uplift v2.1 | Causal benchmark quy mô lớn | RCT, binary labels, 14M rows | ID dài hạn, revenue, transactions |
| Online Retail II | Probabilistic CLV benchmark | 2 năm transactions, customer, quantity/price | randomized treatment |
| Hillstrom Email | Real monetary causal benchmark | randomized email, conversion/visit/spend | long horizon |
| Semi-synthetic longitudinal RCT | End-to-end integration | `Y(0)`, `Y(1)`, transactions, known policy value from DGP | evidence từ campaign triển khai |
| X5/MT-LIFT | Stretch | history/multi-treatment/scale | long-horizon monetary outcome đầy đủ |

### Điều kiện sử dụng bắt buộc

- **Criteo:** trang chính thức mô tả benchmark gốc có 25M rows, 11 features và hai label; file
  local `v2.1` trong repo có schema/kích thước khác. Mỗi run phải lưu `data_manifest.json` gồm URL,
  SHA-256, row count, column list và treatment rate; không chuyển số liệu của một version sang version khác.
- **Online Retail II:** gồm 1,067,371 transaction trong 2009–2011, có missing customer ID, cancellations
  (`InvoiceNo` bắt đầu bằng `C`) và nhiều customer wholesale. Cần report sensitivity: (a) net revenue sau
  returns, (b) filter/flag wholesale hợp lý, (c) khách không có repeat purchase. Dataset không có COGS,
  campaign assignment hay treatment cost, nên không thể chứng minh incremental profit/causal CLV.
- **Hillstrom:** 64,000 khách được random vào Mens email, Womens email hoặc control; outcome chỉ được
  theo dõi hai tuần. Mỗi analysis phải chọn trước một contrast nhị phân (ví dụ Mens vs control và loại
  Womens) hoặc dùng policy đa treatment; `spend` là monetary outcome ngắn hạn, không phải CLV.
- **Semi-synthetic:** là testbed kỹ thuật duy nhất có đủ counterfactual dài hạn. Mọi chart/result phải
  mang nhãn `semi-synthetic`, kèm seed và DGP scenario.

Nguồn dataset và trạng thái xác minh chi tiết ở [`08_SOURCE_AUDIT.md`](08_SOURCE_AUDIT.md).

## Dữ kiện benchmark probabilistic đã có

Từ benchmark cũ trên Online Retail II:

- 1,067,371 transaction rows;
- 805,549 rows sau cleaning hiện tại;
- calibration/holdout có 4,977 customers;
- 4,189 returning customers dùng cho CLV;
- BG/NBD + Gamma-Gamma pipeline: khoảng 203.6 giây, 444 MB peak RSS;
- frequency–monetary correlation: 0.133;
- mean 6-month CLV benchmark: 1,026.48 GBP.

Đây là regression targets để kiểm tra implementation mới, không phải final result. Pipeline mới
phải chạy lại, thêm temporal/rolling validation và kiểm tra wholesale.

## Giá trị vòng đời khách hàng xác suất (Probabilistic CLV)

BG/NBD phù hợp với bối cảnh continuous-time, non-contractual repeat purchase ([Fader et al., 2005](https://doi.org/10.1287/mksc.1040.0098);
[derivation note](https://brucehardie.com/notes/039/bgnbd_derivation__2019-11-06.pdf)). Nó mô hình hóa số lần mua và xác suất còn active,
không tự tạo bằng chứng về tác động của campaign. Gamma-Gamma thêm expected monetary value nhưng cần
kiểm tra giả định frequency–monetary independence ([Hardie note](https://www.brucehardie.com/notes/025/gamma_gamma.pdf)); ngưỡng tương quan
trong thư viện chỉ là diagnostic heuristic, không phải định lý. Khách không có repeat purchase phải được
xử lý rõ vì monetary model thường không fit trực tiếp được cho nhóm này.

### P0

- BG/NBD cho purchase frequency và probability alive.
- Gamma-Gamma cho expected average monetary value.
- temporal calibration/holdout.
- rolling-origin validation ở nhiều cutoff/horizon.

### P1

- Bayesian BG/NBD hoặc Pareto/NBD bằng PyMC-Marketing.
- predictive intervals/posterior diagnostics.

### P2

- full Pareto/NBD benchmark;
- time-invariant covariates;
- richer survival/BTYD variants.

Chọn champion bằng out-of-time forecast/calibration, không chỉ in-sample likelihood.

## Giá trị nhân quả (Causal Value)

Mục tiêu policy là welfare/value của quyết định, không phải chỉ CATE ranking. [Causal forest](https://doi.org/10.1080/01621459.2017.1319839)
hỗ trợ ước lượng heterogeneity và inference dưới các giả định đã nêu; [meta-learners](https://doi.org/10.1073/pnas.1804597116)
là candidate linh hoạt nhưng không có nghĩa policy của chúng tối ưu. Dùng [policy learning](https://doi.org/10.3982/ECTA15732)
và [doubly robust evaluation](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/)
để đo giá trị policy trên holdout, đồng thời giữ Qini/AUUC làm diagnostic cho binary uplift.

Model P0:

- response/predicted spend baseline;
- T-Learner;
- DR-Learner;
- Causal Forest hoặc ForestDR challenger.

Outcome:

- binary conversion cho causal regression tests;
- continuous spend/net margin cho monetary uplift;
- discounted cumulative margin ở horizon `H` cho iCV.

Policy layer:

- target nếu expected incremental net value dương và nằm trong budget;
- compare với random, propensity, predicted CLV, conversion CATE;
- đánh giá bằng held-out doubly robust policy value.

## RCT bán tổng hợp theo thời gian (Semi-synthetic Longitudinal RCT)

Generator phải:

1. lấy phân phối pre-treatment RFM/monetary từ Online Retail II;
2. randomized treatment 50/50 hoặc config được;
3. sinh purchase rate, dropout và order value theo latent customer state;
4. cho treatment tác động khác nhau lên purchase rate/dropout/order value;
5. lưu cả `Y(0)`, `Y(1)` để có ground truth;
6. có config/seed và unit tests;
7. tạo scenario:
   - treatment chỉ tăng conversion ngắn hạn;
   - treatment cải thiện retention;
   - treatment tăng conversion nhưng giảm margin;
   - sleeping-dog subgroup;
   - heterogeneous treatment cost.

Semi-synthetic result chỉ chứng minh estimator/policy có thể recover ground truth dưới DGP đã nêu.

## Ràng buộc phương pháp (Method Constraints)

- Không join Criteo/Online Retail ở customer level.
- Không dùng post-treatment variable làm feature.
- Không split transaction ngẫu nhiên theo row.
- Không gọi predicted CLV là incremental CLV.
- Không gọi Hillstrom spend là lifetime value.
- Không báo bốn principal strata như ground truth cá nhân.
- Không tune trên final holdout.
- Không claim production revenue lift từ offline evaluation.
- Không gọi `UnitPrice × Quantity` là margin nếu chưa có COGS/margin-rate đã versioned.
- Không coi diagnostic của library là validation: mọi model phải qua temporal holdout và cohort calibration.
- Không dùng estimator DR như giấy phép bỏ qua positivity/overlap, outcome-model quality hoặc train/test separation.
