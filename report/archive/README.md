# Báo cáo lịch sử

Bằng chứng tiến độ và kế hoạch của các giai đoạn trước. **Không dùng làm nguồn số.**

| Tài liệu | Nội dung | Đã bị thay bởi |
|---|---|---|
| `MENTOR_SPRINT_PLAN_6_WEEKS_AND_EVIDENCE_AUDIT.md` | Kế hoạch 6 tuần, rà soát cấu trúc, sổ đăng ký công thức và claim | Lịch tuần → [`../weekly/`](../weekly/); kết quả → ba báo cáo sprint |
| `REPOSITORY_AUDIT_2026-07-31.md` | Rà soát trước lần push đầu tiên | Trạng thái hiện hành → [`../SPRINT_3_FINAL_REPORT.md`](../SPRINT_3_FINAL_REPORT.md) |
| `week-01/` | Nhật ký ngày, EDA, kết quả baseline đầu tiên | [`../SPRINT_1_FINAL_REPORT.md`](../SPRINT_1_FINAL_REPORT.md) |
| `week-03-04-demo-checklist.md` | Biên bản acceptance dashboard tĩnh Sprint 2 | [`../SPRINT_2_FINAL_REPORT.md`](../SPRINT_2_FINAL_REPORT.md) mục 6 |

## Phần vẫn còn giá trị

`MENTOR_SPRINT_PLAN_6_WEEKS_AND_EVIDENCE_AUDIT.md` mục 4 định nghĩa **chuẩn bằng chứng
A/B/C** mà toàn bộ dự án vẫn dùng:

- **A** — paper gốc, dataset owner, hoặc tài liệu chính thức của tác giả;
- **B** — implementation được đối chiếu với thư viện tham chiếu và có test;
- **C** — input kịch bản do dự án đặt, không phải biến quan sát.

Chuẩn này về sau được mở rộng thành thang xác minh `A`/`B`/`C` cho nguồn nghiên cứu trong
[`../../planning/RESEARCH_LANDSCAPE_2026.md`](../../planning/RESEARCH_LANDSCAPE_2026.md).

## Số đã bị thay

Ví dụ dễ trích nhầm nhất: `week-01/baseline-results.md` ghi Qini Response `0,1793`, còn
release Sprint 1 ghi `0,187886`. Hai con số đến từ hai lần chạy khác nhau; chỉ số sau là
chính thức.
