# Rà soát repository trước lần push đầu tiên — 31/07/2026

## 1. Phạm vi

Rà soát:

- toàn bộ `src/`, `scripts/`, `tests/`, `benchmarks/` và config;
- README, report, docs, planning và model/data card;
- JSON/CSV/HTML/notebook release artifacts;
- liên kết nội bộ và 70 URL ngoài trong tài liệu hiện hành;
- secret/credential, absolute path và kích thước file sẽ đưa vào Git;
- remote/branch Git trước commit đầu tiên.

Raw Criteo và các mảng prediction `.npy/.npz` không được đưa vào Git. Các file đó có thể tái
tạo từ script/config và làm repository tăng khoảng 379 MB.

## 2. Kết quả kiểm tra

| Hạng mục | Kết quả |
|---|---|
| Python compile | pass |
| Pytest | 51/51 pass |
| Dashboard browser acceptance | 11/11 pass |
| JSON/notebook/HTML parse | pass |
| Internal Markdown links | 56 link, 0 broken |
| CSV duplicate header | 0 sau khi sửa Sprint 1 arm summary |
| External URL | 70 URL phương pháp, dữ liệu và implementation trong tài liệu hiện hành |
| Dependency consistency | `pip check`: không có broken requirement |
| Secret/path scan | không thấy API key/private key/password; absolute runtime path đã loại khỏi release manifest hoặc ignore |
| Trackable repository size | khoảng 1,36 MB/117 file hiện hành |

Một số DOI/publisher có thể trả 403 hoặc 429 cho automated checker dù mở được qua resolver
hoặc trang proceedings. Các trường hợp này không được tự coi là link hỏng. Các nguồn
phương pháp chính đã được kiểm tra qua DOI, proceedings, journal page hoặc official
documentation khi lập research plan.

Pytest còn 13 warning từ dependency/environment:

- SHAP/Matplotlib pending deprecation;
- scikit-learn rename `force_all_finite`;
- joblib không đọc được physical-core count trong môi trường hiện tại;
- SciPy optimize warning ở LogisticRegression;
- sandbox không cho pytest tạo `.pytest_cache`.

Không warning nào làm test fail. Chúng cần được theo dõi khi nâng package nhưng không thay
đổi kết quả release hiện tại.

## 3. Vấn đề đã sửa trong lần rà soát

### Data contract

`validate_criteo_schema()` trước đây:

- truy cập thẳng `df[FEATURES]`, nên có thể raise `KeyError` thay vì trả audit result khi
  thiếu một feature;
- ép binary values sang `int`, nên giá trị sai như `0.5` có thể bị biến thành `0` và qua
  contract.

Đã sửa để báo missing/non-numeric feature và kiểm tra đúng giá trị binary gốc. Đã thêm hai
regression test.

### Artifact CSV

`arm_outcome_summary.csv` trước đây dùng pandas MultiIndex header, tạo ba cột cùng tên
`conversion`, `visit`, `exposure`. Đã đổi generator sang tên phẳng:

- `row_count`;
- `conversion_rate`, `conversion_count`;
- `visit_rate`, `visit_count`;
- `exposure_rate`, `exposure_count`.

Artifact đã được tái sinh từ raw file có SHA-256
`2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`.

### Model-selection export

Dashboard exporter trước đây chỉ đưa Response/X-Renormalized/X-Calibrated vào tập chọn
champion và loại T-LocalExact mà không có rule tổng quát. Đã đổi sang toàn bộ candidate có
Qini/AUUC hữu hạn. Kết quả vẫn chọn Response trên validation.

### Legacy comparison scripts

`train_baselines.py` và `build_comparison.py` trước đây:

- đặt tên bootstrap tail heuristic là `p_value`;
- dùng CI riêng của Qini để tạo cột `significant`;
- đổi dấu score thành nhãn Persuadable/Sleeping Dog.

Đã chuyển comparison sang paired percentile CI của `ΔQini`; đổi bucket thành
`Predicted positive effect`, `Predicted negative effect`, `Near-zero score`; Response không
được dùng để tạo CATE score-sign diagnostic.

### Data provenance và interpretation

Data card đã bổ sung:

- Criteo public benchmark được subsample không đồng đều vì riêng tư;
- ATE/Qini của public sample không suy ngược thành incrementality campaign gốc;
- `f0`–`f11` ẩn danh/randomly projected nên không có business semantics;
- `exposure` không phải baseline feature.

Model card/report đã ghi thêm:

- confirmation hiện là retrospective cho vòng model sau;
- random top-k hiện có một fixed seed;
- CI của random comparison chưa tích hợp biến thiên qua nhiều random-policy seed.

### Git hygiene

`.gitignore` đã loại:

- raw data và virtual environment;
- `.npy/.npz` prediction arrays;
- smoke/benchmark intermediate directories;
- ba artifact root lịch sử đã được thay bằng release có version;
- runtime logs và test cache.

Final CSV/JSON/PNG/HTML release evidence vẫn được track.
`.gitattributes` khóa LF cho source/document và đánh dấu PNG là binary để diff ổn định
giữa Windows và cloud Linux.

Notebook Colab fallback cũng đã được đổi từ tail heuristic gắn nhãn `p_value` sang paired
CI của `ΔQini`, không còn chọn champion trên holdout test và không gán dấu score thành
principal strata. Trang giải thích HTML đã được bổ sung cấu trúc document chuẩn
`doctype/html/head/body`.

## 4. Đánh giá thiết kế causal hiện tại

Các điểm đạt:

- estimand và outcome được ghi rõ;
- không dùng `visit`/`exposure` làm feature;
- Sprint 1 và Sprint 2 dùng split/hash có thể tái lập;
- CATE metric được đối chiếu `scikit-uplift`;
- model difference dùng paired bootstrap CI trong release;
- monetary output luôn ghi là scenario;
- Causal Forest chưa chạy cloud được ghi `pending`.

Các giới hạn còn lại:

1. Sprint 2 confirmation đã được xem; không còn là untouched test cho model mới.
2. Qini có variance cao với rare binary outcome; cần RATE/AUTOC, outcome adjustment và
   pROCini/PUC trước khi mở rộng search.
3. Random comparator cần expected-random estimator và multi-seed sensitivity.
4. Chưa có external randomized validation.
5. Causal Forest 20/30/50 Kaggle chưa chạy.
6. Repository chưa có license cho code. Không tự thêm license vì đây là quyết định quyền
   phát hành của chủ repository.
7. Full integration tests cần raw Criteo; chưa có lightweight CI workflow tách synthetic
   unit tests khỏi data-required tests.

Kế hoạch xử lý 1–5 nằm tại
[`../planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md`](../../planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md).

## 5. Nguồn mới ảnh hưởng trực tiếp đến kế hoạch

- Mahajan et al., ICLR 2024: surrogate metric selection và causal ensembling.
- Lan & Syrgkanis, AISTATS 2024: causal Q-aggregation với doubly robust loss.
- Yadlowsky et al., JASA 2025 issue: RATE/AUTOC cho treatment prioritization.
- Bokelmann & Lessmann, EJOR 2024: variance reduction cho uplift evaluation trên RCT.
- Verbeken et al., JMLR 2025: pROCini.
- Zhu et al., ICML 2025: PUC/PUL/PTONet.
- Vanderschueren et al., ICML 2025: AutoCATE evaluation–estimation–ensembling pipeline.
- Zheng et al., AAAI 2026: delayed feedback; đã xác định không áp dụng vì Criteo thiếu
  event time/horizon.

Direct links, phạm vi đọc và quyết định áp dụng/không áp dụng nằm trong mục 10 của plan.
