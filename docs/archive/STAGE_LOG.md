# Nhật ký giai đoạn — cập nhật khi một stage kết thúc

Một dòng cho mỗi giai đoạn **đã chạy xong**, kèm ngày, artifact sinh ra và điều nó cho phép kết luận. Quy tắc: một stage chỉ được ghi ở đây khi nó đã chạy và để lại artifact; kế hoạch chưa chạy nằm ở [MASTER_PLAN](MASTER_PLAN.md) và [runbook](EXPERIMENT_RUNBOOK_V4.md), không ghi vào đây.

Cột **cho phép nói gì** quan trọng ngang cột trạng thái: một stage xong không tự động nâng hạng bằng chứng.

## Đã chạy

| # | Ngày | Giai đoạn | Artifact | Cho phép nói gì | Không cho phép nói gì |
|---|---|---|---|---|---|
| S1 | 21/09/2026 | Tái hiện trạng thái đã công bố (tests, challenge suite, contracts, inference smoke, assignment audit, API parity) | [VERIFICATION_V4_1.md §1](VERIFICATION_V4_1.md) | Các số trong README/status/ledger tái hiện được trên máy hiện tại; audit Orange giống hệt từng trường | Không nói kết quả mạnh hơn trước — tái hiện không phải bằng chứng mới |
| S2 | 21/09/2026 | Đóng khoảng trống G01, G02, G03, G04, G05, G07 kèm test A01–A09, A11, A13, A15 | `policy_comparison.py`, `research_runner.py`, `problem_contract.py`, `allocation.py`, `tests/test_estimator_contracts.py` | Sáu lớp lỗi đã khai báo giờ bị chặn ở cấp contract, có test và mutation riêng | Không nói estimator “đúng” — chỉ nói sáu lỗi đã nêu bị bắt |
| S3 | 21/09/2026 | Bộ kiểm chứng 18 → 24 mutation (Q19–Q24) | [CHALLENGE_SUITE_REPORT.md](../../reports/v4/CHALLENGE_SUITE_REPORT.md) | 21/21 critical mutation bị bắt, 0 false block trên 24 case đã khai báo | Không nói pipeline an toàn với lỗi chưa ai viết ra |
| S4 | 21/09/2026 | Chỉ mục bằng chứng + decision console | [EVIDENCE_INDEX.md](../../reports/v4/EVIDENCE_INDEX.md), `telco_churn.dashboard` | Release tier được **tính** từ cổng; artifact cũ hơn code bị gắn cờ | Không nói tier cao hơn `ENGINEERING_FOUNDATION` |
| S5 | 21/09/2026 | Triển khai hai dịch vụ + Postgres, deployment smoke 12/12 (stack **không còn chạy** sau khi Docker Desktop tắt; artifact ghi lại lần chạy lúc 02:40, không phải trạng thái hiện tại) | [DEPLOYMENT.md](../DEPLOYMENT.md), [DEPLOYMENT_SMOKE.md](../../reports/deployment/DEPLOYMENT_SMOKE.md) | Parity host↔container 1,110e−16; console container tái tạo locked decision lệch 1,4e−17; migration đã áp | Không nói production-ready: không auth, không SLA, không load test |
| S6 | 21/09/2026 | **R00** — sáu exact identity ngoài Q01–Q18 | [VALIDITY_REPORT.md](../../reports/v4/validity/VALIDITY_REPORT.md) | Sáu đẳng thức giữ đúng tới sai số dấu phẩy động, gồm cả enumeration thay cho assertion sai về IPW | Không nói evaluator không còn lỗi nào |
| S7 | 21/09/2026 | **R01** — 8 scenario × 1.000 world × 3 estimator mode (430 s) | cùng file | Bốn cell **không đạt coverage**; đây là kết quả của gate, không phải sự cố hạ tầng — xem §Kết quả R01 | **Không được mở R02.** Runbook đặt điều kiện “R01 validity gates đạt”, và gate này FAIL |
| S8 | 21/09/2026 | **QG0** — dependency lock cho 3 môi trường + công cụ verify | `locks/*.lock.txt`, `telco_churn.environment`, [environment.json](../../reports/v4/environment.json) | 180 gói của môi trường nghiên cứu được pin và **kiểm được**; hai image có lock riêng chụp từ container đang chạy | Không nói build tái lập bit-for-bit: lock ghi version, không ghi hash wheel |
| S9 | 21/09/2026 | **WP03 + WP02** — Hillstrom adapter, manifest, split đông cứng, contract | [dataset_manifest.json](../../reports/hillstrom/dataset_manifest.json), `telco_churn.hillstrom_data`, `configs/problem_contracts.toml` | Có real-data primary thật: 64.000 hàng, 3 nhánh cân bằng (21.387/21.307/21.306), outcome spend thật; split 80/20 hash theo row_id, confirmation **chưa mở** | Randomisation là **do nguồn mô tả**, repo này chưa audit; chưa được gọi là design probability đã kiểm |
| S10 | 21/09/2026 | **WP08** — M01–M08 + ba baseline, đúng hyperparameter runbook | `telco_churn.candidates` | Tám candidate fit và score được trên dữ liệu thật; **M07 DR-Ridge lần đầu tồn tại**; DR learner từ chối tự bịa propensity | Không nói candidate nào tốt hơn — đó là câu hỏi của R02 |
| S11 | 21/09/2026 | **WP09** — harness R02, tự chặn khi R01 chưa đạt | `telco_churn.screening` | Harness sẵn sàng, đã kiểm bằng test rằng nó **từ chối chạy** sau gate FAIL và ghi FIT_FAILED thay vì bỏ qua | Chưa có kết quả screening nào: stage chưa được phép chạy |
| S12 | 21/09/2026 | **Sửa lỗi seeding của chính gate** + đo lại R01 (681 s) | [validity_suite.json](../../reports/v4/validity/validity_suite.json) | Cùng scenario giờ cho cùng world bất kể chạy kèm gì; kết luận sai về V03 đã được đính chính | Số R01 công bố trước 21/09 buổi chiều **không dùng lại được** |
| S13 | 21/09/2026 | **Ba phương pháp khoảng tin cậy** ở scale gate (681 + 916 + 2.072 s) | ba thư mục `reports/v4/validity*` | Tách được vấn đề làm hai: lệch (sửa được bằng Edgeworth) và thiếu bề rộng (chưa cái nào sửa) | **Không** được nói đã tìm ra phương pháp đúng; mặc định vẫn là `normal` |
| S15 | 21/09/2026 | **Audit assignment của Hillstrom** — cùng bài kiểm đã bác bỏ Orange | [HILLSTROM_ASSIGNMENT_AUDIT.md](../../reports/v4/HILLSTROM_ASSIGNMENT_AUDIT.md) | **Không bác bỏ exchangeability**: AUC 0,4975, p 0,6832, Brier skill −0,0007, ESS giữ **99,95%**. Đây là dataset đầu tiên trong kho có design probability dùng được | Không bác bỏ ≠ chứng minh randomised. Phép kiểm có độ phân giải (null sd 0,0040) nhưng vẫn chỉ là *không phát hiện* vi phạm |
| S16 | 21/09/2026 | **V09** — recruitment hai giai đoạn, hai study, có cell biên q=1 | `telco_churn.recruitment_validation` | Ở q=1, khoảng recruitment-only có bề rộng **đúng bằng 0** và coverage **0,000** — chứng minh bằng số điều G03 cảnh báo | Không dùng recruitment-only làm CI chính, ở bất kỳ q nào |
| S17 | 21/09/2026 | **Xác nhận ở 2.000 world, seed 20260923** với hiệu chỉnh Edgeworth + bậc tự do hữu hiệu | [validity_confirm](../../reports/v4/validity_confirm/VALIDITY_REPORT.md) | 6/8 scenario đạt ở power cao (nhiễu cổng 0,43%); **V04 đã sửa được** (0,934 → 0,9415) | V05 vẫn trượt **decisive** (0,929); không được nói đã sửa xong |
| S18 | 21/09/2026 | **V05B** — cell tách nguyên nhân: hiếm nhưng **cân bằng** | cùng run | **Hiếm một mình không phá khoảng tin cậy**: 0,52% event ở e=0,5 cho coverage 0,948. Nguyên nhân là **lệch propensity**, hiếm chỉ khuếch đại | Không suy ra evaluator đúng ở mọi e; vùng hợp lệ đo được tới lệch 0,3 |
| S19 | 21/09/2026 | **Vùng thiết kế hợp lệ** suy ra từ run, và **kiểm bằng máy** trong harness R02 | `validated_design_region` trong artifact; `screening.gate_status(cohort_propensity=…)` | Một cohort chỉ được cấp phép khi thiết kế của nó nằm trong vùng *đã đo*; không khai báo thiết kế thì không có phép | Không dùng vùng để đi vòng qua gate cho thiết kế ngoài vùng |
| S20 | 21/09/2026 | **R02 — model screening chạy được lần đầu** trên Hillstrom development | [SCREENING_REPORT.md](../../reports/screening/SCREENING_REPORT.md) | M01–M08 × 3 outer fold, cap 20%, cùng fold cùng evaluator; **baseline M01 thắng cả tám** | Không nói "causal learner vô dụng": 3 fold của 1 dataset, CI của M03/M04/M06 vẫn cắt 0 |
| S21 | 21/09/2026 | **Đối chiếu văn liệu** + rút gọn giải tích, có kiểm bằng số | [RELATED_WORK.md](../RELATED_WORK.md) | Skewness của trung bình DR có dạng đóng `γ = (1−2e)/√(n·h·rate·e(1−e))`, khớp số đo trong 15% trên `e` từ 0,5 tới 0,95 | Ngưỡng của `A = |γ|` **chưa biết**; cổng gác chưa sửa. Mệnh đề weak-overlap của Dorn (2025) **không** áp dụng được ở đây |
| S22 | 21/09/2026 | **Lưới ranh giới** 6 propensity × 3 tỷ lệ × 2 phương pháp × 1.000 world (515 s) | [OVERLAP_BOUNDARY.md](../../reports/v4/overlap_boundary/OVERLAP_BOUNDARY.md) | `A` phân tách **hoàn hảo** 18/18 cell cho `normal` (ngưỡng trong (0,202; 0,212]); `skewness_adjusted_t` không chặn df chỉ trượt **1/18** và **phủ được thiết kế của V05** (0,937) | Ngưỡng đo trên **một** generator; `A` chưa kiểm ngoài họ này. Cổng gác vẫn đang dùng biến sai |
| S23 | 21/09/2026 | **Sửa cổng gác** sang chỉ số bất đối xứng + công bố việc chọn phương pháp | `screening.CohortDesign`, `policy_comparison.design_asymmetry_index`, `evidence._gate_coverage` | Cohort phải khai báo **cả bốn** thừa số; ngưỡng **đọc từ artifact sweep**, không hard-code; gate tự tố cáo khi verdict PASS là chọn sau khi nhìn | Ngưỡng chỉ hợp lệ cho họ generator đã quét và cho `e` hằng số; propensity phụ thuộc X không được phủ |
| S24 | 21/09/2026 | **Bốn hình**, vẽ từ artifact và **chỉ** từ artifact | [reports/v4/figures](../../reports/v4/figures) | Lấp khoảng trống "không có hình nào"; hình `why_not_imbalance` là bằng chứng trực quan cho S22 | Không hình nào tự tính lại số; thiếu artifact thì **bỏ qua và nói là bỏ qua** |
| S25 | 21/09/2026 | **Thử phá chỉ số `A`** — 28 thiết kế ngoài mẫu, 1.000 world (1.424 s) | [ASYMMETRY_TRANSFER.md](../../reports/v4/asymmetry_transfer/ASYMMETRY_TRANSFER.md) | **Cả ba dự đoán đều bị bác bỏ.** `A` giải thích R²=0,762 độ biến thiên coverage — vẫn là biến đúng — nhưng **không phải một lằn ranh sắc** | **Ngưỡng 0,202 của S22 KHÔNG chuyển được**: ở `A=0,20` có 3/7 thiết kế trượt. Cổng gác đang cấp phép rộng hơn bằng chứng cho phép |
| S26 | 21/09/2026 | **Siết cổng gác** theo bằng chứng ngoài mẫu | `screening._out_of_sample_ceiling`, 7 test | Ngưỡng tự động siết **0,584 → 0,100**; nơi sweep và transfer bất đồng thì **transfer thắng**, vì nó là bằng chứng không bị fit | Hillstrom (A=0,0007) vẫn được cấp phép; V05 (A=0,533) vẫn bị từ chối |
| S27 | 21/09/2026 | **Cổng coverage ĐẠT** — 2.000 world, seed mới 20260925, df không chặn | [validity_unshrunk](../../reports/v4/validity_unshrunk) | **9/9 scenario, 0 trượt, 0 false-promotion**; V05 `dr_correct` từ 0,929 lên **0,9440**. QG4 mở. Release tier **ENGINEERING_FOUNDATION → RESEARCH_INTERIM** | **Đây là biến thể chọn hậu nghiệm.** Cổng tự in `SELECTED AFTER LOOKING` vào mọi artifact dùng nó |
| S28 | 21/09/2026 | **V08 bỏ chặn và ĐẠT** — 500 world × 2 chế độ, 1.419 s | [V08_REPORT.md](../../reports/v4/validity_v08/V08_REPORT.md) | 4/4 readout có cổng đều phủ (0,946–0,964); control **nổ** ở chế độ đo được (0,302). Tìm ra **hai lỗi thật trong G06** khi dựng scenario | Một cơ chế, một cap, thiết kế cân bằng; không nói gì về cap dưới thiết kế lệch |
| S29 | 21/09/2026 | **R03 bounded tuning** — 3 family × 8 config × 3 outer × 3 inner, 237 fit, 36 s | [TUNING_REPORT.md](../../reports/v4/tuning/TUNING_REPORT.md) | **Tinh chỉnh không cứu được causal learner**: gain +0,00008 và +0,00004, tức bằng 0. Lỗ hổng chặn ứng viên B đã được vá | **Không một family nào chọn được cấu hình ổn định** qua 3 fold — 302 event là quá ít để chọn hyperparameter |
| S30 | 21/09/2026 | **R04 factorial thành phần** — 2×2×2 × 3 outer × 2 chế độ chi phí, 12 effect fit, 6 s | [FACTORIAL_REPORT.md](../../reports/v4/factorial/FACTORIAL_REPORT.md) | **Không thành phần nào lay chuyển kết quả**; null fixture **giữ đúng bằng 0,000000** | Chi phí liên hệ là **giá giả định**, không phải posting; 3 fold không phải 3 dataset |
| S31 | 21/09/2026 | **R06 selection stress** — 300 world × 2 cơ chế, 1-vs-4 candidate, 185 s | [SELECTION_STRESS.md](../../reports/v4/selection_stress/SELECTION_STRESS.md) | Nhìn 4 candidate thay vì 1 **không** làm phồng false promotion (0,023 so 0,043 dưới null) | **Không phải cổng**: 300 world null chỉ phân giải được ±0,025, rộng hơn chính đại lượng cần chấm |
| S32 | 21/09/2026 | **R05 learning curve + ổn định seed** — 3 finalist × 3 tỷ lệ × 3 outer, 45 fit, 12 s | [LEARNING_CURVES.md](../../reports/v4/learning_curves/LEARNING_CURVES.md) | **Gấp 4 lần dữ liệu không cải thiện gì**; seed gần như tất định (M01/M03 IQR = 0) | Ba seed **không phải** ba world — không dựng CI từ chúng, và artifact nói rõ |
| S33 | 21/09/2026 | **R08 thiết kế lấy mẫu + kinh tế** — 2 thiết kế × 3 mức bất đồng × 1.000 world | [SAMPLING_ECONOMICS.md](../../reports/v4/sampling_economics/SAMPLING_ECONOMICS.md) | Lần chạy đầu **chấm sai target** và cho coverage 0,61; đã sửa và giữ lại làm negative control | Chi phí là **giá khai báo**, output là tỷ lệ chi phí ở cùng độ chính xác, không phải lợi nhuận |
| S34 | 21/09/2026 | **R07 bỏ chặn** — replay theo policy, 4 chiến lược × 3 cơ chế × 40 world | [TEMPORAL_REPLAY.md](../../reports/v4/temporal_replay/TEMPORAL_REPLAY.md) | **Không chiến lược nào thắng ở cả ba cơ chế**; `calibration_only` không cứu được effect drift (+0,1) | Thế giới mock, phần thưởng là churn tránh được, **không có sổ tiền**; ledger cân |
| S35 | 21/09/2026 | **Lặp lại toàn bộ giao thức trên nhánh Womens** của cùng dataset | [replication_womens](../../reports/v4/replication_womens) | **KẾT LUẬN ĐẢO NGƯỢC**: M03 thắng M01 +0,001412; M03 có learning curve thật; HGB **kém đi** −0,000492 (3,3 se) | Đây **không phải** R10 (cùng dataset, cùng khách hàng). Nó **làm yếu** ứng viên B chứ không củng cố |
| S36 | 21/09/2026 | **R09 — quyết định KHÔNG mở** split confirmation | [R09_CONFIRMATION_DECISION.md](../R09_CONFIRMATION_DECISION.md) | Bốn lý do độc lập, mỗi lý do đủ để hoãn; điều kiện mở được viết ra rõ ràng | `confirmation_outcomes_read: false` giữ nguyên. Đây là quyết định, không phải việc chưa làm |
| S37 | 21/09/2026 | **Audit assignment của Lenta** — miền thứ hai cho R10 | [assignment_audit_lenta.json](../../reports/v4/assignment_audit_lenta.json) | **Không bác bỏ exchangeability**: AUC 0,5037, p 0,1765, ESS giữ **97,9%**. Dataset **thứ hai** có design probability dùng được | Audit trên mẫu con 60.000 hàng; propensity ước lượng chạm 0,9999 ở đuôi |
| S38 | 21/09/2026 | **R10 — lặp lại ngoài miền trên Lenta**, 60.000 unit, 6.498 event, 2.689 s | [EXTERNAL_REPLICATION.md](../../reports/v4/replication_lenta/EXTERNAL_REPLICATION.md) | **P1 đúng mạnh**: cả **bảy** causal learner thắng M01, M01 **đứng bét**. P3 đúng. **P2 SAI**: bất ổn hyperparameter **không** biến mất ở 21× event | Release tier **RESEARCH_REPLICATED**, 9/10 cổng. Hai dataset là **mức tối thiểu**, chưa phải câu trả lời chốt |
| S14 | 21/09/2026 | **Sweep cỡ mẫu** V03/V05 ở n = 10k/40k/160k | [STAGE_LOG §Sweep](#sweep-cỡ-mẫu-v05-không-sửa-được-bằng-thêm-dữ-liệu) | Dưới allocation lệch, thêm 16× dữ liệu gần như không cải thiện coverage | Không suy ra ngưỡng event an toàn: cái chặn là thiết kế, không phải cỡ mẫu |

## Trạng thái các đợt R00–R10 (cập nhật 21/09/2026)

| Đợt | Trạng thái | Ghi chú |
|---|---|---|
| R00, R01 | **xong** | Cổng ĐẠT ở 2.000 world (S27) qua biến thể **chọn hậu nghiệm**; cần xác nhận độc lập |
| R02 | **xong (S20)** | Dưới giấy phép vùng thiết kế. Harness đã kiểm là **từ chối đúng** khi gate FAIL |
| R03 | **xong (S29)** | Tinh chỉnh +0,00008; **không family nào** ổn định cấu hình |
| R04 | **xong (S30)** | Không thành phần nào lay chuyển; null fixture giữ ±0,000000 |
| R05 | **xong (S32)** | 4× dữ liệu không cải thiện; seed gần tất định |
| R06 | **xong (S31)** | Chọn 4 thay 1 **không** phồng false promotion. Tự khai **không phải cổng** |
| R07 | **xong (S34)** | Bỏ chặn bằng replay theo policy; không chiến lược nào thắng cả ba cơ chế |
| R08 | **xong (S33)** | Làm giàu rẻ hơn ở cùng độ chính xác: 26% / 26% / 59% theo `d` |
| R09 | **quyết định KHÔNG mở** | Bốn lý do: [R09_CONFIRMATION_DECISION.md](../R09_CONFIRMATION_DECISION.md) |
| R10 | **đang chạy** | Lenta (SMS bán lẻ, 687.029 hàng, response 10,8%), ba dự đoán đăng ký trước |
| V08 | **xong, ĐẠT (S28)** | Lý do chặn cũ đã cũ; dựng nó ra thì tìm được **hai lỗi thật** trong G06 |
| V09 | **xong (S16)** | — |
| Lặp lại nhánh Womens | **xong (S35)** | **Không phải R10.** Kết luận R02–R05 **đảo ngược** |

Không dòng nào ở bảng trên được mô tả là "đang chạy" nếu chưa có artifact.

## Kết quả R01

### Đính chính: lần đo 21/09 đầu tiên có lỗi seeding

Bản R01 đầu tiên báo **V03 và V05 không đạt coverage**. Kết luận về V03 **sai**, và nguyên nhân là lỗi trong chính công cụ đo: seed của mỗi world được tạo từ `[seed, vị_trí_trong_danh_sách, world]`. Chạy `--scenarios V03` và chạy full suite vì thế sinh ra **hai tập world khác nhau** cho cùng một generator đã đông cứng — đúng thứ mà việc đông cứng generator phải ngăn.

Đã sửa: namespace seed lấy từ **hash của scenario_id**, không phụ thuộc thành phần lần chạy. Có test chặn hồi quy (`test_a_scenario_draws_the_same_worlds_whatever_else_is_requested`). Mọi số dưới đây là đo **sau** khi sửa.

### Kết quả sau khi sửa (1.000 world/scenario, seed 20260921, 681 s)

Trạng thái: **FAIL — 4/29 readout**, 0 false promotion.

| Scenario | Thiết kế | IPW | DR đúng | DR sai nuisance |
|---|---|---|---|---|
| V01 sharp null | e=0,5 | 0,950 | 0,950 | 0,951 |
| V02 constant | e=0,5 | 0,943 | 0,952 | 0,953 |
| V03 heterogeneous | e=0,5 | 0,953 | 0,950 | 0,952 |
| V04 stratum-varying | **e=0,2/0,8** | 0,951 | **0,934** | **0,931** |
| V05 rare + imbalanced | **e=0,9** | 0,948 | **0,887** | **0,886** |
| V06 clustered | e=0,5 | 0,960 | 0,945 | 0,947 |
| B01 boundary | e=0,5 | 0,945 | 0,958 | 0,957 |
| V07 heavy tail | e=0,5 | 0,963 | 0,941 | 0,942 |

**Quy luật, và nó sạch:** khoảng tin cậy DR chỉ hỏng ở hai scenario có **propensity lệch**. Mọi thiết kế cân bằng đều đạt, kể cả heavy tail t(3) và clustered. Đuôi nặng một mình không phá coverage; **lệch propensity thì có**, vì nó dồn inverse-probability weight lớn lên một nhánh nhỏ và làm phân phối score lệch phải.

Miss cũng lệch đúng một phía: V05 có 0,006 dưới / **0,107 trên**. Truth nằm *trên* cận trên, tức estimate thường thấp hơn truth và thỉnh thoảng vọt lên — chữ ký của phân phối lệch phải. Bias vẫn nằm trong 1 MCSE ở cả bốn cell: **lỗi của khoảng, không phải của estimator**.

IPW không dính (0,948–0,953) vì khoảng của nó rộng hơn một bậc.

### Negative control kích hoạt đúng

| Control | Kết quả |
|---|---|
| IPW + constant propensity (V04) | bias **+0,5766**, coverage **0,000**, miss dưới 1,000 — sai hoàn toàn |
| DR + cùng propensity sai, outcome model đúng | bias −0,000016, coverage 0,954 — **sống sót**; double robustness đo được |
| IID SE trên dữ liệu clustered (V06) | coverage 0,788–0,807 so 0,945–0,960 của cluster-robust |

### Ba phương pháp khoảng tin cậy đã thử ở scale gate

| Phương pháp | Chi phí | Số cell fail | V05 dr coverage | V05 miss dưới/trên |
|---|---:|---:|---:|---|
| **normal** (mặc định) | 681 s | **4** | 0,887 | 0,006 / 0,107 |
| skewness-adjusted (Cornish–Fisher) | 916 s | 6 | 0,923 | 0,024 / 0,053 |
| studentized bootstrap, B=499 | 2.072 s | 6 | 0,930 | 0,029 / 0,041 |

⚠️ Bản bootstrap chạy **trước** khi sửa lỗi seeding, nên nó đo trên tập world khác và **không so sánh trực tiếp** được với hai dòng trên. Hai dòng normal và skewness-adjusted dùng đúng cùng world.

Điều đọc được từ so sánh hợp lệ (normal vs skewness-adjusted, cùng world):

- Hiệu chỉnh skewness **sửa đúng phần nó nhắm tới**: miss của V05 từ 0,006/0,107 (lệch hẳn) về 0,024/0,053 (gần cân), coverage 0,887 → 0,923.
- Nhưng nó **không** đóng được phần thiếu bề rộng, và đẩy V07 (vốn sát ngưỡng ở 0,941) xuống dưới vạch. Tổng số cell fail tăng 4 → 6.

Nên vấn đề tách làm hai phần độc lập, và mới giải quyết được một:

1. **Lệch (asymmetry)** — đã hiểu và sửa được bằng số hạng Edgeworth bậc một.
2. **Thiếu bề rộng** — chưa phương pháp nào đóng. Ứng viên tiếp theo là bậc tự do hữu hiệu theo kurtosis: với V05, excess kurtosis ≈ 2.744 cho `df_eff = 2n/(κ−1) ≈ 7`, tức t-quantile rộng hơn ~19% thay vì 1,96 — nhiều khả năng **quá tay**, nên phải đo chứ không đoán.

### Phép thử đã pre-register: kết quả, và cả hai dự đoán đều sai

Vòng trước tôi ghi trước dự đoán cho ứng viên tiếp theo (`df_eff = 2n/(κ−1)`), chạy trên **seed mới 20260922**:

> Dự đoán đã ghi: df không chặn sẽ **quá rộng** ở V05 (coverage vượt 0,96), và **cần** một bản chặn (ví dụ sàn df = 30).

Kết quả:

| Phương pháp | fails | V04 | V05 | V07 | B01 |
|---|---:|---:|---:|---:|---:|
| normal | 4 | 0,934 | **0,887** | 0,941 | 0,958 |
| skew + df **không chặn** | **2** | 0,942 | **0,947** | 0,943 | 0,938 |
| skew + df chặn ở 30 | 4 | 0,942 | 0,931 | 0,941 | 0,938 |

**Cả hai vế của dự đoán đều bị bác bỏ.** Không chặn cho coverage 0,947 chứ không vọt quá 0,96 (tuy width ratio 1,143 đúng là rộng); và cái sàn df=30 — thứ tôi đoán là *cần* — chính là thứ làm hỏng, vì nó chặn đúng phần nới mà V05 cần. Đây là lý do tồn tại của pre-registration: nếu chọn sau khi nhìn số, tôi đã kể một câu chuyện hợp lý cho bất kỳ kết quả nào.

### Cổng tự nó thiếu power — sửa lại tham số của runbook

Trong lúc diễn giải các failure sát vạch, một lỗi thiết kế trong chính cổng lộ ra. Luật chấm là pointwise (mọi readout phải có Wilson lower bound ≥ 0,92) và được áp lên **29 readout**. Với 1.000 world:

| | |
|---|---|
| readout trượt khi coverage quan sát ≤ | 0,936 |
| P(một readout trượt \| coverage thật = 0,95) | 0,0284 |
| **P(ít nhất một trong 29 trượt)** | **0,567** |
| cùng luật ở 2.000 world | 0,005 |
| cùng luật ở 5.000 world | ~0 |

Tức là **một estimator hoàn hảo vẫn trượt cổng này 56,7% số lần** ở kích thước mà runbook khai báo. MASTER_PLAN §4.4 đã cảnh báo đúng điều này ("pointwise bounds không hỗ trợ câu đó") nhưng runbook vẫn đặt 1.000 world. Con số này giờ được in trong mọi báo cáo R01 (`family_false_failure_rate`) và failure được tách thành **decisive** so với **marginal**.

Đọc lại các kết quả theo đó:

- V05 với khoảng `normal` (0,887) là **decisive**: thấp hơn danh nghĩa ~8 MCSE, không thể là nhiễu.
- Hai failure còn lại của bản df không chặn (B01 0,938; V07 ipw) đều **marginal** và không phân biệt được với nhiễu của chính cổng.

**Đề nghị sửa protocol:** R01 cần **≥2.000 world/scenario**, không phải 1.000. Một lần chạy xác nhận ở 2.000 world, seed 20260923, đang chạy.

### S21 — văn liệu, một rút gọn giải tích, và một giả thuyết của chính tôi bị bác bỏ

Chi tiết và trích dẫn: [RELATED_WORK.md](../RELATED_WORK.md). Bốn điều phải ghi lại.

**1. Repo không ở chế độ weak overlap.** Generator dùng `e` **hằng số** (`np.full(N_UNITS, propensity)`); không có đuôi `e(X)→0`, trọng số IPW bị chặn bởi 10 ở V05. Định lý của [Dorn (2025)](https://arxiv.org/abs/2504.13273) — thresholded AIPW cho Wald hiệu chỉnh đúng — **không áp dụng**, vì không có gì để threshold. Mọi câu chữ xếp V05 vào văn liệu weak overlap đều sai địa chỉ.

**2. Mệnh đề giải tích đã có, cho đúng chế độ này.** [Qiu (2025)](https://arxiv.org/abs/2512.18898) chặn `|coverage − danh nghĩa|` cho AIPW trong RCT với propensity biết trước. Kế hoạch dự trù 8–16 giờ cho bước này; thực tế là một buổi tra cứu cộng một phép rút gọn.

**3. Giả thuyết `N_eff` — đề ra, kiểm, và bác bỏ trong cùng stage.** Rút gọn đầu tiên chỉ đếm gai nhánh đối chứng và cho `ρ₃/(σ³√n) = 1/√N_eff` với `N_eff = n·h·rate·(1−e)`. Đo trên chính vector score thì tỷ số ấy **đúng là hằng số** (0,58–0,69 trên dải `N_eff` rộng 37 lần) — nhưng đó là rút gọn của mômen **tuyệt đối**, tức của *chặn*, không của đại lượng lái coverage. Skewness đo được bác bỏ ngay: V05 cho 0,436 còn V05B cho 0,0087, lệch **50 lần** trong khi `N_eff` chỉ lệch 5 lần. Ở `e=0,5` gai hai nhánh cùng độ lớn nên mômen bậc ba **triệt tiêu**.

**4. Công thức đúng, và S18 được minh oan.** Giữ cả hai nhánh:

> **γ = (1 − 2e) / √( n·h·rate·e·(1−e) )**

Kiểm trên estimator thật, 6 world mỗi điểm: dự đoán/đo được là 0,082/0,073 (e=0,6), 0,177/0,137 (0,7), 0,305/0,262 (0,8), 0,544/0,500 (0,9), 0,845/0,781 (0,95), và **0/0,0015** ở e=0,5. Khớp trong 8–22%.

Thừa số `(1−2e)` **bằng 0 ở thiết kế cân bằng với mọi độ hiếm**. Đó đúng là điều S18 kết luận từ V05 vs V05B — *"nguyên nhân là lệch propensity, hiếm chỉ khuếch đại"* — và giờ nó có công thức chứ không chỉ có hai điểm. **S18 đứng vững.**

**Hệ quả cho cổng gác — chưa thi hành.** `validated_design_region` cấp phép theo `imbalance ≤ 0,30`, tức chỉ nhìn tử số của

> `A = |1 − 2e| / √( n·h·rate·e·(1−e) )`

Nó bỏ qua `n`, `rate`, `h`. Một cohort lệch 0,25 với `rate = 0,0005` sẽ được cấp phép **sai**. Giá trị đã biết: Hillstrom primary `A = 0,0007`; V05B/V03/V01 `A = 0`; V05 `A = 0,533` (trượt). Ngưỡng nằm giữa 0 và 0,533 và **chưa biết** — lưới quét đang đo. Không sửa code trước khi có số.

### S22 — lưới ranh giới: biến đúng là `A`, không phải imbalance, cũng không phải `N_eff`

36 cell, 1.000 world mỗi cell, 515 s. Bảng đầy đủ: [OVERLAP_BOUNDARY.md](../../reports/v4/overlap_boundary/OVERLAP_BOUNDARY.md).

**1. Imbalance không phải quy tắc dùng được.** Cùng một imbalance cho hai phán quyết ngược nhau tuỳ tỷ lệ sự kiện:

| imbalance | rate 0,5% | rate 1,0% | rate 3,5% |
|---:|---|---|---|
| 0,30 | 0,934 ✗ | 0,934 ✗ | **0,955 ✓** |
| 0,40 | 0,907 ✗ | 0,924 ✗ | **0,939 ✓** |

Ranh giới theo imbalance **dịch gấp đôi** khi tỷ lệ đổi (0,20 ở 0,5% lên 0,40 ở 3,5%). Quy tắc `imbalance ≤ 0,30` mà cổng gác đang dùng vừa **quá lỏng** ở chế độ hiếm vừa **quá chặt** ở chế độ thường.

**2. `N_eff` bị bác bỏ bằng cặp trùng khớp.** Hai cell có `N_eff` **đúng bằng 10**:

| rate | `e` | `N_eff` | `A` | coverage | |
|---:|---:|---:|---:|---:|---|
| 0,005 | 0,6 | 10,0 | 0,082 | 0,951 | ✓ |
| 0,010 | 0,8 | 10,0 | 0,212 | 0,934 | ✗ |

Cùng `N_eff`, **ngược phán quyết**. `A` xếp đúng thứ tự. Giả thuyết `N_eff` của S21 chết ở đây, đúng như thiết kế thí nghiệm dự tính.

**3. `A` phân tách hoàn hảo cho `normal`.** Xếp 18 cell theo `A`: **mọi** cell `A ≤ 0,202` đạt, **mọi** cell `A ≥ 0,212` trượt. Không có chồng lấn. Hồi quy thiếu hụt coverage theo `A` cho R² = **0,909**, theo `1/√N_eff` chỉ **0,860**.

> **Ngưỡng đo được (normal): `A ≤ 0,20`.** Điểm cắt bị kẹp trong (0,202; 0,212] — hai cell cách nhau 5%, tức trong nhiễu, nên công bố mức **đạt lớn nhất**, không nội suy.

**4. Hiệu chỉnh Edgeworth mua được bao nhiêu — đo được, không phỏng đoán.**

| phương pháp | cell trượt | `A` đạt lớn nhất | `A` trượt nhỏ nhất |
|---|---:|---:|---:|
| `normal` | 7/18 | 0,202 | 0,212 |
| `skewness_adjusted_t` (không chặn df) | **1/18** | **0,584** | 0,826 |

Hiệu chỉnh mở rộng vùng dùng được **khoảng 2,9 lần** theo `A`. Đây là câu trả lời định lượng cho câu hỏi mà module đặt ra khi viết: không phải "nó hỏng", mà "nó hỏng ở đây, và hiệu chỉnh mua cho bạn chừng này".

**5. Điều quan trọng nhất: `skewness_adjusted_t` không chặn df **phủ được thiết kế của V05**.** Cell (rate 0,5%; e=0,9) — chính là V05 — cho **0,937**, đạt. Trong khi đó [validity_confirm](../../reports/v4/validity_confirm/VALIDITY_REPORT.md) ở 2.000 world vẫn trượt V05 ở 0,929. Khác biệt duy nhất về phương pháp là **sàn bậc tự do hữu hiệu**: lưới chạy `--effective-df-floor 1`, bản confirm chạy mặc định 30.

Điều này khớp với dự đoán đã bị bác bỏ ở S13: tôi từng pre-register rằng bỏ sàn sẽ làm coverage vượt quá 0,96 và cần sàn 30; thực tế bản không sàn tốt hơn, và sàn làm V05 **tệ đi**.

**Cảnh báo về tính hợp lệ của bước này.** Chọn biến thể df **sau khi** đã thấy biến thể nào đạt là **lựa chọn hậu nghiệm**. Nó không phải hạ ngưỡng — ngưỡng 0,92 không đổi, và cả ba phương pháp khoảng đều đã được khai báo trước — nhưng nó vẫn là chọn sau khi nhìn. Vì vậy:

- Đang chạy xác nhận trên **seed mới 20260925**, 2.000 world, `--effective-df-floor 1`, ghi vào `reports/v4/validity_unshrunk`.
- Kết quả đó phải được đọc là **biến thể chọn hậu nghiệm cần xác nhận độc lập**, không phải "gate đã đạt".
- Lưới chỉ chấm `dr_correct`. Bản confirm trượt **cả** `dr_correct` **và** `dr_misspecified`. Theo Qiu, nuisance sai thêm số hạng `{E‖Q̂−Q‖²}^{1/3}` **không** triệt tiêu, nên `dr_misspecified` **có thể vẫn trượt**. Chưa được phép nói gate sẽ mở.

**Chưa làm:** cổng gác vẫn cấp phép theo imbalance. Giờ đã có số để sửa, nhưng phải chờ xác nhận seed mới trước khi chốt ngưỡng vào code.

### S23 — cổng gác dùng biến đúng, và tự tố cáo khi nó chọn sau khi nhìn

Ba thay đổi code, mỗi cái có test.

**1. `design_asymmetry_index` trong `policy_comparison`.** Công thức của S21 thành hàm có hợp đồng: từ chối propensity suy biến, và **kiểm bằng test đối chiếu với skewness đo được** trên chính code path DR ([test_design_asymmetry.py](../../tests/test_design_asymmetry.py), 18 test). Đây là chỗ duy nhất trong kho có một công thức tuyên bố dự đoán một đại lượng đo được, nên test kiểm đúng điều đó chứ không kiểm số học.

**2. `CohortDesign` thay cho `cohort_propensity` trần.** Cohort phải khai báo `n_units`, `propensity`, `event_rate` và `acted_fraction`. Ngưỡng **đọc từ** `reports/v4/overlap_boundary/overlap_boundary.json`, không hard-code, và nếu sweep báo `separates=False` thì **không có ngưỡng nào được cấp** — cổng không được tự bịa ra một cái.

Quy tắc mới **thắng cả khi nó chặt hơn**. Test [`test_the_measured_rule_governs_even_when_it_is_the_stricter_one`](../../tests/test_screening.py) dựng đúng trường hợp đã hỏng: cohort `e=0,75` (imbalance 0,25, **lọt** quy tắc cũ) nhưng `n=2.000`, `rate=0,002`, `acted=0,2` cho `A = 1,25` — quy tắc mới **từ chối**. Quy tắc cũ giữ lại cho caller chỉ biết propensity, và thông điệp **nói rõ** nó là quy tắc yếu hơn.

`event_rate` lấy là **đuôi hiếm hơn** `min(p, 1−p)`: với reward phần lớn bằng 1 thì độ hiếm nằm ở các số 0, và lấy trung bình sẽ ra 0,98 — sai hoàn toàn.

**3. Cổng tự tố cáo việc chọn phương pháp.** `_read_gate` xếp artifact theo số world rồi **ưu tiên bản đạt** khi bằng power. Đó chính là *chọn sau khi nhìn*: nếu hai phương pháp khoảng cùng chạy 2.000 world và chỉ một cái qua, lấy cái qua là chọn hậu nghiệm. Quy tắc giữ nguyên — một bản đạt cùng power vẫn là bằng chứng tốt hơn **về phương pháp đó** — nhưng giờ nó không được xảy ra im lặng:

```
SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree
(reports/v4/validity_confirm/...: FAIL), so this verdict is a post-hoc
choice of interval method and needs independent confirmation
```

Câu này đi vào `gate_detail` và vào cả artifact R02. Nó tồn tại vì run `validity_unshrunk` đang chạy **sẽ** kích hoạt đúng tình huống đó nếu nó đạt, và tôi không muốn cái PASS ấy trông sạch hơn thực tế.

**4. Evidence index** báo cả hai vùng, vùng đo được trước, và gọi vùng theo scenario đúng tên: *"coarse; ignores event rate and frame size"*.

**Giới hạn phải nói rõ:** ngưỡng `A` đo trên **một** họ generator với `e` **hằng số**. Thiết kế có propensity phụ thuộc X không nằm trong phạm vi đó, và cổng hiện **không** phát hiện được sự khác biệt ấy — nó tin lời khai của caller.

### S24 — bốn hình

`telco_churn.figures`, 12 test. Nguyên tắc: **mọi giá trị trên mọi trục đọc từ file trên đĩa**. Không hàm nào tính lại kết quả, không điểm dữ liệu nào hard-code, và thiếu artifact thì hình bị **bỏ qua kèm lý do** chứ không lặng lẽ lùi về một con số nhớ được. Test kiểm đúng chuyện đó chứ không kiểm matplotlib chạy được.

| Hình | Trả lời câu gì |
|---|---|
| `boundary.png` | Coverage theo `A`, hai phương pháp, kèm vạch 0,92 và vùng được cấp phép |
| `why_not_imbalance.png` | **Hình quan trọng nhất**: cùng bộ số, trái vẽ theo imbalance (ba đường **tách nhau**), phải vẽ theo `A` (**một đường**) |
| `formula.png` | 18 thiết kế, `A` dự đoán vs skewness đo được, kèm đường `y=x` và `y=0,85x` |
| `correction.png` | Hiệu chỉnh mua được bao nhiêu, tính theo vùng cấp phép: 0,202 → 0,584 |

`formula.png` cũng cho thấy **giới hạn** của công thức chứ không giấu: mọi điểm bám sát `y=0,85x` cho tới `A ≈ 0,6`, còn cell cực đoan `A=0,826` rơi xuống 0,56 — mô hình gai dự đoán **thừa** ở đó. Đúng như vậy thì nên vẽ.

### S25 — thử phá chỉ số `A`: cả ba dự đoán đều sai

Pre-registration nằm trong docstring của [asymmetry_transfer.py](../../src/telco_churn/asymmetry_transfer.py), viết và commit **trước** khi chạy. 28 thiết kế hằng-`e` cộng 4 thiết kế nhánh ngoài phạm vi, 1.000 world mỗi cái.

| Dự đoán | Kết quả |
|---|---|
| **P1** matched `A` khớp trong 2 MCSE | **SAI** — spread 0,021–0,029 so với dung sai 0,0195 ở cả bốn mức |
| **P2** `A ≤ 0,202` phủ, trên đó không | **SAI** — ở `A=0,10` đã có 1/7 trượt; ở `A=0,20` có 3/7 trượt; ở `A=0,30` có 4/7 **đạt** |
| **P3** nhánh `e` thay đổi phủ kém hơn | **SAI như phát biểu** — đúng ở `A=0,30` (+0,036) và `A=0,55` (+0,033), **sai** ở `A=0,10` (−0,012) và `A=0,20` (−0,002) |

#### Cái gì sống sót

`A` **vẫn là biến đúng**. Hồi quy coverage trên 28 thiết kế ngoài mẫu:

| Mô hình | R² | hệ số |
|---|---:|---|
| `coverage ~ A` | **0,762** | −0,118 |
| `coverage ~ 1/√N_eff` | 0,595 | −0,115 |
| `coverage ~ A + 1/√N_eff` | 0,768 | A −0,102; `1/√N_eff` **−0,021** |

Thêm `N_eff` gần như không thêm gì (R² 0,762 → 0,768) và hệ số của nó nhỏ hơn 5 lần. Giả thuyết `N_eff` chết lần thứ hai, lần này trên dữ liệu ngoài mẫu.

**Cấu trúc tích cũng sống sót — nhưng chỉ ở `A` thấp.** Bốn thiết kế cùng tích `n·h·r = 25` nhưng khác 16 lần về `n`, 4 lần về `h`, 8 lần về rate:

| `A` | bốn coverage | spread | dung sai |
|---:|---|---:|---:|
| 0,10 | 0,943 0,945 0,946 0,950 | 0,007 | 0,0195 ✓ |
| 0,20 | 0,943 0,936 0,943 0,935 | 0,008 | 0,0195 ✓ |
| 0,30 | 0,940 0,925 0,935 0,954 | 0,029 | 0,0195 ✗ |
| 0,55 | 0,894 0,907 0,880 0,893 | 0,027 | 0,0195 ✗ |

Ở `A` thấp, `n`, `h` và rate thực sự **chỉ vào qua tích** — đúng như công thức nói, và đó là một xác nhận mạnh vì bốn thiết kế này không giống nhau ở bất cứ điểm nào khác. Ở `A` cao thì không còn.

#### Cái gì chết

**Ngưỡng sắc nét chết.** Coverage trung bình theo mức `A`: 0,942 → 0,939 → 0,938 → **0,891**. Ba mức đầu gần như phẳng và **đều dưới 0,95**; sụp chỉ xảy ra giữa 0,30 và 0,55. Không có điểm cắt nào ở 0,202 cả — **sự phân tách 18/18 hoàn hảo của S22 là đặc tính của lưới đó, không phải của `A`**.

Không đại lượng đơn nào phân tách được 28 thiết kế này: `A` chồng lấn 21 cell, `1/√N_eff` chồng lấn 17, tổng của chúng 13.

**Có một sàn thiếu hụt.** Ngay ở `A=0,10`, coverage trung bình chỉ **0,942**, không phải 0,95. Trong họ generator này có một mức thiếu hụt nhẹ không biến mất khi `A → 0`. Đó chính là ứng viên (b) mà S21 nêu: số hạng `φ(z)·z·(σ†−σ#)/σ#` của Qiu không co theo `n`.

**P3 đúng ở chỗ nguy hiểm nhất.** Nhánh `e` thay đổi không phá được gì ở `A` thấp — hợp lý, vì tính lồi của `1/(1−e)` chẳng có gì để khuếch đại khi bất đối xứng đã gần 0. Nhưng ở `A = 0,30` và `0,55` nó lấy đi 3,3–3,6 điểm coverage. Nghĩa là **cổng gác bị lừa được ở đúng vùng sát ngưỡng**, vì caller sẽ khai `e` trung bình.

#### Hệ quả bắt buộc cho cổng gác

Cổng S23 cấp phép `A ≤ 0,202` theo lưới S22. Dữ liệu ngoài mẫu nói giấy phép đó **rộng hơn bằng chứng**. Đã sửa ở S26.

### S26 — cổng gác siết lại theo bằng chứng ngoài mẫu

S23 cấp phép `A ≤ 0,584` theo lưới S22. S25 cho thấy lưới đó là dữ liệu mà công thức được rút ra từ đó, và ngưỡng **không chuyển được**. Cổng giờ đọc cả hai artifact và **lấy cái chặt hơn**:

```
measured over 18 cells at 1000 worlds each, but tightened from 0.584 because
the transfer study saw a design fail at A = 0.100, its lowest clean level,
so the licence stops strictly below that (28 out-of-sample designs)
```

Quy tắc: nếu có mức `A` nào mà **mọi** thiết kế ngoài mẫu đều phủ thì lấy mức lớn nhất như vậy; nếu ngay mức thấp nhất đã có thiết kế trượt thì giấy phép dừng **ngay dưới** mức đó. Không ngoại suy xuống dưới vùng đã thử. Nhánh `varying_propensity` **không** được tính làm bằng chứng, vì nó là control ngoài phạm vi.

Hillstrom `A = 0,0007` vẫn qua — thấp hơn 140 lần bất cứ thứ gì từng trượt. V05 `A = 0,533` vẫn bị chặn. Một cohort ở `A = 0,175` **trước đây được cấp phép, giờ bị từ chối**, và có test riêng cho đúng ca đó.

### S27 — cổng coverage ĐẠT, và tại sao vẫn phải dè dặt

`--worlds 2000 --seed 20260925 --interval-method skewness_adjusted_t --effective-df-floor 1`

| | |
|---|---|
| Scenario | **9/9 đạt** |
| Coverage failures | **0** |
| False-promotion failures | **0** |
| Nhiễu cổng (family false-failure rate) | 0,48% |
| V05 `dr_correct` | 0,929 → **0,9440** |
| V05 `dr_misspecified` | **0,9450** |

Mọi readout nằm trong khoảng. QG4 mở; evidence index chuyển **8/10 gate PASS** và release tier **ENGINEERING_FOUNDATION → RESEARCH_INTERIM**.

**Dè dặt bắt buộc, và nó được thi hành bằng code.** Biến thể df không chặn được chọn **sau khi** đã thấy nó là biến thể đạt. Bản `validity_confirm` cùng phương pháp, cùng 2.000 world, chỉ khác sàn df, vẫn **FAIL**. Cơ chế S23 phát hiện đúng tình huống này và in vào mọi `gate_detail`:

> `SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree (validity_confirm: FAIL), so this verdict is a post-hoc choice of interval method and needs independent confirmation`

Câu đó đi vào artifact R02 và vào evidence index. Cho tới khi có một lần xác nhận độc lập trên seed chưa dùng với recipe **khóa trước**, đây là "đạt có điều kiện", không phải "đã chứng minh evaluator đúng".

### S28 — V08 bỏ chặn, và hai lỗi thật trong G06

Runbook ghi V08 *"blocked on G06: the batch-policy interval has no validated domain yet"*. G06 (`batch_policy_contrast`) đã được viết từ trước, nên lý do chặn đã cũ. Dựng scenario ra thì tìm được **hai lỗi thật**, cả hai đều thuộc loại mà test cũ không bắt được.

**Lỗi 1 — khoảng `finite_batch` có bề rộng đúng bằng 0.** Nhánh ấy resample bằng `sample = identity`, tức mọi lần lặp trả về **cùng một số**, và quantile của một hằng số là chính nó. Test cũ chỉ khẳng định `finite ≤ future`, điều mà bề rộng 0 thỏa mãn một cách tầm thường. Đây đúng là lớp lỗi mà V09 từng bắt ở `q=1`. Đã sửa: khi giữ cố định batch thì thành phần còn ngẫu nhiên là nhiễu outcome, và khoảng dựng từ SE điều kiện.

**Lỗi 2 — `se_frozen_actions` không phải SE điều kiện.** Nó lấy độ lệch chuẩn của **toàn bộ** score qua các unit, nên mang cả biến thiên giữa các unit của `m_a(X)` — đó là đại lượng siêu tổng thể. Dùng nó để "điều kiện trên batch" cho khoảng quá rộng và over-cover. Đã thêm tham số `predicted_reward`: khi có means thì SE điều kiện tính trên **phần dư**, vì `m_a(X)` cố định một khi batch đã cố định. Đo được: SE điều kiện tỷ lệ với nhiễu outcome (gấp 10 lần nhiễu → gấp 10 lần SE) trong khi `se_frozen` gần như không đổi.

**Kết quả ở 500 world: ĐẠT.**

| chế độ | readout | coverage | bề rộng | materiality | |
|---|---|---:|---:|---:|---|
| noisy | `future_vs_super` | 0,946 | 0,02704 | 0,34 | ✓ |
| noisy | `finite_vs_finite` | 0,946 | 0,02024 | 0,46 | ✓ |
| noisy | `finite_vs_super` | 0,848 | 0,02024 | 0,46 | *không có gì để phát hiện* |
| predictable | `future_vs_super` | 0,964 | 0,01812 | 0,45 | ✓ |
| predictable | `finite_vs_finite` | 0,960 | **0,00324** | **2,55** | ✓ |
| predictable | `finite_vs_super` | **0,302** | 0,00324 | 2,55 | **nổ** |

Ở chế độ dự đoán được, khoảng điều kiện hẹp gấp **6 lần** (0,0032 so 0,0181) và vẫn phủ đúng target của nó ở 0,960 — trong khi đọc nó như một bảo đảm hướng tới tương lai cho **0,302**. Đó là toàn bộ nội dung cảnh báo trong docstring của `batch_policy_contrast`, giờ đã có số.

**Thiết kế scenario cũng phải sửa, và lý do đáng ghi lại.** Bản đầu dùng outcome nhị phân hiếm như mọi scenario khác trong kho, và **mọi readout phủ ở 1,000, kể cả negative control**. Đó không phải đạt, đó là scenario không thể trượt. Lý do có tính cấu trúc chứ không phải chỉnh tham số: biến thiên của sự thật giữa các batch tỷ lệ `sd(tau)/√n`, nhiễu outcome tỷ lệ `sd(score)/√n`, nên **`n` triệt tiêu** và tỷ số do generator quyết định. Với outcome nhị phân vài phần trăm, `sd(score) ≈ 2√(p(1−p)) ≈ 0,9` so với `sd(tau) ≈ 0,07`: biến thiên thành phần nhỏ hơn một bậc, hai target trùng nhau, và **không cỡ mẫu nào cứu được**.

Nên scenario chạy **hai chế độ** và báo cáo chế độ nào là chế độ nào, thay vì chỉnh generator cho tới khi control chịu nổ:

| chế độ | nhiễu | materiality | control |
|---|---:|---:|---|
| `noisy_outcome` | 0,25 | < 1 | **không có gì để phát hiện** — báo cáo đúng như vậy |
| `predictable_outcome` | 0,04 | ≈ 2,7 | **nổ** (coverage 0,36) |

`materiality` là khoảng cách sự thật dịch chuyển giữa các batch chia cho nửa bề rộng khoảng. Dưới 1 thì hai target không phân biệt được **ở bề rộng đó**, nên báo sai cái này thành cái kia không lừa được ai và một control không nổ chẳng chứng minh gì. Cổng chỉ **đòi** control nổ ở nơi materiality đạt 1 — đòi ở mọi nơi thì chỉ là một chỉ thị chỉnh generator cho tới khi nó hợp tác.

### S29 — R03: tinh chỉnh không đổi kết luận, và lý do đáng lo hơn kết luận

[RESEARCH_READINESS.md](RESEARCH_READINESS.md) gọi đây là **lỗ hổng chặn ngay** của ứng viên B: R02 so *mặc định với mặc định*, nên "baseline thắng" chưa bảo vệ được. R03 là đợt trả lời.

Giao thức theo runbook: tối đa 3 family từ shortlist R02, **đúng 8 cấu hình/family**, lồng 3 outer × 3 inner, inner search **chỉ đọc phía train** của mỗi outer fold, cùng baseline và cùng fold như R02.

| candidate | family | giá trị tuned | so baseline | **lợi từ tinh chỉnh** | config ổn định | config phân biệt được |
|---|---|---:|---:|---:|---|---|
| M01 | outcome_ranking | +0,00163 | −0,00102 | **−0,00102** | không | 8/8 |
| M03 | s_learner | +0,00207 | −0,00058 | **+0,00008** | không | 8/8 |
| M07 | dr_learner | +0,00091 | −0,00175 | **+0,00004** | không | **4/8** |

**Trả lời câu hỏi chặn: không.** Tinh chỉnh mang lại +0,00008 cho M03 và +0,00004 cho M07 — bằng 0 trong mọi ý nghĩa thực tế. Kết luận R02 *"xếp hạng theo outcome đối chứng thắng"* **không phải là artefact của hyperparameter mặc định**. Đáng chú ý là tinh chỉnh còn làm **M01 tệ đi** (−0,00102): inner search chọn `C` theo inner fold rồi outer fold không xác nhận.

**Phát hiện quan trọng hơn: không family nào chọn được cấu hình ổn định.**

| | chọn theo từng outer fold |
|---|---|
| M01 | `C=1,0`; `C=1,0`; `C=0,01` |
| M03 | `C=0,03`; `C=3,0`; `C=0,03` |
| M07 | `α=0,1`; `α=100`; `α=0,1` |

Ba fold, ba lần bất đồng, và biên độ rất rộng — `C` nhảy 100 lần, `α` nhảy 1.000 lần. Với **302 event**, dữ liệu không đủ để ghim một hyperparameter. Hệ quả cho R09: **không có recipe nào đáng đóng băng để mang sang confirmation**, và điều đó phải nói trước khi mở split, không phải sau.

**Một lỗi trong chính lưới của runbook.** Lưới DR-Ridge khai `α ∈ {0,1; 1; 10; 100} × shrinkage λ ∈ {0,5; 1}` = 8 cấu hình. Nhưng shrinkage về hằng số là **phép biến đổi affine của score**, còn allocator thì **xếp hạng** — nên λ không thể đổi được ai được chọn. Đo trên dữ liệu thật: M07 chỉ tạo ra **4/8** phân bổ khác nhau. Lưới hẹp hơn nó trông một nửa.

Đã thi hành bằng code: mỗi cấu hình ghi một `allocation_signature`, và artifact báo `distinct_configurations_searched` cùng cờ `grid_is_degenerate`. Báo 8 trial khi allocator chỉ phân biệt được 4 là nói quá về độ rộng của search. λ chỉ có nghĩa với allocator dùng **thang** của score (net-value hoặc ngưỡng), không dùng thứ hạng — đó là câu hỏi của R04, không phải R03.

### S30 — R04: tháo rời pipeline, và không tìm thấy bộ phận nào đang làm việc

R02 nói *cái nào* thắng, R03 nói tinh chỉnh không lật được. Không cái nào nói **vì sao**. R04 là đợt tháo rời.

Ba yếu tố theo E24, chéo nhau: **A** biểu diễn (base vs base + 4 tương tác khai báo), **B** tầng cuối (DR-Ridge vs DR-HGB, **cùng** nuisance cross-fit và cùng pseudo-outcome), **C** allocator (rank vs net-value). Tám cell × 3 outer fold, nhưng chỉ **12 effect fit** chứ không phải 24: C chỉ đổi allocator nên hai mức đọc **cùng một score**. Đó cũng là lý do contrast của C là *chính xác* chứ không nhiễu.

| yếu tố | từ → đến | hiệu ứng ghép cặp | se | đọc thế nào |
|---|---|---:|---:|---|
| representation | base → +tương tác | +0,000098 | 0,000209 | **0,5 se — không có gì** |
| final_stage | ridge → hgb | +0,000349 | 0,000256 | 1,4 se — gợi ý, chưa kết luận |
| allocator (chi phí đồng nhất) | rank → net_value | **+0,000000** | **0,000000** | null fixture |
| allocator (chi phí dị biệt) | rank → net_value | +0,000079 | 0,000109 | 0,7 se — không có gì |

**Null fixture giữ, và nó quan trọng.** Với chi phí đồng nhất, net value là score trừ một hằng số, mà allocator thì xếp hạng — nên hai mức **phải** chọn đúng cùng một tập khách. Đo được: hiệu ứng **đúng bằng 0,000000**, se **0,000000**, và chữ ký tập được chọn trùng khớp từng fold. Nếu nó khác 0 thì đó là lỗi allocator chứ không phải phát hiện. Chạy nó song song với chế độ dị biệt là cách duy nhất để đọc chênh lệch ở chế độ kia như *quy tắc phân bổ* thay vì như nhiễu pipeline.

**Kết luận cho ứng viên B.** Ba đợt độc lập giờ nói cùng một điều theo ba cách khác nhau:

| đợt | câu hỏi | trả lời |
|---|---|---|
| R02 | model nào thắng? | baseline outcome-ranking |
| R03 | tinh chỉnh có lật được không? | không (+0,00008) |
| R04 | **bộ phận nào đang làm việc?** | **không bộ phận nào** |

Không phải "causal learner tệ", mà là: ở **302 event**, không lựa chọn nào trong pipeline — biểu diễn, tầng cuối, quy tắc phân bổ — tạo ra khác biệt đo được. Đó là câu trả lời *vì sao* baseline thắng, và nó là một câu trả lời về **dữ liệu**, không về phương pháp.

**Ghi rõ giới hạn:** chi phí liên hệ là **giá khai báo** (`Phone 0,0020 / Web 0,0005 / Multichannel 0,0035`), không phải posting. Hillstrom không có sổ chi phí, và artifact ghi `cost_source: assumed, not measured`.

### S31 — R06: quy trình chọn có tự tạo winner giả không?

R01 chấm evaluator cho **một policy cố định**. Đó không phải bảo đảm mà workflow cần, vì workflow không đánh giá một policy cố định — nó sàng vài cái, chọn cái tốt nhất trên selection sample, rồi báo khoảng cho cái thắng. Chọn trên tiêu chí nhiễu rồi báo giá trị đã chọn là cách cổ điển nhất để tạo ra kết quả không lặp lại được, và coverage của policy cố định **không** loại trừ nó.

300 world/cơ chế, 4 recipe đóng băng, ba mẫu độc lập mỗi world (train / selection / evaluation), N = 20.000 mỗi mẫu.

| cơ chế | nhánh | promotion | 95% CI | coverage | regret |
|---|---|---:|---|---:|---:|
| null_effect | 1 candidate | 0,043 | [0,025; 0,073] | 0,917 | 0 |
| null_effect | **4 candidate** | **0,023** | [0,011; 0,047] | 0,950 | 0 |
| weak_heterogeneous | 1 candidate | 0,580 | [0,523; 0,634] | 0,957 | 0 |
| weak_heterogeneous | **4 candidate** | **0,567** | [0,510; 0,622] | 0,967 | +0,000115 |

**Không có winner's curse.** Nhìn bốn candidate thay vì một làm false promotion **giảm nhẹ** (−0,020) chứ không tăng, và dưới alternative thì hai nhánh gần như trùng. Lý do có tính cấu trúc và đó mới là điều đáng ghi: giao thức **ba mẫu** báo cáo trên mẫu *không* dùng để chọn, nên hiệu ứng chọn-rồi-báo không có chỗ phát sinh. R06 **chứng minh** điều đó bằng số thay vì giả định nó.

Giá phải trả của việc chọn là **regret**, không phải bias: +0,000115 dưới alternative, tức đôi khi selector chọn recipe hơi kém hơn cái tốt nhất. Dưới null thì regret **đúng bằng 0** theo cấu trúc, vì không recipe nào tốt hơn recipe nào.

**Không phải một cổng, và artifact tự nói vậy.** Ngưỡng false-promotion 5% **không** chấm được ở 300 world null: khoảng nhị thức 95% ở quy mô đó rộng khoảng **±0,025**, tức rộng hơn chính đại lượng đang chấm. `is_a_gate: false` nằm trong artifact, kèm lý do có mang con số. Muốn chốt cổng thì phải tăng số null replication lên hàng chục nghìn hoặc thiết kế pipeline rẻ hơn riêng cho việc đó — đúng như runbook đã cảnh báo.

### S32 — R05: không phải thiếu dữ liệu, cũng không phải seed

Hai câu hỏi khác nhau, và R05 tách chúng ra.

**Có phải do lượng dữ liệu không?** Không.

| candidate | 25% | 50% | 100% |
|---|---:|---:|---:|
| M01 | +0,002016 | +0,001791 | +0,002654 |
| M03 | +0,002167 | +0,001546 | +0,001994 |
| M07 | +0,001532 | +0,001458 | **+0,000864** |

Gấp **4 lần** dữ liệu huấn luyện (5.682 → 22.728 hàng, 50 → 201 event) và đường cong **không đi lên**. M07 thậm chí *đi xuống*. Với 3 fold thì phần lớn là nhiễu, nhưng điều rút ra được vẫn vững: **ở chế độ này thêm dữ liệu không mua được gì**, khớp với R02/R03/R04.

Nuisance bị giới hạn **cùng ngân sách** với candidate. Nếu không thì hàng 25% sẽ được chấm bởi một evaluator đã thấy gấp bốn lần dữ liệu so với model nó đang chấm — một lợi thế mà chế độ ít dữ liệu không bao giờ có trong thực tế.

**Có phải do seed không?** Không.

| candidate | IQR | đồng thuận hành động được chọn |
|---|---:|---:|
| M01 | 0,000000 | **1,000** |
| M03 | 0,000000 | **1,000** |
| M07 | 0,000058 | 0,976 |

M01 và M03 tất định hoàn toàn. M07 rung nhẹ nhưng vẫn liên hệ **97,6%** cùng một nhóm khách. Đồng thuận hành động được báo cạnh giá trị chứ không thay cho nó: hai seed cho cùng một con số nhưng liên hệ hai nhóm khách khác nhau thì **chưa tái lập được gì** mà doanh nghiệp dùng được.

**Ba seed không phải ba world**, và artifact ghi câu đó vào chính nó (`seeds_are_not_worlds`). Không có CI nào được dựng từ chúng, vì nó sẽ mô tả rung của bộ tối ưu và bị đọc thành bất định lấy mẫu.

### S33 — R08: thiết kế làm giàu rẻ hơn thật, sau khi sửa một lỗi chấm điểm của tôi

R08 đánh giá **đóng góp tự tuyên bố** của V4: thiết kế lấy mẫu làm giàu vùng bất đồng. Hai cách nó có thể được tâng bốc, cả hai đều bị chặn: so ở **cùng N tuyển** (làm giàu thắng theo cấu trúc) và **ép cỡ mẫu** về đúng mục tiêu rồi giữ trọng số cũ (thiên lệch estimator). Ở đây so ở **cùng độ chính xác**, có tính chi phí sàng lọc, và cỡ mẫu Bernoulli được để tự do dao động.

**Lần chạy đầu cho coverage 0,61 và tôi suýt báo đó là lỗi estimator.** Không phải. Tôi đã chấm khoảng `finite_frame` — thứ mà docstring của chính estimator nói là *"treats Z as fixed"* — đối chiếu với **hiệu ứng thật**. Phương sai finite-frame chỉ đếm phần mà việc rút lại mẫu tuyển sẽ làm dịch chuyển, nên nó nhắm **giá trị tổng điều tra** của frame, không nhắm hiệu ứng. **Sai target, không sai estimator.**

Sau khi mỗi khoảng được chấm với **đúng target của nó**, cả **12/12 readout có cổng đều phủ** (0,940–0,959):

| d | thiết kế | `finite_vs_census` | `super_vs_effect` | `finite_vs_effect` (control) |
|---:|---|---:|---:|---:|
| 0,05 | uniform | 0,941 | 0,953 | 0,922 |
| 0,05 | **enriched** | 0,943 | 0,952 | **0,612 nổ** |
| 0,20 | uniform | 0,945 | 0,940 | 0,902 nổ |
| 0,20 | **enriched** | 0,948 | 0,941 | **0,628 nổ** |
| 0,50 | uniform | 0,951 | 0,941 | 0,906 |
| 0,50 | **enriched** | 0,959 | 0,958 | **0,896 nổ** |

**Chi phí ở cùng độ chính xác — kết quả chính:**

| d | chi phí uniform | chi phí enriched | tỷ lệ | rẻ hơn |
|---:|---:|---:|---:|---|
| 0,05 | 3.150 | **818** | **0,260** | enriched, ~3,8 lần |
| 0,20 | 3.053 | **798** | **0,261** | enriched, ~3,8 lần |
| 0,50 | 3.032 | **1.781** | **0,587** | enriched, ~1,7 lần |

Ở mức bất đồng thấp, thiết kế làm giàu đạt **cùng bề rộng khoảng** với **26% chi phí**. Ở `d = 0,50` lợi thế thu hẹp còn 1,7 lần, đúng như dự đoán: công thức chỉ đẩy `q_D` lên 0,35 khi một nửa frame đã bất đồng, nên gần như không còn chỗ để làm giàu. **Chỉ báo mức `d = 0,05` sẽ nói quá về phương pháp.**

Đây là kết quả **dương** đầu tiên cho một thứ mà kho này tự tuyên bố, và nó đứng được vì so sánh ở cùng độ chính xác chứ không cùng N, và vì chi phí sàng lọc của chính thiết kế làm giàu được tính vào.

**Negative control chỉ nổ ở thiết kế làm giàu** (0,612 / 0,628), không nổ ở uniform tại d = 0,05 và 0,50. Lý do đáng ghi: làm giàu kéo `q_D` lên 0,8 nên phương sai tuyển co lại, để nhiễu score trở thành thành phần chi phối — đúng chỗ mà giả định "Z cố định" sai nhất. **Khoảng càng hẹp thì đọc sai nó càng nguy hiểm.** Đây là **lần thứ ba** cùng một bài học xuất hiện trong kho (V09 ở `q=1`, V08 ở batch có cap, giờ là R08).

**Giới hạn:** chi phí là **giá khai báo** (`sàng 0,01 / tuyển 1,00 / nhãn 0,50`), không phải posting. Output là **tỷ lệ chi phí ở cùng độ chính xác**, không phải tuyên bố lợi nhuận.

### S34 — R07 bỏ chặn: replay chứ không chấm lại

Runbook đánh dấu R07 `BLOCKED_BY_IMPLEMENTATION` và nói rõ lý do: *"actions phải thay future state, không tái chấm fixed logged trajectory như rollout truth"*. Simulator cũ gán treatment **ngẫu nhiên** và không lái được bằng policy, nên chấm chiến lược trên log cố định của nó chỉ đo được mức độ mỗi chiến lược *đồng ý với một policy ngẫu nhiên* — không phải câu hỏi cần trả lời.

`telco_churn.temporal_replay` là replay đó. Mỗi chiến lược lái **quỹ đạo riêng**: liên hệ của nó đổi churn, đổi lịch sử liên hệ (mệt mỏi liên hệ), đổi ai còn hoạt động. Đến tháng thứ ba hai chiến lược đã đối mặt **hai cohort khác nhau**. Nhãn chín có độ trễ khai báo, và một lần refit chỉ được đọc nhãn đã chín **trước** thời điểm cắt của nó.

40 world/cơ chế, 3.000 tài khoản, 12 tháng huấn luyện + 12 tháng quyết định.

| cơ chế | chiến lược | tránh (cả kỳ) | so frozen | tránh (nửa sau) | **nửa sau so frozen** | se |
|---|---|---:|---:|---:|---:|---:|
| covariate_shift | calibration_only | 31,1 | +0,1 | 6,7 | +0,0 | 0,0 |
| covariate_shift | full_expanding | 31,1 | +0,1 | 6,7 | +0,0 | 0,0 |
| covariate_shift | **rolling_6** | 33,5 | **+2,5** | 9,2 | **+2,5** | 0,5 |
| effect_reversal | calibration_only | 2,7 | +0,1 | −10,4 | +0,1 | 0,1 |
| effect_reversal | **full_expanding** | 8,7 | **+6,0** | −4,4 | **+6,1** | 0,5 |
| effect_reversal | rolling_6 | 6,2 | +3,5 | −6,2 | +4,3 | 0,5 |
| ingestion_delay | calibration_only | 33,2 | −0,1 | 9,2 | −0,1 | 0,0 |
| ingestion_delay | full_expanding | 33,3 | −0,1 | 9,3 | +0,0 | 0,0 |
| ingestion_delay | **rolling_6** | 28,9 | **−4,4** | 7,7 | **−1,6** | 0,6 |

**Không chiến lược nào thắng ở cả ba cơ chế.** `rolling_6` thắng rõ dưới covariate shift (+2,5 = 5 se) và **thua nặng nhất** dưới ingestion delay (−4,4). `full_expanding` thắng dưới effect reversal (+6,0 = 12 se) nhưng gần như bất động dưới covariate shift, vì 12 tháng huấn luyện trước-drift pha loãng mọi thứ nó học thêm. Đó là điểm yếu đã biết của cửa sổ mở rộng, và ở đây nó **đo được**.

**`calibration_only` không cứu được effect drift**, đúng như runbook cảnh báo. Nó refit đường cong rủi ro nhưng giữ nguyên ước lượng *lift* từ lúc huấn luyện, nên khi hiệu ứng đảo dấu nó vẫn liên hệ như cũ: +0,1 so với frozen, tức **không làm gì cả**. Tên gọi "calibration" mang tải nghĩa và test khoá đúng điều đó.

**Dưới effect_reversal, nửa sau có giá trị âm** (frozen −10,5): khi hiệu ứng đã đảo, việc liên hệ **chủ động gây** churn. `full_expanding` giảm thiệt hại xuống −4,4 nhưng không tránh được.

**Một lỗi thiết kế đã phải sửa.** Bản đầu để chiến lược đọc thẳng `world.risk` — tức rủi ro **thật**. Một chiến lược biết sự thật thì không có gì để học, refit chỉ thêm nhiễu, và `frozen` thắng theo cấu trúc ở cả ba cơ chế. Đó là scenario không đo được gì. Đã sửa: chiến lược chỉ thấy đặc trưng quan sát được `x` và phải **học** rủi ro gắn với nó từ nhãn đã chín.

**Cột "nửa sau" tồn tại vì tổng cả kỳ giấu mất hiệu ứng.** Những tháng đầu chi phối tổng — pool còn lớn, mệt mỏi chưa tích tụ, mọi chiến lược còn dùng chung một model vừa fit. Runbook yêu cầu cả readout theo tháng lẫn theo toàn kỳ, và đây là lý do.

### S35 — kết luận của R02–R05 **không lặp lại** sang nhánh còn lại của chính dataset đó

R02 đến R05 đều chạy trên **Mens E-Mail vs No E-Mail**. Hillstrom có ba nhánh, nên chạy lại **toàn bộ** giao thức trên **Womens E-Mail vs No E-Mail** gần như miễn phí. Tôi làm vậy để kiểm tra độ bền. Kết quả **đảo ngược kết luận chính**.

**R02 — bảng xếp hạng lật:**

| | Mens (251→302 event) | Womens (251 event) |
|---|---|---|
| Ai thắng | **M01 thắng cả tám** | **M03 (S-Logistic) thắng**, +0,001412 so M01 |
| M01 đứng đâu | nhất | **gần bét** — chỉ hơn M04 |
| Shortlist | M01, M03, M07 | M02, M03, M07 |

Trên nhánh Womens, **bốn** candidate nhân quả (M03 +0,001412, M05 +0,000780, M07 +0,000593, M02 +0,000496) đều vượt baseline.

**R05 — learning curve xuất hiện:**

| candidate | 25% | 50% | 100% |
|---|---:|---:|---:|
| M03 (Womens) | +0,000956 | +0,001142 | **+0,001841** |
| M01 (Womens) | +0,000746 | +0,000477 | +0,000429 |

M03 tăng **đơn điệu** theo dữ liệu trên nhánh Womens — đúng thứ mà nhánh Mens **không** có. Còn M01 thì *giảm*.

**R04 — dấu của hiệu ứng lật:**

| yếu tố | Mens | Womens |
|---|---:|---:|
| final_stage ridge → hgb | +0,000349 (1,4 se) | **−0,000492 (3,3 se)** |

Trên Mens, HGB hơi tốt hơn và không kết luận được. Trên Womens, HGB **kém hơn** và mức 3,3 se. Null fixture vẫn giữ ở cả hai nhánh, nên đây không phải lỗi pipeline.

#### Điều này có nghĩa gì

Kết luận *"trong chế độ ít sự kiện, xếp hạng theo outcome đối chứng thắng các causal learner"* — thứ mà S29/S30/S32 vừa củng cố bằng ba đợt độc lập — **là kết luận riêng của một nhánh**, không phải một tính chất chung. Ba đợt ấy đồng thuận với nhau vì chúng dùng **cùng một cohort**, không phải vì kết luận vững.

Có thể chênh lệch giữa hai nhánh là nhiễu: 3 fold, ~250–300 event mỗi bên. Nhưng điều đó **cũng** là lý do để không phát biểu kết luận chung: nếu hai nhánh của *cùng một thí nghiệm, cùng một tệp khách hàng, cùng một giao thức* đã cho hai câu trả lời ngược nhau, thì một nhánh không đủ để nói gì về phương pháp.

**Đây không phải R10.** Cùng dataset, cùng khách hàng, cùng thời kỳ, chỉ khác nội dung email. Nó không cung cấp bằng chứng ngoài miền. Nó chỉ chứng minh rằng bằng chứng hiện có **mỏng hơn** ba đợt đồng thuận khiến người ta tưởng.

**Hệ quả cho ứng viên B: phải phát biểu lại lần nữa,** và lần này yếu hơn hẳn. Xem [RESEARCH_READINESS.md](RESEARCH_READINESS.md).

### S36 — R09: quyết định **không** mở split confirmation

Chi tiết đầy đủ và điều kiện mở: [R09_CONFIRMATION_DECISION.md](../R09_CONFIRMATION_DECISION.md).

Runbook đòi ký manifest có **model recipes/settings** trước khi mở. Không có recipe nào đáng ký:

1. **R03**: không family nào chọn được cấu hình ổn định qua ba fold (`C` nhảy 100 lần, `α` nhảy 1.000 lần).
2. **S35**: người thắng **không lặp lại** sang nhánh Womens của chính dataset đó.
3. **S27**: evaluator mới chỉ đạt qua một biến thể **chọn hậu nghiệm**, chưa xác nhận độc lập.
4. **R04/R05**: không thành phần nào tạo khác biệt đo được, nên chưa có giả thuyết cụ thể để xác nhận.

Split dùng được **một lần**. Mở hôm nay sẽ cho một con số mà dù ra sao cũng không diễn giải được, và không thể đóng lại. R10 (miền độc lập) đứng trước R09 trong hàng đợi.

### S37 — Lenta qua được audit assignment

R10 cần một miền độc lập mà DR **được phép** chạy trên đó. Cùng phép kiểm đã bác bỏ Orange và cho Hillstrom qua, chạy trên mẫu con 60.000 hàng của split development Lenta, 50 permutation refit toàn bộ pipeline:

| | Orange | Hillstrom | **Lenta** |
|---|---:|---:|---:|
| OOF ROC-AUC dự đoán treatment | 0,6355 | 0,4975 | **0,5037** |
| p (add-one permutation) | 0,0099 | 0,6832 | **0,1765** |
| Brier skill so hằng số | — | −0,0007 | **−0,0046** |
| ESS giữ được dưới `e(X)` | **0,04%** | 99,95% | **97,91%** |
| Dùng được design probability? | **không** | có | **có** |

Không bác bỏ pooled-IID exchangeability. Đây là dataset **thứ hai** trong kho có propensity thiết kế dùng được, và là điều kiện để R10 chạy DR.

**Hai giới hạn phải nói:** audit chạy trên mẫu con 60.000 hàng (không phải toàn bộ 549.867), nên p-value hợp lệ cho mẫu con đó; và propensity ước lượng chạm **0,9999** ở đuôi trên, dù ESS 97,9% cho thấy phần đuôi ấy không gánh ước lượng. Không bác bỏ ≠ chứng minh randomised.

**Chỉ số bất đối xứng cấp phép cho Lenta dù nó lệch.** `e = 0,751`, tức imbalance **0,251** — sát ngưỡng 0,30 của quy tắc cũ. Nhưng với 60.000 hàng và tỷ lệ response 10,8%, `A = 0,032`, thấp hơn nhiều so với ngưỡng thi hành 0,100. Đây đúng là trường hợp mà quy tắc imbalance trần sẽ đánh giá sai và chỉ số gộp bốn thừa số thì không.

### S38 — R10: lời giải thích "thiếu sự kiện" đúng, nhưng chỉ một nửa

Lenta, chiến dịch SMS của một chuỗi bán lẻ: khác công ty, khác nước, khác kênh, khác outcome, khác dân số, và **khác chế độ sự kiện** (10,8% response so với 0,9% của Hillstrom). Cùng `run_screening` / `run_bounded_tuning` / `run_learning_curves` mà các đợt Hillstrom đã gọi — tái hiện giao thức chứ không viết lại nó. 60.000 unit, **6.498 event** (21 lần Hillstrom), 45 phút.

Ba dự đoán viết trong docstring **trước** khi chạy:

| | Dự đoán | Kết quả |
|---|---|---|
| **P1** | Ít nhất một causal learner thắng M01 | **ĐÚNG, rất mạnh** |
| **P2** | Bất ổn hyperparameter biến mất khi có nhiều event | **SAI** |
| **P3** | Learning curve xuất hiện | **ĐÚNG** |

**P1 — không phải "ít nhất một", mà là tất cả.** Cả **bảy** candidate nhân quả vượt M01, và **M01 đứng bét với giá trị âm**:

| candidate | policy value | so M01 |
|---|---:|---:|
| M06 (T-HGB) | +0,002270 | **+0,003334** |
| M03 (S-Logistic) | +0,001463 | +0,002528 |
| M08 (DR-HGB) | +0,000898 | +0,001962 |
| M05 (T-Logistic) | +0,000882 | +0,001946 |
| M07 (DR-Ridge) | +0,000059 | +0,001123 |
| M04 (S-HGB) | −0,000366 | +0,000698 |
| M02 (outcome HGB) | −0,000488 | +0,000577 |
| **M01 (baseline)** | **−0,001064** | 0 |

**P3 đúng**: M02, M06, M08 đều cải thiện từ 25% lên 100% dữ liệu — đúng thứ mà nhánh Mens của Hillstrom không có.

#### Bức tranh ba điểm, và nó mạch lạc

| dataset | event | ai thắng |
|---|---:|---|
| Hillstrom Mens | 302 | M01 (baseline) |
| Hillstrom Womens | 251 | M03 |
| **Lenta** | **6.498** | **cả bảy causal learner; M01 bét** |

Lời giải thích "thiếu sự kiện" **được xác nhận**: ở ~300 event thứ hạng là nhiễu (hai nhánh cho hai người thắng), ở ~6.500 event causal learner thắng dứt khoát. Đây là phát biểu mạnh hơn và bảo vệ được hơn cả hai phát biểu trước đó của dự án.

#### P2 sai, và đó là phần quan trọng cho R09

Với **21 lần** số event, **vẫn không family nào** chọn được cấu hình ổn định qua ba fold. Bất ổn hyperparameter **không phải** vấn đề đếm sự kiện — nó là tính chất của tiêu chí chọn bên trong, và thêm dữ liệu không sửa.

Điều này **củng cố** quyết định S36: lý do số 1 để không mở confirmation (không có recipe nào đáng đóng băng) vừa được kiểm ở quy mô lớn hơn 21 lần và vẫn đúng.

Đáng chú ý thêm: tinh chỉnh làm **tệ đi** ở hai trong ba family (M02 −0,000499; M08 −0,001947). Inner search chọn theo inner fold rồi outer fold không xác nhận — cùng hiện tượng đã thấy với M01 trên Hillstrom.

#### R04 **không** được chạy ở đây, có chủ đích

Yếu tố biểu diễn của nó định nghĩa bằng chính các cột của Hillstrom, và mô hình chi phí của nó khoá vào cột `channel` mà Lenta không có. Chạy một factorial **khác** rồi gọi cùng tên stage chính là kiểu thay thế ngầm mà đợt này tồn tại để phát hiện. Artifact ghi rõ lý do.

#### Hệ quả cho cổng

Release tier **RESEARCH_INTERIM → RESEARCH_REPLICATED**, **9/10 cổng PASS**. Cổng duy nhất còn lại là prospective partner trial, cần một đối tác thật và một sổ chi phí thật — nằm ngoài phạm vi dự án này theo đúng ràng buộc đã khai báo.

**Giới hạn phải nói:** hai dataset dưới một giao thức là **mức tối thiểu** để gọi là replication, không phải câu trả lời đã chốt. Lenta được chạy trên mẫu con 60.000 hàng đã khai báo của split development 549.867 hàng, ba outer fold.

### Sweep cỡ mẫu: V05 không sửa được bằng thêm dữ liệu

| n | event/world (V05) | coverage DR |
|---:|---:|---:|
| 10.000 | 46 | 0,920 |
| 40.000 | 182 | 0,922 |
| 160.000 | 727 | 0,936 |

Tăng cỡ mẫu **16 lần** chỉ đưa coverage từ 0,920 lên 0,936 và skew giữ nguyên ~46, vì skew đến từ `e=0,9` chứ không từ số hàng. Hệ quả thực tế: với một campaign có allocation lệch, **thu thêm dữ liệu không làm khoảng tin cậy DR đáng tin hơn** — phải sửa thiết kế hoặc sửa phương pháp khoảng.

### Hệ quả

1. **R02 vẫn bị chặn** cho tới khi một phương pháp khoảng qua được toàn bộ 29 readout.
2. **Không hạ ngưỡng 0,92.**
3. Hillstrom (primary thật) có `e≈0,5` cân bằng — nằm trong vùng mọi phương pháp đều đạt. Nhưng gate là gate: nó phải qua trước, không có ngoại lệ theo dataset.


## Kết quả R02 — screening đầu tiên chạy được

Hillstrom development, Mens E-Mail so No E-Mail: 34.092 khách, 302 conversion, e = 0,4987, cap 20%, 3 outer fold dùng chung, evaluator là paired DR cross-fitted với nuisance chỉ fit trên phía train.

| ID | Candidate | Policy value | Δ so M01 | 95% qua fold |
|---|---|---:|---:|---|
| **M01** | Control-outcome Logistic | **+0,00265** | — | baseline |
| M03 | S-Logistic | +0,00199 | −0,00066 | [−0,00184; +0,00051] |
| M06 | T-HGB | +0,00177 | −0,00088 | [−0,00205; +0,00028] |
| M04 | S-HGB | +0,00123 | −0,00142 | [−0,00312; +0,00028] |
| M02 | Control-outcome HGB | +0,00122 | −0,00143 | [−0,00171; −0,00116] |
| M05 | T-Logistic | +0,00100 | −0,00165 | [−0,00250; −0,00080] |
| M07 | DR-Ridge | +0,00087 | −0,00179 | [−0,00239; −0,00119] |
| M08 | DR-HGB | +0,00083 | −0,00183 | [−0,00218; −0,00147] |

Shortlist theo luật đã khai báo (một đại diện mỗi họ): **M01, M03, M07**.

**Baseline đơn giản nhất thắng cả tám.** Điều này lặp lại phát hiện của Orange — nhưng lần này trên một dataset **cân bằng, 3,5× lớn hơn, và có randomisation sống sót qua audit**. Đó là điều Orange không cho phép nói.

Giới hạn phải nói kèm:

- CI ở đây là biến thiên **qua 3 fold của một dataset**, không phải population uncertainty. M03, M04, M06 có khoảng cắt 0: chưa phân biệt được với baseline.
- M02, M05, M07, M08 có khoảng **hoàn toàn dưới 0**: bốn candidate này thua baseline một cách nhất quán qua cả ba fold.
- Development only. Split confirmation **chưa mở**, và theo protocol nó chỉ được mở một lần, sau khi R03 đóng băng recipe cuối.
- Đây là shortlist, không phải kết luận. Runbook đặt R03 (bounded tuning) trước khi có bất kỳ candidate nào được đề cử.
