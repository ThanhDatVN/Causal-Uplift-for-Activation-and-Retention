# Chỉ mục báo cáo

Thư mục này chứa **kết quả đã chạy**. Kế hoạch nằm ở [`../planning/`](../planning/);
hướng dẫn thực thi nằm ở [`../docs/`](../docs/).

## Cấu trúc

```text
report/
├── SPRINT_1_FINAL_REPORT.md    nền tảng, sáu model, final test
├── SPRINT_2_FINAL_REPORT.md    policy, calibration, dashboard
├── SPRINT_3_FINAL_REPORT.md    vòng cải tiến đăng ký trước, web app
├── CAUSAL_FOREST_REPORT.md     thuật toán chuyên dụng, ba mốc dữ liệu
├── weekly/                     sáu báo cáo tiến độ theo tuần
└── archive/                    lịch sử, không dùng làm nguồn số
```

Quy ước đặt tên: **VIẾT HOA** là nguồn số chính thức, **viết-thường-gạch-nối** là lịch
sử. Nhìn tên file là biết trạng thái.

## Nguồn số chính thức

Bốn báo cáo dưới đây là nguồn duy nhất được phép trích dẫn. Nếu một tài liệu khác trong
repo mâu thuẫn với chúng, ưu tiên báo cáo.

| Báo cáo | Phạm vi | Kết luận chính |
|---|---|---|
| [SPRINT_1_FINAL_REPORT.md](SPRINT_1_FINAL_REPORT.md) | Nền tảng causal, sáu model, final test 2.096.940 dòng | Response Qini `0,187886` dẫn đầu; chỉ X vượt baseline của chính nó |
| [SPRINT_2_FINAL_REPORT.md](SPRINT_2_FINAL_REPORT.md) | Policy, calibration, dashboard, confirmation 1.397.959 dòng | Champion Response top-k; X‑Renormalized − Response có CI chứa 0 |
| [SPRINT_3_FINAL_REPORT.md](SPRINT_3_FINAL_REPORT.md) | Vòng cải tiến có đăng ký trước, web app, ba chẩn đoán bổ sung | Không challenger nào đạt promotion rule; champion giữ nguyên |
| [CAUSAL_FOREST_REPORT.md](CAUSAL_FOREST_REPORT.md) | Thuật toán chuyên dụng trên ba mốc dữ liệu, chấm cùng holdout Sprint 1 | `policy_area_dr` hạng 1/6, Qini hạng 3/6; CI chứa 0 so với Response nên là hoà |

Đọc Sprint 3 trước nếu chỉ có ít thời gian — nó chứa trạng thái hiện hành.

## Tiến độ theo tuần

[weekly/](weekly/) — sáu báo cáo bám lịch đã chốt trong
[`../planning/SPRINT_PLAN_6_WEEKS.md`](../planning/SPRINT_PLAN_6_WEEKS.md). Mỗi báo cáo
có mục "Cách hoạt động" giải thích cơ chế từng thành phần.

| Tuần | Sprint | Nội dung |
|---|---|---|
| [1](weekly/WEEK_01.md) | 1 | EDA, chẩn đoán randomization, năm baseline, bộ metric |
| [2](weekly/WEEK_02.md) | 1 | Đóng băng pipeline, tuning, final test, gate Causal Forest |
| [3](weekly/WEEK_03.md) | 2 | Decision contract, policy value, dashboard đầu tiên |
| [4](weekly/WEEK_04.md) | 2 | Dashboard acceptance, độ nhạy chi phí |
| [5](weekly/WEEK_05.md) | 3 | Giao thức đăng ký trước, evaluation stack, 12 candidate |
| [6](weekly/WEEK_06.md) | 3 | Confirmation, quyết định champion, web app |

Tuần 5 và 6 lệch khỏi kế hoạch gốc; lý do và phần bị bỏ ghi ở mục 5.1 và 6.1 của hai báo
cáo đó.

## Lịch sử

[archive/](archive/) giữ năm tài liệu để truy vết tiến độ. Chi tiết từng file và số nào
đã bị thay: [archive/README.md](archive/README.md).

Vì sao giữ: chúng là bằng chứng tiến độ và được các báo cáo sprint trích dẫn. Vì sao tách
riêng: số trong đó đã bị thay thế, trộn lẫn với báo cáo hiện hành dễ dẫn tới trích nhầm.

## Quy tắc

- Mọi con số trong báo cáo phải truy được về một file trong `output/`; xem
  [`../output/README.md`](../output/README.md) để biết thư mục nào là release.
- Không sửa số trong báo cáo đã phát hành. Nếu kết quả đổi, thêm banner cập nhật và trỏ
  sang báo cáo mới.
- Không dùng `report/archive/` làm nguồn số cho bất kỳ claim nào.
