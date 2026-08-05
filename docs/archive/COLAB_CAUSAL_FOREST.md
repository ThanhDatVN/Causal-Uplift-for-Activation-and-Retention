# Causal Forest trên Colab — phương án không dùng

> **Trạng thái: lịch sử.** Luồng hiện hành chạy Causal Forest trên **Kaggle**, theo
> [KAGGLE_RUNBOOK_COMPLETE.md](../KAGGLE_RUNBOOK_COMPLETE.md). File này được giữ vì
> `report/archive/MENTOR_SPRINT_PLAN_6_WEEKS_AND_EVIDENCE_AUDIT.md` đã trích dẫn nó.

## Vì sao không chọn Colab

`CausalForestDML` của EconML bị chặn bởi **CPU và system RAM**, không phải GPU. Colab
Pro chủ yếu bán thêm GPU và thời lượng session; nó không giải quyết đúng nút thắt của
bài toán này. Mua Colab Pro chỉ để chạy `CausalForestDML` là chi tiền cho tài nguyên
không được dùng.

Điều kiện duy nhất khiến Colab Pro đáng cân nhắc, ghi trong
`planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md` mục 6:

- có candidate deep learning đã thắng screening trên Kaggle hoặc local;
- GPU hoặc RAM là blocker **đã đo**, không phải giả định;
- compute còn lại ước tính nhỏ hơn ngân sách mua;
- checkpoint và resume đã sẵn sàng.

Không điều kiện nào trong bốn điều trên được thỏa ở thời điểm hiện tại: vòng cải tiến
Sprint 3 không promote candidate nào, và không có candidate deep nào trong shortlist.

## Điều vẫn đúng, đã được chuyển sang luồng Kaggle

Nguyên tắc quan trọng nhất của bản cũ vẫn được giữ nguyên và nay được kiểm chứng bằng
code trong `scripts/evaluate_causal_forest.py`:

> Holdout được xác định bởi `seed=42` + `frac=0.50` + cách stratify. Đừng đổi `FRAC`,
> `SEED`, `TEST_SIZE`, nếu không CATE sẽ không ghép được với 5 baseline.

Trong luồng Kaggle, điều này được kiểm tra tự động bằng hash của `Y` và `T` chứ không
dựa vào việc người chạy nhớ đúng tham số.

## Ghi chú về các con số trong bản cũ

Bản cũ có các mốc 30%/50%, 24 GB và 90 phút. Đó là **ngoại suy tuyến tính từ benchmark
20% chạy local**, không phải cam kết tài nguyên hay runtime của Colab. Resource của
Colab thay đổi theo thời điểm và loại tài khoản; không ghi cứng một cấu hình nào vào
tài liệu.

`notebooks/colab_causal_forest.ipynb` thuộc cùng phương án này và mang cùng trạng thái
lịch sử.

Xem [KAGGLE_RUNBOOK_COMPLETE.md](../KAGGLE_RUNBOOK_COMPLETE.md).
