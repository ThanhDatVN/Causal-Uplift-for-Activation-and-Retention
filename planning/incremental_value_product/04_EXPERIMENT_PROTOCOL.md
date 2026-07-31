# 04 — Giao thức Thí nghiệm (Experiment Protocol)

File này phải được freeze trước khi final holdout được mở.

## 0. Cổng dữ liệu/đại lượng mục tiêu (Data/Estimand Gates) trước mọi model

Mỗi run phải ghi rõ: unit of analysis, index date, treatment/action, control, outcome, currency,
horizon `H`, discount convention, cost definition, data version/hash và exclusion rule. Không có field
này thì artifact chỉ là exploratory và không được vào README/slide/CV.

- **Criteo:** lưu schema/hash của file thực chạy; không kế thừa row count/feature count của version khác.
- **Online Retail II:** xây `net_revenue` từ transaction theo rule returns đã freeze; `gross_margin_rate`
  nếu dùng phải là scenario input versioned. Report riêng cohort one-time buyers và wholesale sensitivity.
- **Hillstrom:** chọn trước Mens-vs-control hoặc Womens-vs-control. Nếu giữ cả ba arms, dùng model/evaluation
  đa action và report propensity từng arm; không gộp Mens/Womens sau khi nhìn kết quả.

## 1. Giao thức chia tập (Split Protocol)

### Criteo/Hillstrom

- split theo customer row;
- stratify treatment × rare outcome khi cần;
- fixed final holdout;
- model selection chỉ trên train/validation;
- cùng holdout cho mọi model/policy.

### Online Retail II

- calibration period trước, holdout period sau;
- ít nhất 2–3 rolling cutoffs;
- customer xuất hiện lần đầu trong holdout được xử lý/ghi rõ theo model assumption;
- customer lần đầu trong holdout không được đưa vào train-period forecasting metric; report size cohort này;
- không random split transaction.

### Semi-synthetic

- separate seeds cho DGP, split và model;
- final scenario/seed set được freeze;
- report cả average và worst-case scenario.

## 2. Baselines bắt buộc

1. random targeting;
2. highest conversion propensity;
3. highest predicted spend;
4. highest predicted CLV;
5. highest conversion CATE;
6. heuristic `conversion CATE × predicted CLV`;
7. direct incremental value model;
8. oracle policy trên semi-synthetic data.

Không chỉ so causal model với random; predicted CLV và response propensity là business
baselines cần báo cáo.

## 3. Các model ứng viên (Candidate Models)

### CLV

- BG/NBD + Gamma-Gamma fast baseline;
- Bayesian BG/NBD hoặc Pareto/NBD challenger;
- simple historical average/recency-frequency baseline.

### Giá trị nhân quả (Causal Value)

- response/predicted-outcome baseline;
- T-Learner;
- DR-Learner;
- Causal Forest/ForestDR challenger.

Không cần lặp lại toàn bộ lineup causal cũ nếu model không phục vụ monetary policy.

## 4. Thước đo (Metrics)

### CLV xác suất (Probabilistic CLV)

- purchase-count MAE/RMSE/Poisson deviance;
- calibration theo frequency cohort;
- holdout monetary MAE/WAPE;
- Spearman predicted CLV vs realized future value;
- interval coverage nếu có posterior;
- stability qua cutoff.

### Giá trị nhân quả (Causal Value)

- Qini/AUUC cho binary outcome;
- value uplift curve cho monetary outcome;
- incremental net value at top-k;
- uplift calibration by bin;
- bootstrap CI;
- paired bootstrap comparison.

### Bộ ước lượng giá trị chính sách (Policy Value Estimator)

Với policy nhị phân `π(X) ∈ {0,1}`, evaluation set không được dùng để fit policy. Primary estimator
trên RCT là [doubly robust](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/),
dùng propensity randomization đã biết và nuisance models cross-fitted:

```text
V_DR(π) = mean_i[ m̂_{π(X_i)}(X_i)
                 + I(T_i=π(X_i)) / p(T_i|X_i) · (Y_i - m̂_{π(X_i)}(X_i))
                 - cost_i · π(X_i) ]
```

Report cùng lúc direct-method, IPW và DR value; nếu chênh lệch vượt ngưỡng diagnostic đã
xác định, không chọn headline cho đến khi
kiểm tra overlap, outcome calibration và implementation. Với Criteo/Hillstrom, propensity biết từ design
là primary; propensity ước lượng chỉ là ablation/diagnostic.

### Chính sách tác động (Policy)

- doubly robust policy value;
- gain vs random/propensity/predicted CLV;
- policy regret vs oracle trên semi-synthetic;
- net value tại budget 5/10/20/40%;
- top-k Jaccard/Spearman qua seed;
- exclusion rate do predicted net value âm;
- runtime/throughput.

## 5. Ma trận thí nghiệm (Experiment Matrix)

| Axis | Mức |
|---|---|
| Horizon | 14, 30, 90, 180 ngày tùy dataset |
| Cost | low / medium / high |
| Budget | 5%, 10%, 20%, 40% |
| Model | T, DR, forest/challenger |
| Policy | random, propensity, CLV, CATE, direct iCV |
| Robustness | 3 seeds/folds; 2–3 temporal cutoffs |
| Monetary definition | revenue, margin proxy, wholesale-sensitive |

Chạy screening trên sample/validation. Chỉ shortlist được chạy final matrix.

## 6. Semi-synthetic scenarios

| Scenario | Treatment effect |
|---|---|
| Immediate-only | tăng first purchase, không đổi retention |
| Retention | giảm dropout/tăng repeat purchase |
| Margin trade-off | tăng conversion nhưng giảm margin |
| Sleeping dogs | effect âm cho subgroup |
| Heterogeneous cost | voucher cost khác theo treatment/customer |
| No effect | negative control |

Generator phải lưu true `tau(x)`, true policy và oracle value.

## 7. Quy tắc thống kê (Statistical Rules)

- 500 bootstrap resamples cho final headline nếu tài nguyên cho phép.
- Cùng bootstrap indices khi so hai policy/model.
- CI và p-value không thay business effect size.
- Multiple comparisons phải được ghi rõ nếu thử nhiều model/config.
- Báo cáo candidate không đạt gate; không đổi seed sau khi xem kết quả để lựa chọn estimate
  thuận lợi hơn.
- Với RCT, dùng known/randomized propensity làm primary và estimated propensity làm ablation.
- Report arm counts, expected/observed assignment rate, max IPW weight và effective sample size.
- Nuisance fit cho DR evaluation phải được cross-fit hoặc fit trên training data; tuyệt đối không fit outcome
  model trên final holdout rồi tự đánh giá cùng prediction.

## 8. Chọn model/chính sách dẫn đầu (Champion Selection)

Thứ tự:

1. pass data/assumption checks;
2. pass calibration/robustness gates;
3. maximize validation policy net value dưới business constraints;
4. ưu tiên model đơn giản hơn nếu CI overlap;
5. final holdout chỉ dùng xác nhận một lần.

Qini cao nhất không tự động là champion.

## 9. Đầu ra bắt buộc (Required Outputs)

```text
output/final/
  clv_temporal_validation.csv
  causal_value_comparison.csv
  policy_value_comparison.csv
  robustness.csv
  sensitivity.csv
  semisynthetic_regret.csv
  data_manifest.json
  policy_evaluation_audit.json
  customer_scores.parquet
```

Mọi headline trong README/slide/CV phải trỏ được về đúng file và run ID.

## 10. Quy tắc dừng khi gate không đạt (Stop Rules)

- Pareto/Bayesian model không hội tụ hoặc vượt time budget → giữ fast baseline, ghi limitation.
- Direct value model không hơn baseline có ý nghĩa → report negative result, không bỏ baseline.
- Semi-synthetic recovery kém → sửa estimator/DGP test trước khi làm app.
- Real monetary RCT quá ngắn → chỉ claim short-horizon iCV.
- Không đủ long-horizon randomized data: không báo empirical iCLV ngoài observed horizon.
