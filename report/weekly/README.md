# Báo cáo tiến độ theo tuần

Sáu báo cáo tuần bám đúng lịch đã chốt trong
[`SPRINT_PLAN_6_WEEKS.md`](../../planning/SPRINT_PLAN_6_WEEKS.md)
mục 6. Mỗi báo cáo có cùng cấu trúc:

1. Kế hoạch tuần đã chốt trước đó
2. Đã làm gì
3. **Cách hoạt động** — phần dài nhất, giải thích từng thành phần vận hành thế nào
4. Kết quả kèm số
5. Quyết định và lý do
6. Chưa xong và rủi ro
7. Chuẩn bị cho tuần sau
8. Câu hỏi cần mentor phản biện

## Lịch và trạng thái

| Tuần | Sprint | Trọng tâm theo kế hoạch | Báo cáo | Trạng thái |
|---|---|---|---|---|
| 1 | Sprint 1 | EDA, randomization diagnostic, 5 baseline, metric test | [WEEK_01.md](WEEK_01.md) | Đạt |
| 2 | Sprint 1 | Freeze data/run, Causal Forest preflight, sửa claim, bảng so sánh cuối | [WEEK_02.md](WEEK_02.md) | Đạt, trừ Causal Forest |
| 3 | Sprint 2 | Decision contract, decile/policy table, dashboard đầu tiên | [WEEK_03.md](WEEK_03.md) | Đạt |
| 4 | Sprint 2 | Dashboard acceptance, sensitivity, giải thích cho người dùng | [WEEK_04.md](WEEK_04.md) | Đạt |
| 5 | Sprint 3 | Kế hoạch cũ: Docker/CI, draft báo cáo | [WEEK_05.md](WEEK_05.md) | **Đổi phạm vi** — xem mục 5.1 của báo cáo |
| 6 | Sprint 3 | Kế hoạch cũ: release QA, demo, handoff | [WEEK_06.md](WEEK_06.md) | **Đổi phạm vi** — xem mục 6.1 của báo cáo |

## Ghi chú về thời điểm thực hiện

Công việc được thực hiện sớm hơn lịch. Sáu báo cáo này chia lại theo đúng cadence tuần đã
lên kế hoạch để đọc và kiểm tra theo từng phần, không phải để mô tả sáu tuần lịch thật.
Ngày trong mỗi báo cáo là ngày artifact được sinh ra, lấy từ manifest.

Tuần 5 và 6 lệch khỏi kế hoạch gốc. Kế hoạch cũ dự kiến Docker/CI/slides; thực tế mở một
vòng cải tiến model có đăng ký trước và một web application. Lý do và đánh đổi được ghi
trong mục 5.1 và 6.1 của hai báo cáo đó, không giấu trong phụ lục.

## Đọc kèm

- Tổng quan toàn dự án: [`../SPRINT_1_FINAL_REPORT.md`](../SPRINT_1_FINAL_REPORT.md) rồi
  [`../SPRINT_2_FINAL_REPORT.md`](../SPRINT_2_FINAL_REPORT.md)
- Rà soát từng thành phần: [`../../docs/COMPONENT_REVIEW_GUIDE.md`](../../docs/COMPONENT_REVIEW_GUIDE.md)
- Số chính thức: `../SPRINT_1_FINAL_REPORT.md`, `../SPRINT_2_FINAL_REPORT.md`,
  `../SPRINT_3_FINAL_REPORT.md`
