# Data Card — Criteo Uplift Prediction Dataset v2.1

## Identity

- Local file: `data/criteo-research-uplift-v2.1.csv.gz`
- SHA‑256: `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`
- Rows/columns: 13.979.592 × 16
- Upstream description:
  [Criteo AI Lab](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)
- Mirror/data description:
  [Criteo trên Hugging Face](https://huggingface.co/datasets/criteo/criteo-uplift)

Người tái sử dụng phải tự kiểm tra terms của upstream dataset. Dự án không tự gán một
license mới cho dữ liệu.

Nguồn Criteo cho biết bản public được ghép từ nhiều incrementality test và được
**subsample không đồng đều** vì lý do riêng tư. Do đó ATE/Qini trong repository là kết quả
trên benchmark public v2.1, không phải ước lượng có thể suy ngược thành incrementality của
campaign gốc. Các feature cũng đã được ẩn danh và chiếu ngẫu nhiên; dự án có thể đánh giá
ranking/policy nhưng không thể gán ý nghĩa kinh doanh cho từng `f0`–`f11`.

## Fields used

- Features: `f0` … `f11` (pre-treatment anonymous features).
- Treatment: `treatment`.
- Primary outcome: `conversion`.
- Excluded from features: `visit`, `exposure`. Nguồn mô tả `exposure` là việc người dùng
  thực tế đã được quảng cáo tiếp cận; cả hai trường không được coi là baseline covariate
  trước treatment trong pipeline này.

## Quality contract

- không missing;
- mọi feature hữu hạn;
- treatment/conversion/visit/exposure chỉ nhận 0/1;
- treatment rate `0,850000`;
- conversion rate `0,002917`;
- difference in means conversion toàn data `0,001152`.

Balance AUC/SMD là diagnostic, không tự chứng minh randomization. Identification dựa vào
provenance randomized incrementality test của nguồn Criteo.

## Sprint 2 split

Phần 50% được Sprint 1 chọn bằng stratified sample seed 42 được loại hoàn toàn. Phần bù
6.989.795 dòng được chia:

| Split | Rows | Vai trò |
|---|---:|---|
| fit | 4.193.877 | fit model/nuisance |
| validation | 1.397.959 | calibration và chọn champion |
| confirmation | 1.397.959 | một lần đánh giá ngoài mẫu |

Index hash và seed nằm trong `output/sprint2/protocol_manifest.json`.

## Missing business fields

Dataset không có customer revenue, margin, contact cost hay long-term horizon. Vì vậy
mọi monetary/value result chỉ là scenario assumption; dataset này chưa đủ để kết luận
incremental CLV.
