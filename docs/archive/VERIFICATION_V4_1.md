# Kiểm chứng và vòng triển khai 2 — V4.1

Ngày: 21/09/2026. Tài liệu này ghi **những gì đã chạy trong lượt này**, đối chiếu claim trong repo với artifact trên đĩa, và ghi phần code mới được thêm theo [MASTER_PLAN §18](MASTER_PLAN.md) bước 2.

Khác với lượt 20/09 (chỉ hoàn thiện tài liệu), lượt này **có sửa source, có chạy lại tests và có sinh artifact mới**. Không có claim business nào mới; mọi thay đổi nằm ở cổng tính đúng, một allocator và một giao diện đọc bằng chứng.

## 1. Tái hiện trạng thái đã công bố

| Kiểm tra | Kết quả | Ghi chú |
|---|---|---|
| `python -m pytest` trước khi sửa | 134 passed, 7,2 s | khớp con số trong README |
| `python -m ruff check .` trước khi sửa | pass | |
| `python -m telco_churn.challenge_suite` | JSON **giống từng byte** bản lưu (bỏ timestamp) | 15/15 critical, 0 false block |
| `python -m telco_churn.problem_contract_cli` | 3 revision, 1 promotable | khớp manifest |
| `python -m telco_churn.inference_smoke --worlds 1000` | `paired`/`unpaired` block **giống hệt** artifact cũ | bias, coverage, CI width không đổi |
| `python -m telco_churn.assignment_audit --permutations 100` | ba block `treatment_predictability`, `permutation_test`, `estimated_propensity` **giống hệt từng trường** | 229,8 s cho 100 permutation (bản ghi cũ: 469,88 s trên cùng máy, khác machine load) |
| Host↔API prediction parity | max |chênh lệch| = 9,54e−17 trên 50 record | đúng nghĩa "parity 0" tới sai số dấu phẩy động |
| Docker Compose smoke | **đã chạy, 12/12 check pass** | Docker Desktop được khởi động trong lượt này; chi tiết ở [DEPLOYMENT.md](../DEPLOYMENT.md) |

Kết luận phần này: các con số đang công bố trong README/status/ledger **tái hiện được** trên máy hiện tại, trừ Docker vốn đã được ghi là chưa xác minh.

### Một phát hiện về CI, không phải về kết quả

`.github/workflows` chạy `ruff format --check .`. Lệnh này **fail trên 31 file**, trong đó 27 file có từ trước lượt này (`train.py`, `orange_benchmark.py`, `simulation.py`, `uplift.py`, `api.py`, …). Repo chưa bao giờ ở trạng thái ruff-format sạch, nên bước CI đó đang đỏ độc lập với mọi thay đổi ở đây. `ruff check .` (lint) thì pass.

Lượt này **không** format lại repo: đó là một diff lớn chạm vào các module sinh ra artifact đã công bố, và là một quyết định riêng. Hai lựa chọn cho chủ dự án: bỏ bước `ruff format --check` khỏi CI, hoặc format toàn repo trong một commit riêng không kèm thay đổi logic.

### Đo lại API latency

`python -m telco_churn.performance` chạy lại trên cùng bundle: p95 **17,05 ms** (trước: 22,79 ms), 0 lỗi/1.000 request. Đây là **cùng code phục vụ inference**, chênh lệch là machine load; cả hai lần đo được giữ cạnh nhau trong [PERFORMANCE_REPORT](../../reports/api/PERFORMANCE_REPORT.md), không ghi đè.

## 2. Khoảng trống G01–G08: trạng thái sau lượt này

[MASTER_PLAN §1.2](MASTER_PLAN.md) liệt kê 8 khoảng trống phải xử lý trước screening. Bước 2 của §18 yêu cầu đóng G01/G02/G04/G05 và chốt target/reward units (G07) **bằng test trước tiên**.

| ID | Trạng thái trước | Đã làm trong lượt này | Trạng thái sau |
|---|---|---|---|
| G01 | `dr_action_scores` clip e ở 0,001 sau khi kiểm row sums | Tách ba chế độ: `unmodified` (primary, dùng e nguyên), `reject` (support contract, fail kèm row key), `clip` (sensitivity đã khai báo, đếm số cell bị sửa). Thêm `SupportDiagnostics`: min e, max weight, ESS, ESS ratio, số cell dưới sàn | **đóng** — A01 + Q19 |
| G02 | nuisance gather theo vị trí | Join theo row key: index phải trùng nhau đúng thứ tự, `align_by_row_key()` cho phép reindex tường minh, reject duplicate key, reject nhãn action trùng sau `str()` (`1` vs `"1"`), reject cột trùng tên, reject NaN/Inf kèm row key | **đóng** — A02/A03/A04 + Q20 |
| G03 | HT variance có hệ số `(1−q)`; q=1 ⇒ SE=0 | Tách hai domain: `se_recruitment_only` (conditional trên score đã hiện thực) và `se_superpopulation` (thêm noise của assignment/outcome), `variance_target` phải khai báo, `scope_note` đi kèm kết quả | **đóng** — A05/A06 + Q21 |
| G04 | `run_stage` kiểm artifact bằng `.exists()` | So chữ ký (mtime_ns, size, sha256) **trước và sau** khi stage chạy: file không được ghi lại trong lần chạy này là `STALE_ARTIFACT`. Manifest có `run_id`, `config_hash`, environment, hash từng artifact; completion marker ghi sau cùng và chỉ cho run `COMPLETE` | **đóng** — A07/A09 + Q22 |
| G05 | `TimeoutExpired` không có nhánh xử lý | `TIMED_OUT` và `LAUNCH_FAILED` là trạng thái stage; manifest vẫn được ghi; output của child bị giết không được publish | **đóng** — A08 + Q23 |
| G06 | batch-policy CI chưa có domain riêng | chưa làm | **còn mở** — cần V08 |
| G07 | endpoint là cancellation nhưng `reward_unit` là tiền | `EndpointSpec` (`target_id`, `target_kind`, `orientation`, `unit`, `role`, cửa sổ quan sát, `maturity_rule`); contract phải có đúng một endpoint `outcome`, cửa sổ khớp horizon, và `reward_unit` phải do một endpoint khai báo sinh ra. Registry thật khai báo `cancellation90` (binary, adverse), `prevented_cancellation90` (effect) và `net_contribution90` (currency, reward) | **đóng** — A11 + Q24 |
| G08 | `screen`/`confirm` chưa có; Hillstrom chưa có | chưa làm; hai profile vẫn chủ động `NotImplementedError` | **còn mở** |

## 3. Test plan A01–A24: phần đã có

| ID | Nội dung | Trạng thái |
|---|---|---|
| A01 | e=0,0005 dùng nguyên hoặc reject, không âm thầm thành 0,001 | có, `tests/test_estimator_contracts.py` |
| A02 | hai frame cùng length, row ID đảo thứ tự | có |
| A03 | nhãn `1` và `"1"`, cột trùng, nhãn lạ | có |
| A04 | NaN/Inf trong reward/propensity/nuisance | có |
| A05 | q=1, reward nhiễu, CI tổng không co về 0 | có |
| A06 | redraw S/A/Y độc lập, so variance báo cáo với variance thực nghiệm | có, budget 600 world: SE báo cáo 0,0988 so SD thực nghiệm 0,1010 (lệch 2,3%); recruitment-only understate 1,28× |
| A07 | stage exit 0, file có sẵn từ run khác | có, `tests/test_research_runner.py` |
| A08 | child timeout, executable không tồn tại | có |
| A09 | manifest còn khi run fail; marker chỉ cho run COMPLETE; marker pin hash manifest | có |
| A10 | cache cùng seed khác inner training IDs | **chưa** — chưa có cache layer |
| A11 | endpoint tiền không có reward spec | có, `tests/test_endpoints_and_evidence.py` |
| A12 | batch-policy CI (V08) | **chưa** — phụ thuộc G06 |
| A13 | all-equal scores, hoán vị hàng, N=1/4/5/6, K=floor(0,2N) | có, `telco_churn.allocation` |
| A14–A24 | bootstrap occurrences, adapter, preprocess, data roles, ledger, temporal, reporting gate | **chưa** |

### A13 và một khác biệt convention đã tìm thấy

`top_fraction_mask` trong `uplift.py` dùng `ceil(fraction × N)`, trong khi V4.1 khai báo cap là `floor(0,2N)`. Ở N=2.380 và 30%, hai quy tắc chênh nhau 1 đơn vị; với một hard cap thì đó là vi phạm, không phải làm tròn.

Xử lý: **không** sửa `top_fraction_mask` — budget curve đã công bố được sinh bằng nó, và sửa sẽ làm artifact cũ không tái hiện được. Thay vào đó `telco_churn/allocation.py` là allocator triển khai với cap `floor`, tie-break ổn định theo `(−score, unit_id)`, không ép chọn đơn vị có score không dương, và mỗi đơn vị có `reason`. Console để người đọc chuyển giữa hai convention và thấy chênh lệch.

Kiểm chứng: allocator mới chạy với convention `ceil` ở đúng model và budget đã khóa **tái tạo chính xác** quyết định đã công bố — `test_dr_uplift` 0,0333090725007235, cùng 714 đơn vị, 0 thêm 0 bớt (`tests/test_dashboard.py`).

## 4. Bộ kiểm chứng: 18 → 24 mutation

| ID | Fault được khai báo | Detector |
|---|---|---|
| Q19 | design probability bị thay bằng sàn | `propensity_support_contract` |
| Q20 | nuisance frame join theo vị trí sau khi shuffle | `row_key_join_contract` |
| Q21 | census recruitment báo cáo là zero uncertainty | `recruitment_variance_decomposition` |
| Q22 | artifact của run trước xác nhận run này | `artifact_freshness_gate` |
| Q23 | stage timeout làm mất manifest | `timeout_manifest_contract` |
| Q24 | reward tiền gắn vào endpoint sự kiện | `endpoint_unit_contract` |

Vòng chạy hiện tại: **21/21 critical được phát hiện, 0 false block, 24/24 case chạy**. Meta-test vẫn giữ: gate chuyển FAIL khi một critical mutation lọt lưới, khi một fixture sạch bị chặn, hoặc khi một mutation đã khai báo không được chạy.

Cách đọc không đổi: pass nghĩa là **24 lỗi đã khai báo** bị bắt, không nghĩa pipeline an toàn.

## 4b. Triển khai — mục treo đã đóng

Ledger từ vòng 1 ghi “Docker compose chưa smoke lại ở snapshot cuối”. Lượt này daemon đã lên và stack đã chạy thật:

- **parity host↔container 1,110e−16** trên 50 record (ngưỡng 1e−12) — claim “Docker parity = 0” giờ có số đo, không phải ký ức;
- console trong container **tái tạo quyết định Orange đã khóa** lệch 1,4e−17, quyết định vẫn `no_launch`;
- `evidence_snapshot` của container trùng host (`88e731be5bdf55a6`) — image phục vụ đúng snapshot của repo;
- migration Postgres áp đủ 4 bảng; record mâu thuẫn schema bị trả 422; POST vào console trả 405;
- cả hai container uid 65532, filesystem read-only (đã thử ghi và bị chặn), image console không có catboost/sklearn/scipy/mlflow.

Để console không phải mang training stack, `bootstrap_selected_effect` chuyển sang `telco_churn/resampling.py` (chỉ NumPy) và `uplift.py` re-export — một implementation, mọi import cũ giữ nguyên, số của quyết định đã khóa không đổi.

Cổng mới trong chỉ mục bằng chứng: `deployment_replay` (QG7). Đầy đủ: [DEPLOYMENT.md](../DEPLOYMENT.md).

## 4c. R00 và R01 — cổng chặn model screening

Runbook đặt điều kiện mở R02 là “R01 validity gates đạt”. Artifact: [VALIDITY_REPORT.md](../../reports/v4/validity/VALIDITY_REPORT.md); nhật ký đầy đủ kèm đính chính: [STAGE_LOG.md](STAGE_LOG.md).

- **R00 — 6/6 exact identity pass**, gồm điểm runbook nhấn: với reward hằng số, DR bằng đúng 0 ở **mọi** realization còn IPW chỉ 0 **trong kỳ vọng**, kiểm bằng enumeration toàn bộ 2⁶ assignment.
- **R01 — FAIL: 4/29 readout**, 0 false promotion, 1.000 world/scenario.

**Một lỗi trong chính công cụ đo đã được tìm ra và sửa.** Bản R01 đầu tiên báo V03 không đạt; kết luận đó **sai**. Seed world được tạo từ vị trí scenario trong danh sách, nên `--scenarios V03` và full run sinh hai tập world khác nhau cho cùng generator đã đông cứng. Sau khi khóa seed theo hash của `scenario_id`, V03 đạt 0,950–0,953. Có test chặn hồi quy.

**Quy luật sau khi sửa:** DR interval chỉ hỏng ở hai scenario có **propensity lệch** — V04 (e=0,2/0,8): 0,934/0,931; V05 (e=0,9): 0,887/0,886. Mọi thiết kế cân bằng đạt, kể cả heavy-tail t(3) và clustered. Miss lệch hẳn một phía (V05: 0,006 dưới / 0,107 trên) và bias nằm trong 1 MCSE — **lỗi của khoảng tin cậy, không phải của estimator**.

**Ba phương pháp khoảng đã thử ở scale gate:** normal (681 s, 4 fail); studentized bootstrap B=499 (2.072 s, sửa asymmetry của V05 nhưng thêm 2 fail mới — B quá nhỏ cho quantile đuôi); skewness-adjusted Cornish–Fisher. Bootstrap **không** được nhận mặc định.

**Sweep cỡ mẫu:** tăng n 16 lần (46 → 727 event) chỉ đưa V05 từ 0,920 lên 0,936. Skew đến từ thiết kế `e=0,9`, không từ số hàng: **thu thêm dữ liệu không sửa được khoảng tin cậy dưới allocation lệch**.

Hệ quả: **R02 vẫn bị chặn**, ngưỡng 0,92 **không** được nới.

## 5. Hai thành phần mới

### `telco_churn.evidence` — chỉ mục bằng chứng

Một chỗ trả lời ba câu cho mỗi artifact: nó có tồn tại không (kèm SHA-256), nó có **cũ hơn module sinh ra nó** không (cờ `producer_newer`, phục vụ QG0), và nó nuôi cổng nào. Release tier được **tính** từ các cổng theo [MASTER_PLAN §16](MASTER_PLAN.md), không phải khai báo.

Trạng thái hiện tại: `ENGINEERING_FOUNDATION`. Hai cổng chặn `RESEARCH_INTERIM` là `inference_coverage` (1/8 canonical scenario) và `real_domain_identification` (Orange vẫn conditional). `NOT_MET` không phải fail và cũng không phải pass — nó là một cổng đã định nghĩa chưa được thỏa mãn.

### `telco_churn.dashboard` — decision console

Trang đọc-only tại `http://127.0.0.1:8050` gom cổng, mutation, coverage, audit, capacity và mechanism lab vào một chỗ, kèm evidence state của từng con số. Ba quy tắc nó tự áp:

1. Không tính gì từ dữ liệu mà report chưa mở. Capacity curve đọc lại `holdout_predictions.csv`, không refit gì và không thấy raw features.
2. Kéo slider **không phải** một nghiên cứu mới. `evidence_state: EXPLORATORY` nằm trong payload API, không chỉ trong chữ trên trang.
3. Artifact thiếu thì hiện là thiếu — không có fallback hiển thị số cũ thay cho số chưa từng được sinh.

Trang giữ nguyên danh sách **phát biểu không được viết** (ledger §7) ở cuối, vì console chính là nơi một con số conditional dễ biến thành claim nhất.

## 6. Kết quả mới có thể đọc được từ lượt này

Chỉ hai, và cả hai là về method, không phải về thị trường:

1. **Recruitment-only variance understate tổng uncertainty 1,28× ở scenario đã kiểm** (600 world, q=0,4 trên vùng disagreement). SE superpopulation 0,0988 so SD thực nghiệm 0,1010. Đây là số đo cho đúng thứ G03 cảnh báo: q=1 làm sampling variance bằng 0 nhưng không làm causal-evaluation uncertainty bằng 0.
2. **Allocator triển khai tái tạo chính xác quyết định đã khóa** dưới convention đã công bố, và chênh đúng 1 đơn vị dưới convention `floor`. Điều này khóa được một câu hỏi vốn để ngỏ: khác biệt ceil/floor là thật, nhỏ, và đã được định vị.

Không có dòng nào của Orange đổi trạng thái. Không có coverage gate nào được coi là đạt.

## 7. Việc tiếp theo, không đổi thứ tự

1. **Coverage gate** — mở `inference_smoke` sang đủ 8 canonical scenario, ≥1.000 replication mỗi cái, cộng full selection pipeline. Phần fixed-policy rẻ (4 s/1.000 world); phần selection mới là chi phí thật.
2. **G06/V08** — estimand và CI cho batch policy dưới hard cap. Cho tới khi đạt, không cấp confirmatory status ở cap 20%.
3. **V4-04 / E24** — factorial 2×2×2, cần profiling một cell trước khi mở 8 cell × 20 world.
4. **V4-06 / E21** — support gate và hybrid fallback; trên Orange phải là **giới hạn population**, không phải reweighting (ESS 3,9).
5. **Hillstrom adapter** — sau khi kiểm nguồn/license và freeze split; cần cho multi-arm và reward thật.
6. **Relational mock generator** — E19 mới chạy trên tiny fixture viết tay.

A10, A12, A14–A24 đi kèm các mục trên, không tách thành đợt riêng.

## 8. Kiểm tra ở snapshot này

- `python -m ruff check .`: pass.
- `python -m pytest`: **244 passed** (134 cũ + 110 mới), khoảng 16 s.
- `python -m telco_churn.research_runner --profile smoke`: COMPLETE, 5 stage, run directory có completion marker.
- `python -m telco_churn.challenge_suite`: 21/21 critical, 24 case, gate PASS.
- `python -m telco_churn.evidence`: release tier `ENGINEERING_FOUNDATION`, 0 failing gate, 0 artifact cũ hơn producer.
- Console: 13 test API, trong đó có test tái tạo locked decision.
- Deployment: 14 test cho probe, snapshot content-address và chính smoke runner.
- Docker Compose: **đã xác minh** — `docker compose up` ba container healthy, `python -m telco_churn.deployment_smoke` 12/12 pass.
