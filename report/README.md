# Chỉ mục báo cáo

Thư mục này chứa **kết quả đã chạy**. Phương pháp nằm ở [`../docs/`](../docs/); bối cảnh
nghiên cứu ở [`../planning/`](../planning/).

## Nguồn số chính thức

Bảy báo cáo dưới đây là nguồn duy nhất được phép trích dẫn. Nếu một tài liệu khác trong
repo mâu thuẫn với chúng, ưu tiên báo cáo.

| Báo cáo | Phạm vi | Kết luận chính |
|---|---|---|
| [SPRINT_1_FINAL_REPORT.md](SPRINT_1_FINAL_REPORT.md) | Nền tảng causal, sáu model, final test 2.096.940 dòng | Response Qini `0,187886` dẫn đầu; khoảng tin cậy chỉ tách được Response khỏi T-Learner và DR-Learner |
| [SPRINT_2_FINAL_REPORT.md](SPRINT_2_FINAL_REPORT.md) | Policy, calibration, dashboard, confirmation 1.397.959 dòng | Champion Response top-k; X‑Renormalized − Response có CI chứa 0 |
| [SPRINT_3_FINAL_REPORT.md](SPRINT_3_FINAL_REPORT.md) | Vòng cải tiến có đăng ký trước, web app, ba chẩn đoán bổ sung | Không challenger nào đạt promotion rule; champion giữ nguyên |
| [CAUSAL_FOREST_REPORT.md](CAUSAL_FOREST_REPORT.md) | Thuật toán chuyên dụng trên ba mốc dữ liệu, chấm cùng holdout Sprint 1 | `policy_area_dr` hạng 1/6, Qini hạng 3/6; CI chứa 0 so với Response nên là hoà |
| [DATA_OPTIMIZATION_REPORT.md](DATA_OPTIMIZATION_REPORT.md) | Quay lại từ EDA, sentinel/funnel ablation, OOF hai seed và gate từng vấn đề | Response-Sentinel đi tiếp nhưng chưa được promote; champion vẫn là Response |
| [CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md](CAUSAL_FOUNDATION_EXPERIMENT_REPORT.md) | DINA, Anchored R, Pattern R; synthetic tests, screen hai seed và full finalist | Không causal learner qua screen; Response-Sentinel không ổn định ở full; giữ Response |
| [TOP_TAIL_RESEARCH_V2_REPORT.md](TOP_TAIL_RESEARCH_V2_REPORT.md) | Paired simultaneous audit của phát hiện hậu nghiệm ở hard budget 1–2%, event support và membership overlap | 16/16 causal point delta dương nhưng 0/16 lower bound vượt 0; không promote, giữ Response |

Đọc Causal Foundation trước nếu chỉ có ít thời gian — nó chứa trạng thái hiện hành; đọc Data
Optimization để xem giả thuyết EDA đứng trước vòng này.

## Cách đọc bảy báo cáo cùng nhau

Sprint 1 dựng nền tảng đo lường và cho ra một bảng xếp hạng. Sprint 2 biến bảng xếp hạng
đó thành một quyết định ngân sách có khoảng tin cậy. Sprint 3 đóng băng giao thức chọn
model trước khi chạy, rồi thử mười hai ứng viên dưới giao thức đó. Báo cáo Causal Forest
bổ sung một thuật toán chuyên dụng ngoài họ meta-learner, chấm trên cùng holdout Sprint 1.
Data Optimization lấy failure mode từ EDA và kết quả model để thử hai can thiệp mới mà không
sửa artifact đã phát hành.
Causal Foundation tiếp tục từ đó bằng estimator cho binary outcome hiếm, risk anchor và partial
pooling; finalist được chạy full-development trước khi quyết định giữ champion.
Top-Tail Research v2 kiểm định riêng tín hiệu 1–2% bằng familywise band và giữ nguyên quyết định vì
không có lower bound dương.

Kết luận xuyên suốt: **không phương pháp nhân quả nào tách được khỏi baseline dự đoán
outcome** trên bộ dữ liệu này. Bối cảnh nghiên cứu giải thích vì sao đây là chế độ đã được
mô tả trước chứ không phải dị thường:
[`../planning/RESEARCH_LANDSCAPE_2026.md`](../planning/RESEARCH_LANDSCAPE_2026.md).

## Kết luận tổng hợp — vì sao kết quả là "không cải thiện", và vì sao đó là một kết quả

Năm vòng cải tiến — mười hai candidate ở Sprint 3, bảy ở vòng data optimization, sáu ở vòng
causal foundation — không một challenger nào được promote. Cách đọc đúng con số đó **không**
phải "các phương pháp nhân quả không chạy được", mà là ba phát biểu tách bạch, mỗi phát biểu
có bằng chứng riêng.

### 1. Có một cơ chế giải thích, đo được trên dữ liệu thô

Hiệu ứng gần như tỉ lệ thuận với rủi ro nền: `τ(x) ≈ 0,53 · p₀(x)`. Trên 26 pattern
sentinel **rời nhau** — tức các tầng độc lập, không dùng chung quan sát — Pearson là
`0,769` và Spearman `0,883`. Quyết định hơn cả hai con số đó: Cochran `Q` giảm từ `861` trên
thang cộng xuống `150` trên thang nhân, tỷ lệ `5,7` lần.

Nghĩa là phần lớn heterogeneity biến mất khi đổi sang thang nhân. Hiệu ứng *có* thay đổi
theo `x`, nhưng chủ yếu theo đúng cách mà `p₀(x)` thay đổi. Vì `p₀` là thứ Response ước
lượng trực tiếp và ước lượng tốt, xếp hạng theo `p₀` đã gần đạt xếp hạng theo `τ`.

Đây là bằng chứng **đo trước mọi model**, nên nó không phải lời giải thích hậu nghiệm cho
một kết quả không mong muốn.

### 2. Phép đo hết độ phân giải trước khi model hết dư địa

Kể cả nếu một challenger thực sự tốt hơn, thiết kế hiện tại không công nhận được. Chênh
lệch Causal Forest − Response trên metric chính là `+4,96e-07` với nửa độ rộng CI
`5,90e-05` — CI rộng gấp **119 lần** đại lượng cần đo. Để tách được cần `2,97e10` dòng, tức
`2.123` lần toàn bộ Criteo.

Phân biệt hai câu này là điểm mấu chốt của cả tập báo cáo:

- "Challenger không tốt hơn" — điều dữ liệu **không** khẳng định được.
- "Dữ liệu không đủ để nói challenger tốt hơn" — điều dữ liệu **có** khẳng định.

Mọi kết luận trong bảy báo cáo đều là loại thứ hai. Đó là lý do quyết định luôn được viết
là *giữ champion vì challenger không vượt gate*, không phải *challenger kém hơn*.

### 3. Kết quả âm chỉ có giá trị khi giao thức đủ chặt

Một kết quả "không ai thắng" chỉ đáng tin nếu loại trừ được khả năng giao thức thiếu độ
nhạy hoặc kết luận được chọn sau khi nhìn số. Bốn cơ chế trong repo phục vụ đúng việc đó:

| Cơ chế | Nó loại trừ điều gì | Bằng chứng nó hoạt động thật |
|---|---|---|
| Metric hierarchy đăng ký trước | chọn metric có lợi sau khi xem kết quả | Sprint 3: Qini xếp ba challenger trên Response, metric chính xếp ngược lại — kết luận không đổi |
| Gate theo **từng** fold seed | che giấu bất ổn bằng cách lấy trung bình | Causal Foundation: `Response-Sentinel` qua screen rồi đổi dấu ở full |
| Power diagnostic trên `visit` | giao thức thiếu độ nhạy | Đổi sang outcome 4,7%, ba challenger chuyển từ "thua rõ" sang "không phân biệt được" |
| Paired CI bắt buộc | nhầm point estimate với bằng chứng | Sprint 2 giữ Response dù X‑Renormalized cao hơn; Sprint 3 xác nhận quyết định đó đúng |

Dòng thứ ba là quan trọng nhất. Nó cho thấy pipeline **có** phản ứng khi tín hiệu mạnh
lên, nên việc nó không phản ứng trên `conversion` là phát biểu về dữ liệu chứ không phải về
pipeline.

### Điều dự án tạo ra có giá trị

Sản phẩm của bảy báo cáo này không phải một model tốt hơn — không có model nào tốt hơn.
Sản phẩm là **một bộ máy đo đủ chặt để kết luận "không tốt hơn" một cách đáng tin**, cộng
với một cơ chế giải thích vì sao. Trong ứng dụng thực tế, biết chắc rằng một baseline rẻ và
đơn giản đã gần tối ưu là kết quả có giá trị vận hành trực tiếp: nó chặn được việc đầu tư
tiếp vào một hướng đã hết dư địa.

## Trạng thái sau bảy báo cáo

Cập nhật **12/08/2026**.

| | |
|---|---|
| Champion | **Response top-k**, không đổi từ Sprint 2 qua cả năm vòng cải tiến |
| Số vòng cải tiến đã chạy | 5, mỗi vòng một giao thức đăng ký trước riêng |
| Số challenger đạt promotion rule | **0** |
| Cơ chế giải thích | `τ(x) ≈ 0,53 · p₀(x)` — đo trực tiếp trên dữ liệu thô, xem `output/eda/` |

Bảy báo cáo trên là **đóng băng**: không sửa số trong báo cáo đã phát hành. Kết quả mới đi vào
một báo cáo mới, kèm banner trỏ qua lại.

## Hướng kế tiếp

Hướng "tìm model tốt hơn trên Criteo `conversion`" **đã đóng** — cần `2.123×` toàn bộ dataset mới
phân biệt được trên metric chính. Ba hướng còn mở, xếp theo giá trị trên chi phí, ghi đầy đủ ở
[`../planning/README.md`](../planning/README.md):

1. External validity trên dataset thứ hai — trả lời "Response thắng vì outcome hiếm hay nói chung".
2. Cross-fitted evaluation toàn bộ dữ liệu — thiếu hụt trên Qini chỉ `3,3×`, cải tiến **cách đánh
   giá** chứ không phải model.
3. M1 hybrid — đã hiện thực, chưa có dòng nào trong registry.

## Quy ước trình bày

Bảy báo cáo dùng chung một bố cục: kết luận trước, bằng chứng số ở giữa, giới hạn và
artifact ở cuối. Báo cáo chỉ chứa **kết quả và diễn giải**; phần vận hành nằm ở nơi khác:

| Cần gì | Đọc ở đâu |
|---|---|
| Lệnh chạy lại một vòng | [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) |
| Vai trò từng script | [`../scripts/README.md`](../scripts/README.md) |
| Phương pháp và công thức | [`../docs/README.md`](../docs/README.md) |
| Hướng nghiên cứu còn mở | [`../planning/README.md`](../planning/README.md) |

## Quy tắc

- Mọi con số trong báo cáo phải truy được về một file trong `output/`; xem
  [`../output/README.md`](../output/README.md) để biết thư mục nào là release.
- Không sửa số trong báo cáo đã phát hành. Nếu kết quả đổi, thêm banner cập nhật và trỏ
  sang báo cáo mới.
- Mọi claim "model A hơn B" phải kèm paired confidence interval.
- Không claim SOTA: không challenger nào thắng được baseline, và benchmark bên ngoài dùng outcome
  khác nên không so trực tiếp được.
