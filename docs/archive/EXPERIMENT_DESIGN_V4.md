# Thiết kế thử nghiệm V4: quyết định, nguyên nhân cải thiện và kiểm chứng chất lượng

Soạn ngày 20/09/2026; cập nhật ngày 21/09/2026. **Protocol đề xuất, chưa chạy đầy đủ E19–E28. Một số primitives, mutation fixtures và inference smoke đã có trong workspace; xem [MASTER_PLAN](MASTER_PLAN.md) để phân biệt đã có với còn phải làm.** Lượt hoàn thiện tài liệu không tạo kết quả thử nghiệm mới.

Liên kết: [kế hoạch phát triển V4](DEVELOPMENT_PLAN_V4.md), [pipeline/estimators/metrics V3](EXPERIMENT_DESIGN_V3.md), [review thực trạng](REVIEW_RESEARCH_V3.md). V4 bổ sung V3, không thay các yêu cầu nested selection, untouched confirmation, paired inference, point-in-time và ghi nhận failures.

Lịch chạy cụ thể, candidate defaults, tuning grids và fit-count nằm trong [Runbook R00–R09](EXPERIMENT_RUNBOOK_V4.md).

Các mức tham số, effort và ngưỡng dưới đây là lựa chọn khởi đầu cần freeze trước chạy; không phải mức tối ưu đã xác nhận. Source citations là nền phương pháp. Các grid, fixtures và stop rules là đề xuất cho dự án này, không được gán thành kết quả của bài báo.

## 1. Hợp đồng chung cho mọi thử nghiệm

Mỗi experiment phải có: câu hỏi; population; decision time; estimand; data roles; comparator; factors; nuisance training; primary metric; uncertainty; practical margin; guardrails; compute cap; stopping rule; artifacts. Mọi thay đổi sau khi xem evaluation labels tạo protocol revision và chuyển kết quả liên quan sang exploratory.

Primary mặc định là **delta net reward trên 1.000 eligible accounts so BAU ở cùng resource envelope**, khi có reward thật. Public data thiếu costs thì primary là outcome quan sát được, kèm break-even/sensitivity có nhãn giả định; không đổi tên spend thành profit. Một nghiên cứu inference có primary riêng là coverage/false promotion, không cần ép thành business ROI.

Unit phải phân biệt: account được quyết định; household/queue được randomize; campaign được hold out; independent world được replicate. Customer-months, folds, model seeds và synthetic worlds không phải các đơn vị thống kê thay thế nhau.

Một metric tốt không bù được identification sai. Integrity failure → `INVALID_EVIDENCE`; thiếu precision → `INCONCLUSIVE`; không coi hai trạng thái này là policy không hiệu quả.

Quy tắc chọn phương án: (1) loại khỏi promotion những phương án vi phạm validity/constraints; (2) chọn candidate trên inner evaluation bằng primary value với practical margin, không tổng hợp AUC/Qini/latency thành weighted score tùy ý; (3) confirmation đúng một primary contrast; (4) nếu đạt non-inferiority/equivalence đã định trước thì ưu tiên cost/complexity thấp hơn. Nếu confidence sets vẫn chứa cả các phương án tốt và xấu hơn đáng kể, báo chưa chọn được winner thay vì ép một model đứng đầu leaderboard thành kết luận.

## 2. E19 — Time zero, outcome taxonomy và label adjudication

**Câu hỏi:** hiệu quả apparent của campaign thay đổi bao nhiêu chỉ vì định nghĩa nhãn hoặc lựa chọn khách sau assignment?

**Dữ liệu:** relational mock là track chính; partner event data nếu có. IBM/Orange static không đủ kiểm timing thực, không tạo timestamps giả rồi gọi là external validation.

**Contract:** eligibility và feature cutoff tại `t0`; assignment tại `t0`; delivery có thể sau đó; outcome horizon bắt đầu từ `t0`. Chọn một định nghĩa churn hành chính có thể tái tạo từ status ledger. Nguyên nhân ghi nhận là taxonomy vận hành, không tự động là nguyên nhân causal.

**So sánh có kiểm soát:**

1. As-assigned, toàn eligible cohort, fixed horizon — reference protocol.
2. Chỉ người được delivery hoặc sống đến delivery — negative control design cố ý sai, không candidate để promote.
3. “Không có outcome record = không churn” — negative control measurement.
4. Nhãn provisional versus mature versus correction-aware; corrections đến sau cutoff không được lén sửa thông tin từng có ở quá khứ.

Failure levels: delivery delay 0/3/14 ngày; outcome missing 0/5/20%; delayed correction 0/7/30 ngày; missingness độc lập versus phụ thuộc treatment/risk. Screening dùng một yếu tố mỗi lần; chỉ cross delay×selection khi đã thấy mechanism cần kiểm, không full Cartesian.

**Đầu ra nhãn:** `observed_event`, `observed_no_event`, `right_censored`, `not_yet_mature`, `unresolved_conflict`; `reason_code` và provenance riêng. Adjudication thủ công phải blind với policy score nếu thực hiện được, ghi tỷ lệ bất đồng và quy tắc phân xử.

**Metrics:** label disagreement so adjudicated truth trong mock; maturity completeness theo arm; bias và coverage của policy contrast; false promotion; thay đổi selected policy. Real data không có gold truth thì chỉ báo adjudication agreement/audit errors, không gọi đó là sensitivity/specificity thật.

**Mở rộng survival có điều kiện:** first-exit active days có thể đo restricted mean survival đến horizon cố định. Reactivation đòi hỏi state-occupancy/cumulative active days, không đồng nhất với first-event RMST. Voluntary cancellation và involuntary termination có thể là competing events; không censor một loại rồi dùng `1−KM` làm xác suất thực của loại kia. Dùng cumulative incidence/Aalen–Johansen làm baseline; cause-specific/discrete-time models khi đủ dữ liệu. Hazard ratio không thay chênh lệch xác suất hoặc active days. Cơ sở về competing risks và restricted mean time lost: [Conner & Trinquart](https://pmc.ncbi.nlm.nih.gov/articles/PMC8889377/).

**Gate:** mọi intentional post-assignment selection và immature-as-negative fixture bị flag. Trong real data, nguyên nhân không rõ thì giữ outcome all-cause phù hợp hoặc unknown; không ép mọi account vào một subtype để đủ bảng kết quả.

## 3. E20 — So sánh policy theo vùng bất đồng

### 3.1 Estimand và điều kiện

Freeze hai deterministic policies `π1` và `π0` trước evaluation. Đặt `D(X)=1{π1(X)≠π0(X)}`. Với cùng action semantics, reward, không interference và không policy-specific overhead ngoài reward:

`Δ = E[R(π1(X)) − R(π0(X))] = P(D=1) × E[R(π1(X)) − R(π0(X)) | D=1]`.

Đây là identity của policy contrast, không phải giả định effect bằng 0 trong nhóm agreement: effect so no-contact có thể khác 0, nhưng hai policy thực hiện cùng action. Chi phí chạy challenger khác BAU phải trừ riêng dù D=0.

Dùng DR scores `Γ_i(a)` định nghĩa ở V3. Paired contribution `Z_i=Γ_i(π1(X_i))−Γ_i(π0(X_i))` bằng 0 chính xác khi hai policy chọn cùng action và dùng cùng nuisance estimates. **Paired DR đã tận dụng agreement**; không tạo “phương pháp mới” bằng đặt tên khác cho cùng công thức. Bài nền dùng recommended-action groups để tăng hiệu quả so policy. [Simester, Timoshenko & Zoumpoulis](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3379)

### 3.2 Estimator experiment

Comparators: unpaired policy-value analysis với SE bỏ covariance; đúng paired IPW; đúng paired DR; action-pair stratified estimator. Unpaired dùng làm diagnostic về mất hiệu quả, không làm estimator ưu tiên. Nuisance estimators được cross-fit hoặc fit trên training độc lập; policies không tối ưu trên cùng outcomes đang dùng để báo confirmation.

Mock disagreement fractions 0/5/20/50/100%; baseline event rates 0,5/3,5/12%; effect trong disagreement null/beneficial/harmful; trọng tâm 6–12 cells sau screening thay vì toàn bộ tích tổ hợp. Real track: frozen risk versus regularized CATE trên Hillstrom, E17 confirmation roles không đổi.

Metrics: bias; CI coverage; variance ratio và uncertainty của ratio; power tại practical delta; whole-cohort delta; share changed; computation. `d=0` phải có contrast bằng 0 và SE=0 cho phần action-outcome; fixed deployment cost có thể khiến net contrast âm.

### 3.3 Sampling-design experiment — phần bổ sung thực chất

So uniform evaluation recruitment với disagreement-enriched recruitment. Freeze policies và xác định D từ pre-treatment data. Với finite eligible frame có N người, xác suất được thu vào experiment `q_i` phải biết; trong mẫu, action randomization có probabilities `e_i(a)` riêng. Không nhầm `q` với `e`.

Reference unbiased estimator trong randomized setting: `N⁻¹ Σ_{i sampled} q_i⁻¹ Σ_a [π1(a|X_i)−π0(a|X_i)] 1(A_i=a)R_i/e_i(a)`. Chọn variance estimator theo sampling/randomization design, có finite-population correction khi cần; DR extension phải được kiểm riêng. Với sampling dựa vào strata, cũng có thể estimate contrast trong strata rồi tổng hợp bằng trọng số target frame.

Được đặt q=0 ở agreement chỉ để đánh giá **cặp policy cố định này** khi contribution bằng 0 theo assumptions. Khi muốn absolute policy value, kiểm tra logging hoặc tái sử dụng cho future policies thì cần positive inclusion support thích hợp. Đề xuất thêm coverage sample ở agreement; tỷ lệ chọn theo power/cost planner, không mặc định 10% là đủ.

Không sample-D rồi báo conditional delta như whole-cohort delta. Nếu target là future population thay vì finite frame, phải tính thêm uncertainty/shift của disagreement proportion. Không randomize chỉ D rồi tùy tiện scale lên toàn bộ population khi queue/spillover làm outcomes của agreement thay đổi.

**Cost ledger:** screening toàn frame, feature acquisition, recruitment, treatment cost, outcome observation và fixed system overhead. Comparison phải đạt cùng target precision/power và guardrails trước khi so cost. Với chi phí screening cao hoặc D khó dự đoán, enriched design có thể đắt hơn.

**Gate:** null/coverage của E28 đạt; không thiếu action support; top-K policy cần freeze batch/context và phân bổ capacity nhất quán. Nếu hai policies tranh shared capacity hoặc actions phụ thuộc vào assignments của người khác, chuyển sang whole-policy/cluster trial phù hợp, không dùng identity cá nhân một cách máy móc.

### 3.4 Ví dụ số để nhìn đúng độ lớn bài toán

Ví dụ **giả định**, không phải kết quả dataset: 10.000 eligible accounts; cả BAU và challenger contact 2.000 người; overlap 1.800. Disagreement là 400 người, tức 4% cohort. Giả sử true prevented-churn effect ở 200 người chỉ challenger chọn là 2 điểm %, còn ở 200 người chỉ BAU chọn là 0,5 điểm %. Expected incremental prevented churn của challenger là `200×0,02−200×0,005=3` người trên 10.000, hay **0,03 điểm % trên whole cohort**.

Đây có thể là cải thiện chọn người nhưng vẫn quá nhỏ để biện minh chi phí hệ thống hoặc đo chính xác bằng một campaign nhỏ. Không báo “uplift 2%” như tác động của toàn hệ thống. Thiết kế disagreement-aware có thể giảm nhiễu thu mẫu, không làm effect kinh tế lớn lên. Khả năng tiết kiệm sample/cost còn phụ thuộc variance trong nhóm bất đồng và design thực; không suy ra “giảm 96% mẫu” chỉ từ overlap.

## 4. E21 — Support-aware fallback và confounding sensitivity

**Câu hỏi:** có thể giới hạn personalization vào vùng có bằng chứng mà vẫn đem lại value cho toàn cohort không?

**Ba policy families:** personalize-all; hybrid personalize-where-supported/BAU-elsewhere; baseline BAU. So một confidence-penalty policy nếu CI method đã được kiểm, không coi mỗi CATE interval là reliable chỉ vì model xuất được variance.

Define support bằng logging design, availability của action và effective information trong predeclared strata. Propensity model là diagnostic khi design probability không biết; estimated propensity nằm giữa 0 và 1 không chứng minh positivity/ignorability thực. ESS không thay số events hoặc số độc lập clusters.

Screen support thresholds 0,025/0,05/0,10 cho minimum action propensity nếu phù hợp số arms; report sensitivity, không biến một ngưỡng thành bảo đảm thống kê. Tách các nguyên nhân: structurally unavailable action; sampling không bao phủ population; rare action; confounding unresolved; high estimation uncertainty.

**Population transfer:** nếu trial chỉ tuyển nhóm high-risk, không claim low-risk effect từ extrapolation. Chỉ kiểm weighting/augmented transport estimators khi có covariates ở target frame, participation support và assumptions effect transport phù hợp; thiếu support thì thu trial mới hoặc giới hạn target population. Nền phương pháp: [Dahabreh và cộng sự](https://arxiv.org/abs/1709.04589).

**Sensitivity extension:** so nominal policy với confounding-robust improvement relative BAU dưới sensitivity sets. Grid Gamma 1/1,25/1,5/2 là stress scale đề xuất, không phải calibration của Orange. Gamma giới hạn sai lệch odds/weights theo sensitivity model đã chọn; ghi chính xác model, không trộn các định nghĩa Gamma. Worst-case value trong set không đồng nghĩa CI lấy mẫu; phải xử lý cả hai. Bảo đảm của robust method phụ thuộc uncertainty set chứa cơ chế thật và các assumptions của phương pháp. [Kallus & Zhou](https://arxiv.org/abs/1805.08593)

**Metrics:** full-cohort delta; fallback share; supported-population share; selected-action ESS/events; regret trong simulation; true harm/false-promotion under violated assumptions; sensitivity breakpoint nơi recommendation đổi. Báo outcomes theo support strata, không chỉ value trong subset dễ nhất.

**Gate:** Orange unresolved vẫn conditional, kể cả kết quả robust dương tới Gamma=2. Không chuyển “bền trong grid đã chọn” thành “đã sửa hidden confounding”. Core chỉ cần support diagnostics/fallback; robust solver là extension riêng.

## 5. E22 — Reward modeling, heavy tails và economics stress

**Câu hỏi:** model được chọn có còn tốt khi tối ưu tiền thực thay vì proxy churn × margin không?

Tách ba data regimes: binary churn không cost; nonnegative spend có randomized action; actual contribution ledger có revenues, variable costs, discounts, refunds và write-offs. Primary reward chỉ dùng regime thật đang có. Cost assumptions để stress public data phải có cột `assumed_cost`, không lẫn actual postings.

**Models so sánh:**

- Binary-risk/effect × constant margin: baseline proxy, không chuẩn truth.
- Direct conditional-mean reward: regularized linear model và HGB squared-error.
- Với nonnegative spend nhiều zero: hurdle `P(spend>0|X,A) × E[spend|spend>0,X,A]`; positive part thử Gamma/log-link hoặc suitable boosting; zero-probability calibration kiểm riêng.
- Với net reward có thể âm: direct mean hoặc các thành phần inflow/outflow rồi tổng; không fit Gamma/Tweedie positive model trực tiếp lên số âm. Hurdle decomposition là mô hình nuisance mean, không thay đổi causal assignment analysis.

So direct reward DR versus binary-proxy decision ở cùng data split, action availability và costs. Model tuning theo held-out loss phù hợp mean và policy value trong inner evaluation; không tune theo final OPE.

**Stress worlds:** zero mass 50/90/99%; tail concentration nhẹ/nặng với finite variance được khai báo; top 1% account đóng góp phần lớn reward; negative refunds; treatment tăng conversion nhưng giảm mean net reward; cost mismeasurement ±10/30%; cost correlated với risk/queue load.

Mean reward vẫn là primary nếu quyết định kinh tế dựa tổng tiền. Median hoặc log-reward trả lời câu hỏi khác. Winsorization làm đổi estimand; chỉ dùng secondary capped-reward sensitivity với cap học từ training, không báo CI clipped reward như CI original mean. Robust mean estimators/inference chỉ mở khi điều kiện moment và finite-sample behavior được kiểm; bootstrap không tự cứu được mẫu có quá ít tail events.

**Metrics:** policy delta cùng đơn vị tiền/1.000 eligible; CI coverage trong known-truth worlds; arm-wise mean residual; contribution của tail accounts; maximum offer cost giữ được practical gain; sensitivity của winner theo costs. RMSE chỉ diagnostic, không thay expected net value.

**Gate:** reconcile tổng ledger và reward tổng; costs đếm đúng một lần; labels mature. Nếu không có margin thật, kết luận ở mức spend/churn và break-even, không công bố ROI kinh doanh.

## 6. E23 — Thu thêm dữ liệu hay nâng model?

**Câu hỏi:** đầu tư tích hợp thêm nguồn dữ liệu có tốt hơn giữ feature set rẻ và cải thiện estimator không?

Feature packages trong mock/partner: basic CRM; +billing history; +service incidents; +contact history. Từng package ghi historical availability, update frequency, acquisition cost, latency, missingness và retention policy. Trong public data, grouping không có cost thực thì chỉ là methodological stress, không giả thành chi phí integration của operator.

Thiết kế tối thiểu 2×2: base/enriched features × simple/strong estimator. Sau screening mới thử gated acquisition: mọi account dùng base; chỉ một vùng decision uncertainty xác định từ training được thu feature bổ sung. Threshold/gate được chọn ở inner split; evaluation không dùng outcome để chọn ai “đáng thu thêm”.

**Giá trị thông tin:** đánh giá `V(policy_with_G)−V(policy_base)−acquisition_cost−extra_operating_cost` trên toàn eligible cohort. Thử các cost multipliers và report break-even cost. Giữ timing: feature chỉ có sau contact không được dùng để quyết định contact đầu tiên; nó thuộc bài toán next-stage khác.

Metrics: paired net value; tỷ lệ action đổi; acquisition share; latency percentile; missing-data failure; cost per useful change là diagnostic, không tự chứng minh causality. Feature có AUC gain nhưng không đổi decisions có thể không đáng mua cho use case này.

Oracle trong simulation: cùng observable information trước/sau enrichment, cùng resource/action constraints. Optimal expected value không giảm khi có thêm information miễn phí vì có thể bỏ qua; fitted policy có thể kém do overfit. Phân biệt hai trường hợp này bằng oracle và held-out learning curves.

Negative controls: thêm duplicate feature, noise feature và a forbidden future feature. Hai feature đầu không được kỳ vọng luôn vô hại với finite-sample learner; future feature phải bị contract chặn, không chỉ bị model bỏ qua. Missingness phụ thuộc acquisition gate cần đánh giá trên deployment mechanism đúng, không impute rồi giả sample ngẫu nhiên.

**Gate:** chỉ đề xuất thu data mới khi out-of-sample marginal value có triển vọng vượt cost/latency và data access hợp lệ; nếu CI rộng thì báo mức cost break-even chưa xác định, không hứa tích hợp sẽ có ích.

## 7. E24 — Thử nghiệm chéo và phân tích bottleneck của pipeline

### 7.1 Thiết kế chéo thay vì thay mọi thứ một lúc

Core full factorial 2×2×2, ba factors:

| Factor | Level 0 | Level 1 | Điều kiện giữ cố định |
|---|---|---|---|
| A: representation | Common pre-treatment base representation | Base + interactions đã khai báo; temporal windows chỉ khi data hỗ trợ | Cùng train-only transformations; không thêm outcome information |
| B: effect estimation | Cross-fitted DR + regularized linear final stage | Cùng DR pseudo-outcome/nuisance + HGB final stage | Cùng target, nuisance folds, tuning allowance |
| C: decision rule | Budget-feasible rank-based allocation | Cost-aware net-value constrained allocation | Cùng action set/cost/capacity; cho phép không tiêu hết budget |

Không đồng thời đổi nuisance model, class weights và calibration rồi gán khác biệt cho B. Native categorical versus OHE là một experiment representation riêng với estimator phù hợp; không gộp với data enrichment trong cùng factor A.

Cost/capacity đồng nhất và một action có thể khiến hai C levels trùng nhau; đó là null fixture cần giữ. Multiple actions/heterogeneous costs mới giúp phân biệt allocation; nếu public dataset thiếu actual costs thì kết luận allocation chỉ conditional on cost scenarios.

Mỗi cell dùng cùng outer splits và simulated world để paired comparison; inner tuning độc lập theo cell nhưng cùng tối đa trials/early-stopping rule. Ghi cả runtime thay vì coi equal trial count là equal compute. Failures không bị drop khỏi comparison.

Báo main effects, A×B, A×C, B×C; three-way interaction là exploratory nếu chưa đủ power. Có plot per block/domain, không chỉ pooled average. Full factorial giúp tách interactions; nếu giảm xuống fractional design phải công bố alias structure và những hiệu ứng không thể phân biệt. [NIST DOE](https://www.itl.nist.gov/div898/handbook/pri/section4/pri43.htm)

### 7.2 Oracle substitution chỉ trong simulation

So các hệ thống sau dưới cùng realized world và resource envelope:

1. Learned outcomes/effects + learned policy + actual simulated delivery.
2. Observed-X conditional reward oracle + cùng allocator/delivery.
3. Learned scores + exact optimizer nếu có thể giải bài nhỏ; bài lớn dùng bound/gap được chứng minh, không gọi heuristic là oracle.
4. Observed-X oracle + exact optimizer + actual delivery model.
5. Cùng policy nhưng ideal delivery: **operational upper bound**, không candidate feasible mặc định.
6. Full-state information oracle: **information upper bound**, không ceiling achievable của observed-X learner.

Các chênh lệch là interventions trên pipeline trong simulator, có interaction; tổng các one-at-a-time gains không nhất thiết bằng total regret. Nếu cần phân bổ cộng được, dùng một ordering được khai báo hoặc Shapley trên đủ coalitions và báo dependence vào thiết kế — không nhận đó là causal attribution duy nhất.

**Metrics:** paired true expected reward/regret; expected reward ước lượng bằng nhiều outcome draws hoặc analytic integration, kèm MC error; main/interactions CIs theo independent worlds. Trên real data dùng paired OPE, không có PEHE/oracle decomposition thật.

**Run budget khởi đầu:** 8 cells × 20 independent screening worlds = 160 cell-world evaluations trên một fixed setting, chưa tính refit/nuisance/tuning. Sau profiling chọn tối đa 3 contrasts để confirmation trên new mechanism/worlds; 20 worlds không đủ chứng minh coverage 95%, coverage là E02/E28 job riêng. Không nhân tiếp tất cả datasets×sizes×costs trước khi biết bottleneck.

**Gate:** phải rút ra quyết định đầu tư node nào tiếp theo hoặc kết luận không đủ phân biệt; không chỉ xuất 8 model scores.

## 8. E25 — Delivery, hàng đợi và shared-resource interference

**Câu hỏi:** cải thiện offline có tồn tại khi campaign phải đi qua hàng đợi nhân viên và giới hạn xử lý thực không?

So FIFO, risk priority, estimated net-value priority, deadline-aware feasible priority; dùng cùng contact capacity, shift supply, action costs và eligibility. Không cho policy tốt được thêm nhân viên miễn phí. Mô hình discrete-event đơn giản trước, chưa cần RL.

Stress service-time distributions, contact failure, retry limits, backlog, delays và action expiry. Capacity 0,5×/1×/1,5× reference; delivery efficacy stable versus decay theo delay; agent quality independent versus correlated với assignments. Các mức là mock stress, không dữ kiện ngành.

Đo full-cohort ITT reward, time-to-delivery P50/P95, drop/expiry share, overtime/cost, complaints và realized utilization. Không chỉ đo outcome ở người được serve. Nếu model ước lượng ITT của một delivery regime cũ, đổi regime làm target effect thay đổi; không nhân tiếp reach probability một cách máy móc vào ITT đã bao gồm reach.

Shared resources có thể làm policy treatment ảnh hưởng outcomes của control. Trước trial cần chọn đơn vị cluster phù hợp như queue/team/shift và kiểm carryover. Switchback theo thời gian chỉ là phương án có điều kiện, không mặc định hợp lệ với churn và fatigue dài hạn. Few-cluster designs có thể thiếu power dù nhiều accounts. Microsoft mô tả shared infrastructure là một nguồn làm sai A/B comparison; mô hình call-center này là ứng dụng đề xuất, chưa được xác thực. [Microsoft ExP](https://www.microsoft.com/en-us/research/?p=680556)

**Gate:** nếu interference làm invalid individual-level OPE, báo unsupported estimand/design; không “sửa” bằng chỉ bootstrap cluster khi thiết kế đã bị contamination không nhận diện được.

## 9. E26 — Short-term surrogates: thử cả trường hợp chúng gây quyết định sai

**Câu hỏi:** leading outcomes có rút ngắn thời gian chọn policy mà vẫn bảo toàn quyết định về long-term reward không?

So early churn/usage/payment metrics, frozen surrogate index và direct mature long-term outcome. Learn index trên historical campaigns có cả short/long outcomes, hold out entire future campaigns; không train/index-select trên long-term labels của trial đang “dự đoán sớm”.

Correlation/R² dự đoán tốt không đủ xác nhận causal surrogate. Cần assumptions liên kết treatment, surrogates và long-term outcome, cùng khả năng so sánh giữa nguồn dữ liệu; chỉ số có thể bỏ sót tác động trực tiếp của discount lên margin. [Athey, Chetty, Imbens & Kang, Surrogate Index](https://www.nber.org/papers/w26463)

Mock mechanisms: surrogate hợp lệ; treatment làm usage tốt nhưng margin xấu; treatment effect trực tiếp không đi qua surrogate; mapping shift qua campaign; surrogate measurement khác theo treatment. Report treatment-effect bias/coverage, wrong-promotion rate, time-to-valid-decision, sign errors và tỷ lệ phải chờ mature outcome. R² chỉ metric phụ.

**Gate:** không có nhiều historical campaigns với mature endpoints thì chỉ làm simulation/methodological study. Early readout có thể hỗ trợ futility/operational monitoring theo protocol, không tự thay endpoint chính. Không tuyên bố hoàn tất margin180 trong 12 tuần.

## 10. E27 — Partial pooling giữa campaigns và kiểm negative transfer

**Câu hỏi:** rare events ở từng campaign nên fit riêng, gộp hoàn toàn hay chia sẻ có điều kiện?

Comparators: pooled model không campaign interactions; separate model; hierarchical intercept + treatment slope với regularization; shared representation + campaign-specific simple effect head. Dùng action semantics/version đồng nhất trước pooling; tên action giống nhưng offer khác không đủ để coi là một treatment.

Mock 5/20 campaigns, sizes cân bằng/mất cân bằng, effects homogeneous/heterogeneous/sign reversal, assignment rates thay đổi theo campaign. Trong core chọn một sample-size setting và 3 heterogeneity levels, không full grid. Actual campaign IDs bắt buộc cho real leave-campaign-out; không phân ngẫu nhiên Orange thành campaign giả để chứng minh generalization.

Hai evaluation tasks tách biệt: future wave của campaign đã biết; cold-start campaign chưa biết. Với cold-start, không dùng campaign label outcomes để estimate random effect trước prediction; report prior/population prediction và adaptation learning curve khi có thêm randomized labels.

Metrics: out-of-campaign value, effect calibration, worst predeclared campaign group, negative-transfer frequency, event learning curve; uncertainty theo campaign/world. Chỉ có vài real campaigns thì không dùng cluster bootstrap như thể asymptotic reliable; báo limitation và ưu tiên exact/design-aware analysis khi áp dụng được.

**Gate:** selected policy phải tốt cho deployment task đã chọn, không chỉ pooled average. Một campaign lớn không được che losses ở các campaign nhỏ bằng một kết luận universal.

## 11. E28 — Chứng minh bộ đánh giá có khả năng phát hiện sai

### 11.1 Mutation suite đề xuất

Tạo bản fixture riêng cho từng mutation; không sửa raw data/artifacts gốc. Mỗi case có expected output/state, severity và detector owner. Pass nghĩa là phát hiện/chặn đúng lỗi đã cài, không có nghĩa chống mọi lỗi chưa biết.

| ID | Mutation / tình huống | Expected detector hoặc property |
|---|---|---|
| Q01 | Đảo sign churn-prevention hoặc nhầm treatment/control | Hand-computed reward fixture và sign identity thất bại |
| Q02 | Dùng constant propensity khi design probability đổi theo stratum | Design-log mismatch; simulation bias alarm; estimated e không thay nguồn truth |
| Q03 | Feature event trước snapshot nhưng available_at sau snapshot | PIT gate reject record/feature theo contract |
| Q04 | Fit imputer/scaler trên evaluation batch | Batch/single-row/chunk invariance thất bại khi có missingness |
| Q05 | Duplicate account/assignment sau export retry | Uniqueness/idempotency gate; không xuất contact thứ hai |
| Q06 | Immature/missing outcome thành 0 | Maturity/adjudication gate; arm completeness audit |
| Q07 | Filter delivered-only sau randomization | Cohort reconciliation phát hiện lost ITT denominator |
| Q08 | Trừ offer cost hai lần hoặc chỉ trừ ở treatment được success | Ledger identities, exact tiny example thất bại |
| Q09 | Hai policies giống nhau nhưng contrast SE dương do unpaired analysis | Paired-contrast identity cảnh báo evaluator không phù hợp |
| Q10 | Gộp customer-months như independent accounts | Unit manifest mismatch; undercoverage trong clustered DGP |
| Q11 | Giảm q sampling ở disagreement nhưng quên inclusion weight | Sampling contract + known-truth bias test |
| Q12 | Candidate chọn action logging không có support | Support gate; fallback hoặc invalid evidence, không score-imputation |
| Q13 | Tune hàng chục policies trên confirmation rồi báo best CI | Access/run ledger phát hiện role violation; selection-level null test |
| Q14 | Propagate future/oracle columns qua join hoặc rename | Lineage/allowed-source checks; không chỉ denylist tên cột |
| Q15 | Tie score đổi row order làm đổi selected IDs không có rule | Stable-ID tie policy; reproducibility fixture |
| Q16 | Solver vượt monthly capacity/cooldown ở boundary dates | Feasibility checker độc lập allocator |
| Q17 | Native process exit nonzero nhưng research runner báo success | Failure-propagation contract; run status FAILED, thiếu artifact bị chặn |
| Q18 | Schema/outcome/action version khác mà load bundle cũ | Compatibility gate; yêu cầu explicit migration/re-evaluation |

Q04 liên quan đến lỗi `_prepare` của `CatBoostFrameClassifier` từng dùng median từ batch đầu vào trong review V3. Code hiện tại đã lưu train-fitted `numeric_fill_`; giữ Q04 làm regression test, không gọi lỗi cũ là vẫn tồn tại. Điều này không chứng minh các Orange results hiện có từng sai vì missingness.

### 11.2 Statistical challenge suite

Ba tầng phải tách:

1. **Deterministic identities:** exact tiny data, exhaustive assignments nếu đủ nhỏ, hand-computed reward, identical-policy zero contrast. Hai implementations không được share cùng helper có thể đang sai rồi gọi agreement là validation độc lập.
2. **Fixed-policy inference:** null, constant effect, heterogeneous effect, nonconstant known propensity, rare outcomes, clustered outcomes, heavy tails có finite variance. Mỗi canonical scenario có coverage/bias/false-promotion riêng với binomial uncertainty; giữ ít nhất 1.000 cheap replications/scenario theo V3 khi chấm gate.
3. **Full selection pipeline:** số candidates 1/5/20/50; selection/refit/confirmation; cả nuisance tuning và stopping included. Run budget/MCSE report; nếu chỉ chạy 100 expensive worlds thì không tuyên bố đã đo chính xác false-launch quanh 5%.

Treatment-label permutation trên data thật không luôn mô phỏng đúng weak null “ATE=0” với heterogeneous effects. Randomization inference phải theo actual design và null đã định nghĩa; unstratified permutation không hợp lệ cho mọi stratified/cluster design. A/A kiểm plumbing, không tự chứng minh causal identification của observational data.

Gate V4 ban đầu kế thừa V3 là upper Wilson bound false-promotion ≤7%. **Refinement V4.1** trong MASTER_PLAN §4.4 thay bằng đề xuất upper bound ≤5% cho actual null/boundary của rule lower95 > margin (nominal one-sided 2,5%), ≥1.000 replications/scenario; coverage lower Wilson bound ≥92% cùng width/power. Không pool good/bad worlds; simultaneous statements cần adjusted bounds. Đây là tolerances đề xuất cho protocol mới, không re-grade artifacts lịch sử hay bảo đảm ngoài assumptions.

Đồng thời báo interval width và power ở design alternatives đã khóa bằng power planner. Một rule luôn từ chối mọi policy hoặc luôn trả interval vô hạn có thể false-promotion thấp nhưng không hữu ích; không chấm scientific acceptance chỉ từ null gate. Với các low-sample stress cells cố ý thiếu power, kết quả đúng có thể là `INCONCLUSIVE`; không ép mọi cell đạt 80% power hoặc giảm CI để có winner. So cost-to-precision chỉ giữa những phương án đạt cùng validity và precision target.

### 11.3 Quality metrics mới

| Metric | Định nghĩa / cách sử dụng | Không được diễn giải thành |
|---|---|---|
| Critical-mutation detection | Detected critical cases / declared critical cases; yêu cầu 100% trên curated gate set | Độ an toàn tuyệt đối với bugs chưa biết |
| False-block rate | Tỷ lệ clean fixtures bị chặn, theo từng scenario | Mọi cảnh báo đều là lỗi detector |
| Evidence completeness | Required fields/artifacts present AND validated / required | Đếm file là scientific validity |
| Decision reproducibility | Same immutable inputs/contracts → same decisions hoặc declared numeric tolerance | Reproducible result đương nhiên đúng |
| Cost-to-precision | Tổng cost để đạt interval width/power đã khóa | Giảm N luôn tiết kiệm tiền |
| Supported decision coverage | Share eligible cohort có action recommendation đủ support | Coverage cao đương nhiên value cao |
| Value-equivalence | CI của paired delta nằm trong practical bounds đã định trước | p>0,05 chứng minh không khác |

Cho equivalence hai phía ở alpha 5%, TOST tương ứng CI 90% trong bounds khi điều kiện test đúng; nếu dùng 95% thì conservative hơn. Non-inferiority dùng one-sided bound/margin đúng protocol. Không chọn test/margin sau khi đã thấy winner.

## 12. Ma trận triển khai theo node và phạm vi

| Node V3 | V4 core | Extension khi có điều kiện | Output thực nghiệm |
|---|---|---|---|
| N00 problem/actions | E19 problem/time-zero contract | Competing-event/state model | Estimand và admissible population |
| N01 provenance/design | E21 support diagnostics, E28 Q02/Q11 | Transport/sensitivity optimizer | Support/identification report |
| N02 timing/labels | E19, Q03/Q06/Q07 | Partner adjudication | Mature cohort + exclusion ledger |
| N03 features | E24 representation factor, Q04/Q14 | E23 acquisition | Information value/cost table |
| N04 outcome model | E22 mean-reward baseline | Hurdle/heavy-tail alternatives | Arm-wise nuisance diagnostics |
| N05 effects/policy | E24 regularized DR comparisons | E27 pooling | Paired value và learning curves |
| N06 evaluation | E20 paired contrast, E28 | Enriched sampling, E26 surrogate | Bias/coverage/cost-to-precision |
| N07 allocation | E24 common-envelope comparison | Robust optimization | Feasible decisions và solver gap |
| N08 campaign execution | Q05/Q16/Q17/Q18 | E25 queue trials | Assignment/reward reconciliation |
| N09 temporal adaptation | Freeze/future-wave confirmation | E26/E27 adaptation | Drift/transfer decision report |
| N10 serving/audit | Q04/Q15 + immutable packet | Partner shadow UAT | Replay, failures và latency/cost |

Core không có nghĩa phải hoàn thành mọi model trong E22/E24: bắt đầu smallest informative comparison. Extension chỉ mở bằng decision note chỉ ra bottleneck, required data và compute cap.

## 13. Đầu ra bắt buộc của mỗi vòng nghiên cứu

Một run registry record gồm `experiment_id`, `protocol_revision`, `data_hash`, `population_id`, `estimand_id`, `split_role`, `assignment_design`, `candidate_set`, `cost_scenario`, `seed_roles`, `world_or_campaign_id`, `runtime`, `failure_state`, `artifact_hashes`. Không log PII vào artifact công khai.

Một decision note phải trả lời:

1. Chính xác thay đổi gì, yếu tố nào giữ nguyên?
2. Primary contrast bao nhiêu, CI/MC error và practical margin là gì?
3. Có thay action không, và ở population nào?
4. Kết quả có qua integrity/support/coverage gates không?
5. Thành phần nào giải thích cải thiện; còn interactions/confounding nào chưa phân biệt?
6. Costs, failures, negative cases và phạm vi không suy rộng là gì?
7. Giữ baseline, mở thử nghiệm mới, thu thêm data hay dừng hướng này — vì sao?

Không bổ sung biểu đồ chỉ để tăng số trang. Ưu tiên bốn hình có quyết định rõ: factorial main/interactions; value versus cost/support coverage; cost-to-precision by disagreement; failure-detection/false-promotion matrix. Mọi kết quả synthetic, retrospective conditional và prospective confirmed phải có nhãn khác nhau.
