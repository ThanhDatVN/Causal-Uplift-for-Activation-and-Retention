# TelcoChurn Decision System — kế hoạch, tiến độ và hướng tiếp theo

**Snapshot:** 2026-09-14  
**Trạng thái quyết định:** predictive API đã chạy được; causal retention policy trên Orange là
`NO_LAUNCH`; chưa có dữ liệu doanh nghiệp để báo ROI thật.

> **Cập nhật 2026-09-20.** Vòng triển khai đầu tiên của V4 đã chạy: problem/time-zero contract,
> label adjudication, paired policy contrast, reward ledger, integrity gates, stage-gated runner,
> bộ falsification E28 và assignment audit của Orange. Tài liệu này giữ nguyên là snapshot V2–V3;
> đọc [V4_IMPLEMENTATION_STATUS.md](V4_IMPLEMENTATION_STATUS.md) cho trạng thái hiện tại và
> [CLAIM_LEDGER_V4.md](../CLAIM_LEDGER_V4.md) để biết dòng nào là `OBSERVED`, `CONDITIONAL` hay
> `PLANNED`. Các kết quả Orange dưới đây vẫn là `CONDITIONAL`: chúng phụ thuộc giả định
> `propensity = treatment.mean()` mà audit phiên 3 đã kiểm.
>
> **Cập nhật 2026-09-21.** Vòng 2 đã chạy: tái hiện các số ở trên, đóng khoảng trống G01–G05 và G07
> bằng test A01–A09/A11/A13, nâng bộ falsification lên 24 mutation, thêm allocator triển khai
> (`telco_churn.allocation`), chỉ mục bằng chứng (`telco_churn.evidence`) và decision console
> (`telco_churn.dashboard`). Chi tiết: [VERIFICATION_V4_1.md](VERIFICATION_V4_1.md).

## 1. Bài toán trong một đoạn

Hệ thống nhận snapshot thông tin có sẵn **trước thời điểm ra quyết định**, ước lượng rủi ro churn và — khi có
dữ liệu campaign randomized — ước lượng churn có thể ngăn bởi từng action. Đầu ra không phải danh sách “khách
rủi ro nhất”, mà là danh sách contact trong capacity/ngân sách, kèm score semantics, uncertainty, expected
prevented churn, break-even cost và lý do `launch/no-launch`. API chỉ score; campaign system mới thực thi action.

## 2. Giá trị đã chứng minh và giá trị chưa được phép claim

### Đã chứng minh bằng artifact

- Pipeline IBM 7.043 rows có frozen split, preprocessing trong fold, Dummy/Logistic/HGB/CatBoost, calibration,
  budget metrics, error cases, permutation importance, API/batch parity và latency.
- Dữ liệu Orange Belgium 11.896 rows là campaign treatment/control thật trong eligible high-risk pool;
  benchmark dùng IPW và cross-fitted DR, không giả treatment từ nhãn churn.[^orange]
- ATE ngăn churn toàn Orange là 0,275 điểm phần trăm, nhưng 95% CI [-0,503; 1,053] điểm phần trăm; MDE ở 80%
  power là 1,112 điểm phần trăm. Với effect quan sát hiện tại cần xấp xỉ 194.060 rows; với effect 1 điểm phần
  trăm cần khoảng 14.711 rows nếu rate/arm allocation giữ nguyên.
- Policy khóa trước là Risk-Logistic @30%. Holdout cho DR uplift 3,331 điểm phần trăm, CI
  [-1,507; 8,269]; IPW uplift 1,076 điểm phần trăm, CI [-3,587; 6,019]; selected control chỉ có 15 churn
  events. Launch gate fail nên quyết định là `NO_LAUNCH`.
- Full model tournament dùng 14 candidates × 3 repeats × 3 folds trên 9.516 development rows, không đọc lại
  holdout. Risk-Logistic đứng hạng 1 cả 3 repeats, mean Qini-DR 0,002707; không model khác thắng risk trong
  bất kỳ repeat nào.
- Component ablation thay nuisance evaluator Logistic/HGB/CatBoost. Risk-Logistic giữ Qini dương dưới cả ba,
  worst-evaluator mean 0,002550. Trong causal families, DR-ExtraTrees là cấu hình ít yếu nhất
  (worst-evaluator mean 0,000720) nhưng paired delta so với risk vẫn âm; nó chỉ là challenger cần dữ liệu mới.
- Synthetic temporal lab có 80.157 customer-month rows để test điều không thể quan sát trên public real data:
  point-in-time leakage, effect drift, harmful contacts, true policy value và oracle regret. Sau drift,
  risk-HGB @20% có true net value -2.813 đơn vị trong khi S-HGB đạt +1.133 ở cùng capacity. Các số này kiểm
  mechanism; không phải ROI telco.

### Chưa được claim

- Không có offer/contact cost, margin/CLV thật nên không báo profit hay ROI.
- Orange không có customer/campaign timestamp công khai nên không chứng minh temporal generalization,
  repeated-customer isolation hay interference.
- Feature Orange đã PCA/ẩn danh nên không gọi importance là “nguyên nhân churn” và không tạo action playbook.
- Không có logged delivery/acceptance nên effect là intention-to-treat, không phải effect của offer đã nhận.
- Predictive API hiện không phải multi-action policy service; chưa nối CRM/campaign executor.

## 3. Tiến độ theo workstream

| Workstream | Trạng thái | Đầu ra kiểm tra được | Điều kiện để gọi hoàn tất |
|---|---|---|---|
| problem/estimand contract | hoàn tất cho public tracks | prediction point, estimand, capacity, cost limitation, gates | cập nhật lại khi có company action/outcome schema |
| IBM data audit + predictive baseline | hoàn tất | EDA, frozen split, benchmark/calibration/budget/error artifacts | không còn việc bắt buộc cho portfolio MVP |
| real Orange causal benchmark | hoàn tất, kết quả no-launch | data card, ATE/power, OOF, locked test, CI/event gates | benchmark tái lập và quyết định không sửa sau test |
| model family tournament | hoàn tất | 14 candidates, 3×3 OOF, paired delta, runtime, budget matrix | mọi model chung fold/evaluator; test touched = 0 |
| algorithm-component ablation | hoàn tất | nuisance Logistic/HGB/CatBoost; HGB/ExtraTrees effect stage; feature/C matrix | có winner/no-winner cho từng component và sign audit |
| repeated confirmation | hoàn tất cho initial families | 5×3 stability; risk thắng 5/5 trong run đã khóa | challenger mới phải chạy confirmation riêng |
| temporal known-truth lab | hoàn tất | leakage tests, drift, PEHE, value/harm/regret, rolling backtest | mechanism tests deterministic và oracle tách khỏi features |
| product serving | một phần | predictive FastAPI, Dockerfile, Postgres schema, batch/API parity, p95 | causal policy bundle/API contract + compose smoke hiện tại |
| monitoring/continuous experiment | một phần | synthetic rolling report và PSI | SRM, propensity/delivery, delayed outcomes, policy value trên event data |
| external validation | chưa làm | mới có dataset plan | ít nhất một temporal predictive và một independent uplift adapter |
| demo/CV evidence | chưa hoàn tất | script demo và bullet draft có số thật | quay demo, archive environment/run ID, không dùng placeholder |

Không gộp bảng này thành một phần trăm duy nhất vì “chạy notebook” và “có prospective business experiment”
không cùng trọng lượng. Research core hiện hoàn tất; business validation chưa bắt đầu vì thiếu governed company
event data.

## 4. Tiến độ theo notebook/pipeline node

| Node | Câu hỏi | Dữ liệu/xử lý | Model/thử nghiệm | Exit gate | Hiện trạng | Việc tiếp theo |
|---:|---|---|---|---|---|---|
| 00 | ai, action gì, outcome/horizon nào? | entity/action/outcome contract | không train | đủ treatment/control/outcome/cost owner | docs xong cho public data | tạo YAML contract khi có schema doanh nghiệp |
| 01 | dữ liệu IBM có dùng được không? | checksum, schema, duplicates, blank `TotalCharges`, cohorts | EDA/effect size | data card + schema tests | executed | freeze; không thêm chart không phục vụ quyết định |
| 02 | risk model nào đáng serve? | fold-local impute/encode, frozen test | Dummy, Logistic, HGB, CatBoost; calibration | AP/Brier/complexity/budget gates | executed | chỉ retrain khi thêm temporal dataset |
| 03 | campaign Orange có signal/power không? | treatment×outcome, balance, joint split | risk/S/T/DR/X, IPW/DR OPE | CI/Qini/events; allow no-launch | executed, `NO_LAUNCH` | không mở lại holdout |
| 04 | policy hỏng thế nào khi drift? | customer-month, churn exit, oracle isolation | risk/S/T/DR/X/value/oracle | temporal validation lower value CI >0 | executed; no-contact được khóa | thêm delivery noncompliance/multi-offer DGP |
| 05 | model và thuật toán con nào ổn định? | common folds/seeds/evaluator; OOF only | 14-family tournament; nuisance/representation/effect ablation | sign agreement, paired delta, one-SE | executed; risk Logistic giữ champion | DR-ExtraTrees chỉ confirm khi có campaign mới |
| 06 | score có tạo value ở capacity không? | fixed score, IPW/DR/raw, cost sensitivity | no-contact/random/oracle comparisons | lower value CI >0 + harm guardrail | executed | thay giả định value bằng margin/cost tables thật |
| 07 | kết quả có chuyển dataset/time không? | UCI/KKBox/Criteo adapters | frozen-model transfer, refit, recalibration | report degradation + domain limits | chưa làm | triển khai theo thứ tự ở mục 7 |
| 08 | artifact có serve an toàn không? | schema/version/golden payload | batch/API/Docker parity | p95, invalid input, reproducible image | predictive xong, causal còn thiếu | thêm `/policy/score` không auto-action |
| 09 | khi nào rollback/retrain? | rolling windows, delayed labels | champion/challenger shadow | SRM/drift/value/guardrails | mock một phần | thiết kế event tables và monitoring jobs |
| 10 | quyết định có audit được không? | claim ledger từ JSON/CSV | không train | mỗi claim trỏ tới artifact/run | docs phần lớn xong | tạo executive notebook + demo video |

## 5. Model/algorithm selection đã chạy

### Family screen

| Candidate | Mean Qini-DR | Mean Qini-IPW | DR uplift@20 | Paired Δ vs risk | Kết luận |
|---|---:|---:|---:|---:|---|
| Risk-Logistic | 0,002707 | 0,003291 | 0,016328 | reference | development champion |
| Risk-CatBoost | 0,001427 | 0,001873 | 0,016408 | -0,001280 | không trả được thêm complexity/runtime |
| Risk-HGB | 0,001379 | 0,001815 | 0,008425 | -0,001328 | không thắng baseline |
| DR-HGB | 0,001122 | 0,000560 | 0,014782 | -0,001585 | giữ sign nhưng CI/rank yếu |
| DR-ExtraTrees | 0,000991 | 0,000963 | 0,013710 | -0,001716 | causal component challenger, chưa thay baseline |
| TO-HGB | 0,000639 | 0,001351 | 0,010270 | -0,002068 | chỉ dương 2/3 repeats |
| S-Logistic | 0,000427 | -0,000505 | 0,007412 | -0,002280 | DR/IPW khác dấu |
| R-HGB | 0,000021 | -0,000440 | -0,000792 | -0,002686 | reject |
| T-Logistic/HGB/CatBoost | ≤ -0,000029 | âm | point estimate nhỏ | âm | reject |
| X-HGB | -0,000479 | -0,001146 | 0,000745 | -0,003186 | giả thuyết lợi từ 75/25 bị bác bỏ |
| S-HGB | -0,000992 | +0,003843 | -0,005129 | -0,003699 | estimator disagreement; reject |

### Thuật toán con

| Component | Kết quả | Quyết định |
|---|---|---|
| DR nuisance Logistic | OOF Brier 0,034984; AP 0,126321 | không còn là nuisance choice tốt nhất |
| DR nuisance HGB | OOF Brier 0,031333; AP 0,148662 | tốt hơn Logistic, sát CatBoost |
| DR nuisance CatBoost | OOF Brier 0,031173; AP 0,149259 | nuisance winner theo Brier; future evaluator config |
| Risk base learner | Risk-Logistic worst-evaluator Qini 0,002550 | retain |
| S base learner | best worst-evaluator Qini -0,000686 | không có robust winner |
| T base learner | best worst-evaluator Qini -0,000743 | không có robust winner |
| DR effect stage | ExtraTrees worst-evaluator Qini 0,000720 | thắng DR-HGB ở robustness, chỉ confirm challenger |
| Logistic feature/C | mean-best all-178/C=3; one-SE all-178/C=0,3 | giữ C=0,3; feature compression không thắng |

CatBoost nuisance thắng Brier nhưng không được dùng để sửa kết quả locked test. Kết quả đó định nghĩa cấu hình
evaluator cho **campaign tiếp theo**. Đây là ranh giới chống test leakage.

## 6. Definition of Done cho portfolio

### Research package — đã đạt

- raw source/checksum/license và data card;
- deterministic split manifest và leakage boundary;
- negative control, baseline, nonlinear và causal families;
- OOF predictions, repeated stability, tuning/ablation và rejected-config log;
- DR/IPW uncertainty, power/MDE, event-count và no-launch gates;
- temporal known-truth failure lab;
- notebook gọi package/artifact thay vì có training logic riêng;
- unit/integration tests và one-command research script.

### Portfolio release — còn thiếu

- notebook 07–10 hoặc report tương đương được execute;
- causal policy endpoint/batch output có `policy_version`, `eligible`, `score`, `selected`, `reason`,
  `decision=shadow/no-launch`;
- Docker Compose smoke lại khi daemon chạy;
- demo video 4–6 phút: IBM risk → Orange effect/power → tournament rejection → temporal failure → no-launch;
- release tag, environment lock/hash và archived run summary;
- CV bullet chỉ lấy số từ artifact, kèm câu “business impact simulated”.

### Production/business release — cần dữ liệu mới

- point-in-time customer snapshot và stable customer/account IDs;
- campaign/action/offer assignment, known propensity, eligibility và randomization unit;
- attempted contact, delivered treatment, acceptance, channel và contact timestamp;
- churn definition/horizon, label maturity timestamp và censoring;
- offer/contact cost, margin/CLV horizon và guardrail outcomes;
- campaign/time/customer split, SRM check và đủ event count/power;
- prospective shadow/A-B run; lower 95% policy-value CI > 0 trước rollout.

## 7. Hướng tiếp theo theo thứ tự

### P0 — đóng gói release hiện tại (1–2 ngày)

**Công việc:** notebook 03–06 đã execute lại; 28 pytest và Ruff đã pass. Phần còn lại là compose smoke khi
Docker daemon hoạt động, executive claim ledger và demo video.  
**Đầu ra:** notebook không lỗi, test log, Docker log, `10_executive_decision_report.ipynb`, video/link.  
**Exit:** mọi số trong README/CV truy được tới CSV/JSON; không còn placeholder.

### P1 — external validation có mục đích (3–5 ngày)

1. **UCI Iranian Churn:** dùng 9 tháng feature, target ở cuối tháng 12; đánh giá planning gap 3 tháng, frozen
   Logistic transfer/refit/recalibration. Dataset có 3.150 rows/13 features và không missing.[^uci]
2. **Criteo uplift:** dùng sample/tier được ghi checksum để kiểm rare-event scale và DR/IPW implementation,
   không gọi đây là telco validation. Public dataset có gần 14 triệu randomized samples.[^criteo]
3. **KKBox** chỉ làm khi terms/download được chấp nhận; mục tiêu là transaction-log temporal feature building,
   không so metric trực tiếp với IBM/Orange.

**Exit:** mỗi adapter có unit/time/treatment/outcome/license; báo transfer degradation, không chỉ score sau refit.

### P2 — realistic event-data mock (4–6 ngày)

Tạo relational generator thay vì một bảng phẳng: `customers`, `subscriptions`, `usage_daily`, `billing`,
`network_events`, `campaign_eligibility`, `assignments`, `contacts`, `offers`, `deliveries`, `outcomes`,
`customer_value`. Generator phải có late-arriving data, noncompliance, repeated customers, multi-arm offers,
censoring, channel capacity, contact cost, margin và effect drift.

**Thử nghiệm bắt buộc:** snapshot join đúng `event_at <= decision_at`; customer-group/time split; ITT primary;
delivery-adjusted sensitivity; multi-action value policy; capacity theo channel; true regret/harm.  
**Exit:** một test cố ý dùng future aggregate phải fail; risk policy phải thua value policy trong ít nhất một
predeclared regime và thắng trong một regime khác để tránh generator thiên vị một method.

### P3 — multi-action/value policy (5–8 ngày)

Actions: no-contact, call-only, small discount, large discount. Fit outcome/action response, rồi chọn
`argmax_a E[value(a)-cost(a)|X]` dưới budget/channel constraints. So one-vs-control T/DR learners, direct
policy learning và conservative no-contact. Marketing treatment cần đánh giá bằng incremental value chứ không
chỉ Qini nếu action costs khác nhau.[^value]

**Gate:** overlap/effective sample size cho mỗi action; cross-fitted DR value; customer-cluster CI; harm và
discount-spend guardrails; lower 95% incremental net-value CI > 0.

### P4 — prospective campaign design (phụ thuộc doanh nghiệp)

Giữ control thay vì chỉ contact top-risk. Với giả định Orange hiện tại, target tối thiểu khoảng 14.711 eligible
rows để có 80% power cho 1 điểm phần trăm ATE; effect 0,275 điểm phần trăm cần khoảng 194 nghìn. Recompute bằng
rate/cost/capacity thật, có allowance cho non-delivery và repeated-customer clustering.

**Pre-launch checks:** randomization unit, SRM, propensity, offer inventory, delivery rate, sample ratio theo
strata, label maturity.  
**Decision:** promote chỉ khi policy value lower CI > 0, guardrails pass và selected segment đủ events; nếu
không, `continue exploration` hoặc `no-launch`, không đổi metric sau khi xem kết quả.

### P5 — serving/monitoring (sau P2/P3)

Thêm batch-first causal scoring; API chỉ dùng preview/debug. Mỗi decision log phải lưu feature snapshot hash,
model/policy version, eligibility, candidate scores, selected action, propensity và reason code. Monitor SRM,
delivery, feature/score/selection drift, delayed calibration, ATE/IPW/DR/value theo rolling campaign và
capacity utilization. Rollback về no-contact khi guardrail fail hoặc value lower bound âm.

## 8. Lệnh tái lập và artifact đầu mối

```powershell
# toàn bộ research track
powershell -ExecutionPolicy Bypass -File scripts/run_research.ps1 -SkipInstall

# vòng nhanh để kiểm thay đổi code
powershell -ExecutionPolicy Bypass -File scripts/run_research.ps1 -Quick -SkipInstall

# riêng model/algorithm tournament
python -m telco_churn.model_tournament --profile full --repeats 3 --folds 3
python -m telco_churn.component_ablation --folds 3
```

Đọc theo thứ tự:

1. `reports/uplift/locked_policy_decision.json` — quyết định real-data đã khóa;
2. `reports/uplift/tournament/tournament_decision.json` — model screen;
3. `reports/uplift/component_ablation/component_decision.json` — thuật toán con;
4. `reports/temporal_lab/summary.json` — drift/value mechanism;
5. `docs/archive/MODEL_TOURNAMENT.md` — protocol và metric dictionary;
6. `docs/archive/NOTEBOOK_PIPELINE.md` — trách nhiệm từng notebook.

## 9. Kiểm tra ở snapshot này

- `python -m ruff check .`: pass;
- `python -m pytest -q`: 28 pass, còn hai deprecation warnings từ FastAPI/Starlette test client;
- notebook 01–06: lần lượt 8/6/9/10/9/7 code cells đã execute, 0 error outputs;
- tournament và component ablation: `test_rows_touched=0`;
- Docker Compose: chưa smoke lại vì Docker Desktop daemon không chạy (`dockerDesktopLinuxEngine` pipe không
  tồn tại). Mục này giữ trạng thái chưa xác minh, không ghi thành pass.

## 10. Tài liệu nguồn

[^orange]: T. Verhelst et al., *A novel churn uplift modeling dataset from the telecom sector*, 2023, https://arxiv.org/abs/2312.07206 (accessed 2026-09-14).
[^uci]: UCI Machine Learning Repository, *Iranian Churn Dataset*, https://archive.ics.uci.edu/dataset/563/iranian%2Bchurn%2Bdataset (accessed 2026-09-14).
[^criteo]: Criteo AI Lab, *Uplift Prediction Dataset*, https://ailab.criteo.com/criteo-uplift-prediction-dataset/ (accessed 2026-09-14).
[^value]: J. Gubela and S. Lessmann, *Uplift modeling with value-driven evaluation metrics*, Decision Support Systems 2021, https://doi.org/10.1016/j.dss.2021.113648 (accessed 2026-09-14).
