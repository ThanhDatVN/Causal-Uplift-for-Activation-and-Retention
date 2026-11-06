# Retention experimentation playbook

## Quyết định cần học, không chỉ model cần train

Mỗi experiment phải trả lời một câu có thể bác bỏ:

> Trong eligible population E tại decision time T, assignment offer A có làm giảm churn trong horizon H,
> sau khi trừ contact/offer cost và guardrail harm, so với holdout control không?

Không chạy “A/B test để thu thập thêm data” nếu chưa khóa population, unit, treatment, outcome và quyết
định sẽ thay đổi khi kết quả dương/âm.

## Experiment contract bắt buộc

| Trường | Ví dụ production-ready | Lý do |
|---|---|---|
| Unit randomization | `customer_id`, không phải cuộc gọi | Tránh cùng người vào cả hai arm |
| Eligibility | active, không collections, consent hợp lệ, cooldown 90 ngày | Estimand đúng population có thể hành động |
| Snapshot | 00:00 ngày đầu chu kỳ billing | Feature point-in-time rõ ràng |
| Treatment | được assign vào scripted call + offer ID cụ thể | ITT reproducible; không gộp nhiều hành động mơ hồ |
| Control | business-as-usual, không nhận proactive offer | Counterfactual có nghĩa |
| Primary outcome | churn trong 60 ngày | Khớp thời gian campaign/action |
| Secondary | gross margin 180 ngày, complaint, downgrade, payment default | Không tối ưu churn rồi phá giá trị khác |
| Propensity | probability từ randomization service, log từng decision | Bắt buộc cho IPW/DR/OPE |
| Non-compliance | assigned, contacted, offer accepted đều log riêng | Phân biệt ITT và per-protocol |
| Exclusion | fraud, deceased, legal do-not-contact, open escalation | Safety/operations |
| Stopping | fixed horizon hoặc alpha-spending đã định trước | Không peeking rồi dừng khi đẹp |

## Randomization và interference

1. Randomize sau eligibility và trước call-center queue.
2. Stratify/block tối thiểu theo baseline risk decile, region và value tier; propensity phải được lưu từ
   service, không suy lại từ outcome.
3. Nếu household/account có nhiều subscription, randomize theo household để tránh spillover.
4. Reserve 10–20% persistent control cho monitoring dài hạn; phần exploration mới không được ghi đè.
5. Kiểm tra sample-ratio mismatch ngay sau assignment; balance là diagnostic, không phải cách “sửa” một
   randomizer hỏng.

Field experiment trong telco đã ghi nhận hiệu ứng spillover khi gọi cả bạn bè của likely churner, nên
assumption “mỗi customer độc lập” có thể sai.[^1] Nếu có network/household, thiết kế cluster-RCT hoặc đo
exposure của peers trước khi dùng bootstrap theo row.

## Power trước campaign

Full Orange sample có control churn 3,638%, treatment churn 3,363%, treatment allocation 75,74%.
Với two-sided alpha 0,05 và 80% power:

- MDE hiện tại ≈ 1,112 điểm phần trăm;
- cần khoảng 14.711 observations để detect 1 điểm phần trăm;
- nếu effect thật chỉ bằng 0,275 điểm phần trăm đang quan sát, cần khoảng 194.060 observations.

Đây là xấp xỉ two-proportion test, chưa cộng design effect, attrition, multiple offers hay cluster
randomization. Tính power lại bằng business minimum effect, không dùng effect hậu nghiệm như cam kết.

## Evaluation ladder

### 1. Experiment integrity

- sample-ratio mismatch và duplicate unit;
- treatment propensity đúng config;
- pre-treatment balance, missingness, data availability time;
- contamination/crossover/non-compliance;
- đủ follow-up và không censor khác nhau giữa arm.

### 2. Average effect

`ATE = E[Y(0)-Y(1)]`; báo point estimate, CI và event counts từng arm. Vì `y=churn`, số dương là tốt.
ATE âm hoặc CI rộng qua 0 thì chưa có lý do nhảy thẳng sang segment mining.

### 3. Heterogeneity / ranking

- T-, S-, DR-learner và outcome-risk baseline;
- OOF AUUC/Qini với convention công thức được ghi rõ;
- uplift@K ở capacity đã khóa;
- bootstrap theo randomization unit;
- stability giữa folds/campaign/month, không chỉ mean leaderboard.

Outcome prediction đôi khi đánh bại treatment-effect estimation khi counterfactual data ít, outcome và
effect tương quan hoặc threshold hấp thụ một phần bias; đây là kết quả lý thuyết/thực nghiệm, không phải
lý do mặc định uplift model luôn tốt hơn.[^2] Orange paper cũng thấy Outcome RF 0,26±0,47% AUUC và
T-learner RF 0,25±0,38% trên benchmark của họ.[^3]

### 4. Policy value

Với customer i:

`incremental_value_i = CATE_i × retained_margin_i - contact_cost_i - expected_offer_cost_i`.

Rank theo churn risk hoặc CATE đơn thuần đều có thể sai nếu margin/cost khác nhau. Hai field experiments
trong nghiên cứu profit-based churn cho thấy cần xếp theo incremental impact lên churn và cash flow sau
cost, đồng thời tối ưu campaign size.[^4] Nếu dataset không có margin/cost như Orange, báo break-even:
`max_contact_cost = uplift × value_per_prevented_churn`; không bịa một CLV rồi gọi đó là ROI.

### 5. Guardrails và decision gate

Launch chỉ khi tất cả pass:

- policy/budget đã chọn trên development hoặc campaign trước;
- lower 95% CI của primary incremental outcome > 0;
- IPW và DR cùng dấu, không có estimator disagreement chưa giải thích;
- đủ event count và effective sample size trong selected arm;
- complaint/downgrade/bad-debt không vượt non-inferiority margin;
- expected net value lower bound > 0;
- fairness/contact-frequency/eligibility review pass.

Nếu fail: `NO_LAUNCH`, `CONTINUE_EXPERIMENT`, hoặc `NARROW_ELIGIBILITY`; không đổi threshold trên test.

## Continuous experiment loop

```text
snapshot -> eligibility -> randomized exploration + current policy
         -> assignment log -> delivery/non-compliance log
         -> delayed outcomes -> integrity checks
         -> cross-fitted OPE -> challenger comparison
         -> reviewed promotion / no-launch -> monitoring
```

Mỗi tháng lưu cohort, model/policy version, propensity, budget, offers, costs và outcome availability.
Rolling-origin report phải có:

- ATE/CI theo month và campaign;
- Qini/uplift@K/value/guardrail theo month;
- calibration của outcome nuisance models;
- PSI/category drift và treatment-effect stability;
- policy overlap/effective sample size;
- regret chỉ tính được trên simulation; trên real data dùng honest OPE uncertainty.

## Experiment backlog có thứ tự

| Ưu tiên | Hypothesis có thể bác bỏ | Thiết kế | Primary readout | Kill criterion |
|---:|---|---|---|---|
| P0 | Targeted call có ATE dương trong eligible high-risk pool | RCT call vs BAU | churn 60d ITT | CI lower ≤ 0 sau fixed N |
| P0 | Risk targeting tốt hơn random ở capacity 20% | Policy arms + persistent control | incremental margin | value CI lower ≤ random |
| P1 | CATE policy giảm harmful contacts so với risk | shadow score, rồi policy RCT | complaint + churn effect | harm tăng > margin |
| P1 | Offer amount 1/2/3 tối ưu khác theo value tier | multi-arm blocked RCT | incremental net margin | arm dominated / overlap thấp |
| P1 | 30d surrogate dự báo được 180d treatment effect | longitudinal RCT | policy value 180d | surrogate bias vượt tolerance |
| P2 | Household/network treatment tạo spillover | cluster-RCT | direct + peer churn | interference không nhận diện được |
| P2 | Rolling retrain phục hồi sau price/outage drift | shadow backtest | OOT value + calibration | 3 cửa sổ liên tiếp không cải thiện |

Nghiên cứu gần đây cho thấy long-run CATE trên outcome cộng dồn có thể nhiễu hơn model dùng short-term
surrogate signals, nhưng cần kiểm tra surrogacy thay vì mặc định short-term metric là đủ.[^5]

## Logging schema tối thiểu

```text
decision_id, customer_id_hash, household_id_hash, snapshot_at,
eligibility_version, policy_version, model_version, feature_view_version,
assigned_treatment, propensity, offer_id, contact_cost,
delivered_at, contacted, accepted, actual_offer_cost,
churn_60d, gross_margin_180d, complaint_30d, outcome_available_at
```

Không overwrite assignment khi delivery fail. Không dùng field có `available_at > snapshot_at` làm
feature. Không drop control rows khỏi warehouse sau campaign.

## Tài liệu tham khảo

[^1]: de Matos, Ferreira & Belo, “[Target the Ego or Target the Group: Evidence from a Randomized Experiment in Proactive Churn Management](https://doi.org/10.1287/mksc.2018.1099),” *Marketing Science*, 2018.
[^2]: Fernández-Loría & Provost, “[Causal Classification: Treatment Effect Estimation vs. Outcome Prediction](https://www.jmlr.org/papers/v23/19-480.html),” JMLR 23, 2022.
[^3]: Verhelst et al., “[A churn prediction dataset from the telecom sector](https://arxiv.org/abs/2312.07206),” Tables 4–5.
[^4]: Lemmens & Gupta, “[Managing Churn to Maximize Profits](https://doi.org/10.1287/mksc.2020.1229),” *Marketing Science*, 2020.
[^5]: Huang & Ascarza, “[Doing More with Less: Overcoming Ineffective Long-Term Targeting Using Short-Term Signals](https://doi.org/10.1287/mksc.2022.0379),” *Marketing Science*, 2024.
