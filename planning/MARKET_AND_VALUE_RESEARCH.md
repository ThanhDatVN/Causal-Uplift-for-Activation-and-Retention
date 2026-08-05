# Research thị trường và kế hoạch nâng giá trị dự án

Ngày rà soát: 05/08/2026.

Tài liệu này bổ sung mặt **thị trường và ứng dụng công nghiệp** cho
`RESEARCH_LANDSCAPE_2026.md` — vốn chỉ phủ mặt phương pháp. Kết thúc bằng kế hoạch bốn
phase để nâng giá trị dự án.

Trạng thái: **chưa mở**. Mọi phase phải đăng ký protocol trước khi chạy.

---

## 0. Mức xác minh nguồn

Giữ nguyên quy ước của `RESEARCH_LANDSCAPE_2026.md`:

| Mức | Nghĩa |
|---|---|
| `A` | Đọc được công thức hoặc số liệu gốc. Được phép hiện thực |
| `B` | Đọc được tóm tắt hoặc mô tả, chưa đọc công thức. **Chưa** được hiện thực |
| `C` | Chỉ có metadata |

Thêm một mức cho tài liệu thương mại, vì phần thị trường không có nguồn peer-review:

| Mức | Nghĩa |
|---|---|
| `T` | Nguồn thương mại hoặc trade publication. Dùng để mô tả xu hướng, **không** dùng làm căn cứ kỹ thuật |

Số liệu tự đo trong repo này được đánh dấu `[đo tại chỗ]`.

---

## 1. Thị trường đã đổi gì, 2025–2026

### 1.1 Attribution sụp, lift test thành tầng xác thực

iOS ATT opt-in ổn định ở 15–25% toàn cầu, phần lớn người dùng iOS không còn theo dõi
được. Hệ quả là đo lường marketing tách thành ba tầng, mỗi tầng trả lời một câu hỏi
khác nhau trên một khung thời gian khác nhau:

| Tầng | Câu hỏi | Vai trò |
|---|---|---|
| MMM | Phân bổ ngân sách giữa các kênh, không cần dữ liệu định danh | chiến lược |
| Attribution tôn trọng riêng tư | Tối ưu ngắn hạn | vận hành |
| **Lift test / incrementality** | Con số kia có thật không | **xác thực** |

Ở Mỹ năm 2026, 27,6% marketer đánh giá MMM là phương pháp đáng tin cậy nhất, so với
19,4% cho multi-touch attribution. Mức xác minh `T`.

**Liên quan trực tiếp tới repo này.** Uplift modeling nằm ở tầng thứ ba nhưng làm việc
khác: incrementality test trả lời *chiến dịch có hiệu quả không*; uplift model trả lời
*nên nhắm vào ai*. Dự án này đang ở đúng chỗ có nhu cầu tăng, nhưng phải nói rõ nó là
tầng **targeting** đặt sau tầng **measurement**, không thay thế tầng đó.

### 1.2 Geo-lift chuyển từ công cụ chuyên biệt thành kỷ luật vận hành

Synthetic control đẩy geo-lift từ "công cụ phụ trợ cho MMM" thành một quy trình thường
trực: dựng counterfactual tổng hợp từ rổ thị trường donor có trọng số, giảm mạnh tỷ lệ
dương tính giả. Mức xác minh `T`.

Đây là bài toán lân cận mà `RESEARCH_LANDSCAPE_2026.md` chưa nêu: cùng họ causal, nhưng
đơn vị phân tích là **thị trường theo thời gian** chứ không phải **cá nhân**.

### 1.3 Kỹ năng causal tăng nhanh nhất trong tuyển dụng data

Trong tin tuyển dụng data science: causal inference `+17` điểm phần trăm, A/B testing
`+14` điểm phần trăm. SQL xuất hiện ở 79% tin, kỹ năng pipeline ở 31%. Mức xác minh `T`.

Diễn giải: nhà tuyển dụng đang chuyển từ "dự đoán" sang "đo tác động". Nhưng con số SQL
79% và pipeline 31% cũng nói rằng **năng lực kỹ thuật vận hành vẫn là điều kiện cần** —
một dự án causal thuần phương pháp, không có phần triển khai, mất một nửa giá trị.

Repo này đã có web app, gate tài nguyên, registry và CI — phần đó đang đúng hướng.

### 1.4 Model uplift lão hoá nhanh — than phiền số một từ vận hành

40% công ty triển khai model AI ghi nhận suy giảm hiệu năng rõ rệt trong năm đầu do
drift. Riêng với uplift, ghi nhận từ case study ngân hàng bán lẻ: model thế hệ trước
"lão hoá nhanh và trở nên mong manh khi áp dụng cho các chiến dịch ngoài dữ liệu huấn
luyện". Mức xác minh `T`.

**Đây là khoảng trống lớn nhất của repo hiện tại.** Toàn bộ bằng chứng là cắt ngang một
thời điểm. Không có phân tích ổn định theo thời gian, không có tiêu chí phát hiện khi
nào phải huấn luyện lại.

---

## 2. Khoảng trống mà dự án này lấp được

### 2.1 Benchmark công khai không có baseline Response — khoảng trống lớn nhất

`uplift-bench` (yablochnikovds) so 7 phương pháp uplift trên 5 dataset công khai
(Hillstrom, Criteo, Lenta, RetailHero, MegaFon) cộng một DGP tổng hợp, có bootstrap CI
và phân tích robustness. Kết luận của họ:

- **Không có phương pháp thắng phổ quát.** Hillstrom → Causal Forest; Criteo (mẫu
  700k) → S-learner; synthetic có nhiễu → Class Transformation.
- **CI bootstrap chồng lấn nặng** trên Criteo và Hillstrom; chênh lệch dưới vị trí dẫn
  đầu không có ý nghĩa thống kê.

Điểm thứ hai **độc lập xác nhận** phát hiện của repo này: trên Criteo, khác biệt giữa
các CATE learner không phân biệt được. Repo đã đo cùng hiện tượng bằng DR risk chênh
nhau khoảng `7e-6` tương đối, khiến Q-aggregation hội tụ về trung bình cộng thay vì
chọn.

Nhưng benchmark đó **so các phương pháp uplift với nhau, không có baseline dự đoán
outcome**. Nghĩa là nó không thể phát hiện được điều mà repo này phát hiện: Response
đánh bại toàn bộ CATE learner.

Mức xác minh `B` — đọc mô tả repo, **chưa đọc code**. Trước khi tuyên bố "benchmark
công khai bỏ sót baseline này", phải đọc mã nguồn của họ để xác nhận. Đây là claim
trung tâm của Phase 1 nên không được để ở mức `B`.

### 2.2 Kết luận hiện tại mới dựa trên một dataset

Repo kết luận Response thắng, có bốn nguồn giải thích vì sao. Nhưng bằng chứng thực
nghiệm chỉ đến từ **một** dataset với outcome cực hiếm.

Câu hỏi chưa trả lời: Response thắng **vì outcome hiếm**, hay thắng **nói chung**?

Đây không phải câu hỏi học thuật. Nó quyết định lời khuyên cho người dùng: "luôn thử
baseline outcome trước" khác hẳn "thử baseline outcome khi tỷ lệ sự kiện dưới X%".

### 2.3 Không có phân tích ổn định theo thời gian

Xem mục 1.4. Thị trường coi đây là vấn đề số một; repo chưa chạm tới.

---

## 3. Số liệu khả thi — đã đo tại chỗ

`scikit-uplift 0.5.1` **đã cài sẵn và đã nằm trong `requirements.txt`**. Nó chỉ yêu cầu
`scikit-learn>=0.21.0`, không đụng ràng buộc `<1.7` của `econml==0.16.0`. Mở rộng đa
dataset **không tốn thêm dependency nào**.

Tải thử và đo trực tiếp `[đo tại chỗ]`:

| Dataset | Dòng | Feature | Outcome | Tỷ lệ control | Số event ở control |
|---|---:|---:|---|---:|---:|
| Criteo v2.1 | 13.979.592 | 12 | `conversion` | 0,29% | **4.063** |
| Hillstrom | 64.000 | 8 | `conversion` | 0,57% | **122** |
| Hillstrom | 64.000 | 8 | `visit` | 10,62% | **2.262** |
| Lenta | 687.029 | 193 | `response` | 10,26% | **17.555** |

Ba điều rút ra:

1. **Hillstrom `conversion` còn hiếm hơn Criteo** — chỉ 122 event ở nhánh control. Nó
   không giải quyết được vấn đề tín hiệu yếu; nó là một ca cực đoan hơn.
2. **Lenta là dataset duy nhất thoát khỏi chế độ outcome hiếm**: 17.555 event ở control,
   gấp 4,3 lần Criteo, dù ít hơn 20 lần số dòng. Cộng 193 feature so với 12 của Criteo,
   đây là nơi CATE learner có cơ hội công bằng nhất.
3. **Lenta không cân bằng nhánh**: 515.892 test so với 171.137 control, tức khoảng
   75/25. Giả định propensity cố định 0,5 lấy từ Criteo **không chuyển sang được**; phải
   dùng tỷ lệ theo nhánh. Đây là điểm dễ sai nhất khi mở rộng.

Chi phí tải: Hillstrom 443 KB trong vài giây. Lenta vài chục MB. Không cần Kaggle.

---

## 4. Kế hoạch bốn phase

Xếp theo tỷ lệ giá trị trên chi phí. Không bắt buộc làm hết.

### Phase 1 — Ngoại suy đa dataset: Response thắng khi nào

**Giá trị cao nhất, chi phí thấp nhất.**

Câu hỏi đăng ký trước: *ngưỡng tỷ lệ sự kiện nào khiến baseline dự đoán outcome thôi
thống trị các CATE learner?*

**Cách làm.** Chạy đúng protocol Sprint 3 — cùng `policy_area_dr`, cùng paired
percentile bootstrap, cùng promotion rule — trên bốn chế độ tín hiệu:

| Chế độ | Dataset / outcome | Event ở control |
|---|---|---:|
| Cực hiếm | Hillstrom `conversion` | 122 |
| Rất hiếm | Criteo `conversion` | 4.063 |
| Trung bình | Hillstrom `visit` | 2.262 |
| Dồi dào | Lenta `response` | 17.555 |

Criteo `conversion` đã có kết quả; ba chế độ còn lại là việc mới.

**Kết quả kỳ vọng và giá trị của từng khả năng.**

- Nếu Response thắng ở mọi chế độ → kết luận mạnh hơn hiện tại nhiều, và mâu thuẫn với
  `uplift-bench` (nơi Causal Forest thắng Hillstrom). Mâu thuẫn đó tự nó là phát hiện,
  vì hai bên dùng metric khác nhau — họ dùng Qini, repo này dùng `policy_area_dr`.
- Nếu Response thua ở Lenta → xác định được **ngưỡng**, và biến kết luận từ "trên
  Criteo Response thắng" thành "prognostic dominance là hiện tượng của chế độ outcome
  hiếm, ranh giới đo được nằm ở đâu". Đây là phát biểu tổng quát, trích dẫn được.

Cả hai khả năng đều có giá trị. Đó là dấu hiệu câu hỏi được đặt đúng.

**Việc phải làm trước.** Đọc mã nguồn `uplift-bench` để nâng claim 2.1 từ `B` lên `A`.
Nếu hoá ra họ *có* baseline outcome thì luận điểm khác biệt sụp, và phải viết lại phần
định vị. Kiểm tra điều này **trước** khi chạy, không phải sau.

**Rủi ro kỹ thuật.**

- Hillstrom có **ba nhánh** (`Mens E-Mail`, `Womens E-Mail`, `No E-Mail`). Phải quyết
  định trước: gộp hai nhánh email thành một treatment, hay bỏ một nhánh. Ghi vào
  protocol, không quyết sau khi nhìn kết quả.
- Lenta propensity 75/25, không phải 50/50. Phải dùng tỷ lệ theo nhánh.
- Lenta 193 feature cần data contract riêng: kiểu dữ liệu, missing, biến hậu can thiệp.
  **Kiểm tra leakage cho từng feature** — Criteo chỉ có 12 biến ẩn danh nên bài học
  `visit`/`exposure` không tự chuyển sang được.

**Điều kiện hoàn tất.**

- [ ] Đã đọc code `uplift-bench`, claim 2.1 ở mức `A` hoặc đã viết lại
- [ ] Data card cho từng dataset mới, có kiểm leakage từng feature
- [ ] Protocol đăng ký trước, ghi rõ cách xử lý ba nhánh Hillstrom và propensity Lenta
- [ ] Bốn chế độ chạy xong, mỗi cặp so sánh có paired CI
- [ ] Mọi run vào `output/improvement/registry.csv`
- [ ] Kết luận phát biểu dưới dạng điều kiện, không phải tuyệt đối

### Phase 2 — Ổn định theo thời gian

Lấp khoảng trống ở mục 1.4 — vấn đề thị trường quan tâm nhất.

**Trở ngại.** Criteo v2.1 không có mốc thời gian dùng được. Phải kiểm xem Lenta hoặc X5
RetailHero có trường thời gian không; X5 có dữ liệu giao dịch thô nên nhiều khả năng có.

Nếu không dataset nào có thời gian dùng được thì **đóng phase này và ghi rõ lý do**,
thay vì thay bằng một phép chia ngẫu nhiên rồi gọi là "temporal". Chia ngẫu nhiên không
trả lời câu hỏi về drift.

**Nếu có dữ liệu thời gian.** Huấn luyện trên cửa sổ sớm, đánh giá trên cửa sổ muộn, đo
mức suy giảm `policy_area_dr` theo khoảng cách thời gian. Sản phẩm là một tiêu chí:
*sau bao lâu thì phải huấn luyện lại*.

### Phase 3 — Tầng quyết định và kinh tế

Đã mô tả ở `NEXT_ROUND_PLAN.md` mục B.2. Research thị trường củng cố ưu tiên này: điều
người mua cần là câu trả lời ngân sách và điểm hoà vốn, không phải con số Qini.

Bổ sung một yêu cầu từ mục 1.1: web app phải nói rõ nó là tầng **targeting**, đặt sau
tầng **measurement**, không thay thế incrementality test.

### Phase 4 — Significance-first splitting cho chế độ tín hiệu yếu

Nguồn: *Significance-First Splitting: Aligning Treatment Heterogeneity Detection with
Honest Estimation*, arXiv 2607.03999.

**Vì sao liên quan trực tiếp.** Bài báo nêu đúng vấn đề tôi đã cảnh báo cho Causal
Forest ở `NEXT_ROUND_PLAN.md` mục A.4: tiêu chí chia nhánh chuẩn tối ưu độ chính xác dự
đoán, không đảm bảo phát hiện được tính không đồng nhất của hiệu ứng. Tác giả nói phương
pháp có lợi riêng cho outcome hiếm và tỷ lệ tín hiệu trên nhiễu thấp — đúng chế độ của
Criteo, nơi `min_samples_leaf=500` cho trung bình 1,4 conversion mỗi lá.

**Mức xác minh `B`.** Đọc được mô tả, **chưa đọc công thức tiêu chí chia nhánh**. Theo
quy tắc repo, **chưa được hiện thực**. Phải đọc bản PDF đầy đủ và trích được công thức
trước, nâng lên `A`.

Xếp cuối vì phụ thuộc Phase 1: nếu Phase 1 cho thấy vấn đề là chế độ outcome hiếm, thì
đây là hướng đúng; nếu không, nó mất căn cứ.

---

## 5. Không làm

Bổ sung cho bảng ở `NEXT_ROUND_PLAN.md` mục 4.

| Hướng | Lý do loại |
|---|---|
| MMM hoặc geo-lift | Bài toán khác: đơn vị là thị trường theo thời gian, không phải cá nhân. Cần dữ liệu chuỗi thời gian theo vùng mà repo không có. Nêu ở mục 1.2 như bối cảnh, không mở |
| Multi-touch attribution | Chính thị trường đang rời bỏ nó vì mất tín hiệu định danh |
| Thêm dataset chỉ để cho nhiều | Mỗi dataset là một data contract, một lần kiểm leakage, một data card. Chỉ thêm khi nó bổ sung một **chế độ tín hiệu** chưa có. MegaFon là dữ liệu tổng hợp; X5 chỉ thêm nếu Phase 2 cần trường thời gian |

---

## 6. Thứ tự đề nghị và chi phí

| Phase | Chi phí | Rủi ro | Giá trị |
|---|---|---|---|
| 1 — đa dataset | Thấp. Không thêm dependency, dữ liệu tải trong vài phút | Thấp. Cả hai khả năng kết quả đều dùng được | **Cao nhất** |
| 2 — thời gian | Trung bình | Cao. Có thể không có dataset nào dùng được, phải đóng | Cao nếu chạy được |
| 3 — quyết định | Trung bình | Thấp | Cao về mặt sản phẩm |
| 4 — splitting | Cao | Cao. Chưa đọc công thức | Chưa xác định được |

Đề nghị: chạy **Phase 1**, mở **Phase 3** song song vì hai phase không tranh tài nguyên
(Phase 3 không cần huấn luyện lại). Quyết định Phase 2 và 4 sau khi có kết quả Phase 1.

Ràng buộc giữ nguyên: `no_parallel_full_data_runs` cấm chạy song song hai vòng cùng đụng
full development pool.

---

## Nguồn

Nghiên cứu và benchmark:

- [uplift-bench — benchmark 7 phương pháp trên 5 dataset công khai](https://github.com/yablochnikovds/uplift-bench) — `B`
- [Significance-First Splitting, arXiv 2607.03999](https://arxiv.org/pdf/2607.03999) — `B`
- [Diemert et al., A Large Scale Benchmark for Uplift Modeling](https://bitlater.github.io/files/large-scale-benchmark_comAH.pdf) — `A`, đã dùng trong `RESEARCH_LANDSCAPE_2026.md`
- [Gutierrez & Gérardy, Causal Inference and Uplift Modeling: a review](https://proceedings.mlr.press/v67/gutierrez17a/gutierrez17a.pdf) — `A`
- [scikit-uplift datasets](https://www.uplift-modeling.com/en/latest/api/datasets/index.html) — `A`, số liệu đã đo lại tại chỗ
- [uber/causalml](https://github.com/uber/causalml) — `A`

Thị trường, mức xác minh `T`:

- [MMM vs MTA vs Lift Tests 2026: The Measurement Matrix](https://www.digitalapplied.com/blog/media-mix-vs-attribution-vs-mta-2026-decision-matrix)
- [Marketing Mix Modeling 2026: MMM vs Attribution Guide](https://www.digitalapplied.com/blog/marketing-mix-modeling-2026-mmm-vs-attribution-playbook)
- [Geo-Based Incrementality Testing: Marketer's Guide 2026](https://lifesight.io/blog/geo-based-incrementality-testing/)
- [Privacy-Centric Attribution Models: 2026 Guide](https://www.topanalyticstools.com/blog/privacy-centric-attribution-models-2026-guide/)
- [2026 vs 2025 Data Science job market](https://askdatadawn.substack.com/p/how-has-the-data-science-job-market)
- [AI Model Drift & Performance Risk](https://gaicc.org/blog/ai-model-drift-performance-risk/)
- [Case Study: Retail Bank Uplift Modeling](https://tdwi.org/articles/2007/10/18/case-study-top-retail-bank-more-than-doubles-campaign-profitability-using-latest-umt.aspx)
