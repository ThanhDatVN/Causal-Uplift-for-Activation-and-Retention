# Chỉ mục báo cáo

Thư mục này chứa **kết quả đã chạy**. Phương pháp nằm ở [`../docs/`](../docs/); bối cảnh
nghiên cứu ở [`../planning/`](../planning/).

## Nguồn số chính thức

Bốn báo cáo dưới đây là nguồn duy nhất được phép trích dẫn. Nếu một tài liệu khác trong
repo mâu thuẫn với chúng, ưu tiên báo cáo.

| Báo cáo | Phạm vi | Kết luận chính |
|---|---|---|
| [SPRINT_1_FINAL_REPORT.md](SPRINT_1_FINAL_REPORT.md) | Nền tảng causal, sáu model, final test 2.096.940 dòng | Response Qini `0,187886` dẫn đầu; khoảng tin cậy chỉ tách được Response khỏi T-Learner và DR-Learner |
| [SPRINT_2_FINAL_REPORT.md](SPRINT_2_FINAL_REPORT.md) | Policy, calibration, dashboard, confirmation 1.397.959 dòng | Champion Response top-k; X‑Renormalized − Response có CI chứa 0 |
| [SPRINT_3_FINAL_REPORT.md](SPRINT_3_FINAL_REPORT.md) | Vòng cải tiến có đăng ký trước, web app, ba chẩn đoán bổ sung | Không challenger nào đạt promotion rule; champion giữ nguyên |
| [CAUSAL_FOREST_REPORT.md](CAUSAL_FOREST_REPORT.md) | Thuật toán chuyên dụng trên ba mốc dữ liệu, chấm cùng holdout Sprint 1 | `policy_area_dr` hạng 1/6, Qini hạng 3/6; CI chứa 0 so với Response nên là hoà |

Đọc Sprint 3 trước nếu chỉ có ít thời gian — nó chứa trạng thái hiện hành.

## Cách đọc bốn báo cáo cùng nhau

Sprint 1 dựng nền tảng đo lường và cho ra một bảng xếp hạng. Sprint 2 biến bảng xếp hạng
đó thành một quyết định ngân sách có khoảng tin cậy. Sprint 3 đóng băng giao thức chọn
model trước khi chạy, rồi thử mười hai ứng viên dưới giao thức đó. Báo cáo Causal Forest
bổ sung một thuật toán chuyên dụng ngoài họ meta-learner, chấm trên cùng holdout Sprint 1.

Kết luận xuyên suốt: **không phương pháp nhân quả nào tách được khỏi baseline dự đoán
outcome** trên bộ dữ liệu này. Bối cảnh nghiên cứu giải thích vì sao đây là chế độ đã được
mô tả trước chứ không phải dị thường:
[`../planning/RESEARCH_LANDSCAPE_2026.md`](../planning/RESEARCH_LANDSCAPE_2026.md).

## Quy tắc

- Mọi con số trong báo cáo phải truy được về một file trong `output/`; xem
  [`../output/README.md`](../output/README.md) để biết thư mục nào là release.
- Không sửa số trong báo cáo đã phát hành. Nếu kết quả đổi, thêm banner cập nhật và trỏ
  sang báo cáo mới.
- Mọi claim "model A hơn B" phải kèm paired confidence interval.
