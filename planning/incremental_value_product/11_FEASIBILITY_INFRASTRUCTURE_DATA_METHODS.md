# 11 — Tính khả thi: Hạ tầng, Dữ liệu và Phương pháp (Feasibility: Infrastructure, Data and Methods)

**Assessment date:** 2026-07-29. Đây là gate trước khi đầu tư thời gian/tiền vào remote compute.
Kết luận ngắn: **dự án khả thi trong 5 tuần với laptop hiện có và free tier nếu scope đúng**. Không cần
mua Colab Pro ngay. Nút thắt duy nhất là CausalForestDML 50% trên Criteo; nó là optional challenger,
không được làm trễ data/product/release P0.

## 1. Kết luận thực thi

| Hạng mục | Khả thi? | Nơi chạy khuyến nghị | Quyết định |
|---|---|---|---|
| Causal baseline hiện có, test, EDA sample | Có | Laptop local | Giữ local |
| Online Retail II cleaning, SQL/DuckDB, RFM, BG/NBD/Gamma-Gamma | Có | Laptop local CPU | P0 local |
| Rolling temporal CLV validation | Có | Laptop local; chạy overnight nếu cần | P0 local |
| PyMC/Bayesian challenger | Có nhưng giới hạn | Local trên sample hoặc Colab CPU | P1, time-box |
| Criteo CausalForestDML ≤10% dev run | Có thể | Local chỉ khi RAM rảnh đủ; ưu tiên remote | Dev verify, không final |
| Criteo CausalForestDML 20–30% | Có điều kiện | Colab high-memory nếu cấp được | Chỉ sau preflight |
| Criteo CausalForestDML 50% | Không qua local resource gate hiện tại | Cloud runtime chỉ khi RAM live qua preflight | Optional challenger |
| Kaggle free GPU cho CausalForestDML | Không phải lựa chọn chính | Không dùng để giải quyết RAM | GPU không phải bottleneck |
| Streamlit app, Docker, CI, FastAPI thin API | Có | Laptop + Streamlit Community Cloud/Docker | P0 product |

## 2. Danh mục đã kiểm tra trong workspace (Inventory)

### Laptop/môi trường chạy local (Laptop/Local Runtime)

| Thành phần | Kết quả đo được | Hàm ý |
|---|---:|---|
| CPU | 12 logical CPUs | Đủ cho local development/CLV; không kỳ vọng full CausalForest nhanh |
| System RAM | 15.19 GB total; 5.73 GB available lúc audit | Không chạy CausalForest 20–50% ổn định; đóng bớt app vẫn chỉ dùng dev sample |
| GPU | NVIDIA GeForce RTX 3050 Laptop, 4 GB VRAM | Hữu ích cho code GPU-compatible riêng; không thay system RAM và current CausalForest script không dùng GPU |
| Python | 3.12.10 | Khớp môi trường causal hiện có |
| Cách đo | `os/psutil` + `nvidia-smi` | Re-run trước job nặng; WMI bị sandbox chặn nên không dùng làm nguồn đo |

### Dữ liệu local (Local Data)

| File | Tồn tại / kích thước | Schema/quality đã xác minh | SHA-256 |
|---|---:|---|---|
| `criteo-research-uplift-v2.1.csv.gz` | 311,422,618 bytes (296.98 MiB) | 16 columns: `f0–f11`, `treatment`, `conversion`, `visit`, `exposure`; local code/test dùng 13,979,592 rows | `2716E1BF0FD157A93B5BF86924D9088419DFBAC2022C6CD90030220634F616DC` |
| `online_retail_II.xlsx` | 45,622,278 bytes (43.51 MiB) | 2 sheets: 525,462 + 541,911 rows including headers = **1,067,371** transaction rows; columns Invoice/StockCode/Description/Quantity/InvoiceDate/Price/Customer ID/Country | `BCBE73B35F5B7BABF197FB0CB983A11F5D9FF929078D4AA53D171B1F2DF2E980` |
| Hillstrom | Chưa có local | Phải download/version/hash trước Day 13 | — |

### Dependency tương lai chưa có trong `.venv` (Future Dependencies)

| Package | Trạng thái audit | Khi cần |
|---|---|---|
| `lifetimes`, `openpyxl` | Có | BG/NBD/Gamma-Gamma + xlsx |
| `pymc-marketing` | Chưa có | Week 2 Bayesian challenger, optional |
| `pyarrow` | Chưa có | P0: parquet artifact/cache |
| `duckdb` | Chưa có | P0: DA SQL marts local |
| `streamlit` | Chưa có | P0: dashboard Week 4 |
| `fastapi`, `pydantic` | FastAPI chưa có | Conditional AI Engineer extension |

Không cài toàn bộ ngay. Tạo optional dependency groups, lock environment, rồi chỉ cài group của phase
đang làm. Điều này giảm conflict giữa causal environment và Bayesian/app dependencies.

## 3. Chính sách compute từ xa (Remote Compute): Kaggle, Colab và quyết định chi tiền

### Điều kiện dữ liệu cần ghi trong báo cáo

- Kaggle công bố quota GPU theo tuần (30 giờ hoặc thay đổi theo demand) và nhấn mạnh GPU chỉ tăng tốc
  libraries dùng GPU; pandas/scikit-learn không tự nhanh hơn. [Kaggle official docs](https://www.kaggle.com/docs/efficient-gpu-usage)
- Colab free/paid không cam kết GPU type, memory profile, runtime duration hay availability; paid tăng
  compute availability theo compute-unit balance chứ không cấp hardware cố định. [Colab FAQ](https://research.google.com/colaboratory/faq.html)
- `CausalForestDML` trong script hiện tại là workload CPU/system-RAM. RTX 3050 4 GB hoặc Kaggle P100
  không giải quyết peak RAM của pandas split + forest fitting.

### Quy trình không tốn tiền trước

1. **Local:** mọi test, preprocessing, baseline, CLV và app dùng local.
2. **Kaggle free:** chỉ dùng khi notebook cần session độc lập hoặc GPU-compatible experiment khác; bật GPU
   chỉ khi code thực sự dùng nó. Không chọn Kaggle chỉ để chạy current causal forest.
3. **Colab free:** thử runtime CPU/high-memory nếu UI cấp; chạy remote preflight dưới đây.
4. **Colab paid/Pro/Pay-as-you-go:** chỉ mua khi 30% preflight thành công nhưng 50% cần để chốt causal
   challenger và free tier không cấp đủ RAM. Kiểm tra `psutil.virtual_memory()` sau khi runtime khởi động;
   dừng nếu profile không đạt. Không mua vì giả định “Pro = 51 GB”.
5. **Dedicated cloud:** chỉ cân nhắc khi muốn guaranteed hardware; vượt scope portfolio 5 tuần và không
   cần thiết cho v1.0.

### Giao thức chạy thử Causal Forest (Causal Forest Preflight Protocol)

| Step | Fraction | Điều cần đo | Chỉ đi tiếp nếu |
|---|---:|---|---|
| P1 | 10% | wall time, peak RAM, output schema/Qini smoke | run hoàn tất; peak RAM < 60% total |
| P2 | 20% | như trên; comparison với baseline 20% | peak RAM < 65%; no OOM/swap |
| P3 | 30% | như trên; variance/stability | peak RAM < 70%; runtime còn trong session budget |
| P4 | 50% | final comparable run | runtime có **>=32 GB system RAM** và predicted headroom; output persist ngay |

Benchmark nội bộ hiện có: 20% = 36.7 phút / 8.2 GB; 30% ≈57 phút / 13 GB; 50% ≈90 phút / 24 GB.
Số 30%/50% là extrapolation từ 20%, nên preflight mới là authority. Persist `cate`, holdout metadata,
stdout log và `psutil` samples ra Drive/artifact storage ngay sau mỗi run vì runtime có thể kết thúc.
**Lưu ý implementation hiện tại:** `train_causal_forest.py` ghi fixed filenames trong `output/cate/`; khi
preflight nhiều fraction, archive output vào folder có `frac`/timestamp ngay sau run hoặc thêm `run_id`
trước khi chạy batch. Không để 30% vô tình ghi đè artifact 20%/50%.

### Quy tắc scope-out cho Causal Forest (Scope-out Rule)

Nếu P2/P3 không pass sau hai remote runtime attempts, release `causal-v0.1` với 5 baselines đã có và ghi:

> “Causal Forest was not included in the final comparison because available memory did not support a
> like-for-like holdout run; no cross-sample performance claim is made.”

Đó là tốt hơn chạy forest trên split khác rồi gắn vào bảng final như thể công bằng.

## 4. Tính khả thi dữ liệu và cổng chất lượng (Data Feasibility and Quality Gates)

### Criteo Uplift v2.1 local

**Phù hợp với:** RCT/binary causal uplift, ranking Qini/AUUC, rare-outcome learning, reproducible CATE
benchmark.

**Thuộc tính dữ liệu:** randomized incrementality benchmark; local file có treatment/conversion/visit và
12 covariates cho code hiện có. Original dataset page mô tả benchmark gốc khác version local, vì vậy
manifest/hash trong bảng trên là bắt buộc. [Criteo source](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)

**Không đủ cho:** customer identity dài hạn, transaction history, revenue/margin, treatment cost, iCLV.

**Gates:**

- [ ] Verify schema/rates/hash trước mỗi final run.
- [ ] Randomization diagnostics (propensity AUC/balance) và treatment rate đúng expected.
- [ ] Không dùng `exposure`, `visit` hay feature sau assignment để predict conversion CATE.
- [ ] Không join customer-level với Online Retail II.

### Online Retail II

**Phù hợp với:** non-contractual transaction forecasting, RFM, cohort behavior, rolling temporal CLV
validation, data-quality/SQL portfolio.

**Thuộc tính dữ liệu:** UCI ghi 1.067.371 transactions trong hai năm, UK online retailer, có invoice/time/customer
and unit price; đủ trường dữ liệu cho data engineering và forecasting.
[UCI source](https://doi.org/10.24432/C5CG6D)

**Rủi ro chất lượng/diễn giải:** UCI nêu missing values, cancellation invoices (`C` prefix) và nhiều
wholesale customers; workbook local dùng aliases `Invoice`, `Price`, `Customer ID` thay vì canonical labels.
Dataset không có COGS, campaign, randomized assignment hay cost.

**Gates:**

- [ ] Freeze mapping column aliases → canonical schema.
- [ ] Report missing Customer ID, cancellation/returns, non-positive quantity/price, duplicates, date range.
- [ ] Build `net_revenue` with explicit return rule; compare raw/net/wholesale sensitivity.
- [ ] Use time split, never random transaction split.
- [ ] Call output `forecasted revenue/CLV`, not observed CLV or margin unless a versioned margin assumption is input.

### Hillstrom

**Phù hợp với:** causal monetary policy on RCT data — email treatment/control, `spend`, `visit`,
`conversion` over observed window.

**Thuộc tính dữ liệu:** 64k customers, ba randomized arms và monetary outcome `spend`.
[TFDS source](https://tensorflow.google.cn/datasets/catalog/hillstrom)

**Rủi ro:** outcome window hai tuần; data không chứng minh long-term retention/CLV. Ba arms nghĩa contrast
phải freeze trước analysis.

**Gates:**

- [ ] Download source, record hash/license/schema, create data card.
- [ ] Choose Mens-vs-control or Womens-vs-control before metric/model selection.
- [ ] Use known randomized propensity; report arm counts and overlap.
- [ ] Headline says incremental two-week spend/value, never lifetime value.

### Semi-synthetic longitudinal RCT

**Vai trò đúng:** integration/unit test cho iCV, oracle policy/regret, sleeping dogs, retention/margin
trade-off. **Không dùng để:** thay thế evidence từ campaign đã triển khai.

**Gates:** seed + DGP config, potential outcomes stored, negative control, truth recovery tests, label
`semi-synthetic` in every UI/report artifact.

## 5. Phương pháp: đánh giá phù hợp và điều kiện dùng (Method Assessment)

| Thành phần | Đánh giá | Điều kiện bắt buộc | Không được claim |
|---|---|---|---|
| Response/S/T/X/DR learner trên Criteo | Phù hợp | common holdout, RCT propensity, rare-outcome diagnostics | conversion uplift = revenue uplift |
| Causal forest | Phù hợp nhưng resource-heavy | same holdout; remote preflight; report CPU/RAM | GPU làm model valid/nhanh hơn; forest phải thắng baseline |
| BG/NBD | Phù hợp làm fast baseline | continuous non-contractual repeat purchases; temporal validation | causal treatment effect |
| Gamma-Gamma | Phù hợp có điều kiện | repeat buyers; frequency–monetary diagnostic; revenue definition | gross profit nếu thiếu COGS |
| Bayesian/Pareto NBD | Challenger hữu ích, không P0 | convergence, posterior predictive/interval validation, time budget | “Bayesian tốt hơn” chỉ vì có interval |
| Hillstrom monetary CATE | Phù hợp short horizon | pre-specified binary contrast; zero/skew-aware metric; bootstrap | iCLV/retention dài hạn |
| Direct iCV policy | Phù hợp trên Hillstrom horizon + semi-synthetic | cost/horizon frozen; direct/IPW/DR heldout evaluation | Causal CLV ngoài observed horizon |
| `conversion CATE × predicted CLV` | Baseline heuristic tốt | label strong assumptions; compare in ablation | iCLV ground truth |
| Projected incremental CLV | P2 research only | explicit extrapolation model + uncertainty/sensitivity | headline v1.0 business result |

## 6. Kế hoạch môi trường và kiểm thử tối thiểu (Environment Plan and Minimum Tests)

### Nhóm dependency (Dependency Groups)

```text
.[causal]    pandas numpy scipy lightgbm econml scikit-uplift
.[clv]       lifetimes openpyxl pyarrow duckdb
.[bayesian]  pymc-marketing arviz
.[app]       streamlit pydantic
.[api]       fastapi uvicorn
.[dev]       pytest ruff pre-commit
```

Use Python 3.12 only after lock/CI verifies all groups. Bayesian group is isolated because its dependency
solver/runtime risk must not break causal release.

### Kiểm thử khả thi tối thiểu trước mỗi phase (Minimum Feasibility Tests)

| Phase | Test |
|---|---|
| Causal remote | preflight fraction + memory/time log + output compatibility |
| CLV | xlsx loader, canonical schema, temporal leakage, RFM invariants, benchmark tolerance |
| Causal monetary | treatment-arm balance, known-propensity, policy cost/budget, DR evaluation separation |
| Semi-synthetic | seed determinism, stored truth, no-effect control, oracle dominance |
| App | artifact schema, scenario validation, export reconciliation, Docker health, CI smoke |

## 7. Khuyến nghị cuối (Final Recommendation)

1. **Không mua Colab Pro hôm nay.** Bắt đầu C1–Week 2 local; đó là phần tạo portfolio value lớn nhất.
2. **Causal forest:** use free Colab preflight first. Nếu free/paid profile không đủ RAM, scope out có lý do
   và tiếp tục roadmap; không dùng Kaggle GPU làm workaround giả.
3. **Ưu tiên đầu tư:** `pyarrow + duckdb + streamlit` cho P0; PyMC-Marketing và FastAPI sau khi baseline/
   dashboard green.
4. **Data strategy giữ nguyên là đúng:** Criteo = causal binary benchmark; Online Retail II = probabilistic
   forecast; Hillstrom = real short-horizon monetary RCT; semi-synthetic = integration truth. Không dataset
   nào trong scope hiện tại cho phép claim empirical long-term incremental CLV, và đó là limitation nên nói
   trực tiếp trong limitation để người đọc xác định phạm vi của kết quả.

Các nguồn platform/dataset/method đã được đăng ký trong `08_SOURCE_AUDIT.md` với scope claim cụ thể.
