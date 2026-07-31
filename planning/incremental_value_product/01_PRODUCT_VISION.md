# 01 — Tầm nhìn Sản phẩm (Product Vision)

## Định vị

**Incremental Value Studio** là công cụ ra quyết định chiến dịch cho growth/CRM manager:

> “Với treatment cost, margin, budget và value horizon hiện tại, nên target ai để tối đa hóa
> expected incremental net value?”

Sản phẩm không phải một model explorer dành riêng cho data scientist. Model evidence vẫn có,
nhưng nằm sau quyết định kinh doanh.

## Người dùng

### Người dùng chính (Primary User)

Growth/CRM manager cần:

- chọn tỷ lệ khách được target;
- biết expected incremental value và uncertainty;
- tránh khách có expected effect âm;
- so sánh policy mới với cách nhắm theo propensity/CLV;
- export danh sách cho campaign.

### Người dùng phụ (Secondary User)

Data scientist/analyst cần:

- kiểm tra randomization/balance;
- xem temporal CLV calibration;
- so sánh CATE/value uplift;
- audit policy value và seed robustness;
- truy vết model/config/artifact.

## Workflow một phút

1. Chọn demo dataset hoặc upload file đúng schema.
2. Chọn horizon 14/30/90/180 ngày.
3. Nhập treatment cost, margin, budget và risk tolerance.
4. Xem policy khuyến nghị.
5. So sánh với random, propensity và predicted CLV.
6. Export `targeting_plan.csv`.

## Bốn màn hình

### 1. Tổng quan Quyết định (Decision Overview)

- recommended target rate;
- expected incremental gross/net value;
- bootstrap/credible interval;
- gain vs random, propensity, predicted CLV;
- điểm hòa vốn và budget frontier.

### 2. Chiến lược Khách hàng (Customer Strategy)

| Field | Ý nghĩa |
|---|---|
| `customer_id` | ID đầu ra |
| `predicted_clv` | Giá trị dự báo, không causal |
| `incremental_value` | Hiệu ứng giá trị dự kiến do treatment |
| `uncertainty` | CI/SD tùy model |
| `action` | Target / Hold / Exclude |
| `reason_code` | Vì sao có hành động đó |

Có filter và CSV export.

### 3. Bằng chứng Mô hình (Model Evidence)

- treatment/control balance;
- CLV calibration theo temporal holdout;
- value uplift curve;
- policy value + CI;
- calibration theo predicted-effect bin;
- stability qua seed/cutoff.

### 4. Phòng thử Kịch bản (Scenario Lab)

- cost/margin sensitivity;
- budget từ top 5% đến 100%;
- horizon sensitivity;
- expected value–uncertainty frontier.

## Chế độ sản phẩm (Product Mode)

| Mode | Dùng gì | Claim hợp lệ |
|---|---|---|
| Real causal benchmark | Criteo | Conversion/visit uplift |
| Real monetary RCT | Hillstrom | Incremental spend trong outcome window |
| Real CLV benchmark | Online Retail II | Retailer-Observed CLV forecast |
| Integrated demo | Semi-synthetic longitudinal RCT | Ground-truth policy regret trong simulation |

Mỗi mode phải có banner data provenance. Không trộn số giữa các mode.

## Tiêu chí chấp nhận (Acceptance Criteria)

- Người mới hiểu value proposition trong dưới 60 giây.
- Thay cost/margin/budget làm policy đổi tức thời.
- Mọi số trên UI có artifact nguồn.
- App phân biệt predicted CLV và incremental value.
- App phân biệt real và semi-synthetic evidence.
- CSV export có action/reason code.
- Chạy được bằng một lệnh hoặc Docker.
- Có sample mode không cần người xem chuẩn bị data.

## Phạm vi không làm trong v1.0 (Non-goals)

- real-time bidding;
- production campaign dispatch;
- reinforcement learning/dynamic treatment;
- multi-touch attribution/MMM;
- Kubernetes/feature store;
- báo revenue lift ngoài randomized experiment và observed horizon.
