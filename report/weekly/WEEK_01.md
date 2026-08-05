# Tuần 1 — Nền tảng: dữ liệu, chẩn đoán randomization, baseline và bộ metric

**Sprint:** 1
**Trọng tâm theo kế hoạch:** EDA, randomization diagnostic, 5 baseline, metric test
**Deliverable đã chốt:** `report/archive/week-01/`, benchmark, bảng kết quả
**Trạng thái:** Đạt

---

## 1. Kế hoạch tuần

Dựng môi trường tái lập được, kiểm tra schema và profile dữ liệu Criteo, chạy chẩn đoán
randomization, và xây bộ metric Qini/AUUC/bootstrap có unit test đối chiếu với thư viện
tham chiếu.

Nguyên tắc đặt ra ngay từ đầu: **không tin công thức tự nhớ**. Mọi metric phải hoặc có
nguồn gốc, hoặc được đối chiếu số học với một implementation công khai và có test.

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Môi trường | Python 3.12.10, `.venv` riêng, `econml==0.16.0` pin cứng |
| Data contract | `src/data.py::validate_criteo_schema` |
| EDA | `notebooks/01_eda_criteo.ipynb`, `output/eda_summary.csv` |
| Chẩn đoán cân bằng | SMD từng feature, KS test, propensity AUC |
| Baseline | Response, S-, T-, X-, DR-Learner |
| Metric | Qini, AUUC, bootstrap CI, transformed outcome |
| Test | 18 test pass ở mốc cuối tuần |

## 3. Cách hoạt động

### 3.1 Data contract — vì sao cần và nó kiểm gì

`validate_criteo_schema` chạy trước mọi thứ khác và trả về một dict, không phải chỉ
true/false. Nó kiểm:

- đủ 16 cột bắt buộc, không thừa cột lạ;
- `treatment`, `conversion`, `visit`, `exposure` chỉ nhận giá trị trong `{0, 1}`;
- 12 feature `f0..f11` hữu hạn, không NaN/inf;
- tổng số ô thiếu bằng 0.

Điểm quan trọng ghi ngay trong docstring: **hàm này không khẳng định dữ liệu đã được
randomized.** Nó chỉ kiểm schema và kiểu. Bằng chứng randomization đến từ mô tả nguồn của
Criteo, không đến từ code.

Kết quả: 13.979.592 dòng × 16 cột, 0 ô thiếu, mọi biến nhị phân hợp lệ.

### 3.2 Lấy mẫu phân tầng — vì sao phải phân tầng theo **cặp**

```python
for _, g in df.groupby(["treatment", "conversion"], sort=False):
    n = max(1, int(round(len(g) * frac)))
    idx = rng.choice(g.index.values, size=min(n, len(g)), replace=False)
```

Phân tầng theo `(treatment, conversion)` chứ không chỉ theo `treatment`. Lý do cụ thể:
conversion ở nhánh control chỉ có 4.063 dòng trên toàn bộ dataset. Nếu chỉ phân tầng theo
treatment, một mẫu nhỏ có thể tình cờ không có conversion nào ở control, và khi đó đường
Qini "perfect" có diện tích bằng 0 → `qini_score` trả NaN.

Đây không phải lo xa: ở smoke 1% hiện tượng này xuất hiện thật.

### 3.3 Chẩn đoán cân bằng — ba công cụ, ba vai trò khác nhau

| Công cụ | Đo gì | Không nói được gì |
|---|---|---|
| SMD từng feature | `(mean_t − mean_c) / sqrt((var_t + var_c)/2)` | Không phải test; giá trị nhỏ không chứng minh randomization |
| KS test | Khác biệt phân phối | Với 14 triệu dòng, sai khác cực nhỏ vẫn cho p-value nhỏ |
| Propensity AUC | Dự đoán treatment từ `X` trên holdout | AUC ≈ 0,5 là dấu hiệu cân bằng, **không** là bằng chứng randomization |

Quyết định thiết kế: `propensity_auc` dùng **holdout** chứ không chấm in-sample, để tránh
bias lạc quan. Kết quả 0,5098 — gần ngưỡng ngẫu nhiên.

Không dùng p-value làm tiêu chí chính vì với cỡ mẫu này p-value gần như luôn nhỏ.

### 3.4 Bộ metric — phần được kiểm chứng kỹ nhất

**Qini curve theo threshold:**

```
Qini(t) = Y1(t) − Y0(t) · N1(t)/N0(t)
```

Nguồn khái niệm là Radcliffe & Surry (2011) mục 4.2, nhưng paper **không đưa công thức
per-threshold** mà dẫn ngược về Radcliffe (2007), bản mà repo không tiếp cận được. Vì vậy
hành vi per-threshold được lấy theo `sklift.metrics.qini_curve` sau khi **đọc mã nguồn thư
viện**, và được đối chiếu số học trong test với sai lệch dưới `1e-6`.

Điều này được ghi thẳng trong docstring của `_qini_curve_raw` chứ không giấu đi. Đây là ví
dụ của quy tắc "mức B — implementation-verified": dùng được, nhưng phải ghi rõ biến thể.

**Xử lý tie:** các điểm có cùng score được gộp thành một threshold, khớp hành vi `sklift`.

**Qini score** là AUC(actual) − AUC(random), chuẩn hóa bởi AUC(perfect) − AUC(random),
với `negative_effect=True`. Docstring ghi rõ đây là **một trong nhiều biến thể** của "qini
coefficient" trong tài liệu, và chọn nó vì đó là hàm cross-check bắt buộc, không phải vì
nó "đúng hơn".

**Transformed outcome:**

```
R = Y·(T − p) / (p(1 − p)),    E[R | X] = tau(X)
```

Dùng làm metric phụ vì variance cao. Không dùng một mình để chọn model.

### 3.5 Bootstrap CI — và một cải tiến hiệu năng quan trọng

Percentile bootstrap theo Efron & Tibshirani. Điểm kỹ thuật đáng chú ý: thay vì resample
rồi sort lại mỗi vòng, code **sort một lần** và chỉ cập nhật cumulative weighted counts:

```python
weight = np.bincount(idx, minlength=n).astype("float64")
```

Một bootstrap sample tương đương gán cho mỗi quan sát số lần nó được rút. Vì score không
đổi giữa các resample, thứ tự sort cũng không đổi. Cải tiến này biến bootstrap từ
`O(B·n log n)` thành `O(B·n)`.

Xử lý NaN: nếu một resample cho Qini không xác định, nó bị loại và hàm **cảnh báo** số
resample bị bỏ, không im lặng.

### 3.6 Năm baseline

| Model | Cơ chế | Ghi chú thiết kế |
|---|---|---|
| Response | LightGBM classifier `P(Y=1|X)`, bỏ qua treatment | Không phải CATE estimator |
| S-Learner | Một model `Y ~ f(X, T)` | Regularization có thể làm model ít dùng `T` |
| T-Learner | Hai model riêng, lấy hiệu | Yếu khi một arm ít dữ liệu |
| X-Learner | Impute counterfactual rồi fit lại | Thiết kế cho arm lệch |
| DR-Learner | Pseudo-outcome doubly robust | Propensity dùng `DummyClassifier(strategy="prior")` |

Một chi tiết dễ sai đã được xử lý: EconML gọi `predict` của outcome model. Truyền thẳng
`LGBMClassifier` sẽ trả **nhãn cứng 0/1** thay vì xác suất, làm hỏng phép trừ hai response
surface. Vì vậy có `BinaryProbabilityRegressor` — adapter giữ API scikit-learn nhưng trả
`predict_proba[:, 1]`.

## 4. Kết quả

Holdout 50%, `test_size=0.30`, `seed=42`, test 2.096.940 dòng, 500 bootstrap:

| Model | Qini | CI 95% riêng lẻ | AUUC |
|---|---:|---:|---:|
| Response | 0,1793 | [0,1428; 0,2180] | 0,00581 |
| S-Learner | 0,1768 | [0,1413; 0,2179] | 0,00573 |
| DR-Learner | 0,1540 | [0,1179; 0,1904] | 0,00497 |
| T-Learner | 0,1420 | [0,1068; 0,1755] | 0,00459 |
| X-Learner | 0,1414 | [0,1077; 0,1769] | 0,00457 |

Thời gian fit: Response 15,6s · S 15,7s · T 14,7s · X 45,2s · DR 70,1s. Bootstrap là phần
nặng nhất, khoảng 40 phút cho toàn bộ.

## 5. Quyết định và lý do

1. **Không dùng CI riêng lẻ để so sánh model.** CI của cả năm model đều không chứa 0,
   nhưng đó là CI của từng Qini, không phải của chênh lệch. Chúng chồng lấn gần hoàn toàn.
   Quyết định: từ tuần 2 báo cáo CI của `ΔQini` với cùng bộ resample.
2. **Response đứng đầu nhưng không được diễn giải là "causal learner kém".** Nó chỉ cho
   thấy các cấu hình đã chạy chưa vượt Response trên metric ranking và split đang dùng.
3. **Không dùng `visit`/`exposure` làm feature.** Cả hai xảy ra sau khi treatment được gán.

## 6. Chưa xong và rủi ro

- Causal Forest chưa chạy; chỉ có benchmark tài nguyên.
- `paired_bootstrap_compare()` hiện trả một heuristic tail, **không phải p-value chuẩn**.
  Đã ghi nhận là cần thay bằng CI của chênh lệch.
- Tuning chưa chạy; năm model đang ở cấu hình mặc định.

## 7. Chuẩn bị cho tuần sau

Tuần 2 cần: đóng băng split và seed, chạy tuning có giới hạn trên validation, chấm final
test đúng một lần, và ra quyết định về Causal Forest bằng resource gate thay vì bằng mong
muốn.

## 8. Câu hỏi cần mentor phản biện

Response có Qini cao nhất. Metric ranking như Qini có phù hợp với mục tiêu quyết định
(chọn top-k% để target) không, hay cần một metric gắn trực tiếp với ngân sách?

*Câu hỏi này về sau dẫn thẳng tới việc đổi metric chính ở Tuần 5.*
