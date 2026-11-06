# Benchmark and Experiment Protocol

## Benchmark conclusion

Không có external leaderboard đủ uy tín để đặt một con số “phải đạt” cho IBM Telco sample. Dataset
không phát hành canonical split; public projects khác seed, feature set, missing policy, resampling,
threshold và thậm chí dùng bản 33 cột có leakage. Một AUC lấy từ repo/bài viết khác không phải mốc
so sánh khoa học.

Benchmark chính vì thế là **locked, reproducible internal benchmark**. OpenML 42178 chỉ giúp nhận
diện dataset; Orange KDD Cup 2009 là stretch benchmark độc lập. KDD Cup có protocol và test set rõ,
nhưng dùng 50.000 training examples, 230 hoặc 15.000 biến đã ẩn danh, positive rate churn khoảng
7,3% và chấm ROC-AUC; score của nó không thể so ngang với sample IBM.[^1]

## Câu hỏi thử nghiệm

1. Mô hình có xếp hạng churn tốt hơn logistic đủ lớn để đáng thêm complexity không?
2. Xác suất sau calibration có tốt hơn prevalence predictor và đủ dùng cho cost simulation không?
3. Với contact budget 5%, 10%, 20%, 30%, mô hình bắt được bao nhiêu churners và lift bao nhiêu?
4. Kết quả có ổn định qua fold/seed và qua slice `gender`, `SeniorCitizen`, contract/internet không?
5. Retention policy còn dương trong những cost/uplift assumptions nào?
6. Artifact train và artifact serve có cùng schema/transform/prediction không?

## Frozen data protocol

Sau EDA, tạo `split_manifest.csv` một lần bằng seed `20260913`:

- frozen test: 20% stratified, khoảng 1.409 rows, chỉ mở một lần sau khi khóa model/calibration/policy;
- development: 80%, khoảng 5.634 rows;
- model comparison trên development: RepeatedStratifiedKFold 5 folds × 3 repeats;
- mọi encoder, imputer, resampling (nếu thử), model và calibrator fit trong training fold;
- hash manifest và raw file được log vào MLflow;
- không sửa quyết định vì nhìn thấy test result. Nếu sửa, version thành protocol v2 và test cũ trở
  thành validation, không còn là test.

Giới hạn: không có timestamp nên stratification chỉ là proxy. Với dữ liệu thật, thay bằng out-of-time
split: train các tháng cũ, validation tháng kế, test tháng mới nhất. Google cũng khuyến nghị test trên
dữ liệu sau thời điểm train và đo training-serving skew.[^2]

## Model matrix

| ID | Experiment | Mục tiêu | Không gian thử có giới hạn |
|---|---|---|---|
| E00 | Dummy prior | Calibration/no-skill reference | Constant prevalence; AP reference = test prevalence. |
| E01 | Dummy most-frequent | Chứng minh accuracy trap | Luôn `No`; accuracy xấp xỉ 73,5%, recall churn = 0. |
| E02 | Logistic baseline | Baseline bắt buộc | OHE categorical, standardized numeric, L2; `C` log-uniform. |
| E03 | Logistic sensitive ablation | Governance | So full feature set với bỏ `gender`, `SeniorCitizen`; audit proxy còn lại. |
| E04 | HistGradientBoosting | Main sklearn candidate | Dense OHE in-fold; learning rate, leaves, min samples, L2, iterations. |
| E05 | CatBoost | Main native-cat candidate | Native categoricals; depth, learning rate, L2, iterations. |
| E06 | Class-weight ablation | Imbalance hypothesis | None vs balanced; không mặc định vì có thể làm xác suất lệch. |
| E07 | SMOTE ablation | Educational only | Nếu chạy, đặt trong imblearn Pipeline/fold; không dùng nếu AP/calibration không cải thiện. |
| E08 | Calibration | Reliable probabilities | None vs sigmoid vs isotonic từ OOF development predictions. |
| E09 | Budget policy | Operational value | Top 5/10/20/30%; uniform contact budget và variable-cost scenario. |
| E10 | Explanation/error audit | Trust/debug | Held-out permutation + SHAP nếu champion tree; ≥15 error cases. |
| E11 | Robustness/slices | Risk | Bootstrap CI, seed stability, subgroup calibration/recall/selection. |
| E12 | Serving benchmark | MLE quality | schema parity, p50/p95/p99, throughput, invalid payload, cold/warm. |

CatBoost hỗ trợ categorical features trực tiếp và tài liệu chính thức cảnh báo không one-hot encode
trước CatBoost.[^3] HistGradientBoosting được giữ để có một champion candidate thuần scikit-learn.
Không ensemble nếu single model chưa chứng minh thiếu hụt rõ.

## Metric hierarchy

Scikit-learn nhấn mạnh phải chọn metric từ mục tiêu quyết định và tách dự báo xác suất khỏi quyết
định threshold.[^4]

### Tier 1 — model selection

- **Average Precision (AP)**, đặt tên artifact `average_precision`, là primary. Không ghi mơ hồ
  “PR-AUC”: trapezoidal area và AP khác phép nội suy. AP baseline của constant/random ranking gần
  prevalence 26,54%.
- **ROC-AUC** secondary để đo ranking trên toàn operating range. Không dùng một mình; PR plots hữu
  ích hơn khi positive class ít hơn và tối ưu ROC-AUC không đảm bảo tối ưu PR area.[^5][^6]
- Báo mean, standard deviation và từng fold/seed; không chỉ best run.

### Tier 2 — probability quality

- Brier score (binary range 0–1, lower better).
- Brier Skill Score: `1 - BS_model / BS_prevalence`; phải > 0.
- Log loss.
- Calibration intercept/slope và reliability diagram; ECE chỉ secondary vì phụ thuộc binning.
- Calibrator không được fit trên cùng predictions dùng train base model. Scikit-learn mô tả
  calibrated classifier cần dữ liệu độc lập/CV để tránh biased calibration.[^7]

### Tier 3 — budget decision

Với `N`, budget fraction `b`, `K = ceil(bN)` và top-K theo decision score:

- `Precision@K = TP_topK / K`;
- `Recall@K = TP_topK / all_positives`;
- `Lift@K = Precision@K / prevalence`;
- cumulative gains = `Recall@K` theo budget;
- contacts per captured churner = `K / TP_topK`;
- scenario profit@budget theo cost model đã version.

Top-K là policy chính khi ngân sách là số contact. Probability threshold chỉ dùng khi cost/benefit
cố định và xác suất đã calibration. Threshold/policy chọn trên OOF development predictions, không
trên frozen test. Scikit-learn cũng tách statistical prediction khỏi decision action và cung cấp
threshold tuning bằng CV.[^8]

### Tier 4 — reliability and operations

- 95% paired stratified bootstrap CI (2.000 replicates) cho AP delta, Brier delta, Recall@10% delta;
- slice: n, prevalence, AP, Brier, calibration, Recall@budget, selection rate; không kết luận slice
  có n < 100;
- API: p50/p95/p99 warm latency, cold start, error rate, requests/second, payload sizes 1/100/1.000;
- data drift: schema failures, missing/unknown category rate, PSI/JS divergence secondary;
- delayed performance khi label đủ 30 ngày: AP, Brier, Recall@budget theo cohort thời gian.

## Acceptance gates

Không đặt target AUC tùy ý. Champion chỉ thay logistic nếu:

1. repeated-CV mean AP cải thiện tối thiểu 0,01 absolute **và** không tạo regression Brier > 0,005
   sau calibration; nếu không, logistic thắng nhờ đơn giản;
2. test AP/Brier/Recall@10% được báo với paired CI, kể cả CI chồng lấp;
3. Brier Skill Score > 0 và calibration plot không có lỗi hệ thống rõ;
4. không slice đủ lớn nào có schema failure; chênh lệch slice được công khai, không che;
5. output giống nhau giữa Python batch và Docker API trong tolerance `1e-10`;
6. single-record warm p95 < 100 ms trên hardware/load profile được ghi; 0 lỗi trên 1.000 valid
   requests; invalid enum/range trả 422;
7. one-command run, test/CI xanh, model card và limitations đầy đủ.

Ngưỡng 0,01 và 100 ms là **engineering acceptance criteria của dự án**, không phải industry
standard. Nếu nhu cầu thực khác, SLA phải được thương lượng lại.

## Tuning protocol

- Objective tuning: AP duy nhất; các metric khác được log, không dùng test để trade-off.
- E02: `C ∈ {0,03; 0,1; 0,3; 1; 3; 10}`, L2, class-weight none/balanced, 12 combinations.
- E04/E05: random search 20 candidates mỗi model, giới hạn depth/leaves để phù hợp n=7k.
- Mỗi candidate có seed, package versions, git commit, raw/split hash, wall time và artifact.
- Early stopping validation nằm bên trong training fold; outer validation không dùng dừng cây.
- Sau khi chọn hyperparameters, lấy OOF predictions của development để chọn calibrator/policy;
  refit champion trên toàn development rồi đánh frozen test đúng một lần.

## Explainability and error analysis

Permutation importance trên held-out data là default, dùng scoring AP và lặp ≥30 lần; importance
chỉ có ý nghĩa khi model đã có predictive quality và correlated features có thể chia sẻ importance.[^9]
SHAP dùng bổ sung cho champion tree, kiểm tra additivity và stability qua folds; attribution không là
causal explanation.

Chọn thủ công ≥15 case đã ẩn ID:

- 5 false positives có score cao nhất;
- 5 false negatives có score thấp nhất;
- 5 case gần cutoff budget/cost threshold.

Mỗi case ghi expected/actual, top reasons, data-quality flag, cohort, giả thuyết lỗi, action tiếp theo.

## Business simulation protocol

Với customer `i`:

`EV_i = p_churn_i × assumed_save_rate_i × assumed_margin_at_risk_i - expected_contact_offer_cost_i`

Tối ưu `Σ x_i EV_i`, với `x_i∈{0,1}`, `Σ x_i cost_i ≤ budget`, eligibility constraints, và chỉ chọn
`EV_i > 0`. Nếu cost/value đồng nhất thì top risk tương đương; nếu khác nhau dùng knapsack/ILP.

Chạy ít nhất ba scenario:

| Scenario | Save rate | Gross margin rate | Contact + expected offer cost |
|---|---:|---:|---:|
| Conservative | 5% | 40% | 20 đơn vị tiền |
| Base | 10% | 60% | 15 đơn vị tiền |
| Optimistic | 20% | 70% | 10 đơn vị tiền |

Các số trên chỉ là input giả lập, không phải estimate. Báo sensitivity/break-even, không ghi “revenue
saved”. Churn propensity trả lời “ai có rủi ro”; muốn biết “ai được giữ lại nhờ offer” cần treatment
và control để học uplift. Nghiên cứu retention/uplift cũng phân biệt rõ hai bài toán này.[^10]

## Sources

[^1]: Isabelle Guyon et al., “[Design and Analysis of the KDD Cup 2009](https://www.kdd.org/exploration_files/v11-2-12-KDDCUP09_analysis.pdf),” SIGKDD Explorations 11(2), 2009.
[^2]: Martin Zinkevich, “[Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml),” Google for Developers.
[^3]: CatBoost, “[Categorical features](https://catboost.ai/docs/en/features/categorical-features).”
[^4]: scikit-learn, “[Metrics and scoring: Which scoring function should I use?](https://scikit-learn.org/stable/modules/model_evaluation.html#which-scoring-function-should-i-use).”
[^5]: Takaya Saito and Marc Rehmsmeier, “[The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets](https://doi.org/10.1371/journal.pone.0118432),” PLOS ONE 10(3), 2015.
[^6]: Jesse Davis and Mark Goadrich, “[The Relationship Between Precision-Recall and ROC Curves](https://doi.org/10.1145/1143844.1143874),” ICML, 2006.
[^7]: scikit-learn, “[Probability calibration](https://scikit-learn.org/stable/modules/calibration.html).”
[^8]: scikit-learn, “[Tuning the decision threshold for class prediction](https://scikit-learn.org/stable/modules/classification_threshold.html).”
[^9]: scikit-learn, “[Permutation feature importance](https://scikit-learn.org/stable/modules/permutation_importance.html).”
[^10]: Jeroen Berrevoets et al., “[Why you should stop predicting customer churn and start using uplift models](https://doi.org/10.1016/j.ins.2019.12.075),” Information Sciences 548, 2021.
