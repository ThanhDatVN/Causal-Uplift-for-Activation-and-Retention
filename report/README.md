# Chỉ mục báo cáo

Thư mục này chứa **kết quả đã chạy**. Kế hoạch nằm ở `planning/`; hướng dẫn thực thi nằm
ở `docs/`.

## Nguồn số chính thức

Ba báo cáo sprint là nguồn số duy nhất được phép trích dẫn. Nếu một tài liệu khác trong
repo mâu thuẫn với chúng, ưu tiên báo cáo sprint.

| Báo cáo | Phạm vi | Kết luận chính |
|---|---|---|
| [SPRINT_1_FINAL_REPORT.md](SPRINT_1_FINAL_REPORT.md) | Nền tảng causal, 5 model, final test 2.096.940 dòng | Response Qini `0,187886` dẫn đầu; chỉ X vượt baseline của chính nó |
| [SPRINT_2_FINAL_REPORT.md](SPRINT_2_FINAL_REPORT.md) | Policy, calibration, dashboard, confirmation 1.397.959 dòng | Champion Response top-k; X‑Renormalized − Response có CI chứa 0 |
| [SPRINT_3_FINAL_REPORT.md](SPRINT_3_FINAL_REPORT.md) | Vòng cải tiến có đăng ký trước, web app, ba chẩn đoán bổ sung | Không challenger nào đạt promotion rule; champion giữ nguyên |

Đọc theo thứ tự ngược lại nếu chỉ có ít thời gian: Sprint 3 trước, vì nó chứa trạng thái
hiện hành.

## Tiến độ theo tuần

[weekly/](weekly/) — sáu báo cáo bám đúng lịch 6 tuần đã chốt, mỗi báo cáo có mục "Cách
hoạt động" giải thích cơ chế từng thành phần.

| Tuần | Sprint | Nội dung |
|---|---|---|
| [1](weekly/WEEK_01.md) | 1 | EDA, chẩn đoán randomization, 5 baseline, bộ metric |
| [2](weekly/WEEK_02.md) | 1 | Đóng băng pipeline, tuning, final test, gate Causal Forest |
| [3](weekly/WEEK_03.md) | 2 | Decision contract, policy value, dashboard đầu tiên |
| [4](weekly/WEEK_04.md) | 2 | Dashboard acceptance, độ nhạy chi phí |
| [5](weekly/WEEK_05.md) | 3 | Giao thức đăng ký trước, evaluation stack, 12 candidate |
| [6](weekly/WEEK_06.md) | 3 | Confirmation, quyết định champion, web app |

Tuần 5 và 6 lệch khỏi kế hoạch gốc; lý do và cái bị bỏ được ghi ở mục 5.1 và 6.1 của hai
báo cáo đó.

## Lịch sử — giữ để truy vết, không dùng làm nguồn số

[archive/](archive/) chứa:

| Tài liệu | Vai trò khi đó |
|---|---|
| `MENTOR_SPRINT_PLAN_6_WEEKS_AND_EVIDENCE_AUDIT.md` | Kế hoạch 6 tuần và sổ đăng ký công thức/claim. Là **nguồn của lịch tuần** mà `weekly/` bám theo. Mục 4 (chuẩn bằng chứng A/B/C) vẫn đáng đọc. |
| `REPOSITORY_AUDIT_2026-07-31.md` | Rà soát code/tài liệu trước lần push đầu tiên |
| `week-01/` | Nhật ký và kết quả baseline thời kỳ đầu; số đã bị thay bởi Sprint 1 report |
| `week-03-04-demo-checklist.md` | Biên bản acceptance của dashboard tĩnh Sprint 2 |

Vì sao giữ: chúng là bằng chứng tiến độ và được các báo cáo sprint trích dẫn. Vì sao tách
riêng: số trong đó đã bị thay thế, và trộn lẫn với báo cáo hiện hành dễ dẫn tới trích nhầm.

## Quy tắc

- Mọi con số trong báo cáo phải truy được về một file trong `output/`; xem
  [`../output/README.md`](../output/README.md) để biết thư mục nào là release.
- Không sửa số trong báo cáo đã phát hành. Nếu kết quả đổi, thêm banner cập nhật và trỏ
  sang báo cáo mới.
- Không dùng `report/archive/` làm nguồn số cho bất kỳ claim nào.
