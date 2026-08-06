# Báo cáo lịch sử

Bằng chứng tiến độ của các giai đoạn trước. **Không dùng làm nguồn số.**

Quy ước đặt tên trong `report/`: tên VIẾT HOA là **nguồn số chính thức**, tên viết-thường-
gạch-nối là **lịch sử**. Nhìn tên file là biết trạng thái, không cần mở ra.

| Tài liệu | Nội dung | Đã bị thay bởi |
|---|---|---|
| `week-01-daily-log.md` | Nhật ký ngày tuần 1 | [`../weekly/WEEK_01.md`](../weekly/WEEK_01.md) |
| `week-01-report.md` | EDA và chẩn đoán randomization lần đầu | [`../SPRINT_1_FINAL_REPORT.md`](../SPRINT_1_FINAL_REPORT.md) |
| `week-01-baseline-results.md` | Kết quả năm baseline lần chạy đầu | [`../SPRINT_1_FINAL_REPORT.md`](../SPRINT_1_FINAL_REPORT.md) mục 6 |
| `week-03-04-demo-checklist.md` | Biên bản acceptance dashboard tĩnh Sprint 2 | [`../SPRINT_2_FINAL_REPORT.md`](../SPRINT_2_FINAL_REPORT.md) mục 6 |
| `repository-audit-2026-07-31.md` | Rà soát code và tài liệu trước lần push đầu tiên | [`../SPRINT_3_FINAL_REPORT.md`](../SPRINT_3_FINAL_REPORT.md) |

## Số đã bị thay

Chỗ dễ trích nhầm nhất: `week-01-baseline-results.md` ghi Qini Response `0,1793`, còn
release Sprint 1 ghi `0,187886`. Hai con số đến từ hai lần chạy trên hai tập test khác
nhau; chỉ số sau là chính thức.

## Kế hoạch 6 tuần đã chuyển đi

Kế hoạch sáu tuần trước nằm ở thư mục này, nhưng nó là **kế hoạch** chứ không phải báo
cáo — và `weekly/` vẫn trích nó làm nguồn của lịch tuần, tức nó chưa hề chết. Để nó trong
thư mục dán nhãn "không dùng làm nguồn" là một mâu thuẫn.

Nó đã chuyển sang
[`../../planning/SPRINT_PLAN_6_WEEKS.md`](../../planning/SPRINT_PLAN_6_WEEKS.md).

Mục 4 của tài liệu đó định nghĩa **chuẩn bằng chứng A/B/C** mà toàn bộ dự án vẫn dùng:

- **A** — paper gốc, dataset owner, hoặc tài liệu chính thức của tác giả;
- **B** — implementation được đối chiếu với thư viện tham chiếu và có test;
- **C** — input kịch bản do dự án đặt, không phải biến quan sát.

Chuẩn này về sau được mở rộng thành thang xác minh `A`/`B`/`C` cho nguồn nghiên cứu trong
[`../../planning/RESEARCH_LANDSCAPE_2026.md`](../../planning/RESEARCH_LANDSCAPE_2026.md).
