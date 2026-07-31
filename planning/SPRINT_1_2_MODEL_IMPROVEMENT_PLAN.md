# Kế hoạch cải tiến Sprint 1–2: mô hình uplift, đánh giá và policy

**Tên đề tài:** Đo lường tác động tăng thêm và tối ưu nhắm mục tiêu marketing
(*Causal Uplift Measurement and Policy Optimization*)
**Ngày chốt research:** 31/07/2026
**Phạm vi:** cải tiến sản phẩm causal hiện tại; chưa mở bài toán Giá trị vòng đời khách
hàng tăng thêm (*Incremental Customer Lifetime Value*)
**Điều kiện:** laptop 6 CPU vật lý/12 luồng, RAM 15,19 GB, GPU RTX 3050 4 GB; Kaggle
Free là compute phụ; Colab Pro chỉ là phương án cuối có điều kiện.

Tài liệu này là kế hoạch tương lai. Các con số đã chạy nằm trong
`report/SPRINT_1_FINAL_REPORT.md` và `report/SPRINT_2_FINAL_REPORT.md`.

## 1. “Model tốt nhất” được hiểu như thế nào?

Không thể quan sát đồng thời \(Y(1)\) và \(Y(0)\) của từng khách hàng, nên không có một
test RMSE CATE cá nhân trực tiếp để tìm “model tốt nhất”. Trong dự án này, một model chỉ
được coi là tốt hơn khi đồng thời:

1. tạo policy có **giá trị tăng thêm ngoài mẫu** tốt hơn tại nhiều mức ngân sách;
2. cải thiện có độ ổn định qua split/seed và có paired confidence interval;
3. không đổi kết luận khi thay một metric ranking bằng metric có căn cứ khác;
4. không dùng confirmation để tune;
5. chạy được trong giới hạn RAM/thời gian và có thể tái lập;
6. giữ đúng estimand, không dùng `visit` hoặc `exposure` làm feature.

Mục tiêu không phải đẩy riêng Qini lên cao bằng cách thử nhiều cấu hình trên cùng test.
Mục tiêu là tạo bằng chứng đủ chặt để giữ hoặc thay champion.

## 2. Điểm xuất phát đã có

### 2.1 Dữ liệu

- Criteo v2.1: 13.979.592 dòng, 12 feature ẩn danh, treatment nhị phân.
- Treatment/control: khoảng 85%/15%.
- Conversion: 40.774 positive trên toàn bộ dữ liệu; trong đó control chỉ có 4.063.
- Conversion rate: 0,2917%; đây là bài toán outcome rất hiếm.
- Dataset public đã được Criteo subsample không đồng đều vì riêng tư. Estimand hiện tại là
  trên benchmark public, không phải incrementality có thể suy ngược về campaign gốc.
- `exposure` mô tả tiếp xúc thực tế sau assignment; `visit` và `exposure` đều bị loại khỏi
  feature set.

Hệ quả thực hành: smoke test 0,1–1% chỉ kiểm tra code path. Nó có quá ít conversion,
đặc biệt ở control, nên không được dùng để chọn model.

### 2.2 Baseline và release

- Sprint 1: Response, S-, T-, X- và DR-Learner; multi-seed validation; final holdout chung.
- Sprint 2: Response, X-Renormalized, X-Calibrated, T-LocalExact; policy IPW/DR;
  dashboard self-contained.
- Champion hiện tại: Response top-k, được chọn trên validation.
- X-Renormalized có Qini confirmation cao hơn Response nhưng paired 95% CI của chênh
  lệch chứa 0; chưa đủ căn cứ thay champion.
- Causal Forest research profile đã đo đến 20%; local 50% không khả thi với RAM hiện có.

### 2.3 Các khoảng trống cần xử lý trước khi thêm model

1. Confirmation Sprint 2 đã được xem và báo cáo. Nó không còn là test “chưa quan sát” cho
   vòng cải tiến mới.
2. Qini/AUUC hiện là metric chính nhưng nghiên cứu 2024–2025 đã chỉ ra cần đánh giá thêm
   RATE/AUTOC, outcome-adjusted evaluation, pROCini hoặc PUC.
3. Random top-k hiện dùng một seed; CI có điều kiện trên ranking đó, chưa phản ánh biến
   thiên qua nhiều random policy.
4. Chưa có R-Learner/NonParamDML, ForestDRLearner và causal ensemble có selection loss
   phù hợp.
5. Chưa có experiment registry thống nhất cho model, split hash, runtime, RAM và metric.
6. Criteo có feature ẩn danh nên không thể tạo câu chuyện nguyên nhân theo tên biến; phần
   giải thích chỉ được nói về pattern trên feature đã ẩn danh.

## 3. Protocol mới trước khi chạy bất kỳ challenger nào

### 3.1 Phân vai dữ liệu

| Tập | Cách dùng từ vòng cải tiến | Điều cấm |
|---|---|---|
| Sprint 2 `fit + validation` | Development pool; tạo out-of-fold prediction bằng cross-fitting | Không chấm in-sample |
| Sprint 2 `confirmation` | Retrospective confirmation sau khi khóa shortlist | Không tune, không đổi rule sau khi xem |
| Sprint 1 final test | Historical evidence | Không tái dùng để chọn model mới |
| Hillstrom hoặc campaign RCT mới | External validity/portfolio evidence | Không trộn với Criteo rồi gọi là cùng estimand |

Tạo 3-fold cross-fitting trên development pool. Mỗi dòng chỉ được chấm bởi model không fit
trên dòng đó. Chạy thêm seed thứ hai cho finalist; seed thứ ba chỉ khi hai seed đầu cho kết
luận khác nhau. Cách này dùng dữ liệu development hiệu quả hơn một validation split cố định
mà vẫn giữ out-of-fold evaluation.

Vì confirmation cũ đã được xem, kết quả mới trên nó phải ghi là **retrospective
confirmation**, không gọi là prospective/unseen test. Muốn có bằng chứng hoàn toàn mới cần
một randomized campaign log mới hoặc external randomized dataset.

### 3.2 Estimand và propensity

\[
\tau(x)=E[Y(1)-Y(0)\mid X=x]
\]

- Outcome chính: `conversion`.
- Treatment: assignment quảng cáo của benchmark.
- Propensity dùng hằng số assignment của benchmark 0,85 trong primary run; dùng tỷ lệ fit-fold trong
  sensitivity run. Không fit propensity phức tạp từ \(X\) làm mặc định cho RCT.
- Policy chỉ dùng feature trước treatment.
- Cost/value giả định không tham gia chọn model chính vì Criteo không có monetary outcome.

### 3.3 Metric hierarchy đã đăng ký trước

**Primary selection metric**

Diện tích dưới đường **DR gross policy value theo budget 1–30%**, ưu tiên vùng
5–20%. Đây là trung bình conversion tăng thêm trên toàn population, không gắn tiền giả.

**Secondary evidence**

- RATE/AUTOC (*Rank-Weighted Average Treatment Effect / Area Under the TOC*);
- pROCini và PUC cho binary outcome;
- Qini và AUUC hiện tại để giữ khả năng so sánh lịch sử;
- R-score hoặc doubly robust risk để chọn/ensemble CATE;
- EUCE/calibration curve chỉ cho score có scale CATE;
- outcome log loss/Brier theo arm để kiểm tra nuisance model.

**Policy evidence**

- Treat-none.
- Expected random targeting: dùng stochastic policy \(\pi(x)=b\), không chỉ một random
  ranking.
- 20 random-ranking seed là sensitivity check, không phải 20 lần chọn kết quả tốt nhất.
- Response top-k champion và các challenger.
- Paired bootstrap hoặc influence-function inference trên cùng OOF/confirmation rows.

Không chọn champion theo AUC dự báo conversion, Qini riêng lẻ, hoặc CI riêng của từng model.
So sánh phải dùng CI của **chênh lệch paired**.

## 4. Danh mục phương pháp theo mức ưu tiên

### P0 — phải làm, phù hợp laptop

| ID | Phương pháp | Lý do | Thử nghiệm tối thiểu |
|---|---|---|---|
| EVAL-01 | RATE/AUTOC + DR policy curve | Đo trực tiếp chất lượng prioritization | synthetic truth test, OOF, paired CI |
| EVAL-02 | Outcome-adjusted uplift evaluation | Nghiên cứu EJOR 2024 đề xuất giảm variance metric trên RCT | đối chiếu raw vs adjusted trên cùng predictions |
| EVAL-03 | pROCini và PUC | Qini có thể bỏ phí thông tin binary negative | cross-check implementation với code/paper gốc |
| M-R | R-Learner qua `NonParamDML` | Orthogonal loss, phù hợp RCT và base learner linh hoạt | constant propensity, 3-fold, LightGBM final |
| M-DR | DR-Learner cải tiến | Model hiện tại chưa thử binary nuisance, MC cross-fit và final learner có kiểm soát | `discrete_outcome` A/B; `mc_iters=2`; 2 final learners |
| M-META | S/T/X ablation có kiểm soát | Outcome hiếm và arm lệch; giữ baseline nhưng sửa từng yếu tố | classifier vs regressor; raw vs k=7; fixed propensity |
| ENS-Q | Causal Q-Aggregation | Selection/ensemble bằng doubly robust loss thay vì lấy model cao nhất một metric | ensemble shortlist OOF, weights freeze |

Giới hạn search space trước khi chạy:

- LightGBM: tối đa 8 cấu hình/base learner ở screening; chỉ thay đổi
  `num_leaves`, `min_child_samples`, learning rate/trees, L1/L2 và subsampling.
- DR: tối đa 2 nuisance option × 2 final option × 2 `mc_iters`.
- R: tối đa 4 final-model cấu hình.
- Mỗi thay đổi phải có một giả thuyết: giảm variance, cải thiện rare-outcome nuisance,
  hoặc tăng khả năng học heterogeneity.

### P1 — chạy có gate trên Kaggle CPU/RAM

| ID | Phương pháp | Vai trò | Gate |
|---|---|---|---|
| M-CF | CausalForestDML | Honest forest + DML residualization | 20% → 30% → tối đa 50% |
| M-FDR | ForestDRLearner | Honest forest ở final stage của DR-Learner | smoke 1%, benchmark 10%, chỉ lên 20–30% nếu có tín hiệu |
| AUTO | AutoCATE reproduction | Kiểm tra pipeline search/ensemble 2025 | chỉ 1–5% để hiểu protocol; không full-search mù |

GPU không tăng tốc trực tiếp cho EconML CausalForestDML. Với hai forest trên, chọn Kaggle
vì CPU/RAM runtime chứ không vì nhãn “GPU”.

### P2 — research challenger, chỉ chạy nếu P0 hoàn tất

| ID | Phương pháp | Khi nào đáng thử | Lý do không ưu tiên trước |
|---|---|---|---|
| M-PTONET | PTONet/PUL (ICML 2025) | PUC implementation đã kiểm chứng; có GPU session | code/deep tuning phức tạp, rare outcome, chỉ 12 feature tabular |
| M-LTR | LambdaMART/PCG direct ranking | Product chỉ cần top-k và metric PUC/RATE đã ổn | paper báo top-k optimization không generalize ở test trong thí nghiệm đó |
| M-TAR | TARNet/DragonNet | cần một neural benchmark cho AI Engineer portfolio | representation balancing ít có lợi thế rõ trên RCT constant propensity |

Các model deep chỉ được promote nếu thắng P0 trên OOF qua ít nhất hai seed, không chỉ vì
mới hơn.

### Đã research nhưng không áp dụng cho Criteo hiện tại

- **Heteroscedasticity-aware stratified sampling (2025):** hữu ích khi thiết kế/chọn người
  tham gia RCT mới; không được dùng như thủ thuật post-hoc để thay sampling design của
  benchmark đã cố định.
- **Uplift with delayed feedback (AAAI 2026):** cần thời gian phản hồi/censoring; Criteo
  v2.1 không có event time hoặc observation horizon.
- **Continuous-treatment uplift (2026):** không đúng treatment nhị phân hiện tại.
- SMOTE trên outcome hoặc class weights không hiệu chỉnh: có thể phá probability scale và
  treatment contrast; không dùng làm default.
- Bayesian Causal Forest full 14 triệu dòng: không phù hợp ngân sách compute.

## 5. Ma trận thực nghiệm

### Giai đoạn A — nâng evaluation trước model

1. Viết synthetic data generator có ground-truth CATE và rare outcome gần Criteo.
2. Implement RATE/AUTOC, expected-random policy, multi-seed random sensitivity.
3. Reproduce pROCini/PUC bằng test nhỏ từ paper/code gốc.
4. Implement outcome-adjusted Qini/RATE theo công thức paper EJOR 2024.
5. Kiểm tra metric invariance, tie handling, binary edge cases và paired resampling.

**Điều kiện đạt:** metric mới pass synthetic truth, không NaN ở valid rare-outcome sample,
và có test đối chiếu nguồn độc lập.

### Giai đoạn B — functional smoke

- Fraction: 0,1–1%.
- Mục tiêu: import, fit, predict, finite score, artifact schema, peak RAM.
- Không ghi “model tốt/xấu” từ kết quả này.

### Giai đoạn C — screening

- Dùng tối thiểu 10% development pool hoặc ngưỡng số positive control đã đăng ký.
- Chạy P0 với cùng fold/seed.
- Early stop candidate nếu:
  - score gần hằng số hoặc không hữu hạn;
  - nuisance calibration hỏng rõ;
  - bị Response và current X-Learner dominate ở mọi budget 5–20%;
  - runtime/RAM vượt gate mà không có tín hiệu metric.

### Giai đoạn D — full development OOF

- Chỉ 3–5 finalist.
- 3-fold OOF, seed 1; finalist sát nhau chạy seed 2.
- Tính primary policy-area, AUTOC, pROCini/PUC, Qini, calibration và resource.
- Fit causal Q-aggregation chỉ bằng OOF predictions/nuisance đúng split.
- Khóa code, config, package version, split hash và selection rule.

### Giai đoạn E — retrospective confirmation

Chạy đúng một lần sau khi freeze:

- paired difference so với Response và X-Renormalized;
- 95% CI primary policy-area và AUTOC;
- sensitivity theo budget;
- không thêm hyperparameter sau khi xem.

Quy tắc thay champion:

1. primary OOF policy-area thắng ở ít nhất hai seed;
2. confirmation point estimate cùng dấu;
3. paired 95% CI của primary difference có lower bound > 0;
4. không có regression nghiêm trọng về runtime, calibration/validity hoặc guardrail.

Nếu CI chứa 0, giữ champion đơn giản hơn và phát hành challenger/uncertainty; không viết
“model mới tốt hơn”.

### Giai đoạn F — external evidence

Hillstrom có randomized email campaign và outcome visit/conversion/spend, nhưng quy mô nhỏ
và khác domain. Dùng nó để kiểm tra pipeline portability, không gộp metric với Criteo. Giá
trị nhất cho portfolio là chứng minh cùng protocol chạy trên dataset thứ hai và mô tả đúng
khác biệt estimand.

## 6. Gate hạ tầng

### Laptop

- P0 mặc định dùng `float32`, giới hạn thread theo benchmark, giải phóng model giữa run.
- Full Sprint 2 đã đo peak process RSS 2,74 GB; đây là bằng chứng cho pipeline hiện tại,
  không phải bảo đảm cho model mới.
- Dừng/giảm fraction nếu process + system use vượt 75% RAM hoặc available RAM dưới 2 GB.
- Không chạy song song nhiều full-data model.

### Kaggle Free

Tài nguyên dịch vụ có thể thay đổi; luôn in `psutil.virtual_memory()`, CPU count, disk và
elapsed time ngay đầu notebook.

Với Causal Forest:

1. `kaggle-safe`, 200 trees, CV=2, `max_samples=0.25`, `inference=False`;
2. chạy 20%; tiếp tục khi peak RAM <75% runtime RAM và còn đủ thời gian;
3. chạy 30%; đánh giá lại cùng gate;
4. chỉ thử 50% nếu 30% pass và dự báo bảo thủ còn margin;
5. nếu fail, phát hành learning curve 20–30%; không đổi holdout để ép model chạy.

Benchmark research profile hiện có:

| Fraction | Wall time local | Peak RSS |
|---:|---:|---:|
| 1% | 126 giây | 2,10 GB |
| 5% | 528 giây | 3,11 GB |
| 10% | 1.052 giây | 4,80 GB |
| 20% | 2.200 giây | 8,16 GB |

Ngoại suy research profile 50% là 17,5 GB linear và envelope bảo thủ 24 GB; laptop
15,19 GB không đủ. Đây là ngoại suy, không phải runtime đã đo.

### Colab Pro

Chỉ cân nhắc khi:

- PTONet/deep candidate đã thắng screening trên Kaggle/local;
- GPU/RAM là blocker đã đo, không phải giả định;
- estimated remaining compute nhỏ hơn ngân sách mua;
- checkpoint/resume đã sẵn sàng.

Không mua Colab Pro chỉ để chạy CausalForestDML vì model đó chủ yếu dùng CPU/system RAM.
Google công bố resource/usage limit của Colab thay đổi theo thời điểm; không ghi một cấu
hình RAM/GPU cố định vào plan.

## 7. File/code cần bổ sung khi thực hiện

```text
configs/
  sprint12_improvement_protocol.json
src/
  rlearner.py
  ranking_metrics.py
  policy_evaluation.py
  ensemble.py
scripts/
  run_oof_experiment.py
  compare_improvement_candidates.py
  run_external_hillstrom.py
output/improvement/
  registry.csv
  oof_metrics.csv
  paired_comparisons.csv
  resource_profiles.csv
docs/model_cards/
  <candidate>.md
```

Mỗi registry row phải có:

- run ID, commit SHA, UTC timestamp;
- dataset checksum, source-index hash, fold/seed;
- model/config hash và package versions;
- row/event counts theo arm;
- fit/predict time, peak RSS;
- toàn bộ metric đã đăng ký, không chỉ metric tốt nhất;
- status `smoke`, `screen`, `finalist`, `retrospective_confirmation` hoặc `failed`;
- failure reason nếu dừng.

## 8. Thứ tự thực hiện đề xuất

### Work package 1 — 1 ngày: khóa protocol

- Chuyển `fit + validation` thành development cross-fitting pool.
- Viết config selection metric/gate.
- Đánh dấu confirmation cũ là retrospective.
- Thêm expected-random baseline.

### Work package 2 — 1–2 ngày: evaluation stack

- RATE/AUTOC.
- Outcome-adjusted evaluation.
- pROCini/PUC reproduction.
- Synthetic tests và paired inference.

### Work package 3 — 2 ngày: P0 models

- R-Learner.
- DR binary/MC/final-stage ablation.
- Meta-learner rare-outcome ablation có giới hạn.
- Screening và resource registry.

### Work package 4 — 1 ngày: ensemble

- Best-single theo pre-registered risk.
- Softmax/R-score ensemble làm baseline.
- Causal Q-aggregation làm challenger.

### Work package 5 — 1 ngày có session: forest gate

- CausalForestDML 20% → 30%.
- ForestDRLearner chỉ khi Causal Forest hoặc DR OOF cho thấy lý do tiếp tục.

### Work package 6 — 1 ngày: release

- Full OOF finalist, retrospective confirmation.
- Dashboard thêm budget-value curve, paired CI, metric agreement và resource panel.
- Model card, experiment table, CV bullets, demo script.

PTONet/deep learning là work package tùy chọn sau release, không nằm trên critical path.

## 9. Thành quả phải show được cho DA, DS và AI Engineer

### Data Analyst

- data contract, event-rate/balance audit và leakage policy;
- bảng policy theo budget, expected random, sensitivity và confidence interval;
- dashboard giải thích quyết định bằng đơn vị conversion/customer;
- giới hạn non-uniform sampling và anonymous feature được nêu rõ.

### Data Scientist

- RCT estimand, CATE meta-learners, R-/DR-Learner, Causal Forest;
- cross-fitting, rare-outcome correction, RATE/Qini/pROCini/PUC;
- paired uncertainty, model selection khi không có ground-truth CATE;
- kết quả không cải thiện và quy tắc giữ champion có căn cứ.

### AI Engineer

- one-command experiment runner, config/schema validation, artifact registry;
- unit + integration tests, deterministic split hash, resource gates;
- model/data cards, self-contained dashboard, reproducible environment;
- Kaggle package có preflight/checkpoint và không phụ thuộc notebook thủ công.

CV không nên ghi “đạt model tốt nhất”. Có thể ghi:

> Xây dựng và kiểm định pipeline causal uplift trên 13,98 triệu quan sát randomized;
> triển khai cross-fitted R/DR/meta-learners, paired policy evaluation và dashboard
> budget-aware; thiết kế compute gates cho laptop/Kaggle và model-selection protocol không
> tune vào holdout.

Chỉ thêm phần trăm cải thiện sau khi challenger đạt promotion rule.

## 10. Nguồn gốc đã kiểm tra và thứ tự đọc

### Bắt buộc trước khi code P0

1. **Criteo dataset và giới hạn sampling**
   [Criteo AI Lab](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) và
   [Criteo Hugging Face card](https://huggingface.co/datasets/criteo/criteo-uplift).
   Đọc data description, fields, privacy và key figures.

2. **Meta-learners (S/T/X)**
   Künzel et al., PNAS 2019,
   [DOI 10.1073/pnas.1804597116](https://doi.org/10.1073/pnas.1804597116).
   Đọc assumptions, thuật toán S/T/X và phần thí nghiệm arm imbalance.

3. **R-Learner**
   Nie & Wager, Biometrika 2021,
   [DOI 10.1093/biomet/asaa076](https://doi.org/10.1093/biomet/asaa076).
   Đọc Robinson residualization, R-loss, cross-fitting và quasi-oracle conditions.

4. **DR-Learner**
   Kennedy, Electronic Journal of Statistics 2023,
   [DOI 10.1214/23-EJS2157](https://doi.org/10.1214/23-EJS2157).
   Đọc doubly robust pseudo-outcome, sample splitting và error decomposition.

5. **Rare outcome uplift**
   Nyberg et al., ACML/PMLR 2021,
   [paper](https://proceedings.mlr.press/v157/nyberg21a.html); Nyberg & Klami,
   DMKD 2023,
   [DOI 10.1007/s10618-023-00917-9](https://doi.org/10.1007/s10618-023-00917-9).
   Với paper 2023, đọc mục 3.1–3.3 và công thức khôi phục xác suất trước khi sửa sampling.

6. **CATE model selection thực nghiệm**
   Mahajan et al., ICLR 2024,
   [paper chính thức](https://proceedings.iclr.cc/paper_files/paper/2024/hash/71484f17ae8ddd0500c8571bed59926d-Abstract-Conference.html).
   Đọc surrogate metrics, protocol tune metric và kết luận về ensembling.

7. **Causal Q-Aggregation**
   Lan & Syrgkanis, AISTATS 2024,
   [PMLR](https://proceedings.mlr.press/v238/lan24a.html).
   Đọc setup validation tách biệt, doubly robust loss, Q-aggregation objective và empirical
   section. Candidate models phải được fit trên sample khác validation dùng để học weights.

8. **Treatment prioritization**
   Yadlowsky et al., JASA 2025 issue,
   [DOI 10.1080/01621459.2024.2393466](https://doi.org/10.1080/01621459.2024.2393466).
   Đọc TOC, RATE/AUTOC, inference và sample-splitting requirement.

### Evaluation mới 2024–2025

9. **Variance reduction cho uplift evaluation trên RCT**
   Bokelmann & Lessmann, EJOR 2024,
   [DOI 10.1016/j.ejor.2023.09.018](https://doi.org/10.1016/j.ejor.2023.09.018).
   Đọc outcome adjustment, điều kiện giảm variance và real-data experiments.

10. **pROCini**
    Verbeken et al., JMLR 2025,
    [paper](https://www.jmlr.org/papers/v26/22-1455.html).
    Đọc mục 2 về Qini definitions, mục 3 về ROCini/pROCini và mục 4 về model-selection
    sensitivity.

11. **PUC/PTONet**
    Zhu et al., ICML 2025,
    [conference page](https://icml.cc/virtual/2025/poster/44364) và
    [source code](https://github.com/euzmin/PUC).
    Trước hết reproduce PUC; chỉ sau đó mới cân nhắc PUL/PTONet.

12. **AutoCATE**
    Vanderschueren et al., ICML 2025,
    [PMLR](https://proceedings.mlr.press/v267/vanderschueren25a.html) và
    [official code](https://github.com/toonvds/AutoCATE).
    Đọc ba tầng evaluation–estimation–ensembling; dùng như design reference, không mặc định
    chạy full AutoML trên 14 triệu dòng.

### Forest và policy

13. **Generalized Random Forests**
    Athey, Tibshirani & Wager, Annals of Statistics 2019,
    [DOI 10.1214/18-AOS1709](https://doi.org/10.1214/18-AOS1709).
    Đọc local moment equations, honesty và asymptotic inference.

14. **EconML 0.16 implementation contracts**
    [CausalForestDML](https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html),
    [NonParamDML](https://www.pywhy.org/EconML/_autosummary/econml.dml.NonParamDML.html),
    [DR-Learner](https://www.pywhy.org/EconML/spec/estimation/dr.html) và
    [RScorer](https://www.pywhy.org/EconML/_autosummary/econml.score.RScorer.html).
    Đọc parameter contract về discrete outcome/treatment, CV, MC iterations, honesty,
    inference và scoring trước khi viết wrapper.

15. **Policy learning**
    Athey & Wager, Econometrica 2021,
    [DOI 10.3982/ECTA15732](https://doi.org/10.3982/ECTA15732); Dudík et al.,
    ICML 2011,
    [Microsoft Research](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/).
    Đọc value/regret framing và doubly robust evaluation; không chuyển pointwise CATE
    thành profit khi thiếu cost/revenue.

### Emerging 2025–2026: đọc để xác định phạm vi, chưa code ngay

- Bokelmann & Lessmann, heteroscedasticity-aware RCT sampling,
  [DOI 10.1016/j.ejor.2025.02.030](https://doi.org/10.1016/j.ejor.2025.02.030).
- Zheng et al., uplift delayed feedback, AAAI 2026,
  [DOI 10.1609/aaai.v40i19.38686](https://doi.org/10.1609/aaai.v40i19.38686).

## 11. Definition of Done

- [ ] Confirmation cũ được đánh dấu retrospective trong mọi output mới.
- [ ] Synthetic truth + edge-case tests cho metric mới.
- [ ] Expected-random policy và multi-seed random sensitivity.
- [ ] OOF registry cho Response/X/R/DR và ensemble.
- [ ] R-Learner và DR ablation chạy full development trong resource gate.
- [ ] Causal Q-aggregation weights chỉ học trên validation/OOF hợp lệ.
- [ ] Forest có learning curve hoặc lý do dừng định lượng.
- [ ] Champion chỉ đổi theo promotion rule; nếu không, giữ Response.
- [ ] Dashboard hiển thị policy-area, paired CI, metric agreement và limitation.
- [ ] Model/data card cập nhật commit SHA, run ID, package version.
- [ ] External Hillstrom run hoặc ghi rõ chưa có external validity.
- [ ] Không có claim revenue/CLV, individual principal stratum hoặc “SOTA” không có benchmark.
