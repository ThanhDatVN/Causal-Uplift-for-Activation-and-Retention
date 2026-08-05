# Báo cáo Sprint 3 — Vòng cải tiến model, quyết định champion và web application

**Run ID:** `sprint3-retrospective-confirmation-v1`
**Protocol:** `sprint3-improvement-v1`, đăng ký trong `configs/sprint3_improvement_protocol.json`
**Ngày:** 05/08/2026
**Nguồn số chính thức:** `output/sprint3/`, `output/improvement/`
**Trạng thái:** hoàn thành local; Causal Forest Kaggle vẫn pending

## 1. Kết quả điều hành

Sprint 3 chạy một vòng cải tiến model có đăng ký trước metric, gate và promotion
rule, rồi áp rule đúng một lần.

**Kết quả: không challenger nào đạt promotion rule. Champion giữ nguyên Response.**

- 12 candidate được screening ở 20% development pool; 6 finalist chạy full
  development OOF ở hai fold seed; 9 model/ensemble được chấm trên retrospective
  confirmation.
- Trên metric chính `policy_area_dr`, Response đứng đầu ở **cả hai** fold seed OOF
  và trên confirmation.
- Không challenger nào có `oof_seeds_won = 2`, nên điều kiện 1 của promotion rule
  hỏng với tất cả. Điều kiện 2 cũng hỏng vì mọi chênh lệch trên confirmation đều âm.
- Số test tăng từ 51 lên **139**, toàn bộ pass.
- Web application có API và giao diện, 23/23 headless-browser acceptance pass.

Phát hiện đáng chú ý nhất là **metric bất đồng**: trên confirmation, Qini xếp
Ensemble-QAgg (`0,209845`), S-Under7 (`0,205904`) và X-Renormalized (`0,201812`)
cao hơn Response (`0,192989`), trong khi metric chính `policy_area_dr` và AUTOC đều
xếp Response cao nhất. Nếu Qini vẫn là metric chính, kết luận đã đảo chiều. Đây
đúng là tình huống mà việc đăng ký trước metric hierarchy được thiết kế để xử lý.

## 2. Điều đã thay đổi so với Sprint 1–2

| Hạng mục | Sprint 1–2 | Sprint 3 |
|---|---|---|
| Metric chính | Qini | `policy_area_dr` (DR policy value theo budget) |
| Metric phụ | AUUC, EUCE, transformed-outcome MSE | thêm AUTOC/RATE, biến thể outcome-adjusted, DR risk |
| Chọn model | validation split cố định | 3-fold cross-fitting OOF trên toàn development pool, hai fold seed |
| Comparator random | một ranking seed 42 | stochastic policy `π(x)=b` + 20 random-ranking seed |
| Ensemble | không có | causal Q-aggregation, best-single theo DR risk, rank average |
| Registry | không có | `output/improvement/registry.csv`, ghi cả run bị dừng sớm |
| Quyết định | mô tả | promotion rule 4 điều kiện, áp đúng một lần |

## 3. Giao thức dữ liệu

| Tập | Rows | Vai trò |
|---|---:|---|
| Development (Sprint 2 `fit + validation`) | 5.591.836 | cross-fitting OOF, chọn shortlist, học ensemble weights |
| Retrospective confirmation (Sprint 2 `confirmation`) | 1.397.959 | áp promotion rule đúng một lần |
| Final test Sprint 1 | 2.096.940 | bằng chứng lịch sử, không tái sử dụng |

Development pool có 14.684 conversion ở nhánh treatment và 1.625 ở nhánh control.
Hash source-index của cả ba split được đối chiếu với manifest Sprint 2 trước khi
chạy; lệch hash thì pipeline dừng.

Confirmation Sprint 2 đã được quan sát và báo cáo ở Sprint 2, nên mọi kết quả ở đây
được gọi là **retrospective confirmation**, không phải prospective unseen test.

## 4. Kết quả theo từng stage

### 4.1 Smoke 1% — chỉ kiểm tra code path

55.919 dòng, 16 conversion ở control. Quy tắc early-stop tự động kích hoạt thật:
X-Renormalized và S-Under7 trả về score hằng số vì undersampling `k = 7` trên mẫu
quá nhỏ khiến `min_child_samples = 1000` chặn mọi split. Cả hai được ghi vào
registry với `failure_reason = constant_score`. Không kết luận model nào từ stage này.

### 4.2 Screening 20% — fold seed 101

1.118.367 dòng, 325 conversion ở control, 1.353 giây.

| Candidate | `policy_area_dr` | AUTOC | Qini | Fit (giây) |
|---|---:|---:|---:|---:|
| Response | 0,000766 | 0,002729 | 0,176841 | 13,0 |
| Rank-K05 | 0,000698 | 0,002110 | 0,169579 | 108,5 |
| Rank-K1 | 0,000694 | 0,002228 | 0,168861 | 108,3 |
| X-Renormalized | 0,000693 | 0,002201 | 0,151600 | 6,5 |
| Rank-K2 | 0,000687 | 0,002030 | 0,165335 | 109,3 |
| S-Under7 | 0,000671 | 0,002190 | 0,129375 | 3,1 |
| DR-Regression | 0,000570 | 0,001862 | 0,076844 | 103,1 |
| DR-Binary-MC2 | 0,000569 | 0,001766 | 0,086485 | 171,8 |
| DR-Binary | 0,000554 | 0,001733 | 0,074232 | 98,7 |
| R-Binary | 0,000552 | 0,001764 | 0,067743 | 83,7 |
| R-Regression | 0,000522 | 0,001763 | 0,058726 | 81,3 |
| T-Under7 | 0,000519 | 0,001617 | 0,044794 | 3,0 |

Ở stage này paired CI của **mọi** challenger so với Response đều nằm hoàn toàn dưới
0. Họ DR-Learner và R-Learner bị Response và X-Renormalized dominate ở mọi budget
5–20% nên bị dừng theo đúng quy tắc early-stop đã đăng ký, không tiếp tục lên
full development.

Kết quả outcome-adjusted xếp hạng giống hệt kết quả raw ở mọi candidate. Đây là
cross-check quan trọng: nếu hai phiên bản metric cho thứ hạng khác nhau, kết luận
sẽ phụ thuộc lựa chọn kỹ thuật thay vì phụ thuộc dữ liệu.

### 4.3 Full development OOF — hai fold seed

5.591.836 dòng, 3 fold, 3.067 giây mỗi seed.

| Model | Trung bình | Nhỏ nhất | Seed 101 | Seed 202 |
|---|---:|---:|---:|---:|
| Response | 0,000861 | 0,000852 | 0,000852 | 0,000870 |
| Ensemble-QAgg | 0,000835 | 0,000834 | 0,000835 | 0,000834 |
| X-Renormalized | 0,000835 | 0,000826 | 0,000826 | 0,000844 |
| Ensemble-BestSingle | 0,000835 | 0,000826 | 0,000826 | 0,000844 |
| Ensemble-RankAverage | 0,000827 | 0,000826 | 0,000826 | 0,000827 |
| S-Under7 | 0,000814 | 0,000799 | 0,000829 | 0,000799 |
| Rank-K2 | 0,000798 | 0,000793 | 0,000793 | 0,000802 |
| Rank-K1 | 0,000787 | 0,000771 | 0,000771 | 0,000802 |
| Rank-K05 | 0,000771 | 0,000747 | 0,000747 | 0,000795 |

Expected-random policy area là `0,000151` với độ lệch chuẩn `0,0000167` qua 20
random-ranking seed. Mọi model đều cách xa random khoảng 5–6 lần.

`oof_seeds_won` của mọi challenger bằng 0: không challenger nào thắng Response ở
bất kỳ seed nào. Điều kiện 1 của promotion rule hỏng ngay tại đây.

Ghi chú về S-Under7: ở seed 101 chênh lệch so với Response có CI chứa 0
(`[-0,000052; +0,000007]`), nhưng ở seed 202 CI nằm hoàn toàn dưới 0
(`[-0,000101; -0,000044]`). Đây chính là lý do điều kiện 1 được kiểm tra theo từng
seed thay vì so hai giá trị đã gộp: gộp lại sẽ che mất tính không ổn định này.

### 4.4 Retrospective confirmation

1.397.959 dòng, 500 paired bootstrap, 1.704 giây.

| Model | `policy_area_dr` | AUTOC | Qini | AUUC | EUCE | Score âm |
|---|---:|---:|---:|---:|---:|---:|
| Response | 0,000912 | 0,003823 | 0,192989 | 0,006244 | không áp dụng | 0,0% |
| Ensemble-QAgg | 0,000911 | 0,003271 | 0,209845 | 0,006780 | 0,000526 | 16,8% |
| Ensemble-RankAverage | 0,000908 | 0,003332 | 0,195022 | 0,006304 | không áp dụng | 0,0% |
| S-Under7 | 0,000896 | 0,003116 | 0,205904 | 0,006658 | 0,000449 | 2,5% |
| X-Renormalized | 0,000890 | 0,003283 | 0,201812 | 0,006521 | 0,000404 | 23,7% |
| Ensemble-BestSingle | 0,000890 | 0,003283 | 0,201812 | 0,006521 | 0,000404 | 23,7% |
| Rank-K2 | 0,000862 | 0,002454 | 0,184993 | 0,005983 | không áp dụng | 83,4% |
| Rank-K1 | 0,000852 | 0,002400 | 0,185657 | 0,006005 | không áp dụng | 82,2% |
| Rank-K05 | 0,000848 | 0,002388 | 0,186454 | 0,006032 | không áp dụng | 80,2% |

Chênh lệch paired so với Response:

| Challenger | Δ `policy_area_dr` | 95% CI | Kết luận | Δ AUTOC | 95% CI |
|---|---:|---:|---|---:|---:|
| Ensemble-QAgg | -0,0000011 | [-0,0000563; +0,0000525] | CI chứa 0 | -0,000552 | [-0,001024; -0,000067] |
| Ensemble-RankAverage | -0,0000047 | [-0,0000575; +0,0000460] | CI chứa 0 | -0,000491 | [-0,000901; -0,000046] |
| S-Under7 | -0,0000168 | [-0,0000798; +0,0000462] | CI chứa 0 | -0,000707 | [-0,001250; -0,000164] |
| X-Renormalized | -0,0000226 | [-0,0000762; +0,0000240] | CI chứa 0 | -0,000540 | [-0,000962; -0,000108] |
| Rank-K2 | -0,0000504 | [-0,0000837; -0,0000198] | CI dưới 0 | -0,001369 | [-0,001765; -0,000920] |
| Rank-K1 | -0,0000605 | [-0,0000981; -0,0000184] | CI dưới 0 | -0,001423 | [-0,001856; -0,000975] |
| Rank-K05 | -0,0000639 | [-0,000108; -0,0000170] | CI dưới 0 | -0,001434 | [-0,001877; -0,000981] |

Trên AUTOC, **mọi** challenger có CI nằm hoàn toàn dưới 0. Trên `policy_area_dr`,
bốn challenger có CI chứa 0 và ba biến thể Rank-Learner có CI dưới 0. Không
challenger nào có CI với lower bound lớn hơn 0, tức điều kiện 3 cũng hỏng với
tất cả.

## 5. Quyết định champion

`output/sprint3/promotion_decision.csv` ghi kết quả áp rule cho từng challenger.
Không challenger nào đạt cả ba điều kiện định lượng:

| Điều kiện | Số challenger đạt |
|---|---:|
| 1 — thắng Response ở cả hai fold seed OOF | 0/8 |
| 2 — chênh lệch confirmation cùng dấu dương | 0/8 |
| 3 — paired 95% CI có lower bound > 0 | 0/8 |

**Champion giữ nguyên Response top-k.** Đây là kết quả "không cải thiện" và được
ghi đúng như vậy: bảy phương pháp mới, ba biến thể ensemble và một vòng screening
12 candidate không tạo ra bằng chứng đủ để thay một baseline không phải CATE
estimator.

## 6. Policy result

Kịch bản chính: budget 10%, `value = 1`, `cost = 0,0005`, trên retrospective
confirmation.

| Policy | DR net/khách hàng | 95% CI | Δ so random | 95% CI |
|---|---:|---:|---:|---:|
| Ensemble-QAgg top-k | 0,000870 | [0,000692; 0,001043] | 0,000830 | [0,000657; 0,001003] |
| S-Under7 top-k | 0,000869 | [0,000685; 0,001039] | 0,000829 | [0,000654; 0,000997] |
| Rank-K2 top-k | 0,000868 | [0,000697; 0,001032] | 0,000828 | [0,000665; 0,000998] |
| Rank-K05 top-k | 0,000858 | [0,000692; 0,001025] | 0,000818 | [0,000660; 0,000971] |
| Response top-k | 0,000856 | [0,000675; 0,001044] | 0,000816 | [0,000638; 0,000994] |
| Ensemble-RankAverage top-k | 0,000856 | [0,000674; 0,001023] | 0,000816 | [0,000644; 0,000981] |
| Rank-K1 top-k | 0,000850 | [0,000685; 0,001014] | 0,000810 | [0,000650; 0,000964] |
| X-Renormalized top-k | 0,000811 | [0,000629; 0,000983] | 0,000771 | [0,000600; 0,000947] |
| Random top-k | 0,000040 | [-0,000015; 0,000096] | — | — |
| Treat none | 0,000000 | — | -0,000040 | [-0,000096; +0,000015] |

Point estimate ở bảng này **không** được dùng để đổi champion sau khi xem
confirmation; selection contract đã khóa từ development OOF.

Đường cong ngân sách của Response:

| Budget | Gross/khách hàng | 95% CI | Chi phí hòa vốn |
|---:|---:|---:|---:|
| 1% | 0,000536 | [0,000386; 0,000672] | 0,053614 |
| 2% | 0,000690 | [0,000530; 0,000835] | 0,034494 |
| 5% | 0,000857 | [0,000678; 0,001032] | 0,017134 |
| 10% | 0,000906 | [0,000725; 0,001094] | 0,009059 |
| 15% | 0,000921 | [0,000736; 0,001102] | 0,006140 |
| 20% | 0,000969 | [0,000788; 0,001152] | 0,004847 |
| 25% | 0,000987 | [0,000806; 0,001168] | 0,003949 |
| 30% | 0,000986 | [0,000802; 0,001169] | 0,003288 |

Với một triệu khách hàng, Response top 10% tương ứng khoảng `906` incremental
conversions, 95% CI `[725; 1.094]`. Đây là phép scale với giả định population
tương tự confirmation, không phải forecast đã deploy. Mọi giá trị tiền là
conversion-equivalent scenario, không phải doanh thu hay lợi nhuận quan sát được.

## 7. Điều học được về từng phương pháp

### Rank-Learner (ICLR 2026)

Là challenger CATE-style mạnh nhất ở screening 20% (`0,000698` so với
X-Renormalized `0,000693`), nhưng **tụt hạng khi có nhiều dữ liệu hơn**: ở full
development, cả ba biến thể `kappa` đều thấp hơn X-Renormalized và S-Under7, và
trên confirmation là ba model thấp nhất theo metric chính. Cách đọc phù hợp là
lợi thế của paper nằm ở chế độ mẫu nhỏ — paper cũng báo "largest gains in
small-sample regimes" — chứ không ở chế độ 5,6 triệu dòng.

Chi phí cũng là một dữ kiện: 638 giây fit so với 33 giây của X-Renormalized và
10,8 giây của S-Under7 trên cùng dữ liệu, tức chậm gấp 19–59 lần cho kết quả thấp hơn.

Tỷ lệ score âm 80–83% trên confirmation là hệ quả của việc score này không có
scale CATE; nó chỉ mang thứ tự, nên dấu của nó không diễn giải được.

### Causal Q-Aggregation (AISTATS 2024)

Weights hội tụ về `X-Renormalized 0,5 / S-Under7 0,5` ở cả hai fold seed và cả hai
inner fold — rất ổn định. Nhưng lý do ổn định lại là một hạn chế: **DR loss gần như
không phân biệt được các model trên benchmark này**. Ở full development, DR loss là
`0,01448225` cho X-Renormalized và `0,01448235` cho S-Under7 — chênh lệch tương đối
khoảng `7e-6`. Với outcome hiếm, variance của pseudo-outcome áp đảo phần chênh lệch
do CATE, nên mục tiêu gần như phẳng và Q-aggregation về bản chất đang lấy trung
bình chứ không chọn.

Hệ quả thực hành: DR risk không nên là metric chọn model trên dữ liệu kiểu này.
Đây là bằng chứng cụ thể ủng hộ quyết định đặt `policy_area_dr` làm metric chính.

Ở screening 20%, best-single theo DR risk chọn S-Under7 trong khi
`policy_area_dr` xếp X-Renormalized cao hơn S-Under7 — hai tiêu chí cho hai câu
trả lời khác nhau trên cùng dữ liệu.

### R-Learner và DR-Learner

Cả hai họ đều xếp dưới meta-learner đơn giản ở mọi cấu hình đã thử, với khoảng cách
lớn (`0,00052`–`0,00057` so với `0,00067`–`0,00077`). `discrete_outcome=True` không
cải thiện so với `False`; `mc_iters=2` cải thiện nhẹ DR nhưng làm runtime gấp đôi và
vẫn thấp hơn baseline. Giả thuyết "nuisance dạng classifier phù hợp outcome nhị
phân hiếm hơn regressor" không được dữ liệu ủng hộ ở thiết lập này.

### S-Learner

UpliftBench 2026 (arXiv 2604.06123) báo S-Learner đứng đầu trên chính Criteo v2.1
theo Qini. Ở đây S-Under7 quả thật là meta-learner tốt nhất theo Qini trên
confirmation (`0,205904`, cao hơn X-Renormalized `0,201812`), phù hợp với báo cáo
đó. Nhưng UpliftBench dùng outcome `visit` (4,7%) còn dự án này dùng `conversion`
(0,29%), và theo metric chính S-Under7 vẫn dưới Response. Hai kết quả không mâu
thuẫn; chúng trả lời hai câu hỏi khác nhau trên hai outcome khác nhau.

### Vì sao Response vẫn đứng đầu

Response không phải CATE estimator; nó xếp hạng theo `P(conversion)`. Trên Criteo
với conversion 0,29% và treatment/control 85/15, tín hiệu heterogeneity của
treatment effect nhỏ so với nhiễu, trong khi tín hiệu của `P(conversion)` mạnh và
dễ học. Ba sprint liên tiếp cho cùng kết luận này bằng ba giao thức khác nhau.

Rà soát tài liệu ngày 05/08/2026 cho thấy đây là một chế độ **đã được mô tả trước**,
từ bốn hướng độc lập. Chi tiết và mức xác minh từng nguồn nằm trong
`planning/RESEARCH_LANDSCAPE_2026.md` mục 1.

1. **Causal bias–variance tradeoff.** Fernández-Loría & Provost, JMLR 23(59), 2022,
   đặt tên bài toán này là *causal classification* và chứng minh outcome prediction
   có bias so với CATE nhưng variance nhỏ hơn nhiều; khi variance của ước lượng CATE
   đủ lớn, outcome prediction ra ít quyết định sai hơn. Bốn điều kiện thuận lợi họ
   nêu đều đúng ở đây, gồm cả điều kiện "bias sửa được một phần bằng cách chọn ngưỡng
   khác" — chính là policy top-k.
2. **Proxy phản ánh dominant moderator.** Fernández-Loría & Loría, arXiv 2206.12532
   (bản sửa 10/2025), nêu điều kiện để một proxy dự báo xếp hạng đúng theo mức đáp
   ứng treatment mà không cần ước lượng hiệu ứng, và chỉ riêng bối cảnh discrete
   choice nơi "xu hướng hành động khi không có can thiệp điều tiết mức độ bị thuyết
   phục". Response chính là ước lượng của đại lượng đó.
3. **Chính nhóm tạo dataset đã cảnh báo.** Diemert et al., AdKDD 2018, khuyến nghị
   mô hình hóa uplift trên `visit` thay vì `conversion` vì tín hiệu uplift của
   `conversion` quá yếu do mất cân bằng nhãn.
4. **Hai tên gọi hiện đại.** VALOR (arXiv 2604.02472, 2026) gọi hiện tượng main
   effect tiên lượng áp đảo và đẩy phần heterogeneous về 0 là *prognostic dominance*,
   và hiện tượng loss bị các số 0 chi phối là *counterfactual gradient collapse*.
   Benchmark deep uplift (arXiv 2406.00335) báo baseline đơn giản cạnh tranh được với
   phương pháp deep trên chính Criteo conversion.

Cách đọc đúng kết quả Sprint 3 vì thế không phải "thử nhiều phương pháp và không cái
nào chạy", mà là "một giao thức đăng ký trước đã xác nhận được chế độ mà tài liệu dự
đoán, trên chính dataset mà nhóm tạo ra nó đã cảnh báo về estimand này".

Điều đó **không** có nghĩa Response tốt hơn theo mọi tiêu chí. Nó không cho ước
lượng CATE có scale, không có EUCE diễn giải được, và không tách được persuadable
khỏi sure-thing. Nó chỉ thắng theo đúng các metric ranking/policy đã được báo cáo.

Một hệ quả kiểm chứng được, chưa chạy: nếu chạy lại đúng pipeline này với outcome
`visit` (tỷ lệ 4,7% thay vì 0,29%) và các CATE learner tách được khỏi Response ở đó,
thì đó là bằng chứng giao thức có đủ power và kết luận trên `conversion` là kết luận
về dữ liệu chứ không phải về pipeline. Dùng `visit` làm **outcome** là một estimand
khác và hợp lệ; dùng `visit` làm **feature** vẫn là leakage và vẫn bị cấm.

## 7bis. Ba chẩn đoán bổ sung (05/08/2026)

Ba hạng mục dưới đây được thêm sau vòng cải tiến chính, để trả lời những câu hỏi mà kết
quả "không cải thiện" đặt ra nhưng bản thân nó không trả lời được.

### 7bis.1 Power diagnostic — giao thức có đủ độ nhạy không?

**Câu hỏi:** không challenger nào tách được khỏi Response. Đó là do dữ liệu, hay do
pipeline thiếu power?

**Cách làm:** chạy lại **đúng** pipeline screening 20%, cùng fold seed 101, cùng split,
chỉ đổi outcome sang `visit` (4,7% thay vì 0,29%). Cùng 1.118.367 dòng, nhưng số positive
ở control tăng từ 325 lên **6.414**, tức gấp gần 20 lần.

| Candidate | `policy_area_dr` (visit) | Δ vs Response | 95% CI | `policy_area_dr` (conversion) |
|---|---:|---:|---:|---:|
| Response | 0,005133 | — | — | 0,000766 |
| DR-Binary | 0,005036 | -0,000097 | [-0,000507; +0,000350] | 0,000554 |
| X-Renormalized | 0,004840 | -0,000293 | [-0,000766; +0,000236] | 0,000693 |
| R-Binary | 0,004838 | -0,000295 | [-0,000653; +0,000147] | 0,000552 |
| S-Under7 | 0,004603 | -0,000530 | [-0,000980; -0,000007] | 0,000671 |
| T-Under7 | 0,004115 | -0,001018 | [-0,001479; -0,000557] | 0,000519 |

**Kết luận rút ra được:**

1. **Giao thức có phản ứng với độ mạnh tín hiệu.** Trên `conversion`, paired CI của **mọi**
   challenger nằm hoàn toàn dưới 0. Trên `visit`, ba challenger (DR-Binary, X-Renormalized,
   R-Binary) có CI **chứa 0**, tức trở thành không phân biệt được với Response. Họ
   DR/R-Learner — vốn bị dominate rõ trên `conversion` — thu hẹp khoảng cách đáng kể.
2. **Response vẫn dẫn đầu trên cả hai outcome** theo metric chính. Nên kết luận "Response
   khó bị đánh bại" không phải chỉ là hệ quả của outcome hiếm.
3. **Qini lại lệch hướng với giá trị quyết định.** Qini của Response trên `visit` là
   `0,081139`, thấp hơn nhiều so với `0,176841` trên `conversion`, trong khi
   `policy_area_dr` lại **cao gấp 6,7 lần**. Đây là minh hoạ trực tiếp cho việc Qini là đại
   lượng đã chuẩn hóa và không theo dõi giá trị quyết định.

**Phạm vi bắt buộc:** `visit` là **estimand khác**. Kết quả trên nó là chẩn đoán cho
phương pháp, **không** phải kết quả sản phẩm, và không được trộn metric giữa hai outcome.
Dùng `visit` làm outcome hợp lệ; dùng nó làm feature vẫn là leakage và vẫn bị cấm.

Artifact: `output/improvement/screen_visit/`. Registry ghi cột `outcome` cho mọi run.

### 7bis.2 Chẩn đoán proxy-ordering — khi nào Response ngừng thắng?

Fernández-Loría & Loría (arXiv 2206.12532 v7) cho một **điều kiện đủ** để một proxy dự báo
xếp hạng đúng theo CATE:

```
theta_max < (1 − beta_max) / 2
```

`theta_max` là xác suất baseline lớn nhất trong population; `beta_max` là chặn trên của
CATE lớn nhất.

Trên development OOF (5.591.836 dòng):

| Đại lượng | Giá trị |
|---|---:|
| `theta_max` = max `mu0` | 0,885764 |
| Ngưỡng với `beta_max = 0,598` | 0,200783 |
| Điều kiện thỏa | **Không** |

Độ nhạy: điều kiện hỏng ở **mọi** lựa chọn `beta_max`, kể cả `beta_max = 0` (ngưỡng 0,5).
Nguyên nhân là `theta_max`, không phải lựa chọn `beta_max`. Chỉ 1.313 dòng (0,023%) có
`mu0 >= 0,5`.

**Cách đọc đúng:** đây là điều kiện **đủ**, không phải điều kiện **cần**. Điều kiện hỏng
**không** kết luận Response xếp hạng sai — bằng chứng thực nghiệm nói ngược lại. Nó nói
khung lý thuyết này không bao phủ trường hợp đang xét, nên lời giải thích cho việc Response
thắng phải dựa vào causal bias–variance tradeoff (mục 7) chứ không dựa vào định lý ordering
này.

**Một kết quả âm về mở rộng của chính repo:** ngoài điều kiện gốc, repo thêm một bảng áp
cùng bất đẳng thức cho từng nhóm top-b, kỳ vọng điều kiện sẽ thỏa ở budget nhỏ. Nó **không**
thỏa ở bất kỳ budget nào, vì các cá nhân có baseline cực cao lại chính là những người
Response xếp đầu bảng. Mở rộng này không thêm thông tin trên dataset này; ghi lại thay vì bỏ đi.

Tương quan thứ hạng giữa Response và các CATE estimator: S-Under7 `0,800`, Rank-K05 `0,744`,
Rank-K1 `0,710`, plug-in tau `0,560`, X-Renormalized `0,485`.

Artifact: `output/improvement/proxy_diagnostic/`. Ranh giới nguồn ba mức được ghi trong
docstring của `src/proxy_diagnostic.py`.

### 7bis.3 Resource gate kiểm tra liên tục

Mục 8 ghi nhận resource gate chỉ được kiểm tra **trước khi chạy**, và ở các stage full-data
RAM khả dụng đã tụt xuống 1,55 GB — dưới ngưỡng 2,0 GB đã đăng ký — mà không có gì dừng lại.

`ResourceMonitor` nay nhận `min_available_gb`, bật cờ khi vi phạm, và runner gọi
`raise_if_breached()` tại **điểm dừng an toàn**: giữa hai fold và giữa hai candidate.

Vì sao không dừng ngay lập tức: một thread nền không thể ngắt an toàn một lệnh fit LightGBM
đang giữ bộ nhớ, và ngắt giữa chừng dễ để lại artifact hỏng. Dừng ở điểm an toàn vẫn ghi
được registry đầy đủ và vẫn giữ được artifact của các candidate đã xong.

Ngưỡng lấy từ chính `configs/sprint3_improvement_protocol.json`, không phải hằng số rời rạc
trong script. Sáu test trong `tests/test_resource_gate.py` khóa hành vi này.

## 8. Hạ tầng và resource

| Stage | Rows | Wall time | Peak process RSS | RAM khả dụng thấp nhất |
|---|---:|---:|---:|---:|
| Smoke 1% | 55.919 | 47 giây | — | — |
| Screening 20% | 1.118.367 | 1.353 giây | 1,29 GB | — |
| Full OOF seed 101 | 5.591.836 | 3.067 giây | 3,20 GB | 1,55 GB |
| Full OOF seed 202 | 5.591.836 | 3.067 giây | 3,21 GB | 1,60 GB |
| Retrospective confirmation | 1.397.959 | 1.704 giây | 2,81 GB | 1,83 GB |

**Quan sát cần ghi:** ở các stage full-data, RAM khả dụng của hệ thống tụt xuống
1,55–1,83 GB, tức dưới ngưỡng 2,0 GB đã đăng ký trong `resource_gate`. Gate hiện
được kiểm tra **trước khi chạy**, không kiểm tra liên tục trong lúc chạy, nên các
run này không bị dừng. Không có run nào thất bại vì bộ nhớ, nhưng biên an toàn hẹp
hơn mức đã đăng ký và điều này nên được sửa trước khi thêm model nặng hơn.

Causal Forest vẫn chưa chạy trên Kaggle; không có kết quả cloud nào trong release này.

## 9. Web application

`webapp/` phục vụ artifact release qua FastAPI và một giao diện một trang không
phụ thuộc CDN. App không train model khi nhận request; `/api/score` dùng scorer đã
fit sẵn trên development pool.

Tính năng: tổng quan release, so sánh model kèm paired CI, budget/policy explorer
có slider và input value/cost, đường cong ngân sách có CI, lưới độ nhạy theo chi
phí, uplift theo decile, chẩn đoán cân bằng, batch scoring từ CSV hoặc JSON,
experiment registry, bảng giới hạn/giả định và export CSV.

Kiểm thử: 19 test cho API và 23/23 headless-browser acceptance check. Trong đó có
một test chức năng chấm điểm 2.000 dòng Criteo thật: ở budget 10%, scorer target
9,9% số dòng và tỷ lệ conversion trong nhóm được target là `0,04545` so với `0,00000`
ở phần còn lại, tức scorer đã lưu vẫn giữ được sức phân biệt chứ không chỉ trả về
đúng kiểu dữ liệu. Runbook: `docs/WEBAPP.md`.

## 10. Bằng chứng chất lượng

- 139/139 pytest pass, tăng từ 51 ở đầu Sprint 3.
- Synthetic-truth test cho mọi metric mới: score oracle phải thắng random và thắng
  ranking đảo ngược; bất biến với biến đổi đơn điệu tăng; score hằng số cho RATE
  bằng 0; giá trị hữu hạn trên mẫu rare-outcome.
- Test đối chiếu release: `dr_policy_value_curve` tái lập đúng cột DR đã phát hành
  ở Sprint 2 với sai khác tối đa `2,6e-08`; Qini tính lại khớp số đã báo cáo trong
  dung sai của việc lưu prediction ở `float32`; bảng Qini Sprint 1 trong tài liệu
  khớp artifact.
- Hai lỗi thật bị test bắt trong lúc phát triển: tie không được gộp trong TOC/RATE
  (làm score hằng số cho RATE khác 0) và cùng lỗi đó trong đường cong policy value.
- Một khẳng định sai của chính tài liệu bị bác bỏ bằng chứng minh: AUTOC không phản
  đối xứng khi đảo ngược ranking; chỉ biến thể `α(q)=q` mới đổi dấu chính xác.

## 11. Hạng mục chưa hoàn thành

- **Causal Forest Kaggle 20/30/50** vẫn pending; cần session và dataset attachment
  bên ngoài. Runbook đầy đủ và code đã chuẩn bị xong trong
  `docs/KAGGLE_RUNBOOK_COMPLETE.md`; bước chấm điểm còn thiếu đã được bổ sung bằng
  `scripts/evaluate_causal_forest.py`, và đã kiểm chứng rằng ở `frac=0.50` holdout
  trùng khít final test Sprint 1 nên kết quả sẽ so trực tiếp được với bảng release.
- **pROCini (JMLR 2025)** nằm trong P0 của kế hoạch nhưng không được hiện thực:
  trang paper công khai không cung cấp công thức và repo không tiếp cận được bản
  đầy đủ. Hiện thực từ suy đoán sẽ vi phạm quy tắc không tự chế công thức của dự
  án. Ghi là chưa làm, không ghi là đã cân nhắc và loại bỏ.
- **PUC/PTONet, AutoCATE, TARNet/DragonNet** đã research và ghi phạm vi, chưa chạy;
  không nằm trên critical path sau khi P0 không tách được challenger nào khỏi Response.
- **External validity (Hillstrom)** chưa chạy; chưa có bằng chứng portability sang
  dataset thứ hai.
- **Production A/B test** của learned policy chưa có; mọi kết quả là offline.
- **Docker, CI đầy đủ, video demo và slide deck** — lệch khỏi kế hoạch gốc của Sprint 3;
  xem `report/weekly/WEEK_05.md` mục 5.1. CI chạy phần test không cần dữ liệu đã được
  thêm sau (`.github/workflows/tests.yml`, 98/139 test); Docker và phần trình bày chưa có.
- **LICENSE** chưa có; đây là quyết định về quyền sở hữu, không tự chọn thay chủ repo.

### Ba hạng mục đã hoàn thành sau khi bản đầu của báo cáo này được viết

Bản đầu ghi ba mục dưới đây là chưa làm. Chúng đã được thực hiện, kết quả ở mục 7bis:

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Resource gate kiểm tra liên tục | **Đã làm** | `src/experiment.py::ResourceMonitor`, `tests/test_resource_gate.py` |
| Power diagnostic bằng outcome `visit` | **Đã làm** | `output/improvement/screen_visit/`, mục 7bis.1 |
| Diagnostic đánh giá proxy utility | **Đã làm** | `src/proxy_diagnostic.py`, `output/improvement/proxy_diagnostic/`, mục 7bis.2 |

### Hướng tiếp theo còn lại

Xếp theo tỷ lệ giá trị trên chi phí trong `planning/RESEARCH_LANDSCAPE_2026.md` mục 5:

1. **causal post-processing** của Response bằng dữ liệu randomized (arXiv 2406.09567);
   repo đã có sẵn cả hai thành phần đầu vào mà phương pháp yêu cầu. **Chặn ở mức nguồn
   `B`** — mới đọc được abstract và mô tả phương pháp, chưa đọc được công thức.
2. **mở rộng `src/policy.py` sang ràng buộc ngân sách không đồng nhất** theo cấu trúc
   knapsack (arXiv 2605.12235); top-k hiện tại là trường hợp riêng khi chi phí đồng nhất.
   **Chặn ở mức nguồn `B`.**
3. **ForestDRLearner (M-FDR)** trong kế hoạch P1 chưa hiện thực; sẽ cần chạy trên Kaggle
   như Causal Forest vì cùng đặc tính tài nguyên.

Cả ba đều yêu cầu nâng nguồn lên mức xác minh `A` (đọc được công thức) trước khi code,
theo quy tắc nguồn của dự án.

## 12. Lệnh tái lập

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.01 --stage smoke --n-boot 50 --output-dir output\improvement\smoke
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.20 --stage screen --n-boot 300 --output-dir output\improvement\screen
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 1.0 --stage finalist --fold-seed 101 --n-boot 200 --candidates "Response,X-Renormalized,S-Under7,Rank-K05,Rank-K1,Rank-K2" --output-dir output\improvement\finalist
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 1.0 --stage finalist --fold-seed 202 --n-boot 200 --candidates "Response,X-Renormalized,S-Under7,Rank-K05,Rank-K1,Rank-K2" --output-dir output\improvement\finalist_seed202
.venv\Scripts\python.exe scripts\compare_improvement_candidates.py --run-dir output\improvement\finalist --run-dir output\improvement\finalist_seed202 --n-boot 200 --shortlist-size 4 --output-dir output\improvement\finalist_comparison
.venv\Scripts\python.exe scripts\run_sprint3_confirmation.py --shortlist output\improvement\finalist_comparison\shortlist.json --oof-run-dir output\improvement\finalist_comparison --n-boot 500
.venv\Scripts\python.exe scripts\build_champion_scorer.py
.venv\Scripts\python.exe -m pytest tests -q
node scripts\smoke_webapp_browser.mjs
```

## 13. Phạm vi suy luận

- Kết quả là offline policy evaluation trên một RCT benchmark; chưa có A/B test
  production.
- Criteo không có doanh thu, biên lợi nhuận hay chi phí liên hệ; mọi giá trị tiền
  là kịch bản giả định.
- Không quan sát được principal stratum của bất kỳ cá nhân nào.
- Response là ranking policy score, không phải calibrated CATE.
- Confirmation là retrospective; nó không thay thế được một tập chưa từng quan sát.
- Không có claim "SOTA": không challenger nào trong vòng này thắng được baseline,
  và benchmark bên ngoài dùng outcome khác nên không so trực tiếp được.
