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

Protocol `data-optimization-v1` dùng `visit` theo một vai trò hẹp hơn: auxiliary training
outcome để factorize joint probability, không phải feature của người cần score. Cache giữ nó
theo `source_index`; `predict(X)` vẫn chỉ nhận `f0..f11`. Không diễn giải mô hình conditional
qua `visit` như direct hoặc mediated causal effect.

## Quality contract

- không missing;
- mọi feature hữu hạn;
- treatment/conversion/visit/exposure chỉ nhận 0/1;
- treatment rate `0,850000`;
- conversion rate `0,002917`;
- difference in means conversion toàn data `0,001152`.

Balance AUC/SMD là diagnostic, không tự chứng minh randomization. Identification dựa vào
provenance randomized incrementality test của nguồn Criteo.

## Cấu trúc feature — điều mà "không missing" không nói ra

Contract "không missing" đúng về mặt cú pháp. Chẩn đoán đầy đủ ở `output/eda/` cho thấy cấu
trúc thật khác hẳn ấn tượng của một bảng 12 biến liên tục:

| Quan sát | Số đo |
|---|---|
| Đặc trưng có hơn 90% khối lượng ở đúng một giá trị | 6/12 (`f1` 0,988 · `f11` 0,986 · `f4` và `f10` 0,957 · `f5` và `f7` 0,947) |
| Đặc trưng không cắt được thành hai bin phân vị | 6/12 — cùng sáu đặc trưng trên |
| Cặp có mask "nằm ở mode" trùng khít **đúng 1,00** | 4 — `(f0, f6)`, `(f2, f8)`, `(f4, f10)`, `(f5, f7)` |
| Cặp có `|Spearman| > 0,99` | 2 — `(f4, f10)` `+0,999`, `(f5, f7)` `−0,999`; `|Pearson|` chỉ `0,66` và `0,75` |
| Số pattern "ở mode / khác mode" khác nhau | 53 trên 4.096 khả năng; pattern lớn nhất chiếm 43,6% số dòng |
| Trung vị số đặc trưng khác giá trị mode trên mỗi dòng | **2 trên 12** |

Bốn cặp mask trùng khít tuyệt đối là bằng chứng rằng point mass **có thể** là mã của giá trị
không quan sát được với một cơ chế mã hóa dùng chung. Criteo **không** công bố quy trình mã hoá
giá trị thiếu, nên đây là suy luận từ cấu trúc quan sát được, không phải một tính chất được
nguồn xác nhận. Không dùng nó để hoàn nguyên giá trị gốc.

Cách dùng đúng: giải thích vì sao không gian covariate hiệu dụng hẹp hơn con số 12 rất
nhiều. Champion không dùng feature phái sinh; protocol data optimization chỉ kiểm tra cờ
sentinel fold-local như một ablation, chưa đưa nó vào release.

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
