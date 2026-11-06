# Kế hoạch tổng thể: nghiên cứu, thử nghiệm và phát triển Retention Decision Lab

Rà soát bắt đầu 20/09/2026, hoàn thiện cập nhật ngày 21/09/2026. Phiên bản kế hoạch: **V4.1 / DRAFT_FOR_REVIEW**.

**Lượt này chỉ hoàn thiện tài liệu. Không sửa source/config thực thi, không chạy lại tests, không train models, không tạo kết quả thí nghiệm mới.** Các kết quả hiện có bên dưới được đọc từ workspace, không phải do lượt lập kế hoạch này chạy ra.

## 0. Tài liệu nào là căn cứ thực hiện?

Đây là entry point và bản chốt phạm vi. Không cần đọc các phiên bản lịch sử theo thứ tự thời gian để biết phải làm gì tiếp.

| Tài liệu | Vai trò |
|---|---|
| **Tài liệu này** | Trạng thái hiện tại, quyết định thiết kế, phần việc còn lại, dependencies, nghiệm thu, nguồn lực, release gates |
| [Runbook R00–R09](EXPERIMENT_RUNBOOK_V4.md) | Danh sách model, hyperparameter grids, split/seed, số lượt fit và lịch chạy; bổ sung V4.1 nằm cuối runbook |
| [Thiết kế E19–E28](EXPERIMENT_DESIGN_V4.md) | Giả thuyết, cách so sánh, failure cases và diễn giải từng nghiên cứu |
| [Thiết kế pipeline V3](EXPERIMENT_DESIGN_V3.md) | Các phương pháp/metrics theo N00–N10; extensions chưa chọn không mặc nhiên trở thành core |
| [Thiết kế hệ thống V3](SYSTEM_DESIGN_V3.md) | Contracts, module boundaries, campaign lifecycle và kiến trúc dự kiến |
| [Trạng thái implementation](V4_IMPLEMENTATION_STATUS.md), [claim ledger](../CLAIM_LEDGER_V4.md) | Snapshot công việc/bằng chứng đã có; không đồng nghĩa mọi gate của bản này đã đạt |
| [Review gốc](REVIEW_RESEARCH_V3.md) | Findings lịch sử và căn cứ thay đổi; lỗi đã sửa không bị coi là vẫn tồn tại chỉ vì còn trong review |

Khi chi tiết mâu thuẫn, dùng **quyết định V4.1 ở đây và phần bổ sung V4.1 trong runbook**. Không sửa kết quả/manifest cũ để làm chúng khớp protocol mới. V4.1 là thiết kế đang chờ freeze, không phải một experiment đã preregistered hay completed.

## 1. Trạng thái hiện tại và phần thiếu thực sự

### 1.1 Đã thấy trong workspace

| Thành phần | Bằng chứng đã đọc | Cách ghi trạng thái đúng |
|---|---|---|
| Problem/action/time-zero contracts | `problem_contract.py`, `configs/problem_contracts.toml` | Có implementation; payment-support vẫn là use case giả định, chưa partner-confirmed |
| Label adjudication, economics, integrity gates | `outcome_adjudication.py`, `economics.py`, `integrity_gates.py` | Có primitives/fixtures; chưa đồng nghĩa relational data pipeline hoàn chỉnh |
| Paired DR/IPW và sampling contrast | `policy_comparison.py` | Có estimator primitives; cần bổ sung statistical/domain gates bên dưới |
| CatBoost missing-value preparation | `uplift.py` có `numeric_fill_` học tại fit | Lỗi batch-median cũ đã được sửa trong code đang đọc; lượt này không re-test |
| Mutation suite | [report lưu sẵn](../../reports/v4/CHALLENGE_SUITE_REPORT.md) | 18 declared cases, 15/15 critical detected, 0 false blocks khi bản kế hoạch này được viết; vòng triển khai 21/09 nâng lên 24 cases / 21 critical ([VERIFICATION_V4_1.md](VERIFICATION_V4_1.md)); không bảo đảm bắt mọi lỗi |
| Research runner | `research_runner.py`, [run report](../../reports/v4/run_report.json) | Profile smoke có report COMPLETE; `screen`/`confirm` hiện chủ động từ chối chạy |
| Fixed-policy inference smoke | [correct nuisance](../../reports/v4/inference_smoke.json), [misspecified nuisance](../../reports/v4/inference_smoke_misspecified.json) | Mỗi report 1.000 worlds, cùng một mechanism; paired coverage 95,7%/95,6%; vẫn `SMOKE_ONLY` |
| Orange assignment audit | [audit report](../../reports/v4/ORANGE_ASSIGNMENT_AUDIT.md) | Có diagnostic mới; Orange vẫn conditional, không phục hồi causal identification bằng classifier |

Không dùng “1.000 worlds” để kết luận đã chạy R01: smoke hiện tại là reward Gaussian, X uniform, effect và propensity có cơ chế riêng; R01 mới kiểm binary rare events, null, clusters và các tình huống khác. Không chuyển report cũ sang run ID mới.

Các phát biểu trong status/claim ledger như “unbiased” cần đọc ở mức **bias quan sát tương thích 0 trong scenario đã chạy**, không phải chứng minh từ Monte Carlo. AUC permutation gần 0,5 không chứng minh toàn pipeline không leakage; ESS xấu ở một fitted propensity không loại bỏ mọi estimator propensity có thể có. Kế hoạch giữ Orange conditional vì identification chưa giải quyết, không vì một thuật toán duy nhất đã thất bại.

### 1.2 Khoảng trống phải xử lý trước screening mới

| ID | Quan sát từ code hiện tại, chưa chạy tái hiện trong lượt này | Công việc cần thiết |
|---|---|---|
| G01 | `dr_action_scores` clip e tại 0,001 sau khi kiểm row sums | Known-design e không được âm thầm thay. Tách primary unmodified estimator, explicit support rejection và sensitivity-clipped estimator; log counts/weights |
| G02 | Nuisance/action gathering chủ yếu dùng positional arrays | Contract phải join bằng row key, kiểm duplicate/action-label collision và reject shuffled/mismatched indices; không chỉ so lengths |
| G03 | `enriched_sampling_contrast` tính Poisson recruitment variance có hệ số `(1−q)` | Phân biệt variance conditional on fixed scores với uncertainty do treatment/outcome. q=1 làm sampling variance=0 nhưng thường không làm causal-evaluation uncertainty=0 |
| G04 | `run_stage` kiểm artifact tồn tại bằng `.exists()` | Stale artifact từ run trước không được dùng để xác nhận run mới; kiểm run_id/hash/schema/producer/config và atomic completion marker |
| G05 | `subprocess.run` có timeout nhưng không thấy nhánh ghi nhận `TimeoutExpired` trong `run_stage` | Timeout/interruption/launch error vẫn phải xuất failed/incomplete manifest, không mất toàn bộ lịch sử run |
| G06 | Paired scalar-score inference đã có; cap 20% sử dụng batch top-K | Chưa đủ để mặc định CI IID trên frozen scores đúng cho deployment batch policy; cần V08 và xác định estimand |
| G07 | Payment contract endpoint là cancellation nhưng `reward_unit` là tiền | Tách outcome/effect/reward endpoints và units; không trộn cancellation ITT với currency reward trong cùng field |
| G08 | `screen`/`confirm` chưa triển khai; Hillstrom adapter chưa có trong inventory | Xây phần còn thiếu từ primitives hiện tại; không chạy script cũ rồi gắn nhãn V4.1 |

Đây là backlog kiểm chứng/sửa ở phase implementation sau, không phải danh sách lỗi đã được sửa trong lượt này. Không yêu cầu viết lại các modules đã có.

## 2. Quyết định phạm vi đã chọn cho bản kế hoạch

| Decision | Default được đề xuất | Khi nào cần thay |
|---|---|---|
| Bài toán nghiên cứu chính | Khi nào representation, effect estimator và allocation tạo thêm policy value dưới sparse outcomes/constraints? | Chỉ revision trước main results nếu data/resources không phù hợp |
| Real-data primary | Hillstrom Mens versus No email, conversion hai tuần, eligible source population | Không có quyền truy cập/sử dụng: dừng real track, chỉ làm validity/mock; không tự dùng mirror không rõ nguồn |
| Baseline chính | M01 control-outcome Logistic ranking; không gọi là BAU khách hàng thật | Partner track có actual BAU thì protocol mới |
| Decision constraint | Tối đa floor(0,2N) contacts theo evaluation/deployment batch | Capacity thật khi partner xác nhận; không chọn lại theo confirmation curve |
| Practical benchmark margin | 1 extra conversion/1.000 eligible | Chỉ thay trước development outcome analysis và ghi rationale; chưa là business threshold |
| Models core | M01–M08, tối đa 3 representatives vào tuning | Extensions theo trigger, không mở full model zoo |
| Data split | 80% development / 20% untouched confirmation; nested 3×3 trong development | Ingestion thấy insufficient arm/event support thì khóa lại protocol trước model comparison |
| Hướng nghiên cứu phụ | Disagreement-aware sampling; chỉ mở khi G03/R08 evaluator đạt | Không đủ thời gian: giữ như thiết kế, không claim saving |
| Use case sản phẩm mô phỏng | Payment-support với action catalogue hiện có | Partner discovery có bằng chứng chọn use case khác |
| Serving | Batch research packet/replay; không gửi campaign thật | Pilot cần owner/budget/design/consent và quyền riêng |
| Tooling | Python package hiện có, versioned artifacts; lock environment | Không cần dựng thêm distributed platform ở core |

**Không nằm trong core 12 tuần:** production live campaign, RL, nhiều deep architectures, validated long-term surrogate, business ROI thật, survival đa trạng thái toàn diện hoặc migration toàn package. Có thiết kế extension không đồng nghĩa phải implement tất cả.

## 3. Data acquisition và contracts triển khai

### 3.1 Checklist một dataset trước khi cho model đọc

1. Ghi source URL, source description version, retrieval timestamp, raw SHA-256, điều kiện sử dụng và redistributability. Không có explicit permission chia sẻ raw thì publish loader/manifests, không tự publish raw.
2. Raw giữ read-only; parsing tạo immutable derived version. Chuyển null/type/category có report counts trước/sau.
3. Xác định entity key, assignment unit, arm semantics, feature availability, outcome horizon. Source-row key không biến thành real customer identity.
4. Kiểm row counts, duplicate signatures, malformed categories, impossible numeric values, arm distribution, missing outcomes. Exact duplicate covariates không tự là duplicate customer và không tự xóa.
5. Freeze feature allowlist, label denylist theo lineage; adverse-event score versus beneficial reward có sign conversion rõ.
6. Lập split manifest trước EDA có label; lưu ai/công cụ nào đã đọc label, mục đích và role. File permissions/access logs chỉ giảm nguy cơ leakage, không chứng minh không ai từng xem public labels.
7. Ingestion có thể kiểm label integrity/counts; analyst không dùng confirmation effect/metrics để sửa model. Label access vì QC ghi riêng với model selection.
8. Dataset card nêu population được áp dụng, dữ liệu không có, giả định assignment và phạm vi không suy rộng.

### 3.2 Artifact schemas tối thiểu

Tên là contract thiết kế, chưa phải file đã tạo:

| Artifact | Khóa | Required fields / invariants |
|---|---|---|
| `dataset_manifest` | dataset_id + version | Raw/derived hash, source, parser, license note, target/action mapping, entity-key quality |
| `split_manifest` | revision + row_id + fit_context | role, outer/inner fold, cluster, train hash; row không train và evaluate trong cùng fit |
| `feature_manifest` | feature_view + column | source columns, transformations, fit-only role, event/availability rules, dtype |
| `prediction_frame` | fit_id + row_id + action_id | predicted target, unit/horizon, model/preprocessor/calibrator hash; finite values |
| `policy_frame` | policy_id + batch_id + row_id | eligible, candidate/chosen action, reason, score kind, cost/support/constraints versions |
| `evaluation_frame` | eval_id + row_id | observed A/R, source e, optional q, nuisance values, paired contribution, cluster key |
| `run_manifest` | run_id | parent, protocol revision, configs, all input hashes, dependency lock, stage status, seeds, compute |
| `comparison_result` | comparison_id + estimand_id | point, CI/method, denominator, units, evidence tier, budget, validity state, decision |

Join theo keys và explicit action order. Mixed labels `1` và `"1"`, duplicate action columns, same-length khác row ordering, NaN/Inf hoặc unknown action phải fail. Không dùng positional “cùng N” như bằng chứng cùng cohort.

### 3.3 Units và horizons

Mỗi endpoint có `target_id`, `target_kind`, `orientation`, `unit`, `window_start`, `window_end`, `maturity_rule`. Với payment mock: `cancellation90` là binary adverse outcome; `net_contribution90` là currency reward riêng; ingest lag 30 ngày nghĩa complete readout sớm nhất ở ngày 120 cho cohort mới. Không gọi metric tiền là cancellation ITT.

Visit/conversion/spend của Hillstrom là outcomes, không đưa vào features. Phương thức thanh toán sau contact, delivery, offer acceptance và hậu nghiệm complaint không được dùng để chọn contact đầu tiên. Extension next-stage decision cần contract mới.

## 4. Statistical analysis plan phải freeze

### 4.1 Ba estimands khác nhau

1. **Individual rule trên future population:** policy được học/khóa từ training, mỗi X quyết định độc lập; paired DR mean và inference theo sampling/randomization assumptions.
2. **Batch policy hard cap:** quyết định một người phụ thuộc scores của cả batch; primary của real benchmark thuộc loại này. Target là expected average reward của batch policy ở declared batch size/distribution, không lén thay bằng individual fixed threshold.
3. **Finite frame với recruitment:** N eligible đã biết, q là inclusion, e là treatment; uncertainty có thể conditional frame nhưng vẫn gồm assignment/outcome noise theo estimand. Không nhầm HT recruitment-only variance với full causal uncertainty.

Một result ghi đúng một primary estimand. Conditional fixed-frame readout có thể secondary; không dùng nó để suy ra future-batch guarantee.

### 4.2 Primary statistic và CI

Với reward cao là tốt: `Γ_i(a)=m_a(X_i)+1(A_i=a)/e_i(a)×[R_i−m_a(X_i)]`; `Z_i=Γ_i(π1)−Γ_i(π0)`. Delta = mean Z, nhân 1.000 cho report. Known design probabilities giữ nguyên. Ranking score không tự biến thành calibrated effect.

DR là phương pháp nền, không đóng góp mới của dự án; correctness phụ thuộc data/design và nuisance construction. [Dudík, Langford & Li](https://arxiv.org/abs/1103.4601)

Candidate CI cho batch primary: account bootstrap, scoring functions/nuisances giữ frozen, mỗi resample **allocate lại cả hai policies** với cùng capacity rule và deterministic tie semantics. Final readout dự kiến 2.000 resamples. Cluster case resample clusters; fixed-size assignment design có thể cần design-specific method. Phương pháp chỉ được dùng khi V08 validation đúng design/target đạt; bootstrap không mặc nhiên đúng chỉ vì đã implement.

Bootstrap occurrences của cùng original row là draws hợp lệ, không bị dedup như duplicate ingest; dùng occurrence key giữ paired sample và tie handling thống nhất. Kiểm near-threshold ties, all-equal scores, negative effects và N nhỏ. Không dùng test outcomes để quyết định thứ tự tie hoặc lựa bootstrap method.

Nếu CI cho batch policy chưa validate, không cấp confirmatory claim ở cap 20%. Có thể thực hiện fixed-threshold study với protocol/estimand mới được khóa **trước** confirmation; không thay tên metric hậu nghiệm để vượt gate.

### 4.3 Recruitment variance cần bổ sung

Gọi Z là randomized action-score contrast, S là recruitment indicator với probability q. Ngay dưới independent recruitment, conditional X:

`Var(SZ/q) = Var(Z)/q + (1−q)/q × [E(Z)]²`.

Nếu chỉ tính variance khi Z là số đã cố định, sẽ bỏ uncertainty của action/outcome. Test q=1 phải còn uncertainty khi Z noisy; chỉ sampling contribution hết. Cũng cần test outcome noise→0 và assignment support→1 ở cases có thể xác định.

Hai estimator targets được thử riêng: augmented two-stage DR/influence approach cho superpopulation và design-aware finite-frame estimator/bounds. Kiểm bias/coverage bằng independent re-draws của recruitment, treatment và outcomes; không chỉ resample S trên một Z cố định. Công thức trên là phân tích cho thiết kế này, không claim implementation hiện tại đã thực hiện đầy đủ.

### 4.4 Decision thresholds và multiple comparisons

Primary dùng 95% **two-sided** CI và promote khi lower bound > margin. Vì vậy boundary rejection probability danh nghĩa là **2,5% một phía**, không phải 5%. V4.1 đề xuất gate upper Wilson bound false-promotion ≤5% tại actual boundary-null scenarios với ≥1.000 replications/scenario; thay tolerance 7% của bản thiết kế trước cho protocol mới. Coverage nominal 95%: engineering gate lower Wilson bound ≥92%, đồng thời báo width, power, bias, MCSE và mọi failed cases. Các tolerances là thiết kế benchmark, không lý thuyết bảo đảm.

Null phải phù hợp claim: Δ=0 cho claim superiority over zero; Δ=δ_min cho practical superiority. V03 có ATE=0 nhưng policy effect dương không phải promotion null. Chấm riêng actual null, practical-boundary và alternatives.

Một primary comparison trên confirmation. Family/model/budget selection dùng development. Secondary comparisons đã khóa dùng Holm nếu đưa nhiều hypothesis claims; exploratory plots ghi exploratory. Muốn phát biểu “mọi scenario đều pass đồng thời” dùng adjusted binomial bounds; pointwise bounds không hỗ trợ câu đó.

Unpaired SE, naïve IID dưới clustering, wrong propensity và leaked evaluation là negative controls; **không yêu cầu chúng đạt gate rồi loại case vì fail**. Chúng phải bị detector hoặc known-truth tests phát hiện.

## 5. Chốt tính khả thi thống kê trước khi tiêu confirmation

Sau R02, ước lượng variance của paired contribution từ development OOF hoặc Monte Carlo phù hợp. Với IID fixed-rule approximation, additional effect cần vượt margin để có khoảng 80% power gần `2,80×s_Z/sqrt(n_confirm)`; đây là planning approximation, không exact power cho batch/cluster/rare events. Những trường hợp đó dùng simulation của đúng evaluator/policy rule.

Power report cần: n_confirm thực, counts theo arm, disagreement share, feasible effect range, practical margin, projected CI width và sensitivity theo variance inflation. Không đọc confirmation treatment effects để chọn n/target.

Nếu 20% holdout quá nhỏ cho margin 1/1.000: vẫn có thể báo honest CI và inconclusive; hoặc trước mở holdout quyết định cần fresh data/new trial. Không hạ margin sau khi thấy kết quả; không biến “không significant” thành equivalence.

Power cho tiền cần reward variance/tails; power cho policy trial khác power trong subgroup được contact. Repeat customer-months không tự tăng independent N. Nếu không đủ independent clusters hoặc tail observations thì report unsupported inference thay vì automatic normal CI.

## 6. Phát triển từng module: đầu vào, phần việc và acceptance

| WP | Input / dependencies | Việc còn phải làm | Deliverable và gate |
|---|---|---|---|
| WP01 — Baseline freeze | Current source + reports | Snapshot hashes, link evidence, environment inventory; không regenerate history | Existing claims có trạng thái/source; source changes hiện có được bảo toàn |
| WP02 — Contract completion | WP01 | Units/targets G07, Hillstrom contract, declared data roles/access | Invalid units/horizon/action map fail; public benchmark và partner mock không dùng chung giả định |
| WP03 — Data adapter | WP02 + source access | Fetch/parse/manifest/split/quality; no raw redistribution mặc định | Rebuild từ same raw hash cùng rows/schema/split; post-treatment features bị chặn |
| WP04 — Estimator hardening | WP02 | G01/G02, source e, finite values, keys/action labels | Exact fixtures; clip explicit; same-length shuffled frames không silently accepted |
| WP05 — Inference domains | WP04 | G03/G06, batch and recruitment inference, cluster design | V07/V08/V09 và q=1 law-of-variance tests; unsupported designs refuse promotion |
| WP06 — Runner/artifacts | WP01/WP02 | G04/G05, immutable run dirs, resolved config, lock/resources/resume | Stale file/timeout/interruption cannot COMPLETE; publish marker sau schema/hash validation |
| WP07 — Coverage job | WP04–06 | Compile R01/R06 manifests, separate smoke/screen worlds | Coverage/bias/width/power per scenario; no scope overclaim |
| WP08 — Model adapters | WP03/WP04 | M01–M08 with common features/sign; add DR-Ridge; nested nuisance | All model outputs same target/action units; S/T/DR no evaluation leakage |
| WP09 — Screening/tuning | WP07/WP08 | R02/R03, bounded trials, honest outer predictions | All attempts/failures logged; shortlist deterministic and frozen |
| WP10 — Component study | WP09 | R04, at least one triggered component probe | Main/interaction effects + explanation of investment next step, không chỉ leaderboard |
| WP11 — Stability/selection | WP09/WP10 | R05 nếu budget; mandatory bounded R06 | Seed variation khác population CI; full-selection limitations rõ |
| WP12 — Relational generator | WP02/WP06 | Invoice/assignment/delivery/outcome/cost timelines + as-of snapshots | Hidden truth inaccessible; labels/reward/cost reconciled; policy changes trajectories |
| WP13 — Workflow demo | WP12 + valid bundle | Feasible batch packet, immutable assignment, retry/backfill | Tiny full path pass; chưa live sends |
| WP14 — Final evaluation | WP09–11 + WP05 gates | R09, frozen final candidate/baseline/evaluator | One primary contrast, non-overwritten artifacts, negative/inconclusive outcomes retained |
| WP15 — Replication | WP14 hoặc preregistered parallel protocol | One external-domain run with same method recipe | Domain-level limits; no pooled “business gain”; absence remains unmet release item |
| WP16 — Handoff | WP13–15 hoặc scoped interim | Evidence report, limitations, run cost, reproduction instructions | New reviewer reconstructs claims from artifacts; package tier đúng evidence |

WP12/WP13 có thể phát triển bên cạnh training về mặt dependency khi nguồn lực cho phép, nhưng kế hoạch nguồn lực mặc định **một người**; không tính cùng giờ công hai lần. Không có yêu cầu dùng sub-agents trong kế hoạch này.

## 7. Implementation specification theo node

| Node | Contract cần khóa | Thử nghiệm bắt buộc / điều kiện | Nghiệm thu chính |
|---|---|---|---|
| N00 problem | Population/action/BAU/target units/horizon | E19; discovery khi có partner | Một decision không có 2 estimands mâu thuẫn |
| N01 source/design | Raw hash, design e, assignment vs delivery, q | Orange audit giữ conditional; V04/V09 | Propensity provenance explicit; no hidden clipping |
| N02 label/snapshot | event_at, available_at, maturity/corrections | E19/Q03/Q06/Q07 | Không dùng future label/feature; unknown khác zero |
| N03 preprocessing | Fit membership, column semantics/order | Base vs 4 interactions; missingness probe nếu trigger | Train-only transforms; batch invariance; RAM estimate |
| N04 outcome models | Probabilities/target per arm | M01/M02 and common nuisances; calibration probe | Arm Brier/log-loss, natural prevalence, no leaked calibrator |
| N05 effect models | Reward difference orientation; OOF pseudo-outcomes | M03–M08, R03, shrinkage/R/X extensions nếu trigger | True-value/real OPE criteria, không chỉ model fit loss |
| N06 evaluation | Individual/batch/frame estimand + CI domain | R01, V08/V09, R06 | Scope-valid CI; paired units; proper denominators |
| N07 allocation | One action/unit, hard cap/costs/cooldown | R04 C factor + tiny exact solver | Zero violations; identical scores deterministic; no forced negative value |
| N08 execution | Approved decision vs randomized assignment | Replay/ITT/idempotent retry | Immutable arm even delivery fails; no real customer contact |
| N09 adaptation | Training as-of / label lag / method trigger | R07 extension + minimal temporal fixture core | Refits không dùng immature labels; distinct drift mechanisms |
| N10 serving/audit | Bundle/schema/version/target | Batch packet; API compatibility if changed later | Traceable reason/evidence state; no false `risk_30d` validation |

Các phương pháp RATE/Qini chỉ supporting heterogeneity/ranking metrics; hai model trên cùng cohort cần paired comparisons, không lấy hai independent error bars để kết luận khác biệt. [GRF RATE documentation](https://grf-labs.github.io/grf/reference/rank_average_treatment_effect.html)

## 8. Lịch 12 tuần còn lại, có đầu ra theo tuần

Lịch bắt đầu **sau khi được yêu cầu triển khai**; không là deadline ngày lịch đã cam kết. Không làm lại mười phiên đã có code. Một người, 290–384 giờ cho bảng dưới + 20 giờ contingency = **310–404 giờ** dự kiến còn lại; thay estimate 300–400h cũ, không cộng hai estimate. Lịch có thể phải kéo dài nếu compute/validity/data access thất bại.

| Tuần | Giờ | Work packages và đợt chạy | Đầu ra bắt buộc cuối tuần |
|---|---:|---|---|
| 1 | 18–24 | WP01/02; verify existing primitives, G01–G08 review | Current-state map; protocol candidate; endpoint/unit decisions |
| 2 | 28–36 | WP03/04/06 | Dataset+split manifests, immutable runner, new critical fixtures |
| 3 | 28–36 | WP05/07; R00/R01 smoke rồi gate jobs | Per-design inference validation; blocked cases còn nguyên trạng thái |
| 4 | 22–30 | WP08; profile one fit, R02 | Eight-model screening, event counts, first feasibility/power report |
| 5 | 28–36 | WP09; R03 nested search | Bounded tuning report, no confirmation access |
| 6 | 28–36 | WP10; R04 real + mock factorial | Component/interaction report, selected improvement rationale |
| 7 | 24–32 | WP11; R05/R06 bounded | Data-efficiency and selection-stress report; scope of guarantees |
| 8 | 24–32 | WP12; relational generator | Reproducible event tables, audit truth and as-of snapshots |
| 9 | 24–32 | WP13; R07 minimal + UAT fixtures | Batch packet/retry/label maturity demo, evidence-state transitions |
| 10 | 24–32 | R08 nếu G03 đạt; WP15 dataset prep | Cost/precision study hoặc explicit deferral; replication protocol |
| 11 | 24–32 | WP14 R09; external confirmation/replication nếu feasible | Primary final comparison, all failures/negative findings |
| 12 | 18–26 | WP16 | Research report, claim ledger update, reproduction/handoff checklist |

Nếu tuần 3 chưa đạt G03 nhưng individual/batch evaluation đã đạt: **đóng R08**, vẫn tiến hành model studies. Nếu batch CI chưa đạt: có thể screen development nhưng R09 chưa được cấp confirmatory status. Nếu Hillstrom chưa có: tiếp tục fixtures/mock, không gọi đó là real-data study.

Không chờ lịch tuần để bỏ qua gate; milestone chưa pass thì dependent work phải đổi trạng thái. Nếu công việc cuối tuần không tạo artifact/câu trả lời cụ thể, chưa được tính hoàn tất vì đã đủ giờ.

## 9. Budget tính toán và quy tắc không vượt phạm vi

Runbook phân bổ 118,5 CPU-hours cho R00–R09; đây là **trần kế hoạch**, chưa chứng minh matrices chạy đủ. V4.1 thêm V07–V09 và các boundary controls nên giữ 25% reserve, làm tròn **150 CPU-hours cho campaign đầu**. Nếu profiling chỉ ra vượt 150 thì chọn scope nhỏ hơn trước xem kết quả hoặc xin mở rộng nguồn lực; không tự thuê GPU/cloud.

R10 external-domain replication có quota riêng đề xuất 20 CPU-hours, chưa nằm trong 150. Nếu không đủ nguồn lực thì release thiếu external replication phải mang nhãn interim. CPU-time sum/process, wall-time, peak RSS, model-internal fits và human effort báo riêng.

Default một heavy job, tối đa 4 threads; RAM budget = min(8 GiB, 50% RAM máy) sau inventory. Dense OHE có projected bytes `N×P×dtype_size` cộng copies; không chỉ nhìn size raw CSV. HGB trong environment hiện pin scikit-learn 1.7.x cần adapter đúng input/parameter contract; chọn dense feature matrix explicit, không vô tình biến OHE thành ordinal giữa models. [API 1.7](https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)

Run manifest compile phải đếm thực: T learner = 2 arm fits; DR với 3 nuisance folds thường = 6 arm fits + 1 final-stage fit, chưa kể evaluator/refits. Cache có thể giảm compute khi train-membership/config identical; không dùng số 216 top-level fits như tổng mọi model training.

Thứ tự cắt khi budget không đủ: extra seeds → optional curves → optional model families → large temporal/R08 → replication deferred. Không cắt provenance, held-out roles, negative controls hoặc uncertainty rồi giữ release claim cũ.

## 10. Quality gates và failure handling cụ thể

| Gate | Chấm ở đâu | Pass / hành động fail |
|---|---|---|
| QG0 reproducibility | WP01/06 | Dependency lock + exact source/config/data manifests; fail nếu không biết run dùng gì |
| QG1 data/target | WP02/03 | Required keys/sign/units/arm support hợp lệ; quarantined reasons; không silent drops |
| QG2 numeric identities | R00 | Integer/keys exact; float tiny fixtures atol 1e−10, rtol 1e−8; library parity tolerance khóa riêng |
| QG3 mutations | R00 + new G-cases | 100% declared critical caught, clean critical fixtures không false block; chưa là unknown-bug guarantee |
| QG4 statistical validity | R01 domains + boundary scenarios | Theo §4.4, đủ replications và width/power; unsupported domains không promote |
| QG5 honest selection | R02–R06 | Same folds/resources, inner-only tuning, all attempts log, selection stress scope rõ |
| QG6 final evidence | R09 | Frozen manifest, one primary comparison, correct CI/domain, no holdout retuning |
| QG7 operational replay | WP13 | Zero declared constraint/idempotency/ledger violations; reward mature; retry reproducible |
| QG8 reporting | WP16 | Mọi headline claim → artifact/estimand/CI/limitation; no fabricated partner/ROI |

Timeout/OOM không cho model score 0 hoặc −∞. Trạng thái `FIT_FAILED`; paired comparison chỉ hợp lệ trên common completed runs và báo missing pattern, không xóa khó khăn để tăng average. Không tự ưu tiên model nhanh khi model khác bị resource settings không công bằng; tài nguyên là explicit study constraint.

Runtime failures có thể retry cùng immutable config với bounded attempts, tối đa 1 retry cho lỗi hạ tầng tạm thời; deterministic data/model failure không retry vô hạn. Đổi threads/dtype/library/hyperparameter tạo resolved-config revision mới. Stage crash phải giữ stderr/status và phần artifact chưa hoàn tất ở quarantine.

Existing artifacts phải được nhận diện bằng run_id + hashes chứ không existence. Resume không ghi đè successful stage. Cancellation của user → INCOMPLETE; không xuất report thành completed study.

## 11. Relational mock và demo có tình huống sử dụng rõ

### 11.1 Minimal operational world

Default 1.000 accounts cho deterministic acceptance; 6.000 accounts/24 tháng cho temporal screening chỉ khi profiling cho phép. Accounts có subscription state, invoice failure/due/grace interval, permission/cooldown, action catalogue, campaign assignment, delivery attempts, actual cost postings và outcome observations. Không cần invent sensitive demographics để demo.

Một account có nhiều episodes cần `episode_id`; cooldown/global capacity theo account, không né constraint bằng tạo episode mới. Time stored UTC, business calendar/timezone explicit; không so local naive timestamps với UTC ngầm.

World generation tách: account attributes → pre-treatment event processes → eligibility snapshot → logged assignment → delivery/queue → outcome/cashflow → ingestion delays/corrections. Oracle nằm separate audit namespace, learner cannot request through adapter. Bốn truth conditions bắt buộc: action không effect; action có effect nhưng lỗ cost; outcome risk tốt nhưng effect ranking sai; offline good nhưng delivery delay làm mất gain.

### 11.2 Năm acceptance stories

| Story | Hành vi mong đợi | Bằng chứng demo |
|---|---|---|
| Ticket phát sinh trước t0 nhưng kho nhận sau t0 | Snapshot t0 không dùng ticket; snapshot sau đó có thể dùng | Feature lineage/as-of diff |
| Assignment contact nhưng không delivery | Giữ assigned arm và account trong ITT; cost theo actual attempt | Assignment→delivery→outcome reconciliation |
| Export retry hoặc worker restart | Cùng assignment_id; không tạo lần contact mới | Immutable packet hash và unique constraints |
| Offer cost đổi khiến expected value âm | New cost version; recompute decision/packet, không sửa artifact cũ | Action diff và explainable cost/value readout |
| Outcome chưa mature hoặc có conflict | Không thành non-churn; report WAITING/UNRESOLVED | Label-state counts và evidence gate |

Hàng đợi full discrete-event, fatigue dài hạn và cluster-randomized pilot là extensions. Core demo chứng minh handling/constraints; không claim biết hành vi call-center thật.

## 12. External replication R10

R09 chỉ kiểm trên một real-data domain; để đạt research release đầy đủ cần một domain độc lập. Default candidate là Criteo nếu nguồn/license/compute được xác nhận; không tự tải toàn bộ dataset trong phase planning này. Partner randomized data có thể thay bằng protocol riêng.

R10 không frozen-transfer các weights Hillstrom qua schema khác. Transfer **method recipe và selection protocol**: M01 + final method + một simple causal baseline; 8 configs mỗi trainable recipe nếu cần, same declared search allowance; 80/20 split mới, một primary policy contrast cùng capacity convention. Target/action semantics theo dataset mới, không ép churn/email/ad exposure thành cùng outcome.

Để giới hạn scale, initial proposal max 200.000 uniformly hash-selected rows trước label analysis, không downsample controls hoặc chỉ lấy converters rồi giữ prevalence cũ. Nếu outcome quá hiếm thì report power/support; chọn size lớn hơn chỉ theo predeclared event/precision rule trước confirmation. Exact inclusion probability/version phải log.

Replication pass không bắt buộc “mọi model đều thắng”. Câu hỏi là cơ chế/điều kiện của claim chính có lặp lại hay khác ở đâu. Không average conversion gains giữa hai domains để thành telco business effect. Không đạt access/resources → `EXTERNAL_REPLICATION_PENDING`, không đổi tên Women/Men arms thành hai domains.

## 13. Bằng chứng thực tế với partner — cổng riêng

Trước pilot cần xác nhận: action owner và actual BAU; eligible counts/wave; churn/cancellation definition; endpoint delays; assignment logistics; delivered-cost ledger; slots/agent minutes; contamination/cooldown; stop authority và business practical margin. Không coi default 500 slots/week và cost 6,5 trong mock contract là dữ kiện khách hàng.

Pilot thiết kế tách hai câu hỏi: action có hiệu quả so BAU không; frozen targeting policy có cải thiện so incumbent dưới cùng envelope không. Chọn randomization unit theo interference/household/capacity thật, không mặc định account. Outcome cohort theo assignment, không theo received offer.

Primary business endpoint margin90 hoặc margin180 chỉ chọn khi ledger/owner xác nhận. Với horizon90 + lag30, một cohort mới cần ít nhất 120 ngày tới maturity; margin180 còn lâu hơn. Lịch code 12 tuần không thể thay thời gian follow-up. Shadow workflow có thể hoàn tất trước business validation.

Không gửi email, gọi API campaign, cấp discount hay đăng ký dịch vụ/cloud từ việc approve kế hoạch nghiên cứu. Các hành động live cần yêu cầu và quyền tương ứng sau này.

## 14. Risk register và quyết định khi gặp trở ngại

| Risk | Tín hiệu / checkpoint | Quyết định mặc định |
|---|---|---|
| Dataset unavailable/usage unclear | WP03 source check | Dừng real track đó; làm mock/validity, không tìm mirror không rõ quyền |
| Public holdout đã xem labels | Access ledger hoặc người thực hiện xác nhận | Relabel exploratory; new untouched data cho confirmation |
| Few events/low power | Pre-R09 power report | Báo CI/inconclusive hoặc thu fresh evidence; không hạ margin hậu nghiệm |
| R01 gate fail | Undercoverage/false-promotion | Dừng dependent claims; inspect design/estimator, revise và rerun fresh gate worlds |
| Model search mở rộng không kiểm soát | Attempt count vượt declared budget | Runner refuse thêm trial; revision, không che attempted configs |
| Batch/cluster inference unsupported | V08/design validation fail | Chỉ exploratory readout; không promote theo IID SE |
| Extreme estimated e | Weight tails/support diagnostic | Giữ identification caveat; explicit sensitivity, không hidden clipping |
| G03 unresolved | q=1/dual-randomization coverage fail | R08 deferred; không claim cheaper experiment |
| Mock chỉ ưu ái learner nào đó | One-mechanism-only wins | Add unseen mechanism, report limitation; không tune test generator để winner đẹp |
| Partner economics thiếu | Cost attribution/revenue chưa rõ | Conversion/churn/break-even assumptions only; no ROI |
| External replication thiếu | R10 access/compute fail | Interim release, ghi unmet requirement |
| User/codebase tiếp tục thay đổi | Hash/file inventory thay giữa phases | Reconcile current state, preserve unrelated edits; không reset workspace |

## 15. Vai trò, review và change control

Mặc định một người có thể kiêm implementer/research analyst, nhưng thao tác tách theo artifacts: người/phase training không đọc confirmation; final evaluator chỉ load locked policy. Có reviewer độc lập thì họ kiểm manifests/gates trước mở test; không có reviewer thì ghi `self-reviewed`, không giả có external approval.

Research owner quyết định hypothesis/scope; engineering owner giữ runner/data contracts; domain/finance owner xác nhận business margin/cost; operations owner xác nhận action/capacity. Vai trò domain/finance/ops chưa có người thật thì trường owner=`UNASSIGNED`, live pilot bị chặn nhưng public-method study vẫn tiến hành.

Change classification:

- Documentation typo không đổi protocol/claim: editorial revision.
- Model/feature/evaluator/cost/split/tie/seed policy change: scientific revision; existing results không rewrite.
- Fix bug làm thay metrics/actions: invalidate affected results với cause, re-run scope dependency; không xóa artifact cũ.
- Confirmation đã đọc: subsequent selection là exploratory; cần evidence mới cho confirmation tiếp.

## 16. Deliverables và tiêu chuẩn hoàn thành

| Deliverable | Nội dung phải có | Điều kiện chấp nhận |
|---|---|---|
| D01 protocol bundle | Problem/target, data roles, model recipes, metric, inference, budget | Frozen hash trước main run |
| D02 validity report | Exact/mutation/statistical scenarios; failures; MCSE | QG0–QG4 trong domains dùng cho final claim |
| D03 model study | M01–M08, bounded tuning, full attempts, event learning curve nếu chạy | Same conditions, held-out predictions, no seed-CI substitution |
| D04 component study | Factor levels, interactions, one counterexample/limitation | Trả lời node nào tạo gain hoặc chưa đủ phân biệt |
| D05 workflow packet | Cohort/actions/evidence/reasons/ledger/replay | QG7; no actual live actions |
| D06 confirmation report | Primary delta/CI/margin, power limits, secondary separation | One honest primary comparison, hoặc explicit no-candidate/no-confirmation |
| D07 external replication | Independent-domain protocol/results/limits | Nếu thiếu thì release tier không nâng lên replicated |
| D08 handoff | Reproduction steps, environment, costs, artifact index, open risks | Một reviewer đọc được claim từ result mà không cần đoán notebook state |

Release tiers: `ENGINEERING_FOUNDATION` khi primitives/gates cơ bản có; `RESEARCH_INTERIM` khi có một real-domain study + mock validity đúng scope; `RESEARCH_REPLICATED` khi thêm external domain và findings có giới hạn rõ; `BUSINESS_VALIDATED` chỉ khi prospective partner trial mature và economics/guardrails đạt. Model thắng baseline không phải điều kiện duy nhất để research có giá trị, nhưng integrity/traceability là bắt buộc.

Không cố tìm positive result để đủ release: kết quả đáng tin có thể là baseline đủ tốt, personalization thiếu power, một representation làm hại, hoặc một claimed advantage biến mất dưới đúng evaluation. Phải đo độ lớn/uncertainty và giải thích hành động tiếp theo, không dùng “cần thêm dữ liệu” như kết luận chung chung.

## 17. Các điểm còn mở và cách đóng

| Câu hỏi chưa có dữ kiện | Default hiện tại | Mốc phải chốt / evidence cần |
|---|---|---|
| Máy có bao nhiêu RAM/cores và thời gian chạy cho phép? | CPU, 4 threads, quota §9, chưa đo | WP01 inventory/profiling; không tự mua cloud |
| Source Hillstrom còn truy cập/được sử dụng thế nào? | Check source rồi mới adapter | WP03 manifest và usage note |
| Confirmation labels đã từng được xem chưa? | Chưa được khẳng định untouched | Access disclosure trước freeze; nếu đã xem thì đổi evidence tier |
| Batch CI chọn method nào? | Paired reallocation bootstrap là candidate | V08 diagnostics/coverage/domain pass, protocol lock trước R09 |
| Two-stage recruitment CI dùng target nào? | Tách finite frame/superpopulation | WP05 + V09; nếu chưa đạt thì R08 đóng |
| Feature/model nào thắng? | Không giả định trước | R02–R09 results, không chốt bằng tên architecture |
| Practical business margin/cost có thật không? | Chỉ benchmark margin và mock costs | Partner discovery/finance; không chặn methodological study |
| Dùng method nào cho external replication? | Frozen final recipe + M01 + simple causal baseline | R10 protocol trước xem external confirmation |

Những mục này là dependencies có owner/mốc/behavior khi thiếu, không phải lời hứa mơ hồ. Không thể điền một con số khách hàng/hardware/performance chưa đo chỉ để làm tài liệu có vẻ hoàn tất.

## 18. Thứ tự bắt đầu khi chuyển sang implementation

1. Freeze current code/report inventory; giữ nguyên tất cả thay đổi hiện có.
2. Chốt target/reward units và xử lý G01/G02/G04/G05 bằng tests trước.
3. Triển khai Hillstrom adapter/split manifests và evaluator validation domains còn thiếu; có thể làm độc lập về dependency.
4. R00/R01 pass theo scope → profile M01/M07 → R02 tám models → R03 bounded tuning.
5. R04 đo nguyên nhân cải thiện → R06 selection stress → R09 confirmation; R07/R08/R10 mở theo gates và budget.

Hoàn thiện kế hoạch không có nghĩa tự động bắt đầu các bước trên. Trạng thái cuối của lượt này vẫn là **documentation-only**.

## 19. Test plan còn thiếu trước khi mở research profiles

Danh sách A01–A24 **bổ sung** Q01–Q18 đã có, không tuyên bố đã implement/chạy. Mỗi test cần clean fixture, mutant/edge case, expected state và artifact evidence. Tên test files sẽ theo convention repository khi implementation; không tạo placeholder tests xanh trước logic thật.

| ID | Tầng / phụ thuộc | Fixture hoặc phép kiểm | Expected result |
|---|---|---|---|
| A01 | Unit / G01 | Known e=0,0005 cho một action, probabilities hợp lệ | Primary dùng e nguyên hoặc reject explicit theo support contract; không đổi thành 0,001 ngầm |
| A02 | Unit / G02 | Hai nuisance frames cùng length nhưng row IDs đảo thứ tự | Reindex có kiểm keys hoặc reject; không tính nhầm positional contrast |
| A03 | Unit / G02 | Action labels `1` và `"1"`, duplicate columns, unknown label | Contract reject ambiguity trước scoring |
| A04 | Unit / G02 | NaN/Inf trong reward, propensity, cost hoặc selected nuisance | Fail có row/key/reason, không output metric NaN như success |
| A05 | Statistical / G03 | q=1, e=0,5, noisy reward, policies khác nhau | Total CI không co về zero chỉ vì recruitment hết ngẫu nhiên |
| A06 | Statistical / G03 | Giữ frame, redraw S/A/Y độc lập; so empirical variance với reported variance | Coverage/variance calibration đúng target; recruitment-only mode bị nhận diện sai scope |
| A07 | Integration / G04 | Stage exit 0, output file tồn tại từ run khác | Không COMPLETE; producer/run/config hash mismatch |
| A08 | Integration / G05 | Child timeout, executable missing, interrupted process | TIMEOUT/FAILED/INCOMPLETE manifest vẫn được ghi; child outputs không publish |
| A09 | Integration / WP06 | Crash sau write artifact nhưng trước complete marker | Resume kiểm hash/schema và transactional state; không tự coi artifact partial là success |
| A10 | Integration / WP06 | Cache cùng model seed nhưng khác inner training IDs | Cache miss bắt buộc; không reuse fitted nuisance |
| A11 | Unit / G07 | Cancellation endpoint gắn currency unit nhưng chưa có reward specification | Contract reject; requires distinct target/effect/reward IDs |
| A12 | Statistical / G06 | Repeated batch draws, cap20%, model scores frozen | V08 CI chấm future-batch truth; fixed-vector CI không được tự nâng scope |
| A13 | Unit / allocator | All-equal scores, input row permutation, N=1/4/5/6 | Same stable decisions; K=floor(0,2N); no over-cap off-by-one |
| A14 | Unit / bootstrap | Same original row xuất hiện nhiều draws | Keep occurrences; paired sample/tie order reproducible; không ingest-dedup bootstrap draws |
| A15 | Unit / R00 | Constant reward c≠0, unbalanced realized treatment counts | Correct DR zero exactly; IPW không bị assert zero ở mỗi realization |
| A16 | Unit / data adapter | `visit`, `spend` hoặc renamed post-treatment column đi vào X | Feature provenance rejects; chỉ bỏ tên `conversion` là chưa đủ |
| A17 | Unit / preprocess | Numeric column toàn missing trong train; unseen category ở evaluation | Fitted fallback/token behavior explicit, finite outputs hoặc declared unsupported; không học từ evaluation |
| A18 | Integration / data roles | Calibrator/feature selector thử đọc confirmation labels | Access gate fail và log; không chỉ gate ở model.fit |
| A19 | Integration / R03 | Một required inner/outer fit thất bại | Candidate incomplete, không shortlist bằng surviving folds mean |
| A20 | Unit / labels | Outcome ở boundary t0/H, timezone khác, correction về muộn | Interval convention rõ: event trong `(t0,t0+H]`; no future availability; unknown không thành zero |
| A21 | Integration / ledger | Refund/reversal/duplicate posting, hai episodes cùng account | Monetary conservation, idempotency, reversal linked; không double count theo horizon |
| A22 | Integration / temporal | Decision tháng 24 với horizon90+lag30 nhưng logs chỉ tới tháng24 | NOT_MATURE, không false non-event; cần observation tail |
| A23 | Integration / lifecycle | User dừng sau 2/3 folds; resume đúng config | Không COMPLETE cho run đầu; resume chỉ missing jobs, no overwrite successful artifacts |
| A24 | Reporting / evidence | Result conditional/synthetic, report template yêu cầu headline business gain | Publication gate reject unsupported claim; giữ valid scoped statement |

Cheap unit/contract tests chạy mỗi thay đổi. Integration tiny fixtures chạy trước merge/release. Statistical tests chạy như research jobs có declared N/worlds/budget, không đưa mọi expensive MC vào mỗi test invocation. Existing 18-case suite xanh không thay được A05/A06/A12.

## 20. Runner và artifact lifecycle bàn giao được

### 20.1 Canonical storage sau implementation

- Raw datasets: existing data root + dataset-specific immutable hash/version; chưa đổi/move raw hiện tại trong lượt này.
- Heavy artifacts: `runs/research_v4_1/<protocol_revision>/<run_id>/` chứa resolved config, splits references, models, predictions, logs, metrics, resource report và completion marker.
- Human reports: `reports/experiments_v4/<protocol_revision>/<run_id>/` chứa summary, figures và pointers/hashes tới heavy artifacts; không nhân bản predictions tùy tiện.
- `reports/v4/` hiện có là historical evidence, không dùng làm scratch output của runner mới.

Khóa một convention trong executable config; không vừa dùng `runs/...` vừa `reports/...` như hai truth sources độc lập. Run identity từ experiment/config/input hashes + unique execution attempt ID; repeated attempt có parent, không giả là independent experiment.

### 20.2 State machine và output contract

`DRAFT → FROZEN → VALIDATED → QUEUED → RUNNING → ARTIFACT_VALIDATED → REVIEWED`.

Nhánh riêng: `BLOCKED_DATA`, `BLOCKED_INFERENCE`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `DEFERRED_BUDGET`. Stage completion chỉ là execution status; evidence decision và release tier là fields riêng. `SUCCESS` không tự thành `BENCHMARK_CONFIRMED`.

Runner trước thực thi phải: validate config; resolve dependency graph; list planned fits/readouts/bootstrap jobs; estimate resources từ profiler; kiểm data-role permissions; reserve new run directory; không cho output target trùng historical artifact. Nếu estimate vượt cap, dừng trước main runs và yêu cầu scope decision — không tự giảm số worlds.

Runner sau child exit phải: kiểm exit/timeout; validate schema và producer hashes; reconcile row counts/roles; ghi resources; publish completion marker cuối. Report renderer chỉ đọc completed artifacts đúng revision. Nếu có optional stage deferred, report overall scope phải liệt kê, không dùng “all experiments complete”.

### 20.3 Những lệnh đã có và những lệnh chưa có

Các entry points hiện có gồm `telco_churn.problem_contract_cli`, `challenge_suite`, `inference_smoke`, `assignment_audit`, `research_runner --profile smoke`. Chúng là công cụ kiểm primitives/audit, **không đại diện R00–R09 completed**.

`research_runner --profile screen` và `--profile confirm` hiện không chạy được. Không đưa command giả để người triển khai copy rồi hiểu đã hỗ trợ. Khi bổ sung profile, help/CLI phải công bố dataset/protocol/output/resource args thực sự có và refuse unused/unknown parameters.

Các CLI hiện có có thể ghi vào `reports/v4` mặc định; muốn reproduce mà giữ snapshot thì chạy trong isolated reproduction workspace hoặc sau khi implementation hỗ trợ output namespaces đầy đủ. Chỉ đổi `--report` của parent chưa chắc đổi output paths của child commands. Không chạy kiểm chứng ngay trong lượt planning này.

## 21. Freeze sheet cho từng đợt chạy

Mỗi R-stage là một document/machine-readable record có đủ fields sau trước khi QUEUED; đây là **mẫu đặc tả**, chưa tạo config thực thi:

| Nhóm | Required fields |
|---|---|
| Identity | experiment_id, scientific_revision, stage_id, parent_revision, hypothesis_id |
| Data | source_version/hash, derived_version, eligibility, target_id, action_map, exact split manifest |
| Design | population/finite-frame/batch estimand, batch size, q/e provenance, independent unit, clusters, label maturity |
| Methods | candidate IDs + fully resolved parameters, preprocessing/calibration, nuisance recipe, allocator/tie rule |
| Evaluation | primary contrast/unit/margin, estimator, CI method/domain, secondary list/multiplicity, truth definition |
| Replication | independent world seeds, learner seeds, training/refit/MC counts, bootstrap B, cache policy |
| Resources | CPU/RAM/wall caps, early-stop semantics, profiler record, retry limit |
| Gates | required predecessor statuses, data validity, inference coverage, failure policy |
| Output | new run namespace, required schemas/hashes, plots/tables, claim scope |
| Review | owner/reviewer or self-review, holdout access declaration, freeze timestamp, remaining blockers |

Không có defaults ẩn từ library cho các parameters ảnh hưởng comparison. Không yêu cầu expose mọi internal library option, nhưng resolved constructor và library version phải lưu đủ để reproduce. Quyết định primary/secondary/margin không được suy ra từ file report sau khi kết quả có sẵn.

### Decision note mẫu sau mỗi đợt

“Rxx revision r: kiểm H… trên population… với comparator…; có …/… planned runs hoàn tất, … failures/deferred. Primary delta … [CI…], units…, validity…. Component changed…, independent replications…, compute…. Kết luận thuộc tier…. Quyết định tiếp theo… vì…. Bằng chứng chưa có… và chỉ có thể thu bằng….”

Các chỗ trống chỉ được điền từ artifacts. Kết quả chưa chạy thì ghi NOT_RUN, không dùng expected improvement như observed delta.

## 22. Cấu trúc báo cáo nghiên cứu cuối cùng

1. **Problem và decision:** một use case, một action catalogue, population, BAU/comparator, pain point và business assumptions.
2. **Evidence audit:** dữ liệu gì nhận diện được gì, Orange limitations, timestamps/roles và conflicts đã xử lý.
3. **Methods:** baseline, bounded alternatives, component factors, reward/constraints, evaluator/CI và compute budget.
4. **Validity trước results:** deterministic tests, mutation failures, inference domains, limitations chưa giải quyết.
5. **Main results:** primary policy delta, uncertainty, cost/utilization/events, confirmation và replication tách biệt.
6. **Mechanism study:** component interactions, learning curves, oracle information limits; trường hợp phương pháp thất bại.
7. **Workflow demonstration:** replay/ledger/time-to-campaign, integrity violations và support/fallback behaviors.
8. **Practical decision:** nên đầu tư model, data, action hay delivery; mức bằng chứng nào cần tiếp và chi phí dự kiến.
9. **Limitations/reproducibility:** full attempt ledger, artifacts, environment, negative/inconclusive findings, không giả partner validation.

Đóng góp dự kiến chỉ được giữ nếu có kết quả hỗ trợ:

| Candidate claim | Bằng chứng tối thiểu | Điều có thể bác bỏ/giới hạn claim |
|---|---|---|
| “Component X đáng đầu tư hơn model upgrade Y trong regime Z” | Paired factorial/ablation + independent worlds; real comparison tương thích | Interactions đổi sign, unseen mechanism không lặp hoặc cost xóa gain |
| “Personalization không đáng complexity trong low-event regime này” | Practical-equivalence/non-inferiority evidence hoặc bounded upper gain | CI quá rộng chỉ cho inconclusive, không cho no-benefit conclusion |
| “Sampling theo disagreement giảm chi phí thu bằng chứng” | Valid two-stage estimator + equal-precision validation + full cost ledger | Screening cost lớn, weak overlap, interference hoặc coverage fail |
| “Pipeline ngăn được failure class F” | Clean/mutant tests + realistic replay cho class F | Chỉ fixture handcrafted, bug variation chưa kiểm; không gọi universal safety |

Không lấy paired DR, top-K, cross-fitting hay dùng CatBoost làm novelty tự thân. Đầu tư học thuật nằm ở câu hỏi được kiểm đủ, thiết kế tạo phản ví dụ, ranh giới áp dụng định lượng và tái lập được.

## 23. Định nghĩa “kế hoạch đã đủ để bắt đầu”

Kế hoạch được coi là implementation-ready ở cấp thiết kế khi: có source-of-truth document; default target/comparator/split/metric; ordered run matrix; acceptance tests; current-state/gap map; artifact/runner contracts; effort/compute bounds; behavior khi thiếu data/inference; và claims/release tiers rõ. Những điều kiện dữ liệu/hardware còn mở phải có checkpoint như §17, không bị che bằng một số giả.

Chưa được gọi là “protocol frozen” trước khi source/license/access status, hardware/profile và CI-domain choices đã được kiểm tại implementation checkpoints. Chưa được gọi là “dự án hoàn thiện” chỉ vì tài liệu đã đủ chi tiết. Bước tiếp theo là thực hiện WP01–WP07 theo yêu cầu triển khai riêng, rồi mới mở sàng lọc model.
