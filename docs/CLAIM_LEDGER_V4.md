# Claim ledger V4

Ngày: 20/09/2026, cập nhật 21/09/2026 sau vòng triển khai 2 ([VERIFICATION_V4_1.md](archive/VERIFICATION_V4_1.md)). Phiên 1 của [kế hoạch V4](archive/DEVELOPMENT_PLAN_V4.md) §12.

Mục đích của tài liệu này là tách ba loại phát biểu đang tồn tại trong repo, để không lẫn kết quả đã quan sát với kết quả có điều kiện và với thiết kế chưa chạy. Mỗi dòng trỏ tới artifact sinh ra nó. Không dòng nào ở đây là bằng chứng business mới.

Ba trạng thái:

- **OBSERVED** — số liệu đã được sinh ra bởi một lần chạy có artifact, và phát biểu không vượt quá phạm vi của phép đo.
- **CONDITIONAL** — số liệu có thật nhưng diễn giải phụ thuộc giả định chưa kiểm được (identification, cost, horizon, population).
- **PLANNED** — thiết kế đã viết, chưa có kết quả thực nghiệm.

Quy tắc: `PLANNED` không chuyển thành `OBSERVED` vì unit test xanh. `CONDITIONAL` không chuyển thành `OBSERVED` vì lặp lại nhiều seed hơn.

## 1. Dữ liệu và provenance

| Claim | Trạng thái | Artifact | Giới hạn |
|---|---|---|---|
| IBM Telco 7.043 hàng, SHA-256 khớp hằng số trong `schema.py` | OBSERVED | `src/telco_churn/schema.py`, `tests/test_data.py` | Không có treatment; không dùng cho causal claim |
| Orange/OpenML 45580 11.896 hàng, MD5 `bd328613…`, 178 feature | OBSERVED | `src/telco_churn/orange_data.py`, `data/raw/churn-uplift-mlg.arff` | File không có campaign/customer/time/cost |
| Orange: 2.886 control với 105 churn; 9.010 treatment với 303 churn | OBSERVED | `reports/uplift/` | 408 events toàn bộ; mọi so sánh đều low-event |
| Panel synthetic 80.157 customer-month có known CATE | OBSERVED | `src/telco_churn/simulation.py`, `reports/temporal_lab/` | Cơ chế do chính dự án viết; không phải bằng chứng thị trường |
| Orange là randomized experiment với propensity đã biết | **CONDITIONAL → xem §5** | `docs/REVIEW_RESEARCH_V3.md` F01 | `propensity = treatment.mean()` là tỷ lệ quan sát, không phải design probability |

## 2. Kết quả predictive (IBM)

| Claim | Trạng thái | Artifact | Giới hạn |
|---|---|---|---|
| Logistic frozen-test AP 0,6396; ROC-AUC 0,8499; Brier 0,1345 | OBSERVED | `reports/benchmark/BENCHMARK_REPORT.md` | Một lần chạy trên một test split đã khóa |
| 10% contact budget bắt 27,0% churners, lift 2,70× | OBSERVED | `reports/benchmark/budget_metrics.csv` | Là ranking metric, không phải incremental effect |
| Host/batch/API/Docker prediction parity = 0 | OBSERVED | `reports/api/PERFORMANCE_REPORT.md`, `reports/deployment/deployment_smoke.json` | Đã smoke lại 21/09: max lệch 1,110e−16 trên 50 record giữa host và container |
| Mọi con số expected value trong `policy.py` | CONDITIONAL | `src/telco_churn/policy.py` | `save_rate`/`margin`/`cost` là scenario giả định, không có ledger thật |

## 3. Kết quả causal (Orange)

| Claim | Trạng thái | Artifact | Giới hạn |
|---|---|---|---|
| ATE prevented churn +0,275 điểm %, CI [−0,503; +1,053] | CONDITIONAL | `reports/uplift/` | CI qua 0; phụ thuộc giả định assignment ở §5 |
| MDE 80% power = 1,112 điểm %; effect 0,275 cần ≈194.060 obs | OBSERVED | `reports/uplift/` | Tính toán power, không phải kết quả về hiệu quả |
| Locked policy decision = `NO_LAUNCH` | OBSERVED | `reports/uplift/locked_policy_decision.json` | Quyết định của gate đã khai báo trước, không phải kết luận method vô dụng |
| `risk_logistic` thắng 13 candidate khác trên repeated development Qini | CONDITIONAL | `reports/uplift/tournament/tournament_decision.json` | CI từ repeats là variation theo fold/seed trên cùng dataset, không phải population uncertainty (F02) |
| H01–H06 `rejected` | CONDITIONAL | `configs/orange_experiments.toml` | “Không thắng baseline với cấu hình này” ≠ “phương pháp bị bác bỏ” |
| DR uplift holdout +3,331 điểm % [−1,507; +8,269] | CONDITIONAL | `reports/uplift/` | Selected control chỉ có 15 churn events |

## 4. Kết quả temporal (synthetic)

| Claim | Trạng thái | Artifact | Giới hạn |
|---|---|---|---|
| Regime change đổi true ATE +0,649% → −0,105% | OBSERVED (trong simulator) | `reports/temporal_lab/summary.json` | Đúng với cơ chế đã viết; không suy ra tần suất drift thật |
| Post-drift 20% capacity: risk-HGB true value −2.813; S-HGB +1.133; oracle +5.815 | OBSERVED (trong simulator) | `reports/temporal_lab/test_policy_truth.csv` | Đơn vị giá trị là synthetic, không phải tiền |
| Conservative gate chọn `no_contact`, bỏ lỡ 6.806 đơn vị oracle | OBSERVED (trong simulator) | `reports/temporal_lab/` | Trade-off có số đo, không phải claim uplift luôn thắng |

## 5. Trạng thái mới sau phiên 3 — assignment integrity của Orange

Kiểm định bổ sung mà F01 nêu là còn thiếu đã được chạy: cross-fitted out-of-fold ROC-AUC và log loss cho việc dự đoán treatment từ 178 pre-treatment covariates, kèm permutation test refit toàn bộ pipeline.

| Claim | Trạng thái | Số liệu |
|---|---|---|
| OOF ROC-AUC dự đoán treatment từ 178 covariate = 0,6355 | OBSERVED | `reports/v4/assignment_audit.json` |
| Permutation null 100 refit: mean AUC 0,5003, 0/100 đạt hoặc vượt observed, p = 0,0099 | OBSERVED | cùng file |
| Pooled-IID exchangeability bị bác bỏ ở alpha 0,05 | OBSERVED | cùng file |
| ESS dưới IPW sụp từ 8.743 xuống 3,9 khi dùng `e(X)` ước lượng | OBSERVED | cùng file |
| Orange có assignment không đồng nhất | **không kết luận được** | bốn cơ chế khác nhau cho cùng dấu vết pooled |

Trạng thái bằng chứng của audit là **EXPLORATORY**.

Hệ quả cho ledger: mọi dòng ở §3 phụ thuộc `propensity = treatment.mean()` giữ nguyên `CONDITIONAL`. Không có dòng nào của Orange được nâng lên `OBSERVED` như một causal effect.

Hệ quả thứ hai, mới: **ước lượng `e(X)` không phải phương án sửa**. ESS 3,9 nghĩa là một nhúm weight cực lớn gánh toàn bộ ước lượng. Trước audit đây là một lựa chọn để ngỏ; giờ nó đã bị loại bằng số liệu, không phải bằng phỏng đoán.

Kiểm định này không phân biệt được các cơ chế: tỷ lệ treatment khác nhau giữa campaign có population khác nhau, preselection sau randomization, covariate không thực sự pre-treatment, hay assignment không đồng nhất. Thiếu campaign/customer IDs nên permutation null là pooled-IID null, không phải null của thiết kế thật. Kết quả cũng không chứng minh randomization theo từng campaign mà bài gốc mô tả là sai.

## 6. Trạng thái V4 sau các phiên 1–10

| Hạng mục | Trạng thái | Artifact |
|---|---|---|
| Problem/endpoint/time-zero contract (V4-01) | OBSERVED (code + tests) | `src/telco_churn/problem_contract.py`, `configs/problem_contracts.toml`, `reports/v4/contracts.json` |
| Label adjudication E19 | OBSERVED (code + tests) | `src/telco_churn/outcome_adjudication.py` |
| Paired policy contrast E20 (V4-02) | OBSERVED (code + tests + known-truth smoke) | `src/telco_churn/policy_comparison.py`, `reports/v4/inference_smoke.json` |
| Mutation suite E28 (V4-03) | OBSERVED | `reports/v4/CHALLENGE_SUITE_REPORT.md` |
| Reward ledger E22 (V4-05, một phần) | OBSERVED (code + tests) | `src/telco_churn/economics.py` |
| Runner failure propagation Q17 | OBSERVED | `scripts/run_research.ps1`, `src/telco_churn/research_runner.py` |
| R00: sáu exact identity giữ đúng tới sai số dấu phẩy động | OBSERVED | `reports/v4/validity/validity_suite.json` |
| R01: V01 sharp null có promotion rate 2,1% (danh nghĩa 2,5%) | OBSERVED | cùng file |
| R01: IPW + constant propensity lệch +0,576, coverage 0,000 trên V04 | OBSERVED | cùng file |
| R01: DR với cùng propensity sai nhưng outcome model đúng vẫn coverage 94,1% | OBSERVED | cùng file |
| R01: IID SE trên dữ liệu clustered coverage 78,5–79,1% so 94,9–95,1% cluster-robust | OBSERVED | cùng file |
| **R01: DR interval under-cover ở low-event regime — V05 coverage 0,905, V03 0,930; bias trong 2 MCSE** | OBSERVED | cùng file |
| **Hillstrom: không bác bỏ pooled-IID exchangeability** — AUC 0,4975, p 0,6832, ESS giữ 99,95% | OBSERVED | `reports/v4/assignment_audit_hillstrom.json` |
| Hillstrom 64.000 hàng, 3 nhánh 21.387/21.307/21.306, split 80/20 đông cứng, confirmation chưa mở | OBSERVED | `reports/hillstrom/dataset_manifest.json` |
| M01–M08 + 3 baseline fit được trên Hillstrom development (302 conversion, e≈0,4987) | OBSERVED | `telco_churn.candidates` |
| V09: ở q=1, khoảng recruitment-only rộng 0 và coverage 0,000 | OBSERVED | `reports/v4/validity_v09/v09_recruitment.json` |
| R01: DR interval chỉ hỏng khi propensity lệch (V04 0,934; V05 0,887); thiết kế cân bằng đều đạt | OBSERVED | `reports/v4/validity/validity_suite.json` |
| Tăng cỡ mẫu 16× không sửa được coverage của V05 (0,920 → 0,936) | OBSERVED | STAGE_LOG §Sweep |
| Coverage gate ≥1.000 replications × mọi canonical scenario | **FAIL ở lần chạy 21/09** — 4/22 readout không đạt; V08/V09 chưa chạy | `reports/v4/validity/validity_suite.json` |
| Support contract G01 (unmodified / reject / clip + ESS diagnostics) | OBSERVED (code + tests + Q19) | `src/telco_churn/policy_comparison.py`, `tests/test_estimator_contracts.py` |
| Row-key join contract G02 (shuffle, nhãn trùng, NaN/Inf) | OBSERVED (code + tests + Q20) | cùng file |
| Tách recruitment variance và superpopulation variance G03 | OBSERVED (code + tests + Q21) | cùng file |
| Artifact freshness + run identity + timeout manifest G04/G05 | OBSERVED (code + tests + Q22/Q23) | `src/telco_churn/research_runner.py`, `tests/test_research_runner.py` |
| Endpoint/unit separation G07 (`cancellation90` ≠ `net_contribution90`) | OBSERVED (code + tests + Q24) | `src/telco_churn/problem_contract.py`, `configs/problem_contracts.toml` |
| Deployment allocator cap `floor(fraction × N)`, tie-break ổn định (A13) | OBSERVED (code + tests) | `src/telco_churn/allocation.py` |
| Allocator tái tạo locked Orange decision dưới convention đã công bố | OBSERVED | `tests/test_dashboard.py` |
| Recruitment-only SE understate tổng SE 1,28× (600 world, q=0,4) | OBSERVED (trong scenario đã chạy) | `tests/test_estimator_contracts.py::test_a06_reported_variance_tracks_the_empirical_variance` |
| API p95 17,05 ms, 0 lỗi/1.000 request, đo lại 21/09/2026 | OBSERVED | `reports/api/latency.json` |
| Host↔API prediction parity 9,54e−17 trên 50 record | OBSERVED | đo lại 21/09/2026 |
| Release tier hiện tại = `ENGINEERING_FOUNDATION` | OBSERVED (tính từ cổng) | `reports/v4/evidence_index.json` |
| Deployment smoke 12/12: parity, evidence-snapshot identity, locked decision, schema | OBSERVED | `reports/deployment/deployment_smoke.json` |
| Console container không chứa catboost/sklearn/scipy/mlflow; uid 65532; fs read-only | OBSERVED | `docs/DEPLOYMENT.md` §4 |
| E20 sampling experiment trên dữ liệu thật (V4-07) | **PLANNED** | — |
| E21 support gate / fallback (V4-06) | **PLANNED** | — |
| E23/E24/E25/E26/E27 | **PLANNED** | — |
| Hillstrom adapter và multi-arm track | **PLANNED** | — |
| Relational mock generator | **PLANNED** | — |

## 7. Những phát biểu bị cấm ở trạng thái hiện tại

Cập nhật 21/09/2026 sau S21–S36.

Không viết, dưới bất kỳ dạng nào:

- "Hệ thống giảm churn X%" hoặc "tăng ROI" cho Orange — CI qua 0, không có margin/cost thật.
- "Uplift modelling thắng risk modelling", **và cũng không được viết câu ngược lại**. Xem §8: hai nhánh của cùng một thí nghiệm cho hai người thắng khác nhau.
- "Đã khôi phục RCT bằng cách ước lượng `e(X)`" — ước lượng propensity nằm trong (0,1) không chứng minh positivity hay ignorability, và trên Orange thì ESS sụp còn 3,9.
- "Orange không phải randomized experiment" — audit bác bỏ pooled-IID exchangeability, không bác bỏ thiết kế per-campaign mà bài gốc mô tả.
- "Pipeline an toàn" vì mutation suite pass — suite chỉ chứng minh 24 lỗi đã khai báo bị bắt.
- "Coverage đạt 95%" từ `inference_smoke` — một scenario, không phải gate.
- "Production-ready" — chưa có partner, chưa có prospective trial, chưa có serving path cho policy bundle.

### Ba câu **mới bị cấm** sau đợt 21/09

- ~~"Cổng coverage đã đạt, evaluator đã được kiểm chứng."~~ Nó đạt ở 2.000 world, nhưng **qua một biến thể chọn hậu nghiệm** (`--effective-df-floor 1`) trong khi bản cùng power với sàn mặc định vẫn FAIL. Mọi artifact dùng cổng này đều mang dòng `SELECTED AFTER LOOKING`. Câu được phép: *"đạt có điều kiện, chờ xác nhận độc lập trên seed chưa dùng với recipe khoá trước"*.
- ~~"Trong chế độ ít sự kiện, baseline thắng causal learner."~~ **Bị chính dữ liệu bác bỏ** (S35): chạy lại toàn bộ giao thức trên nhánh Womens của *cùng* dataset thì M03 thắng M01 +0,001412 và có learning curve đơn điệu. Ba đợt R02/R03/R04 đồng thuận vì dùng **cùng một cohort**, không vì kết luận vững.
- ~~"Chỉ số bất đối xứng `A` có ngưỡng 0,58."~~ Ngưỡng đó đo trên chính lưới đã sinh ra công thức. Trên **28 thiết kế ngoài mẫu** nó **không chuyển được** (S25): cả ba dự đoán đăng ký trước đều bị bác bỏ. Cổng đã tự siết xuống **0,100** và câu được phép phải nói rõ con số nào đang được thi hành.

## 8. Phát biểu **được phép** sau đợt 21/09

| Claim | Trạng thái | Artifact | Giới hạn |
|---|---|---|---|
| Skewness của trung bình DR có dạng đóng `γ = (1−2e)/√(n·h·r·e(1−e))`, khớp số đo trong 8–22% | OBSERVED | [test_design_asymmetry.py](../tests/test_design_asymmetry.py), [RELATED_WORK.md](RELATED_WORK.md) | Một họ generator, `e` hằng số. Thiết kế có `e(X)` thay đổi **không** được phủ |
| `A` giải thích R²=0,762 biến thiên coverage trên 28 thiết kế ngoài mẫu, tốt hơn `1/√N_eff` (0,595) | OBSERVED | [asymmetry_transfer](../reports/v4/asymmetry_transfer/) | **Không phải một lằn ranh sắc** — cả ba dự đoán đăng ký trước đều bị bác bỏ |
| Hiệu chỉnh Edgeworth mở rộng vùng dùng được ~2,9 lần trên lưới đã quét | OBSERVED | [overlap_boundary](../reports/v4/overlap_boundary/) | Trên lưới đó; không chuyển được nguyên vẹn ra ngoài |
| Thiết kế lấy mẫu làm giàu đạt cùng độ chính xác với **26%** chi phí ở `d=0,05`, **59%** ở `d=0,50` | OBSERVED | [sampling_economics](../reports/v4/sampling_economics/) | Chi phí là **giá khai báo**, không phải posting. Là tỷ lệ chi phí, **không** phải lợi nhuận |
| Chọn 4 candidate thay vì 1 không làm phồng false promotion dưới giao thức ba mẫu | OBSERVED | [selection_stress](../reports/v4/selection_stress/) | **Không phải cổng**: 300 world null chỉ phân giải ±0,025 |
| Không chiến lược refresh nào thắng cả ba cơ chế drift | OBSERVED | [temporal_replay](../reports/v4/temporal_replay/) | Thế giới mock; phần thưởng là churn tránh được, **không có sổ tiền** |
| Khoảng batch-cap phủ đúng target của nó ở cả hai chế độ | OBSERVED | [validity_v08](../reports/v4/validity_v08/) | Một cơ chế, một cap, thiết kế cân bằng |
| **Ở ~300 sự kiện, thứ hạng giữa các họ model là nhiễu** | OBSERVED | [replication_womens](../reports/v4/replication_womens/) | Hai nhánh của một thí nghiệm cho **hai người thắng khác nhau** |
| **Ở ~6.500 sự kiện, cả bảy causal learner thắng baseline và baseline đứng bét** | OBSERVED | [replication_lenta](../reports/v4/replication_lenta/) | Một miền độc lập (SMS bán lẻ), mẫu con 60.000 hàng đã khai báo, 3 outer fold |
| **Bất ổn hyperparameter KHÔNG phải vấn đề đếm sự kiện** | OBSERVED | [replication_lenta](../reports/v4/replication_lenta/) | Dự đoán đăng ký trước P2 **bị bác bỏ**: 21× event, vẫn không family nào ổn định |

Quy tắc bổ sung, rút ra từ chính đợt này: **ba đợt đồng thuận trên cùng một cohort là một bằng chứng, không phải ba.**

### Câu **được phép** về ứng viên B, sau R10

> Ở ~300 sự kiện thứ hạng giữa các họ model là nhiễu; ở ~6.500 sự kiện causal learner thắng dứt khoát.

Ba điểm trên hai dataset độc lập cùng giao thức: Hillstrom Mens (302 event, M01 thắng), Hillstrom Womens (251 event, M03 thắng), Lenta (6.498 event, **cả bảy** causal learner thắng, M01 bét với giá trị âm). Hai điểm đầu **mâu thuẫn nhau** ở cùng cỡ event — đó chính là nội dung của chữ "nhiễu".

**Vẫn không được viết:** "causal learner tốt hơn baseline" mà không kèm cỡ sự kiện; hoặc "cần thêm dữ liệu" như một kết luận chung — P2 bị bác bỏ cho thấy thêm dữ liệu **không** sửa được bất ổn hyperparameter.
