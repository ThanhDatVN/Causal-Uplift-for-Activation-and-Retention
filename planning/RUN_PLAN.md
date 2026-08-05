# RUN PLAN — đã thay thế

> **Trạng thái: lịch sử.** Runbook này viết trước Sprint 1 release (superseded
> 29/07/2026) và mô tả một lineup 6 model chạy một phần trên Colab. Nó được giữ vì
> `planning/CAUSAL_UPLIFT_PLAN.md` đã trích dẫn nó.

## Dùng gì thay thế

| Việc cần làm | Tài liệu hiện hành |
|---|---|
| Hiểu toàn bộ dự án | [`../docs/PROJECT_GUIDE.md`](../docs/PROJECT_GUIDE.md) |
| Tái lập Sprint 1 (5 model) | [`../README.md`](../README.md) mục "Chạy lại" |
| Tái lập Sprint 2 | [`../report/SPRINT_2_FINAL_REPORT.md`](../report/SPRINT_2_FINAL_REPORT.md) mục 10 |
| Tái lập Sprint 3 | [`../report/SPRINT_3_FINAL_REPORT.md`](../report/SPRINT_3_FINAL_REPORT.md) mục 12 |
| Causal Forest | [`../docs/KAGGLE_RUNBOOK_COMPLETE.md`](../docs/KAGGLE_RUNBOOK_COMPLETE.md) |
| Kế hoạch và trạng thái từng phase | [`SPRINT_3_EXECUTION_AND_WEB_PLAN.md`](SPRINT_3_EXECUTION_AND_WEB_PLAN.md) |

## Điều đã thay đổi so với bản cũ

- **Lineup không còn là "6 model".** Sprint 3 chạy 12 candidate ở screening và 6
  finalist trên toàn development pool, cộng ba biến thể ensemble. Danh sách nằm trong
  `configs/sprint3_improvement_protocol.json`.
- **Causal Forest chuyển từ Colab sang Kaggle**, vì nút thắt là CPU và system RAM chứ
  không phải GPU.
- **Metric chính đổi từ Qini sang `policy_area_dr`**, đăng ký trước khi chạy.
- **Bảng so sánh không còn dựng bằng `scripts/build_comparison.py`** cho vòng mới;
  Sprint 3 dùng `run_oof_experiment.py` → `compare_improvement_candidates.py` →
  `run_sprint3_confirmation.py`.

Kết quả 5 model local @50% mà bản cũ tham chiếu (`report/archive/week-01/baseline-results.md`)
vẫn là bằng chứng lịch sử hợp lệ, nhưng nguồn chính thức của số Sprint 1 là
`report/SPRINT_1_FINAL_REPORT.md`.
