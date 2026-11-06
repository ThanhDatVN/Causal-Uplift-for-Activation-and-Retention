# Kế hoạch nghiên cứu, thiết kế và phát triển dự án V3

Review bắt đầu 19/09/2026; bản kế hoạch hoàn thiện 20/09/2026. **Chỉ lập kế hoạch và tài liệu; chưa triển khai code hoặc chạy các thử nghiệm V3.**

Bổ sung ngày 20/09/2026: [kế hoạch V4](DEVELOPMENT_PLAN_V4.md) và [thiết kế E19–E28](EXPERIMENT_DESIGN_V4.md) đi sâu vào định nghĩa bài toán, disagreement-aware evaluation, bottleneck attribution và quality challenge suite. Nếu chọn hướng V4, dùng lộ trình tích hợp của V4 thay phân bổ effort ở V3; không cộng hai roadmap thành một phạm vi bắt buộc.

## 1. Đọc tài liệu theo thứ tự

| Tài liệu | Dùng để quyết định |
|---|---|
| [Review và research](REVIEW_RESEARCH_V3.md) | Tin được gì từ dự án hiện tại, lỗi/hạn chế nào ưu tiên, nguồn nghiên cứu và dataset nào có căn cứ |
| [Thiết kế thử nghiệm](EXPERIMENT_DESIGN_V3.md) | Từng nút pipeline thay gì, models/thuật toán con nào so sánh, metric/split/uncertainty/gates nào dùng |
| [Thiết kế hệ thống](SYSTEM_DESIGN_V3.md) | Data contracts, modules, state machine, API/batch/assignment/replay, tests và lưu trữ |
| Tài liệu này | Chọn phạm vi, thứ tự phát triển, nguồn lực, milestone và definition of done |

## 2. Định hướng đề xuất

Phát triển thành một hệ thống nghiên cứu và ra quyết định retention trả lời:

> Với dữ liệu có ít churn events và ngân sách hữu hạn, policy nào đem lại incremental value đáng tin cậy so với cách làm hiện tại, khi nào chưa thể kết luận, và nên thu thập bằng chứng tiếp theo như thế nào cho hiệu quả?

Ba năng lực tạo giá trị cần chứng minh bằng số:

1. **Tránh quyết định sai do dữ liệu/evaluation:** đo false launch, CI coverage, bias và cost của quyết định sai; audit Orange là case cụ thể đã thấy.
2. **Chọn action theo giá trị dưới constraints thật:** so risk/CATE/direct policy ở cùng money/channel/cooldown constraints, bằng incremental reward chứ không chỉ global ranking metric.
3. **Thu bằng chứng với ít tài nguyên hơn:** so experiment sampling/allocation/variance reduction theo cùng power/precision và tổng cost, gồm cả contacts và thời gian chờ labels.

Đây là hướng khác biệt cần kiểm nghiệm, chưa là claim độc quyền hoặc novelty đã được chứng minh. Có thể tái sử dụng các thành phần mạnh hiện tại; phần đầu tư mới nằm ở experimental design, evaluation correctness, economics và campaign lifecycle.

## 3. Pain points và bằng chứng phải có

| Người dùng | Pain point giả định | Baseline phải đo | Output dự án | Bằng chứng thành công |
|---|---|---|---|---|
| Retention lead | Gọi nhiều khách risk cao nhưng ít người thay đổi quyết định | BAU contact count, delivery, churn, offer cost | Policy chọn account/action theo incremental value | Policy A/B hoặc valid OPE có delta versus BAU tại cùng budget |
| Finance | Campaign giảm churn nhưng giảm margin vì discount | Realized contribution margin và actual costs theo arm | Value/cost curve; chọn campaign size; reconciliation | Net margin tăng có CI; không dùng doanh thu thay lợi nhuận |
| Data scientist | Model winner đổi khi đổi seed/evaluator | Existing ranking variance và false selection trong known-truth worlds | Honest selection, calibrated effect, inference diagnostics | Coverage/false-promotion đạt protocol và quyết định ổn định hơn |
| Experiment owner | Không đủ events và chờ outcome quá lâu | N/cost/time của uniform RCT | Power/cost planner; stratified/HS/CUPAC comparison | Cùng precision/power, giảm cost/time có đo uncertainty |
| Call-center ops | Trùng contacts, vượt capacity, khó audit | Lỗi export/retry, effort chuẩn bị campaign | Feasible action packet và replay | Zero violations trong fixtures; giảm thời gian/số lỗi trong shadow UAT |

Trước pilot, phỏng vấn/quan sát workflow cần xác nhận actual baseline, treatment catalogue, capacity, chi phí, churn definition và quyết định sẽ thay đổi. Chưa có partner thì chỉ được báo “pain point giả định được mô phỏng”; không tạo case study khách hàng hư cấu.

## 4. Phạm vi và thứ tự ưu tiên

### Core release

- Resolve hoặc mô tả chính xác uncertainty của Orange assignment; giữ artifact cũ và audit ledger.
- Executable protocol/registry, immutable manifests, nested selection và evaluation thích hợp thiết kế.
- Hillstrom làm real multi-arm benchmark mới; Criteo subset làm rare-event/scale replication nếu nguồn lực cho phép.
- Correct evaluator, policy value@budget, causal calibration/TOC-RATE supporting metrics, null/coverage validation.
- Risk/regularized CATE/direct policy baselines và component ablations có mục đích; shrinkage/calibration là cải tiến ưu tiên để kiểm.
- Constrained allocation, relational mock, monthly trajectory replay và meaningful no-contact decision.
- Batch campaign packet có lineage/evidence states; demo replay từ inputs đến delayed outcomes.

### Extensions có điều kiện

HS sampling/CUPAC và sequential inference; KKBox survival/temporal; robust policy under drift; TabPFN; deep causal models ở large-data track; prospective pilot. Mỗi extension chỉ mở khi có data/resources và câu hỏi chưa được core trả lời. Không triển khai tất cả đồng thời.

Không ưu tiên dựng thêm dashboard lớn, chatbot, Kubernetes, graph neural network hay RL khi chưa có dữ liệu/chứng cứ cho vấn đề chúng giải quyết. Đây là lựa chọn phân bổ effort, không khẳng định các phương pháp đó không hữu ích trong mọi bối cảnh.

## 5. Lộ trình 12 tuần và điều kiện nghiệm thu

Ước lượng cho một người phát triển có khoảng 25–35 giờ/tuần, CPU cá nhân; effort có thể thay đổi sau profiling. Lịch này tạo research release, không cam kết hoàn tất prospective margin180. Các estimate là kế hoạch, không là benchmark runtime đã đo.

| Mốc | Tuần / effort dự kiến | Công việc cụ thể | Deliverables và exit gate |
|---|---|---|---|
| M0 — Evidence audit | 1 / 20–30h | F01–F04, data provenance, Orange diagnostics, review all claims, freeze old artifacts | Audit report, identification decision, claim ledger; không gọi pooled observed rate là known propensity |
| M1 — Protocol và evaluator | 2–3 / 45–65h | Registry đọc config thật, split/maturity contract, metrics identities, paired policy evaluation, coverage/null jobs | E02/E03 pass theo tolerances đã khóa; protocol revision/hash và independent evaluation roles |
| M2 — Dataset adapters và baselines | 4 / 25–35h | Hillstrom adapter; Criteo 100k smoke; representation/missing/weight ablation; base outcomes | E04 tables; adapter manifest/license/semantics; no post-treatment features |
| M3 — Model/selection study | 5–6 / 50–70h | E05–E08, learning curves, shrinkage/calibration/direct policy, bounded tuning | Selection report bằng value@budget; retain simpler baseline nếu challenger không đạt; đầy đủ failed runs |
| M4 — Constraints và economic behavior | 7 / 25–35h | E09/E10, multi-arm costs, integer solver fixtures, reward semantics | Same-budget comparison; zero violations; no-contact/BAU đúng; economics assumptions tách khỏi facts |
| M5 — Temporal mechanism study | 8–9 / 45–65h | E11/E12, relational mock, observed-X oracle, delayed outcomes, monthly replay | Worst-window/trajectory reports; không overlapping cash-flow double count; unseen DGP structures |
| M6 — Evidence acquisition study | 10 / 25–35h | Chọn E13 hoặc E14 theo feasibility; core ưu tiên fixed-design HS/CUPAC | Cost/precision frontier và coverage; nếu không có lợi vẫn xuất failure analysis |
| M7 — Replay/product packet | 11 / 25–35h | E16, batch/artifact schema, assignment/outcome ledger, idempotency; API preview compatibility | One end-to-end fixture + failure injection + audit packet; operations metrics có environment context |
| M8 — External confirmation và handoff | 12 / 25–35h | E17/top policies freeze, test mới nếu available, docs/claim audit, reproducibility bundle | Methodology report có effect/CI/limits; clean run nhỏ; final decision rõ, không ép có “winner” |

Tổng khoảng 285–405 giờ. Nếu chỉ có 10 giờ/tuần, kế hoạch tương ứng khoảng 7–10 tháng, không nên gọi là sprint 12 tuần. Thứ tự artifacts quan trọng hơn ngày; milestone không pass thì chưa dùng kết quả downstream để tuyên bố cải tiến.

Data adapter/contract và product skeleton có thể làm xen kẽ sau khi schema ổn định; không cần đợi mọi paper experiment xong mới test replay. Không thay evaluator sau khi đã mở confirmation để giữ một winner.

## 6. Backlog phát triển có thể giao việc

| ID | Thay đổi dự kiến | Vị trí hiện tại liên quan | Kiểm chứng khi thực hiện | Phụ thuộc |
|---|---|---|---|---|
| DEV-01 | Version archive, code/environment hashes, protocol revision | reports, artifacts, pyproject, TOML | Artifact không bị overwrite; hash mismatch fail | M0 |
| DEV-02 | Data adapter semantics/provenance, assignment audit | orange_data/orange_benchmark | Raw/table parity; global balance; probability source labels | DEV-01 |
| DEV-03 | Executable config và run ledger | tournament/tuning/stability | Config hash khớp actual runs; native process failures propagate | DEV-01 |
| DEV-04 | Split planner: nested, group/time, maturity | train, orange_benchmark, temporal_lab | Inner/outer isolation; future labels blocked | DEV-03 |
| DEV-05 | Evaluator API: reward/estimand/paired uncertainty | evaluation/uplift | Sign identities, analytic fixtures, Monte Carlo coverage | DEV-02/04 |
| DEV-06 | Preprocessor state, category/weight/interactions | uplift/features/inference | Batch invariance, unseen category, per-arm calibration | DEV-04 |
| DEV-07 | Hillstrom/Criteo adapters và independent manifests | datasets proposal | No exposure/outcome feature leakage; outcome-sign contract | DEV-02 |
| DEV-08 | Model factory registry + bounded searches | uplift/model_tournament/tuning | Equal splits/evaluator/search budget; cache correctness | DEV-05/06/07 |
| DEV-09 | Shrinkage, calibration, direct-policy adapters | models proposal | E06–E08 paired comparisons; no test-selected hyperparameter | DEV-08 |
| DEV-10 | Action economics và constrained optimizer | policy proposal | Exhaustive small fixtures; feasible budget/cooldown | DEV-05 |
| DEV-11 | Structural worlds, observed-X oracle, relational events | simulation proposal | Oracle information parity, null worlds, process invariants | DEV-04/05 |
| DEV-12 | Trajectory replay, monthly resources, delayed reward | temporal_lab proposal | Fresh trajectories under policy; cashflow counted once | DEV-10/11 |
| DEV-13 | Sampling/allocation planner, variance reduction | experiments proposal | Same-cost power/coverage; inclusion and action probabilities | DEV-05/11 |
| DEV-14 | Campaign packet, assignment/delivery/outcome ledger | API/batch/SQL proposal | ITT join, idempotency, persistent audit/restore | DEV-10/12 |
| DEV-15 | Metrics-to-claims report và notebook refresh | reporting/scripts/notebooks/docs | Every headline resolves to artifact and evidence tier | Các main experiments |
| DEV-16 | CI/reproducibility/performance separation | CI/scripts/Docker | Format gate; fast fixtures; cached research runs; no false success | DEV-03/14 |

Không đổi hàng loạt module trước khi có baseline fixtures. Sửa đúng behavior review đã phát hiện, rồi refactor dần để tránh vừa thay thuật toán vừa thay infrastructure khiến khó quy nguyên nhân.

## 7. Ngân sách compute và thứ tự tăng quy mô

Vòng A: vài nghìn rows, deterministic correctness, không dùng để claim. Vòng B: full Orange/Hillstrom development, Criteo 100k; profile fit time/RSS. Vòng C: Criteo 1M, refit simulation worlds và selected methods. Vòng D optional: full Criteo/deep/TabPFN GPU sau khi vòng C trả lời được câu hỏi và đủ budget.

Giới hạn search ban đầu: tối đa ba shortlisted families × 12 configs × 3 inner folds × 3 outer folds = 324 top-level fits/dataset. Một DR/R/X fit có nhiều nuisance/effect fits bên trong nên compute thực tế lớn hơn; profiler phải tính toàn dependency graph. Cache nuisance theo đúng fold/config để tránh train lặp, không reuse sai train membership.

Đề xuất quota lần đầu: 20 CPU-hours cho smoke/profile, 100 CPU-hours cho core screening, review budget trước confirmation lớn. Đây là ceilings planning có thể điều chỉnh, không phải dự báo thời gian chắc chắn. Khi quá quota, giảm số unrelated branches/cells trước khi giảm control events/evaluation independence. Báo mọi truncation và timeout.

Không cần GPU cho core. Optional GPU run có cost log và local checkpoint/license review; không tuyên bố thuật toán tốt hơn nếu nó được search nhiều lần hơn hoặc dùng test information khác.

## 8. Ba phương án nguồn lực

| Phương án | Làm đủ phần nào | Chưa claim được |
|---|---|---|
| 8 tuần, CPU, không partner | M0–M4, subset M5, basic replay; Orange audit + Hillstrom + synthetic; một contribution study A hoặc B | Full scale, sequential system, real business effect |
| 12 tuần, CPU, có thời gian đều | Roadmap core; Criteo 1M nếu profile cho phép; study A và một nhánh B/C | Prospective margin180; novelty/publication được đảm bảo |
| 3–6 tháng, có data partner/resources | Core + mature temporal data + prospective campaign; optional survival/robust/deep nếu cần | Business gain chỉ được claim sau endpoint mature và valid evaluation |

Chưa có thông tin bổ sung về partner/compute từ người dùng khi soạn bản này, nên core dựa trên public data + synthetic, không chờ quyền truy cập để có kết quả nghiên cứu. Các phần phụ thuộc doanh nghiệp được tách rõ.

## 9. Dữ liệu cần xin từ doanh nghiệp khi có cơ hội

Không xin “mọi dữ liệu khách hàng”. Đề xuất pilot data extract tối thiểu:

- Account/subscription pseudonymous keys và household/group mapping nếu là đơn vị randomization.
- Billing/usage/tickets events, event_at/available_at, status/contract history để dựng as-of snapshots.
- Historical eligibility, campaign/action/version, assignment probabilities/design, contact attempts, delivery/acceptance và actual costs.
- Churn/censoring definition, outcome observation windows, data loss reasons và label availability.
- Contribution margin/discount/service costs theo horizon, capacity/offer inventory/cooldown và BAU policy.

Nếu chỉ có churn labels nhưng không treatment/design thì chỉ làm prediction/temporal data quality và chuẩn bị randomized logging mới. Nếu có observational treatment nhưng assignment confounded, cần DAG/assumptions/sensitivity; không tự nâng thành causal evidence vì train được propensity classifier.

Xác nhận feasibility với partner bằng bốn con số: eligible accounts/wave, churn baseline, effect kinh tế nhỏ nhất đáng làm, contact/offer cost. Sau đó mới tính N, duration, allocation và treatment catalogue. Không cam kết “giảm churn X%” trước trial.

## 10. Chu kỳ nghiên cứu liên tục

Mỗi vòng dài khoảng một tuần trong development: chọn một giả thuyết → freeze config/data roles → chạy diagnostic và main comparisons → inspect failures → viết decision note → cập nhật backlog. Những vòng dựa trên outcomes thực phải chờ maturity, không thể ép theo nhịp tuần nếu label horizon dài.

Meeting/report cuối vòng chỉ cần trả lời: thay đổi nào, comparator nào, thêm được thông tin gì, uncertainty còn bao nhiêu, điều gì bị loại, bước tiếp theo sẽ đổi quyết định ra sao. Không tăng model count nếu bottleneck là identification hoặc sample size.

Stop rules:

1. Assignment/provenance chưa rõ: dừng causal promotion trên dataset đó; tiếp tục audit hoặc dataset khác.
2. Hết search budget mà no improvement: giữ baseline, viết phạm vi kết luận; không tiếp tục mở grid hậu nghiệm.
3. Cần fresh evidence mà chưa có: đánh dấu exploratory; dùng future wave/new dataset để confirmation, không reset seed của test cũ.
4. Không có economics: chỉ báo churn/spend hoặc break-even dưới assumptions, không ROI thật.
5. Phương pháp phức tạp không vượt practical delta hoặc cost envelope: không chọn chỉ vì mới hơn.
6. Quy mô partner không đủ power: thiết kế lại action/population/horizon hợp lệ hoặc chấp nhận chưa thể chứng minh.

## 11. Definition of Done

### Research release

- Tất cả F01–F08 có resolution hoặc explicit evidence limitation, không bỏ qua bằng disclaimer chung.
- Có ít nhất một câu hỏi chính được trả lời bằng paired results, uncertainty và cơ chế giải thích; không chỉ bảng model scores.
- Evaluator/gate được kiểm null, nonconstant propensity, rare events và dependence theo assumptions đã khai báo.
- Model improvements tách được từ representation, calibration, solver và sampling changes qua ablations.
- Có real-data replication với semantics đúng; simulation nhiều mechanisms/worlds và unseen structures.
- Report đầy đủ negative/inconclusive cases và compute; claim ledger truy được đến artifacts.

### Product research release

- Một campaign fixture replay được từ snapshot đến assignment/delivery/mature outcome/evaluation.
- Eligibility/budget/cooldown/idempotency đúng; score semantics không giả horizon.
- Packet nói được tại sao contact/không contact, mức bằng chứng và bước cần tiếp theo.
- Compatibility IBM giữ được; causal pipeline không mượn API IBM để tuyên bố đã productionize.
- CI format/lint/tests đạt; environment lock, immutable run artifacts và small clean reproduction thành công.

### Business validation

- Có partner và use case/baseline/cost xác nhận.
- Policy trial hoặc thiết kế đánh giá nhận diện được tác động trên population đích.
- Primary endpoint mature, incremental net value vượt practical delta với uncertainty hợp lệ và guardrails đạt.
- Ops xác nhận capacity/delivery/audit workflow dùng được; tác động không chỉ nằm trong notebook.

Research/product release có thể hoàn tất khi chưa có business validation. Tài liệu và demo phải nói đúng trạng thái này.

## 12. Kế hoạch chỉnh tài liệu hiện có khi bước implementation được bắt đầu

| Tài liệu hiện tại | Thay đổi cần làm |
|---|---|
| README | Cập nhật evidence status, không gọi Orange pooled estimates là certified causal evidence; link audit và new experiments |
| DATA_CARD/MODEL_CARD/PRODUCT_DESIGN | Sửa horizon semantics IBM; tách intended contract với validated target; ghi product boundary thực tế |
| ORANGE_UPLIFT_DATA_CARD | Thêm F01 bằng raw counts, working assumptions, pooled-campaign possibilities và uncertainty chưa resolve |
| BENCHMARK_PROTOCOL/MODEL_TOURNAMENT | Nested selection, sampling versus seed uncertainty, policy-value primary, bounded comparisons |
| RESEARCH_V2/PROJECT_PLAN_AND_PROGRESS | Đánh dấu historical snapshot; R-learner đã có; không mô tả direct IBM→Iranian transfer; sửa nguồn sai |
| ARCHITECTURE_V2/EXPERIMENTATION_PLAYBOOK | Status implemented/planned, cost semantics, assignment/capacity consistency, real outcome maturity |
| NOTEBOOK_PIPELINE và notebooks | Metric/claims từ shared artifacts; bổ sung 07–12 theo dependency, không nhân code |
| CURRICULUM/CURRICULUM_V2/DEMO_SCRIPT | Chuyển từ checklist portfolio sang thí nghiệm có hypotheses và negative evidence; demo actual behavior |

Trong lượt hiện tại chỉ tạo bộ tài liệu V3 mới, giữ tài liệu/source/artifacts trước đó để người dùng review kế hoạch. Không đánh dấu backlog trên là đã hoàn thành.
