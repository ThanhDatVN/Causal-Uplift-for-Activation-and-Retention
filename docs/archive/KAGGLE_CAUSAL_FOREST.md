# Runbook Causal Forest trên Kaggle — đã thay thế

> **Trạng thái: lịch sử.** Tài liệu này là bản tóm tắt ngắn của Sprint 2. Nó đã được
> thay bằng [**KAGGLE_RUNBOOK_COMPLETE.md**](../KAGGLE_RUNBOOK_COMPLETE.md), chứa toàn bộ
> bước từ tạo notebook đến khi có số trong báo cáo, code dán được ngay, danh mục 15 lỗi
> có thể gặp và checklist đóng hạng mục.
>
> File này được giữ vì các báo cáo Sprint 1 và Sprint 2 đã trích dẫn nó. Không cập nhật
> nội dung ở đây; mọi thay đổi đi vào runbook mới.

## Điều vẫn đúng và không đổi

- **Trạng thái:** local code-path smoke 0,1% pass (4.194 score finite và aligned).
  Kaggle 20% / 30% / 50% **chưa chạy**. Không có Causal Forest trong bảng release.
- **Không chọn GPU.** `CausalForestDML` dùng CPU parallelism và system RAM; chọn GPU
  không làm forest nhanh hơn. Xem
  [Kaggle Efficient GPU Usage](https://www.kaggle.com/docs/efficient-gpu-usage).
- **Profile `kaggle-safe`:** 200 trees, `min_samples_leaf=500`, cross-validation 2-fold,
  `max_samples=0.25`, `inference=False`. Vì `inference=False`, không gọi
  `effect_interval()`; uncertainty đến từ holdout bootstrap.
- **Ba stage bắt buộc theo thứ tự** 20% → 30% → 50%, mỗi stage phải pass gate.
- **SHA-256 dữ liệu:** `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`.

## Điều đã được bổ sung trong runbook mới

Runbook mới thêm những phần mà file này không có:

- code chuẩn bị session, cài dependency có ghim `scikit-learn<1.7` theo ràng buộc của
  `econml==0.16.0`, và yêu cầu restart kernel;
- `scripts/evaluate_causal_forest.py` — bước chấm điểm còn thiếu; gate cũ **chỉ** kiểm
  tra tài nguyên và toàn vẹn artifact, không đánh giá chất lượng model;
- giải thích vì sao **chỉ stage 50% mới so được với bảng release**, và bằng chứng kiểm
  chứng cho điều đó;
- danh mục 15 lỗi có thể gặp kèm cách sửa;
- checklist đóng hạng mục và cách viết báo cáo nếu quyết định không chạy.

Xem [KAGGLE_RUNBOOK_COMPLETE.md](../KAGGLE_RUNBOOK_COMPLETE.md).
