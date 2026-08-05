# Bối cảnh nghiên cứu và các bài toán lân cận

**Ngày rà soát:** 05/08/2026
**Mục đích:** đặt kết quả Sprint 3 vào đúng bối cảnh nghiên cứu, và xác định bài toán
lân cận nào đáng mở tiếp, với lý do và điều kiện cụ thể.
**Phạm vi:** đây là tài liệu scoping. Không con số nào ở đây là kết quả đã chạy trong
repo; kết quả của repo nằm trong `report/`.

## 0. Cách đọc và mức độ xác minh nguồn

Mỗi nguồn được gắn một mức xác minh. Quy tắc của dự án là không trình bày nội dung
suy đoán như nội dung đã đọc.

| Mức | Nghĩa |
|---|---|
| `A` | Đã đọc được phần phương pháp/công thức đủ để hiện thực |
| `B` | Đã đọc abstract và mô tả phương pháp, chưa có công thức đầy đủ |
| `C` | Chỉ có metadata hoặc mô tả gián tiếp; chưa đủ để trích dẫn kỹ thuật |

Không hiện thực bất cứ phương pháp nào ở mức `C` mà không nâng lên `A` trước.

## 1. Phát hiện trung tâm của repo đã có lời giải thích trong tài liệu

Ba sprint liên tiếp, với ba giao thức khác nhau, đều cho cùng kết luận: **Response —
một model dự báo `P(conversion)` không phải CATE estimator — xếp hạng tốt hơn mọi
CATE learner đã thử trên Criteo `conversion`.** Sprint 3 kiểm tra lại bằng metric
chính đăng ký trước, cross-fitting hai seed và paired CI, và kết luận không đổi.

Đây không phải dị thường. Nó là chế độ đã được mô tả trong tài liệu, từ bốn hướng
độc lập.

### 1.1 Causal bias–variance tradeoff

Fernández-Loría & Provost, *Causal Classification: Treatment Effect Estimation vs.
Outcome Prediction*, JMLR 23(59), 2022 —
[jmlr.org/papers/v23/19-480.html](https://jmlr.org/papers/v23/19-480.html) — mức `B`.

Bài toán họ đặt tên là *causal classification*: xác định cá nhân mà outcome sẽ bị
treatment làm thay đổi theo hướng tốt, đúng bài toán của repo này. Kết quả chính là
một đánh đổi bias–variance mang tính nhân quả: **outcome prediction có bias so với
CATE nhưng variance nhỏ hơn nhiều**, và khi variance của ước lượng CATE đủ lớn, tổng
số quyết định sai của outcome prediction lại ít hơn.

Bốn điều kiện được nêu là thuận lợi cho outcome prediction:

1. dữ liệu để ước lượng counterfactual bị hạn chế;
2. sampling variance của CATE estimation lớn hơn bias của outcome prediction;
3. outcome và treatment effect tương quan với nhau;
4. bias có thể được sửa một phần bằng cách chọn ngưỡng khác.

Criteo `conversion` thỏa cả bốn: control chỉ có 1.625 conversion trong development
pool 5,59 triệu dòng; CATE thật ở mức `1e-3`; và policy của repo là top-k, tức đúng
"chọn ngưỡng khác" ở điều kiện 4.

### 1.2 Proxy và dominant moderator

Fernández-Loría & Loría, *Causal Ordering Without Effect Estimation: A Framework for
Using Proxies in Treatment Prioritization*, arXiv 2206.12532, bản sửa 10/2025 —
[arxiv.org/abs/2206.12532](https://arxiv.org/abs/2206.12532) — mức `B`.

Khung này nói khi nào một proxy dự báo có thể xếp hạng đúng theo mức độ đáp ứng
treatment mà **không** cần ước lượng hiệu ứng. Hai điều kiện:

- proxy phản ánh một **dominant moderator** của treatment effect;
- hoặc proxy nhắm vào tín hiệu **dễ ước lượng chính xác hơn**, kể cả khi moderator
  nó phản ánh không phải dominant.

Các tác giả nêu riêng bối cảnh *discrete choice*, nơi "xu hướng hành động khi không
có can thiệp điều tiết mức độ bị thuyết phục". Quảng cáo hiển thị của Criteo đúng là
bối cảnh đó, và Response chính là ước lượng của "xu hướng hành động khi không có can
thiệp". Đây là lời giải thích cụ thể nhất cho kết quả của repo.

Lưu ý nguồn: bản arXiv 2504.02456 (*The Amenability Framework*) là bản thay thế của
chính bài này và **đã bị rút**. Chỉ trích dẫn 2206.12532.

### 1.3 Chính tác giả dataset đã cảnh báo

Diemert, Betlei, Renaudin & Amini, *A Large Scale Benchmark for Uplift Modeling*,
AdKDD @ KDD 2018 —
[papers.adkdd.org](http://papers.adkdd.org/2018/papers/adkdd18-diemert-large-scale.pdf) —
mức `B`.

Nhóm tạo ra chính Criteo v2.1 khuyến nghị mô hình hóa uplift trên `visit` thay vì
`conversion`, vì tín hiệu uplift của `conversion` quá yếu do mất cân bằng nhãn. Với
`visit` họ đạt được ý nghĩa thống kê ở mẫu nhỏ hơn nhiều; với `conversion` cần mẫu
lớn nhất mới có kết quả tương đương.

Hệ quả cho repo: việc không tách được challenger nào khỏi Response **không phải lỗi
pipeline**. Nó là đặc tính đã biết của estimand đã chọn.

### 1.4 Hai tên gọi hiện đại của cùng hiện tượng

VALOR, arXiv 2604.02472 (2026) —
[arxiv.org/html/2604.02472](https://arxiv.org/html/2604.02472) — mức `B` — đặt tên
hai cơ chế:

- **Prognostic dominance:** main effect tiên lượng mạnh áp đảo biểu diễn tiềm ẩn và
  đẩy phần heterogeneous treatment effect về 0, khiến uplift model thoái hóa thành
  một propensity estimator.
- **Counterfactual gradient collapse:** với outcome zero-inflated, loss MSE chuẩn
  làm model dự đoán uplift gần 0 ở mọi nơi vì gradient bị các số 0 chi phối.

Criteo `conversion` ở mức 0,29% là trường hợp cực đoan của cả hai.

*Benchmarking for Deep Uplift Modeling in Online Marketing*, arXiv 2406.00335 —
[arxiv.org/pdf/2406.00335](https://arxiv.org/pdf/2406.00335) — mức `B` — báo rằng
trên chính Criteo với outcome conversion, **baseline đơn giản cạnh tranh được với
các phương pháp deep**. Điều này phù hợp với việc ba biến thể Rank-Learner của repo
không thắng được meta-learner đơn giản.

### 1.5 Điều cần ghi vào báo cáo

Kết luận "không cải thiện" của Sprint 3 nên được trình bày kèm bốn nguồn trên. Nó
chuyển kết quả từ "chúng tôi thử nhiều thứ và không cái nào chạy" thành "chúng tôi
xác nhận được một chế độ đã có dự đoán lý thuyết, bằng một giao thức đăng ký trước".

## 2. Hướng đi có giá trị cao nhất cho chính repo này

Xếp theo tỷ lệ giá trị trên chi phí, có tính đến việc repo đã có sẵn gì.

### 2.1 Causal post-processing của Response — ưu tiên 1

Fernández-Loría và cộng sự, *Causal Post-Processing of Predictive Models*,
arXiv 2406.09567 —
[arxiv.org/pdf/2406.09567](https://arxiv.org/pdf/2406.09567) — mức `B`.

Bài toán đúng bằng bài toán của repo: đã có một model dự báo mạnh, đã có dữ liệu
randomized, làm sao kết hợp hai thứ thay vì chọn một. Phương pháp hiệu chỉnh output
của model có sẵn bằng thông tin nhân quả, không train lại từ đầu.

Dữ liệu cần: prediction của model có sẵn trên population đích, và ước lượng hiệu ứng
từ thí nghiệm randomized. **Repo có cả hai**: `output/webapp/champion_scorer.joblib`
và DR signal đã cross-fit trong `output/improvement/finalist/oof_scores.npz`.

Điều kiện trước khi code: nâng nguồn lên mức `A`. Không hiện thực từ abstract.

### 2.2 Diagnostic cho proxy utility — ưu tiên 2

arXiv 2206.12532 có phần công cụ chẩn đoán để đánh giá một proxy có hữu ích không.
Repo hiện chỉ chứng minh Response thắng bằng thực nghiệm; một diagnostic sẽ trả lời
được **vì sao** và **khi nào nó sẽ ngừng thắng**, tức là điều kiện phải theo dõi khi
vận hành. Đây là loại kết quả trực tiếp làm mạnh phần production thinking.

### 2.3 `visit` như một outcome thứ hai — ưu tiên 3, cần cẩn trọng

Đây là điểm dễ hiểu sai nên phải phát biểu chính xác:

- Dùng `visit` làm **feature** là leakage. `visit` xảy ra sau treatment. Quy tắc hiện
  tại của repo giữ nguyên, không đổi.
- Dùng `visit` làm **outcome** là một **estimand khác**, hoàn toàn hợp lệ. Đó chính
  là điều Diemert et al. khuyến nghị và là điều UpliftBench 2026 làm.

Giá trị: nếu chạy đúng pipeline Sprint 3 với outcome `visit`, repo sẽ có một câu trả
lời cho câu hỏi "phương pháp của chúng tôi có phát hiện được cải thiện khi tín hiệu
đủ mạnh không?". Nếu ở `visit` các CATE learner tách được khỏi Response còn ở
`conversion` thì không, đó là bằng chứng mạnh rằng giao thức có power và kết luận
`conversion` là kết luận về dữ liệu chứ không phải về pipeline.

Chi phí: gần bằng 0 về code. `src/data.py` đã có `outcome` là tham số; runner cần
thêm một cờ. Đây là thí nghiệm có tỷ lệ giá trị trên chi phí cao nhất trong tài liệu này.

Bắt buộc kèm theo: `visit` không phải mục tiêu kinh doanh mà repo tuyên bố. Kết quả
`visit` chỉ được dùng làm **power diagnostic cho phương pháp**, không được trình bày
như kết quả sản phẩm, và không được trộn metric giữa hai outcome.

### 2.4 Denoised IPW-Lasso cho chế độ tín hiệu yếu — ưu tiên 4

arXiv 2510.10527 — [arxiv.org/pdf/2510.10527](https://arxiv.org/pdf/2510.10527) —
mức `B`. Nhắm đúng chế độ tín hiệu yếu trên RCT: khử nhiễu ước lượng outcome bằng
IPW rồi dùng Lasso để chọn biến điều tiết thưa. Với 12 feature ẩn danh, phần chọn
biến ít giá trị, nhưng phần khử nhiễu thì liên quan trực tiếp.

### 2.5 Calibration error cho HTE — ưu tiên 5

*Calibration Error for Heterogeneous Treatment Effects*, arXiv 2203.13364 — mức `C`.
Repo đang dùng EUCE tự hiện thực. Một định nghĩa có nguồn sẽ thay thế được, nhưng
cần nâng lên mức `A` trước.

## 3. Bài toán lân cận

### 3.1 Revenue uplift và value-aware targeting

Repo hiện quy đổi mọi thứ về conversion-equivalent vì Criteo không có tiền. Nhánh
nghiên cứu này giải quyết đúng khoảng trống đó.

| Nguồn | Nội dung | Mức |
|---|---|---|
| Gubela & Lessmann, *Response Transformation and Profit Decomposition for Revenue Uplift Modeling*, EJOR 2021, arXiv 1911.08729 | biến đổi response để mô hình hóa uplift doanh thu thay vì conversion | `C` |
| *Incremental Profit per Conversion*, arXiv 2306.13759 | biến đổi response nhắm lợi nhuận, kiểm soát chi phí khuyến mãi | `C` |
| *Rankability-enhanced Revenue Uplift Modeling*, KDD 2024, arXiv 2405.15301 | ZILN loss cho response đuôi dài, tối ưu thứ hạng uplift | `C` |
| VALOR, arXiv 2604.02472 (2026) | treatment-gated representation, Focal-ZILN, value-weighted ranking loss; A/B thật 4 tháng | `B` |

Điều kiện áp dụng: **cần một dataset có outcome tiền tệ**. Criteo không có. Đây là
lý do kỹ thuật để mở dataset thứ hai, không phải lý do "muốn thử phương pháp mới".

Chi tiết đáng dùng lại ngay cả khi không có tiền: value-weighted ranking loss của
VALOR phạt nặng "catastrophic inversion" và nhẹ với sai thứ tự giữa các cá nhân giá
trị tương đương. Ý tưởng "sai thứ tự không phải lỗi đồng nhất" áp dụng được cho bất
kỳ policy top-k nào.

### 3.2 Incremental CLV và hiệu ứng dài hạn

Đây là hướng repo đã tuyên bố trong `planning/incremental_value_product/`. Bài toán
thật nằm ở chỗ: **CLV dự báo không phải CLV tăng thêm**, và outcome dài hạn không
quan sát được trong cửa sổ thí nghiệm.

| Nguồn | Nội dung | Mức |
|---|---|---|
| Bibaut, Kallus, Ejdemyr & Zhao, *Long-Term Causal Inference with Imperfect Surrogates using Many Weak Experiments, Proxies, and Cross-Fold Moments*, arXiv 2311.04657 | dùng nhiều thí nghiệm nhỏ làm instrument; chịu được confounding giữa surrogate và outcome; cross-fold để khử bias của 2SLS | `B` |
| *Long-term Causal Inference via Modeling Sequential Latent Confounding*, arXiv 2502.18994 | confounding tiềm ẩn theo chuỗi thời gian | `C` |
| H-CLOuN, IJSRCSEIT 2025 | meta-learning phân cấp cho incremental CLV; báo cải thiện Qini 14,7% | `C` — tạp chí ngoài danh sách đã kiểm chứng của dự án, cần thận trọng |

Điều kiện dữ liệu rất khắt khe và repo **chưa** đáp ứng: cần nhiều thí nghiệm
randomized lịch sử có cả surrogate ngắn hạn lẫn outcome dài hạn. Criteo là một
snapshot, không có chuỗi thí nghiệm.

Cảnh báo phải giữ: **surrogate paradox**. Ngay cả khi treatment được randomize,
confounding giữa surrogate và outcome dài hạn có thể làm kết luận sai **dấu**. Ghép
Online Retail II với Criteo rồi gọi là incremental CLV sẽ vấp đúng cái bẫy này. Quy
tắc hiện có trong `planning/sprints.md` là đúng và nên giữ.

### 3.3 Policy learning có ràng buộc ngân sách

Repo hiện dùng top-k theo score, tức đã ngầm giả định chi phí đồng nhất trên mọi
khách hàng. Nhánh này bỏ giả định đó.

| Nguồn | Nội dung | Mức |
|---|---|---|
| *Optimal Policy Learning under Budget and Coverage Constraints*, arXiv 2605.12235 (2026) | cấu trúc knapsack; policy tối ưu là ngưỡng affine theo shadow price của ngân sách và coverage; thuật toán Greedy-Lagrangian và rank-and-cut | `B` |
| *PAC-Bayesian Treatment Allocation Under Budget Constraints*, arXiv 2212.09007 | bảo đảm PAC-Bayes cho phân bổ có ràng buộc | `C` |
| *Maximizing the Success Probability of Policy Allocations in Online Systems*, arXiv 2312.16267 | phân bổ policy trong hệ thống online | `C` |

Điểm đáng chú ý: khi chi phí đồng nhất, nghiệm knapsack **thoái hóa đúng về top-k**.
Nên top-k của repo không sai; nó là trường hợp riêng. Giá trị của nhánh này chỉ xuất
hiện khi có chi phí không đồng nhất theo cá nhân, hoặc có ràng buộc coverage tối thiểu.
Đây là mở rộng có ý nghĩa cho `src/policy.py` và cho tab Policy của web app.

### 3.4 Quyết định tuần tự và causal bandit

*Budget-Constrained Causal Bandits: Bridging Uplift Modeling and Sequential
Decision-Making*, arXiv 2604.26169 (2026) —
[arxiv.org/abs/2604.26169](https://arxiv.org/abs/2604.26169) — mức `B`.

**Bài này chạy thí nghiệm trên chính Criteo Uplift dataset**, nên so sánh được trực
tiếp với repo. Nội dung: gộp học hiệu ứng cá nhân, khám phá, và điều tiết chi tiêu
ngân sách vào một vòng tuần tự. Họ báo phương pháp offline cần khoảng 10.000 quan sát
lịch sử mới cho kết quả tin cậy, còn BCCB hoạt động từ người dùng đầu tiên, và
variance giữa các lần chạy thấp hơn 3–5 lần.

Liên quan tới repo: đây là câu trả lời cho hạng mục "chưa có production A/B test".
Nó chuyển bài toán từ "chọn model offline rồi deploy" sang "học và chi tiêu đồng
thời". Nếu mở, cần một môi trường mô phỏng có contract rõ ràng, và phải ghi rõ kết
quả là mô phỏng chứ không phải triển khai thật.

### 3.5 Multi-treatment và continuous treatment

| Nguồn | Nội dung | Mức |
|---|---|---|
| *Uplift modeling with continuous treatments: A predict-then-optimize approach*, EJOR 2026, arXiv 2412.09232 | ước lượng conditional average dose response rồi giải phân bổ liều bằng integer linear programming; hỗ trợ ràng buộc công bằng và chi phí theo cá nhân | `B` |
| Zhao & Harinen, *Uplift Modeling for Multiple Treatments with Cost Optimization*, arXiv 1908.05372 | nhiều treatment kèm tối ưu chi phí | `C` |
| *Enhancing Uplift Modeling in Multi-Treatment Marketing Campaigns*, arXiv 2408.13628 | score ranking và calibration cho nhiều treatment | `C` |
| *Heterogeneous Multi-treatment Uplift Modeling for Trade-off Optimization*, arXiv 2511.18997 | đánh đổi nhiều mục tiêu trong gợi ý video ngắn | `C` |

Criteo có treatment nhị phân nên nhánh này **không áp dụng được** cho dữ liệu hiện
tại. Ghi lại để không phải research lại khi có dataset multi-treatment.

### 3.6 Transfer và external validity

*Domain adaptive uplift modeling across heterogeneous cohorts* (ScienceDirect 2026) —
mức `C` — báo rằng tín hiệu xếp hạng uplift **chuyển giao được một phần** qua một số
dạng dịch chuyển phân phối, nhưng meta-learner cổ điển không hỗ trợ sẵn việc chuyển
giao giữa các dataset có không gian feature khác nhau.

Liên quan trực tiếp tới hạng mục còn thiếu của repo: chưa có bằng chứng portability.
Kế hoạch Hillstrom hiện có vẫn đúng hướng. Điều cần thêm: Criteo có 12 feature ẩn
danh, Hillstrom có feature khác hẳn, nên **không** thể transfer model; chỉ transfer
được *pipeline* và *protocol*. Phải phát biểu đúng như vậy để không hứa quá.

### 3.7 Vận hành: chọn policy theo độ ổn định, không chỉ theo metric

*Stability-Aware Uplift Policy Selection for Customer Retention*, Applied Sciences
16(10):4918, 2026 — [doi.org/10.3390/app16104918](https://doi.org/10.3390/app16104918) —
mức `C` (trang xuất bản trả về 403 khi truy cập trực tiếp).

Luận điểm được trích dẫn lại: thuật toán tối đa hóa metric xếp hạng nhân quả như Qini
**thường không tối ưu trong thực tế**; cần đánh giá đồng thời tiện ích kinh tế, độ ổn
định thuật toán và tính minh bạch của phân khúc.

Điều này trùng với những gì Sprint 3 đã quan sát được một cách độc lập: S-Under7
thắng Response ở fold seed 101 nhưng thua rõ ở seed 202, và chính sự không ổn định đó
là lý do promotion rule kiểm tra theo từng seed. Nên nâng nguồn này lên mức `A` và
đối chiếu tiêu chí ổn định của họ với tiêu chí đang dùng.

## 4. Đã xem xét và kết luận không áp dụng

| Hướng | Lý do không áp dụng cho repo hiện tại |
|---|---|
| Deep uplift (TARNet, DragonNet, CFRNet) | Benchmark 2024 báo baseline đơn giản cạnh tranh được trên chính Criteo conversion; 12 feature tabular không có cấu trúc mà representation learning khai thác được |
| Heteroscedasticity-aware RCT sampling, EJOR 2025 | Thuộc khâu thiết kế thí nghiệm mới; không dùng post-hoc trên benchmark đã cố định |
| Uplift với delayed feedback, AAAI 2026 | Criteo v2.1 không có event time hay observation horizon |
| Continuous-treatment uplift | Treatment của Criteo là nhị phân |
| SMOTE hoặc class weight không hiệu chỉnh | Phá probability scale và treatment contrast; Nyberg et al. đã có công thức đúng và repo đã hiện thực |
| Cannibalization framework (arXiv 2607.05242) | Cần nhiều seller/incentive tương tác; Criteo là một treatment đơn |

## 5. Thứ tự đề xuất nếu mở vòng tiếp theo

> **Cập nhật 05/08/2026:** mục 1 và mục 2 (phần proxy diagnostic) **đã thực hiện**.
> Kết quả ở mục 5bis. Ba mục còn lại giữ nguyên thứ tự.

1. ~~**`visit` như power diagnostic.**~~ **Đã làm** — xem mục 5bis.1.
2. **Nâng arXiv 2406.09567 và 2206.12532 lên mức `A`**, rồi hiện thực causal
   post-processing và proxy diagnostic.
   - Proxy diagnostic (2206.12532): **đã làm** — xem mục 5bis.2.
   - Causal post-processing (2406.09567): **chưa** — vẫn ở mức `B`, chỉ đọc được
     abstract và mô tả phương pháp, chưa đọc được công thức.
3. **Mở rộng `src/policy.py` sang ràng buộc ngân sách không đồng nhất**, theo cấu
   trúc knapsack của arXiv 2605.12235. Cần nâng lên mức `A` trước.
4. **Chỉ mở revenue uplift hoặc incremental CLV khi đã có dataset có outcome tiền
   tệ và thiết kế randomized.** Không ghép dataset để tạo ra estimand không quan sát
   được.
5. **Causal bandit** chỉ sau khi có contract mô phỏng rõ ràng và tiêu chí đánh giá
   đăng ký trước.

## 5bis. Kết quả của hai hạng mục đã thực hiện

### 5bis.1 Power diagnostic bằng outcome `visit`

**Câu hỏi:** không challenger nào tách được khỏi Response. Do dữ liệu hay do pipeline
thiếu power?

**Cách làm:** chạy lại đúng pipeline screening 20%, cùng fold seed, cùng split, chỉ đổi
outcome sang `visit`. Số positive ở control tăng từ 325 lên 6.414.

**Kết quả:** trên `conversion`, paired CI của **mọi** challenger nằm hoàn toàn dưới 0.
Trên `visit`, ba challenger (DR-Binary, X-Renormalized, R-Binary) có CI **chứa 0**. Họ
DR/R-Learner — vốn bị dominate rõ trên `conversion` — thu hẹp khoảng cách đáng kể.

**Kết luận:** giao thức **có** phản ứng với độ mạnh tín hiệu. Nhưng Response vẫn dẫn đầu
trên cả hai outcome theo metric chính, nên kết luận "Response khó bị đánh bại" không phải
chỉ là hệ quả của outcome hiếm.

Chi tiết và bảng số: `report/SPRINT_3_FINAL_REPORT.md` mục 7bis.1.

### 5bis.2 Proxy-ordering diagnostic

Bản HTML v7 của arXiv 2206.12532 cho phép nâng nguồn lên mức `A` cho **một phần**: điều
kiện đủ `theta_max < (1 − beta_max)/2`, với `theta_max` là xác suất baseline lớn nhất và
`beta_max` là chặn trên của CATE lớn nhất.

**Kết quả trên development OOF:** `theta_max = 0,885764`, ngưỡng `0,200783`, điều kiện
**không thỏa**. Độ nhạy cho thấy nó hỏng ở **mọi** lựa chọn `beta_max`, kể cả `beta_max = 0`
(ngưỡng 0,5), vì chỉ riêng `theta_max` đã vượt. Chỉ 1.313 dòng (0,023%) có baseline ≥ 0,5.

**Cách đọc:** đây là điều kiện **đủ**, không phải **cần**. Điều kiện hỏng không kết luận
Response xếp hạng sai; nó nói khung này không bao phủ trường hợp đang xét. Lời giải thích
cho việc Response thắng vì thế phải dựa vào causal bias–variance tradeoff (mục 1.1), không
dựa vào định lý ordering này.

**Phần chưa hiện thực:** paper còn một điều kiện cho *subset* với biến `tau_k` không được
định nghĩa đủ rõ trong bản trích xuất. Không hiện thực từ suy đoán. Muốn dùng phải đọc đầy
đủ mục 4.6 của bản gốc.

Hiện thực: `src/proxy_diagnostic.py`, `scripts/run_proxy_diagnostic.py`. Ba mức nguồn khác
nhau trong cùng module được đánh dấu rõ trong docstring.

## 6. Quy tắc giữ nguyên

- Không hiện thực phương pháp ở mức `C`.
- Không trích số của paper khác như dự đoán cho repo khi thiết lập thí nghiệm khác
  nhau. Rank-Learner là ví dụ đã gặp: paper báo lợi thế ở chế độ mẫu nhỏ và train có
  confounding, repo chạy chế độ 5,59 triệu dòng randomized, và kết quả khác nhau đúng
  như thiết lập gợi ý.
- `visit` và `exposure` vẫn bị cấm làm feature. Việc dùng `visit` làm outcome là một
  estimand khác và phải được gọi tên như vậy ở mọi nơi.
- Mọi vòng mới vẫn phải đăng ký metric, gate và promotion rule trước khi chạy.
