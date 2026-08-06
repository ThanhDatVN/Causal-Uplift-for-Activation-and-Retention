# Tutorial — đã thay thế

> **Trạng thái: lịch sử.** Tutorial này viết ở thời kỳ Sprint 2. Nó đã được thay bằng
> `report/SPRINT_1_FINAL_REPORT.md`, bao phủ toàn bộ nội dung của nó và bổ sung
> kiến trúc split, từng module trong `src/`, giao thức chọn model, web app và danh mục
> bẫy khi đọc kết quả.

## Vì sao thay

Số trong tutorial cũ là số Sprint 2 (Qini confirmation `0,182789` cho Response, DR net
`0,000799` tại budget 10%). Sau Sprint 3 những con số hiện hành là:

| Đại lượng | Sprint 2 | Sprint 3 |
|---|---:|---:|
| Metric chính | Qini | `policy_area_dr` |
| Response trên confirmation | Qini `0,182789` | `policy_area_dr` `0,000912`, Qini `0,192989` |
| DR net/khách hàng tại budget 10% | `0,000799` | `0,000856` |

Số Sprint 3 khác vì model được refit trên development pool lớn hơn (5.591.836 dòng thay
vì 4.193.877), không phải vì phương pháp đánh giá đổi.

## Nội dung khái niệm vẫn đúng nguyên văn

Ba điểm sau trong tutorial cũ vẫn là quy tắc của dự án và được giữ nguyên trong
`report/SPRINT_1_FINAL_REPORT.md`:

1. Với cùng một người chỉ quan sát được một trong hai potential outcome. Randomized
   experiment cho phép ước lượng hiệu ứng có điều kiện, nhưng **không** biến principal
   stratum của từng cá nhân thành nhãn quan sát được.
2. Persuadable, Sure Thing, Lost Cause và Sleeping Dog là **khung khái niệm**. Không
   được nhìn dấu của một score rồi tuyên bố đã biết một người thuộc nhóm nào.
3. Model A có point estimate cao hơn model B là chưa đủ; phải xem CI của **chênh lệch**
   trên cùng bootstrap resamples.

Đọc `report/SPRINT_1_FINAL_REPORT.md`.
