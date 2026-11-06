# Kế hoạch bổ sung V4: từ dự đoán churn đến quyết định có thể kiểm chứng

Soạn ngày 20/09/2026; cập nhật dẫn đường ngày 21/09/2026. Đây là **bản thiết kế V4**, không phải current-status report. Workspace hiện có một phần implementation/smoke; xem [kế hoạch tổng thể V4.1](MASTER_PLAN.md) cho trạng thái, work packages và lịch còn lại. Lượt hoàn thiện kế hoạch chỉ sửa tài liệu.

V4 tiếp nối [review V3](REVIEW_RESEARCH_V3.md), [thiết kế pipeline V3](EXPERIMENT_DESIGN_V3.md) và [hệ thống V3](SYSTEM_DESIGN_V3.md). Các phát hiện về Orange, uncertainty, temporal replay và semantics của API vẫn giữ nguyên. Không coi nghiên cứu bổ sung là bằng chứng dự án đã cải thiện hiệu quả.

Đọc tài liệu này để chọn phạm vi và thứ tự đầu tư; đọc [EXPERIMENT_DESIGN_V4.md](EXPERIMENT_DESIGN_V4.md) để thực hiện E19–E28. Mã E01–E18, N00–N10 và DEV01–DEV16 vẫn thuộc V3. Các file/module/contract mới nhắc dưới đây đều là **thiết kế tương lai**, trừ khi ghi rõ đã tồn tại.

Muốn xem **chạy model nào, grid nào, bao nhiêu fits, thứ tự các đợt và chọn winner thế nào**, đọc [Runbook thử nghiệm R00–R09](EXPERIMENT_RUNBOOK_V4.md). Smoke runner đã có; full screen/confirm protocol chưa triển khai. Effort 300–400h và mười phiên đầu bên dưới là thiết kế lịch sử; dùng phần việc còn lại 310–404h cùng dependencies trong MASTER_PLAN, không cộng hai lịch.

## 1. Kết luận định hướng

Không nên lấy “thêm nhiều model” làm mục tiêu tiếp theo. Đề xuất tập trung dự án vào câu hỏi:

> Trong một campaign có ngân sách, capacity và dữ liệu hạn chế, khi nào thay đổi quyết định của policy hiện tại tạo thêm giá trị; cần bổ sung dữ liệu, cải thiện model, thay action hay sửa vận hành để đạt được giá trị đó?

Ba sản phẩm nghiên cứu cụ thể:

1. **Bản đồ nguyên nhân mất giá trị:** sai bài toán/nhãn, thiếu thông tin, sai ước lượng, sai phân bổ hay delivery không đạt. Chỉ rõ sửa khâu nào đáng đầu tư bằng thử nghiệm chéo và các mức oracle hợp lệ.
2. **Quy trình so policy tiết kiệm bằng chứng:** phân tích nhóm hai policy quyết định khác nhau, paired evaluation và trial có thiết kế; đo cost để đạt cùng độ chính xác, không chỉ số mẫu giảm.
3. **Bộ kiểm chứng có thể làm hệ thống thất bại:** time-zero, unsupported actions, giả định causal bị vi phạm, chi phí sai, delayed labels, shared capacity và lỗi software. Báo cả trường hợp hệ thống phải từ chối kết luận.

Đây là hướng đóng góp cần kiểm nghiệm, không phải khẳng định đã có thuật toán mới hoặc chưa ai nghiên cứu. Phương pháp nền đã có; giá trị học thuật khả thi nằm ở câu hỏi rõ, benchmark đáng tin, phát hiện có khả năng tái lập và ranh giới áp dụng được đo.

## 2. Thu hẹp bài toán theo action có thể thực hiện

### 2.1 Churn là outcome; không phải một cơ chế duy nhất

Các use case dưới đây là giả thuyết để khảo sát với partner, không phải thông tin đã xác nhận về khách hàng thật.

| Use case | Quyết định cụ thể | BAU cần ghi nhận | Dữ liệu bổ sung tối thiểu | Outcome và nguy cơ diễn giải sai |
|---|---|---|---|---|
| Thanh toán thất bại | Có gửi hỗ trợ cập nhật thanh toán trước mốc hủy không? | Quy trình nhắc nợ/retry hiện có | Invoice, due date, retry result, grace period, actual collection cost | Khoản thu ròng và active days; không coi mọi nợ quá hạn là churn |
| Chất lượng dịch vụ | Có ưu tiên chẩn đoán/xử lý lỗi thay vì discount không? | Hàng đợi xử lý sự cố hiện tại | Ticket timeline, incident, repair capacity, account–incident map | Contribution margin, thời gian khắc phục, complaints; repair có thể tác động cả vùng |
| Gia hạn/giá | Có đề nghị một offer cụ thể trước renewal không? | Offer policy đang dùng | Contract end, offer eligibility, discount ledger, renewal state | Margin sau discount và retention; doanh thu tăng không đủ chứng minh lợi nhuận |

Chỉ chọn **một use case chính, một action rõ và một BAU rõ** cho pilot đầu. Không hứa giải quyết cả ba trong research release. Orange/Hillstrom không có đầy đủ các trường trên; không gán causal mechanism hoặc tác động telco cho các cột ẩn danh.

Không dùng feature importance/SHAP để suy ra “khách churn vì giá nên discount sẽ có hiệu quả”. Giải thích predictor, chẩn đoán nguyên nhân và hiệu ứng của action là ba câu hỏi khác nhau. Treatment-effect model cũng không xác nhận nguyên nhân churn của từng cá nhân.

### 2.2 Problem contract phải khóa trước model

Một contract phải ghi đủ: population, eligibility tại thời điểm quyết định, đơn vị account/household, action và version, BAU, time zero, horizon, endpoint, censoring/competing events, giá/cost, capacity, estimand, phương pháp inference và ranh giới triển khai.

Ví dụ giả định cho payment-support: account có invoice thất bại trước snapshot, còn trong grace period tại snapshot, đủ điều kiện nhận kênh liên hệ; assignment ngay sau snapshot; theo dõi từ assignment kể cả người không nhận/không mở tin. Không chọn mẫu bằng điều kiện “đã sống sót đến lúc nhân viên gọi được”. Không loại người churn trước delivery khỏi ITT.

Nguyên tắc đồng bộ eligibility, assignment và bắt đầu follow-up lấy từ target-trial framework; việc áp dụng sang retention ở đây là đề xuất của dự án, không phải bằng chứng về hiệu quả telco. [Hernán và cộng sự, 2016](https://pubmed.ncbi.nlm.nih.gov/27237061/)

### 2.3 Tiêu chuẩn chọn use case sau discovery

Không cộng điểm cảm tính để bù cho một điều kiện nhận diện bị thiếu. Dùng các cổng theo thứ tự:

1. Action hợp lệ, vận hành được và có owner; consent/eligibility do partner xác nhận.
2. Có thể phân biệt assignment, delivery và outcome; outcome không do việc được contact mới được ghi nhận.
3. Có BAU, cost ledger và đủ eligible units để thử nghiệm với precision hữu ích.
4. Có đủ variation/support cho action hoặc có thể tổ chức randomized logging mới.
5. Sau các cổng trên mới so cơ hội kinh tế và thời gian chờ bằng chứng.

Không có partner: chọn Hillstrom cho phương pháp ra quyết định, relational mock cho workflow; ghi rõ chưa xác nhận product–customer fit.

## 3. Bổ sung mới so với V3

| Khoảng trống còn lại | Bổ sung V4 | Kết quả phải cung cấp, kể cả âm |
|---|---|---|
| Có PIT nhưng chưa đặc tả đầy đủ ai bắt đầu follow-up khi nào | E19: time-zero và label-adjudication contract | Độ lệch do lựa chọn sau assignment; bảng nhãn hợp lệ/không xác định |
| So global policy value chưa tận dụng cấu trúc agreement | E20: disagreement-aware evaluation/design | Variance, coverage và cost-to-precision theo tỷ lệ quyết định khác nhau |
| Không đủ support vẫn có thể xuất một score đẹp | E21: support gate, fallback và sensitivity | Giá trị của toàn hybrid policy, tỷ lệ fallback và vùng không thể kết luận |
| Churn × margin chưa mô tả cash flow bất đối xứng/chi phí sai | E22: reward model và economics stress | Break-even/cost sensitivity, realized reward khi có ledger, không ROI giả |
| Thêm features theo AUC thay vì giá trị quyết định | E23: giá trị thông tin sau cost/latency | Feature package nào đáng thu, khi nào thêm dữ liệu thua model đơn giản |
| Ablation từng biến không thấy tương tác các thành phần | E24: thiết kế chéo và oracle substitution | Nguồn cải thiện, tương tác và bottleneck có uncertainty |
| Capacity chỉ là số slots, chưa có hàng đợi/shared resource | E25: delivery/queue stress | Policy ranking có đảo khi delay/agent capacity thay đổi không |
| Leading metric có thể tốt nhưng long-term value xấu | E26: surrogate failure challenge | Khi nào phải chờ endpoint thật; không promote dựa correlation đơn thuần |
| Nhiều campaign nhỏ, pooling dễ che heterogeneity | E27: partial pooling và leave-campaign-out | Khi nào chia sẻ dữ liệu hữu ích, khi nào negative transfer |
| Tests chạy xanh chưa xác nhận evaluator có khả năng bác bỏ | E28: mutation/falsification suite | Những lỗi nào được phát hiện, bỏ lọt và gây false promotion |

V4 không thay toàn bộ pipeline V3. Mỗi bổ sung chỉ mở khi có dữ liệu và đi qua gate trong tài liệu thử nghiệm.

## 4. Các câu hỏi nghiên cứu được ưu tiên

### RQ-A — Nâng cấp nào thực sự tạo ra giá trị?

Giữ cố định data/split/budget, thay có kiểm soát representation, effect estimator và allocation. Trong simulation, lần lượt thay bằng oracle có cùng tập thông tin để đo mức mất giá trị có thể khắc phục. Tách giá trị của biết thêm thông tin khỏi giá trị của fit model tốt hơn.

Deliverable: một biểu đồ main effects/interactions, một bảng bottleneck và ít nhất một phản ví dụ cho kết luận tổng quát. Không phân bổ toàn bộ regret cho từng node theo một thứ tự tùy ý rồi gọi đó là causal decomposition duy nhất.

### RQ-B — Hai policy gần giống nhau có thể so sánh rẻ hơn không?

Tính agreement từ các policy đã freeze, dùng cùng reward/constraints. Chỉ so sánh độc lập hai overall means có thể đưa thêm nhiễu từ khách nhận cùng action. Nghiên cứu của Simester và cộng sự cung cấp nền tảng cho evaluation theo nhóm recommended actions; thiết kế V4 sẽ kiểm tra thêm low-event, chi phí thu dữ liệu và constraints. [Simester, Timoshenko & Zoumpoulis, 2020](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3379)

Deliverable: frontier cost–precision, không hứa tiết kiệm một tỷ lệ cố định. Nếu paired DR của V3 đã loại toàn bộ nhiễu agreement thì E20 phải nói rõ lợi ích đến từ **thiết kế thu mẫu**, không nhận nhầm thành estimator mới.

### RQ-C — Khi nào không nên cá nhân hóa thêm?

So baseline đơn giản, partial pooling, personalized policy và hybrid fallback trên rare-event/weak-support settings. Primary là whole-population value so BAU; complexity, acquisition cost và uncertainty là tiêu chí phụ đã định trước.

Không dùng “p > 0,05” để kết luận các phương pháp tương đương. Chọn practical equivalence/non-inferiority margin trước evaluation. Khi CI còn rộng phải ghi inconclusive; không mặc định model nhỏ tốt hơn hoặc model lớn vô ích.

**Chọn RQ-A làm trục chính.** RQ-B là nghiên cứu thứ hai nếu inference và power gates đạt. RQ-C là extension, không chạy ba hướng như ba luận văn đồng thời.

## 5. Data strategy và mock có mục đích

| Data track | Có thể làm ngay ở phase triển khai | Không được suy ra |
|---|---|---|
| IBM hiện tại | Compatibility, prediction quality, schema/serving tests | Hiệu ứng can thiệp hoặc horizon tương lai đã kiểm chứng |
| Orange hiện tại | Audit và sensitivity; low-event comparisons với assumptions rõ | Population-wide telco value; campaign transfer khi không có campaign IDs |
| Hillstrom sau kiểm nguồn/license và freeze split | Multi-arm value, paired comparison, reward modeling trên spend | Spend là net margin; email là bằng chứng action telco |
| Criteo nếu tài nguyên đủ | Rare-outcome scale và replication một câu hỏi | Exposure là covariate pre-treatment hoặc thay assignment bằng exposure |
| Relational mock | E19–E28 với known mechanism và failure injection | Customer demand, response elasticity hay revenue thật |
| Partner data sau thỏa thuận | Một use case và prospective trial có maturity | Tự suy rộng ra mọi operator/campaign |

### Mock phải dựng pain point, không dựng “demo luôn thắng”

Bổ sung vào relational schema V3: invoices/retries, subscription-state history, campaign/action version, assignment, delivery attempts, agent/queue shifts, cost postings/reversals, outcome adjudication và support map. Một demo có thể dùng một subset; không cần tạo mọi bảng cho public static benchmark.

Các thế giới bắt buộc gồm: discount không hiệu quả; discount giữ khách nhưng lỗ margin; model risk tốt nhưng chọn nhầm action; effect model tốt nhưng delivery chậm; data enrichment có predictive value nhưng không đổi decision; hai policy quyết định giống nhau; policy khác nhau chỉ ở unsupported segment.

Quy tắc generator:

- Tách mechanism seeds, treatment-assignment seeds và learner seeds; training worlds và challenge worlds không chỉ khác random seed mà còn khác cơ chế.
- Không tạo outcome bằng chính candidate model rồi dùng kết quả để kết luận candidate đó phù hợp thực tế.
- Binary probabilities phải hợp lệ theo thiết kế. Nếu clipping làm đổi phân phối effect thì báo actual induced effect, không chỉ effect tham số đầu vào.
- Có outcome measurement process: missing outcome, delayed correction, treatment-dependent logging; không chỉ thêm Gaussian noise vào features.
- Known truth chỉ nằm trong evaluator/oracle artifacts; learner input không có latent states, assignment tương lai hoặc nhãn hậu nghiệm.
- Đánh giá oracle theo thông tin và constraints ngang bằng; clairvoyant/full-state chỉ là upper bound riêng.

## 6. Kiến trúc bổ sung tối thiểu

| Thành phần đề xuất | Input → output | Điều kiện thiết kế quan trọng |
|---|---|---|
| `problem_contract` | Population/action/time/endpoint specs → validated estimand | Version riêng với model; đổi endpoint không ghi đè result cũ |
| `outcome_adjudication` | Event histories + as-of date → label/status/reason | Giữ unknown/censored/disputed riêng với outcome=0 |
| `policy_comparison` | Frozen policy pair + evaluation cohort → action-pair strata | Không đọc evaluation outcomes để chọn strata/threshold |
| `support_diagnostics` | Logging design + target cohort → support/fallback mask | Biết unsupported không đồng nghĩa biết counterfactual value |
| `economics_ledger` | Actual postings + attribution rules → reward/cost | Mỗi khoản đếm một lần; tách allocated overhead với incremental cost |
| `experiment_matrix` | Protocol factors + blocks → run manifest | Match seeds/splits để paired comparison; record failed cells |
| `challenge_suite` | Valid fixtures + mutations → expected failure + detection | Mutation không sửa dữ liệu gốc; bản lỗi cô lập, không xuất campaign |

Ưu tiên tích hợp vào package/Parquet/registry đang đề xuất ở V3. Chưa cần microservices mới. Hợp đồng dữ liệu và evaluator đáng ưu tiên hơn giao diện.

Packet mới cần bốn thông tin quyết định: action BAU, action challenger, lý do thay/giữ, trạng thái bằng chứng. `NO_ACTION`, `FALLBACK_BAU` và `NEEDS_EVIDENCE` là các trạng thái khác nhau; không gom thành score thấp.

## 7. Lộ trình tích hợp 12 tuần, không cộng thêm vô hạn

Lộ trình này **thay phần phân bổ effort** của V3 khi chọn hướng V4, không cộng 12 tuần mới lên V3. Một người thực hiện; ước lượng 280–370 giờ công việc và 20–30 giờ dự phòng, tổng 300–400 giờ. Đây là ước lượng chưa profiling, không cam kết hoàn tất nếu data access hoặc identification bị chặn. Thời gian chờ outcome thật nằm ngoài effort này.

| Giai đoạn | Effort | Việc thực hiện | Deliverable / gate |
|---|---:|---|---|
| Tuần 1–2: khóa bài toán và validity | 40–55h | Orange audit V3; chọn public-data fallback; problem contract; E19 label fixtures; chuẩn hóa reward/BAU | Không còn causal claim thiếu assumptions; chưa training nếu data roles chưa khóa |
| Tuần 3–4: evaluator trước model | 50–65h | E02/V3; paired comparison E20; E28 core mutations; registry/split/uncertainty | Metric identities đúng; null/coverage đạt protocol; lỗi nghiêm trọng bị chặn |
| Tuần 5–6: baseline và bottleneck | 50–65h | Hillstrom adapter; baseline risk/regularized CATE; E24 full 2×2×2; E22 break-even | Bảng attribution có uncertainty, compute ledger; giữ baseline nếu chưa hơn |
| Tuần 7–8: lựa chọn một cải tiến | 45–60h | Chọn shrinkage/direct policy hoặc E20 sampling từ pilot; E21 support gate; một replication | Một hypothesis confirmable; không mở grid sau khi xem confirmation |
| Tuần 9–10: workflow và chất lượng | 45–60h | Relational replay E19/E16; ledger; E28 end-to-end; E25 queue stress nhỏ nếu còn budget | Deterministic replay, zero declared constraint violations, decision packet rõ |
| Tuần 11–12: confirmation và bàn giao | 50–65h | Fresh evaluation đúng role; sensitivity; negative results; clean reproduction; demo | Research result có scope/CI và actionable next step; không tự gọi production-ready |

Nếu inference/data access chiếm quá 4 tuần: cắt E20 sampling, E25 queue và replication lớn; giữ validity + một real-data benchmark + một nghiên cứu nguyên nhân. Không bỏ null/coverage để đủ số model.

### Chủ động hoãn khỏi core

TabPFN/deep causal, KKBox survival toàn diện, robust minimax optimizer, hierarchical multi-campaign, surrogate learning và nhiều action telco cùng lúc. Chỉ mở sau khi xác nhận chúng giải quyết bottleneck đã đo. Robustness diagnostics có thể core; triển khai optimizer robust đầy đủ thì không.

## 8. Backlog mới và definition of done

| ID | Ưu tiên / phụ thuộc | Công việc | Acceptance cụ thể |
|---|---|---|---|
| V4-01 | P0 / DEV01 audit | Problem + endpoint contract; E19 | Cùng một timeline không thể vừa eligible sau assignment vừa được đưa vào baseline; unknown không thành non-churn |
| V4-02 | P0 / evaluator V3 | Paired action-pair comparison; E20 | Hai policy giống nhau có delta và SE của contrast bằng 0, dù outcome nhiễu; không tính uncertainty triển khai cố định vào contrast này |
| V4-03 | P0 / V4-01/02 | Mutation suite E28 | Mọi critical mutation có expected failure; published score không xuất ra khi gate fail |
| V4-04 | P1 / baselines V3 | E24 factorial manifest | 8 cells, cùng splits/tuning allowance; main/interaction effects; không coi folds là independent datasets |
| V4-05 | P1 / reward contract | E22 break-even + cost stress | Chi phí đổi có thể đảo recommendation đúng fixture; không đếm offer cost hai lần |
| V4-06 | P1 / support/design logs | E21 fallback | Unsupported action không được đề xuất; denominator vẫn là whole eligible cohort |
| V4-07 | P1 có điều kiện / V4-02/03 | E20 sampling experiment | Mọi inclusion probability được log; bias/coverage/cost so cùng target estimand |
| V4-08 | P2 / feature latency/cost | E23 value of information | Out-of-sample marginal value đã trừ acquisition cost; sampling missingness được kiểm |
| V4-09 | P2 / replay V3 | E25 queue/shared-resource | Chính sách dưới cùng supply, full-cohort outcome; chỉ rõ interference unit |
| V4-10 | P2 / mature multiple campaigns | E26/E27 | Không dùng campaign giả tạo từ row split để claim external generalization |

P0 là gate tính đúng; P1 là core nghiên cứu; P2 chưa nằm trọn trong 300–400h. Acceptance về thống kê phải dùng đủ replication và uncertainty theo V3/E28, không chấm pass chỉ vì một run đẹp.

## 9. Khi nào tăng model complexity, khi nào dừng?

| Quan sát đã kiểm | Bước nên đầu tư tiếp | Không nên làm |
|---|---|---|
| Oracle action value cũng không vượt BAU sau cost | Thiết kế action/use case mới với domain owner | Tuning thêm model để “tạo” treatment effect |
| Observed-X oracle tốt, fitted policy kém | Estimation, sample size, shrinkage hoặc representation | Đổ lỗi data thiếu latent signal khi chưa đo |
| Full-state oracle tốt nhưng observed-X oracle không tốt | E23 kiểm giá trị và khả năng thu signal mới | Dùng full-state gap làm mục tiêu achievable của learner |
| Fitted score tốt nhưng allocation mất value | Constraints/solver hoặc reward specification | Thay neural network trước khi kiểm optimizer |
| Offline value tốt, delivery/replay xấu | Workflow, latency, shared capacity; thiết kế trial | Tuyên bố deployment gain từ OPE |
| Model hơn AUC nhưng policy gần như giống BAU | E20 so contrast và overhead | Gọi AUC gain là incremental business gain |
| CI quá rộng hoặc support thiếu | Thu evidence phù hợp hoặc giới hạn population | Đổi seed/clip propensity rồi gọi đã chứng minh |

## 10. Tiêu chuẩn chất lượng tài liệu và công bố

Một kết luận hợp lệ phải ghi: population, action, endpoint/horizon, comparator, effect đơn vị gốc, uncertainty, mức bằng chứng, assumptions, compute và trường hợp thất bại. Mỗi claim trỏ tới protocol/run/artifact; không chỉ tới notebook tổng hợp.

Mẫu chưa có số liệu: “Trên [population], policy [P] so [BAU] tại [budget] thay quyết định ở [d%] account; delta [reward/1.000 eligible] với CI [...]. Kết quả [exploratory/confirmatory/synthetic], phụ thuộc [...]. Chi phí bổ sung [...]. Chưa xác thực [...].” Các ô trống là yêu cầu báo cáo, không phải số liệu để tự điền.

Tách ba loại tài liệu: dữ kiện đã quan sát; giả thuyết/phương án đề xuất; kết quả đã thực nghiệm. Không chuyển `PLANNED` thành `VALIDATED` chỉ vì unit tests xanh. Cũng không kết luận phương pháp bị bác bỏ khi dữ liệu chỉ chưa đủ power.

Tiêu chí hoàn tất tốt nhất của bản research không nhất thiết là “CATE thắng”. Có thể là xác định được vùng baseline đơn giản đủ tốt, vùng phải thu thêm evidence, hoặc phát hiện một benchmark không hỗ trợ claim đang dùng — miễn là được đo, kiểm chứng và dẫn đến quyết định cụ thể.

## 11. Gắn kế hoạch với codebase hiện tại

Đây là mapping để triển khai sau khi kế hoạch được chọn, **không phải các file đã được sửa trong V4**. Tách commit theo contract/evaluator/model/runner/report để review được nguyên nhân thay đổi.

| File hiện tại | Phần giữ lại / dùng làm baseline | Thay đổi được đề xuất | Kiểm chứng trước khi đi tiếp |
|---|---|---|---|
| `src/telco_churn/orange_data.py` | Loader và raw validation | Manifest assignment/provenance, feature availability status, limitation flags | Hash/count reconciliation; không tự điền campaign IDs/design probabilities |
| `src/telco_churn/uplift.py` | Model adapters và DR/IPW primitives | Train-fitted preprocessing; shared paired scores; explicit target/reward/action schema | Hand calculation, Q01/Q02/Q04/Q09; input output invariants |
| `src/telco_churn/model_tournament.py` | Candidate definitions và runtime capture | Tách selection process khỏi honest evaluation; không dùng repeats CI như population CI | Full-selection null suite, locked role/access manifest |
| `src/telco_churn/component_ablation.py` | Reporting pattern và candidate reuse | 8-cell controlled matrix E24; paired contrasts/interactions; failures included | Same nuisance/split/budget audit; report không chọn theo test Qini |
| `src/telco_churn/policy.py` | Eligibility/ranking primitives thích hợp | BAU/action catalogue, support fallback, common-envelope allocator | Independent feasibility checker; cost/sign/exhaustive tiny solver fixtures |
| `src/telco_churn/simulation.py` | Existing simulator làm historical baseline | Tách world/state/observation/delivery, observed-X versus full-state truth | E19/E24 metamorphic checks, no oracle leakage, induced effects đúng |
| `src/telco_churn/temporal_lab.py` | Existing temporal report để đối chiếu | Theo actual decision periods, mature labels, trajectory/reward ledger | Không double count overlapping horizons; monthly capacity và ITT reconciliation |
| `src/telco_churn/batch.py`, `api.py`, `schema.py` | IBM compatibility | Target semantics và bundle versions rõ; research packet riêng với existing risk endpoint | Existing contract compatibility; Q15/Q18; không gắn horizon chưa xác thực |
| `configs/orange_experiments.toml` | Historical experiment descriptions | Executable versioned registry cho dataset/protocol mới; không ghi đè history | Unknown/unused parameters fail; run manifest phản ánh config thực thi |
| `scripts/run_research.ps1` | Entry-point orchestration | Explicit exit-code checks; stage gates; smoke/screen/confirm profiles | Q17 injected failure; không xuất COMPLETE khi một subprocess fail |
| `scripts/build_research_notebooks.py` | Notebook generation | Reports đọc immutable artifacts; status/claims từ registry | Không recompute/tune âm thầm khi render; references không stale |
| `tests/test_uplift.py`, `test_simulation.py`, `test_policy.py` | Regression fixtures cũ | Thêm deterministic challenge fixtures; long MC jobs tách CI | Cheap CI chạy nhanh; statistical report có seed/scenario/count/MCSE riêng |

Không chuyển `features.py` thành package `features/` hoặc đổi imports đồng loạt ngay ở bước đầu. Có thể bổ sung interfaces/modules nhỏ, giữ wrappers cũ; chỉ refactor sau khi behavior được khóa bằng tests. Artifact cũ giữ read-only/historical, không chạy notebook `--inplace` lên bằng chứng cũ như một bước migration tự động.

## 12. Mười phiên làm việc đầu tiên khi bắt đầu triển khai

Mỗi phiên là một work package khoảng 3–5 giờ, không phải cam kết hoàn tất toàn phase trong 10 ngày. Effort này nằm trong tuần 1–2 và đầu tuần 3 ở mục 7, không cộng thêm.

| Phiên | Công việc | Đầu ra có thể review | Điều kiện chuyển bước |
|---|---|---|---|
| 1 | Inventory evidence, data hashes, source versions và existing outputs | Claim ledger: observed/conditional/planned | Không lẫn historical results với proposed results |
| 2 | Khóa một problem contract, endpoint và BAU; ghi open questions | Contract và target population | Thiếu partner được ghi là assumption; không tự bịa economics |
| 3 | Resolve Orange audit trong phạm vi nguồn có thể kiểm; xác định fallback | Identification note | Không resolve thì vẫn tiến hành Hillstrom track, không causal-promote Orange |
| 4 | Freeze data-role registry và immutable confirmation policy | Split/access manifest | Evaluation labels chưa dùng cho feature/model/cost selection |
| 5 | Thiết kế và implement tiny reward/action fixtures | Independent expected-value table | Sign, denominator và cost conventions có một nghĩa |
| 6 | Paired policy contrast và identical-policy test | E20 estimator smoke report | D=0 identity pass; q và e phân biệt |
| 7 | Time-zero/maturity contract trên relational tiny fixture | E19 label state report | Delivered-only/immature-as-zero không lọt |
| 8 | Train-fitted preprocessing và batch invariance | Q04 regression test | Single-row/chunks/permutations thống nhất trong tolerance |
| 9 | Runner failure propagation + executable protocol checks | Failed-run fixture và stage states | Invalid input/subprocess fail không thành success |
| 10 | 100-world inference smoke, profiling và scope checkpoint | Runtime/MCSE/next-run budget | Chỉ smoke, chưa chấm coverage gate; quyết định chạy 1.000+ worlds ở phase kế tiếp |

### Hạn mức chạy nghiên cứu

Ba profiles được đề xuất: `smoke` kiểm deterministic/nhỏ; `screen` tìm vấn đề và chọn bounded contrasts trên development; `confirm` chỉ chạy protocol đã freeze. Đây là tên thiết kế, chưa phải CLI đang tồn tại.

- Trước profiling không mở run dài hơn 2 giờ theo ước lượng. Chọn 1 small cell, đo wall time/RAM và fit-count gồm nuisance/refits; extrapolation phải ghi uncertainty.
- Đề xuất trần screening ban đầu 40 CPU-hours cho E24; nếu vượt, giảm world sizes hoặc số contrasts/inner trials theo revision trước chạy, không bỏ những cell đang thua. Số core × wall-hours phải ghi riêng với human effort.
- Cheap inference Monte Carlo và expensive full-refit có ngân sách khác nhau. Cache chỉ những objects dùng chung hợp lệ về train role/fold/data hash; không tái sử dụng fitted nuisance xuyên split gây leakage.
- Confirmation mở đúng một primary contrast đã chọn; secondary comparisons có multiplicity treatment. Chạm confirmation rồi thay method sẽ cần bằng chứng mới, không đổi tên profile để tiếp tục tuning.
- Nếu hết budget mà không phân biệt được methods, bàn giao precision/compute frontier và scope limitation; không chạy đến khi có một seed thắng.

### Nghiệm thu cuối vòng đầu

Chỉ cần một đường đi nhỏ nhưng đúng: source fixture → as-of snapshot → eligibility → frozen policies → feasible actions → assignment/delivery → mature reward → paired evaluation → evidence state. Lỗi deliberate phải được phát hiện. Sau đó mới mở model studies; chưa cần dashboard hay production deployment.
