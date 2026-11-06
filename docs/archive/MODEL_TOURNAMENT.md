# Model tournament và component ablation

## Quyết định cần đưa ra

Không hỏi “classifier nào có AUC cao nhất”. Câu hỏi là: trong tập khách hàng high-risk đủ điều kiện của
campaign Orange, score nào xếp hạng được nhóm có `E[Y(0)-Y(1)|X]` lớn nhất, giữ được kết quả qua seed,
evaluator và capacity, rồi có đủ bằng chứng để thay policy đơn giản hơn hay không. `Y=1` là churn; uplift
dương là churn được ngăn. Kết quả chỉ là intention-to-treat trong eligible pool, không ngoại suy ra toàn bộ
thuê bao hay một offer khác.[^orange]

Holdout Orange đã được mở trong benchmark trước. Vì vậy tournament mới chỉ tạo **future challenger** từ
9.516 development rows; nó không được phép đọc 2.380 test rows để chọn lại model.

## Ma trận model và thuật toán con

| Lớp thử nghiệm | Cấu hình chạy | Điều muốn kiểm chứng | Failure mode chính |
|---|---|---|---|
| negative control | random ranking | pipeline có tạo Qini giả hay không | variance làm random có vẻ tốt |
| risk policy | Logistic, RF, HGB, CatBoost | risk có thể proxy response khi outcome/effect tương quan | chọn “sure thing/lost cause” |
| S-learner | Logistic + treatment interactions; HGB | dùng chung response surface có giảm variance | treatment bị model bỏ qua |
| T-learner | Logistic, HGB, CatBoost | hai response surface có bắt heterogeneity | control arm nhỏ làm variance cao |
| transformed outcome | IPW pseudo-outcome + HGB | direct effect target có đủ signal | pseudo-outcome variance lớn |
| DR-learner | common Logistic nuisance + HGB/ExtraTrees effect stage | orthogonal score + nonlinear stage | nuisance/effect overfit |
| R-learner | cross-fitted marginal Logistic + HGB weighted residual stage | residualization cô lập heterogeneity | residual denominator/noise |
| X-learner | Logistic arm models + hai HGB imputation stages | tận dụng treatment/control 75/25 | imputed effect vẫn quá nhiễu |

R-learner dùng objective residualized của Nie và Wager; X-learner theo metalearner framework; DR-learner dùng
cross-fitting để effect stage không học in-sample residual.[^rlearner] [^metalearners] [^drlearner]
CatBoost được giữ như một base learner riêng vì ordered boosting/native categorical processing giải quyết một
failure mode khác one-hot + boosting; nó không mặc nhiên được coi là tốt hơn.[^catboost]

### Component ablation bắt buộc

| Component | Variants | Primary comparison | Quy tắc |
|---|---|---|---|
| nuisance outcome model dùng cho DR evaluation | Logistic one-hot, ordinal-HGB, native-category CatBoost | OOF Brier; Qini của mọi policy dưới từng nuisance | không chọn evaluator làm model ưa thích đẹp hơn |
| representation | all 178; factor-only; PC20+factor; PC40+factor | repeated Qini-DR | one-standard-error, ưu tiên ít feature |
| Logistic regularization | `C={0.01,0.03,0.1,0.3,1,3}` | repeated Qini-DR | preprocessing fit trong fold |
| nonlinear risk learner | RF bagging; HGB; CatBoost ordered boosting | worst-evaluator Qini | cùng outer folds/seeds |
| effect second stage | HGB; ExtraTrees | worst-evaluator Qini | cùng DR pseudo-outcome |
| meta-learner | S/T/TO/DR/R/X | Qini-DR + IPW sign + stability | không chọn theo PEHE vì real counterfactual không biết |
| capacity | 10%, 20%, 30% | uplift, estimated prevented churn, event count | 20% là operational reference, không tune bằng test |
| randomness | 3-repeat screen; 5-repeat confirmation | mean/std/win-rate/paired delta | một seed không đủ để promote |

Không dùng SMOTE cho causal tournament: synthetic resampling có thể làm thay đổi joint distribution
`(X,T,Y)` và estimand. Class weighting chỉ là sub-experiment cho outcome ranking; nuisance probability dùng
cho DR phải được đánh giá bằng Brier/log-loss, không chỉ discrimination.

## Protocol chạy

### Stage A — smoke/negative controls

Chạy `quick` với hai repeats để kiểm schema, sign convention, deterministic tie-break, OOF coverage và random
negative control. Kết quả quick không dùng làm claim.

### Stage B — family screen

Chạy 14 candidates, ba repeats × ba stratified folds. Trong từng repeat:

1. khóa chung folds stratified theo `(t,y)`;
2. fit preprocessing và policy model chỉ trong outer-train;
3. tạo score cho outer-validation đúng một lần;
4. tạo common cross-fitted nuisance predictions trên development;
5. tính normalized Qini/AUUC với DR score, đồng thời tính IPW sensitivity;
6. tính uplift tại 10/20/30%, policy overlap với risk baseline và runtime.

Mọi candidate dùng đúng cùng row/fold/evaluator. Raw OOF score được lưu để kiểm toán. Vì một người chỉ quan sát
một potential outcome, Qini/AUUC trên RCT vẫn có variance đáng kể; regression adjustment/DR được dùng để giảm
variance, còn IPW giữ vai trò kiểm tra độ nhạy.[^evaluation]

### Stage C — component sensitivity

Giữ nguyên OOF policy score rồi thay **common evaluator nuisance** giữa Logistic, HGB và CatBoost. Nuisance
được so bằng factual OOF Brier (primary), log-loss và AP; policy được so bằng minimum mean Qini qua ba
evaluator. Đây là robustness analysis, không phải ba cơ hội để lấy max.

Trong từng component group, winner tạm thời là cấu hình có `max(min_evaluator_Qini)`. Nếu minimum không dương,
kết luận đúng là “không có robust winner”.

### Stage D — tune có giới hạn

Chỉ tune family sống qua screen. Search space phải khóa trước; không mở rộng sau khi thấy kết quả. Với current
data, risk-Logistic có matrix 4 feature sets × 6 `C` × 3 repeats × 3 folds. Chọn cấu hình đơn giản nhất nằm
trong một standard error của mean-best. Hyperparameter tuning không được biến thành hàng trăm phép thử trên
11.896 rare-event rows.

### Stage E — confirmation và promotion

Một challenger chỉ được đề nghị confirmation nếu đồng thời:

- mean Qini-DR và mean Qini-IPW dương;
- Qini-DR dương ở ít nhất 80% repeats;
- uplift@20 dương;
- khi thay risk baseline: paired Qini delta lower 95% CI > 0 và thắng ít nhất 80% repeats;
- không đổi dấu qua ba nuisance evaluators;
- nằm trong compute/latency envelope đã khai báo.

Trong tập eligible, one-standard-error rule chọn model ít phức tạp nhất còn gần mean-best. Sau đó phải chạy
5-repeat confirmation và đánh giá trên **campaign/time holdout mới**. Không model nào, kể cả winner development,
được phép vượt launch gate cũ: DR/IPW lower CI > 0 và đủ churn events trong cả hai arm của selected segment.

## Metric dictionary

| Metric | Vai trò | Không được diễn giải thành |
|---|---|---|
| normalized Qini-DR | primary ranking metric toàn curve | số churn thực sự đã cứu |
| Qini-IPW | estimator sensitivity | metric để cherry-pick |
| uplift@K | effect trung bình estimated trong top K | profit khi chưa có cost/value |
| estimated prevented churn | `selected_n × uplift` | causal truth không uncertainty |
| paired delta/win-rate | bằng chứng thay baseline | độc lập giữa repeats |
| Brier/log-loss nuisance | quality của probability nuisance | CATE quality trực tiếp |
| policy Jaccard | policy thay đổi bao nhiêu | effectiveness |
| runtime | compute feasibility | API p95; tournament là offline |

PEHE chỉ dùng trong synthetic lab nơi biết `true_cate`; không báo PEHE giả trên Orange. Profit chỉ được tính khi
có customer value, contact/offer cost và delivery log; nếu thiếu chỉ báo break-even contact cost.

## Artefact và lệnh chạy

```powershell
# kiểm tra nhanh
python -m telco_churn.model_tournament --profile quick --repeats 2 --folds 2

# tournament đầy đủ và component ablation
python -m telco_churn.model_tournament --profile full --repeats 3 --folds 3
python -m telco_churn.component_ablation --folds 3
```

Artefact chính:

- `tournament_raw.csv`: từng repeat/model, Qini, rank, overlap, runtime;
- `tournament_budgets.csv`: uplift/IPW/DR theo 10/20/30%;
- `tournament_oof_predictions.csv`: row-level audit, development only;
- `tournament_summary.csv` và `tournament_decision.json`: gate và selection;
- `qini_by_evaluator.csv`: policy × nuisance evaluator;
- `nuisance_diagnostics_summary.csv`: AP/Brier/log-loss/DR variance;
- `component_winners.csv` và `component_decision.json`: quyết định cấp component.

## Kết quả tournament đã chạy

Full screen hoàn tất trên 9.516 development rows, 14 candidates × 3 repeats × 3 folds; `test_rows_touched=0`.

| Model | mean Qini-DR ± SD | 95% CI mean | mean Qini-IPW | DR uplift@20 | mean paired Δ vs risk | thắng risk |
|---|---:|---:|---:|---:|---:|---:|
| risk Logistic | 0,002707 ± 0,001025 | [0,000161; 0,005253] | 0,003291 | 0,016328 | 0 | reference |
| risk CatBoost | 0,001427 ± 0,000455 | [0,000295; 0,002558] | 0,001873 | 0,016408 | -0,001280 | 0/3 |
| risk HGB | 0,001379 ± 0,000266 | [0,000719; 0,002040] | 0,001815 | 0,008425 | -0,001328 | 0/3 |
| DR-HGB | 0,001122 ± 0,000797 | [-0,000857; 0,003101] | 0,000560 | 0,014782 | -0,001585 | 0/3 |
| DR-ExtraTrees | 0,000991 ± 0,000176 | [0,000555; 0,001428] | 0,000963 | 0,013710 | -0,001716 | 0/3 |

Risk Logistic đứng hạng 1 ở cả ba repeats. CatBoost tạo uplift@20 point estimate gần như bằng Logistic nhưng
Qini thấp hơn, policy overlap chỉ 0,329 và chi phí OOF khoảng 31,9 giây/repeat so với 0,45 giây của Logistic;
không có bằng chứng để trả chi phí/độ phức tạp thêm. DR-ExtraTrees ổn định hơn DR-HGB nhưng không thắng risk ở
repeat nào. S-HGB đổi dấu giữa DR (-0,000992) và IPW (+0,003843), nên bị loại dù một evaluator trông tốt.

Kết luận được khóa: `development_champion=risk_logistic`, `causal_replacement=none`. Đây không phải kết luận
“risk luôn tốt hơn causal”; nó cho thấy rare outcome, effect nhỏ và 2.886 control rows chưa đủ để learner phức
tạp thắng một proxy ít variance. Kết quả component-evaluator được lưu riêng và phải đọc trước khi xác nhận
challenger.

Component run cho thấy CatBoost là nuisance model tốt nhất theo OOF Brier 0,031173 (HGB 0,031333; Logistic
0,034984). Tuy vậy, Risk-Logistic vẫn có Qini dương dưới cả ba evaluators và worst-evaluator mean 0,002550.
DR-ExtraTrees là causal component tốt nhất theo worst-evaluator rule (0,000720), còn S/T learners không có
robust winner. Nuisance CatBoost và DR-ExtraTrees vì thế là hai component để kiểm tra trên **campaign mới**;
chúng không được ghép lại rồi đánh giá lại trên holdout cũ.

## Stop rules

Dừng tuning khi không có new campaign/temporal holdout, causal challenger không vượt paired gate, estimator
đổi dấu, hoặc observed effect nhỏ hơn độ phân giải của experiment. Khi đó công việc có giá trị nhất là thiết
kế thêm randomized control, log delivery/cost/value và tăng event count — không phải thêm một boosting library.

[^orange]: T. Verhelst et al., *A novel churn uplift modeling dataset from the telecom sector*, 2023, https://arxiv.org/abs/2312.07206 (accessed 2026-09-14).
[^rlearner]: X. Nie and S. Wager, *Quasi-Oracle Estimation of Heterogeneous Treatment Effects*, Econometrica 2021, https://arxiv.org/abs/1712.04912 (accessed 2026-09-14).
[^metalearners]: S. Künzel et al., *Metalearners for estimating heterogeneous treatment effects using machine learning*, PNAS 2019, https://doi.org/10.1073/pnas.1804597116 (accessed 2026-09-14).
[^drlearner]: E. Kennedy, *Towards optimal doubly robust estimation of heterogeneous causal effects*, 2023, https://arxiv.org/abs/2004.14497 (accessed 2026-09-14).
[^catboost]: L. Prokhorenkova et al., *CatBoost: unbiased boosting with categorical features*, NeurIPS 2018, https://proceedings.neurips.cc/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html (accessed 2026-09-14).
[^evaluation]: D. Bokelmann and W. Lessmann, *Improving uplift model evaluation on randomized controlled trial data*, European Journal of Operational Research 2024, https://doi.org/10.1016/j.ejor.2023.07.037 (accessed 2026-09-14).
