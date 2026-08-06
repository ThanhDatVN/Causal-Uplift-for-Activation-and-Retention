# Chỉ mục kế hoạch

Thư mục này chứa tài liệu định hướng nghiên cứu. Kết quả đã chạy nằm ở
[`../report/`](../report/); phương pháp nằm ở [`../docs/`](../docs/).

| Tài liệu | Nội dung |
|---|---|
| [RESEARCH_LANDSCAPE_2026.md](RESEARCH_LANDSCAPE_2026.md) | Bối cảnh nghiên cứu, vì sao baseline dự đoán outcome không bị tách khỏi các CATE learner, các bài toán lân cận, và mức xác minh của từng nguồn |

## Mức xác minh nguồn

Mọi nguồn được phân loại trước khi hiện thực:

| Mức | Nghĩa |
|---|---|
| `A` | Đọc được công thức hoặc số liệu gốc. Được phép hiện thực |
| `B` | Đọc được tóm tắt hoặc mô tả, chưa đọc công thức. **Chưa** được hiện thực |
| `C` | Chỉ có metadata |

Quy tắc: nguồn ở mức `C` không được hiện thực; phải nâng lên `A` trước.

## Quy tắc cho một vòng cải tiến mới

- Đăng ký metric, gate và promotion rule **trước** khi chạy, theo mẫu
  `configs/sprint3_improvement_protocol.json`.
- Không tune thêm trên test Sprint 1.
- Metric chính là `policy_area_dr`; Qini, AUUC, AUTOC và calibration là bằng chứng phụ.
  Không đổi kết luận bằng cách chọn metric sau khi xem kết quả.
- Mọi claim "model A hơn B" phải kèm paired confidence interval.
- Mọi lần chạy phải ghi vào `output/improvement/registry.csv`, kể cả lần thất bại.
