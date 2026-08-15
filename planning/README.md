# Chỉ mục kế hoạch

Thư mục này chứa tài liệu định hướng nghiên cứu. Kết quả đã chạy nằm ở
[`../report/`](../report/); phương pháp nằm ở [`../docs/`](../docs/).

| Tài liệu | Nội dung |
|---|---|
| [LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md](LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md) | Ledger paper gốc 2024–2026 đến ngày 09-08, ánh xạ bằng chứng sang xử lý dữ liệu, hybrid/pretraining/direct-ranking, synthetic matrix, inference và promotion gate |
| [CAUSAL_DEEP_RESEARCH_2026.md](CAUSAL_DEEP_RESEARCH_2026.md) | Deep research sau causal-foundation: ITT so với exposure effect, information bound của thiết kế 85/15, top-tail policy, model selection không có CATE label, shrinkage/forest và falsification matrix |
| [RESEARCH_LANDSCAPE_2026.md](RESEARCH_LANDSCAPE_2026.md) | Bối cảnh nghiên cứu, vì sao baseline dự đoán outcome không bị tách khỏi các CATE learner, các bài toán lân cận, và mức xác minh của từng nguồn |
| [CAUSAL_FOUNDATION_RESEARCH.md](CAUSAL_FOUNDATION_RESEARCH.md) | Research khóa trước cho DINA, risk-anchored R-Learner và partial pooling; có status link sang kết quả đã chạy |

## Hướng kế tiếp

Cập nhật **14/08/2026**, sau sáu vòng cải tiến. Nguồn số: tám báo cáo trong
[`../report/`](../report/README.md).

| Hướng | Trạng thái | Lý do |
|---|---|---|
| Thêm model trên Criteo `conversion` | **Đã đóng** | Độ phân giải `±1,74e-05` trên metric chính, nhỏ hơn chênh lệch cần đo một bậc độ lớn. Vòng `rare-outcome` đã loại nốt giả thuyết "thua do cấu hình đặt sai" |
| External validity trên dataset thứ hai | **Ưu tiên 1** | Hướng duy nhất trả lời được "Response thắng vì outcome hiếm hay nói chung". Còn một điều kiện tiên quyết: nâng claim về `uplift-bench` từ mức `B` lên `A` |
| Cross-fitted evaluation toàn bộ dữ liệu | **Ưu tiên 2** | Đưa độ phân giải từ `±1,74e-05` xuống `±5,5e-06`. **Không** đủ để tách top 2 (chênh lệch `1,2e-06`), nhưng đủ để tách phần giữa bảng — ví dụ CF so với X-Renormalized (`2,4e-05`) và S-Under7 (`1,8e-05`), hiện đều có CI chứa 0 |
| M1 hybrid prognostic–causal logit | **Ưu tiên 3** | Đã hiện thực ở `src/hybrid.py` và có test, nhưng **0 dòng trong registry**. Chạy theo đúng thứ tự đã khóa |

Chi tiết và bằng chứng số của bảng này:
[LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md](LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)
mục 9 và 10.

### Backlog Causal Forest

Ghi lần đầu ở vòng causal foundation v1. Hạng mục có lý lẽ số mạnh nhất — event-aware minimum
leaf — **đã chạy và không đổi kết luận**, nên căn cứ cho các hạng mục còn lại yếu đi đáng kể.

| Hạng mục | Trạng thái |
|---|---|
| Event-aware minimum leaf | **Đã chạy 14/08/2026** — kết quả hòa, xem [`../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md`](../report/CAUSAL_FOREST_RARE_OUTCOME_REPORT.md) |
| Balanced/honest sampling | Chưa làm |
| Leaf shrinkage | Chưa làm |
| Sentinel contract cho feature | Chưa làm |
| Cùng OOF artifact schema với các candidate khác | Chưa làm — cần một `build_causal_forest()` trong `src/candidates.py` |

Hạng mục đầu xuất phát từ một con số: với `min_samples_leaf=500` của cấu hình đã chạy, mỗi lá
chỉ có kỳ vọng `0,145` sự kiện control, và honest splitting còn chia đôi tiếp. Cấu hình
`rare-outcome` nâng lên khoảng `2,9`.

Lưu ý profile `research` sẵn có **không** phải bản sửa cho vấn đề này: nó dùng
`min_samples_leaf=200`, tức đi sai hướng trên đúng ràng buộc đang bó.

Hạng mục cuối là điều kiện để Causal Forest đi qua được promotion rule của Sprint 3 thay vì chỉ
được chấm rời; nó cần 3 fold × 2 fold seed, tức sáu lần fit.

**Khi hai tài liệu trong thư mục này mâu thuẫn nhau, research plan thắng.** Ba tài liệu còn lại
giữ vai trò ghi bối cảnh và các hướng đã bị loại kèm lý do, không còn là lịch thực thi.

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
