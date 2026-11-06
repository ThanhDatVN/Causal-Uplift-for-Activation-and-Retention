# Review dự án và cơ sở nghiên cứu V3

Review bắt đầu 19/09/2026, tài liệu hoàn thiện 20/09/2026. Phạm vi: snapshot tại `D:\GitHub\machine`. Đây là review và kế hoạch, chưa sửa source code, chưa chạy lại training/tournament. Thư mục hiện không có Git repository khả dụng; không thể kiểm tra lịch sử commit hoặc xác nhận thời điểm thực sự khóa protocol.

Đọc cùng [thiết kế thử nghiệm](EXPERIMENT_DESIGN_V3.md) và [kế hoạch phát triển](DEVELOPMENT_PLAN_V3.md). Khi đánh giá khả năng suy luận, các phát hiện dưới đây cần được xử lý trước khi tái sử dụng kết luận trong tài liệu V1/V2. Artifact cũ được giữ để truy vết.

## 1. Kết luận review

Dự án đã có nền tảng kỹ thuật sử dụng được: ba track dữ liệu, preprocessing trong fold, nhiều causal learners, lưu OOF predictions, policy có thể không triển khai, API/batch dùng chung inference. Tuy nhiên, chưa chứng minh được lợi ích giữ chân khách hàng hay lợi nhuận trong một doanh nghiệp. Thêm mô hình vào tournament hiện tại không giải quyết được khoảng trống này.

Hai vấn đề cần ưu tiên hơn model selection:

1. Dữ liệu Orange có quan hệ rõ giữa treatment và một số biến đầu vào, trong khi evaluator sử dụng một propensity hằng số lấy từ tỷ lệ treatment trong development. Chưa đủ cơ sở xem đây là thiết kế randomization đồng nhất với propensity đã biết.
2. Kết quả lặp CV và kết quả synthetic chưa được diễn giải đúng mức về sampling uncertainty, thông tin oracle và giá trị dài hạn.

Đề xuất chuyển trọng tâm sang **đánh giá và lựa chọn policy retention trong điều kiện ít sự kiện, thiết kế dữ liệu chưa chắc chắn, chi phí khác nhau và thay đổi theo thời gian**. Thành công có thể là một cải tiến có kiểm chứng về quyết định hoặc hiệu quả thu thập bằng chứng; không đặt điều kiện causal learner phải thắng risk model.

## 2. Bằng chứng đã kiểm tra

| Khu vực | Hiện trạng được kiểm tra | Ý nghĩa và giới hạn |
|---|---|---|
| IBM | Loader/checksum, EDA, split manifest, Logistic/HGB/CatBoost, calibration, report và model bundle | Predictive benchmark trên sample tĩnh; không xác nhận dự báo churn tương lai 30 ngày |
| Orange | 11.896 hàng, 178 feature; 2.886 control với 105 churn; 9.010 treatment với 303 churn | Chỉ 408 churn toàn bộ dữ liệu; 178 feature tạo bài toán ít thông tin so với độ linh hoạt của learner |
| Causal modeling | Risk, S/T/TO/DR/R/X; internal cross-fitting cho các nuisance tương ứng | R-learner và X-learner đã có, không phải đề xuất mới |
| Tournament | 14 ứng viên, 3 repeats × 3 folds, 9.516 development rows | Repeats đo sensitivity với chia fold; không tạo 3 mẫu khách hàng độc lập |
| Locked policy | Risk Logistic, capacity 30%; DR uplift 3,331 điểm %, CI [−1,507; 8,269]; IPW 1,076 điểm %, CI [−3,587; 6,019] | Chưa có bằng chứng lợi ích dương; giá trị causal còn phụ thuộc audit assignment |
| Temporal lab | 80.157 customer-month từ 6.000 khách giả lập; 18 tháng; một cấu hình DGP chính | Không phải 80.157 khách độc lập; chưa phải benchmark nhiều cơ chế và nhiều quần thể |
| Product | API/batch IBM; preview EV giả định; SQL bốn bảng; Docker/CI scripts | Chưa có execution/assignment/delivery/outcome loop theo kiến trúc V2 |
| Notebooks | 01–06 có 8/6/9/10/9/7 code cells và stored outputs không có error | Chỉ kiểm tra nội dung/output lưu sẵn, chưa execute lại notebooks trong lượt review |

Kiểm tra thực hiện ngày review:

- `python -m pytest -q -p no:cacheprovider`: 28 tests pass; hai deprecation warnings từ dependency test client.
- `python -m ruff check . --output-format concise`: pass.
- `python -m ruff format --check . --output-format concise`: fail, 17 files cần format, 41 files đã đúng. CI có bước format check nên trạng thái “Ruff pass” chưa tương đương CI pass.
- Đọc lại raw Orange qua loader hiện có và tính contingency tables, không fit mô hình mới.
- Không chạy Docker, không train lại, không thay model/report cũ, không liên hệ tác giả hoặc doanh nghiệp.

## 3. Phát hiện theo mức ưu tiên

### F01 — P0: giả định assignment của Orange chưa được bảo vệ

`src/telco_churn/orange_benchmark.py:379`, `model_tournament.py:206` và các module stability/tuning lấy `propensity = treatment.mean()` trong development. Metadata và config gọi evaluator là `known-propensity IPW`. Đây là tỷ lệ quan sát được, không phải log xác suất phân bổ từng campaign/customer.

Đối chiếu raw file đúng MD5 `bd328613c1c4ef793ab04cd4dd1c6db0`:

| FACTOR18=V7 | Control | Treatment |
|---|---:|---:|
| Số hàng | 922 / 2.886 | 4.466 / 9.010 |
| Tỷ lệ | 31,947% | 49,567% |
| Chênh lệch treatment − control | | 17,620 điểm % |

Pearson chi-square cho V7 versus các mức còn lại: 273,873; p ≈ 1,62 × 10⁻⁶¹ dưới null độc lập theo hàng. Kiểm định toàn bộ FACTOR18: p ≈ 7,35 × 10⁻⁶⁰; FACTOR4: p ≈ 1,16 × 10⁻⁶². Điều chỉnh Bonferroni cho 18 categorical features không làm mất tín hiệu này. Đây không phải một SMD lớn đơn lẻ có thể bỏ qua chỉ vì đã xét nhiều biến.

Bài gốc mô tả randomization trong từng campaign và báo kiểm tra dự đoán treatment dựa trên Hamming loss không có ý nghĩa thống kê. Tuy nhiên Hamming loss tại threshold 0,5 có thể không phát hiện dependence khi treatment là lớp đa số ở mọi phân nhóm. Đây là lý do cần ROC-AUC/log-loss và permutation test bổ sung, không phải kết luận tác giả đã làm sai. [Dataset paper](https://arxiv.org/html/2312.07206v1)

Các khả năng cần phân biệt: tỷ lệ treatment khác nhau giữa các campaign có population khác nhau; preselection/sampling sau randomization; feature chưa thực sự pre-treatment; khác biệt phiên bản dữ liệu; hoặc assignment không đồng nhất. Chưa biết khả năng nào đúng. Thiếu customer/campaign IDs cũng khiến p-value theo hàng không tính được dependence thật; số liệu trên là diagnostic đối với giả định pooled IID, không là phán quyết về thiết kế từng campaign.

Hệ quả: ATE thô và IPW hằng số không được mặc định là unbiased causal estimates trên pool. DR chỉ còn đảm bảo trong điều kiện nhận diện và nuisance phù hợp; “DR” không tự sửa unmeasured campaign confounding. Giữ Orange làm benchmark có điều kiện và đối tượng sensitivity analysis. Ước lượng `e(X)` là phương án khảo sát dưới giả định conditional exchangeability, không phải chứng nhận đã khôi phục RCT.

### F02 — P1: CI từ repeats đang bị dùng quá mức

`model_tournament.py:132` tính Student-t interval trên metric của 3 repeats; `:142` dùng CI của paired delta để chọn causal replacement. Các repeats cùng khách hàng/outcomes. Khoảng này chủ yếu phản ánh variation do chia fold/seed trên dataset đã có, không phải uncertainty khi lấy một quần thể/campaign mới. Tăng repeats có thể làm CI hẹp mà không thêm một churn event.

Thay bằng ba loại báo cáo riêng: variation theo seed; uncertainty của policy đã cố định trên evaluation độc lập; uncertainty của toàn bộ quá trình chọn mô hình qua outer validation/refit. Không gọi win-rate 3/3 hoặc 5/5 là xác suất mô hình thắng ngoài thực tế. [Bengio & Grandvalet](https://www.iro.umontreal.ca/~lisa/pointeurs/grandvalet04a.pdf)

### F03 — P1: adaptive selection và kết luận “rejected” chưa tương xứng

`configs/orange_experiments.toml` đánh dấu nhiều giả thuyết là `rejected` dù bằng chứng chính là không thắng baseline trên repeated development scores. “Chưa thấy cải thiện với cấu hình và dữ liệu này” khác với “bác bỏ khả năng phương pháp có lợi”.

IBM chọn hyperparameters trên toàn development trước khi chạy `_stability_scores` và `_calibration_candidates` (`train.py:73,109,148`). Đó không phải nested evaluation của toàn bộ selection procedure. Frozen test còn giá trị cho quyết định ban đầu nếu thực sự chỉ được dùng sau lựa chọn; không thể dùng lại test đã xem để xác nhận V3. Các bảng test của nhiều model đã được công khai trong repo.

Config TOML hiện đóng vai trò tài liệu: không tìm thấy loader sử dụng nó trong `src/` hoặc scripts để thực thi protocol. Metadata `test_rows_touched=0` cũng không thay thế audit lineage tự động. Cần registry có hash, danh sách run và trạng thái data access thực tế.

### F04 — P1: launch gate chưa đo đúng giá trị quyết định

`orange_benchmark.py:557` yêu cầu ≥20 churn events ở mỗi selected arm. Đây là heuristic, không phải bằng chứng CI có coverage đúng; treatment rất hiệu quả còn có thể giảm số event của treatment arm. Qini toàn curve dương không chứng minh policy tốt ở capacity vận hành. Hai CI DR/IPW cùng dương là điều kiện bảo thủ nhưng chưa có đánh giá Type I error/power của toàn bộ gate.

Cần primary metric tại ngân sách cố định, minimum practical improvement và comparator cụ thể. Phân biệt `INVALID_EVIDENCE`, `INCONCLUSIVE`, `NOT_COST_EFFECTIVE`, `HARMFUL`, `ELIGIBLE_FOR_PILOT`. `NO_LAUNCH` là hành động, không tự nó là khám phá khoa học hay giá trị khách hàng đã chứng minh.

### F05 — P1: temporal value hiện là một bước trên trạng thái do logging policy tạo ra

`temporal_lab.py:117` chọn top-K trên bảng nhiều tháng gộp lại. Cách đó cho phép capacity dịch chuyển giữa tháng và ranking dựa trên pool tương lai; không tương đương mỗi tháng có một ngân sách độc lập. `_rolling_backtest` xử lý từng tháng nhưng chỉ chạy policy đã chọn, hiện là no-contact; chưa so đầy đủ ứng viên dưới cùng monthly constraints.

`simulation.py:144` dùng `true_cate × gross_margin_6m − 4`. Khi cộng các proxy sáu tháng trên cùng khách ở nhiều tháng, đó không phải discounted realized cash flow của một rollout policy. Quỹ đạo churn/risk set/history đã sinh dưới treatment Bernoulli 0,5; thay policy sẽ thay quỹ đạo đó. Giá trị −2.813/+1.133 là one-step mechanism readout của simulator này, không là long-run ROI.

Khắc phục thiết kế: monthly allocation; oracle có cùng capacity/cooldown; hai endpoint riêng `one_step_value` và `trajectory_cashflow`; mô phỏng lại toàn bộ trajectory dưới từng policy bằng common random numbers và nhiều world seeds.

### F06 — P1: oracle đang có nhiều thông tin hơn learner

Generator dùng latent price sensitivity, latent loyalty và noise chưa quan sát để sinh p0/p1. `true_cate_prevented_churn` là hiệu ứng điều kiện trên trạng thái đầy đủ của generator, không tự động bằng CATE điều kiện trên `TEMPORAL_FEATURES`. Vì thế `pehe` hiện tại và gap với oracle có cả irreducible information gap.

Cần hai oracle: oracle full-state và oracle chỉ biết các feature được phép. Với thiết kế DGP, tính CATE theo observed X bằng tích phân/Monte Carlo trên latent state hoặc có track fully observed riêng. Không gán toàn bộ gap với full-state oracle cho lỗi mô hình. Joint potential outcomes sinh bằng cùng uniform draw cũng là lựa chọn cơ chế; thử thêm coupling khác khi nghiên cứu realized individual harm.

### F07 — P1: kiểm tra point-in-time còn là allowlist

`validate_point_in_time_schema` chỉ ngăn cột oracle/treatment/label và kiểm tra cột thiếu. Simulator flat table chưa có `event_at`, `available_at`, `label_available_at`, source corrections. Nó chứng minh thứ tự tạo feature trong DGP hiện tại, chưa chứng minh pipeline chống late-arriving data hoặc label-delay leakage.

### F08 — P1: horizon công khai của API mạnh hơn chứng cứ dữ liệu

`api.py:145`, `batch.py:33`, `policy.py:90` trả `risk_30d`; IBM data card đã thừa nhận không có prediction timestamp/horizon để xác nhận điều này. Metadata/output tương lai cần ghi rõ `score_target`, horizon được xác thực hay chỉ giả định, population và evidence tier.

API chỉ load `champion.joblib` theo schema IBM. `orange_retention_policy.joblib` chưa nối vào serving workflow. SQL chưa có bảng assignment/propensity/delivery/outcome; không tìm thấy code ghi Postgres trong `src/`. Sơ đồ V2 là kiến trúc đề xuất, chưa là end-to-end implementation.

### F09 — P2: ablation còn confound giữa thuật toán và biểu diễn

- Risk RF bật `balanced_subsample`, các risk learners khác không dùng cùng weighting: so family đã trộn cả lựa chọn loss/weight.
- HGB nhận ordinal categorical như số có thứ tự trong pipeline hiện tại; CatBoost nhận native categories. Cần so representation × learner thay vì quy mọi khác biệt cho thuật toán.
- S-logistic chỉ tạo interaction treatment với numeric, chưa với categorical. Không thể kết luận shared model thất bại trước khi kiểm nghiệm treatment × category.
- Component evaluator chọn theo pooled factual Brier, có thể che chất lượng control arm nhỏ. Cần Brier/log-loss từng arm, variance influence score và policy delta uncertainty.
- `_component_winners` xếp theo worst-evaluator mean Qini; config mô tả thêm one-SE nhưng function đó chưa thực thi one-SE. Worst-of-three point estimates là stress audit, không phải robust confidence bound.

### F10 — P2: lỗi tiềm ẩn khi mở rộng dữ liệu

`CatBoostFrameClassifier._prepare` tại `uplift.py:52` điền numeric missing bằng median của dataframe đang predict. Một khách có thể nhận score khác nếu đổi các khách đi cùng batch. Orange không có missing nên không khẳng định artifact hiện tại đã bị ảnh hưởng. Trước dataset mới phải fit imputation state trên train hoặc dùng native missing support có contract rõ ràng.

`curve_metrics` chưa thêm điểm gốc (0,0) khi tích phân; tie handling theo thứ tự hàng khác tie-break ID ở top-K. Sai lệch điểm gốc nhỏ khi N lớn, nhưng cần invariant tests và convention thống nhất để so thư viện. `bootstrap_selected_effect` resample các pseudo-outcomes selected đã cố định: phải ghi rõ conditional evaluation, chưa gồm uncertainty của training/selection/threshold và cluster chưa biết.

### F11 — P2: tính tái lập và tests chưa bao phủ failure modes nghiên cứu

28 tests hiện hữu hữu ích nhưng chưa kiểm: null-effect false launch; CI coverage; nonconstant propensity; label maturity; budget theo tháng/channel; same-customer batching; cohort missing outcomes; multi-action feasibility; policy replay. Dependency ranges chưa là environment lock. `run_research.ps1` chưa kiểm `$LASTEXITCODE` sau mỗi native process, có thể báo hoàn tất sau một command lỗi trong môi trường PowerShell tương ứng.

### F12 — P2: tài liệu cần chỉnh claims và nguồn

`MODEL_TOURNAMENT.md` ghi sai authors/DOI cho paper evaluation: tác giả là Björn Bokelmann và Stefan Lessmann, DOI đúng `10.1016/j.ejor.2023.09.018`, không phải `...2023.07.037`. [Bản tác giả](https://arxiv.org/abs/2210.02152)

`RESEARCH_V2`/progress đề xuất frozen IBM model transfer sang Iranian: schema không giống nhau, không có mapping semantic đầy đủ để chuyển model trực tiếp. Chỉ có thể benchmark cùng phương pháp với refit độc lập; đó là replication trên dataset khác, không đo transfer degradation của model IBM. Iranian cũng không cho phép tự thay đổi planning gap vì public file đã aggregate một horizon cố định.

## 4. Nghiên cứu dẫn đến các lựa chọn V3

Các thiết kế thử nghiệm trong bộ tài liệu đi kèm là đề xuất của review này, chưa phải kết quả mới. Không gọi việc ghép các phương pháp có sẵn là thuật toán đầu tiên trên thế giới. Những nguồn dưới đây được kiểm tra từ paper/tác giả/nhà phát hành trong ngày 19–20/09/2026; đường dẫn arXiv có thể là bản tác giả của bài đã xuất bản, không mặc định là nghiên cứu chưa qua phản biện.

| Nguồn gốc | Điều sử dụng trong V3 | Điều không suy ra |
|---|---|---|
| [Fernández-Loría & Provost, JMLR 2022](https://www.jmlr.org/papers/v23/19-480.html) | So risk proxy với effect estimation theo chất lượng quyết định; vẽ vùng điều kiện mỗi cách thắng | Risk thắng Orange không chứng minh causal methods vô dụng |
| [Bokelmann & Lessmann, evaluation](https://arxiv.org/abs/2210.02152) | So adjustment/IPW/DR bằng variance, coverage và decision error | DR luôn giảm variance trong mọi small sample |
| [Yadlowsky et al., RATE](https://arxiv.org/abs/2111.07966) và [GRF](https://grf-labs.github.io/grf/articles/rate.html) | TOC/RATE cho ưu tiên treatment; test heterogeneity trên evaluation độc lập | RATE dương đồng nghĩa profit dương |
| [Van Der Laan et al., ICML 2023](https://proceedings.mlr.press/v202/van-der-laan23a.html) | Causal calibration và cross-calibration cho effect magnitude | Calibration xác suất churn đủ để calibrate CATE |
| [Athey & Wager, policy learning](https://arxiv.org/abs/1702.02896) và [policytree](https://github.com/grf-labs/policytree) | DR empirical welfare với policy tree nhỏ làm đối chứng direct policy learning | Tree tối ưu trên train sẽ tạo value tốt trên test |
| [Sverdrup et al., multi-arm Qini](https://arxiv.org/abs/2306.11979) và [MAQ](https://grf-labs.github.io/maq/reference/maq.html) | Budget-value curve với nhiều action/cost; đối chiếu solver trong trường hợp assumptions phù hợp | Ratio greedy luôn tối ưu cho integer/channel/cooldown constraints |
| [Lemmens & Gupta, Marketing Science 2020](https://pubsonline.informs.org/doi/abs/10.1287/mksc.2020.1229) | Tối ưu incremental cash flow và campaign size | Có thể thay cash flow bằng monthly fee tùy ý |
| [Bokelmann & Lessmann, HS sampling, 2025](https://doi.org/10.1016/j.ejor.2025.02.030), [preprint](https://arxiv.org/abs/2401.14294) | So thiết kế lấy mẫu theo heteroskedasticity với random sampling dưới cùng cost | Tăng sampling risk cao mà bỏ inclusion weights vẫn giữ cùng estimand |
| [Haupt et al., supervised randomization](https://arxiv.org/abs/1910.00393) | So allocation ưu tiên policy hiện hành với uniform exploration; log xác suất | Logging policy tất định đủ overlap cho mọi challenger |
| [Microsoft, variance reduction](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/deep-dive-into-variance-reduction/) | CUPED/CUPAC khi có pre-period outcome/proxy hợp lệ | Churn pre-period luôn hữu ích: trong active risk set biến này có thể gần như hằng 0 |
| [Howard et al., Annals of Statistics 2021](https://arxiv.org/abs/1810.08240) | Confidence sequences cho monitoring liên tục, sau khi xác định bounded score/predictable nuisance/delay assumptions | CI 95% thông thường vẫn đúng khi nhìn mỗi ngày và dừng tùy ý |
| [Kallus et al., ICML 2022](https://proceedings.mlr.press/v162/kallus22a.html) | Robust OPE/policy như nhánh nâng cao khi có shift model rõ | Lấy min của ba evaluators là một DRO estimator có bảo đảm |
| [Wang et al., concept drift, ICML 2025](https://proceedings.mlr.press/v267/wang25cm.html) | Phân biệt thay đổi P(X) và thay đổi outcome conditional để chọn adaptation | Reweight X tự sửa được treatment-effect sign reversal |
| [Hollmann et al., Nature 2025](https://www.nature.com/articles/s41586-024-08328-6) | TabPFN là optional outcome nuisance challenger trong small-data track; so cả calibration và compute | Predictive superiority suy ra causal superiority; paper không bảo đảm cho Orange |
| [Shalit et al., ICML 2017](https://proceedings.mlr.press/v70/shalit17a.html) và [Shi et al., Dragonnet, NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/hash/8fb5f8be2aa9d6c64a04e3ab9f63feee-Abstract.html) | Optional shared-representation/targeted-loss ablations ở large-data track | Representation learning tự loại được unmeasured confounding |
| [scikit-survival evaluation](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html) | IBS/IPCW Brier, time-dependent AUC, Uno C-index khi có event time/censoring | Một C-index cao đủ chứng minh xác suất 60/180 ngày đúng |

## 5. Dataset portfolio được chọn theo câu hỏi

| Dataset | Quyết định | Thí nghiệm có căn cứ | Giới hạn cần giữ |
|---|---|---|---|
| Orange/OpenML 45580 | Giữ, ưu tiên audit trước | Pooled randomization integrity; low-event estimator sensitivity; reproduction | Thiếu campaign/customer/time/cost, identification chưa giải quyết |
| [Hillstrom, nguồn tác giả](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html) | Dataset mới ưu tiên 1 | 64.000 khách, ba arms; compare no-email/mens/womens; visit, conversion và spend sau hai tuần; multi-action và outcome mismatch | Retail/email; spend không phải profit; không suy ra telco effect; xác minh điều kiện tải/tái phân phối |
| [Criteo unbiased](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) | Dataset mới ưu tiên 2 | 13.979.592 rows, treatment 85%, conversion 0,292%; learning curves, rare outcome, scalability | Dùng bản sửa advertiser leakage; exposure là hậu assignment, không dùng như feature trước quyết định; không có customer margin |
| [KKBox](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge) | Nhánh temporal khi truy cập được | Billing/log feature pipeline, label horizon/maturity, temporal prediction và survival nếu dựng được event definitions | Cần account/terms; không treatment; không hứa survival benchmark trước khi audit censoring |
| [Iranian/UCI](https://archive.ics.uci.edu/dataset/563/iranian%2Bchurn%2Bdataset) | Optional lightweight replication | 3.150 customers, aggregates 9 tháng, label cuối tháng 12; refit cùng learner families | Một planning gap cố định; không temporal panel, không causal, không transfer trực tiếp model IBM |
| IBM | Giữ làm compatibility baseline | Schema/inference regression; predictive teaching | Không làm trung tâm novelty |
| Synthetic relational + semi-synthetic | Bắt buộc cho mechanisms/coverage | Known effects, null controls, shift, delayed labels, costs, action replay | Semi-synthetic chỉ giữ X thực; outcome/effect do thiết kế vẫn là synthetic evidence |

Không gộp Orange, Hillstrom và Criteo thành một tập train có cột giả định tương đương. Dùng chung protocol/adapters và báo kết quả theo từng domain. Criteo subsampling phải dùng row hash/seed độc lập outcome; nếu lấy mẫu khác theo treatment/outcome phải lưu inclusion probabilities và đánh giá trên distribution mục tiêu.

## 6. Tiêu chuẩn viết nhận xét từ đây

Mỗi nhận xét phải có: population/horizon; comparator; effect size và đơn vị; interval và phương pháp uncertainty; số khách/event/cluster; budget; evidence tier; điều kiện sai; hành động tiếp theo. Tách số quan sát, giả định kinh tế, mục tiêu đề xuất và kết quả synthetic.

Ví dụ được phép: “Trong simulation S07, sau sign reversal, policy A giảm expected loss so với B ở cùng monthly budget; interval qua world seeds còn chứa 0 nên chưa chọn A. Cần tăng số worlds hoặc đơn giản hóa policy.”

Ví dụ không được phép: “Mô hình thông minh nâng cao trải nghiệm, giúp doanh nghiệp tối ưu retention”; “NO_LAUNCH chứng minh giá trị thực tế”; “X-learner bị bác bỏ”; “chỉ dự án này giải quyết được”. Tính khác biệt phải được chứng minh bằng benchmark và pilot, không bằng lời mô tả.
