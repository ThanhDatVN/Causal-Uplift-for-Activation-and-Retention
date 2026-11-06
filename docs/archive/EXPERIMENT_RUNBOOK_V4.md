# Runbook V4 — Thiết kế các đợt chạy thử nghiệm cụ thể

Soạn ngày 20/09/2026; hoàn thiện bổ sung V4.1 ngày 21/09/2026. **Đây là thiết kế chạy R00–R09, không phải báo cáo đã chạy đủ. Workspace đã có smoke runner và primitives V4; screen/confirm chưa triển khai. Lượt hoàn thiện kế hoạch không chạy thêm experiments.**

Đọc [kế hoạch tổng thể](MASTER_PLAN.md) để biết trạng thái hiện tại và phần việc còn lại. Phần §9 bên dưới chốt các refinement V4.1, có ưu tiên khi khác các lựa chọn V4 ban đầu. Không gắn lại nhãn báo cáo smoke cũ thành R01 completed.

Tài liệu này trả lời “chạy gì, cấu hình nào, bao nhiêu lượt, thứ tự nào, đọc kết quả ra sao”. [V3](EXPERIMENT_DESIGN_V3.md) giải thích pipeline/model/metric; [V4](EXPERIMENT_DESIGN_V4.md) giải thích giả thuyết E19–E28; [roadmap](DEVELOPMENT_PLAN_V4.md) phân bổ công việc phát triển. Runbook này cụ thể hóa một campaign nghiên cứu đầu tiên, không yêu cầu chạy toàn bộ extensions V3/V4.

Các defaults và giới hạn dưới đây là **đề xuất để khóa trước khi chạy**, không là cấu hình tối ưu đã tìm được. Không có số performance giả định nào được ghi thành kết quả đạt được.

## 1. Chốt track, target và tập dữ liệu trước

### Track chính: public randomized marketing, kiểm phương pháp

Chọn Hillstrom làm benchmark mới sau khi kiểm truy cập, nguồn và điều kiện sử dụng. Tài liệu tác giả mô tả 64.000 khách, phân ngẫu nhiên vào Mens email/Womens email/No email, theo dõi visit/conversion/spend hai tuần. [Nguồn gốc dataset](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html)

Đợt đầu dùng **Mens email versus No email**, primary outcome `conversion`, positive effect nghĩa là **tăng xác suất mua**, không phải giảm churn. Cần adapter reward/sign riêng; không đưa conversion vào code convention `Y(0)−Y(1)` rồi giữ nguyên dấu. Với thiết kế ba arms phân bổ đều như nguồn mô tả, assignment probability trong binary subset là 1/2 theo design; phải kiểm provenance/version trước áp dụng, không lấy observed treatment rate để tự chứng nhận design.

Primary policy constraint: contact tối đa 20% eligible cohort; rank policies dùng cùng cap và stable-ID tie break. Primary comparison: challenger versus **control-outcome Logistic ranking** tại cùng constraint. Baseline này xếp theo xác suất conversion không email, chỉ là algorithmic comparator, không phải BAU của một doanh nghiệp thật. Capacity là trần: value policy có thể chọn ít hơn khi estimated effect âm; báo cả utilization và matched-contact sensitivity.

Primary metric: `1.000 × Δ conversion probability` trên toàn eligible cohort. Các outcomes visit/spend và capacities 10%/30% là secondary, không dùng để đổi winner sau khi thấy confirmation. Margin benchmark đề xuất: 1 incremental conversion/1.000 eligible; đây là practical threshold nghiên cứu chưa có economics, không phải ngưỡng launch kinh doanh. Khóa hoặc sửa bằng protocol revision trước khi xem development results.

### Các track bổ trợ

| Track | Chạy gì | Không dùng để làm gì |
|---|---|---|
| Orange | Audit/reanalysis của 8 model dưới assumptions rõ; giữ split lịch sử | Không gọi seed/split mới trên data đã xem là fresh confirmation |
| Synthetic IID | Truth-based estimator tests, model learning curves, oracle decomposition | Không claim telco ROI |
| Synthetic temporal/relational | Maturity, drift, ledger, replay và capacity | Không gán response elasticity giả định cho khách hàng thật |
| Hillstrom Womens / multi-arm | Extension sau primary protocol, report secondary/exploratory | Không coi là external domain replication độc lập của Mens track |
| Criteo hoặc partner mới | Replication có protocol riêng nếu tài nguyên/data hợp lệ | Không âm thầm mở thêm dataset đến khi có kết quả thắng |

Core một dataset thực là bước đầu, chưa đáp ứng tiêu chí methodological replication hai domains của research release V3. Orange unresolved không được dùng để lấp điều kiện đó; nếu chưa có replication hợp lệ thì ghi release chưa đạt phần này.

## 2. Split, seeds và evaluator cố định

### Dữ liệu thật

- Khóa 20% confirmation trước EDA có outcome; 80% development. Manifest lưu exact row IDs/counts/hash, không giả định binary subset có số rows đúng bằng 2/3 của 64.000.
- Split theo stable source ID bằng deterministic hash với salt/version cố định; balance audit do ingestion stage thực hiện và không lựa seed theo effect. Nếu không có ID thật, dùng source-row key gắn raw-file hash và ghi hạn chế dedup/entity linkage.
- Development: 3 outer × 3 inner folds, stratified theo treatment×outcome nếu số events cho phép. Nếu fold support không đủ, **dừng và sửa protocol trước so sánh**; không drop fold xấu rồi lấy trung bình phần còn lại.
- Preprocessing, calibration, nuisance fitting, feature selection và hyperparameter search nằm trong train role tương ứng. Outer evaluation dùng policy fit trên outer-train; confirmation chỉ nhận final frozen policy.
- Xem outer results để chọn/revise phương pháp khiến toàn development study là exploratory. Chỉ nested CV bên trong một stage không tự làm toàn chuỗi nghiên cứu thích nghi trở thành unbiased confirmation.

### Seed roles đề xuất

| Role | Seed / cơ chế |
|---|---|
| Split manifest | 41001 |
| Inner-fold manifests | 42001, 42002, 42003 theo outer fold |
| Model seed chính | 43001 |
| Model-seed stability, chỉ sau shortlist | 43002, 43003; report descriptive, không tạo CI population |
| Screening synthetic worlds | 51001–51020 |
| Confirmation worlds | Seed namespace 61000+, mechanism version khác screening |
| Bootstrap | 71001, 2.000 resamples cho fixed-policy readouts khi bootstrap phù hợp |

Không dùng cùng RNG stream cho world generation, assignment và learner. Mỗi run manifest ghi resolved seeds chứ không chỉ master seed.

### Evaluator không thay tùy model

Primary fixed-policy evaluation: paired DR reward contrast. Nuisance mặc định Logistic L2, C=0,3, train-fitted OHE/scaling, không class balancing; fit từng arm trên train side, known design propensity khi có nguồn xác nhận. Sensitivity: paired IPW và DR với HGB nuisance; không chọn evaluator vì cho model mình thích thắng.

Trên outer fold, evaluator nuisance không fit vào outer evaluation outcomes. Trên confirmation, nuisance fit từ development rồi freeze. Inner DR pseudo-outcomes cho effect training phải cross-fit trong phần training. Cache chỉ reuse khi dataset/fold/train-membership/target/config hashes trùng.

Uncertainty theo account dưới IID working assumptions hoặc đúng cluster/design nếu có. Fixed-size top-K batch policy cần CI/design đã được kiểm ở R01: nếu dùng resampling thì tính lại allocation trong resample cho batch-policy target; nếu conditional on frozen batch decisions thì nói rõ conditional estimand. Không báo SE theo số seeds.

## 3. Danh sách model phải chạy trong vòng sàng lọc

Tám candidates, không bắt đầu bằng tích tổ hợp mọi estimator/library:

| ID | Candidate | Cấu hình mặc định cho screening | Câu hỏi phân biệt |
|---|---|---|---|
| M01 | Control-outcome Logistic ranking | L2 C=0,3; natural prevalence | Baseline đơn giản đủ tốt không? |
| M02 | Control-outcome HGB ranking | 200 iterations, 15 leaves, min-leaf 100, L2=10, LR=0,05 | Nonlinear outcome ranking có thêm value không? |
| M03 | S-Logistic | C=0,3; treatment×numeric/category interactions explicit | Shared linear response có giảm noise không? |
| M04 | S-HGB | HGB settings như M02; treatment là input | Nonlinear shared surface có học treatment response không? |
| M05 | T-Logistic | Hai arm models, C=0,3 | Fit riêng arms tốt hơn sharing khi nào? |
| M06 | T-HGB | Hai arm models, settings như M02 | Treatment heterogeneity có đủ events cho model riêng không? |
| M07 | DR-Ridge | Cross-fitted common nuisances; Ridge alpha=10 | Linear final stage chịu pseudo-outcome noise tốt hơn không? |
| M08 | DR-HGB | Cùng pseudo-outcomes M07; HGB regressor settings tương ứng M02 | Nonlinear final stage có đáng complexity không? |

Tất cả parameters phải được translate/validate theo estimator API ở implementation phase; bảng không phải CLI/config đã chạy được. Tắt implicit early stopping ở screening để fixed iterations dễ đối chiếu; khi bật ở tuning phải có inner-train-side validation được log. Numeric preprocessing, categorical vocabulary và missing rules không thay giữa candidates trừ experiment chuyên biệt.

Feature recipe Hillstrom mặc định: numeric `recency`, `log1p(history)`; binary `mens`, `womens`, `newbie`; categorical `history_segment`, `zip_code`, `channel` bằng train-fitted OHE cho linear models. Chuẩn hóa numeric trên train; numeric missing dùng train median+indicator; categorical missing dùng explicit token. `segment` chỉ là treatment, không là predictor thông thường; `visit`, `conversion`, `spend` đều là post-treatment và không được đưa vào X. `history_segment` và `history` có liên hệ cấu trúc, nên giữ/drop segment là một ablation nếu cần, không âm thầm thay giữa models. HGB screening nhận cùng representation để tách learner effect; native-category là probe riêng.

Baselines không training: no-email; deterministic-ID random contact 20%; constant-effect policy với tie rule cố định. Constant effect ước lượng từ training, không dùng evaluation ATE để quyết định contact. Không đánh đồng ba baselines này với số model fits.

R-/X-learner, CatBoost, honest forest, direct policy tree là **vòng mở rộng có trigger**, không bị loại vì thiếu tên trong core: xem mục 8.

## 4. Lịch chạy R00–R09

`fit` dưới đây là top-level candidate fit. Một T/DR learner có nhiều internal fits; số internal fits và evaluator fits phải log riêng. `readout` là metric/evaluation trên predictions, không phải training. Không cộng các đơn vị khác nhau để quảng bá tổng số “thí nghiệm”.

| Đợt | Run matrix chính | Quy mô kế hoạch | Điều kiện mở đợt |
|---|---|---:|---|
| R00 — Validity/preflight | 18 Q-fixtures V4 + 6 exact identities | 24 fixture cases | Runner/contract triển khai; không cần training study |
| R01 — Evaluator validation | V01–V09, mỗi scenario ≥1.000 worlds; tối đa 3 compatible estimator modes | 9.000 worlds cơ sở; tối đa 27.000 main readouts, chưa gồm boundary/stress cells và bootstrap | R00 pass; V07–V09 theo §9 |
| R02 — Model screening | M01–M08 × 3 outer folds, defaults | 24 candidate fits + baselines/evaluators | R01 validity gates đạt |
| R03 — Bounded tuning | Tối đa 3 families × 8 configs × 3 outer × 3 inner | Tối đa 216 candidate fits + 9 outer refits | R02 completed, shortlist freeze |
| R04 — Component experiments | 8 factorial cells × 3 outer; + 8 cells × 20 mock worlds | 24 real + 160 synthetic pipeline evaluations | Factor levels/nuisances frozen |
| R05 — Learning curves/stability | 3 finalists × 3 sample fractions × 3 outer; seed extras trên full fraction | 27 + 18 candidate fits | R03/R04 chọn bounded finalists |
| R06 — Selection stress | 4 frozen candidate recipes × 50 screening worlds; 200 new worlds nếu đủ budget | 200 + 800 candidate fits, internal fits chưa tính | R01 pass; profiler xác nhận feasible |
| R07 — Temporal/workflow | 4 strategies × 3 mechanisms × 10 worlds, monthly decisions | 120 trajectories, nhiều scheduled refits | Ledger/replay đúng, R00 temporal fixtures pass |
| R08 — Policy comparison/economics | 3 disagreement levels × 2 sampling designs × 1.000 cheap worlds; cost grid đọc lại frozen predictions | 6.000 design-world evaluations; không cần 6.000 refits | Sampling evaluator đã validate |
| R09 — Final confirmation | Final selection 3 families×8 configs×3 inner; refit selected + M01; 1 primary contrast | Tối đa 72 search fits + 2 final fits + evaluator fits | Protocol/sign/target/primary choice freeze, confirmation chưa mở |

R04/R05/R07/R08 là các probes phục vụ chọn cải tiến, không tất cả bắt buộc chạy full ngay. Nếu vượt budget, core tối thiểu là R00/R01/R02/R03, một component study R04, R06 phù hợp khả năng và R09; temporal/economics extensions chuyển backlog bằng revision rõ. Không hạ số Monte Carlo xuống rồi giữ nguyên claim về coverage.

### R00 — Sáu exact identities ngoài Q01–Q18

1. Hai policies giống nhau → paired action-outcome contrast và SE bằng 0.
2. Policy no-action so chính nó → delta bằng 0, không trừ cost tưởng tượng.
3. Bài tiny multi-arm enumerable → IPW/DR expectation khớp truth theo actual assignment design.
4. Constant reward ở mọi action → true contrast bằng 0; DR với correct constant nuisance cho contrast đúng bằng 0. IPW nói chung chỉ bằng 0 trong expectation, không phải mọi finite-sample estimate; kiểm bằng enumeration, không dùng một exact-zero assertion sai.
5. Tiny allocation exhaustive → solver feasible; increasing cost không tăng optimal net value dưới cùng constraints.
6. Chuyển binary adverse-outcome thành reward `1−Y` → positive prevented churn khớp positive reward uplift.

Q-fixtures danh sách ở [E28](EXPERIMENT_DESIGN_V4.md). Gate: zero missed critical fixtures trong bộ đã khai báo; pipeline báo FAILED khi một critical invariant fail.

### R01 — Sáu scenarios phải khóa generator trước chạy

| Scenario | Truth/design | Lỗi cần phát hiện |
|---|---|---|
| V01 | Sharp null, balanced randomized assignment | False promotion; sign và interval plumbing |
| V02 | Constant positive effect, balanced assignment | Bias/coverage/power, không chỉ kiểm null |
| V03 | Heterogeneous effects với marginal ATE=0 | Không đồng nhất weak null với sharp-null permutation; policy truth có thể khác 0 |
| V04 | Known stratum-varying propensity | Constant-propensity evaluator phải bị audit flag; dùng đúng e là comparator |
| V05 | Rare binary outcome và imbalanced assignment | Interval reliability, event scarcity, no false certainty |
| V06 | Repeated accounts/household dependence | IID SE undercoverage; correct cluster/design alternative |

Ba estimator modes là IPW, DR-correct nuisance và DR-misspecified nuisance; propensity đúng ở các modes chính. Constant-propensity bug là negative-control readout thêm tại V04, không một candidate được promote. True value của **policy đang đánh giá**, không ATE chung, xác định null/power cho mỗi readout.

Scenario protocol phải ghi N, event rate, effect, propensity, cluster sizes và policy rule trước chạy; defaults: N=10.000, baseline rate 3,5%, effect V02=0,5 điểm %, V05 rate=0,5% và treatment allocation 90%; V06 clusters 4 accounts với shared latent factor được version. Binary probabilities phải feasible theo construction. Đây là mock values, không estimates từ Orange.

Generator IID đủ cụ thể cho V01–V05: `X1,X2 ~ Bernoulli(0,5)`, `Z ~ Normal(0,1)`, độc lập; `p0=0,01+0,05×sigmoid(0,8(2X1−1)+0,5Z)`. Do đối xứng, marginal p0=3,5%. Đây là xác suất adverse event; reward `R=1−Y`, `p1=p0−tau`. V01 tau=0; V02 tau=0,005; V03/V04 tau=0,01(2X1−1); V05 thay p0 bằng `0,001+0,008×sigmoid(...)` và tau=0,0005, marginal p0=0,5%. Các probabilities nằm trong [0,1] mà không cần clipping. V04 dùng e=0,2 khi X1=0 và e=0,8 khi X1=1; các case còn lại e=0,5 trừ V05 e=0,9.

Policies kiểm estimator là `pi0=no-action`, `pi1=action nếu X1=1`; cap 50% theo expectation, **riêng cho inference fixture**, không thay cap 20% của real benchmark. True population contrasts lần lượt V01=0; V02=0,0025; V03/V04=0,005; V05=0,00025. V03 có ATE=0 nhưng policy contrast dương, nên không chấm đó là false promotion. Finite-frame truth tính conditional expectation trên actual X thay vì lấy population mean như exact finite-frame truth.

V06 dùng tau=0; mỗi cluster có 4 accounts, chung treatment draw e=0,5 và chung outcome uniform shock để tạo residual dependence; marginal p0 như V01. Split và SE phải theo cluster. Đây là deliberately strong dependence challenge, không mô tả household thực. DR-correct-nuisance mode nhận analytic conditional means từ generator chỉ trong evaluator test; misspecified mode dùng intercept-only arm means fit trên independent training sample. Model learners không nhận oracle này. World seed namespaces tách các samples và shocks.

100-world smoke precedes 1.000-world jobs nhưng không được tính là đủ acceptance. Báo binomial uncertainty và width/power. Refinement V4.1: primary promotion dùng lower bound của 95% two-sided CI, nominal one-sided error 2,5%; đề xuất upper Wilson bound false-promotion ≤5% tại đúng null/boundary, theo MASTER_PLAN §4.4. Underpowered alternatives được báo là underpowered, không làm intervals hẹp giả tạo.

### R02/R03 — Cách shortlist và tinh chỉnh

Screen bằng primary value tại cap 20% và baseline M01. Chọn tối đa ba representatives: một outcome-ranking family, một S/T family, một DR family; nếu family invalid thì không lấp chỗ bằng thêm random model. Shortlist và failed fits lưu đầy đủ; development scores không là xác nhận thắng.

Search grids đúng **8 cấu hình/family**:

| Family | Tám cấu hình |
|---|---|
| Logistic-based | C ∈ {0,003; 0,01; 0,03; 0,1; 0,3; 1; 3; 10}; interactions theo model recipe cố định |
| HGB-based | max-leaves ∈ {15,31} × min-leaf ∈ {50,200} × L2 ∈ {1,10}; LR=0,05, iterations cap=300 |
| DR-Ridge | alpha ∈ {0,1; 1; 10; 100} × shrinkage λ ∈ {0,5;1}; shrink toward train-only constant effect |

Không search cả C×features×calibrator×class-weight trong cùng vòng rồi gọi là 8 trials. Calibration và representation là experiments riêng. Mỗi inner fit tính policy value trên inner evaluation, aggregate theo evaluation-unit weights đúng target; hyperparameter selection không đọc outer labels. Outer refit dùng lựa chọn inner của fold đó.

Sau khi xem development outer scores, final selection procedure phải freeze. Trên toàn development chạy lại 3-fold inner search theo recipes đã khóa để lấy final settings; không lấy settings có điểm cao nhất trên confirmation. Nếu chọn M01 hoặc không có candidate đáng xác nhận thì giữ baseline, có thể không mở confirmation để bảo toàn ngân sách bằng chứng.

### R04 — Chạy thuật toán con, không chỉ đổi model name

Factorial A/B/C theo E24:

- A: base feature representation versus base + bốn interactions: `log1p(history)×recency`, `log1p(history)×newbie`, `recency×newbie`, `mens×womens`. Fit/scaling train-only. Hillstrom static không dựng temporal windows giả.
- B: DR-Ridge versus DR-HGB với cùng cross-fitted nuisance/pseudo-outcomes.
- C: feasible rank rule versus net-value allocation, cùng action availability/resource envelope.

Có 8 cells nhưng C chỉ đổi allocator: tại một fold/world chỉ cần **4 effect-model fits** khi cache hợp lệ. Vì vậy 24 real cell evaluations tương ứng 12 effect fits; 160 synthetic cell evaluations tương ứng 80 effect fits, cộng nuisance fits. Nếu binary homogeneous-cost làm C hai levels giống nhau thì giữ làm null fixture; heterogeneous-cost/multi-arm mock mới là distinguishing condition, không bóp dữ liệu để một solver thắng.

Các one-component probes nhỏ, chạy **một probe khi có trigger**, không nhân vào factorial:

| Component | Variants / quy mô cho 1 fixed finalist | Trigger |
|---|---|---|
| Missing processing | train-median+indicator / native missing, 2×3 folds | Missing stress làm score/policy suy giảm; chỉ dùng estimator hỗ trợ cả hai hoặc report pairing limitation |
| S interactions | T only / T×numeric / T×numeric+categories, 3×3 folds | S model kém dù outcome fit ổn |
| Outcome calibration | none / sigmoid / isotonic, 3×3 folds | Arm calibration sai; isotonic chỉ khi event support đủ, fit train-side |
| Effect shrinkage | λ=0/0,25/0,5/0,75/1, 5×3 fold readouts | Pseudo-outcomes noisy, value unstable; fitting cost có thể reuse valid scores |
| Solver | rank / gain-cost ratio / exact tiny knapsack hoặc bounded MIP | Costs/capacity heterogeneity; không dùng outcome truth làm score |

Artifact bắt buộc: main-effect/interaction table, paired uncertainty, runtime, feasibility và decision note về node đáng đầu tư tiếp. Không coi 3 folds là 3 independent real datasets.

### R05 — Dữ liệu ít, thiếu events, model seed

Training fractions 25%/50%/100% trong từng outer-train, stratified; outer evaluation rows giữ nguyên. Cùng fraction membership cho mọi finalist; không sample evaluation để làm prevalence đẹp. Nuisance training cũng theo data-budget regime đã ghi, tránh cho model ít dữ liệu dùng evaluator/training information không ngang bằng.

Ba finalists×ba fractions×ba outer = 27 fits. Tại fraction 100%, thêm hai learner seeds×ba finalists×ba outer =18 fits. CI population không lấy từ 3 seeds; report selected-action agreement, mean/IQR của value và time riêng. Learning curves gồm unique accounts và events mỗi arm.

### R06 — Selection procedure có tự tạo winner giả không?

Chọn 4 fixed recipes từ core, không retune theo world outcomes evaluation. Mỗi world có train/selection/evaluation samples độc lập; selection chọn candidate trên selection sample, evaluation báo true/estimated chosen-policy contrast. So candidate sets chứa 1 versus 4 recipes dùng cùng predictions; không cần fit lại cho mỗi set.

Hai mechanisms: null action effect và weak heterogeneous effect; 50 screening worlds chia đều 25/25. Nếu profiler cho phép, thêm 200 unseen worlds chia 100/100. Báo false selection/promotion, regret, coverage và binomial CI. **100 null worlds không đủ chấm precise 5% false-promotion gate**; chỉ sensitivity về selection. Muốn claim gate của toàn selection procedure phải tăng null replications hoặc thiết kế computationally cheaper pipeline riêng và công bố phạm vi. Không dùng R01 fixed-policy acceptance thay cho R06 full-selection guarantee.

### R07 — Chu kỳ temporal thực sự phải chạy thế nào?

Mock 24 tháng; train ban đầu tháng 1–12, đánh giá decisions tháng 13–24; chỉ labels mature và available trước mỗi training cutoff được vào refit. Bốn strategies: frozen; calibration-only monthly; full expanding monthly; rolling-window 6 tháng monthly. Calibration-only nghĩa outcome/nuisance recalibration được khai báo, không giả đó là sửa mọi treatment-effect drift.

Thêm observation tail sau decision month24 đủ horizon+ingestion lag; với cancellation90 và lag30 cần ít nhất 120 ngày sau decision cuối. Tail không tạo thêm decisions ngoài evaluation scope, nhưng theo dõi outcomes/cashflow của actions đã assigned. Rolling 6 tháng chọn decisions trong trailing window mà labels đã mature, không cố đủ 6 tháng bằng thêm future labels. Cashflow của account ghi một lần theo ngày/tháng, không cộng chồng nhiều reward90 windows thành rollout profit.

Ba mechanisms: covariate shift; treatment-effect reversal; ingestion/label delay. Mười independent worlds/mechanism; tất cả strategies cùng initial world/shocks nhưng actions phải thay future state, không tái chấm fixed logged trajectory như rollout truth. Capacity theo từng tháng; không gộp top-K toàn năm.

Readouts: monthly/whole-horizon reward, ledger reconciliation, account-cluster uncertainty hoặc independent-world paired uncertainty tùy claim, violations, refit count/CPU, degradation/recovery. Chưa có simulator replay đúng thì R07 trạng thái BLOCKED_BY_IMPLEMENTATION, không dùng temporal_lab cũ để tuyên bố đã chạy cùng protocol.

### R08 — Đánh giá policy và sensitivity kinh tế

Disagreement fractions 5%/20%/50%; hai designs uniform versus disagreement-enriched, mỗi cell 1.000 inexpensive worlds. Fixed policies để tách hiệu quả thiết kế thu mẫu khỏi training. Log inclusion q và treatment e riêng; estimator phải target cùng eligible frame. So cost tại **cùng precision**, gồm screening/recruitment/label cost; không so raw N đơn thuần.

Sampling screen cụ thể: frame N=10.000; uniform q=0,2, expected recruited N=2.000. Enriched dùng `q_D=min(0,8; [0,2−0,05(1−d)]/d)` và `q_agree=(0,2−d×q_D)/(1−d)`, với d là actual disagreement share của frame; giữ cùng expected recruited N và coverage sample ngoài D. Action assignment e=0,5 ở sampled units. Cả q và e phải được log; sampling Bernoulli cho phép actual sample size dao động, không ép về 2.000 rồi giữ weights cũ. Sau screen, muốn claim cost-to-precision thì khóa sample sizes mới theo target interval width rồi chạy validation mới; variance-ratio extrapolation đơn thuần chỉ là planning estimate.

Economics readouts trên frozen predictions: assumed unit contact costs 0/0,5/1/2 trong reward currency chỉ khi reward là tiền; không trừ số tiền vào conversion probability. Conversion track báo break-even bằng công thức theo assumed value-per-incremental-conversion rõ đơn vị. Không chọn primary cost scenario theo winner; exact cost amounts có thể đổi trước freeze để phù hợp reward scale, có revision.

Tách uncertainty của fixed policy khỏi policy được reoptimized cho từng cost; cost-based reoptimization là cả một decision rule cần evaluated out-of-sample. Khi chưa có finance ledger thì không có real profit/ROI claim.

### R09 — Confirmation và quy tắc ra quyết định

Trước mở confirmation phải ký manifest: dataset hash/IDs, target sign/horizon, model recipes/settings, preprocessing, policy/capacity/cost, evaluator, primary contrast, margin, CI method, secondary multiplicity và stop rules. Hai final policies/nuisance không được đọc confirmation outcomes trong fit.

Primary: paired delta conversion/1.000 so M01 ở cap 20%, 95% CI phù hợp estimand/design. Lower bound vượt margin benchmark đã khóa → đủ bằng chứng **trên benchmark này**, chưa phải launch thực tế. CI chồng margin → inconclusive hoặc chưa đủ practical improvement; upper bound dưới margin → không chứng minh đáng thay baseline trong phạm vi đã xét. Negative/harm guardrails riêng nếu có.

No-email comparison và spend/visit/budget curves là secondary đã định trước; điều chỉnh multiplicity nếu đưa nhiều confirmatory claims. Không yêu cầu đồng thời IPW và DR significance theo hai gate tùy ý; evaluator disagreement được điều tra theo protocol và validity evidence. Nếu candidate là M01 thì không tạo một “thắng” từ contrast bằng 0.

## 5. Ngân sách tính toán và profile

Chưa có profiling/hardware contract nên không cam kết runtime. Thiết kế khởi đầu: CPU-only, tối đa 4 worker threads/job, một heavy job tại một thời điểm; điều chỉnh sau khi biết RAM/cores, giữ parallelism như nhau cho paired comparisons. Không mặc định CatBoost/GPU/API ngoài được dùng miễn phí.

| Nhóm | Trần CPU-hours đề xuất ban đầu |
|---|---:|
| R00 | 0,5 |
| R01 | 8 |
| R02 | 8 |
| R03 | 30 |
| R04 | 30 |
| R05 | 8 |
| R06 | 8 |
| R07 | 12 |
| R08 | 8 |
| R09 | 6 |
| Tổng trần phân bổ | 118,5 |

Các trần là **budget cap**, không phải dự đoán mọi matrix sẽ chạy đủ trong mức này. Profile một small fit/world trước; projection vượt cap thì chuyển experiment sang DEFERRED hoặc giảm scope bằng revision trước xem kết quả. Ví dụ R06 800 fits có thể không khả thi trong 8 CPU-hours; không tự cắt xuống 20 worlds rồi vẫn báo thiết kế đã hoàn tất.

Giảm budget theo thứ tự: bỏ extra seed stability → hoãn R07/R08 → ít sample-size levels → giảm finalists trước freeze. Không bỏ holdout, leak labels hoặc hạ validity requirements để đủ lịch. CPU-hours khác wall-hours và khác 300–400 giờ công phát triển của roadmap.

## 6. Kết quả từng run phải lưu gì?

Đường dẫn dưới đây là **artifact layout đề xuất**, chưa tạo:

`reports/experiments_v4/<protocol_revision>/<stage>/<run_id>/`

Mỗi run lưu manifest; fit records including internal fits; held-out predictions; chosen actions; constraints/support checks; metric estimates/CI; timing/RAM; failure log. Stage report có tất cả attempted configs kể cả failed/timeouts; không chỉ winner.

Một dòng comparison tối thiểu:

| run_id | model/component | population/split | cap | primary delta/1.000 | CI | events/arm | CPU | validity | decision |
|---|---|---|---|---|---|---|---|---|---|
| Chưa chạy | Chưa có kết quả | Manifest bắt buộc | 20% | Không điền giả | Không điền giả | Từ dữ liệu thật | Đo khi chạy | PENDING | NOT_RUN |

Model scores tách khỏi conclusions: `FIT_FAILED`, `INVALID_EVIDENCE`, `INCONCLUSIVE`, `NO_PRACTICAL_GAIN`, `BENCHMARK_CONFIRMED`, `DEFERRED_BUDGET`. Không gộp failed model vào điểm 0 hoặc âm vô hạn để làm bảng xếp hạng giả.

## 7. Điều kiện để runbook trở thành chạy được

Hiện `research_runner.py` có smoke profile và `scripts/run_research.ps1` có failure propagation; **chưa thực thi đầy đủ protocol R00–R09 này**. `screen`/`confirm` chủ động raise `NotImplementedError`. Contracts, paired comparison, label/economics/integrity primitives đã có; vẫn thiếu Hillstrom adapter và full executable experiment registry. Vì vậy tài liệu không đưa một lệnh `--protocol v4` giả như thể đã hỗ trợ.

Trước khi tuyên bố hoàn thành R00/R01 mới cần hoàn thiện trong phase code được cho phép sau này, có tái sử dụng primitives hiện có:

1. Dataset/target adapter, immutable data-role registry và executable config validation.
2. Correct preprocessing và paired evaluator có design/uncertainty contract.
3. Stage runner với exit-code propagation, caching đúng fold, CPU cap và statuses.
4. Synthetic fixtures/world generator phù hợp scenarios; oracle giữ ngoài model inputs.
5. Report writer đọc artifacts, không tune/retrain khi render.

Runner tương lai phải hỗ trợ ba profiles: smoke chỉ fixtures/small worlds; screen chỉ development; confirm yêu cầu frozen manifest và explicit selection lock. Resume chỉ chạy missing/failed jobs theo cùng config hash, không sửa successful results tại chỗ. Đây là acceptance requirements, không source code được tạo trong lượt lập kế hoạch.

## 8. Khi nào mở thêm models/phương pháp?

| Quan sát từ core | Thử nghiệm kế tiếp có giới hạn | Comparator và tiêu chí |
|---|---|---|
| Arm imbalance khiến T/DR variance cao | X-HGB versus finalist tại 50/50,75/25,90/10 trong mock; cùng total N rồi cùng control-event budget ở study riêng | True regret/value; không nhầm sample composition với algorithm benefit |
| Nuisance misspecification là bottleneck | R-Ridge/R-HGB versus DR dưới correctly/misspecified nuisance | Paired value và sensitivity, không chỉ residual loss |
| Categorical handling gây mất information | CatBoost versus matched HGB/OHE; giữ tuning budget/evaluator | Value, unseen-category failures, runtime |
| Nonlinear effect tốt nhưng variance cao | Honest forest versus DR-shrinkage | Events/leaf, calibration, regret và compute |
| Effect estimation tốt mà decision kém | Direct policy tree depth 1/2/3 versus plug-in allocator | Whole-cohort value và complexity, training/selection độc lập |
| Data lớn, tabular baselines có learning-curve ceiling | Một deep/TabPFN track với license/resource review riêng | Same evidence/compute accounting, không mở đồng loạt nhiều architectures |

Mỗi extension có tối đa hai new families ở vòng đầu, 8 configs/family, một primary hypothesis. Các E21/E23/E25/E26/E27 chỉ mở khi required data và bottleneck tương ứng có thật. Không phải bỏ thử nghiệm model; đây là cách sắp chúng thành các vòng mà mỗi vòng có thể đưa ra một quyết định rõ.

## 9. Bổ sung V4.1 — khóa các chi tiết còn thiếu trước chạy

### 9.1 R01 bổ sung V07–V09

| Scenario | Cơ chế và contrast | Estimators/diagnostics cần chạy |
|---|---|---|
| V07 heavy tail | X~Uniform(0,1), e=0,5; R(a)=1+0,2a(X−0,5)+epsilon, epsilon~t(df=3)/sqrt(3); pi0=hold, pi1=contact nếu X>0,5; population delta=0,025 | IPW, correct-mean DR, constant-mean DR; bias/coverage/width, tail-contribution diagnostics; finite variance không bảo đảm small-sample normal accuracy |
| V08 batch cap | V03 binary DGP; policy scores frozen từ independent training, baseline p0 versus challenger tau; cap=floor(0,2N); N=2.000 cho screen, N=10.000 cho deployment-scale gate | Paired statistic + allocation-aware resampling; compare frozen-actions-only SE như diagnostic; independent worlds với ties/near-ties |
| V09 recruitment + treatment | Finite X frame, V03 reward; pi0=hold, pi1=X1; recruitment q khác theo X1, sau đó e=0,5; thêm q=1 boundary | Two-stage IPW/DR với total uncertainty; current recruitment-only variance là negative-control mode, không được dùng làm main CI |

V07 epsilon độc lập giữa accounts; noise cho potential actions và common-random-number policy comparisons phải ghi coupling. Learner chỉ nhận observed reward. Tails không bị winsorize ở primary; nếu dùng cap thì estimand mới có ID riêng.

V08 truth target phải tách: finite-batch expected contrast là mean `[pi1_i−pi0_i]tau_i` trên actual X; future-batch target là expectation của quantity đó qua batch draws. Gate của primary future-batch CI so với future-batch target tính bằng analytic result nếu có hoặc independent large-MC oracle với reported MC error ≤10% median CI half-width. Không lấy finite-frame truth làm target cho một CI tuyên bố bao gồm X-sampling uncertainty mà không giải thích.

V08 thêm frozen score regimes: continuous oracle scores; rounded scores nhiều ties; constant scores. Fixed policies ở đây gồm entire scoring+allocation recipe, không phải một action vector áp dụng mọi world. Tau của V03 có ties tự nhiên; stable tie dùng hash của predeclared independent row ID, không outcome/risk khi chưa khai báo. Bootstrap occurrences dùng occurrence keys, không làm mất cloned rows.

V09 base q=0,6 khi X1=1, q=0,1 khi X1=0; all-sampled control q=1. Frame N=10.000; stochastic outcomes và action assignment được redraw qua worlds. Một study giữ X frame cố định để chấm finite-frame inference; một secondary study redraw X để chấm superpopulation inference. Không mix hai target errors thành cùng coverage số.

R01 count 9.000 worlds là **base matrix**, chưa gồm second N của V08, tied-score regimes, q=1 controls, practical-boundary cells hoặc bootstrap draws. Run manifest phải enumerate actual matrix và compute projection trước chạy; full acceptance trên một domain cần những stress cells liên quan, không nói 9.000 đã bao phủ mọi Cartesian product.

Bootstrap count: smoke B=199 chỉ kiểm mechanics; development inference screen B=499; final readout B=2.000. Gate phải kiểm method với B sẽ dùng, hoặc chứng minh bằng paired Monte Carlo sensitivity rằng B nhỏ hơn cho cùng quyết định/coverage trong tolerance đã khóa. Nếu không đủ compute thì ghi thiếu gate, không dựa vào quy ước “bootstrap 2.000 là đủ”. Batch allocation bootstrap là phần nặng, không ngoại suy thời gian từ Gaussian fixed-policy smoke.

### 9.2 Practical-boundary null

Đối với rule `lower95 > delta_min`, thêm boundary scenario có true policy delta đúng delta_min. Trong simple policy pi1=X1 và pi0=0 với X1~Bernoulli(0,5), đặt constant tau=2delta_min; nếu delta_min=0,001 thì tau=0,002 và population contrast=0,001. Kiểm power ở delta_min+0,001 và delta_min+0,003 bằng cách đặt tau tương ứng, miễn probabilities feasible.

Đây là thêm diagnostic cells, không sửa V01–V06 truth. Không dùng weak-null ATE=0 để suy ra Type-I control cho policy contrast khác 0.

### 9.3 Tách ba layers nuisance và tránh cache leakage

| Layer | Fit data | Dùng cho gì | Không được reuse khi |
|---|---|---|---|
| Effect-training nuisance | 3-fold cross-fit trong candidate-training portion | DR pseudo-outcomes để fit M07/M08 | Fold/rows/target/preprocessing hoặc nuisance recipe đổi |
| Inner selection evaluator | Inner-train only | Score fixed candidate trên inner evaluation | Evaluation rows đã đi vào fit hoặc calibrator |
| Outer/confirmation evaluator | Outer-train/full development tương ứng | Final paired OPE trên unseen evaluation | Đã fit/select trên outer/confirmation outcomes |

Common nuisance **không nghĩa common leakage**. M07/M08 có thể share cross-fitted pseudo-outcomes cùng training portion; hai inner folds khác nhau không share fitted object chỉ vì seed giống. Nuisance recipe freeze trước so models, không chọn evaluator sau khi biết winner.

Top-level DR fit đếm riêng `nuisance_fit_count`, `effect_fit_count`, `evaluator_fit_count`. DR-Ridge alpha grid có thể reuse pseudo-outcomes nếu mọi parent hashes giống; shrinkage lambda không cần retrain Ridge khi chỉ postprocess đúng train-only constant target. Báo executed fits và logical trials riêng.

### 9.4 Hyperparameter ties, selection và candidate failures

Inner selection tối đa hóa sample-weighted primary value ở budget đã khóa. Tie resolution trong numerical tolerance 1e−8 reward/account: lower declared complexity, rồi lower measured train CPU trên cùng profiling regime, rồi stable config ID. Không dùng informal one-SE rule trên 3 seeds như statistical equivalence.

Một candidate thiếu fit ở bất kỳ required fold → `FIT_FAILED_INCOMPLETE`; không average các folds còn lại để shortlist. Có thể retry một lần cho transient infrastructure failure, đúng config. Algorithmic non-convergence phải log; tăng max_iter là revision nhất quán, không chỉ cứu candidate ưa thích âm thầm.

M01 comparator cố định recipe C=0,3. Nếu outcome-ranking family được tune tốt hơn M01, nó vẫn là challenger, không đổi baseline giữa các stages. Shortlist có thể chứa cả M01 và tuned outcome family, nhưng primary final chỉ một candidate so fixed M01.

M03 S-Logistic treatment interactions không được penalize/scale khác giữa C trials ngoài declared recipe. M04/S-HGB và T-HGB use positive reward orientation. HGB input dense OHE explicit trong core; no target encoding hoặc native-category change trước probe có tên riêng.

### 9.5 R04 mock matrix chốt cho screening

20 screening worlds chia **năm mechanisms, 4 worlds/mechanism**: null; effect aligned với baseline risk; effect independent; effect opposite; interaction-only. Mỗi world có 10.000 train, 5.000 selection và 10.000 evaluation units độc lập, unless profiling revision giảm trước chạy. Same world reused paired giữa 8 cells; không coi 160 cell outputs là 160 independent worlds. Bốn worlds/mechanism chỉ screening/diagnostic; chưa đủ cho phát biểu ổn định của effect theo từng mechanism.

Binary features X1/X2 balanced, p0 như V03. Null tau=0; aligned tau=0,01(2X1−1); independent tau=0,01(2X2−1); opposite tau=−0,01(2X1−1); interaction-only tau=0,01×[2×1(X1=X2)−1]. Do baseline p0 còn phụ thuộc Z, tên aligned/opposite ở đây nói theo X1 risk component, không claim perfect correlation. Tất cả probabilities feasible; interaction-only tạo một test có mục đích cho factor A, không chỉ thêm features vào DGP không cần chúng.

A_mock base là X1/X2/Z; enriched thêm X1×X2, X1×Z, X2×Z và Z², transformations train-only. Đây là adapter theo mock schema; không cố dùng tên `history/recency` khi mock không có các cột đó. Mock baseline có thể rank adverse-event p0, khác control-conversion baseline của Hillstrom; báo task/score orientation rõ, không coi chúng là cùng fitted policy.

Costs của mock economics version độc lập: giả định value-per-prevented-event=100 currency units, cost/action=0,2 hoặc 1,2 tùy observed X2. Đây là proxy economics **chỉ trong simulation**; score orientation Y adverse versus reward phải convert rõ. Capacity 20%, money cap giả định 1.000 CU trên evaluation batch 10.000; null cost-free fixture giữ riêng để test solver equivalence.

Hai C algorithms đều feasible dưới cùng caps: rank-by-benefit rồi duyệt skip actions không vừa budget; optimize predicted net proxy dưới money+contact limits và cho phép no-action. Exact tiny solver reference không suy thành exact large-N solution khi dùng heuristic. Latent/full-state oracle không được nhìn future shock để cạnh tranh với observed-X learners.

Với public conversion không có money rewards, R04 C factor chủ yếu so capacity/rank/positive-effect stop; money-cost distinguishing claim lấy từ mock có nhãn giả định, không gán cho real profit.

Muốn claim một component improvement ngoài exploratory screening, thêm R04-C: freeze tối đa một primary component contrast, ba mechanisms gồm expected-benefit/boundary/negative-control, mỗi mechanism 30 independent new worlds, hai compared recipes → 180 pipeline evaluations. Chọn mechanisms và changed factor trước khi generate confirmation worlds, báo MCSE/CIs theo world; R04-C không phải coverage gate 1.000-world. Quota/projection phải được duyệt trong 150 CPU-hours hoặc scope mở rộng; nếu deferred, main component findings vẫn exploratory dù real final policy được R09 xác nhận. Không dùng kết quả policy tổng thể để khẳng định đã nhận diện riêng main effect của từng component.

### 9.6 Freeze package trước R09

Checklist bắt buộc: full resolved config; code/dependency/raw/split hashes; M01 baseline; chosen model/preprocessor/feature/cost/policy bundle; capacity/tie semantics; target sign/horizon; primary/margin; estimator/CI domain validation; bootstrap plan; secondary multiplicity; resource cap; artifact directory; analyst/owner and holdout-access declaration.

Không đủ một mục → chưa mở confirmation. Freeze là khóa inputs/analysis decisions, không là nhãn viết vào report sau khi đã xem kết quả. Nếu cần bug fix sau mở, giữ evaluation cũ, đánh dấu invalidated và quyết định evidence mới; không chạy lại đến khi headline đẹp.
