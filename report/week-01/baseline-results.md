# Sprint 2 — So sánh 5 model baseline trên holdout 50%

> **Historical / superseded:** đây là lần chạy baseline cũ. Không dùng số liệu trong
> file này để báo cáo. Xem [`../SPRINT_1_FINAL_REPORT.md`](../SPRINT_1_FINAL_REPORT.md)
> cho release 29/07/2026 với split, ablation và paired bootstrap đã chuẩn hóa.

**Trạng thái:** Năm model local đã chạy. Causal Forest chưa có cloud result.

Holdout chung: sample **50%**, `test_size=0.30`, `seed=42`, stratify `(treatment, conversion)`.
Tập test **2.096.940 dòng** (~6.100 conversion). Bootstrap CI 500 resample. Sinh bởi
`scripts/train_baselines.py`; số liệu ở `output/qini_comparison.csv`.

## 1. Ma trận so sánh (Qini/AUUC + bootstrap CI)

| Model | Qini | CI 95% của Qini riêng lẻ | AUUC |
|---|---|---|---|
| **Response** (không dùng treatment) | **0.1793** | [0.1428, 0.2180] | 0.00581 |
| **S-Learner** | 0.1768 | [0.1413, 0.2179] | 0.00573 |
| DR-Learner | 0.1540 | [0.1179, 0.1904] | 0.00497 |
| T-Learner | 0.1420 | [0.1068, 0.1755] | 0.00459 |
| X-Learner | 0.1414 | [0.1077, 0.1769] | 0.00457 |

Thời gian fit (local, 50%): Response 15.6s · S-Learner 15.7s · T-Learner 14.7s · X-Learner 45.2s · DR-Learner 70.1s. Bootstrap là phần nặng nhất (~40 phút cho toàn bộ).

## 2. Ba kết quả chính

**(a) CI Qini riêng lẻ của cả năm model không chứa 0 trên holdout 50%.** Đây không phải
CI của chênh lệch giữa hai model và không đủ để kết luận model nào hơn model nào. Ở smoke
1% với khoảng 120 conversion, chỉ CI của X-Learner không chứa 0.

**(b) Response có Qini point estimate cao nhất trong năm model ở lần chạy này.** Tail
heuristic từng được ghi như `p-value` đã bị loại khỏi báo cáo vì không có null-centering/
inversion protocol đủ căn cứ. Release hiện hành dùng paired bootstrap CI của `ΔQini`.
T/X-Learner lấy hiệu hai outcome model nên có thể nhạy với phương sai khi conversion rate
chỉ 0,29%; đây là giả thuyết cần kiểm tra bằng ablation, không phải nguyên nhân đã được
chứng minh. Qini implementation đã được đối chiếu số học với `sklift`.

**(c) Trên lần chạy lịch sử này, top 10% theo Response tương ứng 1.740/2.051
incremental conversions ước tính.** Con số này đã bị supersede; không dùng trong release
hiện hành.

## 3. Phân khúc khách hàng (theo dấu CATE)

| Model | Predicted positive effect | Near-zero score | Predicted negative effect |
|---|---|---|---|
| S-Learner | 53.99% | 45.64% | 0.37% |
| DR-Learner | 34.11% | 65.29% | 0.60% |
| T-Learner | 32.68% | 63.38% | **3.94%** |
| X-Learner | 28.02% | 71.15% | 0.83% |

Trong các CATE model, **S-Learner có Qini cao nhất nhưng tỷ lệ score âm gần 0**.
**T-Learner gán score âm cho 3,94% mẫu**, cao nhất trong bảng. Response không có trong bảng
vì score của nó là xác suất response, không phải ước lượng dấu CATE. Các tỷ lệ này không xác
định principal strata ở cấp cá nhân.

## 4. Diễn giải theo mục tiêu sử dụng

Qini đo chất lượng ranking theo incremental conversion. Response score không ước lượng CATE
và không cung cấp dấu treatment effect. Vì vậy:
- Với **xếp hạng để nhắm ngân sách**: Response/S-Learner có Qini cao nhất trong bảng.
- Với **phân tích score CATE âm**: cần CATE estimator; T-Learner cho tỷ lệ score âm cao nhất
  trong các model đã chạy.
- Qini không đo calibration CATE hoặc principal-stratum membership; cần đọc cùng
  calibration diagnostic và policy value.

## 5. Giới hạn hiện tại
- Conversion rate là 0,29%; số positive event thấp làm tăng sampling uncertainty.
- Meta-learner dùng cấu hình cố định `LGBM(n_estimators=200, max_depth=5)` và chưa có
  rare-outcome correction trong lần chạy này.
- Causal Forest chưa có cloud artifact và không xuất hiện trong bảng.

Hướng cải tiến: xem [`planning/CAUSAL_UPLIFT_PLAN.md`](../../planning/CAUSAL_UPLIFT_PLAN.md)
mục “Hướng cải tiến model”.

## 6. Output đã sinh
- Ba artifact root cũ (`qini_comparison.csv`, `qini_curve.png`, `segments_baseline.csv`)
  không được đưa vào release Git; chúng đã được thay bởi artifact có version trong
  `output/sprint1/` và `output/sprint2/`.
- `output/cate/` — CATE đã lưu (để ghép Causal Forest, không train lại).
- `output/dashboard_data.json` — dữ liệu cho dashboard.
