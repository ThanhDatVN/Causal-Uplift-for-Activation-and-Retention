# EDA Report — IBM Telco Customer Churn

> Trạng thái: hoàn tất EDA mô tả; chưa train, tune hay chọn mô hình. Các liên hệ dưới đây không phải quan hệ nhân quả.

## Executive summary

- Dataset có **7,043 khách hàng**, **1,869 churners** (26.5%). Vì vậy accuracy của luật luôn đoán `No` đã là 73.5%; accuracy không được dùng làm metric chính.
- Có **11** chuỗi trống trong `TotalCharges`; tất cả đều có `tenure = 0`. Đây là missing có cấu trúc. Giữ các dòng này, kiểm tra điều kiện rồi gán 0 trong pipeline là hợp lý hơn xóa khách hàng mới.
- Có **0** `customerID` trùng và **0** dòng trùng hoàn toàn.
- Dataset không có timestamp/snapshot date/campaign treatment. Vì vậy không thể kiểm chứng temporal split, 30-day prediction horizon hay tác động thực của ưu đãi; business impact chỉ là scenario analysis.

## Những segment có churn rate quan sát cao

| Feature | Level | n | Churn rate | 95% Wilson CI |
|---|---|---:|---:|---:|
| PaymentMethod | Electronic check | 2,365 | 45.3% | 43.3%–47.3% |
| Contract | Month-to-month | 3,875 | 42.7% | 41.2%–44.3% |
| InternetService | Fiber optic | 3,096 | 41.9% | 40.2%–43.6% |
| OnlineSecurity | No | 3,498 | 41.8% | 40.1%–43.4% |
| SeniorCitizen | 1 | 1,142 | 41.7% | 38.9%–44.6% |

Cramér's V chỉ dùng để sàng lọc sức liên hệ đơn biến. File CSV có cả p-value và Benjamini–Hochberg q-value qua 16 kiểm định; significance vẫn không chứng minh feature gây churn và không thay thế đánh giá out-of-sample.

| Feature | Cramér's V |
|---|---:|
| Contract | 0.410 |
| OnlineSecurity | 0.347 |
| TechSupport | 0.343 |
| InternetService | 0.322 |
| PaymentMethod | 0.303 |

## Numeric profile

| Feature | Non-churn mean | Churn mean | Standardized difference |
|---|---:|---:|---:|
| tenure | 37.57 | 17.98 | -0.893 |
| MonthlyCharges | 61.27 | 74.44 | 0.470 |
| TotalCharges | 2555.34 | 1531.80 | -0.482 |

## Diễn giải có giới hạn

- Trong cohort tenure 0–6 tháng + month-to-month, churn rate quan sát là 55.2% (n=1,413).
- `Contract`, `tenure`, `InternetService` và `PaymentMethod` là các giả thuyết ưu tiên cho mô hình/segment analysis; chưa được biến thành khuyến nghị can thiệp.
- `gender` và `SeniorCitizen` phải được dùng để audit slice. Trước production cần thử ablation không dùng thuộc tính nhạy cảm và không xuất chúng thành reason code.
- Tương quan giữa phí, tenure và churn không cho phép kết luận giảm giá sẽ giữ chân. Cần randomized treatment/control data để ước lượng uplift.

## Quyết định cho phase mô hình

1. Loại `customerID` khỏi features nhưng giữ làm join key/audit key.
2. Parse `TotalCharges`; với đúng điều kiện `tenure == 0` và missing, gán 0 trong transformer. Mọi missing khác phải fail validation.
3. Không resample trước split/CV. Mọi encoder/imputer/calibrator phải fit chỉ trên training fold.
4. Dùng stratified split vì sample không có thời gian, đồng thời ghi rõ đây là proxy kém hơn out-of-time validation.
5. Primary metric là Average Precision; báo thêm ROC-AUC, Brier/log loss, calibration curve và Recall/Precision/Lift@budget.

## Artifacts

- `summary.json`: machine-readable quality/prevalence summary.
- `schema_profile.csv`: dtype, missing, cardinality, range và sample values từng cột.
- `categorical_churn_rates.csv`: counts, rates, Wilson intervals, chi-square và Cramér's V.
- `numeric_by_churn.csv`: numeric profiles và standardized mean difference.
- `tenure_contract_cohorts.csv`: cohort table phục vụ heatmap.
- `figures/`: ba biểu đồ PNG tái lập được.
