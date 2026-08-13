# Deep research dossier — bài toán nhân quả trên Criteo conversion

Ngày rà soát: 2026-08-09  
Trạng thái: follow-up `top-tail-research-v2` đã chạy retrospective inference; chưa fit model mới trên Criteo  
Nguồn số nội bộ: [causal foundation report](../report/CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md),
[`budget_deltas.csv`](../output/improvement/causal_foundation_analysis/budget_deltas.csv) và
[`run_manifest.json`](../output/improvement/causal_foundation_finalist_seed101/run_manifest.json)

> **Cập nhật sau dossier:** paired simultaneous audit cho family 20 cells đã hoàn tất. Cả 16 causal
> point deltas đều dương, nhưng 0/16 pointwise và 0/16 simultaneous lower bounds vượt 0; minimum causal
> overlap là 61,31% và minimum control tail events là 84. Vì vậy champion vẫn là Response. Xem
> [research/experiment plan mới nhất](LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md) và
> [báo cáo top-tail v2](../report/TOP_TAIL_RESEARCH_V2_REPORT.md).

## 0. Kết luận điều hành

Kết quả hiện tại không nói rằng “model nhân quả không thể cải thiện”. Nó nói rằng dự án đang
giải đồng thời bốn bài toán khác nhau nhưng chưa tách estimand đủ chặt:

1. **Nhận dạng:** hiệu ứng của việc được gán vào nhóm có thể được target quảng cáo;
2. **Ước lượng:** học `tau(x)` khi conversion hiếm và control chỉ chiếm 15%;
3. **Xếp hạng:** đưa đúng người có hiệu ứng lớn lên đầu score;
4. **Quyết định:** tối đa hóa incremental conversion dưới một budget cụ thể.

RCT làm lớp 1 tương đối mạnh. Nút thắt nằm ở lớp 2–4. Với outcome hiếm, một score có CATE
calibration tốt hơn chưa chắc có policy tốt hơn; một score không phải CATE như Response vẫn có
thể xếp hạng tốt nếu baseline risk là proxy ổn định của treatment benefit. Ngược lại, một causal
learner có thể tốt ở top 1–2% nhưng thua khi lấy diện tích 1–30%. Đây không phải mâu thuẫn: hai
metric trả lời hai quyết định khác nhau.

Ba kết luận mới quan trọng nhất:

- **5,59 triệu dòng không tương đương 5,59 triệu đơn vị thông tin nhân quả.** Full-development
  chỉ có 1.625 control conversions. Với event rate quan sát được, thiết kế 85/15 làm phần
  randomization-noise variance xấp xỉ 1,65 lần thiết kế 50/50 và 1,67 lần phân bổ Neyman gần
  tối ưu; sai số chuẩn tương ứng khoảng 1,29 lần tối ưu.
- **Quan sát top 1–2% là một giả thuyết mới, chưa phải kết quả xác nhận.** Bốn causal candidate
  đều hơn Response tại 1% và 2% trên hai fold seed, nhưng các seed dùng cùng source rows,
  budget được chú ý sau khi xem kết quả, và artifact chưa có paired simultaneous interval riêng
  cho đuôi này.
- **Estimand hiện tại là ITT của assignment/targeting, không phải effect của actual exposure.**
  `exposure` là biến sau treatment. Nếu câu hỏi sản phẩm là hiệu ứng của việc thật sự nhìn thấy
  quảng cáo, cần một bài toán IV/LATE với giả định bổ sung; conditioning vào `exposure` không
  giải quyết được.

Vì vậy hướng cải tiến có giá trị nhất trước khi chạy Kaggle lại không phải thêm nhiều learner.
Cần khóa lại estimand và budget, xây inference đúng cho top-tail, rồi mới so sánh direct policy
learning và shrinkage tách prognostic/effect. Causal Forest nằm sau các bước đó.

## 1. Causal question thực sự là gì?

Ký hiệu:

- `X`: 12 feature trước treatment đã ẩn danh;
- `Z`: cột `treatment`, tức assignment vào nhóm có thể được target;
- `A`: `exposure`, tức có được phơi nhiễm quảng cáo thật hay không;
- `M`: `visit`, xảy ra sau assignment;
- `Y`: `conversion`.

Một sơ đồ tối thiểu phù hợp với mô tả dataset là:

```text
X ───────────────► M ─────► Y
│                  ▲        ▲
└──────────────────┼────────┘
                   │
Z ───────────────► A
```

Sơ đồ chỉ biểu diễn thứ tự và các đường hợp lý, không tuyên bố đã nhận dạng mediation. Criteo mô
tả dữ liệu là nhiều incrementality test, trong đó một phần dân số ngẫu nhiên bị ngăn không cho
target quảng cáo; `exposure` ghi nhận phơi nhiễm hiệu quả. Dataset còn bị subsample không đồng
đều để che mức incrementality gốc. Xem [trang dữ liệu chính thức của Criteo](https://ailab.criteo.com/criteo-uplift-prediction-dataset/).

### 1.1 Estimand đang dùng: conditional ITT

Pipeline hiện tại ước lượng:

```text
tau_Z(x) = E[Y | do(Z=1), X=x] - E[Y | do(Z=0), X=x]
```

Nếu quyết định kinh doanh là **chọn ai được đưa vào nhóm target**, đây là estimand đúng. Random
assignment nhận dạng ATE/conditional ITT trong sample phát hành, với các điều kiện consistency,
positivity, không interference và provenance randomization đúng.

### 1.2 Estimand không được nhận dạng tự động: effect của exposure

Nếu câu hỏi là:

```text
tau_A(x) = E[Y | do(A=1), X=x] - E[Y | do(A=0), X=x]
```

thì `A` không được randomize trực tiếp. So sánh người exposed với người không exposed bị selection:
khả năng thắng auction, eligibility và hành vi người dùng có thể cùng dự báo conversion.

Có thể xem `Z` như instrument cho `A`, nhưng một LATE chỉ được nhận dạng khi có ít nhất:

- independence của assignment;
- relevance: assignment làm đổi xác suất exposure;
- exclusion: assignment chỉ ảnh hưởng conversion qua exposure;
- monotonicity: không có nhóm bị assignment làm giảm exposure theo hướng trái thiết kế;
- SUTVA/không interference phù hợp.

Ngay cả khi đủ, kết quả là effect trung bình cho **compliers**, không phải ATE của exposure cho mọi
user. Đây là giới hạn cốt lõi của IV được chỉ ra bởi
[Imbens–Angrist](https://www.nber.org/papers/t0118). Repo chưa đăng ký estimand này và không được
đổi diễn giải ITT thành exposure effect.

### 1.3 Các estimand chưa có dữ liệu để trả lời

- Conditioning vào `visit` không cho direct effect hợp lệ nếu thiếu giả định mediation/sequential
  ignorability. Dùng `visit` làm feature vẫn là leakage.
- Dùng `visit` làm outcome là hợp lệ, nhưng đó là effect của targeting lên visit, không phải
  conversion. Nó chỉ nên là power diagnostic.
- Dataset không có retention trajectory, CLV hay cost/revenue quan sát. Tên dự án không làm cho
  causal retention hoặc profit được nhận dạng từ hai label hiện có.
- Vì sample bị subsample không đồng đều và không có sampling weight, ATE/CATE tuyệt đối chỉ nên
  diễn giải trong benchmark sample. Không có căn cứ để generalize calibration về population quảng
  cáo gốc.

## 2. Information bound: vì sao dữ liệu lớn vẫn thiếu tín hiệu

Với propensity đã biết `e=0,85`, một doubly robust pseudo-outcome chuẩn có dạng:

```text
Gamma = mu1(X) - mu0(X)
        + Z/e       * [Y - mu1(X)]
        - (1-Z)/(1-e) * [Y - mu0(X)]
```

Khi nuisance đúng hoặc được cross-fit phù hợp:

```text
E[Gamma | X] = tau(X)
```

Phần variance do randomization, có điều kiện trên `X`, là:

```text
Var(Gamma | X)
  = Var(Y(1) | X) / e + Var(Y(0) | X) / (1-e)
```

Đây là lý do nhánh control bị khuếch đại bởi `1/(1-e)=6,67`. Orthogonalization làm giảm bias bậc
nhất từ nuisance error; nó không xóa variance vật lý do chỉ có 15% control.

### 2.1 Phép tính từ full-development

Artifact ghi:

| Arm | Số dòng | Conversion | Event rate |
|---|---:|---:|---:|
| Treated | 4.753.061 | 14.684 | 0,00308938 |
| Control | 838.775 | 1.625 | 0,00193735 |

Lấy marginal Bernoulli variance `Vw = pw(1-pw)` làm plug-in thô cho phần noise:

```text
C(e) = V1/e + V0/(1-e)
e*   = sqrt(V1) / [sqrt(V1) + sqrt(V0)]
```

Kết quả:

| Phân bổ treated | Noise coefficient `C(e)` | So với tối ưu |
|---:|---:|---:|
| 85,0% hiện tại | 0,016514 | 1,669 lần variance |
| 50,0% | 0,010027 | 1,013 lần variance |
| 55,79% Neyman plug-in | 0,009894 | 1,000 |

Suy ra sai số chuẩn của thiết kế hiện tại xấp xỉ `sqrt(1,669)=1,292` lần tối ưu và hiệu quả cỡ
mẫu tương đương khoảng `1/1,669=59,9%`. So với 50/50, variance xấp xỉ 1,647 lần.

Đây là **diagnostic thiết kế**, không phải exact CATE efficiency bound: phép tính dùng event rate
biên, bỏ qua `Var[tau(X)]`, covariate adjustment và cấu trúc local. Trong các leaf/segment nhỏ,
thiếu event có thể nặng hơn con số trung bình này. Kết quả phù hợp với lý thuyết semiparametric
về efficient treatment-effect score của [Hahn](https://ideas.repec.org/a/ecm/emetrp/v66y1998i2p315-332.html),
nhưng tỷ số trên là phép suy ra trực tiếp cho chính manifest của repo.

### 2.2 Event budget trong cross-fitting và top-tail

- Screen có 244 control conversions. Với 3-fold cross-fitting, mỗi lần fit chỉ thấy khoảng 163
  control positives trong hai training folds.
- Full có 1.625 control conversions; mỗi fit thấy khoảng 1.083.
- Nếu top 1% có risk như population trung bình, evaluation slice chỉ kỳ vọng khoảng 16,25 control
  conversions; top 2% khoảng 32,5. Ranking theo risk có thể làm số thật cao hơn, nhưng trước khi
  quan sát score đây là quy mô thông tin nền.

Hệ quả: million-row asymptotics không bảo đảm top-tail inference tốt khi effective event count chỉ
ở hàng chục. Minimum leaf theo **số dòng** không đủ; cần theo dõi positive count từng arm và local
standard error.

### 2.3 Những thao tác không thể khôi phục thông tin đã mất

- Duplicate/oversample control positives không tạo observation độc lập.
- SMOTE tạo dữ liệu theo model giả định, không tạo counterfactual evidence.
- Undersample treated có thể giảm compute và làm learner cân bằng hơn, nhưng không hạ variance
  bound của dataset gốc.
- IPW/DR sửa target và bias dưới giả định; trọng số không biến 1.625 events thành nhiều events hơn.
- Đổi fold seed đo training instability, không phải thu một RCT replication mới.

## 3. Năm mục tiêu thường bị gọi chung là “model tốt”

| Mục tiêu | Đại lượng | Câu hỏi đúng |
|---|---|---|
| Outcome prediction | `mu1(x)` hoặc `P(Y=1|X)` | Ai có khả năng conversion? |
| CATE accuracy | `tau_hat(x) ≈ tau(x)` | Độ lớn effect có đúng theo từng `x`? |
| Calibration | `E[tau(X)|tau_hat=s] ≈ s` | Một score 0,001 có thật sự lift 0,001? |
| Prioritization | ordering của score | Top score có benefit cao hơn phần còn lại? |
| Budgeted policy | `V_b(s)` | Với budget `b`, policy tạo bao nhiêu incremental conversion? |

Với DR signal `Gamma`, gross policy value tại budget `b` có thể viết:

```text
V_b(s) = E[Gamma * 1{s(X) >= q_(1-b)}]
```

trong đó `q_(1-b)` là ngưỡng lấy top `b`. Diện tích policy 1–30% là tích phân/average của nhiều
`V_b`; nó không đồng nhất với `V_0.01` hay `V_0.02`.

[RATE](https://arxiv.org/abs/2111.07966) đánh giá ranking rule mà không yêu cầu rule đó là CATE;
nó bao gồm Qini trong một họ rank-weighted estimand và cung cấp inference. AUTOC nhấn mạnh phần
đầu ranking bằng trọng số liên quan `-log(q)-1`, nhưng vẫn tích hợp trên một miền quantile; nó
không phải hard-budget value tại đúng 1%.

Điều này giải thích ba hiện tượng của repo:

1. Response có thể thắng dù không phải CATE: causal classification có bias–variance tradeoff;
   outcome risk có variance thấp và có thể là proxy hữu ích khi risk tương quan với benefit.
   Đây là trường hợp được phân tích bởi
   [Fernández-Loría–Provost](https://jmlr.org/beta/papers/v23/19-480.html).
2. DINA có AUTOC tốt hơn nhưng policy area thấp hơn: score có thể tốt ở phần đầu mà kém ở phần
   budget rộng.
3. Calibration và ranking có thể đi ngược chiều: monotone transform giữ ranking nhưng đổi
   calibration; calibrator đúng trung bình không tự sửa thứ tự sai.

## 4. Diễn giải đúng phát hiện top 1–2%

Bốn causal candidate đều có point delta dương so với Response tại hai budget và hai seed screen:

| Candidate | Mean delta 1% | Mean delta 2% | Min của 4 so sánh |
|---|---:|---:|---:|
| Anchored-R25 | +1,57e-5 | +3,68e-5 | +1,96e-6 |
| Anchored-R25-Sentinel | +1,98e-5 | +6,48e-5 | +1,58e-5 |
| Anchored-Pattern-R | +4,19e-5 | +3,57e-5 | +3,53e-5 |
| DINA-CATE-Sentinel | +3,70e-5 | +4,77e-5 | +3,33e-5 |

Đây là pattern đáng nghiên cứu, nhưng chưa đủ để kết luận superiority vì:

- 1% và 2% được chú ý sau khi primary 1–30% đã thất bại;
- hai seed thay fold trên cùng 838.776 source rows, không phải hai sample độc lập;
- có bốn learner và hai budget, tạo multiplicity;
- CI trong `budget_deltas.csv` là interval của từng policy value, không phải paired interval của
  delta tại từng budget và không phải simultaneous band;
- tất cả model dùng chung screen để tạo giả thuyết và đánh giá nó.

Kết luận được phép là:

> Có tín hiệu hậu nghiệm, nhất quán theo hai fold seed, rằng causal reranking có thể hữu ích khi
> budget thật sự bị khóa ở 1–2%. Cần protocol mới và dữ liệu xác nhận mới để kiểm tra.

Không được đổi champion từ pattern này. Cũng không được chọn “budget tốt nhất” bằng cùng sample.

## 5. Chọn model khi không quan sát CATE cá nhân

Trong supervised learning, validation loss so prediction với label. Với CATE, không user nào có
cả `Y(1)` và `Y(0)`, nên factual outcome loss không phải CATE loss. Có bốn lớp proxy khác nhau:

### 5.1 Orthogonal/DR CATE risk

R-loss hoặc doubly robust pseudo-outcome loss có thể dùng để chọn model bằng cross-fitting. Nó
nhắm tới sai số bình phương CATE dưới các điều kiện nuisance. Causal Q-aggregation đề xuất ensemble
với doubly robust loss và đạt oracle selection regret bậc `log(M)/n`, cộng higher-order nuisance
error; kết quả không đòi một candidate gần truth. Xem
[Lan–Syrgkanis](https://arxiv.org/abs/2310.16945).

Giới hạn cho repo: CATE L2 risk là average trên population. Nó không trực tiếp tối ưu ranking hoặc
policy value ở top 1%.

### 5.2 RATE/TOC cho prioritization

RATE so sánh bất kỳ score nào — Response, CATE learner hoặc rule thủ công — theo khả năng đưa nhóm
benefit cao lên đầu. Đây là công cụ phù hợp để kiểm tra “proxy có xếp đúng không”, nhưng lựa chọn
trọng số RATE vẫn phải diễn ra trước khi xem kết quả.

### 5.3 Policy value cho quyết định

Nếu business constraint là hard budget, objective gần nhất là paired DR estimate của `V_b` hoặc
regret so reference. [Athey–Wager](https://arxiv.org/abs/1702.02896) và
[Kitagawa–Tetenov](https://www.homepages.ucl.ac.uk/~uctptk0/Research/kitagawa_tetenov_ecta2018.pdf)
cho thấy có thể học policy trực tiếp dưới budget/capacity constraint thay vì bắt buộc ước lượng
toàn bộ CATE chính xác.

Direct policy learning không phải free improvement. Policy class càng linh hoạt càng dễ tối đa
hóa noise; capacity của class, nested sample split và honest outer evaluation là bắt buộc.

### 5.4 Calibration

Large-scale RCT trên Facebook và Criteo đã ghi nhận HTE estimate từ ML lệch đáng kể so với subgroup
difference-in-means; model-agnostic calibration có thể sửa magnitude/sign theo subgroup benchmark.
Xem [Leng–Dimmery](https://pubsonline.informs.org/doi/10.1287/isre.2021.0343) và metric calibration
robust của [Xu–Yadlowsky](https://arxiv.org/abs/2203.13364).

Calibration là diagnostic/repair cho effect scale, không phải bằng chứng ranking tốt hơn.

## 6. Causal learner nào có cơ sở cải thiện?

### 6.1 Không có một family thắng mọi lớp mục tiêu

[Alaa–van der Schaar](https://proceedings.mlr.press/v80/alaa18a.html) nhấn mạnh rằng HTE khác
supervised learning vì counterfactual không quan sát được; bottleneck thay đổi theo sample size và
cách model hóa hai response surface. Do đó câu hỏi đúng không phải “model nào mạnh nhất”, mà là
“inductive bias nào khớp failure mode đã đo được”.

### 6.2 BCF: tách prognostic và treatment regularization

Bayesian Causal Forest viết response surface sao cho prognostic component và treatment-effect
component được regularize riêng, cho phép shrink effect về homogeneity mà không làm mất khả năng
fit baseline risk. Đây là điểm khớp nhất với prognostic dominance của repo.

```text
E[Y | X=x, Z=z] = mu[x, e_hat(x)] + tau(x) z
```

[Paper BCF](https://arxiv.org/abs/1706.09523) chủ yếu nhắm small effects, heterogeneous effects và
confounding. Với RCT Criteo, phần sửa confounding qua propensity ít giá trị vì `e` đã biết và hằng;
phần **separate shrinkage** vẫn rất liên quan. Không nên bê nguyên continuous-outcome likelihood
sang conversion; cần Bernoulli-compatible implementation hoặc coi đây là kiến trúc để kiểm chứng
trên synthetic trước.

### 6.3 Causal Forest/GRF: local moments và honesty

[Causal Forest](https://arxiv.org/abs/1510.04342) cung cấp consistency/inference dưới các điều kiện
của honest random forest; [Generalized Random Forest](https://doi.org/10.1214/18-AOS1709) xem forest
như adaptive local weights giải local moment equations.

Các đóng góp này giải quyết adaptive neighborhood và inference, nhưng **không bảo đảm** mỗi leaf
có đủ conversion trong cả hai arm. Với repo, backlog forest có cơ sở lý thuyết phải tách thành:

1. honesty: sample quyết định split khác sample ước lượng leaf effect;
2. known-propensity orthogonal score;
3. treatment/control support trong leaf;
4. project extension: minimum positive events từng arm và local-SE guard;
5. shrink leaf effect về parent/global effect khi information thấp;
6. outer OOF score để policy evaluation độc lập với tree growth.

Mục 4–5 là giả thuyết kỹ thuật của dự án, không phải theorem sẵn có từ paper. Chúng phải qua
synthetic DGP có truth trước khi chạy Kaggle.

### 6.4 Orthogonal Random Forest

[ORF](https://proceedings.mlr.press/v97/oprescu19a.html) kết hợp Neyman orthogonality với local
forest weights và có oracle-like rate khi nuisance đạt điều kiện. Nó hữu ích nhất khi nuisance
cao chiều/khó học. Criteo chỉ có 12 feature ẩn danh và propensity biết chính xác, nên ORF không
tự chữa được bottleneck control events; lợi ích kỳ vọng chủ yếu ở local outcome residualization.
Đây là candidate đối chiếu lý thuyết, không nên ưu tiên hơn việc khóa estimand/top-tail inference.

### 6.5 Direct policy learning

Nếu budget thực sự là 1% hoặc 2%, EWM/efficient policy learning có objective khớp quyết định hơn
CATE regression. Candidate nên là policy class hạn chế — ví dụ shallow tree hoặc monotone
reranking quanh Response — để giảm variance. Một unrestricted tree/boosting policy trên cùng DR
signal hiếm rất dễ học noise.

### 6.6 Causal Q-aggregation

Ensembling bằng DR loss có cơ sở hơn average score tùy ý. Nhưng Q-aggregation nhắm CATE risk, nên
nếu primary là `V_0.01`, trọng số ensemble cũng cần được đánh giá bằng outer policy value; không
được dùng theorem CATE-risk để claim tail-policy optimality.

## 7. Assumption audit

| Claim | Điều kiện | Trạng thái hiện tại |
|---|---|---|
| ITT ATE/CATE trong released sample | random assignment, consistency, positivity, SUTVA | Plausible theo mô tả dataset; provenance không được repo tự chứng minh |
| Positivity thống kê | `0 < e < 1` | Đúng về support; kém hiệu quả do 85/15 |
| Effect của actual exposure | valid IV + monotonicity | Chưa audit, chưa đăng ký |
| Direct effect không qua visit | mediation assumptions | Không nhận dạng trong pipeline |
| Generalize về source population | known sampling/transport weights | Không có do non-uniform subsampling |
| Individual treatment effect | joint potential outcomes/extra assumptions | Không quan sát, không được claim |
| Incremental retention/CLV/profit | đúng outcome và cost/revenue | Dataset không có |

Hai rủi ro SUTVA cần ghi nhận dù benchmark không cung cấp dữ liệu kiểm tra: một user có thể chịu
ảnh hưởng từ quảng cáo/kênh khác, và treatment của một user có thể tác động auction hoặc campaign
budget của user khác. Không có artifact để định lượng interference; vì vậy kết luận luôn conditional
trên benchmark experiment design.

## 8. Falsification matrix cho research tiếp theo

| Giả thuyết | Bằng chứng ủng hộ hiện tại | Test có thể bác bỏ | Điều không được coi là xác nhận |
|---|---|---|---|
| H1: causal reranking hơn Response ở budget 1–2% | 4/4 point wins cho mỗi causal candidate trên hai seed | Budget khóa từ business; outer paired DR delta; simultaneous CI; replication mới | Chọn lại budget/model trên screen cũ |
| H2: event scarcity là bottleneck chính | 244/1.625 control events; 85/15 variance penalty | Semi-synthetic DGP giữ risk/effect, thay số control event; oracle-nuisance ablation; `visit` outcome diagnostic | Oversampling làm metric tăng |
| H3: Response là proxy của dominant moderator | Response thắng ba sprint; risk/effect có tương quan | Honest RATE/TOC; orthogonal regression of effect signal on risk; subgroup stability | AUC conversion cao |
| H4: direct policy loss tốt hơn CATE loss ở hard budget | Tail wins nhưng area losses | Restricted EWM vs plug-in score trong nested protocol | In-sample welfare cao |
| H5: separate shrinkage ổn định hơn residual learner tự do | Anchored R tự do thua; Pattern R fold-sensitive | Bernoulli BCF-inspired/shrunk local effect trên synthetic và outer folds | Một seed tốt |
| H6: product cần exposure effect thay vì assignment ITT | Có cột exposure và noncompliance | Business estimand review; first-stage; IV assumption audit | Conditioning vào exposed users |

`visit` diagnostic chỉ bác bỏ/ủng hộ H2 ở mức phương pháp: nếu cùng pipeline tìm được stable HTE
trên visit nhưng không trên conversion, có thêm bằng chứng rằng power/event scarcity quan trọng.
Nó không chứng minh conversion CATE đúng.

## 9. Thứ tự ưu tiên theo information value

### Tier 0 — làm rõ trước mọi model run

1. Quyết định action là assignment-to-target hay actual exposure.
2. Xác nhận budget sản phẩm thật: hard 1%, 2%, hay dải 1–30%.
3. Chọn outcome: conversion ITT là primary; visit chỉ là diagnostic; retention/profit ngoài scope.

Nếu một trong ba câu trả lời thay đổi, estimand/protocol phải thay đổi. Không được tái sử dụng gate
cũ như thể cùng bài toán.

### Tier 1 — inference và diagnostic, chưa cần learner mới

1. Sinh paired delta curve Response vs từng causal score tại các budget khóa.
2. Dùng simultaneous confidence band hoặc điều chỉnh multiplicity cho tập budget/candidate đã đăng ký.
3. Báo số treated/control rows và positive events thực tế trong từng targeted slice.
4. Tách score stability thành rank overlap, top-k Jaccard, RATE và policy delta; fold seed không đủ.
5. Chạy calibrated semi-synthetic benchmark với truth để đo PEHE, rank regret và policy regret riêng.

### Tier 2 — experiment mới sau preregistration

1. Restricted direct policy learner dưới hard capacity.
2. BCF-inspired separate shrinkage hoặc hierarchical local-effect shrinkage.
3. DR Q-aggregation của candidate list cố định.
4. Model-agnostic HTE calibration, chỉ nếu calibration là deliverable thật.

### Tier 3 — Causal Forest/Kaggle sau khi nền tảng khóa

1. Honest/orthogonal forest baseline đúng paper.
2. Event-aware leaf support và leaf-SE artifact.
3. Parent/global shrinkage ablation.
4. Cùng outer split, score contract và paired policy evaluation như non-forest candidates.

Không chạy forest trước Tier 0–1: nếu budget/estimand chưa đúng, compute lớn chỉ tối ưu sai target.

## 10. Blueprint thực nghiệm có khả năng bác bỏ

Một protocol mới tối thiểu nên có bốn lớp độc lập:

```text
candidate development
  └─ inner folds: nuisance, shrinkage/hyperparameter, policy-class selection

outer development evaluation
  └─ OOF score: paired DR value, RATE, calibration, rank stability

locked confirmation
  └─ đúng một policy/budget decision; không tune

future randomized replication
  └─ bằng chứng promotion thật
```

Các guard bắt buộc:

- Candidate, budget, primary metric và multiplicity method khóa trước khi đọc outer result.
- Model selection loss khớp deliverable: CATE risk cho estimation; RATE cho ranking; `V_b` cho policy.
- Mọi comparison dùng paired signal trên cùng rows; interval của hai model riêng không thay paired CI.
- Nuisance prediction cho một row không được train trên row đó.
- Top-tail phải có event-count/power gate; không kết luận từ slice chỉ có vài event control.
- Multi-seed là sensitivity analysis, không được nhân số seed để giả thành sample size.
- Synthetic DGP phải thay độc lập: outcome prevalence, allocation ratio, effect strength, alignment
  giữa risk và effect, sparsity của moderator và smoothness.
- Confirmation đã đọc ở sprint trước không trở lại thành unseen confirmation bằng cách đổi code.

### Primary metric nếu hard budget được xác nhận

Không nên mặc định average 1% và 2% chỉ vì cả hai đẹp. Business phải chọn một trong:

- `V_0.01` nếu capacity đúng 1%;
- `V_0.02` nếu capacity đúng 2%;
- một weighted policy value với weights lấy từ distribution budget vận hành, khóa trước;
- regret/cost-aware net value nếu sau này có cost thật.

AUTOC/Qini/calibration giữ vai trò secondary diagnostic. Nếu business vẫn vận hành 1–30%, primary
metric hiện tại hợp lý hơn quan sát hậu nghiệm ở 1–2%.

## 11. Những việc không nên làm

- Không thêm `visit` hoặc `exposure` làm covariate để “tăng signal”.
- Không gọi score của Response là individual causal effect.
- Không diễn giải odds ratio/log-odds effect thành absolute conversion lift nếu chưa map qua baseline risk.
- Không duplicate control positives, SMOTE hoặc class-weight rồi nói causal information tăng.
- Không chọn shrinkage, leaf size, model và budget trên cùng outer sample.
- Không dùng CATE calibration để override policy regression, hoặc dùng policy win để claim CATE accuracy.
- Không coi forest honesty là đủ khi leaf chỉ có rất ít positive ở một arm.
- Không generalize con số absolute lift về population gốc khi không có sampling weights.
- Không gọi exposure effect là ITT, và không conditioning trên exposure/visit để “sửa” noncompliance.

## 12. Source ledger và mức sẵn sàng

Mức xác minh dùng quy ước của [planning index](README.md): `A` đủ chi tiết để hiện thực; `B` đủ
cho scoping nhưng phải đọc full method trước khi code.

| Nguồn gốc | Nội dung dùng trong dossier | Mức |
|---|---|---:|
| [Criteo dataset page](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) và [Diemert et al.](https://www.adkdd.org/papers/a-large-scale-benchmark-for-uplift-modeling/2018) | assignment test, exposure, non-uniform subsampling, benchmark scope | A cho metadata; B cho thuật toán paper |
| [Hahn 1998](https://ideas.repec.org/a/ecm/emetrp/v66y1998i2p315-332.html) | semiparametric efficiency/propensity context | B; công thức variance trong dossier được suy ra trực tiếp |
| [Imbens–Angrist](https://www.nber.org/papers/t0118) | IV không tự đủ; LATE cần điều kiện bổ sung | A |
| [Yadlowsky et al., RATE](https://arxiv.org/abs/2111.07966) | score-agnostic prioritization, Qini/RATE inference | A |
| [Fernández-Loría–Provost](https://jmlr.org/beta/papers/v23/19-480.html) | causal classification bias–variance | B |
| [Athey–Wager](https://arxiv.org/abs/1702.02896) | efficient policy learning dưới constraint | B |
| [Kitagawa–Tetenov](https://www.homepages.ucl.ac.uk/~uctptk0/Research/kitagawa_tetenov_ecta2018.pdf) | empirical welfare maximization/capacity | B |
| [Lan–Syrgkanis](https://arxiv.org/abs/2310.16945) | DR Q-aggregation, oracle selection regret | A |
| [Leng–Dimmery](https://pubsonline.informs.org/doi/10.1287/isre.2021.0343) | calibration discrepancy và repair trên RCT/Criteo | B |
| [Xu–Yadlowsky](https://arxiv.org/abs/2203.13364) | robust HTE calibration error | B |
| [Alaa–van der Schaar](https://proceedings.mlr.press/v80/alaa18a.html) | limits và DGP-dependent learner choice | B |
| [Wager–Athey](https://arxiv.org/abs/1510.04342), [GRF](https://doi.org/10.1214/18-AOS1709) | honest forest, local moments và inference | A cho core; event-aware extension vẫn là giả thuyết dự án |
| [Hahn–Murray–Carvalho](https://arxiv.org/abs/1706.09523) | separate prognostic/effect regularization, shrink-to-homogeneity | A cho Gaussian core; Bernoulli extension chưa khóa |
| [Oprescu–Syrgkanis–Wu](https://proceedings.mlr.press/v97/oprescu19a.html) | local orthogonal moments/oracle nuisance robustness | A |

## 13. Quyết định research

Chưa mở một model sweep mới. Research này thay đổi thứ tự công việc như sau:

```text
clarify action + budget
→ build tail-specific paired inference and information diagnostics
→ preregister direct-policy vs separate-shrinkage experiment
→ only then implement/test honest event-aware forest for Kaggle
```

Champion vẫn là Response theo protocol đã hoàn tất. Tín hiệu causal top 1–2% được lưu như một
research hypothesis có priority cao, không phải promotion result.
