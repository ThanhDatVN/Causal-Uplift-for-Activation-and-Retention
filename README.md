# Đo lường uplift nhân quả và tối ưu policy marketing

Dự án trả lời: **nên target ai dựa trên tác động tăng thêm của treatment, thay vì chỉ dự
đoán ai có khả năng conversion?**

Pipeline dùng [Criteo Uplift Prediction Dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)
(13,98 triệu dòng, randomized incrementality test), so sánh response/CATE learners, đo
uncertainty và phát hành một dashboard policy chạy được.

## Kết quả

**Champion giữ nguyên Response — một model dự đoán `P(conversion)`, không phải CATE
estimator.** Đã so 8 challenger trên retrospective confirmation; không challenger nào
thắng ở cả hai fold seed OOF, và không paired 95% CI nào có cận dưới lớn hơn 0.

Đó **không** phải "chưa tìm được model tốt hơn". Sau sáu vòng cải tiến, ba hướng sửa độc
lập đều đóng, và phát biểu đúng là: **phép đo hết độ phân giải trước khi model hết dư
địa** — nửa CI `±1,74e-05` so với chênh lệch giữa các model hàng đầu ở bậc `1e-06`.

Metric chính là `policy_area_dr`: trung bình conversion tăng thêm trên mỗi khách
hàng ở dải budget 1–30%, chấm bằng doubly robust signal.

| Model | `policy_area_dr` | AUTOC | Qini |
|---|---:|---:|---:|
| Response | 0,000912 | 0,003823 | 0,192989 |
| Ensemble-QAgg | 0,000911 | 0,003271 | 0,209845 |
| Ensemble-RankAverage | 0,000908 | 0,003332 | 0,195022 |
| S-Under7 | 0,000896 | 0,003116 | 0,205904 |
| X-Renormalized | 0,000890 | 0,003283 | 0,201812 |
| Rank-K2 | 0,000862 | 0,002454 | 0,184993 |
| Rank-K1 | 0,000852 | 0,002400 | 0,185657 |
| Rank-K05 | 0,000848 | 0,002388 | 0,186454 |

Lưu ý metric bất đồng: theo Qini, ba model xếp trên Response; theo metric chính và
AUTOC, Response đứng đầu. Metric hierarchy được đăng ký **trước** khi chạy chính là
để tình huống này không trở thành lựa chọn hậu nghiệm.

Kết quả "một model không phải CATE estimator xếp hạng tốt hơn mọi CATE learner" là
chế độ đã được mô tả trong tài liệu, không phải dị thường: *causal bias–variance
tradeoff* (Fernández-Loría & Provost, JMLR 2022), điều kiện proxy phản ánh dominant
moderator (arXiv 2206.12532), và chính nhóm tạo Criteo đã khuyến nghị dùng `visit`
thay `conversion` vì tín hiệu uplift của `conversion` quá yếu (Diemert et al., AdKDD
2018). Rà soát đầy đủ:
[research landscape](planning/RESEARCH_LANDSCAPE_2026.md).

Tại budget 10%, `value=1`, `cost=0,0005`, Response đạt DR net/customer `0,000856`,
95% CI `[0,000675; 0,001044]`; Δ so random CI `[0,000638; 0,000994]`. Với một triệu
khách hàng, top 10% tương ứng khoảng `906` incremental conversions, CI `[725; 1.094]`.

Các số này là **conversion-equivalent scenario**, không phải actual revenue/profit.

## Mạch phát triển — chín giai đoạn

Sáu vòng cải tiến, mỗi vòng kiểm một giả thuyết về nguyên nhân baseline dự đoán chưa bị
vượt qua. Kết quả mỗi vòng xác định giả thuyết của vòng kế tiếp. Mỗi dòng dưới đây là một giai
đoạn, trải qua mọi thư mục liên quan.

| # | Giai đoạn | Câu hỏi của giai đoạn | Kết quả | Báo cáo |
|---:|---|---|---|---|
| 0 | Chẩn đoán dữ liệu | dữ liệu cho phép suy luận tới đâu | đo được **trần phân giải** trước khi chạy model nào | mục 2 của Sprint 1 |
| 1 | Sprint 1 — nền tảng | model nào xếp hạng tốt nhất | Response dẫn đầu; hai candidate thắng validation đổi dấu trên test | [Sprint 1](report/SPRINT_1_FINAL_REPORT.md) |
| 2 | Sprint 2 — tầng quyết định | biến xếp hạng thành quyết định ngân sách | X-Renormalized cao hơn nhưng CI chứa 0; giữ Response | [Sprint 2](report/SPRINT_2_FINAL_REPORT.md) |
| 3 | Sprint 3 — vòng đăng ký trước | metric nào mới là metric quyết định | 0/12 promote; **Qini và metric chính xếp ngược nhau** | [Sprint 3](report/SPRINT_3_FINAL_REPORT.md) |
| 4 | Causal Forest | có cần thuật toán chuyên dụng không | hạng 1/6 theo metric chính nhưng CI chứa 0 — hòa | [Causal Forest](report/CAUSAL_FOREST_REPORT.md) |
| 5 | Data optimization | biểu diễn dữ liệu có phải nút thắt | qua screen, trượt gate ổn định ở full | [Data optimization](report/DATA_OPTIMIZATION_REPORT.md) |
| 6 | Causal foundation | estimator có sai thang không | không learner nào thắng ở cả hai seed | [Causal foundation](report/CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md) |
| 7 | Top-tail v2 | có đang nhìn sai vùng ngân sách không | 16/16 delta dương, **0/16** cận dưới vượt 0 | [Top-tail v2](report/TOP_TAIL_RESEARCH_V2_REPORT.md) |
| 8 | Causal Forest `rare-outcome` | thuật toán đó có bị đặt sai cấu hình không | hạng 1/10 nhưng CI chứa 0 — hòa | [CF rare-outcome](report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md) |
| 9 | Sản phẩm | đưa quyết định tới người dùng | web app + dashboard, 30/30 và 12/12 acceptance | mục 9 của Sprint 3 |

Sau giai đoạn 8, **không còn giả thuyết nào phía model chưa bị kiểm**. Ba hướng sửa độc
lập — biểu diễn dữ liệu, estimator, thuật toán — đều đóng. Kết luận vì vậy đổi từ "chưa
tìm được model tốt hơn" thành một phát biểu kiểm chứng được: **phép đo hết độ phân giải
trước khi model hết dư địa** (`±1,74e-05` so với chênh lệch bậc `1e-06`).

Mạch đầy đủ, gồm bản đồ script–artifact–báo cáo của từng giai đoạn, ranh giới của kết
luận và kiến trúc sản phẩm hai tầng:
[**docs/END_TO_END_WORKFLOW.md**](docs/END_TO_END_WORKFLOW.md).

## Demo

Web application đầy đủ tính năng:

```powershell
.venv\Scripts\python.exe scripts\build_champion_scorer.py
.venv\Scripts\python.exe scripts\serve_webapp.py --port 8000
node scripts\smoke_webapp_browser.mjs
```

Mở `http://127.0.0.1:8000`; OpenAPI docs ở `/docs`. Hướng dẫn vận hành và tái lập:
[scripts/README.md](scripts/README.md).
Screenshot: [webapp_screenshot.png](output/product/screenshots/webapp_screenshot.png).

App có sáu tab: tổng quan release, so sánh model kèm paired CI, budget/policy
explorer, uplift theo decile và chẩn đoán cân bằng, batch scoring từ CSV, và bảng
bằng chứng kèm experiment registry và export CSV.

Dashboard tĩnh Sprint 2 vẫn dùng được cho bản demo một file:

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

## Tiến trình dự án — chi tiết từng giai đoạn

### 0. Chẩn đoán dữ liệu — bước này dự đoán trước kết quả model

Ba phát hiện dưới đây đo trực tiếp trên dữ liệu thô, **không qua model nào**, và cả ba đều
được tính lại trong [notebook 01](notebooks/01_eda_criteo.ipynb).

**Không gian covariate hẹp hơn con số 12 rất nhiều.** Sáu trên mười hai đặc trưng có hơn
90% khối lượng dồn vào đúng một giá trị — chúng không cắt được thành hai nhóm phân vị. Bốn
cặp đặc trưng có mask "nằm ở giá trị mode/sentinel" **trùng khít tuyệt đối**. Vì dữ liệu
không mã hóa `NA`, đây là cấu trúc sentinel-like chứ không phải bằng chứng trực tiếp về ô
thiếu. Chỉ có 53 pattern trên 4.096 khả năng và trung vị số đặc trưng không ở sentinel là
**2 trên 12**. Cột "0 ô thiếu" đúng về cú pháp nhưng chưa mô tả hết cấu trúc dữ liệu.

**Heterogeneity tồn tại, và rất lớn.** Sáu đặc trưng phân tầng được đều có `I² > 0,99`;
hiệu ứng chênh 15–169 lần giữa các bin phân vị, và chênh tới ba bậc độ lớn giữa các pattern
missingness. Nên cách giải thích "các CATE learner thua vì hiệu ứng đồng nhất" bị bác bỏ
bằng dữ liệu.

**Nhưng hiệu ứng gần như tỉ lệ thuận với rủi ro nền.** Khi gộp 30 bin của sáu feature,
`corr(p₀, τ) = 0,984` (Pearson) và `0,959` (Spearman), còn trung vị `τ/p₀ = 0,53`.
Các bin này dùng lại cùng quan sát giữa nhiều feature nên hai tương quan chỉ mang tính mô
tả, không được gắn p-value hay Cochran `Q`. Bằng chứng suy luận được tính trên các tầng độc
lập: trong từng feature có ít nhất ba bin, Pearson nằm trong `[0,991; 1,000]`; trên 26
pattern sentinel rời nhau, Pearson `0,769`, Spearman `0,883`, và `Q` giảm từ `861` trên
thang cộng xuống `150` trên thang nhân — tỷ lệ **5,7 lần**.

Quan hệ rút gọn: `τ(x) ≈ 0,53 · p₀(x)`. Hàm `p₀` đơn điệu tăng, nên xếp hạng theo rủi ro nền
cho gần đúng thứ tự xếp hạng theo uplift. Điều đó dự đoán trước — từ dữ liệu thô, trước mọi
model — kết quả mà Sprint 1, Sprint 3 và vòng Causal Forest sau đó xác nhận: không phương
pháp nhân quả nào tách được khỏi baseline Response.

Bước này cũng để lại bằng chứng số cho hai ràng buộc mà trước đó chỉ được phát biểu:
`exposure` có **đúng 0** sự kiện ở nhánh control, và `P(conversion = 1 | visit = 0) = 0`
chính xác — `visit` là điều kiện cần của `conversion`. Đó là lý do cả hai bị cấm làm feature.

**Mở ra:** nếu xếp hạng theo rủi ro nền đã gần đúng thứ tự xếp hạng theo uplift, thì
một CATE learner còn thắng được ở đâu. Đó là câu hỏi Sprint 1 nhận.

### 1. Sprint 1 — nền tảng model và đánh giá (29/07)

- data/schema/balance audit;
- Response, S/T/X-Learner, DR-Learner;
- validation nhiều seed và final holdout chung;
- Qini/AUUC cross-check với `scikit-uplift`;
- 500 paired percentile bootstrap;
- Causal Forest resource benchmark.

Nguồn: [Sprint 1 report](report/SPRINT_1_FINAL_REPORT.md).

**Đóng lại:** gate theo point estimate trên một pool validation là không đủ — hai
candidate thắng validation *đổi dấu* trên test. **Mở ra:** vậy chọn model bằng gì.

### 2. Sprint 2 — tầng quyết định và dashboard (31/07)

- confirmation mới 1.397.959 dòng, không tái sử dụng test Sprint 1;
- X-Renormalized, τ-isotonic và T-LocalExact ablation;
- Response top-k champion được chọn trên validation;
- offline policy value bằng IPW/DR, 500 paired bootstrap;
- cost/value sensitivity và break-even;
- dashboard HTML self-contained, 12/12 browser acceptance pass;
- data card, model card, decision contract;
- Kaggle Causal Forest gated package.

Nguồn chính: [Sprint 2 report](report/SPRINT_2_FINAL_REPORT.md).

**Đóng lại:** point estimate cao hơn không phải bằng chứng. **Mở ra:** metric chính
có đang đo đúng thứ cần không.

### 3. Sprint 3 — vòng cải tiến có đăng ký trước (05/08)

- protocol đăng ký trước: metric chính, gate, promotion rule;
- 3-fold cross-fitting OOF trên 5.591.836 dòng, hai fold seed;
- 12 candidate screening, gồm R-Learner, DR ablation và Rank-Learner (ICML 2026);
- causal Q-aggregation và hai ensemble baseline;
- experiment registry ghi cả run bị dừng sớm;
- web application có API, batch scoring và export.

Nguồn: [Sprint 3 report](report/SPRINT_3_FINAL_REPORT.md),
[method guide](docs/SPRINT_3_METHOD_GUIDE.md).

**Đóng lại:** Qini không phải metric quyết định cho bài toán ngân sách. **Mở ra:** có
phải cần một thuật toán chuyên dụng ngoài họ meta-learner.

### 4. Causal Forest — ba mốc 20/30/50% (06/08)

Kaggle 20% → 30% → 50% đã chạy và đã chấm điểm. Báo cáo đầy đủ:
[CAUSAL_FOREST_REPORT.md](report/CAUSAL_FOREST_REPORT.md).

Chấm trên cùng holdout final test Sprint 1 (2.096.940 dòng, trùng khít đã kiểm chứng
từng phần tử), nên sáu model đặt chung một bảng được:

| Model | `policy_area_dr` | Qini |
|---|---:|---:|
| **Causal Forest** | **0,001006** | 0,174678 |
| Response | 0,001005 | **0,187886** |
| S-Learner | 0,000999 | 0,177204 |
| X-Learner | 0,000975 | 0,167168 |
| DR-Learner | 0,000925 | 0,153967 |
| T-Learner | 0,000897 | 0,142021 |

Causal Forest đứng đầu theo metric chính và thứ ba theo Qini. Nhưng chênh lệch so với
Response có **CI 95% chứa 0 trên cả hai metric** — `[-6,0e-05; 5,8e-05]` và
`[-0,0370; 0,0107]` — nên đây là **hòa**, không phải thắng. Champion giữ nguyên Response.

Theo `policy_area_dr`, Causal Forest vượt rõ X, DR, T. Điểm không suy biến: 912.579 giá
trị phân biệt.

Causal Forest dùng cấu hình cố định thay vì chọn qua validation như bốn meta-learner.
Chi tiết cấu hình, learning curve ba mốc và năm biểu đồ:
[CAUSAL_FOREST_REPORT.md](report/CAUSAL_FOREST_REPORT.md).

**Notebook của lần chạy:** [`notebooks/03_causal_forest.ipynb`](notebooks/03_causal_forest.ipynb)
— 23 cell, bản Kaggle trả về sau `Save & Run All` nên **có output thật của cả ba stage**;
`papermill` ghi 3.192,7 giây, `exception: null`. Chạy lại được nguyên trạng, không cần
restart kernel.

**Đóng lại:** thuật toán chuyên dụng cũng không tách được khỏi baseline dự đoán.
**Mở ra:** có phải biểu diễn dữ liệu thiếu cấu trúc.

### 5. Data optimization v1 — quay lại từ EDA (09/08)

- ánh xạ bốn failure mode sang bốn can thiệp đăng ký trong protocol riêng;
- thêm feature sentinel fold-local và funnel factorization dùng `visit` chỉ làm auxiliary
  training outcome;
- chạy OOF 15% trên 838.776 dòng với fold seed 101/202;
- sửa shortlist từ top-N sang gate bắt buộc thắng Response trên từng seed;
- `Response-Sentinel` thắng point estimate ở cả hai seed, trung bình `+0,298%`;
- paired 95% CI vẫn chứa 0, nên challenger chỉ được đi tiếp sang randomized confirmation mới;
- champion hiện hành giữ nguyên **Response**.

Nguồn: [data optimization report](report/DATA_OPTIMIZATION_REPORT.md),
[`optimization_decision.json`](output/improvement/data_opt_comparison/optimization_decision.json).

**Đóng lại:** biểu diễn dữ liệu không phải nút thắt. **Mở ra:** có phải estimator sai
thang.

### 6. Causal foundation v1 — estimator cho binary outcome hiếm (09/08)

- research DINA/R-Learner/PATH được khóa trước trong một protocol riêng;
- thêm Binary DINA-CATE, Anchored R25, Anchored R25-Sentinel và Anchored Pattern R;
- gradient/Hessian, synthetic DGP, leakage/merge/selection contracts đều có test;
- screen 15% dùng cùng 838.776 dòng và fold seed 101/202;
- không causal learner nào thắng Response ở cả hai seed;
- Response-Sentinel qua screen point-estimate gate nhưng full-development đổi dấu giữa seed;
- full paired CI đều chứa 0; champion giữ nguyên **Response**;
- Causal Forest được để lại trong backlog, chưa chạy Kaggle lại.

**Đóng lại:** đúng thang chưa đủ để khử phương sai xếp hạng. **Mở ra:** có phải đang
nhìn sai vùng ngân sách.

### 7. Top-tail research v2 — kiểm riêng phần đuôi 1-2% (09/08)

Top-tail audit đã kiểm 20 model × seed × budget cells bằng paired simultaneous band. Cả
16 causal point delta đều dương, nhưng 0/16 pointwise và 0/16 simultaneous lower bounds vượt 0;
minimum causal overlap chỉ 61,31% và minimum control tail events là 84. Kết luận vẫn là giữ Response,
không promote. Nguồn: [top-tail v2 report](report/TOP_TAIL_RESEARCH_V2_REPORT.md),
[latest research/experiment plan](planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md) và
[inference guide](docs/TOP_TAIL_POLICY_INFERENCE_GUIDE.md).

**Đóng lại:** tín hiệu ở đuôi là giả thuyết, không phải bằng chứng. **Mở ra:** có phải
Causal Forest chỉ bị đặt sai cấu hình cho outcome hiếm.


### 8. Causal Forest `rare-outcome` — sửa cấu hình (14/08)

- cấu hình đã chạy trước đó dùng `min_samples_leaf=500`, chỉ cho `0,145` sự kiện control mỗi
  lá — đại đa số lá có nhánh control rỗng;
- `min_samples_leaf=10000` nâng lên `2,906`; tỷ lệ score âm giảm `19,6% → 11,9%`;
- fit trên development 5.591.836 dòng, predict trên confirmation 1.397.959 dòng, chấm bằng
  **DR signal đã đóng băng** của Sprint 3 nên so trực tiếp được với bảng confirmation;
- Causal Forest **hạng 1/10** theo metric chính (`0,000914` so với Response `0,000912`), nhưng
  paired CI `[-1,52e-05; +1,97e-05]` chứa 0 — **hòa**, champion giữ nguyên **Response**;
- vượt rõ cả ba biến thể Rank-Learner với CI hoàn toàn trên 0.

Phát hiện phụ quan trọng hơn kết quả model: chấm lại **cùng một bộ điểm trên cùng những dòng**
bằng DR signal thay vì IPW làm chênh lệch đo được đổi **69 lần** và làm Response tụt từ hạng 2
xuống hạng 4. Mọi paired CI trong nhóm đầu vẫn chứa 0, nên đây là bằng chứng rằng **thứ hạng
theo point estimate không ổn định khi đổi tín hiệu chấm điểm**, không phải bằng chứng đổi ngôi.

Nguồn: [Causal Forest rare-outcome report](report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md).

**Đóng lại:** cấu hình cho outcome hiếm không phải nút thắt. **Còn lại:** ràng buộc nằm
ở phép đo, không ở model — xem [mạch đầy đủ](docs/END_TO_END_WORKFLOW.md) mục 3.6.

### 9. Sản phẩm — đưa quyết định tới người dùng

- web app FastAPI + SPA không CDN, 30/30 acceptance trình duyệt;
- dashboard HTML self-contained, 12/12 acceptance;
- cả hai **chỉ đọc artifact đã phát hành**, không huấn luyện khi nhận request — nên con số
  trên sản phẩm và con số trong báo cáo không thể trôi khỏi nhau.

**Ranh giới đã ghi và giữ nguyên:** đây là tầng *nhắm mục tiêu*, đặt **sau** tầng *đo
lường*, và **không thay thế** incrementality test. Nhầm hai tầng này là cách một tổ chức
tự thuyết phục mình rằng chiến dịch có hiệu quả bằng chính model dùng để phân phối nó.

Ảnh chụp màn hình và cách chạy: mục [Demo](#demo) bên dưới.

## Notebook

Bốn notebook, đọc theo thứ tự — đây là đường vào ngắn nhất cho người muốn xem mạch phân
tích thay vì đọc code:

| Notebook | Nội dung | Output lưu sẵn |
|---|---|---|
| [`01_eda_criteo.ipynb`](notebooks/01_eda_criteo.ipynb) | Phân tích dữ liệu: toàn vẹn nguồn, cardinality và sentinel value, cân bằng covariate (SMD + Love plot), propensity tuyến tính và phi tuyến, overlap, bằng chứng số cho leakage hậu can thiệp, ATE/risk ratio kèm CI, MDE, heterogeneity theo tầng và chẩn đoán prognostic dominance | 25/25 code cell, 9 biểu đồ |
| [`02_modeling_and_evaluation.ipynb`](notebooks/02_modeling_and_evaluation.ipynb) | Baseline Response so với 8 challenger: estimand, protocol đăng ký trước, OOF hai fold seed, paired bootstrap, bất đồng metric, promotion rule, threats to validity. Mục 7bis huấn luyện thật ngay trong notebook | 22/22 code cell, 5 biểu đồ |
| [`03_causal_forest.ipynb`](notebooks/03_causal_forest.ipynb) | Chạy `CausalForestDML` ba stage 20→30→50% trên Kaggle. Bản notebook Kaggle trả về sau `Save & Run All`, 53,2 phút, không exception | 10/10 code cell |
| [`04_causal_forest_rare_outcome.ipynb`](notebooks/04_causal_forest_rare_outcome.ipynb) | Cấu hình `rare-outcome` trên split Sprint 2/3, đăng ký trước ở `configs/causal_forest_rare_outcome_protocol_v1.json`. Sửa `min_samples_leaf` cho outcome hiếm | 10/10 code cell — bản Kaggle trả về, gate RAM fail ở `90,6%` nhưng điểm số vẫn hợp lệ |

Notebook `02` có hai chế độ, ghi rõ ngay ở đầu notebook. Mục 1–7 và 8–17 **đọc lại artifact
đã đóng băng** trong `output/` — chạy vài giây, không cần dữ liệu gốc. Mục 7bis thì **huấn
luyện thật ngay trong notebook**: 15% development pool, 3-fold cross-fitting, ba candidate,
bằng đúng những hàm mà [`scripts/run_oof_experiment.py`](scripts/run_oof_experiment.py) gọi;
mất khoảng hai phút và cần dữ liệu gốc.

Mục 7bis tồn tại để việc tách trình bày khỏi tính toán **kiểm chứng được** thay vì chỉ được
tuyên bố: nó huấn luyện lại từ đầu rồi đối chiếu với artifact đã đóng băng ở
`output/improvement/data_opt_screen_seed101/`, khớp metric chính ở bậc `1e-17`. Huấn luyện
đầy đủ — 5.591.836 dòng × hai fold seed — vẫn nằm ở `scripts/run_oof_experiment.py` và
`scripts/run_sprint3_confirmation.py`, để mọi con số truy được về đúng một run có `run_id`,
`commit_sha` và hash split cố định.

Notebook `01` chạy trực tiếp trên toàn bộ 13,98 triệu dòng (khoảng 2,5 phút) và **tự đối
chiếu** kết quả với artifact đã đóng băng ở `output/eda/` do
[`scripts/run_eda_profile.py`](scripts/run_eda_profile.py) sinh ra. Phép đối chiếu nằm ở
mục 1.1 chứ không ở cuối: nếu nó fail thì mọi diễn giải phía sau đều đáng ngờ.

## Chạy dự án

Ba cách, từ nhanh nhất tới chi tiết nhất.

### Docker

Cách nhanh nhất để có môi trường đúng, không cần dựng `.venv`:

```powershell
docker compose build
docker compose run --rm tests        # tap test khong can du lieu goc
docker compose up webapp             # mo http://localhost:8000
```

Image chứa **code và dependency**, không chứa dữ liệu. `data/` và `output/` được mount lúc
chạy — `data/` có giấy phép riêng của Criteo nên không phân phối lại trong image, còn
`output/` phải đọc được ở trạng thái thật chứ không phải bản chụp lúc build.

Chi tiết ba service và giới hạn của từng cái:
[docs/REPRODUCTION.md](docs/REPRODUCTION.md) mục 11.

### Kiểm thử

Python 3.12; môi trường mặc định không cài dependency đối chiếu CausalML:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Chỉ khi cần đối chiếu CausalML:
.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
```

```powershell
.venv\Scripts\python.exe -m pytest tests -q          # 294 test
node scripts\smoke_webapp_browser.mjs                # 23 acceptance check
```

### Chạy lại từng vòng

Chẩn đoán dữ liệu (khoảng 2,5 phút, sinh 17 artifact trong `output/eda/`):

```powershell
.venv\Scripts\python.exe scripts\run_eda_profile.py
```

Sprint 2:

```powershell
.venv\Scripts\python.exe scripts\run_sprint2_local.py `
  --pool-frac 1.0 --n-boot 500 --output-dir output\sprint2
```

Sprint 3:

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.20 --stage screen `
  --n-boot 300 --output-dir output\improvement\screen
```

Lệnh đầy đủ của cả tám vòng chạy được — chẩn đoán dữ liệu, Sprint 1–3, data optimization,
causal foundation, top-tail và Causal Forest — nằm trong một runbook duy nhất:
[docs/REPRODUCTION.md](docs/REPRODUCTION.md).

Run cần file Criteo v2.1 với SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

## Cấu trúc repo

```text
src/
  data.py               data contract, split, rare-outcome sampling
  eda.py                cardinality/sentinel, balance, ATE+CI, power, heterogeneity
  baselines.py          Response, S/T/X/DR và corrected classifiers
  calibration.py        probability restoration, tau-isotonic
  evaluation.py         Qini, AUUC, EUCE, paired bootstrap
  policy.py             top-k, cost-aware, IPW/DR value
  ranking_metrics.py    TOC/RATE/AUTOC, outcome adjustment, paired bootstrap
  policy_evaluation.py  budget-value curve, policy_area_dr, expected-random
  rank_learner.py       pairwise orthogonal ranking (ICML 2026)
  candidates.py         danh mục candidate dùng chung một feature contract
  ensemble.py           causal Q-aggregation, best-single, rank average
  experiment.py         cross-fitting, resource monitor, registry
  scoring.py            scorer lưu được cho batch scoring
  proxy_diagnostic.py   khi nào proxy xếp hạng đúng theo CATE
scripts/
  run_eda_profile.py               đóng băng toàn bộ chẩn đoán dữ liệu vào output/eda/
  run_oof_experiment.py            cross-fitting OOF cho toàn bộ candidate
  compare_improvement_candidates.py ensemble + shortlist
  run_sprint3_confirmation.py      retrospective confirmation + promotion rule
  build_champion_scorer.py         fit và lưu champion scorer
  serve_webapp.py                  chạy web app
  run_proxy_diagnostic.py          chẩn đoán proxy-ordering
  evaluate_causal_forest.py        chấm điểm artifact Causal Forest
  smoke_webapp_browser.mjs         acceptance headless cho web app
  run_sprint2_local.py, rebuild_sprint2_*.py, build_dashboard.py
  kaggle_causal_forest_gate.py
notebooks/              bốn notebook, đánh số theo giai đoạn
webapp/                 API FastAPI + SPA không CDN
output/                 artifact đã chạy — xem output/README.md
docs/                   method guide, decision contract, data/model card
planning/               bối cảnh nghiên cứu và mức xác minh nguồn
report/                 tám báo cáo kết quả
```

**Mười một thư mục lớn, mỗi thư mục một `README.md` chỉ mục** ghi vai trò và trạng thái
từng file: [src](src/README.md) · [scripts](scripts/README.md) ·
[configs](configs/README.md) · [notebooks](notebooks/README.md) ·
[tests](tests/README.md) · [output](output/README.md) · [docs](docs/README.md) ·
[report](report/README.md) · [planning](planning/README.md) ·
[webapp](webapp/README.md) · [benchmarks](benchmarks/README.md).

Sự tồn tại của cả mười một được [khóa bằng test](tests/test_documentation_integrity.py), nên
một thư mục mới không thể lặng lẽ xuất hiện mà không có chỉ mục.

Không nhớ một thuật ngữ? [**docs/GLOSSARY.md**](docs/GLOSSARY.md) — khoảng 45 thuật ngữ xếp
theo chủ đề, kèm chỗ dùng trong repo.

Bố cục vật lý xếp theo **loại artifact** vì đó là thứ công cụ Python và CI cần. Muốn đi
theo **giai đoạn** thì đọc bảng ở đầu trang, hoặc bản đồ đầy đủ ở
[docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md) mục 2bis — nó ghép hai trục
đó lại: mỗi dòng một giai đoạn, đọc ngang là đi hết giai đoạn qua mọi thư mục.

## Quyết định và giới hạn

Hai điều dự án **cố ý không làm**, và lý do.

### Vì sao không làm feature engineering

**Champion hiện hành và protocol Sprint 3 không tạo feature phái sinh.** Protocol thử nghiệm
`data-optimization-v1` bổ sung đúng một ablation có căn cứ từ EDA: cờ sentinel fold-local và
sentinel count. Thay đổi này chưa được promote vào scorer phát hành.

**Lý do.** `f0`–`f11` của Criteo v2.1 đã được **ẩn danh và chiếu ngẫu nhiên** trước khi
phát hành (xem [data card](docs/data_cards/CRITEO_V2_1.md)). Không feature nào có ý nghĩa
kinh doanh, nên không có giả thuyết miền nào để dựng interaction, tỉ số hay biến nhóm.
Mọi biến phái sinh tạo ra ở đây sẽ là tổ hợp của các trục ngẫu nhiên — thêm chiều mà
không thêm thông tin, và không diễn giải được khi cần giải thích cho bên kinh doanh.
LightGBM lại tự dựng được interaction dạng cây, nên phần lợi ích còn lại là nhỏ.

Bước phân tích dữ liệu bổ sung một lý do thực nghiệm cho quyết định này. Sáu trên mười hai
đặc trưng có `mode_share > 0,9` nên hầu như không có biến thiên để phái sinh; hai cặp
`(f4, f10)` và `(f5, f7)` có `|Spearman| = 0,999` nên đã dư thừa về thứ hạng. Ngược lại,
moderator mạnh nhất tìm thấy trong dữ liệu là **pattern sentinel-like** — hiệu ứng chênh ba
bậc độ lớn giữa các pattern. Vòng data optimization đã kiểm chứng giả thuyết biểu diễn rõ cấu
trúc này: Response tăng nhẹ, S-Learner giảm, nên không thể kết luận feature phái sinh luôn có
lợi. Số liệu ở [notebook 01](notebooks/01_eda_criteo.ipynb) mục 2 và 5.2 và
[báo cáo data optimization](report/DATA_OPTIMIZATION_REPORT.md).

**Quyết định về feature thực sự quan trọng ở dự án này là quyết định *loại bỏ*.**
`visit` và `exposure` **không** được dùng làm feature, dù cả hai tương quan rất mạnh với
`conversion`. Lý do: chúng xảy ra **sau** treatment. Đưa một biến post-treatment vào tập
covariate sẽ mở một collider path và làm hỏng tính nhận dạng của hiệu ứng nhân quả — mô
hình sẽ có metric đẹp hơn nhiều và kết luận nhân quả sai. Ràng buộc này được ghi vào
protocol (`excluded_post_treatment`) và mọi candidate dùng chung một feature contract
trong `src/candidates.py`, nên không model nào lỡ tay đọc thêm cột.

Bằng chứng số cho ràng buộc đó nằm ở `output/eda/post_treatment_leakage.csv`: `exposure` có
**đúng 0** sự kiện trong 2.096.937 dòng control, và `P(conversion = 1 | visit = 0) = 0`
chính xác — không tồn tại dòng nào conversion mà không visit. Một model biết `visit` loại
được 95,3% dân số khỏi diện có thể conversion mà không cần học gì.

**Thứ thay thế vai trò của feature engineering trong causal ML là nuisance
specification** — nơi công sức kỹ thuật thực sự đổ vào:

| Thành phần | Ở đâu | Vấn đề nó xử lý |
|---|---|---|
| Undersampling có hiệu chỉnh xác suất | `src/data.py`, `src/baselines.py` | conversion rate 0,29%; huấn luyện trên mẫu cân bằng rồi hiệu chỉnh ngược về thang xác suất gốc (Nyberg et al., PMLR 2021) |
| Cross-fitting 3-fold, hai fold seed | `src/experiment.py` | overfitting bias của nuisance model rò vào ước lượng CATE |
| Propensity là hằng số thiết kế | `configs/sprint3_improvement_protocol.json` | RCT nên `e` biết chính xác; vế IPW của tín hiệu DR luôn đúng |
| Biến đổi outcome-adjusted | `src/ranking_metrics.py` | giảm phương sai của tín hiệu chấm điểm (Bokelmann & Lessmann, EJOR 2024) |
| τ-isotonic calibration | `src/calibration.py` | đưa điểm số về thang CATE khi cần diễn giải độ lớn |

Bài toán nằm ở ước lượng một đại lượng không quan sát được từ tín hiệu `0,29%` mà không
đưa bias vào, không ở việc tạo thêm tín hiệu từ feature. Chi tiết
phương pháp: [Sprint 3 method guide](docs/SPRINT_3_METHOD_GUIDE.md).

### Phạm vi suy luận và giới hạn dữ liệu

- Response là ranking policy score, không phải calibrated individual CATE.
- Không quan sát principal stratum cá nhân.
- Balance diagnostics không tự chứng minh randomization; cần upstream provenance.
- Confirmation Sprint 2 đã được quan sát ở Sprint 2 và Sprint 3; kết quả trên tập đó
  là retrospective confirmation, không phải prospective unseen test.
- Không có claim SOTA: không challenger nào trong vòng cải tiến thắng được baseline,
  và benchmark bên ngoài dùng outcome khác nên không so trực tiếp được.
- Criteo không có outcome để kết luận incremental CLV hoặc observed profit.

## Đọc theo thứ tự

Ba đường vào, chọn theo mục đích. Cả ba dùng chung một tập tài liệu, chỉ khác thứ tự.

### Đường 1 — theo mạch phát triển

Khuyên dùng cho người đọc lần đầu, và cho người cần đánh giá cách làm chứ không chỉ kết
quả. Bắt đầu ở [**docs/END_TO_END_WORKFLOW.md**](docs/END_TO_END_WORKFLOW.md), rồi đi theo
bảng chín giai đoạn ở đầu trang này.

Nó trả lời câu hỏi mà không tài liệu nào khác trả lời: *vì sao dự án đi theo đúng thứ tự
đó, và bước tiếp theo được suy ra từ đâu.* Kèm bản đồ script–artifact–báo cáo của từng
giai đoạn, ranh giới của kết luận, và kiến trúc sản phẩm hai tầng.

### Đường 2 — kết quả mới nhất trước

Cho người đã quen bài toán và muốn xem phát hiện gần nhất. Bắt đầu ở
[**Sprint 1 report**](report/SPRINT_1_FINAL_REPORT.md) để lấy nền tảng và bảng model — nó
có sẵn trình tự đọc theo thời gian bạn có (15 phút / 1 giờ / nửa ngày), kiến trúc split,
giải thích từng module, và danh mục bẫy khi đọc kết quả. Sau đó:

1. [Top-tail research v2 report](report/TOP_TAIL_RESEARCH_V2_REPORT.md)
2. [Latest causal research and experiment plan](planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)
3. [Top-tail policy inference guide](docs/TOP_TAIL_POLICY_INFERENCE_GUIDE.md)
4. [Causal foundation experiment report](report/CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md)
5. [Causal foundation method guide](docs/CAUSAL_FOUNDATION_METHOD_GUIDE.md)
6. [Deep research về bài toán nhân quả](planning/CAUSAL_DEEP_RESEARCH_2026.md)
7. [Data optimization report](report/DATA_OPTIMIZATION_REPORT.md)
8. [Sprint 3 final report](report/SPRINT_3_FINAL_REPORT.md)
9. [Notebook 02 — modeling & evaluation](notebooks/02_modeling_and_evaluation.ipynb) — cùng
   nội dung ở dạng có biểu đồ và suy luận thống kê
10. [Sprint 3 method guide](docs/SPRINT_3_METHOD_GUIDE.md)
11. [Decision contract](docs/DECISION_CONTRACT.md)
12. [Sprint 2 final report](report/SPRINT_2_FINAL_REPORT.md)
13. [Data card](docs/data_cards/CRITEO_V2_1.md) và [model card](docs/model_cards/SPRINT_2_POLICY_RELEASE.md)
14. [Causal Forest report](report/CAUSAL_FOREST_REPORT.md)
15. [Bối cảnh nghiên cứu và bài toán lân cận](planning/RESEARCH_LANDSCAPE_2026.md)

### Đường 3 — theo vai trò

| Bạn cần | Đọc theo thứ tự này |
|---|---|
| Đánh giá phương pháp và code | [Sprint 1 report](report/SPRINT_1_FINAL_REPORT.md) → [notebook 01](notebooks/01_eda_criteo.ipynb) → [notebook 02](notebooks/02_modeling_and_evaluation.ipynb) → [src/README.md](src/README.md) |
| Tra một thuật ngữ | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| Hiểu quyết định kinh doanh | [Decision contract](docs/DECISION_CONTRACT.md) → mục [Demo](#demo) → [Sprint 2 report](report/SPRINT_2_FINAL_REPORT.md) mục 5 |
| Tái lập kết quả | [REPRODUCTION.md](docs/REPRODUCTION.md) → [scripts/README.md](scripts/README.md) → [output/README.md](output/README.md) |
| Mở một vòng nghiên cứu mới | [planning/README.md](planning/README.md) → [END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md) mục 9 |

Chỉ mục đầy đủ kèm trạng thái từng tài liệu: [docs/README.md](docs/README.md) và
[planning/README.md](planning/README.md).
