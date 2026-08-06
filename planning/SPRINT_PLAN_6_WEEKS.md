# Báo cáo mentor — Lộ trình 3 sprint, kiểm chứng bằng chứng và định hướng sản phẩm

> **Actual execution update 31/07/2026:** đây là planning snapshot. Kết quả Sprint 2 và
> trạng thái dashboard/Causal Forest chính thức nằm ở
> [`SPRINT_2_FINAL_REPORT.md`](../report/SPRINT_2_FINAL_REPORT.md). Nếu số hoặc trạng thái mâu thuẫn,
> ưu tiên báo cáo Sprint 2.

> **Cập nhật 29/07/2026:** báo cáo này giữ vai trò kế hoạch 6 tuần. Kết quả thực thi
> Sprint 1 sau lần chạy lại nằm ở [`SPRINT_1_FINAL_REPORT.md`](../report/SPRINT_1_FINAL_REPORT.md)
> và được ưu tiên nếu có số liệu mâu thuẫn.

**Dự án hiện tại:** *Causal Uplift for Activation and Retention* — **Nhắm mục tiêu khuyến mãi bằng hiệu ứng tăng thêm do can thiệp nhân quả**
**Hướng sản phẩm sau causal:** *Incremental Customer Value Optimization* — **Tối ưu hóa giá trị khách hàng tăng thêm**
**Thời lượng đã chốt:** 6 tuần; Tuần 1 đã hoàn thành. Báo cáo này là kế hoạch thực thi cho 5 tuần còn lại, thay cho các mốc cũ nếu chúng mâu thuẫn.
**Mục tiêu dự án:** có một demo chạy được, kết quả tái lập được và phần trình bày nêu
đúng metric, điều kiện thí nghiệm, quyết định và giới hạn.

> Quy ước bằng chứng: **Đã có** nghĩa là file/kết quả hiện diện trong repository; **cần làm**
> là backlog; **giả định** không được trình bày như biến quan sát hoặc kết quả đã chạy. Mọi
> công thức, số liệu và claim học thuật cần nguồn hoặc kiểm chứng mã nguồn ghi bên dưới.

---

## 1. Kết luận điều hành để báo cáo mentor

### 1.1 Trạng thái thực tại cuối Tuần 1

Baseline causal uplift hiện bao gồm:

- Dữ liệu Criteo bản local: 13.979.592 dòng, 12 feature ẩn danh, `treatment`, `conversion`, `visit`, `exposure`; pipeline hiện chỉ dùng feature tiền treatment `f0`–`f11` cho outcome `conversion`.
- 5 mô hình đã chạy trên cùng holdout 50%, train/test 70/30, stratify theo `(treatment, conversion)`, `seed=42`: Response, S-, T-, X- và DR-Learner.
- Kết quả Qini hiện có: Response 0,1793; S-Learner 0,1768; DR 0,1540; T 0,1420; X 0,1414.
  Đây là kết quả offline trên Criteo, không phải revenue lift hoặc production effect.
- 24/24 test đang pass. Qini curve/Qini score/AUUC được đối chiếu số học với `scikit-uplift`; test negative-control và edge case đã có.
- Có dashboard HTML tĩnh và dữ liệu xuất dashboard; chưa phải web application có API, container hay CI.

Response baseline có Qini cao nhất trong bảng hiện tại. Kết quả này không cho phép kết luận
causal learner kém trong các bối cảnh khác; nó chỉ cho thấy các cấu hình đã chạy chưa vượt
Response trên metric ranking và split đang dùng. Khi báo cáo với mentor, cần trình bày kèm
confidence interval, protocol chọn model và giới hạn của dataset.

### 1.2 Mục tiêu đến hết Tuần 6

Sản phẩm cuối không phải là “một model CATE”, mà là **Uplift Targeting Console**:

1. Một pipeline tái lập được: raw data → split cố định → train → evaluation → decision table → dashboard.
2. Một quyết định marketing có thể giải thích: chọn tỷ lệ khách hàng cần target, số incremental conversion ước lượng trên holdout, độ bất định và điều kiện để hòa vốn.
3. Một demo web/container nhỏ, chạy bằng artifact đã sinh sẵn; không train model khi người xem bấm dashboard.
4. Một báo cáo nêu rõ data provenance, công thức, assumption, giới hạn, kiểm thử và việc cần làm tiếp theo là probabilistic CLV/iCLV.

**Tuyên bố không được dùng:** “đã tối ưu CLV dài hạn”, “đã chứng minh doanh thu tăng”,
“đã nhận diện principal stratum của từng khách”, hoặc “Causal Forest vượt baseline” khi
chưa có data/model/result tương ứng.

---

## 2. Rà soát cấu trúc dự án và phạm vi thực tế

### 2.1 Cấu trúc hiện tại

| Khu vực | Có trong repo | Vai trò hiện tại | Đánh giá / hành động cần làm |
|---|---|---|---|
| `src/` | `data.py`, `baselines.py`, `evaluation.py`, `paths.py` | Load/split/check data; 5 baseline; metric và bootstrap | **Core đã có.** Giữ API ổn định; thêm model card thay vì vội viết nhiều module mới. |
| `tests/` | 24 tests trong `test_data.py`, `test_baselines.py`, `test_evaluation.py` | Regression test, đối chiếu metric với `scikit-uplift` | **Có.** Sprint 1 phải thêm smoke test cho artifact/export, không chỉ test hàm. |
| `scripts/` | train baseline/causal forest, build comparison, export/build dashboard, benchmark harness, tuning | Pipeline vận hành thủ công nhưng có thể tái lập | **Có.** Chuẩn hóa một lệnh release và manifest đầu ra. |
| `notebooks/` | `01_eda_criteo.ipynb`, `colab_causal_forest.ipynb` | EDA và run Colab | `02_causal_uplift.ipynb` được nêu ở tài liệu cũ nhưng **chưa tồn tại**; chỉ tạo nếu thực sự cần narrative cuối. |
| `benchmarks/` | benchmark meta-learner/Causal Forest; kết quả/log | Đo runtime/RAM | **Có.** Dùng để ra quyết định hạ tầng, không suy diễn tốc độ từ GPU. |
| `output/` | CATE 5 model, CSV comparison, chart, dashboard artifact | Result artifacts | **Có.** Cần thêm `run_manifest.json` và hash input/output trước release. |
| `report/archive/week-01-*` | EDA, daily log, baseline results | Bằng chứng tiến độ tuần 1 | **Có.** Báo cáo này nối tiếp và không ghi lại lịch sử sai khác. |
| `docs/` | tutorial, explainer, dashboard/Colab concept | Giải thích người dùng | **Có.** Một số câu về dashboard/6 model là future-facing; cần đồng bộ khi release. |
| `planning/` | causal plan, run plan, roadmap cũ, `incremental_value_product/` | Kế hoạch causal và hướng CLV kế tiếp | **Có.** `planning/sprints.md` là lịch cũ; báo cáo này là mốc mentor mới. |
| `data/` | Criteo local và Online Retail II local | Input, không commit | Criteo là core causal; Online Retail II chỉ dùng **sau khi causal đóng scope**. |

### 2.2 Những hạng mục tài liệu cũ nhắc đến nhưng chưa được coi là hoàn thành

| Hạng mục | Trạng thái đúng | Quyết định kế hoạch |
|---|---|---|
| Causal Forest kết quả 50% | Chưa có `cate_causal_forest.npy`/bảng 6 model cuối | Là gate đầu Sprint 1. Nếu không qua preflight RAM/runtime, đóng scope ở 5 model và ghi lý do kỹ thuật. |
| `src/causal_forest.py` | Không tồn tại; logic nằm ở script/Colab | Không bắt buộc tạo module mới nếu script có thể tái lập và được test smoke. |
| `src/segments.py`, 4 segment | Không tồn tại; artifact hiện là 3 nhóm theo dấu/độ lớn CATE | Không gọi là 4 principal strata. Chỉ ghi “operational CATE segments” cho đến khi hai potential outcomes được mô hình hóa/hiệu chuẩn riêng. |
| `src/profit.py`, `incremental_profit.csv` | Không tồn tại | Chỉ thêm break-even simulator theo assumption; không gọi scenario output là observed profit khi Criteo không có revenue/cost. |
| Notebook `02_causal_uplift.ipynb` | Không tồn tại | Dùng report/script reproducible trước; notebook là tùy chọn cho storytelling. |
| API, Docker, CI | Chưa tồn tại | Là hạng mục kỹ thuật tùy chọn ở Sprint 3; dashboard tĩnh vẫn là fallback demo hợp lệ. |
| CLV/BG-NBD/Gamma-Gamma | Mới có benchmark/plan; chưa là pipeline chính thức | Để sau causal release, không trộn vào metric/kết quả của dự án hiện tại. |

### 2.3 Quy tắc kiểm soát scope

1. **P0 — bắt buộc:** causal release tái lập, model comparison có metric và uncertainty,
   dashboard demo, report/demo video.
2. **P1 — làm nếu P0 hoàn tất:** run Causal Forest 50%, tuning có giới hạn, policy sensitivity.
3. **P2 — sau causal:** probabilistic CLV trên Online Retail II, Hillstrom monetary uplift
   và incremental CLV. Những phần này đã được định hướng tại
   [`planning/incremental_value_product/README.md`](incremental_value_product/README.md)
   và phải được ghi trạng thái “chưa thực hiện” trong release causal.

---

## 3. Kiểm chứng dữ liệu và điều kiện hạ tầng

### 3.1 Dữ liệu

| Dataset | Mục đích hợp lệ | Điều đã kiểm chứng | Không được suy ra |
|---|---|---|---|
| Criteo Uplift v2.1 local | CATE/uplift cho conversion; so sánh ranking offline | File local có 13.979.592 × 16; RCT origin cần đối chiếu với manifest local; propensity AUC thực nghiệm 0,5098 chỉ là diagnostic balance | Revenue, margin, CLV dài hạn, treatment effect của `visit`/`exposure`, hay triển khai thực tế. |
| Online Retail II | Kế tiếp: temporal RFM, BG/NBD/Gamma-Gamma và data engineering | 2 sheets, tổng 1.067.371 transaction record (theo UCI); có cancellation/missing/wholesale caveat | Causal treatment effect — dataset này không có random treatment/control. |
| Hillstrom (chưa tải local) | Kế tiếp: monetary uplift ngắn hạn trên RCT email | TFDS mô tả 64k customers, 3 arms, outcome hai tuần và `spend` | Long-term CLV hoặc retention dài hạn. |

**Data contract trước mọi run cuối:**

- Ghi version/file name, SHA-256, schema, số dòng, treatment/outcome rate, feature list và thời điểm cắt dữ liệu vào `output/run_manifest.json`.
- Chặn feature hậu treatment: `visit` và `exposure` không được đưa vào feature CATE conversion hiện tại nếu chúng xảy ra sau assignment.
- Giữ split/seed cố định; không đổi `FRAC`, `SEED`, `TEST_SIZE` sau khi đã xem kết quả để
  lựa chọn một estimate thuận lợi hơn.
- Lưu command, package version, runtime/RSS và artifact path cho run phát hành.

### 3.2 Hạ tầng thực tế và quyết định chạy

Máy local đã đo: 12 logical CPU, RAM khoảng 15,2 GB, GPU RTX 3050 Laptop 4 GB. Benchmark CausalForestDML đã quan sát khoảng 36,7 phút / 8,2 GB RSS ở mẫu 20%; 30%/50% là ngoại suy cần kiểm chứng lại, không phải số đo.

| Công việc | Nơi chạy ưu tiên | Lý do | Gate dừng |
|---|---|---|---|
| EDA, baseline, evaluation, dashboard, tests | Laptop local | Đủ RAM/CPU; có artifact và môi trường sẵn | Không cần cloud. |
| Causal Forest preflight 20% → 30% | Kaggle Free, sau khi đọc RAM/CPU live | `CausalForestDML` chịu tải chủ yếu CPU/system RAM, không tự hưởng lợi từ Kaggle GPU | Dừng nếu peak RAM ≥75% runtime RAM, lỗi OOM, hoặc runtime vượt quota. |
| Causal Forest main tối đa 50% | Kaggle Free **chỉ nếu** cả hai preflight qua | Resource-gated profile: 200 cây, cross-validation 2-fold, inference=False | Nếu 30% không qua gate, giữ release 5-model; không nâng hạ tầng chỉ để đủ model thứ sáu. |
| CLV/BG-NBD/Gamma-Gamma | Laptop local sau release causal | `lifetimes`/`openpyxl` đã có; data vừa với laptop | Không cần GPU. |

Kaggle cung cấp GPU theo quota; GPU chỉ giảm runtime khi implementation sử dụng GPU.
Colab không bảo đảm GPU/RAM cố định, kể cả gói trả phí. Vì vậy Causal Forest phải qua
**preflight đo tài nguyên live**. Nguồn chính thức: [Kaggle GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage),
[Google Colab FAQ](https://research.google.com/colaboratory/faq.html).

---

## 4. Kiểm chứng công thức, metric và nguồn tham khảo

### 4.1 Chuẩn bằng chứng áp dụng

Mỗi công thức trong slide/report phải thuộc đúng một trong ba loại sau:

- **A — Primary/authoritative:** paper gốc, dataset owner hoặc tài liệu tác giả/official docs.
- **B — Implementation-verified:** công thức implementation được đối chiếu với thư viện tham chiếu và có test. Có thể dùng trong demo nhưng phải ghi rõ biến thể/thư viện.
- **C — Assumption/scenario:** input do dự án đặt để mô phỏng quyết định; không phải biến
  quan sát hoặc causal estimate từ dataset.

### 4.2 Sổ đăng ký công thức và claim

| Thành phần | Công thức / nội dung được phép nêu | Căn cứ đã kiểm tra | Cấp | Phạm vi trình bày |
|---|---|---|---|---|
| CATE | `τ(x) = E[Y(1) − Y(0) | X=x]` | Wager & Athey; Künzel et al. | A | “Ước lượng hiệu ứng trung bình có điều kiện”, không phải biết counterfactual của từng người. |
| S-/T-/X-Learner | S: `m(x,1)-m(x,0)`; T: `μ1(x)-μ0(x)`; X theo meta-learner paper | [Künzel et al. (2019)](https://doi.org/10.1073/pnas.1804597116) | A | Nêu thuật toán/assumption; không khẳng định X luôn thắng khi imbalance. |
| Causal Forest | Forest ước lượng heterogeneous effect, có inference dưới assumption của paper | [Wager & Athey (2018)](https://doi.org/10.1080/01621459.2017.1319839) | A | Chỉ claim inference khi run và interval thực tế thành công. |
| Transformed outcome | `Z = Y·(W-p)/[p(1-p)]`, khi assignment propensity `p` đúng thì `E[Z|X=x]=τ(x)` | [scikit-uplift documentation](https://www.uplift-modeling.com/en/latest/user_guide/models/transformed_outcome.html), tham chiếu Athey–Imbens trong tài liệu | B | Dùng metric phụ/diagnostic vì phương sai có thể cao; không dùng một mình để chọn model. |
| Qini curve theo threshold | `Q(t)=Y₁(t)−Y₀(t)·N₁(t)/N₀(t)` | `src/evaluation.py` đối chiếu toàn mảng với `sklift.metrics.qini_curve`; [sklift Qini API](https://www.uplift-modeling.com/en/v0.3.2/api/metrics/qini_curve.html) dẫn Radcliffe | B | Ghi “Qini variant implemented compatibly with scikit-uplift”; không gọi là công thức duy nhất/duy nhất trong paper gốc. |
| Qini score | Diện tích actual trừ random, chuẩn hóa theo perfect trừ random trong implementation `sklift` có `negative_effect=True` | Unit test sai số < `1e-6` so với `sklift.qini_auc_score`; [sklift metrics](https://www.uplift-modeling.com/en/v0.3.2/api/metrics/qini_curve.html) | B | Luôn ghi biến thể/normalization. Không so điểm giữa thư viện/biến thể khác mà không chuẩn hóa. |
| Uplift curve/AUUC | `[(Y₁/N₁)-(Y₀/N₀)]·N`; điểm normalized theo implementation hiện tại | Unit test với `sklift.uplift_curve`/`uplift_auc_score`; sklift trích Devriendt et al. | B | Gọi là metric đối chiếu ranking, không phải revenue/profit. |
| Bootstrap CI | Resample cặp quan sát `(Y,W,score)` cùng index; lấy percentile `α/2` và `1−α/2` của statistic | [Efron & Tibshirani, *An Introduction to the Bootstrap*](https://doi.org/10.1201/9780429246593); mô tả percentile rõ tại [MedCalc](https://www.medcalc.org/en/manual/bootstrap.php) | A/B | Ghi “95% percentile bootstrap CI, 500 resamples, fixed seed”, không gọi là exact/BCa CI. |
| So sánh cặp model | Resample **cùng một index** cho hai score rồi report distribution/CI của `ΔQini` | Pairing là hợp lý vì hai score dùng cùng holdout; code hiện trả p-value heuristic | C (hiện tại) | **Không dùng p-value là bằng chứng chính.** Sprint 1 đổi report sang bootstrap CI của `ΔQini`; chỉ ghi p-value nếu protocol/test chuẩn được bổ sung. |
| Segment customer | CATE dương/âm và độ lớn score thành nhóm vận hành | Quy tắc sản phẩm nội bộ | C | Gọi “operational segments”, không gọi Persuadable/Sure Thing/Lost Cause/Sleeping Dog là observed ground truth. |
| Incremental profit simulator | `incremental conversions × assumed contribution margin − targeted customers × assumed contact cost` | Business scenario do dự án định nghĩa; Criteo không có price/margin/cost | C | Bắt buộc hiển thị input assumption, sensitivity range và nhãn “minh họa, không phải doanh thu quan sát”. |
| BG/NBD | Poisson transaction khi active, Gamma heterogeneity, dropout sau transaction, Beta dropout probability | [Fader et al. (2005)](https://doi.org/10.1287/mksc.1040.0098); [Hardie derivation](https://brucehardie.com/notes/039/bgnbd_derivation__2019-11-06.pdf) | A | Chỉ dùng ở dự án sau causal; kiểm tra temporal holdout và one-time buyer caveat. |
| Gamma-Gamma | Monetary model với assumption frequency–monetary independence; repeat purchase requirement thực hành | [Hardie Gamma-Gamma note](https://www.brucehardie.com/notes/025/gamma_gamma.pdf); [PyMC-Marketing CLV quickstart](https://www.pymc-marketing.io/en/stable/notebooks/clv/clv_quickstart.html) | A/B | Không suy ra gross profit khi chỉ có revenue; kiểm tra assumption trước fit. |
| DR policy value (dự án sau) | Direct/IPW/DR policy evaluation với logged randomized feedback | [Dudík et al. (ICML 2011)](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/), [Athey & Wager (2021)](https://doi.org/10.3982/ECTA15732) | A | Dùng khi có policy outcome/overlap; Qini không thay policy value. |

### 4.3 Những sửa chữa bắt buộc cho narrative hiện có

1. `paired_bootstrap_compare()` hiện tính tỷ lệ bootstrap difference ở mỗi phía của 0 rồi nhân đôi. Đó là một heuristic trong code, không phải test chuẩn đã được chứng minh từ nguồn đang trích. Báo cáo cuối sẽ **ưu tiên 95% CI của chênh lệch Qini** và bỏ ngôn ngữ “p-value xác nhận model A thắng” nếu chưa có protocol chuẩn.
2. Qini/AUUC đã khớp implementation tham chiếu trong ngưỡng sai số của unit test; điều này
   không biến metric thành ground-truth CATE evaluation. Vẫn cần readout theo decile,
   uncertainty, negative control và giới hạn outcome hiếm.
3. Tỷ lệ score âm phải báo theo từng model (release: Response 0%; S 0,38%; T 53,96%;
   X 24,15%; DR 0,65%) và không được gọi là principal-stratum prevalence.
4. Release mới: top 10% theo Response giữ ước tính 72,7% incremental conversion trên holdout; không chuyển thành doanh thu hay uplift production.
5. Cụm “6 model” phải ghi “5 model release; Causal Forest là challenger Sprint 2” cho tới khi artifact Kaggle vượt preflight và được chấm một lần trên holdout.

### 4.4 Link audit: nguồn đã kiểm tra và cách dùng

| Nguồn | Tình trạng | Dùng cho | Không dùng cho |
|---|---|---|---|
| [Criteo AI Lab dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) | Official page, đã kiểm tra | RCT provenance, original dataset context | Schema/row count của file v2.1 local nếu chưa dựa manifest/hash. |
| [UCI Online Retail II](https://doi.org/10.24432/C5CG6D) | Official dataset/DOI, đã kiểm tra | Transaction count/time range, cancellations/missing/wholesale caveats | Randomized treatment, margin hay causal effect. |
| [TFDS Hillstrom](https://tensorflow.google.cn/datasets/catalog/hillstrom) | Official docs, đã kiểm tra | 64k random email/control, two-week `spend` | Long-term CLV. |
| [Künzel 2019](https://doi.org/10.1073/pnas.1804597116) và [Wager–Athey 2018](https://doi.org/10.1080/01621459.2017.1319839) | Primary peer-reviewed, đã kiểm tra | Meta-learner/Causal Forest theory | Claim empirical result của project. |
| [Fader 2005](https://doi.org/10.1287/mksc.1040.0098), [Schmittlein 1987](https://doi.org/10.1287/mnsc.33.1.1), Hardie notes | Primary + author technical notes, đã kiểm tra | CLV assumptions và derivation roadmap | Monetary gross profit nếu lack COGS. |
| [Dudík et al., ICML 2011](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/) và [Athey–Wager 2021](https://doi.org/10.3982/ECTA15732) | Primary, đã kiểm tra | Future policy evaluation | Bypass overlap/identification conditions. |
| [EconML DRPolicyForest](https://www.pywhy.org/EconML/_autosummary/econml.policy.DRPolicyForest.html), [PyMC-Marketing](https://www.pymc-marketing.io/en/stable/notebooks/clv/clv_quickstart.html) | Official implementation docs | API/formula implementation detail | General theory stronger than paper/assumptions. |
| `scikit-uplift` docs/code | Implementation reference, đã cross-check bằng unit test | Exact metric behavior used by repo | Claim source paper stated precisely per threshold nếu paper chưa đọc phần đó. |

**Quy tắc link:** chỉ đưa link primary/official vào report chính; package/tutorial links phải gắn nhãn “implementation documentation”. Bài preprint hoặc link không đọc trực tiếp không dùng làm chứng cứ kết luận. Danh mục nguồn mở rộng đã có tại [`planning/incremental_value_product/08_SOURCE_AUDIT.md`](incremental_value_product/08_SOURCE_AUDIT.md).

---

## 5. Lộ trình 3 sprint cho 5 tuần còn lại

### Sprint 1 — Đóng băng pipeline causal và kiểm chứng kết quả

**Thời gian:** Tuần 2 (sau Tuần 1 đã hoàn tất)
**Mục tiêu sprint:** biến kết quả 5-model hiện có thành một causal release có thể audit; quyết định có/không đưa Causal Forest vào release mà không làm chậm sản phẩm.

| Work package | Cần làm | Cần hiểu/rút ra | Bằng chứng bàn giao / Definition of Done |
|---|---|---|---|
| 1. Reproducibility release | Chạy lại `pytest`; chạy/kiểm tra một train smoke nhỏ; ghi Python/package versions, data hash/schema, command, seed, split vào manifest | Reproducibility là ability rerun cùng specification, không chỉ có notebook | `output/run_manifest.json`, command trong README, test pass; artifact paths trace được. |
| 2. Formula/narrative correction | Sửa README/docs/report: 5 model completed, Causal Forest pending; p-value paired bootstrap không là claim chính; segments là operational | Phân biệt model score, causal estimand, metric và business claim | Checklist đối chiếu claim với artifact; không ghi “6 model đã xong” hoặc principal strata như nhãn quan sát. |
| 3. Causal Forest decision gate | Chạy 20% rồi 30% trên Colab theo `docs/KAGGLE_RUNBOOK_COMPLETE.md`; log wall time, peak RAM, errors, alignment với holdout | GPU availability khác system-RAM; benchmark/feasibility là experiment | `benchmarks/logs` + result một trong hai: (a) valid CATE 50%, hoặc (b) documented decision release 5-model. |
| 4. Final comparison | Nếu CF valid: `build_comparison.py`; nếu không: đóng bảng 5-model. Dùng Qini/AUUC, percentile CI; bổ sung CI cho `ΔQini` với same-index resampling thay vì headline p-value | Metric comparison cần paired evaluation và uncertainty | `output/qini_comparison.csv`, curves, table with metric definition/CI; không có placeholder. |
| 5. Decision-oriented evaluation | Tạo decile table: population, observed treated/control conversion, standardized incremental estimate, cumulative Qini; kiểm tra top-decile narrative đúng artifact | Ranking metric chuyển thành decision evidence, nhưng vẫn offline | `output/decile_policy_table.csv` và chart/summary được link trong report. |

**Tiêu chí hoàn thành Sprint 1:**

- Một người khác có thể đọc README → lấy data đúng version → chạy test → tái sinh baseline/artifact theo command rõ ràng.
- Có một bảng comparison chính thức (**5 hoặc 6 model**, số model là kết quả thực tế chứ không bị ép).
- Không còn claim không có nguồn/công thức rõ hoặc result chưa tồn tại.

**Rủi ro và cách cắt scope:** Nếu Causal Forest không qua gate RAM/quota, đóng release với
năm model local, ghi log tài nguyên và giới hạn compute, rồi chuyển thời gian sang policy
table và product demo.

---

### Sprint 2 — Chuyển model thành quyết định và dashboard demo

**Thời gian:** Tuần 3–4
**Mục tiêu sprint:** biến CATE ranking thành màn hình ra quyết định có assumption minh bạch, thay vì chỉ trình bày biểu đồ thuật toán.

| Work package | Cần làm | Cần hiểu/rút ra | Bằng chứng bàn giao / Definition of Done |
|---|---|---|---|
| 1. Decision contract | Chọn champion theo metric/uncertainty đã khóa; định nghĩa policy `target top-k%`; định nghĩa input scenario `contact_cost`, `conversion_value`/contribution margin (không phải data Criteo) | Score cao không tự động là policy tốt; policy cần budget/cost | `docs/DECISION_CONTRACT.md` (tạo mới): objective, treatment rule, data field, metric, assumptions, exclusions. |
| 2. Break-even sensitivity | Tính incremental conversion theo decile/threshold; hiển thị cost/value range và break-even boundary | Khi outcome không có monetary value, chỉ có scenario analysis | `output/policy_sensitivity.csv`; mọi monetary KPI có nhãn “assumption scenario”. |
| 3. Dashboard | Dùng artifact precomputed để dashboard load nhanh: model comparison, Qini, decile table, target slider, scenario inputs, limitations/data provenance panel | Tách rõ KPI, uncertainty, causal caveat, artifact boundary và trạng thái UI | Dashboard chạy local; screenshot + GIF/video 60–90 giây; không hard-code result không trace được. |
| 4. Data-quality/decision guard | Warning khi user chọn cost/value ngoài range; hiển thị sample/split/run ID; không cho export “revenue actual” | UI phải phân biệt observed metric với scenario input | Visible warning panel; export CSV includes run ID + assumption columns. |
| 5. Mini acceptance test | Test dashboard artifact schema and manually replay 3 scenario: low cost, high cost, no-target/random | Kết quả phải nhất quán với công thức ở từng scenario | `report/archive/week-03-04-demo-checklist.md` với screenshot/expected result. |

**Dashboard minimum viable layout:**

```text
Run / data provenance ── Champion & uncertainty ── Target top-k% control
Qini + decile curve    ── Incremental conversion estimate ── Assumption panel
Model comparison       ── Segment/decile table              ── Limitations/export
```

**Tiêu chí hoàn thành Sprint 2:** người xem không biết causal inference vẫn trả lời được: “nên target bao nhiêu phần trăm, bằng chứng offline là gì, chi phí nào thì policy không còn hợp lý, và con số nào chỉ là giả định?”

**Rủi ro và cách cắt scope:** Không xây FastAPI/Streamlit từ đầu nếu dashboard HTML hiện có đáp ứng interaction. Ưu tiên demo không lỗi và provenance rõ hơn kiến trúc phức tạp.

---

### Sprint 3 — Kiểm chứng release và mở lối probabilistic CLV

**Thời gian:** Tuần 5–6
**Mục tiêu sprint:** tạo package có thể chạy lại và kiểm tra độc lập; chốt plan có căn cứ
cho phase probabilistic mà không nhồi một dự án thứ hai vào deadline.

| Work package | Cần làm | Cần hiểu/rút ra | Bằng chứng bàn giao / Definition of Done |
|---|---|---|---|
| 1. Release engineering tối thiểu | Thêm `Dockerfile` hoặc hướng dẫn one-command chạy dashboard; test clean environment; thêm CI tối thiểu chạy tests/lint nếu thời gian cho phép | Demo cần artifact, dependency manifest và entrypoint | `docker compose up`/equivalent chạy được hoặc runbook clean-env đã kiểm chứng; badge/log CI nếu có. |
| 2. Final report | Viết theo Research Question → Data/identification → Methods → Results → Decision simulation → Limitations → Reproduction | Báo cáo phải thể hiện được lập luận và bằng chứng, không chỉ số lượng model | `report/final-report.md`, tất cả number link về output/run ID; source table từ mục 4. |
| 3. Tài liệu và demo | README 5-minute path, architecture diagram nhỏ, 60–90s demo video và 6–8 slides | Người đọc cần theo được problem → evidence → decision → limitation | README, video link/path và slide deck; mọi số liệu truy được về artifact. |
| 4. Quality gate | Run tests, link check internal, test dashboard demo, peer/mentor đối chiếu claim với evidence, kiểm tra README với artifacts | Giới hạn phải xuất hiện trong artifact, không chỉ được nói khi thuyết trình | `report/release-checklist.md` all P0 items pass; known limitations visible. |
| 5. Phase-2 handoff | Không viết CLV model vội. Chốt data card Online Retail II, temporal split, BG/NBD/Gamma-Gamma assumptions, Hillstrom monetary causal contrast, iCLV evaluation protocol | CLV prediction và causal incremental value là hai estimand khác nhau | Link tới `planning/incremental_value_product/` + một 1-page phase-2 backlog, không có fake result. |

**Tiêu chí hoàn thành Sprint 3 / final release:**

- Repository có thể chạy theo runbook trên máy khác hoặc container.
- Demo cho thấy kết quả, uncertainty, data provenance và assumptions trong dưới 2 phút.
- Báo cáo nói chính xác model nào đã chạy; figure/table không placeholder; tất cả link core còn truy cập được.
- Bản release nêu rõ quy mô dữ liệu, số baseline, evaluation protocol, quyết định và giới hạn.

---

## 6. Lịch theo tuần và checkpoint mentor

| Tuần | Trọng tâm | Deliverable gửi mentor | Câu hỏi cần mentor phản biện |
|---|---|---|---|
| 1 — đã qua | EDA, randomization diagnostic, 5 baseline, metric tests | `report/archive/week-01-*`, benchmark, result table | Response có Qini cao nhất; policy metric có phù hợp decision objective không? |
| 2 | Freeze data/run, Causal Forest preflight, correct claims, final 5/6 comparison | Manifest + evidence audit + comparison table | Có chấp nhận release 5 model nếu CF không vượt feasibility gate không? |
| 3 | Decision contract, decile/policy table, first dashboard | Interactive prototype + scenario table | Assumption cost/value và policy `top-k` nên set/đánh giá thế nào? |
| 4 | Dashboard acceptance, sensitivity, user-facing explanation | Demo checklist/video draft | Mức chi tiết kỹ thuật và sản phẩm đã đủ để kiểm tra quyết định chưa? |
| 5 | Docker/runbook/CI, final report/slide draft | Clean-run log + report draft | Claim nào vượt phạm vi evidence hoặc chưa có nguồn? |
| 6 | Release QA, demo recording, phase-2 handoff | Final release package | Quyết định phase sau: CLV baseline trước hay Hillstrom monetary causal policy trước? |

---

## 7. Tiêu chuẩn release kỹ thuật

| Phần | Bằng chứng cần có trong release |
|---|---|
| Dữ liệu và phân tích | Data contract, metric definition, balance/leakage audit, decile table và scenario simulator. |
| Mô hình và đánh giá | Estimand, RCT caveat, baseline comparison, bootstrap CI, negative control và kết quả không cải thiện kèm artifact. |
| Vận hành | Scripts, test suite, manifest, dashboard entrypoint, runbook và Docker/CI nếu thực sự hoàn thành. |

Không ghi “tăng doanh thu X%”, “production-ready” hoặc “CLV optimization” cho release
causal nếu không có online experiment, revenue hoặc production evidence.

---

## 8. Hướng sau causal: probabilistic CLV và causal value, không chồng deadline

Sau khi Sprint 3 release, hướng tiếp theo có tên:

> **Tối ưu hóa Giá trị Khách hàng Tăng thêm do Tác động Nhân quả**
> *(Causal Incremental Customer Value Optimization)*

Chuỗi phát triển đúng thứ tự là:

```text
Online Retail II data contract + temporal split
        → probabilistic CLV baseline (BG/NBD + Gamma-Gamma)
        → held-out calibration / revenue diagnostic
        → Hillstrom randomized monetary policy (short horizon)
        → semi-synthetic/join design được nêu assumption rõ
        → incremental customer value policy + direct/IPW/DR evaluation
```

Lý do không gộp ngay: Online Retail II hỗ trợ behavioral CLV nhưng không có treatment randomization; Hillstrom có treatment/spend nhưng horizon ngắn. Không có dataset nào trong hai nguồn tự nó chứng minh iCLV dài hạn. Nếu kết hợp, phải công khai design liên kết/mô phỏng và sensitivity, không gọi là observed long-term causal revenue.

Tài liệu implementation/research chi tiết cho phase này nằm ở:

- [`planning/incremental_value_product/01_PRODUCT_VISION.md`](incremental_value_product/01_PRODUCT_VISION.md)
- [`planning/incremental_value_product/02_RESEARCH_DATA_METHODS.md`](incremental_value_product/02_RESEARCH_DATA_METHODS.md)
- [`planning/incremental_value_product/10_END_TO_END_EXECUTION_PLAYBOOK.md`](incremental_value_product/10_END_TO_END_EXECUTION_PLAYBOOK.md)
- [`planning/incremental_value_product/11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md`](incremental_value_product/11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md)

---

## 9. Final release checklist

### Khoa học / dữ liệu

- [ ] Manifest có checksum, schema, row count, seed, split, outcome/treatment rate và feature list.
- [ ] Không dùng `visit`/`exposure` như pre-treatment feature cho conversion CATE.
- [ ] Mỗi chart/table có run ID, sample/split và metric definition.
- [ ] Qini/AUUC variants khớp `scikit-uplift`; test pass.
- [ ] Report CI percentile và CI `ΔQini`; không headline heuristic p-value.
- [ ] Causal Forest chỉ xuất hiện nếu có artifact và alignment check; nếu không, ghi trạng thái pending.
- [ ] Monetary numbers có assumption inputs; không gọi là actual revenue/profit.

### Sản phẩm / kỹ thuật

- [ ] `pytest tests/ -v` pass từ clean environment.
- [ ] One-command hoặc Docker runbook mở dashboard được.
- [ ] Dashboard load từ output artifact, không retrain/download implicit.
- [ ] Internal links từ README/report/planning được kiểm tra.
- [ ] Demo video replay được ba scenario và nêu một limitation quan trọng.

### Tài liệu / giao tiếp

- [ ] README có “5-minute path”: problem → screenshot → result → reproduce → limitations.
- [ ] Final report dùng nguồn primary/official; implementation docs được ghi nhãn.
- [ ] Slide có ít nhất: problem, data/identification, model/result, policy demo, limitation/next step.

---

## 10. Tài liệu bắt buộc đọc theo sprint

### Sprint 1 — causal/evaluation

1. Künzel et al., [*Metalearners for Estimating Heterogeneous Treatment Effects using Machine Learning*](https://doi.org/10.1073/pnas.1804597116).
2. Wager & Athey, [*Estimation and Inference of Heterogeneous Treatment Effects using Random Forests*](https://doi.org/10.1080/01621459.2017.1319839).
3. [Criteo Uplift Prediction Dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) và local data manifest.
4. [scikit-uplift Qini API](https://www.uplift-modeling.com/en/v0.3.2/api/metrics/qini_curve.html) và source installed package để hiểu đúng **biến thể implementation**.
5. Efron & Tibshirani, [*An Introduction to the Bootstrap*](https://doi.org/10.1201/9780429246593), phần percentile interval.

### Sprint 2 — policy/product

1. Athey & Wager, [*Policy Learning with Observational Data*](https://doi.org/10.3982/ECTA15732).
2. Dudík et al., [*Doubly Robust Policy Evaluation and Learning* (ICML 2011)](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/).
3. [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml) — data dependencies, baseline-first, training-serving skew.

### Sprint 3 / phase-2 handoff — CLV

1. Fader, Hardie & Lee, [*Counting Your Customers the Easy Way*](https://doi.org/10.1287/mksc.1040.0098).
2. [BG/NBD derivation](https://brucehardie.com/notes/039/bgnbd_derivation__2019-11-06.pdf) và [Gamma-Gamma note](https://www.brucehardie.com/notes/025/gamma_gamma.pdf).
3. [UCI Online Retail II](https://doi.org/10.24432/C5CG6D) data card trước khi clean/model.
4. [Hillstrom TFDS documentation](https://tensorflow.google.cn/datasets/catalog/hillstrom) trước khi nêu monetary causal contrast.

---

## 11. Quyết định cần mentor xác nhận tại checkpoint gần nhất

1. Chấp nhận **quality gate thay vì bắt buộc Causal Forest**: nếu preflight 30% không qua,
   release năm model local và ghi Causal Forest là “không qua resource gate”.
2. Dùng **policy simulator theo assumption** với contact cost và contribution value do user
   nhập; không gọi output là observed incremental profit trên Criteo.
3. Chấp nhận roadmap tách pha: causal release trước; CLV/iCLV sau release, dùng Online Retail II + Hillstrom đúng vai trò dữ liệu.

Nếu ba quyết định này được chấp nhận, phạm vi năm tuần tập trung vào một sản phẩm có
artifact, kiểm thử và demo; ba đề tài có estimand khác nhau không được gộp vào cùng release.
