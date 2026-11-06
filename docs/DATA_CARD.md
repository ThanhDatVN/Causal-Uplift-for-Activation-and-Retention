# IBM Telco Customer Churn — Data Card

> **Current English use note (29 September 2026):** This static sample has no customer-level treatment assignment, delivery logs, actual offer costs, or validated 30-day prediction clock. The local planner accepts approved CSV snapshots and ignores outcome/extra columns before scoring. Its replayable evidence JSON includes every input row and should be handled as customer data if real records are used. The public portfolio demo uses fictional records; the application has no authentication and is intended for localhost. See the [English release guide](PORTFOLIO_RELEASE_2026_EN.md).

## Dataset được chọn

Sử dụng `Telco-Customer-Churn.csv` bản 21 cột trong repository IBM
`telco-customer-churn-on-icp4d`. IBM mô tả sample này trong một code pattern đi từ load/visualize
đến train và deploy; repository đã được archive ngày 22-07-2024.[^1] OpenML dataset 42178 là một
mirror có target mặc định `Churn`, ignore attribute `customerID` và mô tả target là khách hàng rời
đi trong tháng vừa qua.[^2]

| Thuộc tính | Giá trị đã kiểm chứng |
|---|---|
| Số dòng | 7.043 |
| Số cột raw | 21 = 19 candidate features + 1 ID + 1 target |
| Target | `Churn` ∈ {`Yes`, `No`} |
| Churn positive | 1.869 / 7.043 = 26,54% |
| Unique key | `customerID`, 7.043 giá trị unique |
| File SHA-256 | `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91` |
| Missing ẩn | 11 chuỗi trống ở `TotalCharges`; tất cả có `tenure=0` |
| Duplicates | 0 ID trùng, 0 dòng trùng |

## Vì sao chọn bản 21 cột

| Candidate | Quyết định | Lý do |
|---|---|---|
| IBM 21 cột | **Primary dataset** | Nhỏ, dễ audit, schema gần input vận hành và có nguồn IBM trực tiếp. |
| IBM Cognos 33 cột | Không train | Có `Churn Label`, `Churn Value`, `Churn Score`, `Churn Reason`; target hoặc kết quả sau churn gây leakage trực tiếp. `CLTV` cũng là output công thức/model không rõ thời điểm. |
| OpenML 42178 | Mirror/metadata check | Thuận tiện cho interoperability nhưng không thay provenance từ IBM. |
| Orange KDD Cup 2009 | Stretch dataset riêng | Benchmark có tổ chức, 50.000 train + 50.000 test và 230/15.000 biến, nhưng population, target rate và schema khác; không so score với IBM.[^3] |

Không dùng synthetic oversampling để “nâng” dataset lên 100k: resampling không tạo thêm thông tin
độc lập và có thể khiến câu chuyện scale/business bị hiểu sai.

## Nguồn và license status

- Nguồn tải: file raw trong repository IBM.[^4]
- Script tái lập: `scripts/fetch_data.ps1`; download phải khớp checksum trước khi phân tích.
- Repository IBM dùng Apache License 2.0.[^5]
- OpenML ghi license là `Public`, nhưng đó là metadata do contributor của mirror khai báo, không
  phải một data license chi tiết từ người tạo sample.[^2]
- Repository IBM không tách một tuyên bố license riêng cho CSV và không công bố collection process.
  Do đó trạng thái được ghi là **repository-level Apache-2.0; dataset-level provenance/license chưa
  hoàn toàn rõ**. Mặc định không commit/redistribute raw CSV; người dùng tự fetch từ IBM. Đây không
  phải tư vấn pháp lý.

## Schema và vai trò tại prediction time

| Cột | Kiểu mong đợi | Role | Rule / lưu ý |
|---|---|---|---|
| `customerID` | string | Join/audit only | Unique, non-null; tuyệt đối không train. |
| `gender` | category | Audit + ablation | Candidate sensitive attribute; không dùng làm reason code. |
| `SeniorCitizen` | binary int | Audit + ablation | Chỉ nhận 0/1; báo slice metrics. |
| `Partner`, `Dependents` | category | Candidate | Proxy demographic; cần sensitivity review. |
| `tenure` | int | Candidate | 0–72 trong sample; cần xác nhận tính tại snapshot trước outcome. |
| `PhoneService` | category | Candidate | `No` ⇒ `MultipleLines=No phone service`. |
| `MultipleLines` | category | Candidate | Structural category, không biến thành generic missing. |
| `InternetService` | category | Candidate | `No` kéo theo six add-ons = `No internet service`. |
| Six internet add-ons | category | Candidate | `OnlineSecurity` … `StreamingMovies`; structural categories giữ nguyên. |
| `Contract` | category | Candidate | Cần chứng minh có sẵn trước outcome window. |
| `PaperlessBilling` | category | Candidate | Yes/No. |
| `PaymentMethod` | category | Candidate | Bốn level trong sample. |
| `MonthlyCharges` | float | Candidate | Sample range 18,25–118,75; currency không được công bố. |
| `TotalCharges` | float-like string | Candidate | Parse numeric; đúng 11 blank với `tenure=0` có thể fill 0 sau validation. Missing khác phải fail. |
| `Churn` | category | Label only | Map Yes→1, No→0; không bao giờ đi vào request scoring. |

“Six internet add-ons” gồm `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport`,
`StreamingTV`, `StreamingMovies`.

## Prediction point và temporal leakage

Product contract mô phỏng là: tại cuối snapshot ngày T, dùng dữ liệu chỉ đến T để dự đoán churn
trong `(T, T+30 ngày]`. Tuy nhiên sample không chứa `snapshot_at`, `event_at` hoặc data lineage;
OpenML chỉ nói khách đã rời trong tháng vừa qua.[^2] Không thể chứng minh các feature được đo trước
label window. Vì vậy:

- random stratified split chỉ đo khả năng nội suy trên sample;
- không được gọi kết quả là out-of-time/generalization-to-production;
- khi chuyển sang dữ liệu thật, bắt buộc point-in-time join và out-of-time test;
- mọi feature phải có `available_at` và assertion `available_at <= snapshot_at`.

Scikit-learn định nghĩa leakage là sử dụng thông tin không có tại prediction time và khuyến nghị
split trước mọi `fit`; pipeline giúp giữ preprocessing trong từng training fold.[^6]

## Cleaning policy đã khóa

1. Fail nếu schema thiếu/thừa cột hoặc target ngoài `{Yes, No}`.
2. Fail nếu `customerID` null/trùng.
3. Strip rồi parse `TotalCharges` với coercion chỉ để phát hiện lỗi.
4. Nếu `TotalCharges` missing và `tenure==0`, fill 0 bên trong pipeline; nếu missing ở trường hợp
   khác, fail để điều tra.
5. Giữ các label cấu trúc `No phone service` và `No internet service`; không đổi thành `No`/null.
6. Không fit encoder/imputer hoặc tính threshold trên toàn dataset trước split.
7. Không drop 11 khách mới chỉ để làm sạch đẹp.

## Representativeness, privacy và prohibited uses

Không có mô tả sampling frame, geography, calendar period, channel, plan catalog, acquisition
source hoặc collection process. Sample là dữ liệu minh họa/fictitious, không đại diện cho một telco
cụ thể. `customerID` là identifier nhưng sample không có tên/email; trong hệ thật vẫn phải coi ID và
billing fields là dữ liệu hạn chế truy cập.

Không dùng dataset/model này để:

- ước lượng churn/revenue thực của doanh nghiệp;
- đưa ưu đãi thật hoặc tự động từ chối dịch vụ;
- kết luận causal như “fiber optic gây churn”;
- kết luận fairness cho population thật;
- tuyên bố retention uplift hay ROI thật khi chưa có randomized treatment/control outcomes.

## Quality gate hiện tại

EDA đã pass: 7.043 rows, đúng checksum/schema, 0 duplicate, 11 structural blanks, range hợp lệ và 0
mâu thuẫn phone/internet service. Báo cáo đầy đủ nằm ở `reports/eda/EDA_REPORT.md`.

## Sources

[^1]: IBM, “[Predict Customer Churn using Watson Machine Learning and Jupyter Notebooks on Cloud Pak for Data](https://github.com/IBM/telco-customer-churn-on-icp4d),” archived 22 July 2024.
[^2]: OpenML, “[telco-customer-churn, data set 42178](https://www.openml.org/search?type=data&id=42178),” uploaded 15 October 2019. API metadata: `https://www.openml.org/api/v1/json/data/42178`.
[^3]: ACM SIGKDD, “[KDD Cup 2009: Customer Relationship Prediction — Data](https://www.kdd.org/kdd-cup/view/kdd-cup-2009/Data).”
[^4]: IBM, “[Telco-Customer-Churn.csv](https://github.com/IBM/telco-customer-churn-on-icp4d/blob/master/data/Telco-Customer-Churn.csv).”
[^5]: IBM, “[telco-customer-churn-on-icp4d LICENSE](https://github.com/IBM/telco-customer-churn-on-icp4d/blob/master/LICENSE),” Apache License 2.0.
[^6]: scikit-learn, “[Common pitfalls and recommended practices: Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).”
