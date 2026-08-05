# Chỉ mục kế hoạch

Thư mục này chứa kế hoạch và tài liệu scoping. Kết quả đã chạy nằm trong `report/`;
hướng dẫn thực thi nằm trong `docs/`.

## Hiện hành

| Tài liệu | Nội dung |
|---|---|
| [NEXT_ROUND_PLAN.md](NEXT_ROUND_PLAN.md) | Vòng tiếp theo sau Sprint 3. Phần A hoàn tất Causal Forest (đang chạy); Phần B ba hướng cải tiến kèm ba hướng đã loại và lý do. **Không phải Sprint 4** |
| [MARKET_AND_VALUE_RESEARCH.md](MARKET_AND_VALUE_RESEARCH.md) | Research thị trường 2025–2026 và kế hoạch bốn phase nâng giá trị dự án. Số liệu bốn dataset đã đo tại chỗ; mức xác minh `T` cho nguồn thương mại |
| [SPRINT_3_EXECUTION_AND_WEB_PLAN.md](SPRINT_3_EXECUTION_AND_WEB_PLAN.md) | Kế hoạch Sprint 3 và bảng trạng thái từng phase, kèm sai lệch so với plan |
| [RESEARCH_LANDSCAPE_2026.md](RESEARCH_LANDSCAPE_2026.md) | Bối cảnh nghiên cứu, vì sao Response thắng, bài toán lân cận, mức xác minh từng nguồn |
| [sprints.md](sprints.md) | Lộ trình ba sprint và trạng thái gửi mentor |
| [SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md](SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md) | Kế hoạch vòng cải tiến; đã thực hiện xong ở Sprint 3, có banner ghi mục nào làm mục nào không |

## Scoping cho bài toán chưa mở

| Tài liệu | Trạng thái |
|---|---|
| [incremental_value_product/](incremental_value_product/) | Kế hoạch sản phẩm Incremental CLV. **Chưa mở.** Điều kiện dữ liệu chưa đáp ứng; xem `RESEARCH_LANDSCAPE_2026.md` mục 3.2 |

## Lịch sử

| Tài liệu | Trạng thái |
|---|---|
| [CAUSAL_UPLIFT_PLAN.md](CAUSAL_UPLIFT_PLAN.md) | Kế hoạch gốc trước Sprint 1 release |
| [RUN_PLAN.md](RUN_PLAN.md) | Runbook 6 model, thay bằng các runbook theo sprint |

## Quy tắc

Trước khi hiện thực một phương pháp mới, đối chiếu `RESEARCH_LANDSCAPE_2026.md`. Nguồn
ở mức xác minh `C` (chỉ có metadata) không được hiện thực; phải nâng lên `A` (đọc được
công thức) trước.

Mọi vòng cải tiến mới phải đăng ký metric, gate và promotion rule **trước** khi chạy,
theo mẫu `configs/sprint3_improvement_protocol.json`.
