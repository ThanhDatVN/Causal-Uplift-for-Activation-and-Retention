# Model card — policy Response top-k

- **Champion hiện hành:** Response top-k, không đổi từ Sprint 2 qua cả sáu vòng cải tiến
- **Phát hành lần đầu:** Sprint 2 — 31/07/2026
- **Cập nhật gần nhất:** 05/08/2026, sau Sprint 3
- **Luật quyết định:** [`../DECISION_CONTRACT.md`](../DECISION_CONTRACT.md)
- **Bằng chứng số:** [`../../report/02_SPRINT_2_POLICY.md`](../../report/02_SPRINT_2_POLICY.md),
  [`../../report/03_SPRINT_3_IMPROVEMENT.md`](../../report/03_SPRINT_3_IMPROVEMENT.md)

Champion không đổi sau Sprint 3; bằng chứng ủng hộ nó đã được mở rộng. Đọc mục 4 trước khi
trích số của Sprint 2.

## 1. Phạm vi sử dụng

Hỗ trợ quyết định offline cho bài toán chọn top `k%` khách hàng trong một campaign có quần
thể tương tự Criteo RCT. Không dùng để ra quyết định nhạy cảm, không dùng thay cho một thí
nghiệm chạy thật, và không dùng để gán nhãn nhân quả cho cá nhân.

## 2. Model được phát hành

**Response baseline** (LightGBM classifier dự báo conversion từ `f0`–`f11`) được chọn
trên validation theo Qini. Nó cung cấp ranking policy, không phải CATE probability.

Confirmation:

- Qini `0,182789`;
- AUUC `0,005912`;
- X-Renormalized - Response Qini `0,008768`,
  paired 95% CI `[-0,018626; 0,038772]`.

Challenger chưa chứng minh hơn champion; bản phát hành ưu tiên model ít thành phần hơn.

## 3. Kết quả policy

Tại top 10%, `value_per_conversion=1`, `contact_cost=0,0005`:

- DR net/customer `0,000799`;
- percentile-bootstrap 95% CI `[0,000608; 0,000977]`;
- ΔDR net so random 95% CI `[0,000582; 0,000928]`;
- 500 paired bootstrap resamples.

Đây là kịch bản quy đổi theo conversion, không phải lợi nhuận thật.

## 4. Đánh giá lại ở Sprint 3 — 05/08/2026

Champion được đưa qua một vòng thử thách có protocol đăng ký trước với metric chính
mới `policy_area_dr`, 3-fold cross-fitting trên 5.591.836 dòng ở hai fold seed, và 8
challenger gồm R-Learner, DR ablation, S/T-Learner ablation, Rank-Learner (ICML 2026)
và ba ensemble.

**Kết quả: không challenger nào đạt promotion rule; champion giữ nguyên Response.**

Trên retrospective confirmation (1.397.959 dòng, 500 paired bootstrap):

- Response `policy_area_dr = 0,000912`, AUTOC `0,003823`, Qini `0,192989`;
- challenger gần nhất là Ensemble-QAgg, chênh lệch `-0,0000011` với CI
  `[-0,0000563; +0,0000525]`, tức chưa tách khỏi 0;
- không CI nào của bất kỳ challenger nào có lower bound lớn hơn 0;
- trên AUTOC, mọi challenger có CI nằm hoàn toàn dưới 0.

Tại top 10%, `value_per_conversion=1`, `contact_cost=0,0005` trên confirmation
Sprint 3: DR net/customer `0,000856`, 95% CI `[0,000675; 0,001044]`, ΔDR so random
95% CI `[0,000638; 0,000994]`.

**Cảnh báo diễn giải:** theo Qini, **bốn** model xếp **trên** Response `0,192989` —
Ensemble-QAgg `0,209845`, S-Under7 `0,205904`, X-Renormalized `0,201812` và
Ensemble-RankAverage `0,195022`. Response chỉ đứng hạng `6/9` theo Qini. Theo metric chính
đã đăng ký trước và theo AUTOC, Response đứng đầu. Không trích một trong hai nhóm số này
rời khỏi ngữ cảnh còn lại.

*(Ensemble-BestSingle cũng ở `0,201812` nhưng không đếm riêng: nó chọn đúng X-Renormalized
nên trùng khít mọi cột.)*

Scorer phục vụ web app được fit trên development pool (Sprint 2 `fit + validation`),
lưu tại `output/product/webapp/champion_scorer.joblib`, metadata tại
`output/product/webapp/champion_scorer.json`.

## 5. Giới hạn đã biết

- Response score không calibrated về individual treatment effect.
- Confirmation là offline RCT replay, chưa có production policy deployment.
- Population shift, treatment version change và interference chưa được kiểm tra.
- Rare control conversions làm calibration bins nhiễu.
- Causal Forest đã có artifact Kaggle nhưng dùng final test Sprint 1 và IPW signal;
  không so trực tiếp với retrospective confirmation Sprint 3 dùng DR signal.
- Expected-random trong artifact Sprint 3 là policy kỳ vọng giải tích `π(x)=b`;
  dải sensitivity bổ sung dùng 20 random-ranking seed và không được trình bày như
  bootstrap confidence interval.
- Confirmation đã được dùng để lập báo cáo Sprint 2; các vòng phát triển model sau không
  được gọi nó là holdout chưa quan sát.

## 6. Giám sát nếu triển khai

- feature/schema drift và missing rate;
- treatment propensity và overlap;
- conversion rate theo treatment/control;
- realized incremental outcome bằng randomized holdout;
- target fraction, contact cost, complaint/opt-out guardrails;
- không chỉ theo dõi response AUC.
