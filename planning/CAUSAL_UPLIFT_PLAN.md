# Causal Uplift for Activation and Retention

> **Actual execution update 31/07/2026:** đây là historical method plan. Release hiện
> tại nằm ở [`../report/SPRINT_2_FINAL_REPORT.md`](../report/SPRINT_2_FINAL_REPORT.md),
> [`../docs/SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md`](../docs/SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md)
> và [`../output/dashboard.html`](../output/dashboard.html).

> **Historical plan / cập nhật 29/07/2026:** protocol và số liệu thực thi mới nằm ở
> [`../report/SPRINT_1_FINAL_REPORT.md`](../report/SPRINT_1_FINAL_REPORT.md). Run Causal
> Forest bằng `docs/KAGGLE_RUNBOOK_COMPLETE.md`;
> các cấu hình Colab Pro, p-value hoặc segmentation cũ bên dưới không còn là chuẩn release.

> Ước lượng CATE (heterogeneous treatment effect) cho activation/retention từ Criteo Uplift
> Prediction Dataset, đánh giá bằng Qini/AUUC, và chuyển kết quả sang incremental profit
> theo các giả định được ghi rõ. Tài liệu không phụ thuộc file kế hoạch khác; PDF đề bài gốc
> không được lưu trong repository hiện tại.
>
> Tiến độ theo tuần + nhật ký hàng ngày: xem [`report/`](../report/). Tài liệu này là nguồn tham chiếu phương pháp luận + trạng thái hiện tại, không lặp lại lịch sử thay đổi.

---

## 0. Câu hỏi nghiên cứu gốc (source of record)

| Nhóm | Tên work-stream | Câu hỏi nghiên cứu | Dataset | Phương pháp | Paper nền tảng | Nguồn/Năm | Link paper | Link dataset | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|
| Causal Measurement & Long-Term | Causal Uplift for Activation and Retention | Khách hàng nào chỉ activation hoặc retention nhờ voucher, cashback hay notification, thay vì vốn đã tự chuyển đổi? | Criteo Uplift Prediction Dataset | T/X-Learner; Causal Forest; Doubly Robust Learner; Qini; AUUC; incremental profit | Wager & Athey — *Estimation and Inference of Heterogeneous Treatment Effects Using Random Forests* | JASA, 2018 | https://www.tandfonline.com/doi/full/10.1080/01621459.2017.1319839 | https://ailab.criteo.com/criteo-uplift-prediction-dataset/ | Dataset randomized phù hợp để học incrementality; monetary reward cần bổ sung nếu tối ưu profit. |

---

## 1. MỤC TIÊU & TIÊU CHÍ THÀNH CÔNG

**Mục tiêu lịch sử:** ước lượng CATE cho activation/retention trên Criteo và đánh giá
ranking/policy. Bốn principal strata chỉ là khung potential-outcome khái niệm; dữ liệu không
cho phép xác định stratum của từng người. Criteo cũng không có revenue/cost, nên output tiền
chỉ có thể là scenario, không phải incremental profit quan sát được.

**Tiêu chí thành công:**
- Ít nhất một CATE model trong comparison có Qini/AUUC cao hơn random targeting với CI 95%
  không chứa 0.
- Báo phân phối score CATE theo dấu/độ lớn mà không đổi tên thành principal strata quan sát.
- Mọi con số lợi nhuận phải ghi assumption về margin; kết luận không được vượt phạm vi
  outcome và thời gian quan sát của dữ liệu.

---

## 2. NGUYÊN TẮC THIẾT KẾ

- Một mình thực hiện → làm tuần tự theo giai đoạn, không chia nhỏ tập trung.
- Bắt buộc hoàn thành lineup 6 model (Response baseline + S/T/X-Learner + DR-Learner + Causal Forest) và bộ đánh giá Qini/AUUC.
- Mỗi giai đoạn kết thúc bằng notebook hoặc script cùng bảng số liệu truy được về artifact.
- Timeline tham khảo: kế hoạch gốc 8 tuần; tiến độ thực thi theo artifact nằm trong `report/`.

---

## 3. NGHIÊN CỨU PHƯƠNG PHÁP LUẬN CHI TIẾT

**A. Baseline meta-learner (làm trước Causal Forest):**
- **T-Learner:** 2 model riêng biệt (treatment=1 và treatment=0), CATE = ŷ₁ − ŷ₀.
- **X-Learner** (Künzel et al. 2019, *PNAS*, "Metalearners for estimating heterogeneous treatment effects using machine learning", arXiv:1706.03461 — đã đọc trực tiếp) — phù hợp khi treatment/control mất cân bằng (Criteo ≈85/15, đúng use-case X-Learner được thiết kế để giải quyết). Impute outcome đối nghịch cho mỗi nhóm rồi weight theo propensity score.
  - Thư viện: `econml.metalearners.XLearner`.

**B. Causal Forest (phương pháp chính — code xong, chưa chạy):**
- Nền tảng lý thuyết: Wager & Athey (2018, JASA) — honest splitting (1 nửa dữ liệu chọn cấu trúc cây, nửa còn lại ước lượng effect trong leaf) → suy diễn thống kê hợp lệ (asymptotic CI). **Chưa đọc trực tiếp bản gốc paper này** — cần đọc trước khi code `causal_forest.py`.
- Triển khai lịch sử dùng `econml.dml.CausalForestDML` với `discrete_treatment=True`.
  Profile release hiện hành nằm trong `docs/KAGGLE_RUNBOOK_COMPLETE.md`; cấu hình cũ
  `inference=True` không phải profile đang dùng.
- **Nguồn không dùng làm căn cứ:** một ghi chú cũ nêu benchmark “S-Learner Qini ≈0,376,
  Causal Forest chỉ chạy trên 10%” nhưng không có nguồn đã xác minh. Số liệu này không được
  dùng trong comparison; các kết quả dự án phải truy được về artifact trong `output/`.

**C. Doubly Robust Learner (DR-Learner — đã chạy @50%, Qini 0,154):**
- Lý thuyết: kết hợp outcome regression + propensity weighting; nhất quán nếu 1 trong 2 nuisance model đúng, không cần cả hai.
- Triển khai: `econml.dr.DRLearner`. Theo thiết kế RCT của Criteo, propensity xấp xỉ 0,85;
  implementation dùng fixed propensity thay vì ước lượng lại từ feature.
- Tài liệu: https://www.pywhy.org/EconML/spec/estimation/dr.html
- arXiv 2406.00853 (từng dự định dùng làm tutorial) đã xác nhận **withdrawn** trên trang arXiv — không dùng làm nguồn.

**D. Đánh giá: Qini / AUUC**
- **Khái niệm Qini** — Radcliffe & Surry (2011), *Real-World Uplift Modelling with
  Significance-Based Uplift Trees* (đã đọc trực tiếp): định nghĩa Qini curve là
  "incremental gains curve" và Qini measure là diện tích giữa observed curve với random
  targeting, chuẩn hoá theo N². Paper không đưa công thức tính từng threshold mà dẫn sang
  Radcliffe (2007); repository chưa có bản mở để đối chiếu trực tiếp nguồn đó. Công thức
  trong code (`Qini(t) = Y1(t) − Y0(t)·N1(t)/N0(t)`) được viết lại từ hành vi implementation
  của `sklift` và đã có unit test đối chiếu số học.
- **AUUC** — công thức khác Qini: `UpliftCurve(t) = (Y1(t)/N1(t) − Y0(t)/N0(t))·N(t)`. Lấy từ đọc mã nguồn `sklift.metrics.uplift_curve`/`uplift_auc_score`; paper mà `sklift` tự trích dẫn (Devriendt, Guns & Verbeke 2020, arXiv:2002.05897) chưa đọc trực tiếp.
- Không dùng AUC/accuracy (không có ground-truth CATE cá nhân — "fundamental problem of causal inference").
- `bootstrap_ci()` — nonparametric bootstrap percentile chuẩn (Efron & Tibshirani, textbook), không gắn với 1 paper uplift cụ thể.
- `paired_bootstrap_difference_ci()` — resample cùng index cho hai model và báo percentile
  CI của `ΔQini`. Đây là thủ tục uncertainty thực dụng, không được diễn giải thành kiểm định
  giả thuyết hay p-value. `paired_bootstrap_compare()` chỉ còn để tương thích code cũ.
- Thư viện đối chiếu: **scikit-uplift (`sklift`)** — https://www.uplift-modeling.com/en/latest/, https://github.com/maks-sh/scikit-uplift.

**E. Incremental profit (chưa triển khai):**
- Criteo chỉ có `visit`/`conversion` nhị phân, không có giá trị đơn hàng.
- Kế hoạch: response transformation lấy cảm hứng từ *Incremental Profit per Conversion* (arXiv 2306.13759, chưa đọc trực tiếp) — trước khi code phải viết rõ công thức, biến quan sát được trong Criteo, và phần nào là giả định/proxy.
- Khai báo giả định margin/chi phí và sensitivity analysis; không trình bày scenario output
  như revenue hoặc profit quan sát được.

**F. Principal strata khái niệm — không phải output phân loại cá nhân:**

| Nhóm latent | Định nghĩa bằng hai potential outcomes | Giới hạn quan sát |
|---|---|---|
| Persuadables | \(Y(1)=1, Y(0)=0\) | Không xác định trực tiếp ở cấp cá nhân |
| Sure things | \(Y(1)=1, Y(0)=1\) | Không xác định trực tiếp ở cấp cá nhân |
| Lost causes | \(Y(1)=0, Y(0)=0\) | Không xác định trực tiếp ở cấp cá nhân |
| Sleeping dogs | \(Y(1)=0, Y(0)=1\) | Score CATE âm không chứng minh membership cá nhân |

---

## 4. KẾ HOẠCH HÀNH ĐỘNG THEO GIAI ĐOẠN

### GIAI ĐOẠN 0 — Chuẩn bị môi trường
Trạng thái: hoàn thành. Python 3.12.10 dùng `.venv` riêng; `requirements.txt` đã pin.
File Criteo local có 311.422.618 byte và 13.979.592 dòng. Chi tiết: `report/archive/week-01-*`.

### GIAI ĐOẠN 1 — EDA Criteo Uplift
Trạng thái: hoàn thành. `src/data.py` và `notebooks/01_eda_criteo.ipynb`; 7/7 test tại mốc này.
- Schema khớp mô tả, `treatment_rate=0.8500`, `conversion_rate=0.002917`, không missing trên f0-f11.
- Propensity AUC trên sample 5% bằng **0,5098**. Đây là balance diagnostic của model đã dùng;
  không phải kiểm định chứng minh assignment mechanism.
- Chiến lược sample hiện hành dùng learning curve theo resource gate; xem
  `docs/KAGGLE_RUNBOOK_COMPLETE.md`.
- **Output:** `01_eda_criteo.ipynb`, `output/eda_summary.csv`. Chi tiết: `report/archive/week-01-*`.
- Nguồn dataset: link download "chính thức" trên trang Criteo AI Lab đã chết (404) — dùng mirror HuggingFace: https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz. Paper công bố dataset: Diemert et al. (2018), *A Large Scale Benchmark for Uplift Modeling*, AdKDD @ KDD.

### GIAI ĐOẠN 2 — Baseline + Causal Forest + DR-Learner + Đánh giá

*Framework đánh giá — trạng thái: hoàn thành:*
- `src/evaluation.py` (`qini_curve`, `qini_score`, `uplift_curve`, `auuc_score`,
  `bootstrap_ci`, `paired_bootstrap_difference_ci`) — có unit test đối chiếu khớp `sklift`
  (Qini `atol=1e-9`, AUUC lệch <1e-6) và guard NaN cho trường hợp không conversion.
- Chi tiết đầy đủ: `report/archive/week-01-*`.

*Lineup 6 model — 5 model local đã chạy @50% (kết quả: `report/archive/week-01-baseline-results.md`):*
Comparison gồm **Response, S-Learner, T-Learner, X-Learner, DR-Learner và Causal Forest**;
thứ tự liệt kê không biểu thị chất lượng.
- Đã chạy `fit_response_baseline` (`ResponseBaseline`, LGBMClassifier dự đoán
  P(conversion) không dùng treatment); model có Qini cao nhất trong bảng Sprint 1.
- Đã chạy `fit_s_learner` (S-Learner, một model học `Y ~ f(X,T)`).
- Đã chạy `fit_t_learner`, `fit_x_learner`.
- Đã chạy `fit_dr_learner` với `DummyClassifier(strategy="prior")`, LightGBM và
  cross-validation 3-fold.
- `scripts/train_causal_forest.py` đã có code; cloud run chưa hoàn thành. Trạng thái và
  profile hiện hành nằm trong `docs/KAGGLE_RUNBOOK_COMPLETE.md`.

*Kiến trúc script — trạng thái: đã viết:*
- `scripts/train_baselines.py` — train 5 model local + đánh giá + lưu CATE (`output/cate/`).
- `scripts/train_causal_forest.py` — Causal Forest trên Colab, lưu CATE.
- `scripts/build_comparison.py` — ghép mọi CATE đã lưu → ma trận đủ 6 model + Qini curve + phân khúc, **không train lại**.
- `scripts/export_dashboard_data.py` — xuất `output/dashboard_data.json` cho dashboard sản phẩm.
- **Runbook thực thi:** `planning/RUN_PLAN.md`.

*Đánh giá + Segment + Incremental profit:*
- [x] Qini/AUUC cho 5 model local @50% + bootstrap CI (500 resample) — `report/archive/week-01-baseline-results.md`. Causal Forest chờ Colab.
- [x] Paired bootstrap so sánh vs baseline (T-Learner) — đã có trong ma trận 5 model.
- [x] Phân đoạn score sơ bộ (`output/segments_baseline.csv`); model dùng cho release phải
  được chọn theo comparison protocol sau khi có trạng thái Causal Forest.
- [ ] Response transformation sang incremental profit (mục 3.E), 2-3 kịch bản margin.
- **Output:** `02_causal_uplift.ipynb`, `output/qini_comparison.csv`, `output/segments.csv`, `output/incremental_profit.csv`, `output/dashboard_data.json`.

### Hướng cải tiến model

Kết quả năm model trên mẫu 50% (`report/archive/week-01-baseline-results.md`) cho thấy **Response**
và **S-Learner** có Qini khoảng 0,177–0,179, còn **T/X-Learner** khoảng 0,141. Diagnostic
cho thấy uplift score tương quan với xác suất mua nền; T/X ước lượng hiệu của hai outcome
model nên có thể tăng phương sai khi conversion rate là 0,29%. Đây là giả thuyết giải thích,
không phải causal conclusion đã được kiểm định riêng.

Các điều kiện ảnh hưởng đến model comparison:

1. Conversion rate khoảng 0,29%, nên số positive event trong control arm thấp hơn treatment arm.
2. Assignment rate xấp xỉ 0,85; fixed và estimated propensity là hai cấu hình khác nhau và
   phải được so sánh trên cùng validation indices.
3. Các cấu hình S/T/X lịch sử dùng `LGBMRegressor`. Tham số `scale_pos_weight` và
   `is_unbalance` của binary objective không áp dụng trực tiếp cho regression objective.

Các thử nghiệm rare-outcome đã hoàn thành trong Sprint 2:

- stratified negative undersampling;
- renormalization theo hệ số `k`;
- arm-wise exact probability restoration cho T-Learner;
- validation τ-isotonic calibration;
- paired Qini bootstrap và DR policy comparison.

Kết quả và công thức nằm trong `report/SPRINT_2_FINAL_REPORT.md` và
`docs/SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md`. Exact restoration bên trong X-Learner chỉ là
research ablation; release không dùng cấu hình đó.

Backlog model mới phải có hypothesis và acceptance criterion trước khi chạy:

1. R-Learner/NonParamDML với cross-fitted nuisance models.
2. Uplift Random Forest có honesty và rare-outcome ablation.
3. ForestDRLearner trên learning curve có resource gate.
4. Rank-based ensemble hoặc causal aggregation học trọng số trên validation.
5. Direct uplift ranking chỉ như challenger vì objective khác CATE calibration.

Mỗi candidate được đánh giá bằng Qini/AUUC, paired interval, calibration diagnostic và DR
policy value. Không sử dụng `visit` hoặc `exposure` làm feature vì data contract xếp chúng
sau treatment. Confirmation Sprint 2 đã được mở; comparison mới phải ghi đây là retrospective
benchmark hoặc dùng evaluation data mới.

### GIAI ĐOẠN 3 — Robustness + hoàn thiện incremental profit
- [ ] Sensitivity analysis incremental profit theo từng kịch bản margin.
- [ ] Robustness check: Causal Forest/DR-Learner ở 1-2 sample size khác nhau, Spearman correlation CATE ranking.
- **Output:** `output/incremental_profit.csv`, `output/robustness.csv`.

### GIAI ĐOẠN 4 — Báo cáo + Slide
- [ ] Báo cáo: Research Question → Data → Method → Results → Limitations, không placeholder.
- [ ] Slide: tập trung vào kết quả; review chéo từng claim với artifact và nguồn.
- **DoD:** không còn TODO, mọi số liệu trace được về file trong `output/`.

---

## 5. RỦI RO & GIẢI PHÁP

| Rủi ro | Giải pháp |
|---|---|
| pip cài nhầm `econml` 0.8.1 (2020) mà không báo lỗi trên Python 3.14 | Dùng Python 3.12 + pin `econml==0.16.0` (mục 6.5) |
| Vô tình commit dataset ~3GB lên git | `.gitignore` chặn `data/` từ Giai đoạn 0 |
| CausalForestDML vượt local resource gate | Dừng ở stage đã qua gate; báo runtime/RAM và không đưa model vào release table nếu thiếu artifact |
| Conversion rate khoảng 0,29% làm tăng variance | Tăng `min_samples_leaf`, dùng rare-outcome protocol và báo interval |
| Không có monetary outcome cho incremental profit | Chỉ báo conversion-equivalent scenario với value/cost input và sensitivity analysis |
| Qini CI chứa 0 ở 1 hoặc vài model | Báo cáo model đó chưa tách khỏi random theo CI; không suy rộng sang model khác |

**Lỗi phương pháp luận tuyệt đối phải tránh:**
1. Dùng AUC/accuracy để đánh giá uplift model — sai về bản chất, không có ground-truth CATE cá nhân.
2. Suy rộng kết luận nhân quả ngoài population, treatment và outcome của Criteo.

**Ràng buộc:** License Criteo CC BY-NC-SA — chỉ phi thương mại/học thuật. Tránh load toàn bộ ~14M dòng vào RAM cùng lúc.

---

## 6. MÔI TRƯỜNG THỰC THI, KIẾN TRÚC CODE & NGUỒN THAM KHẢO

### 6.1. Nguyên tắc code

- Toàn bộ logic tái sử dụng nằm trong package `src/`; notebook chỉ gọi hàm + vẽ biểu đồ + viết nhận xét, không viết lại công thức.
- Mỗi hàm dùng chung phải có 1 test đối chiếu với kết quả biết trước hoặc thư viện tham chiếu (`sklift`) trước khi dùng cho kết quả chính thức — không tin "chạy không lỗi" là đủ.
- Chỉ gán paper làm nguồn công thức khi đã đối chiếu đúng phần liên quan. Nếu implementation
  được xác minh từ `sklift` hoặc `econml`, ghi đó là nguồn implementation và kèm unit test.
  Nếu chưa đọc được nguồn gốc, ghi “chưa xác minh trực tiếp”.
- `random_state`/`seed = 42` cố định xuyên suốt project.
- Notebook import từ `src/` bằng cách thêm repo root vào `sys.path` ở cell đầu tiên.
- Naming: model object `model_<method>`; output file `output/*.csv`.
- Hyperparameter trong hàm production phải khớp cấu hình đã benchmark ở mục 6.5 — đổi config thì phải benchmark lại trước khi chạy sample lớn.

### 6.2. Kiến trúc & trạng thái code

```
src/
  paths.py                  # REPO_ROOT, DATA_DIR, OUTPUT_DIR, CRITEO_PATH
  data.py                   # load Criteo, sample, holdout dung chung, propensity AUC, KS-test
  baselines.py              # Response + S/T/X-Learner + DR-Learner
  evaluation.py             # Qini + AUUC + bootstrap CI (guard NaN)
  segments.py               # TODO (phan khuc — hien build_comparison.py lam ban rut gon)
  profit.py                 # TODO (incremental profit)
scripts/
  train_baselines.py        # train 5 model local + luu CATE (output/cate/)
  train_causal_forest.py    # Causal Forest tren Colab, luu CATE
  build_comparison.py       # ghep moi CATE -> ma tran 6 model + Qini curve + segment
  export_dashboard_data.py  # xuat output/dashboard_data.json cho dashboard
```

| Module | Trạng thái | Test |
|---|---|---|
| `paths.py` | Đã có | `tests/test_data.py::test_criteo_path_exists` |
| `data.py` (+ `train_test_holdout`, `xty`) | Đã có | `tests/test_data.py` |
| `baselines.py` (Response/S/T/X/DR) | Đã chạy @50% | `tests/test_baselines.py` |
| `evaluation.py` | Đã có | `tests/test_evaluation.py` |
| `scripts/train_baselines.py` | Đã chạy @50% | `report/archive/week-01-baseline-results.md` |
| `scripts/train_causal_forest.py` | Đã viết | cloud run chưa hoàn thành |
| `scripts/build_comparison.py` | Đã viết | phụ thuộc artifact Causal Forest |
| `segments.py` / `profit.py` | Chưa triển khai ở mốc kế hoạch này | — |

Chạy toàn bộ test: `.venv/Scripts/python.exe -m pytest tests/ -v` → hiện tại 24/24 pass.

**Đặc tả hàm còn TODO:**
- `fit_causal_forest(X, T, Y, n_estimators=500, min_samples_leaf=200, cv=3, seed=42)` — bắt buộc `discrete_treatment=True`.
- `fit_dr_learner(X, T, Y, cv=3, seed=42)` — dùng propensity RCT cố định, không tự ước lượng lại.
- `assign_segments(cate, y_control_pred, y_treat_pred, cate_threshold=None)` — theo quy tắc mục 3.F; test: 4 điểm giả lập, mỗi điểm rơi đúng 1 nhóm.
- `response_transform_profit(y, treatment, cate, margin_pct, treatment_cost)` — viết rõ công thức trước khi code; test: `margin_pct=0` → profit=0.
- `sensitivity_scenarios(...)` — 2-3 kịch bản margin; test: Spearman correlation 2 thứ hạng > 0.8.

### 6.3. Nguồn tham khảo

**Đã đọc trực tiếp bản gốc:**
- Künzel, Sekhon, Bickel, Yu (2019), *Metalearners for estimating heterogeneous treatment effects using machine learning*, PNAS — https://www.pnas.org/doi/10.1073/pnas.1804597116 (bản đọc: arXiv:1706.03461).
- Radcliffe & Surry (2011), *Real-World Uplift Modelling with Significance-Based Uplift
  Trees*, TR-2011-1 — https://stochasticsolutions.com/pdf/sig-based-up-trees.pdf.
  (Radcliffe 2007 được paper 2011 dẫn cho chi tiết Qini; repository chưa có bản mở để đối
  chiếu trực tiếp.)
- Bokelmann & Lessmann, *Improving Uplift Model Evaluation on RCT Data* — https://arxiv.org/pdf/2210.02152.
- Liu & Yuan, *We Have It Covered: A Resampling-based Method for Uplift Model Comparison* — https://arxiv.org/html/2509.04315v1.

**Cần đọc trực tiếp trước khi triển khai (chưa đọc):**
- Wager & Athey (2018), *Estimation and Inference of Heterogeneous Treatment Effects using Random Forests*, JASA — https://www.tandfonline.com/doi/full/10.1080/01621459.2017.1319839 (cho Causal Forest).
- Devriendt, Guns & Verbeke (2020), arXiv:2002.05897 (nguồn AUUC mà `sklift` tự trích dẫn).
- *Incremental Profit per Conversion*, arXiv:2306.13759 (cho `profit.py`).

**Tham khảo bổ sung, chưa đọc trực tiếp:**
- Diemert et al. (2018), *A Large Scale Benchmark for Uplift Modeling* — https://bitlater.github.io/files/large-scale-benchmark_comAH.pdf.
- *A Large-Scale Empirical Comparison of Meta-Learners and Causal Forests* — https://arxiv.org/abs/2604.06123.
- *A Large Scale Benchmark for Individual Treatment Effect Prediction and Uplift* — https://arxiv.org/pdf/2111.10106.
- Đánh giá propensity AUC / covariate balance — https://www.r-causal.org/chapters/09-evaluating-ps.

**Cần đọc trực tiếp cho "Hướng cải tiến model" (mục 4) — hiện chỉ đọc abstract/search, KHÔNG dùng số làm căn cứ báo cáo:**
- Nyberg & Klén (2021), *Uplift Modeling with High Class Imbalance*, PMLR v157 — https://proceedings.mlr.press/v157/nyberg21a/nyberg21a.pdf (undersample + isotonic calibration, báo ~+6.5% AUUC trên Criteo; CVT variance cao khi imbalance). Cần đọc full trước khi trích số +6.5%.
- Williamson et al. (2014), *Variance reduction in randomised trials by IPW using the propensity score*, Stat in Medicine — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4285308/ (nuance: propensity ước lượng đôi khi giảm variance so với hằng số trong RCT — căn cứ cho A/B ở cải tiến #1).
- *Class flipping for uplift modeling and HTE estimation on imbalanced RCT data* — https://arxiv.org/pdf/2412.10009.
- Transformed Outcome / CVT: tham chiếu upliftML methods — https://upliftml.readthedocs.io/en/latest/methods.html (công thức `Y* = Y·(T−p)/(p(1−p))`; đọc kỹ + viết lại độc lập + test đối chiếu trước khi code, đúng nguyên tắc mục 6.1).

**Không dùng làm nguồn:**
- arXiv 2406.00853 (*A Tutorial on Doubly Robust Learning*) — xác nhận **withdrawn**.

**Dataset:** Criteo Uplift Prediction Dataset — https://ailab.criteo.com/criteo-uplift-prediction-dataset/ (link download trên trang đã chết) — tải qua HuggingFace: https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz.

**Thư viện:** EconML — https://www.pywhy.org/EconML/ · scikit-uplift (`sklift`) — https://www.uplift-modeling.com/en/latest/ · CausalML (optional, `causalml==0.17.0`) — https://causalml.readthedocs.io/.

### 6.4. Rà soát chất lượng còn mở

| Điểm | Trạng thái | Việc cần làm |
|---|---|---|
| Causal Forest / DR-Learner | Chưa triển khai | Đọc Wager & Athey (2018) trước khi code; DR-Learner dùng propensity RCT cố định |
| Profit proxy | Chưa triển khai | Viết công thức + biến quan sát được trước khi code, không chỉ dựa tên paper |
| Benchmark logs | Log đặt theo `<tag>.log`, có tag trùng (`smoke_cf`) | Đổi harness sang log có timestamp/run id trước khi dùng làm bằng chứng tái lập |

### 6.5. Môi trường thực thi (máy: Ryzen 5 6600H, 15.2GB RAM, Windows 11)

**Python:** release dùng Python 3.12.10 trong `.venv` và pin `econml==0.16.0` trong
`requirements.txt`; Python 3.14 không thuộc supported environment của release này.

**Benchmark lịch sử — CausalForestDML** (`n_estimators=500`, `min_samples_leaf=200`,
`honest=True`, `inference=True`, `cv=3`):

| Sample | Wall time | Peak RSS |
|---|---|---|
| 1% | 2.1 phút | 2,097 MB |
| 2% | 3.75 phút | 2,098 MB |
| 5% | 8.8 phút | 3,105 MB |
| 10% | 17.5 phút | 4,797 MB |
| 20% | 36.7 phút | 8,163 MB |

Peak RSS quan sát tăng nhanh hơn tuyến tính từ 5% trở đi trong benchmark cũ. Các số 25%,
30%, 50%, 70% và 100% trong bảng này là ngoại suy, không phải measurement từ cloud run.

**Protocol lịch sử:** baseline dùng sample 50% với shared holdout. Các số Causal Forest trên
20% là ngoại suy và không phải cloud result. Protocol hiện hành thay phần này bằng Kaggle
resource gate và test-index hash.

Trong benchmark lịch sử, T/X/DR-Learner và Response dùng runtime thấp hơn Causal Forest
12–20 lần ở sample đã đo. Artifact chỉ được ghép khi dùng cùng test-index hash.

**Hạ tầng hiện hành:** baseline và evaluation chạy local. Causal Forest chỉ chạy cloud khi
Kaggle resource gate 20% và 30% đạt; không giả định trước RAM của session.

**Cách đo:** `scripts/bench_harness.py` chạy mỗi benchmark trong subprocess, poll RSS bằng
`psutil` và ghi `benchmarks/results.csv` cùng `benchmarks/logs/`. Model scripts:
`benchmarks/bench_causal_forest.py`, `benchmarks/bench_metalearners.py`.

---

## 7. LỊCH SỬ CẬP NHẬT

Nhật ký chi tiết theo ngày: xem [`report/`](../report/). Mốc lớn:

- **2026-07-20 → 2026-07-23:** Tuần 1 — môi trường, EDA/randomization check, baseline T/X-Learner, framework đánh giá Qini/AUUC/bootstrap CI với guard edge-case. Chi tiết: `report/archive/week-01-*`.
