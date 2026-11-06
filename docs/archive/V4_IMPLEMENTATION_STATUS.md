# Trạng thái triển khai V4 — vòng 1 (phiên 1–10)

> **Đã lỗi thời cho trạng thái hiện tại.** Vòng 2 nằm ở [VERIFICATION_V4_1.md](VERIFICATION_V4_1.md); vòng 3 (21/09/2026, R03–R10 và đợt bất đối xứng) nằm ở [STAGE_LOG.md](STAGE_LOG.md) S21–S36, và bản đối chiếu kế hoạch hiện hành ở [RESEARCH_READINESS.md](RESEARCH_READINESS.md) §1. Tài liệu này giữ nguyên như một bản ghi lịch sử của vòng 1 và **không** được đọc như trạng thái hôm nay.

Ngày: 20/09/2026. **Vòng 2 (21/09/2026) nằm ở [VERIFICATION_V4_1.md](VERIFICATION_V4_1.md)**: tái hiện các số ở đây, đóng G01/G02/G03/G04/G05/G07 kèm test A01–A09/A11/A13, mở rộng bộ kiểm chứng lên 24 mutation, thêm `evidence`, `allocation` và decision console. Tài liệu này giữ nguyên trạng thái vòng 1, không viết lại.

Tài liệu này ghi những gì đã **thực sự chạy được** trong vòng triển khai đầu tiên của [kế hoạch V4](DEVELOPMENT_PLAN_V4.md) §12, đối chiếu với backlog §8. Nó không thay [DEVELOPMENT_PLAN_V4.md](DEVELOPMENT_PLAN_V4.md) hay [EXPERIMENT_DESIGN_V4.md](EXPERIMENT_DESIGN_V4.md); hai tài liệu đó vẫn là thiết kế.

Nguyên tắc: phần lớn công việc vòng này là **cổng tính đúng (P0)**, không phải kết quả nghiên cứu. Không có claim business nào mới. Xem [CLAIM_LEDGER_V4.md](../CLAIM_LEDGER_V4.md) cho phân loại bằng chứng.

## 1. Mười phiên đầu — trạng thái

| Phiên | Công việc theo kế hoạch | Trạng thái | Sản phẩm |
|---|---|---|---|
| 1 | Inventory evidence, claim ledger observed/conditional/planned | xong | [CLAIM_LEDGER_V4.md](../CLAIM_LEDGER_V4.md) |
| 2 | Khóa một problem contract, endpoint, BAU; ghi open questions | xong | `configs/problem_contracts.toml`, `src/telco_churn/problem_contract.py` |
| 3 | Resolve Orange audit trong phạm vi nguồn kiểm được; xác định fallback | xong | `src/telco_churn/assignment_audit.py`, `reports/v4/ORANGE_ASSIGNMENT_AUDIT.md` |
| 4 | Freeze data-role registry và immutable confirmation policy | xong | `DataRoleRegistry` trong `problem_contract.py` |
| 5 | Tiny reward/action fixtures với bảng expected value độc lập | xong | `src/telco_churn/economics.py` |
| 6 | Paired policy contrast và identical-policy test | xong | `src/telco_churn/policy_comparison.py` |
| 7 | Time-zero/maturity contract trên relational tiny fixture | xong | `src/telco_churn/outcome_adjudication.py` |
| 8 | Train-fitted preprocessing và batch invariance (Q04) | xong | sửa `CatBoostFrameClassifier` trong `uplift.py` |
| 9 | Runner failure propagation + executable protocol checks | xong | `src/telco_churn/research_runner.py`, `scripts/run_research.ps1` |
| 10 | Inference smoke, profiling, scope checkpoint | xong | `src/telco_churn/inference_smoke.py`, `reports/v4/inference_smoke.json` |

Backlog: **V4-01, V4-02, V4-03 (P0) đã có code và test**. V4-05 mới có phần reward/ledger, chưa có economics stress trên dữ liệu thật. V4-04, V4-06 đến V4-10 vẫn `PLANNED`.

## 2. Các cổng mới và điều chúng chặn

| Module | Chặn điều gì | Mutation liên quan |
|---|---|---|
| `problem_contract.py` | Feature cutoff sau `t0`; assignment/follow-up lệch `t0`; unknown outcome thành non-event; cohort hậu-assignment không khai báo negative control; bundle revision ghi đè lịch sử | Q13, Q18 |
| `outcome_adjudication.py` | Immature/censored/conflict thành 0; event trước `t0` vào baseline; delivered-only làm mất ITT denominator; maturity lệch giữa các arm | Q06, Q07 |
| `policy_comparison.py` | Contrast của hai policy giống nhau có SE dương; action không có support được score bằng imputation; sampling bỏ inclusion weight; customer-months tính như account độc lập | Q09, Q10, Q11, Q12 |
| `economics.py` | Posting id lặp; `(account, action, kind)` lặp không khai báo; overhead lẫn vào incremental reward; assumed cost bị gọi là actual | Q05, Q08 |
| `integrity_gates.py` | Fact publish muộn hơn `t0`; cột cấm đi qua rename/join; capacity/cooldown vỡ ở biên kỳ; bundle lệch contract | Q03, Q14, Q16, Q18 |
| `research_runner.py` | Subprocess exit khác 0 mà runner báo success; stage thiếu artifact khai báo | Q17 |

Quy tắc chung: một cổng fail thì kết quả của stage đó **không được xuất ra như bằng chứng**. `research_runner` và `run_research.ps1` cùng thực thi quy tắc này.

## 3. Bộ kiểm chứng E28

`python -m telco_churn.challenge_suite` sinh [reports/v4/CHALLENGE_SUITE_REPORT.md](../../reports/v4/CHALLENGE_SUITE_REPORT.md).

18/18 mutation Q01–Q18 có fixture sạch và bản lỗi riêng ở vòng 1: **15/15 critical mutation được phát hiện, 0 false block**. Vòng 2 thêm Q19–Q24 cho các khoảng trống G01–G05 và G07; con số hiện hành là **21/21 critical trên 24 case** — xem [VERIFICATION_V4_1.md §4](VERIFICATION_V4_1.md).

Cách đọc đúng: pass nghĩa là 18 lỗi **đã khai báo** bị bắt. Nó không nói pipeline an toàn với lỗi chưa ai viết ra. Mỗi dòng báo cáo có cả bằng chứng của fixture sạch (để phát hiện detector chặn nhầm) và của bản lỗi.

Bộ test cũng kiểm chính bộ kiểm chứng: `tests/test_challenge_suite.py` xác nhận gate chuyển sang FAIL khi một critical mutation lọt lưới, khi một fixture sạch bị chặn, hoặc khi một mutation đã khai báo không được chạy.

## 4. Inference smoke — kết quả và giới hạn

`python -m telco_churn.inference_smoke --worlds 1000`, một canonical scenario (heterogeneous effect, stratified known propensity 0,3/0,7), policy đã freeze, true contrast 0,075 tính được bằng giải tích.

| Estimator | Bias | MCSE | Coverage | Wilson 95% | CI width trung bình |
|---|---:|---:|---:|---|---:|
| paired DR | +0,00063 | 0,00109 | 95,70% | [94,26%; 96,79%] | 0,1353 |
| unpaired (diagnostic) | +0,00063 | 0,00109 | 98,70% | [97,79%; 99,24%] | 0,1711 |

Hai estimator có **cùng point estimate** — pairing không đổi điểm, nó đổi variance. Pairing giảm sampling variance khoảng **1,6 lần** ở scenario này; unpaired over-cover vì SE bị thổi phồng.

Với outcome model cố tình sai (hằng số) và propensity thiết kế đúng, paired DR vẫn unbiased (bias +0,00077, coverage 95,60%) — đúng tính chất doubly robust.

**Đây không phải coverage gate.** Gate của V3/V4 yêu cầu ≥1.000 replication cho *mỗi* canonical scenario (null, constant effect, heterogeneous, non-constant propensity, rare outcome, clustered, heavy-tailed) và cả full selection pipeline. Ở đây mới có một scenario và policy đã cố định, nên không được đọc ra false-promotion rate.

Chi phí: 0,008 giây/world, 1.000 world ≈ 8 giây. Ngân sách này chưa tính refit nuisance, thứ mà một gate run bắt buộc phải có.

## 5. Sửa lỗi có sẵn: Q04

`CatBoostFrameClassifier._prepare` trước đây điền numeric missing bằng median của **chính batch đang predict**. Một khách hàng có thể nhận score khác nhau tùy vào ai được score cùng lô.

Sửa: median học ở `fit` và lưu trong `numeric_fill_`, dùng lại nguyên vẹn ở inference. `tests/test_uplift.py` kiểm full frame, chunk, từng dòng một và hoán vị thứ tự cho kết quả **bằng nhau đúng từng bit**.

Mức độ ảnh hưởng tới artifact cũ: Orange không có missing value, nên đây là sửa lỗi phòng ngừa cho dataset mới, không phải bằng chứng kết quả Orange hiện có bị sai. Kết luận này giữ nguyên như F09 của review V3.

## 6. Orange — kết quả phiên 3

Số liệu đầy đủ: [reports/v4/ORANGE_ASSIGNMENT_AUDIT.md](../../reports/v4/ORANGE_ASSIGNMENT_AUDIT.md).

Câu hỏi còn mở của F01: treatment có dự đoán được từ 178 pre-treatment covariate không? Bài gốc kiểm bằng Hamming loss ở threshold 0,5 — không phát hiện được dependence khi treatment là lớp đa số (75,740%) trong mọi phân nhóm. Kiểm định bổ sung: cross-fitted out-of-fold ROC-AUC và log loss, kèm permutation test refit toàn bộ pipeline trên nhãn đã xáo.

| Đại lượng | Giá trị |
|---|---:|
| OOF ROC-AUC dự đoán treatment | **0,6355** |
| OOF log loss so constant propensity | 0,5500 so 0,5541 |
| Brier skill so constant propensity | 0,0222 |
| Permutation null (100 refit): mean AUC | 0,5003 (sd 0,0088; q95 0,5143) |
| Số permutation đạt hoặc vượt AUC quan sát | **0 / 100** |
| Add-one p-value | **0,0099** |

Permutation null nằm đúng ở 0,5003 xác nhận cross-fitting không có optimism bias; AUC quan sát 0,6355 cách trung bình null hơn 15 độ lệch chuẩn. **Pooled-IID exchangeability bị bác bỏ.**

### Ước lượng `e(X)` không phải cách sửa

`e(X)` trải toàn bộ [0,0000; 1,0000], median 0,7722. Chỉ 1,60% đơn vị nằm ngoài support ở ngưỡng 0,10 — nhìn qua thì nhẹ. Nhưng effective sample size dưới inverse-probability weighting sụp từ **8.743 xuống 3,9** (tỷ lệ 0,00044).

Đây là con số đáng ra quyết định nhất của audit: một nhúm weight cực lớn sẽ gánh toàn bộ ước lượng. Nói cách khác, "ước lượng `e(X)` rồi reweight" **không** sửa được vấn đề nhận diện ở dataset này — nó chuyển vấn đề sang variance. Câu hỏi này giờ đã có câu trả lời bằng số, không còn là phỏng đoán.

### Hệ quả

Đúng như kế hoạch dự liệu: giữ Orange làm **conditional benchmark**, không nâng thành causal claim; `propensity = treatment.mean()` được gọi đúng tên là giả định, không phải design probability. Mọi dòng Orange trong claim ledger giữ `CONDITIONAL`. Track fallback (Hillstrom) là hướng đúng cho câu hỏi multi-arm và reward thật.

Điều audit **không** kết luận: nó không phân biệt được campaign-level variation, preselection sau randomization, covariate không thực sự pre-treatment và assignment không đồng nhất — thiếu campaign/customer IDs thì bốn cơ chế này để lại cùng một dấu vết trên pooled frame. Permutation null giả định row exchangeable, sẽ sai nếu khách hàng lặp lại, và file không cho kiểm điều đó. Kết quả cũng **không** chứng minh randomization theo từng campaign mà bài gốc mô tả là sai.

### Ngân sách chạy

5,13 giây cho một cross-fit; 469,88 giây cho 100 permutation (4,699 giây mỗi cái). Ước lượng từ profiling trước khi chạy là khoảng 8 phút và khớp với thực tế. Muốn p-value nhỏ hơn 0,0099 thì phải tăng số permutation tuyến tính: 1.000 permutation ≈ 78 phút cho một model kind.

## 7. Cách chạy

```powershell
# cổng tính đúng, không cần dữ liệu ngoài
python -m telco_churn.problem_contract_cli
python -m telco_churn.challenge_suite
python -m telco_churn.inference_smoke --worlds 1000

# profile smoke đầy đủ, dừng ở stage đầu tiên fail
python -m telco_churn.research_runner --profile smoke

# audit assignment của Orange (cần data/raw/churn-uplift-mlg.arff)
python -m telco_churn.assignment_audit --permutations 100 --folds 3

# toàn bộ research track, mọi stage có exit-code check
powershell -ExecutionPolicy Bypass -File scripts/run_research.ps1 -SkipInstall
```

`--profile screen` và `--profile confirm` **raise NotImplementedError**: protocol của chúng chưa freeze, và chạy một pipeline nhỏ hơn dưới tên đó sẽ báo sai phạm vi.

## 8. Việc tiếp theo, theo thứ tự

> Danh sách này là của vòng 1. Vòng 2 đã chèn bước G01–G07 lên trước (theo MASTER_PLAN §18 bước 2) và đã hoàn thành; thứ tự còn lại giữ nguyên, bổ sung coverage gate và G06/V08 ở đầu — xem [VERIFICATION_V4_1.md §7](VERIFICATION_V4_1.md).

1. **V4-04 / E24** — factorial 2×2×2 (representation × effect estimation × decision rule) với cùng split và cùng tuning allowance. Đây là trục chính RQ-A; cần profiling một cell trước khi mở 8 cell × 20 world.
2. **V4-06 / E21** — support gate và hybrid fallback. `assignment_audit` đã cung cấp `e(X)` và bảng support tại 0,025/0,05/0,10; còn thiếu allocator có fallback và đo value trên toàn cohort. Lưu ý kết quả phiên 3: trên Orange, reweight bằng `e(X)` ước lượng làm ESS sụp còn 3,9, nên E21 ở đây phải là **giới hạn population**, không phải reweighting.
3. ~~**Coverage gate**~~ — **đã chạy 21/09 và FAIL**: 8 scenario × 1.000 world, 4/22 readout không đạt coverage (DR ở low-event regime). Xem [STAGE_LOG.md](STAGE_LOG.md). Việc còn lại không phải chạy thêm world mà là sửa phương pháp khoảng tin cậy; full selection pipeline vẫn chưa chạy.
4. **Hillstrom adapter** — sau khi kiểm nguồn/license và freeze split. Cần cho multi-arm và reward thật (spend), là điều Orange không có.
5. **Relational mock generator** — E19 hiện mới chạy trên tiny fixture viết tay. Muốn đo bias thật của delivery delay và missingness phụ thuộc treatment thì cần generator có các bảng invoice/delivery/queue.

Không mở E25/E26/E27 trước khi ba mục đầu có kết quả: kế hoạch đã xếp chúng ngoài 300–400 giờ của vòng này.

## 9. Kiểm tra ở snapshot này (vòng 1)

- `python -m ruff check .`: pass.
- `python -m pytest`: 134 pass (28 của V3 + 106 mới), khoảng 15 giây. *(Vòng 2: 205 pass.)*
- `python -m telco_churn.research_runner --profile smoke`: COMPLETE (lint, unit tests, contract validation, challenge suite). *(Vòng 2 thêm stage `evidence_index`.)*
- Failure propagation của `run_research.ps1` được kiểm trực tiếp: một stage exit code 3 làm script exit 1 và các stage sau không chạy; một stage exit 0 nhưng thiếu artifact khai báo cũng làm script exit 1.
- Docker Compose: vẫn chưa smoke lại, Docker Desktop daemon không chạy. Giữ trạng thái chưa xác minh, không ghi thành pass.
