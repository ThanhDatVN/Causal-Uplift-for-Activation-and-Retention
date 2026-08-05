# Tuần 1 — Nền tảng dự án: Môi trường, EDA, Baseline Meta-Learner & Framework Đánh giá

> **Historical / superseded:** xem [`../SPRINT_1_FINAL_REPORT.md`](../../SPRINT_1_FINAL_REPORT.md)
> cho kết quả Sprint 1 sau lần chạy lại ngày 29/07/2026.

**Trạng thái:** Hoàn thành (2026-07-20 đến 2026-07-23)

---

## 1. Mục tiêu

Dựng môi trường, kiểm tra schema/data profile của Criteo, chạy randomization diagnostic và
xây bộ metric Qini/AUUC/bootstrap có unit test đối chiếu.

## 2. Tài liệu / nguồn đã đọc và tham khảo

**Đã đọc trực tiếp bản gốc:**
- Radcliffe & Surry (2011), *Real-World Uplift Modelling with Significance-Based Uplift Trees*, TR-2011-1 — khái niệm Qini curve/Qini measure.
- Künzel, Sekhon, Bickel, Yu (2019), *Metalearners for estimating heterogeneous treatment effects using machine learning*, PNAS (arXiv:1706.03461) — định nghĩa T/S/X-Learner.
- Bokelmann & Lessmann, *Improving Uplift Model Evaluation on RCT Data*, arXiv:2210.02152.
- Liu & Yuan, *We Have It Covered: A Resampling-based Method for Uplift Model Comparison*, arXiv:2509.04315.

**Đọc mã nguồn thư viện tham chiếu để xác thực công thức khi paper gốc không có công thức per-point:**
- `scikit-uplift` (`sklift`) — `qini_curve`, `qini_auc_score`, `uplift_curve`, `uplift_auc_score`.

**Tham khảo, sẽ đọc trực tiếp khi tới lượt triển khai (Tuần 3+):**
- Wager & Athey (2018), *Estimation and Inference of Heterogeneous Treatment Effects using Random Forests*, JASA — cho `causal_forest.py`.
- Devriendt, Guns & Verbeke (2020), arXiv:2002.05897 — nguồn AUUC.
- *Incremental Profit per Conversion*, arXiv:2306.13759 — cho `profit.py` (Tuần 5).

## 3. Phương pháp & code đã triển khai

| Module | Nội dung |
|---|---|
| `src/paths.py` | Hằng số đường dẫn |
| `src/data.py` | `load_criteo_full`, `stratified_sample`, `propensity_auc`, `ks_test_by_treatment` |
| `src/baselines.py` | `fit_t_learner`, `fit_x_learner` (`econml.metalearners`) |
| `src/evaluation.py` | Qini/AUUC, bootstrap CI; comparison release hiện dùng paired CI của `ΔQini` |
| `notebooks/01_eda_criteo.ipynb` | EDA + randomization diagnostic trên file Criteo local |

**Môi trường:** Python 3.12.10 (`.venv` riêng), `econml==0.16.0`, `pandas`/`scikit-learn`/`scipy`/`lightgbm`/`scikit-uplift` pin trong `requirements.txt`.

## 4. Thử nghiệm đã chạy trên file Criteo local

Tại mốc kết thúc tuần 1, 18 test đều pass (`pytest tests/ -v`). Suite hiện tại đã mở rộng
thành **24/24 pass**:

- `tests/test_data.py` (8 test) — schema, treatment/conversion rate, stratified sample, propensity AUC, KS-test và rare-outcome undersampling.
- `tests/test_baselines.py` (5 test) — T/X-Learner, probability wrapper và fixed propensity.
- `tests/test_evaluation.py` (11 test) — đối chiếu Qini/AUUC với `sklift`, bootstrap, edge cases, transformed outcome và calibration.

Ngoài ra có 13 lượt đo runtime/RAM cho `CausalForestDML`, T-, X- và DR-Learner ở nhiều
mức sample; smoke test fit T/X-Learner trên sample 5% rồi tính Qini/AUUC từ outcome và
treatment quan sát được.

## 5. Kết quả chính

**Dataset:** 13,979,592 dòng × 16 cột, `treatment_rate=0.8500`, `conversion_rate=0.002917`, không missing trên f0-f11.

**Randomization diagnostic:** Propensity AUC trên sample 5% bằng **0,5098**. Mô hình đã
dùng không phân biệt rõ treatment/control từ f0–f11; diagnostic này không tự chứng minh
randomization. Căn cứ về assignment mechanism đến từ provenance của Criteo.

**Đối chiếu công thức đánh giá với `sklift`:**

| Hàm | Đối chiếu | Sai số |
|---|---|---|
| `qini_curve` | `sklift.metrics.qini_curve` | khớp tuyệt đối (`atol=1e-9`) |
| `qini_score` | `sklift.metrics.qini_auc_score` | < 1e-6 |
| `uplift_curve` | `sklift.metrics.uplift_curve` | khớp tuyệt đối (`atol=1e-9`) |
| `auuc_score` | `sklift.metrics.uplift_auc_score` | < 1e-6 |

**Benchmark tài nguyên (CausalForestDML, cấu hình production):**

| Sample | Wall time | Peak RSS |
|---|---|---|
| 1% | 2.1 phút | 2.1 GB |
| 10% | 17.5 phút | 4.8 GB |
| 20% | 36.7 phút | 8.2 GB |

T/X/DR-Learner rẻ hơn 12-20 lần (dưới 90s ở sample 10%).

## 6. Tiếp theo (Sprint 2)

Lineup 6 model (Response, S/T/X-Learner, DR-Learner, Causal Forest). 5 model local đã chạy xong ở holdout 50% — kết quả + đánh giá: [`baseline-results.md`](baseline-results.md). Causal Forest chờ chạy Colab rồi ghép bằng `build_comparison.py`.

Còn lại: phân đoạn khách hàng chính thức, incremental profit, dashboard sản phẩm; bổ sung test cho S/DR/Response baseline.
