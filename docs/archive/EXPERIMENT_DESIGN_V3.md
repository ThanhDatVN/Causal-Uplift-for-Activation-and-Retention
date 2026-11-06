# Thiết kế thử nghiệm theo từng nút pipeline — V3

Soạn ngày 19–20/09/2026. Trạng thái: ĐỀ XUẤT, chưa triển khai/chưa có kết quả V3. Cơ sở và các vấn đề cần sửa nằm trong [review](REVIEW_RESEARCH_V3.md); trình tự triển khai trong [roadmap](DEVELOPMENT_PLAN_V3.md).

Mọi mức cải thiện, budget, grids và cỡ mẫu bên dưới là lựa chọn thiết kế khởi đầu để khóa trước khi chạy; không phải cam kết phương pháp sẽ đạt được. Một experiment thất bại vẫn phải tạo được kết luận có phạm vi, độ bất định và hướng hành động.

## 1. Bài toán và estimands

Khách hàng mục tiêu giả định: đội retention của nhà cung cấp Internet/dịch vụ thuê bao có billing, lịch sử sử dụng và kênh liên hệ. Chưa có đối tác thực được xác nhận. Đơn vị quyết định cơ sở là account đang active; account nhiều subscriptions phải xác định đơn vị randomization trước khi xử lý.

Tại thời điểm t, chọn một action trong tập đủ điều kiện cho mỗi account, dưới tổng ngân sách, capacity kênh và cooldown. Action 0 là business-as-usual (BAU), không mặc định là cắt các dịch vụ chăm sóc đang có. Với dữ liệu chỉ có call-versus-control, action phải giữ đúng semantics đó.

Định nghĩa tách biệt:

- Risk: `m0(x)=P(churn trong H | X=x, do(A=0))` nếu nhận diện được; classifier factual thông thường không tự có nghĩa này.
- Prevented churn: `tau_a(x)=E[Y(0)-Y(a)|X=x]`, y=1 là churn.
- Reward kinh tế: `R_H(a)=tổng contribution margin thực thu trong H − incremental contact/offer/service costs`. Chỉ trừ chi phí một lần; BAU cũng có chi phí nếu đang thực hiện.
- Incremental value: `Delta V(pi, pi_BAU)=E[R_H(pi(X))-R_H(pi_BAU(X))]` trên toàn eligible cohort. Primary business estimand là ITT của policy/assignment.

`tau × margin − cost` chỉ là proxy nếu chưa có cash-flow outcome và cần nêu giả định treatment không thay đổi margin ngoài đường churn. Discount có thể làm giảm margin cả ở người vốn sẽ ở lại; khi có revenue/cost logs phải ước lượng trực tiếp reward.

Ví dụ hoàn toàn giả định để kiểm tra semantics: A có risk 30%, prevented churn 0,2 điểm %, margin 600 và cost 8, EV proxy = −6,8; B có risk 8%, prevented churn 2 điểm %, margin 600 và cost 8, EV = +4. Risk ranking chọn A trước, value policy chọn B. Nếu margin của B chỉ 200, EV của B lại âm. Demo phải giải thích được cả ba quyết định bằng dữ liệu/cost assumptions đã version.

Với multi-arm reward, evaluator DR dùng:

`Gamma_i(a) = m_a(X_i) + 1[A_i=a]/e_a(X_i) × (R_i-m_a(X_i))`.

Giá trị policy tất định cố định là mean `Gamma_i(pi(X_i))`; policy ngẫu nhiên dùng tổng `pi(a|X_i) Gamma_i(a)`. So policy bằng paired difference trên cùng evaluation units. Binary churn dùng dấu đảo để positive là prevented churn. Với dữ liệu chỉ có churn, báo prevented churn/1.000 eligible, không tự đặt đơn vị tiền.

## 2. Protocol chung trước mọi model experiment

### 2.1 Bốn lớp tách biệt

1. **Training:** fit preprocessing, nuisance, effect/policy models.
2. **Inner validation/calibration:** chọn family/hyperparameters/calibrator/budget rule. Tất cả choices nằm trong outer-train.
3. **Outer evaluation:** đánh giá cả selection procedure trên fold/window chưa dùng để lựa chọn. Sau khi nhìn outer results để thay thiết kế, coi phiên bản tiếp theo là một analysis mới.
4. **Confirmation:** một evaluation mới được khóa và chỉ mở một lần cho policy cuối. Một random seed khác trên Orange đã xem không tạo confirmation mới.

Orange cũ: toàn bộ kết quả V3 trên file này là reanalysis/exploratory; giữ nguyên split cũ để audit, có thể dùng nested resampling để ước lượng procedure với caveats, không tuyên bố có fresh test. Dataset mới: default 20% locked evaluation và 80% development, split trước EDA có nhãn; thử 3 outer × 3 inner folds trong development, điều chỉnh nếu cell treatment × outcome quá ít. Mọi người xem full labels trước khóa phải được ghi vào access log.

Panel: rolling origins; train chỉ nhận feature/outcome có `available_at` trước as-of training. Nếu horizon H=60 ngày cộng ingestion lag, các decision rows chưa đủ maturity không được thành negative label. Embargo dựa vào overlap cửa sổ label và thời điểm khả dụng, không chọn một gap tùy ý.

Hai deployment targets cần hai protocol: (a) tương lai của khách hiện hữu: được dùng lịch sử quá khứ đúng thời điểm, uncertainty cluster theo account; (b) khách/account mới: thêm group holdout không trùng account. Không ép group-disjoint toàn bộ khi đang trả lời bài toán (a).

### 2.2 Quy tắc so sánh công bằng

- Cùng rows, folds, eligibility, capacity, evaluator và cost assumptions cho một paired comparison.
- Nuisance/evaluator của test chỉ được fit trên train hoặc cross-fit theo protocol đã khóa, không chọn evaluator làm model ưa thích thắng.
- Prediction cache lưu row ID, fold, role, train-membership hash, target semantics, seed và model config.
- OOF scores của nhiều fitted models có thể khác scale; tính value theo fold với rule deployable, so với pooled ranking như sensitivity. Không mặc định pooled top-K OOF chính là policy final refit.
- Báo learning-curve theo số customer và số positive events mỗi arm; không chỉ theo rows.
- Model screen có fixed defaults; chỉ tối đa ba families vào tuning, 12 configs/family cho vòng đầu. Random search/Sobol so với grid nhỏ; chưa cần Bayesian HPO với số trial thấp. Early stopping phải dùng train-side validation đúng time/group.
- Seed stability báo median/IQR/range; không dùng `SD/sqrt(repeats)` làm CI sampling của khách hàng mới.
- Confirmation chỉ có một primary comparison. Secondary family/subgroup tests khóa trước và dùng Holm hoặc simultaneous intervals khi cần. Exploratory heatmap không được biến thành confirmatory discovery.
- Không SMOTE/resample outcomes trong evaluation. Training weighting là một ablation riêng; probabilities sau weighting phải được kiểm tra/calibrate trên natural prevalence.

### 2.3 Ba mức uncertainty

| Câu hỏi | Đơn vị resample/inference | Cách dùng |
|---|---|---|
| Policy cố định tốt hơn baseline bao nhiêu trên population đánh giá? | IID account nếu có cơ sở; cluster household/account nếu repeated; block/campaign khi có cấu trúc | Paired DR influence scores/cluster bootstrap hoặc estimator phù hợp thiết kế |
| Selection procedure có overfit không? | Refit toàn selection bên trong outer resampling; synthetic dùng independent worlds | Report optimism, winner change, false promotion, coverage |
| Pipeline nhạy với randomness bao nhiêu? | Model/fold seeds trên data cố định | Descriptive stability, không thay sampling CI |

Orange thiếu cluster IDs: chỉ có IID-working intervals, phải ghi hạn chế và khảo sát design-effect assumptions. Không gọi row bootstrap là cluster robust. CI cho top-budget curves phải phân biệt pointwise với simultaneous; chọn budget trên cùng curve cần selection adjustment hoặc independent validation.

## 3. Metric framework thay đổi quyết định

| Lớp | Primary hoặc readout chính | Supporting | Vì sao cần / giới hạn |
|---|---|---|---|
| Integrity | Tỷ lệ joins/labels/propensities hợp lệ; SRM theo allocation đã log | Balance global, C2ST AUC/log-loss, overlap, weights, ESS từng arm | SRM không tính bằng cách lấy observed ratio làm expected ratio |
| Risk | Brier/log-loss nếu score dùng cho value; AP tại prevalence gốc nếu ranking | Calibration intercept/slope, reliability CI, recall/lift@capacity, subgroup | AP và AP/prevalence đều không hoàn toàn loại ảnh hưởng base-rate shift |
| Nuisance | OOF Brier/log-loss **từng arm** và error tại selected region | Variance/tail của influence score, arm-balanced summary | Pooled Brier tốt có thể che control model kém |
| CATE magnitude | Held-out causal calibration theo effect bins đã khóa | Causal calibration slope; held-out R-loss/DR-loss như proxy | Proxy loss chịu nuisance error, không phải ground-truth CATE accuracy |
| Heterogeneity | TOC tại capacity chính; RATE-AUTOC hoặc Qini-weighted RATE được khóa trước | Confidence bands, GATES theo 3–5 bins đủ events | Thêm inferential framework; không đếm RATE và Qini liên quan như hai bằng chứng độc lập |
| Policy không có economics | `1000 × E[pi(X) tau(X)]`, paired delta versus baseline cùng capacity | Selected-segment uplift, total prevented, contact count | Denominator primary là toàn eligible cohort; không so average uplift giữa budgets khác như tổng hiệu quả |
| Policy có economics | Incremental net margin/1.000 eligible, CI, delta versus BAU | Spend, contacts, ROI và break-even với CI, budget-value curve | Margin thực khác revenue; ROI dễ bất ổn khi denominator gần 0 |
| Constraint quality | Vi phạm budget/cooldown/eligibility = 0 trên deterministic fixtures | Budget utilization, integer optimality gap, runtime | Không thưởng utilization cao khi incremental value âm |
| Decision procedure | False-launch rate dưới null; coverage; power tại effect kinh tế tối thiểu | Wrong rejection, missed value, expected decision loss, sample/cost-to-decision | Đánh giá gate, không chỉ learner |
| Synthetic | Oracle regret tại cùng constraints; value; negative-CATE contact share | PEHE/RMSE theo đúng information set; ATE error; rank | Negative CATE share không đồng nghĩa observed individual harm |
| Survival, nếu khả thi | IPCW Brier tại 30/60/90/180d và IBS trong support | Uno C-index, dynamic AUC, calibration theo horizon | Censoring phải được mô hình hóa phù hợp; không extrapolate qua follow-up |
| Temporal drift | Worst-window value + average value theo target weights | Detection delay, false alarm, recalibration loss, regret | PSI là covariate diagnostic; không chứng minh treatment-effect drift |
| Operations | End-to-end time-to-campaign; replay consistency; audit completeness | Batch throughput/RSS, queue latency, duplicate actions, backfill cost | API localhost p95 không phải throughput hay SLA production |

TOC/RATE theo [paper RATE](https://arxiv.org/abs/2111.07966); effect calibration theo [causal isotonic calibration](https://proceedings.mlr.press/v202/van-der-laan23a.html); survival theo [scikit-survival](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html). Những metric mới bổ sung góc nhìn, không chữa được thiếu nhận diện causal.

Với weights w: `ESS=(sum w)^2/sum(w^2)` báo riêng từng action và trong selected population; kèm raw event counts, weight quantiles và max contribution. ESS không thay thế power/identification. Trimming/clipping phải có cả kết quả untrimmed và lý do; trimming có thể đổi target population, clipping có thể tạo bias.

Primary capacity nghiên cứu mặc định 20%, secondary 10%/30%; đây là convention để so được với V2, không phải nhu cầu khách hàng đã xác nhận. Có partner thì dùng monthly contact slots và currency budget thật. Không optimize toàn Qini curve rồi mặc nhiên gọi là tối ưu ở 20%.

## 4. Thiết kế từng nút pipeline

### N00 — Problem contract, khách hàng và action

Input: quy trình hiện tại, ai được liên hệ, offer catalogue, capacity, cost ledger, churn definition. Thử so quyết định BAU thực tế với random eligibility, risk và incremental-value policy; không dựng BAU yếu để dễ thắng.

Output bắt buộc: decision contract một trang, action taxonomy, success metric, minimum practical delta, guardrail margins, review owner. Nếu chưa có doanh nghiệp: customer persona và economics đều mang nhãn giả định. Bằng chứng pain point cần số lượt gọi không thành công, offer spend cho khách không thay đổi hành vi, hoặc giá trị mất do label delay; không chỉ một cuộc phỏng vấn nói “cần AI”.

### N01 — Data provenance và experiment integrity

So checksum/version/parser; dedup theo account/campaign; treatment assignment versus actual exposure; tỷ lệ inclusion; time/feature provenance. Với Orange: tái kiểm FACTOR4/18 và toàn features, C2ST gồm Logistic/HGB với ROC-AUC/log-loss, permutation theo thiết kế khả dụng; không dùng accuracy đơn lẻ.

Propensity variants: documented design probabilities nếu có; pooled rate như baseline giả định; estimated cross-fitted logistic/HGB e(X); stratified e(X) chỉ khi strata có căn cứ. Clip {0,01; 0,025; 0,05} chỉ là sensitivity, không chọn theo score tốt nhất. Kiểm missing campaign confounding bằng DGP riêng.

Metric: assignment diagnostics, balance trước/sau weights, ESS, estimator disagreement. Gate: chưa xác định được assignment thì không phát biểu causal business effect; vẫn cho chạy methodological sensitivity có nhãn. Artifact: `dataset_manifest`, `assignment_audit`, `identification_assumptions`, decision `VALID/CONDITIONAL/UNRESOLVED`.

### N02 — Snapshot, labels, missingness và data processing

Schema cần event time và availability time; separate tables: account/subscription, billing, usage, service incident, support ticket, decision, assignment, delivery, outcome. Snapshot phải tái tạo được tại as-of time, không overwrite lịch sử khi backfill.

Ablations: naïve latest-state join versus bitemporal join (naïve là negative control); 0/7/30-day ingestion lag; complete-case versus median+missing indicator versus native missing; duplicates 0/1/5%; outcome delay 0/30/60 ngày. Đổi lag là kịch bản stress, không sửa timestamp gốc của real data rồi gọi quan sát thực.

Kiểm: 100% selected features có availability ≤ decision; labels chưa mature được censor/quarantine; không inner join mất control/failed delivery. Output: rejected-row reasons, training-eligible label manifest, data-quality impact trên decision/value.

### N03 — Feature representation và thuật toán con

| Component | Variants có mục đích | Cách tách ảnh hưởng |
|---|---|---|
| Numeric missing | Median train + indicator; native missing; constant nếu có semantics | Giữ learner/folds nguyên; same-customer score bất biến với batch composition |
| Category | OHE + rare-category grouping; native CatBoost; HGB categorical đúng metadata; ordinal numeric làm baseline cũ | Report memory, unseen-category behavior, arm Brier và policy value |
| Rare grouping | min-frequency {không gộp, 0,5%, 1%} | Fit mapping chỉ train; tránh unique categories tạo leaf ít treatment/control |
| Linear regularization | L2; elastic-net với l1-ratio {0,1; 0,5; 0,9} | C {0,01; 0,1; 1; 10}, budget tối đa 12 configs/family |
| S-learner interactions | T only; T×numeric; T×numeric+categorical | Group/hierarchical shrinkage nếu thêm interactions nhiều |
| Feature compression | Orange all/factor-only/PC20/PC40; train-only new PCA chỉ khi cần | PCA upstream đã cố định và thiếu fit lineage; không gọi public PCs là fold-fitted |
| Temporal features | Window {7,30,90d}; RFM; slope/volatility; EWMA half-life {7,30d} | Ablate từng nhóm rồi factorial nhỏ window×decay; cần event log |
| Feature selection | None; grouped permutation/regularization; domain groups | Selection nằm inner train; SHAP/importance không là causal explanation |

Giữ nguyên Orange PCA factors để reproduce; không ép tất cả dataset cùng feature engineering. Target encoding chỉ cân nhắc với strict OOF encoding và lượng dữ liệu phù hợp; chưa thêm vào core nếu native categories/OHE đã đủ.

### N04 — Risk, outcome nuisances và fine-tuning

Core baselines: constant per-arm probabilities, control-trained Logistic, elastic-net Logistic; HGB/CatBoost là nonlinear challengers. Risk RF cũ được giữ để audit class weighting. LightGBM hoặc XGBoost chỉ thêm một library đầu tiên cho scale/sparsity hypothesis, không thêm cả hai chỉ để tăng số tên.

Outcome search space ban đầu:

- Logistic: C {0,01; 0,1; 1; 10}; class weights none/balanced là ablation riêng.
- HGB: leaves {7,15,31}; min-leaf {30,100,300}; L2 {1,10,30}; learning rate {0,03;0,08}; tối đa 12 cấu hình sampled, max iterations 300, early stopping bên trong fold.
- CatBoost: depth {4,6}; L2 {3,10,30}; iterations {200,500}; learning rate {0,03;0,08}; tối đa 12 cấu hình; native categories; thread/compute budget ghi rõ.
- Calibration: none; sigmoid; isotonic chỉ khi calibration sample/event support đủ; cross-calibration phải nested. Ưu tiên arm-specific Brier/log-loss và policy value, không chọn bằng accuracy.
- Optional TabPFN: fixed published checkpoint, preprocessing train-only; frozen versus bounded fine-tuning trên development nếu license/resources phù hợp; compare 25/50/100% training data, same evaluator. Không mặc định dùng API đưa data bên ngoài. [Cơ sở nghiên cứu](https://www.nature.com/articles/s41586-024-08328-6)

Output: fit time, predict time, memory, per-arm event learning curve, calibration by risk/value strata. Nuisance winner không tự là policy winner.

### N05 — CATE và học policy trực tiếp

Giữ S/T/TO/DR/R/X cũ làm reference; chọn subset theo hypothesis và runtime, không chạy full Cartesian product.

| Nhánh | Biến thể | Hypothesis cần kiểm chứng |
|---|---|---|
| S/T | Logistic interactions, HGB, CatBoost | Shared representation giảm variance hay làm mất treatment interaction? |
| DR second stage | Ridge; HGB; ExtraTrees | Linear/shrinkage stage có tốt hơn nonlinear stage khi pseudo-outcome noise cao? |
| R-learner | Linear weighted residual versus HGB; known/design e và estimated e | Orthogonalization giúp ở nuisance misspecification nào? |
| X-learner | Logistic/CatBoost arm models; linear versus HGB effect | Lợi ích khi imbalance tăng 50/50→75/25→90/10 có còn sau cùng event budget? |
| Honest causal forest | Honesty on; min-node {50,100,200}; sample fraction {0,5;0,8}; fixed tree count vòng đầu | Local effect estimation có đủ support cho heterogeneous decisions? |
| Shrinkage effect | Constant/strata ATE + λ × learned DR residual, λ {0;0,25;0,5;0,75;1} | Partial pooling có giảm regret và false positives khi heterogeneity yếu? |
| Rank blend | Percentile risk + percentile CATE, weight {0;0,25;0,5;0,75;1} | Kết hợp ranking có tốt hơn chọn cứng một family? Không dùng rank blend như effect magnitude |
| Direct policy | DR policy tree depth {1,2,3}; cost-sensitive classifier | Tối ưu decision/value trực tiếp có thắng estimate-then-rank? |
| Optional deep causal | TARNet/Dragonnet-style shared representation; batch/loss/targeted regularization ablation | Chỉ trên Criteo/large synthetic sau small-data baselines; kiểm representation versus loss riêng |

Shrinkage/rank blend ở đây là ứng viên tổng hợp để kiểm nghiệm, chưa tuyên bố novelty. Tau shrink có cùng đơn vị effect; tránh trộn raw risk với CATE rồi gọi tổng đó là xác suất/giá trị.

Effect calibration: raw versus simple shrinkage versus causal isotonic/cross-calibration, dùng data ngoài effect fit. Metric chính là value tại cost threshold; ranking AUUC có thể không đổi dù calibration làm quyết định positive-value tốt hơn.

### N06 — Evaluator và lựa chọn phương pháp

So difference-in-means khi design cho phép; Horvitz–Thompson/IPW; Hájek normalization; AIPW/DR với nuisance Logistic/HGB/CatBoost; covariate adjustment theo [nghiên cứu evaluation](https://arxiv.org/abs/2210.02152). CUPED/CUPAC chỉ dùng pre-period covariates: spend/usage/complaints, không dùng outcome sau treatment.

Không chọn evaluator dựa vào Qini lớn nhất. Trên known-truth worlds, so bias, empirical SD, CI coverage, interval width và false model promotion. Trên real data, evaluator chính được khóa theo thiết kế; khác biệt DR/IPW là câu hỏi chẩn đoán về overlap, nuisance, event count, assignment và variance.

Primary gate: lower confidence bound của paired `Delta V` versus baseline vượt minimum practical delta đã khóa và guardrails đạt; primary CI phải có coverage được kiểm tra. Secondary IPW robustness được diễn giải, không máy móc yêu cầu hai noisy estimators đều significant. Với Orange chưa resolve F01 thì gate causal vẫn đóng bất kể metric tốt.

### N07 — Allocation, capacity và no-contact

So: fixed top-K risk; top-K CATE; positive net-value threshold; greedy value/cost; integer knapsack/MILP; multi-action budget allocation; direct policy tree. Always include no-intervention relative to BAU, random feasible policy và current business rule nếu có.

Constraint: mỗi account ≤1 action/campaign; monetary budget; call minutes; channel slots; eligibility; cooldown; offer stock; household grouping nếu cần. Chọn ít hơn K là hợp lệ. Control và exploration nằm trong kế hoạch capacity/cost và không bị export sau đó ghi đè.

Với equal costs và chỉ capacity, top positive value có nghiệm đơn giản. Với heterogeneous costs và mutually exclusive actions, so solver với [MAQ](https://grf-labs.github.io/maq/REFERENCE.html) ở relaxed setting phù hợp; với constraints integer/channel, dùng optimality gap và brute-force fixtures nhỏ làm oracle. Không mặc định ratio greedy tối ưu.

### N08 — Experiment assignment, delivery và feedback

Unit/account IDs, assignment probability, randomization strata/version phải immutable. Delivery/acceptance cập nhật riêng; treatment thất bại vẫn ở assigned arm cho ITT. Không nhân ITT effect thêm một lần với delivery probability; điều đó double-discounts reach. Reach-aware modeling là nhánh phụ cần estimand và assumptions khác.

So designs: 50/50; 75/25; blocked randomization theo pre-risk/value; HS sampling; supervised exploration có e bounded. Tách sampling probability vào experiment khỏi treatment probability trong experiment. Tổng budget bằng nhau, so cả opportunity cost và information gain. Nuisance/evaluator không thấy future outcomes trong adaptive rounds.

### N09 — Temporal adaptation, survival và repeated action

So frozen model; expanding window; sliding window {3,6,12 tháng}; exponential time weights half-life {1,3,6 tháng}; recalibration-only; full retrain. Giữ cùng as-of cutoffs và label maturity, so compute với worst-window value và recovery delay.

Drift scenarios tách P(X), baseline risk, tau, action cost, delivery. PSI/C2ST không phát hiện được mọi effect drift; monitor matured DR/value outcomes. Khi có event times, so discrete-time pooled Logistic hazard, Coxnet và random survival forest; không triển khai survival-uplift chỉ vì có cột tenure.

Repeated policy: replay từng account trajectory dưới từng policy, với fresh active set/history/cost và monthly capacity. Multi-step causal OPE/contextual bandit chỉ mở sau static OPE/overlap/propensity logging đã được chứng minh; chưa chọn RL làm core.

### N10 — Serving, monitoring và notebook

Batch-first artifact cần account/snapshot/eligibility/action/score semantics/policy version/reason/assignment status. API preview đọc cùng bundle và validation contract. Integrity fail phải chặn export; evidence inconclusive phải trả lý do riêng.

Kiểm same input same decision, batch size/order invariance, duplicate requests không nhân action, replay từ frozen inputs, missing label không bị đổi thành no-churn. Load profile {10k,100k,1M} rows; đo RSS, wall time, throughput, concurrent API preview 1/10/50 clients nếu cần; không lấy API làm trung tâm học thuật.

Notebook map: 01 data audit; 02 processing; 03 assignment/identification; 04 DGP/world benchmark; 05 selection procedure; 06 policy value/failure; thêm 07 external datasets, 08 constrained multi-action, 09 temporal/maturity, 10 experiment design/power, 11 replay/operations, 12 claims/evidence report. Notebook gọi package/config đã version, không nhân bản training logic.

## 5. Experiment cards, simulator và quyết định

### 5.1 Registry bắt buộc cho mỗi experiment

Mỗi record có `experiment_id`, câu hỏi, giả thuyết, estimand, evidence tier, dataset/version/hash, population, feature cutoff, label maturity, split hash, comparator, changed components, fixed components, search budget, primary metric, minimum practical delta, uncertainty method, multiplicity family, stopping rule, expected artifacts và decision owner.

Run record bổ sung actual config, environment/code snapshot hash, seed, start/end time, CPU/GPU-hours, max RSS, warnings/errors, excluded rows, event counts, model/prediction hashes và mọi failed runs. Thay config sau kết quả phải tạo revision; không sửa hypothesis cũ thành câu phù hợp winner mới.

### 5.2 Các thí nghiệm ưu tiên, có thể chạy độc lập theo dependencies

| ID / ưu tiên | Thiết kế và comparator | Metric quyết định / đầu ra | Điều kiện tiếp tục hoặc dừng |
|---|---|---|---|
| E01 / P0 | Orange pooled e versus e(X) sensitivity; đối chiếu nguồn/version và imbalance; semi-synthetic pooled campaigns với allocation khác nhau | Assignment audit; changes in ATE/policy ranking; ESS; nhận diện giả định nào làm kết luận đổi | Không promote Orange causal policy nếu provenance/identification chưa resolve; chuyển benchmark chính sang Hillstrom |
| E02 / P0 | Fixed policy trên null/constant/heterogeneous worlds; IID-bootstrap cũ versus design-aware IF/cluster bootstrap; refit-selection bootstrap riêng | Bias, nominal 95% coverage, false launch; `inference_validation` | Không dùng evaluator/gate để chọn model trước khi null/coverage đạt protocol |
| E03 / P0 | Latest-state versus point-in-time joins; mature-only versus naïve labels; inject delay/duplicates | Số leakage caught, metric optimism, decision changes; `data_failure_report` | Mọi deliberate future feature phải bị phát hiện; label immature không vào training |
| E04 / P1 | OHE/native categorical/ordinal; missing handling; class weighting; S interactions đầy đủ | Arm Brier/log-loss, policy delta, runtime/RSS; `representation_ablation` | Chỉ giữ component có gain vượt uncertainty hoặc giảm cost trong non-inferiority margin đã khóa |
| E05 / P1 | Risk, S/T/DR/R/X, honest forest trên 10/25/50/100% train; control share 50/25/10%; common test | Value@20%, RATE, per-arm calibration, control-event learning curves | Kết luận theo regime; không tuyên bố một global winner từ mean rank mọi dataset |
| E06 / P1 | DR residual shrink λ grid và rank blend versus best simple risk/CATE; include λ=0/1 | Paired regret/value delta, variance, harmful-contact share; `shrinkage_phase_map` | Loại nếu chỉ thắng selected seeds/cells hoặc chọn λ đòi test labels |
| E07 / P1 | Raw effect, constant shrink, causal isotonic/cross-calibration; cost threshold sweep khóa trước | Held-out calibration, value/decision changes, Brier arm; `calibration_to_value` | Qini giữ nguyên vẫn có thể hữu ích nếu value tăng; không giữ nếu tăng variance ở sparse bins |
| E08 / P1 | Estimate-then-optimize versus DR policy tree depth 1/2/3 và cost-sensitive classification | Value@budget, complexity, stability, auditability; `direct_policy_comparison` | Giữ policy đơn giản nếu delta không vượt chi phí vận hành thêm |
| E09 / P1 | Equal versus heterogeneous costs; top-K, ratio greedy, exact integer solver, MAQ trong compatible setting | Constraint violations, value gap versus constrained oracle, solver runtime | Zero constraint violations; exact fixtures phải đúng; approximate solver cần feasible solution + bound/status |
| E10 / P1 | Hillstrom visit versus conversion versus spend models; binary versus original 3-arm policy; revenue-only versus assumed net margin sensitivity | Incremental spend/1.000, conversion, budget-value curve; `multi_outcome_tradeoff` | Không gọi spend là profit; không đổi primary sang visit chỉ vì spend không significant |
| E11 / P1 | Frozen/recalibration/sliding/expanding/decay dưới từng loại drift và label delay | Worst-window value, cumulative decision loss, adaptation lag, compute | Phân biệt cost/model/assignment/data failure; không retrain vì PSI đơn lẻ |
| E12 / P1 | One-step re-ranking versus trajectory replay; cooldown 0/30/90d, fatigue on/off, monthly constraints | Cash flow 180d/account, churn, contacts, missed value; `trajectory_policy_report` | Không cộng overlapping six-month proxy; oracle phải chịu cùng action constraints |
| E13 / P1 | Uniform sampling/randomization, risk-stratified, HS sampling và supervised exploration | CI width, power, false launch, cost-to-decision, acquisition opportunity cost | Đạt coverage trước khi xét giảm N; inclusion/treatment probabilities đầy đủ; so cùng total cost |
| E14 / P2 | Fixed-N, planned group-sequential, confidence-sequence; daily naïve p-test làm negative control | Type I error, power, time-to-decision với delayed outcomes | Không dùng CS theorem ngoài assumptions; freeze policy theo round, hoặc dùng adaptive inference phù hợp |
| E15 / P2 | KKBox/partner/synthetic event-time: fixed-horizon classifier, discrete hazard, Coxnet, RSF | IBS, horizon calibration, value của lead-time thay đổi | Chỉ mở khi event/censoring definitions có căn cứ; nếu thiếu chỉ giữ synthetic mechanism study |
| E16 / P1 | Batch replay/API/export với duplicate requests, changed order, partial failure, late backfill | Decision reproducibility, idempotency, completeness, time-to-campaign/RSS | Zero duplicate actions trên fixtures; mọi quyết định truy được tới input/model/policy hashes |
| E17 / P1 | Khóa top 3 methods trước khi mở Hillstrom/Criteo confirmation; tiers Criteo 100k/1M/full nếu đủ resources | Paired value/ranking intervals mỗi domain, time/memory scaling, event counts | Không pool outcomes khác semantics; full scale chỉ khi 1M có câu hỏi chưa trả lời |
| E18 / P2 | Reason codes và failure cases trước/sau pipeline V3; subgroup constraints nếu có business justification | Decision explanation completeness, subgroup effect CI, analyst review time/errors | Không gọi PCA/SHAP là nguyên nhân hay treatment recommendation causal |

Dependencies: E01–E03 → E04–E08 → E09–E12 → E13–E17; E16 xây song song theo schema sau E03; E18 sau khi có decisions. Không phải mọi experiment đều phải chạy mới được có release; core milestone ở roadmap.

### 5.3 Ba nghiên cứu có thể tạo đóng góp học thuật

**Study A — Khi nào có thể tin vào việc chọn policy trên low-event campaign data?**

So protocol V2 với protocol V3 bằng false promotion, interval coverage, evaluator disagreement và estimated-versus-true value. Thay đổi có kiểm soát assignment heterogeneity, hidden campaign membership, control events, number of tried policies và rare outcomes. Ablation từng thay đổi: correct propensity; proper evaluation split; design-aware uncertainty; practical-value gate. Tạo bảng “nguồn sai lệch → mức sai → điều kiện phát hiện → sửa có tác dụng đến đâu”. Nếu Orange không resolve được, đó là dataset limitation được đo và documented, không dùng p-value để cáo buộc tác giả.

**Study B — Khi nào shrinkage/calibration/direct policy đáng hơn learner phức tạp?**

Các trục: heterogeneity yếu/mạnh, risk–effect correlation âm/0/dương, số control events, action-cost dispersion và covariate predictability. Compare best tuned simple baseline, best existing CATE method, shrinkage, calibrated policy và direct policy với equal selection budget. Báo phase diagram và uncertainty của paired delta. Nếu không có method mới thắng, đóng góp khả dĩ là giới hạn và quy tắc chọn phương pháp có thể tái lập, chưa mặc định đủ novelty để xuất bản.

**Study C — Có thể giảm chi phí thu bằng chứng giữ chân khách hàng không?**

So E13–E14 theo đường frontier giữa experiment cost, power và policy regret. Phân biệt sampling high-risk để tăng event count với thay đổi estimand. Mục tiêu nghiên cứu đề xuất: tìm chế độ giảm ≥20% tổng cost để đạt cùng precision/power mà không làm coverage kém; con số 20% là target đánh giá, không phải kết quả hay threshold phổ quát. Báo cả regimes không giảm được do nuisance predictability yếu, extreme weights hoặc label delay.

Không gộp cả ba thành một tuyên bố “thuật toán mới”. Study A là ưu tiên bắt buộc; B/C là hai hướng cạnh tranh về effort. Sau pilot simulation đầu tiên chọn một hướng làm đóng góp chính, hướng còn lại là supporting/extension.

## 6. Mock data có cơ chế và kiểm soát được

### 6.1 Ba loại evidence khác nhau

1. Fully synthetic structural worlds để biết assignment/effect/noise và kiểm coverage.
2. Semi-synthetic trên covariates thật của development Orange/Hillstrom/Criteo, tạo treatment/outcomes mới theo công thức khóa trước. Không giữ label thật rồi sửa nhãn cho model ưa thích thắng.
3. Relational event simulator để kiểm pipeline/time/operations; accuracy ở đây không là external effectiveness.

Mỗi world có customer/account state, calendar shock, treatment assignment, delivery, costs, recurring cash flow và exit/censor process. Các seed cho covariates, assignment, outcomes, delay và model tách nhau. Simulation evaluation seeds khác design seeds; lưu cả failed worlds. Giữ một số **DGP structures** chưa dùng khi tune, không chỉ seed mới của cùng công thức.

### 6.2 Cơ chế và lưới giá trị khởi đầu

| Cơ chế | Mức thử | Pain point / thông tin cần rút ra |
|---|---|---|
| Baseline churn | 1%, 3,5%, 10% | Learner/evaluator cần bao nhiêu events để ra quyết định? |
| Effect | Null; constant positive; heterogeneous mixed-sign | Gate có launch giả? Ranking có cần khi effect hằng? |
| Risk–effect relation | Âm; gần 0; dương | Khi nào risk proxy thắng/thua, thay vì thiết kế risk luôn thua |
| Assignment | e=0,5; 0,75; 0,9; e(X); pooled latent campaigns | Global rate có gây bias/false winner? |
| Confounding | Không; measured; latent | DR không sửa được hidden confounding đến mức nào? |
| Noise/predictability | Low/high explained outcome variance | Khi nào adjustment/CUPAC đáng đầu tư? |
| Costs/margin | Constant; heterogeneous; correlate/anticorrelate with tau | Uplift ranking tốt có thể lỗ vì đâu? |
| Delivery | 100%, 70%, 40%; differential reach | Assignment effect versus delivered-treatment selection |
| Delay/missingness | Availability lag 0/7/30d; outcome missing 0/10/30% | Data recency và outcome maturity làm policy sai thế nào? |
| Drift | None; covariate; baseline; tau sign flip; cost/delivery | Method nào phục hồi, method nào chỉ đổi calibration? |
| Contact fatigue | Off; diminishing returns; harmful repeated contacts | Static policy cho quá nhiều ưu đãi có làm giảm lifetime value? |
| Dependence | IID; household clusters; network spillover stress | Sai số CI/estimand nếu giả độc lập; cluster design có trade-off gì? |
| Censoring | Administrative; covariate-dependent; latent-dependent stress | IPCW đúng/sai assumptions gây lỗi bao nhiêu? |

Không chạy full Cartesian grid. Khởi đầu 12 canonical scenarios:

- S00 null treatment; S01 constant benefit; S02 aligned risk/tau; S03 independent risk/tau; S04 opposite risk/tau; S05 weak overlap; S06 latent pooled campaigns; S07 covariate-only drift; S08 tau reversal; S09 heterogeneous economics; S10 delay/censoring; S11 fatigue/repeated actions.
- Mỗi scenario có base và severe variant → 24 cells. Dùng fractional factorial bổ sung cho hai interactions quan trọng nhất tìm từ câu hỏi trước chạy, không chọn theo effect đẹp.
- Dataset sizes 5k/20k/100k accounts theo mục đích; chưa nhân tất cả size × 24 cells × mọi model. Screen 5k/20k trước, mở 100k cho learning-curve và scale hypothesis.
- Stage cheap inference: 1.000–5.000 worlds cho fixed-score estimator/gate, ít hoặc không fit model.
- Stage refit model: 20 worlds/cell để phát hiện failure lớn; 100 worlds/cell cho paired performance chính; tăng theo Monte Carlo error thay vì chọn seed đẹp. Compute có thể buộc giảm cells, phải báo rõ coverage của nghiên cứu.

Ở false-launch probability 5%, Monte Carlo SE với 1.000 worlds khoảng 0,69 điểm %. Với 20 worlds, sai số quá lớn để tuyên bố kiểm soát Type I error. Luôn báo MCSE hoặc Wilson interval của false-launch/coverage, không dùng 20 training seeds để xác nhận “an toàn 95%”.

### 6.3 Oracles và tính đúng của mock

Fully observed track có analytic CATE. Latent track phải có integration oracle theo observed X (kèm MC error) và full-state upper bound riêng. Policy oracle có đúng action availability, cost, monthly budget, cooldown và information cutoff như policy so sánh. Nếu dùng clairvoyant oracle biết future shocks, ghi rõ đó chỉ là upper bound.

Cash flow được ghi theo account-day/month, mỗi khoản đúng một lần. Replay policy thay cả future state, history và active population. Shared random numbers giữa policies giảm variance của paired differences nhưng phải có nhiều independent worlds; không dùng chung world làm “N thí nghiệm độc lập”.

Generator được accept khi: treatment null cho effect 0 trong expectation; increasing cost không tăng feasible optimal net value; capacity tối đa không bắt buộc phải lấp đầy; churned account không tái xuất hiện trừ khi có reactivation process; changing policy thay trajectories; output không lộ oracle vào features. Các điều kiện này phải có fixtures/metamorphic tests ở implementation phase.

Mock không thể xác thực willingness-to-pay, agent behavior hay response elasticity thực tế. Với partner, calibrate distributions/ranges từ development historical data và giữ stress worlds ngoài vùng đã fit; vẫn phải prospective evaluate policy.

## 7. Power và pilot có thể thực hiện

### 7.1 Quy mô là constraint, không dùng tuning để vượt qua

Minh họa tính toán mới bằng normal approximation hai tỷ lệ, alpha hai phía 5%, power 80%, độc lập, chưa có adjustment/cluster/missingness:

| Churn control → treatment giả định | Allocation treatment | Tổng sample xấp xỉ |
|---|---:|---:|
| 3,5% → 2,5% | 50% | 9.129 |
| 3,5% → 3,0% | 50% | 39.480 |
| 3,5% → 3,25% | 50% | 163.807 |
| 12% → 10% | 50% | 7.677 |
| 3,5% → 3,0% | 75% | 54.597 |

Công thức dùng `(z_0.975+z_0.8)^2 × [p0(1−p0)/(1−q)+p1(1−p1)/q] / (p0−p1)^2`. Đây là planning examples, không phải power cho một campaign cụ thể; final design dùng binomial/simulation phù hợp và conservative plausible effects.

Nếu chỉ can thiệp 20% cohort và selected effect là 2 điểm %, cohort effect chỉ khoảng 0,4 điểm % khi các điều kiện khác giữ nguyên. Power cho whole-policy A/B không bằng power cho trial trong selected segment. Repeat customer months không cộng như unique accounts; cluster size/ICC làm tăng sample requirement. Non-delivery thường đã làm nhỏ ITT effect, không vừa dùng ITT đã nhỏ vừa giảm effect lần nữa.

Không chọn high-risk segment sau khi xem outcomes để có power đẹp. Một subgroup được xác định trước có thể tăng baseline event rate nhưng đổi population mục tiêu. Nếu doanh nghiệp chỉ có vài nghìn eligible accounts, cần chọn treatment mạnh hơn, horizon phù hợp, phối hợp nhiều waves/sites hoặc chấp nhận inconclusive; không cam kết đo 0,25 điểm % bằng thêm model.

### 7.2 Thiết kế pilot đề xuất khi có partner

**Giai đoạn khám phá có randomization:** khóa một treatment cụ thể so với BAU, stratify theo pre-risk/value/channel, assignment unit account/household, probability được log. Thiết kế allocation/power trước, không mặc định 10% control đủ. Ban đầu ưu tiên 50/50 nếu chi phí và vận hành cho phép; compare alternatives qua E13.

**Giai đoạn so policy:** challenger và incumbent được freeze; randomize account vào policy regime, stratify tương ứng; primary là net margin của toàn eligible cohort ở horizon đã định. Policy phải có cùng envelope về spend/capacity. Phân tích paired OPE trên historical RCT là sàng lọc; prospective policy A/B mới xác nhận giá trị triển khai. Nếu budget chỉ đủ selected-treatment trial thì chỉ claim selected-segment ITT, chưa claim value của whole targeting system.

Outcome: churn60 và complaints30 có thể là leading readouts; margin180 là endpoint dài hạn. Không hoàn tất margin180 trong roadmap 12 tuần. Treatment contact rồi không nhận máy vẫn ở ITT. CUPAC dùng pre-period margin/usage hợp lệ; kiểm soát post-treatment covariates.

Minimum practical gain do finance/ops xác định từ extra engineering/operations cost và risk margin: ví dụ `delta_min = incremental annual run cost / annual eligible accounts`, cùng đơn vị với reward horizon đã quy đổi. Guardrails có non-inferiority margins trước chạy. Không đặt mặc định universal complaint cap 0 hoặc chọn margin sau khi xem outcome.

### 7.3 Continuous experimentation

Mỗi wave: freeze policy → assignment → delivery → mature labels → integrity → fixed protocol evaluation → quyết định. Không tune policy đang được đánh giá giữa wave rồi pool như cùng treatment.

Quyết định tự động trong research chỉ tạo recommendation:

- `INVALID_EVIDENCE`: integrity/identification/support lỗi; điều tra data/design.
- `INCONCLUSIVE`: CI chưa phân biệt được practical delta; báo additional sample/time/cost hoặc dừng nếu không đáng thu thêm.
- `NOT_COST_EFFECTIVE`: upper bound không đạt practical gain khi dữ liệu đủ; dừng phương án trong phạm vi đã kiểm.
- `HARMFUL`: có bằng chứng harm vượt margin; chặn recommendation triển khai.
- `ELIGIBLE_FOR_PILOT`: offline gate đạt; chưa đồng nghĩa production launch.
- `PROMOTE_CANDIDATE`: prospective evidence và guardrails đạt; owner review trước rollout.

No-contact không đương nhiên bằng no-experiment. Có thể tiếp tục randomized learning với budget đã phê duyệt nếu expected value of information đáng chi phí; phải tách exploration cost với exploitation reward.

## 8. Artifact và tiêu chí nghiệm thu khoa học

Mỗi main experiment xuất raw run records, out-of-sample predictions, paired comparison table, event/ESS audit, estimator assumptions, failures và một decision note. Hình cần có: event learning curves; policy value versus budget; coverage/false-launch plot; risk–effect correlation phase map; temporal degradation/recovery; cost-to-evidence frontier.

Các tiêu chí khởi đầu để khóa trong protocol V3:

1. Metric identity/sign/budget fixtures chính xác; zero deliberate leakage missed trong bộ fixtures đã khai báo.
2. Inference validation: nominal 95% coverage và 5% false launch được báo cùng binomial uncertainty; đề xuất gate upper Wilson bound của false-launch ≤7% cho từng canonical null scenario chính với ít nhất 1.000 replications/scenario. Không pool scenario tốt/xấu để che undercoverage; nếu phát biểu đồng thời cho nhiều scenarios phải điều chỉnh uncertainty tương ứng. Đây là engineering tolerance của benchmark, không là định lý bảo đảm thực tế.
3. Challenger cần paired value improvement vượt practical delta trong confirmatory setting, hoặc đáp ứng non-inferiority đã định trước với cost/complexity thấp hơn; không dùng tên model làm lý do promote.
4. Tối thiểu hai real-data domains cho methodological replication, nhưng chỉ real telco prospective data mới chứng minh business telco effectiveness. Orange unresolved phải giữ nhãn conditional.
5. Mọi oracle/PEHE/harm truth giới hạn trong simulation; lợi nhuận thật cần reward/cost thật; live decision cần experiment validity.
6. Những cell/model thất bại, configs loại bỏ và analysis revisions phải được công bố trong run ledger. Không dừng nghiên cứu ngay khi tìm thấy một seed thắng.
