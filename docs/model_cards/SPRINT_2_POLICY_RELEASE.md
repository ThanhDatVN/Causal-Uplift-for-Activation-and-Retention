# Model Card — Sprint 2 Response top‑k Policy

## Intended use

Offline decision support cho bài toán chọn top `k%` khách hàng trong một campaign có
population tương tự Criteo RCT. Không dùng để ra quyết định nhạy cảm, không dùng thay
production experiment và không dùng để gán causal label cho cá nhân.

## Champion

**Response baseline** (LightGBM classifier dự báo conversion từ `f0`–`f11`) được chọn
trên validation theo Qini. Nó cung cấp ranking policy, không phải CATE probability.

Confirmation:

- Qini `0,182789`;
- AUUC `0,005912`;
- X‑Renormalized − Response Qini `0,008768`,
  paired 95% CI `[-0,018626; 0,038772]`.

Challenger chưa chứng minh hơn champion; release ưu tiên parsimony.

## Policy result

Tại top 10%, `value_per_conversion=1`, `contact_cost=0,0005`:

- DR net/customer `0,000799`;
- percentile-bootstrap 95% CI `[0,000608; 0,000977]`;
- ΔDR net so random 95% CI `[0,000582; 0,000928]`;
- 500 paired bootstrap resamples.

Đây là conversion-equivalent scenario, không phải actual profit.

## Known limitations

- Response score không calibrated về individual treatment effect.
- Confirmation là offline RCT replay, chưa có production policy deployment.
- Population shift, treatment version change và interference chưa được kiểm tra.
- Rare control conversions làm calibration bins nhiễu.
- Causal Forest chưa có Kaggle release artifact.
- “Random top-k” hiện là một ranking ngẫu nhiên cố định bằng seed 42; paired bootstrap
  phản ánh bất định lấy mẫu có điều kiện trên ranking đó, chưa tích hợp biến thiên qua nhiều
  random-policy seed.
- Confirmation đã được dùng để lập báo cáo Sprint 2; các vòng phát triển model sau không
  được gọi nó là holdout chưa quan sát.

## Monitoring nếu triển khai

- feature/schema drift và missing rate;
- treatment propensity và overlap;
- conversion rate theo treatment/control;
- realized incremental outcome bằng randomized holdout;
- target fraction, contact cost, complaint/opt-out guardrails;
- không chỉ theo dõi response AUC.
