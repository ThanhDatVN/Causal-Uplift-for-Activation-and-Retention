# Chỉ mục kế hoạch

Thư mục này chứa tài liệu định hướng nghiên cứu. Kết quả đã chạy nằm ở
[`../report/`](../report/); phương pháp nằm ở [`../docs/`](../docs/).

| Tài liệu | Nội dung |
|---|---|
| [LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md](LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md) | Ledger paper gốc 2024–2026 đến ngày 09-08, ánh xạ bằng chứng sang xử lý dữ liệu, hybrid/pretraining/direct-ranking, synthetic matrix, inference và promotion gate |
| [CAUSAL_DEEP_RESEARCH_2026.md](CAUSAL_DEEP_RESEARCH_2026.md) | Deep research sau causal-foundation: ITT so với exposure effect, information bound của thiết kế 85/15, top-tail policy, model selection không có CATE label, shrinkage/forest và falsification matrix |
| [RESEARCH_LANDSCAPE_2026.md](RESEARCH_LANDSCAPE_2026.md) | Bối cảnh nghiên cứu, vì sao baseline dự đoán outcome không bị tách khỏi các CATE learner, các bài toán lân cận, và mức xác minh của từng nguồn |
| [CAUSAL_FOUNDATION_RESEARCH.md](CAUSAL_FOUNDATION_RESEARCH.md) | Research khóa trước cho DINA, risk-anchored R-Learner và partial pooling; có status link sang kết quả đã chạy |

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
