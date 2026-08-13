# Nghiên cứu nhân quả mới nhất và kế hoạch thực nghiệm 2026

Ngày khóa rà soát: **2026-08-09**  
Outcome duy nhất trong phạm vi chính: **`conversion`**  
Estimand: **conditional ITT của randomized targeting assignment**, thang absolute probability difference  
Protocol máy đọc được: [`top_tail_research_protocol_v2.json`](../configs/top_tail_research_protocol_v2.json)  
Kết quả audit: [`TOP_TAIL_RESEARCH_V2_REPORT.md`](../report/TOP_TAIL_RESEARCH_V2_REPORT.md)

## 1. Kết luận điều hành

Không có nghiên cứu 2024–2026 nào chứng minh rằng chỉ cần thay một biến thể Causal Forest mới là sẽ thắng
trên Criteo `conversion` hiếm, assignment 85/15 và hard budget 1–2%. Bằng chứng mới đưa đến thứ tự ưu
tiên khác:

1. giữ đánh giá ITT trên factual randomized outcomes và sửa winner's curse/multiplicity trước;
2. tận dụng baseline risk mạnh nhưng để dữ liệu **học mức shrinkage của causal score**;
3. kiểm tra direct-ranking objective sau khi hybrid đã có baseline công bằng;
4. chỉ tối ưu forest sau khi nền tảng leakage, synthetic truth, provenance và inference hoàn tất.

Điểm quan trọng nhất của dữ liệu hiện tại là Response thắng không nhất thiết có nghĩa learner nhân quả sai.
Nếu treatment effect gần hằng trên log-odds, với outcome hiếm:

```text
tau_RD(x)
  = expit[logit(mu0(x)) + beta] - mu0(x)
  ≈ mu0(x) [exp(beta) - 1].
```

Khi đó absolute benefit tự nhiên tăng theo baseline risk. Một hybrid phải có khả năng giữ cấu trúc này và
shrink phần CATE nhiễu về 0; tăng độ phức tạp forest không giải quyết được vấn đề đó.

## 2. Ledger nguồn mới và mức chuyển giao

Chỉ dùng paper/trang xuất bản gốc. `Peer-reviewed` và `preprint` được tách rõ; ngày của arXiv là ngày bản
đang đọc, không được gọi là ngày xuất bản peer-reviewed.

| Nguồn | Trạng thái đến 2026-08-09 | Kết quả dùng được | Giới hạn khi chuyển sang dự án |
|---|---|---|---|
| [Athey, Keleher & Spiess, *Machine Learning Who to Nudge*](https://arxiv.org/abs/2310.08672) | Journal of Econometrics 2025; arXiv v2 2024 | Hybrid logit kết hợp control-risk và CATE OOF, tự học shrinkage | Outcome nền khoảng 37%, policy chủ yếu ở budget lớn; cohort 2018 mới có 86% treated. Không phải bằng chứng cho rare `conversion` top 1–2% |
| [Gao & Hastie, DINA](https://academic.oup.com/biometrics/article/81/4/ujaf162/8403946) | Biometrics 81(4), 24-12-2025 | Natural-parameter effect và orthogonal nuisance cho binary outcome | Log-odds heterogeneity không tự đồng nghĩa absolute-ITT ranking tốt |
| [Chernozhukov et al., *Policy Learning with Confidence*](https://arxiv.org/abs/2502.10653) | Preprint v3, 18-01-2026 | Chọn policy bằng simultaneous lower confidence bound thay vì point estimate | Không cứu leakage hoặc policy family được thêm sau khi đọc holdout |
| [Schuessler, Sverdrup & Tibshirani, HTE pretraining](https://arxiv.org/abs/2505.00310) | Preprint v2, 18-06-2025 | Dùng prognostic support làm prior mềm cho R-learner/forest | Có thể hại khi prognostic support và effect support tách rời; paper chủ yếu simulation nhỏ |
| [Asiaee et al., RACER/R-OSCAR](https://arxiv.org/abs/2306.17478) | Preprint v3, 09-07-2026 | CMO augmentation tối thiểu hóa conditional variance; cross-fitting | Nhánh mượn observational data chưa áp dụng. Trong RCT, CMO signal đã đồng nhất đại số với DR signal hiện có |
| [Kamran, Makar & Wiens, direct ranking tree](https://proceedings.mlr.press/v238/kamran24a.html) | AISTATS 2024 | Ranking có thể phù hợp allocation hơn CATE MSE; split theo global AUTOC | Chỉ synthetic, n nhỏ, budget 10–50%; objective 1–2% là extension mới |
| [Arno et al., Rank-Learner](https://arxiv.org/abs/2602.03517) | ICML 2026 accepted; arXiv v2 26-05-2026 | Pairwise orthogonal ranking objective | Criteo experiment của paper dùng `visit` và sampling khác; ba biến thể repo đã không thắng nên không retry nếu không có giả thuyết mới |
| [Bokelmann & Lessmann, heteroscedastic sampling](https://arxiv.org/abs/2401.14294) | EJOR 2025; arXiv 2024 | Sampling theo noise có thể tăng precision, có thí nghiệm Criteo `conversion` | Can thiệp thiết kế RCT trước khi thu outcome; không thể hậu kỳ tạo thêm control events |
| [Rudaś & Jaroszewicz, class flipping](https://arxiv.org/abs/2412.10009) | Preprint v1, 13-12-2024 | Biến đổi label cho class imbalance giữ uplift theo hệ số biết trước | Criteo paper dùng `visit`; chưa có bảo đảm finite-sample top-tail |
| [Zhu et al., PUC/PUL](https://proceedings.mlr.press/v267/zhu25s.html) | ICML 2025 | Chẩn đoán mất cân bằng positive/negative trong Qini/uplift ranking | Real Criteo dùng `visit`; PUC không phải factual AIPW policy value và không có simultaneous selection inference |
| [Casacuberta & Hardt, *Good Allocations from Bad Estimates*](https://arxiv.org/abs/2601.05597) | Preprint 09-01-2026 | Coarse effects có thể đủ cho near-optimal allocation | Lý thuyết strata rời rạc; phải đo mass/stability gần cutoff cực đoan |
| [Shirvaikar et al., relative-risk causal forest](https://arxiv.org/abs/2309.15793) | Preprint v3, 08-06-2025 | Forest split trực tiếp theo relative-risk heterogeneity | Không cùng absolute-ITT policy estimand; GLM ở node hiếm dễ bất ổn |
| [Gao, relative CATE error](https://proceedings.mlr.press/v258/gao25d.html) | AISTATS 2025 | Paired comparison hai CATE estimator có thể hẹp hơn absolute-risk assessment | Là secondary CATE-scale test, không thay hard-budget policy inference |
| [Bastani, Bastani & McLaughlin, winner's curse](https://arxiv.org/abs/2602.08892) | Preprint 09-02-2026 | Model-based counterfactual evaluation có thể lạc quan dù sample splitting/RCT | Không phê phán held-out factual IPW/AIPW của policy đã đóng băng; vì vậy pipeline phải dùng factual outcome |

Hai cảnh báo về khả năng chuyển giao:

- `visit` không phải proxy có thể thay thế `conversion`. Paper dùng Criteo nhưng đổi outcome không được xem là
  replication cho dự án này.
- Kết quả whole-curve AUQC/AUTOC không tự áp dụng cho hard budget 1–2%. Budget là một phần của estimand
  quyết định, không phải hyperparameter được chọn sau khi nhìn đường cong.

## 3. Chẩn đoán dữ liệu quyết định thiết kế model

Full development có 5.591.836 dòng nhưng chỉ 1.625 conversion ở control. Screen 15% có 838.776 dòng và
244 control conversions. Với event rate quan sát được, assignment 85/15 có randomization-noise variance
xấp xỉ 1,65 lần 50/50 và standard error xấp xỉ 1,29 lần.

Hệ quả:

- không SMOTE, không duplicate positives, không coi row count là effective causal sample size;
- inner/outer fold phải stratify đồng thời theo treatment và outcome, đồng thời kiểm event support từng arm;
- mọi preprocessing, sentinel rule, nuisance, calibration và shrinkage phải fit trong training fold;
- `visit`/`exposure` bị cấm làm feature vì xảy ra sau assignment;
- hard top-k phải báo số row, treated/control row, treated/control event và tie tại cutoff;
- hai fold seed trên cùng source rows chỉ đo training instability, không phải hai replication độc lập.

### 3.1 DR signal hiện có đã là RCT-CMO signal

Đặt `A=2T-1`, `pi_A=e` nếu treated và `1-e` nếu control, và

```text
m_CMO(x) = (1-e) mu1(x) + e mu0(x).
```

Khi dùng cùng `mu0`, `mu1`:

```text
A [Y-m_CMO(X)] / pi_A
  = mu1-mu0 + T(Y-mu1)/e - (1-T)(Y-mu0)/(1-e).
```

Vế phải chính là `doubly_robust_effect_signal` của repo. Vì vậy không thêm một candidate RACER trùng
đại số. `adjusted_signal` dùng pooled mean `e*mu1+(1-e)*mu0` vẫn unbiased nhưng không phải CMO tối ưu ở
`e=0,85`; giữ nó như diagnostic lịch sử, không dùng để tuyên bố một learner mới.

## 4. Kế hoạch xử lý dữ liệu fail-closed

### P0 — khóa dữ liệu và estimand

1. Khóa `outcome=conversion`, `propensity=0.85`, feature `f0..f11` trước treatment.
2. Tách rõ `retrospective audit`, `synthetic validation`, `future screen`, `new randomized confirmation`.
3. Existing Sprint 2 confirmation và screen đã đọc không được tái gắn nhãn thành holdout xác nhận.
4. Ghi SHA của protocol, source index, input NPZ/manifest, config từng score và code state.
5. Không ghi đè output namespace; partial run phải dùng attempt namespace mới.

### P1 — cross-fitting theo event

1. Outer 3-fold, seed 101/202, stratify `(treatment, conversion)`.
2. Với hybrid/pretraining, tạo inner folds bên trong mỗi outer-train; không stack trực tiếp các outer-OOF
   score vì score của fold khác đã được fit với row đang calibration.
3. Fit control-risk model chỉ từ control rows của inner-train; log số positive thực tế.
4. Clip probability bằng ngưỡng khóa trước và ghi clip fraction. Artifact screen cho thấy clipping DINA
   không phải chi tiết không đáng kể, vì vậy threshold không được chọn sau khi xem real data.

### P2 — support và cutoff

1. Hard budget dùng đúng `k=floor(n*b)` và deterministic stable sort.
2. Báo `boundary_tie_size`, membership overlap/Jaccard giữa seed.
3. Gate tương lai: ít nhất 100 control tail events và overlap tối thiểu 0,75.
4. Nếu mass gần cutoff lớn hoặc overlap thấp, chuyển sang coarse/event-safe strata trước khi thử model phức tạp.

## 5. Kế hoạch model theo thứ tự

### M0 — baselines bắt buộc

- zero effect và constant ATE;
- Response hiện tại;
- raw Binary DINA;
- baseline-logit-only, raw hybrid input và các sentinel ablation đã đăng ký.

Không model mới nào được so với một baseline yếu hơn Response.

### M1 — hybrid prognostic–causal logit, ưu tiên cao nhất

Trong mỗi outer-train, tạo inner-OOF control risk `fhat(x)` và CATE `tauhat(x)`, sau đó:

```text
f_tilde = logit(clip(fhat))
g_tilde = logit(clip(fhat + tauhat)) - logit(clip(fhat))

logit P(Y=1 | X,T)
  = a + a_f f_tilde + a_g g_tilde
    + [b + b_f f_tilde + b_g g_tilde] T.
```

Score triển khai là `expit(eta1)-expit(eta0)`. Sáu hệ số được fit chỉ trên inner-OOF inputs của
outer-train. Hai ablation bắt buộc:

- Eq.2 baseline-only: chỉ control-risk và treatment coefficient;
- Eq.3 hybrid: cho causal component tự shrink.

Nếu hệ số của `g_tilde` gần 0 và hybrid không vượt baseline-logit trên synthetic/holdout, kết luận hợp lý là
CATE signal chưa nhận diện được, không phải tiếp tục tăng forest depth.

### M2 — prognostic pretraining cho R-learner

Dùng prognostic feature importance làm penalty/sampling prior mềm, không hard feature selection. Chỉ tiếp tục
nếu thắng hoặc hòa standard R ở cả DGP shared-support và disjoint-support. Failure trên disjoint-support là
hard stop vì nó chứng minh prognostic prior đã loại moderator thật.

### M3 — direct ranking objective

Replicate AUTOC ranking tree trước trên đúng công thức DR sign convention của repo. Chỉ sau replication mới
thử tail-weighted objective. Tail 1–2% objective là contribution mới và phải được ghi như vậy; không gán
cho paper gốc.

### M4 — rare-outcome sensitivity

Class flipping chỉ là ablation huấn luyện cho modified-outcome learner. Giữ nguyên labels gốc cho factual
evaluation, báo hệ số scale và kiểm tra finite-sample variance. Nếu chỉ cải thiện AUQC trên `visit` hoặc
whole curve thì không advance.

### M5 — causal forest, để vòng Kaggle sau

Sau khi M1–M4 và protocol platform ổn định, mới ablate:

- event-aware minimum treated/control positives trong leaf;
- honest fraction và parent/global shrinkage;
- prognostic-biased feature sampling nhưng có disjoint-support sentinel DGP;
- relative-risk split chỉ làm heterogeneity diagnostic;
- absolute-ITT policy value vẫn là champion metric.

## 6. Ma trận synthetic bắt buộc

Chạy `e∈{0,5; 0,85}`, base rate `{0,002; 0,01; 0,05}` và hai mức expected control events tương ứng
screen/full. DGP:

1. null CATE;
2. constant risk difference;
3. constant log-odds effect;
4. effect cùng hướng baseline risk;
5. effect ngược hướng baseline risk;
6. prognostic và causal support hoàn toàn tách rời;
7. step subgroup;
8. uplift chỉ tồn tại trong top 1–2%;
9. nuisance misspecification và probability-boundary stress.

Truth invariant bắt buộc: sau mọi probability clipping, `tau == mu1-mu0`. Mỗi model được chấm bằng true
RD-PEHE, rank correlation, oracle top-1/2% regret, false heterogeneity ở null, overlap, clip fraction và
paired interval coverage. Monte Carlo grid nằm trong script/report, không biến thành unit test chậm.

## 7. Evaluation và inference

Với policy đóng băng `pi_jb(x)` và factual RCT holdout:

```text
Gamma_i = mu1_i-mu0_i
          + T_i/e (Y_i-mu1_i)
          - (1-T_i)/(1-e) (Y_i-mu0_i)

psi_jb = mean[pi_jb(X_i) Gamma_i].
```

Các policy dùng cùng rows và cùng bootstrap multiplicities để giữ paired covariance. Với nhiều
candidate × budget, dùng maximum-standardized bootstrap-deviation band cho toàn family. Future selection
dùng nguyên tắc PoLeCe: tối đa hóa simultaneous lower confidence bound, không tối đa hóa point estimate.

Promotion chỉ hợp lệ khi:

1. family, seed, budget và model configs được khóa trước;
2. simultaneous one-sided lower bound của delta so với Response lớn hơn 0;
3. dấu ổn định qua registered folds/seeds;
4. không tạo heterogeneity giả ở null/constant DGP;
5. không hỏng disjoint-support DGP;
6. đạt event-support và overlap gate;
7. có randomized confirmation mới.

Pointwise CI, Qini, PUC, pROCini, RATE/AUTOC, calibration và Gao relative CATE error là evidence phụ; chúng
không override primary hard-budget ITT gate.

## 8. Kết quả audit đã chạy và quyết định hiện tại

Retrospective family gồm 5 challenger × 2 seed × 2 budget = 20 cells, với 200 paired bootstrap draws.
Critical value đồng thời là `3,111821`. Cả 16 causal point deltas đều dương nhưng **không một pointwise hay
simultaneous lower bound nào vượt 0**. Minimum causal overlap là `0,6131`; minimum control events trong
causal tail là `84`.

Quyết định: giữ **Response**, không promote; chỉ mang giả thuyết sang protocol/dữ liệu randomized mới.
Chi tiết và đường dẫn artifact nằm ở
[`TOP_TAIL_RESEARCH_V2_REPORT.md`](../report/TOP_TAIL_RESEARCH_V2_REPORT.md).

## 9. Thứ tự thực thi

```text
research ledger + estimand lock
  -> synthetic truth/inference tests
  -> hybrid Eq.2/Eq.3 structural implementation
  -> smoke code path (không chọn model)
  -> frozen future screen
  -> PoLeCe/max-bootstrap family gate
  -> one locked business budget
  -> new randomized confirmation
  -> causal-forest Kaggle ablations
```

Không chạy lại Causal Forest trong vòng nền tảng này. Đó là trì hoãn có chủ đích để tránh dùng screen đã
đọc như một tuning loop, không phải kết luận rằng forest không thể cải thiện.
