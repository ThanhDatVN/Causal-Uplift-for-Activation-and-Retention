# Model Card — TelcoChurn Decision System v1.0.0

> **Current English scope note (2 October 2026):** The archived local champion has SHA-256 `7e14cf28518edf4494ae039fba9a29eea4d11f510946865023c5d6a48746caa7`. The [quick reproduction](../reports/v4/reproduced_quick/RUN_MANIFEST.json) used in the clean setup has SHA-256 `6e408e2beb7c442e93f0473c52a8d63f1a1ac59c24dc807897bb78960f19419d`; the [full reproduction](../reports/v4/reproduced_full/RUN_MANIFEST.json) has `289c7af82c574f23d92fe59d21197b76b6ee860b2b4a7c12fa0caf0de609e896`. Both were produced from source fingerprint `828b3d284469537aed8ea23dfc9912408a386950ac0e69a697dedc125ee79ec5`; later API and research changes do not rewrite those benchmark runs. These bundles carry the legacy version label `1.0.0`, so use the digest to identify the exact artifact. `/v1` retains the historical `risk_30d` name; `/v2` and the planner use `churn_risk_probability` with `horizon_status: unvalidated` because IBM provides no validated 30-day outcome window. The [compatible migration contract](RISK_FIELD_MIGRATION_EN.md) records both versions. Risk ranking is not a treatment-effect estimate. The planner's save rate, margin, cost and value are scenarios, not observed business outcomes. See the [English release guide](PORTFOLIO_RELEASE_2026_EN.md) and [completion plan](REMAINING_GAPS_AND_COMPLETION_PLAN_2026_EN.md).

## Model summary

Model production là Logistic Regression L2 (`C=10`, không class-weight) trong scikit-learn Pipeline:
constant-impute numeric, standardize numeric, most-frequent-impute categorical, one-hot encode với
unknown-category handling, sau đó dự báo xác suất churn. Không thêm post-hoc calibration vì
development OOF Brier của raw Logistic (0,13567) tốt hơn sigmoid (0,13574) và isotonic (0,13587).

CatBoost cho frozen-test AP cao nhất 0,6766, nhưng repeated-CV AP chỉ hơn Logistic 0,0088, thấp hơn
complexity gate 0,01 đã đăng ký trước. Vì vậy Logistic được giữ làm champion; không thay gate sau khi
nhìn test.

| Thuộc tính | Giá trị |
|---|---|
| Artifact version | `1.0.0` |
| Raw data SHA-256 | `16320c9c...e3055e91` |
| Split manifest SHA-256 | `08a34a4e...950630` |
| Split seed | `20260913` |
| Development / frozen test | 5.634 / 1.409 customers |
| MLflow champion run | `4529c3ed6a3e41eeb7ccf97b25e1d7f7` |
| Runtime | Python 3.11.9, scikit-learn 1.7.2, pandas 2.3.3, NumPy 2.4.6 |

Metadata đầy đủ nằm trong `artifacts/models/model_metadata.json`; MLflow tracking dùng local SQLite.

## Intended use

- Monthly decision support cho retention analyst trên một customer snapshot.
- Xếp hạng rủi ro churn và preview danh sách contact theo capacity/expected-value scenario.
- Portfolio demonstration cho leak-free ML, evaluation theo ngân sách, API/batch parity và audit.
- Analyst phải duyệt danh sách; hệ thống không tự gửi offer hay thay đổi giá.

Không dùng model để quyết định credit, employment, insurance, pricing cá nhân, hoặc bất kỳ quyết định
high-impact nào. Không dùng xác suất này như estimate cho một telco thật trước khi thu thập data có
timestamp, point-in-time validation và recalibration trên population đó.

## Data and label

IBM sample có 7.043 rows, 21 raw columns và prevalence churn 26,54%. Model dùng 19 features account,
service, contract và billing; bỏ `customerID` khỏi features. `Churn` được mô tả là khách đã rời trong
tháng gần nhất. IBM repository đã archived và cấp Apache-2.0 cho repository; data card ghi riêng sự
không chắc chắn về provenance/license của CSV.[^1]

11 `TotalCharges` trống đều ở `tenure=0`; chúng được giữ và impute 0 trong pipeline. Dataset không có
timestamp, treatment/control, intervention cost, margin thật, complaint/service-event history hoặc
population sampling design.

## Evaluation protocol

- Frozen stratified test 20%; mọi model/calibration/gate được quyết định bằng development trước khi
  đánh test.
- Hyperparameter search: Logistic 12 combinations; HistGradientBoosting và CatBoost 20 random
  candidates, 5-fold CV, objective AP.
- Stability: RepeatedStratifiedKFold 5×3; báo mean và standard deviation.
- Calibration: OOF none/sigmoid/isotonic; chọn Brier thấp nhất nếu AP không giảm quá 0,005.
- AP primary; ROC-AUC secondary; Brier/log loss cho probability; Recall/Precision/Lift@budget cho
  decision. Scikit-learn phân biệt probability estimation với action threshold và khuyến nghị chọn
  scoring theo mục tiêu ứng dụng.[^2]

Không có canonical split/leaderboard đáng tin cậy cho IBM sample. KDD Cup 2009 churn là stretch
benchmark khác dataset/protocol (50.000 rows, 230/15.000 biến ẩn danh, churn khoảng 7,3%, ROC-AUC),
do đó không so ngang score.[^3]

## Frozen-test results

| Model | CV AP mean ± sd | Test AP | ROC-AUC | Brier | Log loss |
|---|---:|---:|---:|---:|---:|
| Dummy prior | 0,2654 ± 0,0001 | 0,2654 | 0,5000 | 0,1950 | 0,5787 |
| Logistic | 0,6592 ± 0,0243 | 0,6396 | 0,8499 | 0,1345 | 0,4134 |
| Logistic bỏ sensitive fields | 0,6593 ± 0,0248 | 0,6489 | 0,8502 | 0,1344 | 0,4129 |
| HistGradientBoosting | 0,6659 ± 0,0302 | 0,6646 | 0,8547 | 0,1328 | 0,4063 |
| CatBoost | 0,6680 ± 0,0269 | 0,6766 | 0,8557 | 0,1315 | 0,4048 |
| **Production champion: Logistic** | **0,6592 ± 0,0243** | **0,6396** | **0,8499** | **0,1345** | **0,4134** |

Champion Brier Skill Score so với prevalence predictor là 0,3104. Calibration intercept -0,0988,
slope 1,0128 và 10-bin equal-frequency ECE 0,0259 (ECE phụ thuộc cách binning). Bootstrap delta so với Logistic
reference bằng 0 theo định nghĩa vì champion chính là Logistic; bảng vẫn được xuất để protocol có cùng
schema khi champion đổi trong phiên bản sau.

### Capacity outcomes

| Contact budget | Contacts | Captured churners | Precision | Recall | Lift |
|---:|---:|---:|---:|---:|---:|
| 5% | 71 | 56 | 78,9% | 15,0% | 2,97× |
| 10% | 141 | 101 | 71,6% | 27,0% | 2,70× |
| 20% | 282 | 193 | 68,4% | 51,6% | 2,58× |
| 30% | 423 | 250 | 59,1% | 66,8% | 2,23× |

## Slice audit and responsible-use findings

| Slice | n | Prevalence | AP | Brier | Recall at global 10% | Selection rate |
|---|---:|---:|---:|---:|---:|---:|
| Female | 689 | 26,4% | 0,624 | 0,132 | 25,8% | 10,0% |
| Male | 720 | 26,7% | 0,662 | 0,136 | 28,1% | 10,0% |
| SeniorCitizen=0 | 1.187 | 23,8% | 0,648 | 0,124 | 19,9% | 6,3% |
| SeniorCitizen=1 | 222 | 41,4% | 0,657 | 0,189 | 48,9% | 29,7% |

Selection-rate difference theo `SeniorCitizen` rất lớn và đi cùng khác biệt prevalence quan sát; điều
này không chứng minh công bằng hay bất công. Logistic bỏ `gender`/`SeniorCitizen` có CV AP gần như bằng
model đầy đủ và test AP cao hơn trong holdout này. Production thật cần legal/policy review, proxy audit,
calibration theo group, outcome/offer-harm monitoring và cân nhắc bỏ hai features; không dùng chúng làm
reason code.

Các contract/internet slices prevalence thấp có Recall@10%=0 vì global top 10% tập trung vào nhóm rủi
ro cao. Đây là đặc tính của policy capacity, không có nghĩa các churners đó không tồn tại.

## Interpretability and error analysis

Permutation importance được tính 30 lần trên frozen test với scoring AP. Top features là `tenure`
(0,273±0,014), `InternetService` (0,210±0,015), `MonthlyCharges` (0,141±0,017) và `TotalCharges`
(0,058±0,014). Importance là predictive association, không phải causal driver; correlated features có
thể chia sẻ importance.[^4]

`reports/benchmark/error_cases.csv` chứa đúng 15 ID đã hash: 5 high-risk false positives, 5 low-risk
false negatives và 5 records gần budget boundary, kèm giả thuyết điều tra. Static account fields thiếu
complaints, outages, competitor offers và hành vi sau snapshot nên không thể giải thích mọi churn.

## Simulated decision value

Tại capacity 10%: conservative scenario không contact ai vì mọi EV ≤0; base scenario chọn 141/141 với
tổng EV mô phỏng 1.219,46 đơn vị tiền; optimistic scenario là 6.370,40. Đây **không phải revenue saved,
ROI hay uplift đã đo**. Propensity trả lời “ai có rủi ro”; để trả lời “ai được cứu nhờ offer” phải có
treatment/control và học conditional treatment effect.[^5]

## Operational evaluation

- Host batch và FastAPI score parity: absolute delta `0` cho golden record; batch xử lý đủ 7.043 rows.
- Docker image `telcochurn-decision-system:local` build thành công, chạy non-root, readiness pass và
  Docker/host probability delta `0`.
- Local sequential HTTP, 1-record payload, 50 warmups + 1.000 requests: p50 20,24 ms, p95 22,79 ms,
  p99 25,53 ms, 0 errors, khoảng 48,99 requests/s. First request 54,45 ms; payload 100/1.000 records
  mất 25,09/113,57 ms.
- Environment: Windows 10 build 26200, AMD64 Family 25 Model 68. Đây không phải concurrent load test
  hay production SLA.

## Monitoring and retraining requirements

Theo batch cohort: schema failures, missing/unknown category, numeric range, score distribution,
selection/budget utilization và model version. Khi label đủ 30 ngày: AP, Brier, reliability,
Recall@budget và slices. Không auto-retrain chỉ vì drift; điều tra pipeline/data change, chạy challenger
out-of-time và review trước promotion. Rollback bằng immutable previous artifact.

## Limitations

1. Sample nhỏ/fictitious, không đại diện một telco cụ thể.
2. Không có timestamp nên random split có thể lạc quan và không kiểm tra temporal drift.
3. Label semantics chỉ “churn last month”; prediction timeline 30 ngày là product contract chưa được
   xác thực bởi raw events.
4. Không có treatment/control nên decision value chỉ là scenario sensitivity.
5. Slice n nhỏ (đặc biệt 222 seniors); không đủ để certification fairness.
6. Local latency không suy rộng sang cloud/network/concurrent traffic.
7. Serialized pickle/joblib chỉ được load từ trusted artifact store.

## Artifact map

- `reports/benchmark/BENCHMARK_REPORT.md` và CSV/figures: full results, gồm calibration diagnostics.
- `reports/eda/EDA_REPORT.md`: data analysis.
- `notebooks/01_data_audit_eda.ipynb`, `02_leak_free_processing.ipynb`: executed notebooks.
- `artifacts/models/champion.joblib`, `model_metadata.json`: local ignored model artifacts.
- `reports/api/latency.json`: machine-readable latency evidence.
- `data/splits/split_manifest.csv`: frozen assignment.

## Sources

[^1]: IBM, “[Telco customer churn repository](https://github.com/IBM/telco-customer-churn-on-icp4d).”
[^2]: scikit-learn, “[Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html)” and “[Decision threshold](https://scikit-learn.org/stable/modules/classification_threshold.html).”
[^3]: SIGKDD, “[KDD Cup 2009 data](https://www.kdd.org/kdd-cup/view/kdd-cup-2009/Data).”
[^4]: scikit-learn, “[Permutation feature importance](https://scikit-learn.org/stable/modules/permutation_importance.html).”
[^5]: Jeroen Berrevoets et al., “[Why you should stop predicting customer churn and start using uplift models](https://doi.org/10.1016/j.ins.2019.12.075),” Information Sciences 548, 2021.
