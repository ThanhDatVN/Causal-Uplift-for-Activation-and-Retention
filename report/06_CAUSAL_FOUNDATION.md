# Báo cáo 06 — Causal foundation: estimator cho outcome nhị phân hiếm

- **Ngày:** 09/08/2026
- **Protocol:** `configs/causal_foundation_protocol_v1.json`
- **Phương pháp:** [`../docs/methods/06_RARE_OUTCOME_LEARNERS.md`](../docs/methods/06_RARE_OUTCOME_LEARNERS.md)
- **Research khóa trước:** `planning/CAUSAL_FOUNDATION_RESEARCH.md`
- **Nguồn số:** `output/improvement/causal_foundation_comparison/`,
  `output/improvement/causal_foundation_finalist_comparison/`,
  `output/improvement/causal_foundation_analysis/`
- **Phạm vi bằng chứng:** development OOF, **không đọc confirmation**

> **Vòng tiếp theo:** phát hiện hậu nghiệm ở budget 1–2% đã được kiểm lại bằng paired
> simultaneous band trong [`07_TOP_TAIL_RESEARCH.md`](07_TOP_TAIL_RESEARCH.md).
> Lần kiểm đó không tìm thấy bằng chứng vượt trội và không thay đổi quyết định giữ Response
> của báo cáo này.

## 1. Kết luận

Không causal learner mới nào thắng Response trên cả hai fold seed ở bước sàng lọc 15%. Binary
DINA và Anchored Pattern R đổi dấu theo seed; hai biến thể Anchored R tự do làm giảm
`policy_area_dr` một cách có hệ thống.

`Response-Sentinel` là candidate duy nhất qua được gate point estimate ở bước sàng lọc, nhưng
chạy trên toàn development pool thì kết quả đảo lại:

| Stage | Seed | Response | Response-Sentinel | Delta Sentinel - Response |
|---|---:|---:|---:|---:|
| Screen 15% | 101 | 0,000856779 | 0,000858831 | +2,052e-6 |
| Screen 15% | 202 | 0,000852166 | 0,000855201 | +3,035e-6 |
| Full | 101 | 0,000851809 | 0,000853022 | +1,213e-6 |
| Full | 202 | 0,000870409 | 0,000868334 | -2,075e-6 |

Trung bình delta ở mức full là `-4,310e-7`, tức gate ổn định thất bại. Champion giữ nguyên
**Response**. Vòng này không đọc confirmation Sprint 2, không chạy randomized confirmation mới
và không chạy lại Causal Forest.

## 2. Nghiên cứu và protocol

Phần rà soát nghiên cứu hoàn tất trước khi protocol sinh ra bất kỳ kết quả nào. Ba giả thuyết
được đăng ký:

1. Binary DINA học hiệu ứng trên thang tham số tự nhiên, tức log-odds;
2. Anchored R giữ nguyên thứ hạng tiên lượng và chỉ học phần dư đã co lại theo hệ số 0,25;
3. Anchored Pattern R gộp một phần phần dư theo 53 cấu trúc sentinel.

Estimand vẫn là CATE tuyệt đối của `conversion`. DINA chỉ dùng log odds ratio bên trong
estimator rồi đổi ngược về chênh lệch xác suất. `visit` và `exposure` không được dùng làm
feature; propensity cố định ở `0,85`.

Các gate được khóa trước khi chạy:

- smoke chỉ kiểm đường đi của code;
- sàng lọc dùng đúng 838.776 source row, 244 conversion ở nhánh control, fold seed 101 và 202;
- candidate phải có `policy_area_dr` cao hơn Response ở **cả hai** seed;
- chỉ finalist và Response được chạy trên toàn development pool;
- muốn promote thì cần một randomized confirmation mới với paired 95% CI có cận dưới lớn hơn 0.

Ensemble vẫn được dựng ở bước sàng lọc nhưng chỉ để chẩn đoán; guard chọn model cưỡng chế cờ
`diagnostic_ensemble_not_eligible`.

## 3. Kiểm thử trước khi chạm dữ liệu thật

Các test mới xác nhận:

- gradient và Hessian của DINA khớp với sai phân hữu hạn;
- DINA khôi phục đúng thứ hạng CATE trên thang log-odds với dữ liệu sinh có đáp án;
- Anchored R khôi phục đúng thứ hạng CATE tuyệt đối trên dữ liệu sinh có đáp án;
- Pattern R nhận ra được moderator dạng sentinel;
- shrinkage, prior và ngưỡng cắt xác suất không hợp lệ đều bị từ chối;
- phép so sánh giữa hai seed từ chối chạy nếu khác source row hoặc khác manifest contract;
- bước ghép OOF chạy tách tiến trình từ chối ghép nếu mảng nuisance khác nhau;
- biểu diễn sentinel dạng nén đưa vào LightGBM cho ra dự đoán trùng khít tuyệt đối với dạng
  dày.

Mỗi bộ test có mục tiêu đều pass trước lần chạy tương ứng. Kết quả chạy toàn bộ test của repo
nằm ở mục 10, ghi sau khi hoàn tất tài liệu.

## 4. Smoke và rà soát tài nguyên

Lần thử smoke ở 2% dừng khi hệ thống dùng tới 75,1% RAM. Vì stage này chỉ kiểm đường đi của
code và không có đủ sự kiện để chọn model, protocol ghi một amendment hạ quy mô xuống 1%. Lần
chạy chính thức hoàn tất trên 55.919 dòng nhưng chỉ có 16 conversion ở nhánh control, nên
không con số nào của smoke được dùng để kết luận về chất lượng model.

Lần thử sàng lọc đầu tiên dừng sau khi cross-fit nuisance dùng chung và trước khi chấm điểm
candidate, ở mức 75,8% với 3,68 GB RAM còn trống. Ngưỡng phần trăm được chỉnh dần cho khớp với
sàn tuyệt đối 2 GB; mọi amendment đều ghi rõ lý do và bằng chứng trong protocol. Không
candidate, hyperparameter hay metric nào bị đổi trong quá trình đó.

Lần chạy gộp toàn bộ cho thấy đỉnh bộ nhớ tích lũy dần qua các candidate. Finalist vì thế được
chạy tách tiến trình, và OOF chỉ được ghép sau khi qua các phép kiểm hợp đồng trùng khít. Phép
thêm cờ sentinel dạng dày vẫn chạm sàn cứng, nên transform được cấp phát trước một lần rồi
chuyển sang kiểu dữ liệu hỗn hợp gọn hơn. Đỉnh bộ nhớ của mọi thành phần chạy thành công đều
nằm trong ngưỡng, và mọi manifest hoàn tất đều có `resource_gate_passed=true`.

## 5. Sàng lọc trên 15% pool

| Candidate | Mean `policy_area_dr` | Mean delta vs Response | Min delta | Gate |
|---|---:|---:|---:|---|
| Response-Sentinel | 0,000857016 | +2,543e-6 | +2,052e-6 | advance |
| Response | 0,000854473 | — | — | reference |
| Anchored-Pattern-R | 0,000851566 | -2,907e-6 | -1,480e-5 | fail: seed instability |
| DINA-CATE-Sentinel | 0,000849705 | -4,768e-6 | -2,033e-5 | fail: seed instability |
| Anchored-R25-Sentinel | 0,000830633 | -2,384e-5 | -3,635e-5 | fail: systematic regression |
| Anchored-R25 | 0,000828917 | -2,556e-5 | -4,301e-5 | fail: systematic regression |

Paired CI so với Response đều chứa 0. Ví dụ ở seed 101:

- Response-Sentinel: `+2,052e-6`, CI `[-8,868e-6; 1,373e-5]`, `P(delta>0)=0,64`;
- DINA: `+1,080e-5`, CI `[-7,758e-5; 1,175e-4]`, `P(delta>0)=0,53`;
- Anchored R25: `-4,301e-5`, CI `[-9,597e-5; 2,891e-6]`, `P(delta>0)=0,03`.

Sang seed 202, DINA đổi dấu thành `-2,033e-5`, còn Pattern R đổi từ `-1,480e-5` thành
`+8,986e-6`. Không được phép chọn seed nào có lợi cho kết luận.

## 6. Bất đồng giữa các metric và giữa các mức budget

DINA có AUTOC trung bình `0,003174`, cao hơn Response `0,003086`, nhưng Qini trung bình chỉ
`0,174370` so với `0,183628`, và diện tích policy — metric chính — thì thấp hơn. DINA cũng có
sai số hiệu chuẩn `0,000582–0,000720` và độ lệch chuẩn của điểm khoảng `0,0092`, lớn hơn
Anchored R khoảng `0,004`. Học trên đúng thang tham số tự nhiên không tự khử được phương sai
xếp hạng ở cỡ mẫu hữu hạn.

Một phát hiện hậu nghiệm cần ghi lại cho vòng nghiên cứu sau: cả bốn causal candidate đều có
gross policy value cao hơn Response tại budget 1% và 2%, trên cả seed 101 lẫn 202 — tức thắng
4/4 so sánh với mỗi model. Nhưng metric chính đã khóa là diện tích trên dải 1–30%, và Anchored
R cùng Pattern R mất lợi thế đó khi xét dải budget rộng. Không được dùng quan sát ở 1–2% để
đảo quyết định hiện tại. Nếu ràng buộc kinh doanh thật sự nằm ở budget cực thấp thì phải đăng
ký một protocol mới.

## 7. Finalist trên toàn development pool

Pool đầy đủ có 5.591.836 dòng và 1.625 conversion ở nhánh control.

| Seed | Delta Sentinel - Response | Paired 95% CI | `P(delta>0)` |
|---:|---:|---:|---:|
| 101, 200 bootstrap | +1,213e-6 | `[-2,323e-6; 4,377e-6]` | 0,74 |
| 202, 100 bootstrap | -2,075e-6 | `[-6,186e-6; 1,267e-6]` | 0,09 |

Không CI nào loại được 0, và dấu của chênh lệch không ổn định giữa hai seed.
`Response-Sentinel` vì vậy không qua gate ổn định ở mức full, và không finalist nào đủ điều
kiện đi tiếp sang randomized confirmation.

## 8. Kết quả của từng giả thuyết

| Vấn đề | Can thiệp | Kết quả | Điều rút ra |
|---|---|---|---|
| Sai thang giữa likelihood nhị phân và estimand | DINA học trên log-odds rồi đổi về CATE tuyệt đối | đổi dấu theo seed, trung bình thấp hơn Response | đúng thang chưa đủ; còn phải co và hiệu chuẩn hiệu ứng để kiểm soát phương sai |
| Prognostic dominance | Anchored R25 | thua ở cả hai seed theo diện tích | risk anchor không bảo toàn thứ hạng khi phần dư linh hoạt bị nhiễu ở dải budget rộng |
| Phương sai của phần dư tương tác | Thêm cờ sentinel cho Anchored R | tốt hơn R25 ở seed 101 nhưng vẫn thua Response | biểu diễn dữ liệu giúp được một phần, không khắc phục được phương sai của phần dư nhân quả |
| Moderator sentinel thưa | Gộp một phần theo pattern | thắng seed 202, thua seed 101 | moderator thô có tín hiệu thật nhưng nhạy với cách chia fold |
| Point mass phát hiện trong EDA | Response-Sentinel | qua sàng lọc, trượt gate ổn định ở mức full | hiệu ứng rất nhỏ; thắng point estimate ở sàng lọc không phải bằng chứng để promote |

## 9. Quyết định và backlog

Quyết định máy đọc được nằm ở
`output/improvement/causal_foundation_analysis/analysis_summary.json`: giữ Response, không
causal candidate nào đi tiếp, không finalist nào đi tiếp.

Vòng này chưa chạy Kaggle lại cho Causal Forest; hạng mục đó nằm trong backlog.

Thứ tự ưu tiên cho protocol kế tiếp, kèm bằng chứng số cho những hướng đã đóng:
[`../planning/README.md`](../planning/README.md).

## 9bis. Giới hạn

- **Chỉ là bằng chứng development, không phải confirmation.** Vòng này cố ý không đọc
  confirmation Sprint 2 và không có dữ liệu randomized mới, nên không thể hoàn tất promotion
  cho bất kỳ candidate nào — kể cả nếu một candidate đã qua mọi gate.
- **244 conversion ở nhánh control là chế độ phương sai cao.** Con số đó vượt ngưỡng 200 đã
  đăng ký cho bước sàng lọc, nhưng vừa đủ vượt; nó không đủ để biến một chênh lệch bậc `1e-6`
  thành kết luận.
- **Hai fold seed không phải hai lần lặp độc lập.** Chúng chia fold khác nhau trên **cùng**
  một tập source row, nên chúng đo tính bất ổn khi huấn luyện, không đo biến thiên giữa hai
  mẫu độc lập.
- **Seed 202 ở mức full chỉ có 100 bootstrap draw.** Khoảng tin cậy của nó dùng để kiểm dấu,
  không phải khoảng tin cậy chính.
- **Quan sát ở budget 1–2% là hậu nghiệm.** Nó nảy ra sau khi metric chính trên dải 1–30% đã
  không cho challenger nào thắng, nên phải coi là giả thuyết mang sang vòng sau chứ không phải
  kết quả của vòng này.
- **Feature đã được ẩn danh**, nên không diễn giải được moderator sentinel theo ngôn ngữ kinh
  doanh; báo cáo chỉ mô tả chúng như cấu trúc thống kê.
- **Một cấu hình cho mỗi giả thuyết.** DINA, Anchored R và Pattern R mỗi loại chỉ chạy ở một
  điểm cấu hình đã đăng ký trước; kết quả nói về điểm đó, không nói về cả họ phương pháp.

## 10. Artifact và kiểm thử cuối

Nguồn số:

- `output/improvement/causal_foundation_comparison/` — aggregate, gate và paired CI của bước
  sàng lọc;
- `output/improvement/causal_foundation_finalist_comparison/` — aggregate ở mức full và CI của
  seed 101;
- `output/improvement/causal_foundation_finalist_seed202_comparison/` — CI của seed 202;
- `output/improvement/causal_foundation_analysis/` — bảng giả thuyết, delta theo budget và
  quyết định dạng JSON;
- các thư mục `*_attempt*` — dấu vết kiểm toán cho những lần dừng vì tài nguyên, không dùng để
  xếp hạng.

Lệnh tái lập đầy đủ, gồm cả bước ghép các run chạy tách tiến trình:
[`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 6. Bước phân tích không fit model và
không đọc confirmation. Chi tiết lý thuyết và hiện thực nằm ở
[method guide](../docs/methods/06_RARE_OUTCOME_LEARNERS.md).

Kiểm thử cuối:

- `pytest`: **212/212 pass**;
- acceptance trình duyệt cho web app: **23/23 pass**;
- acceptance trình duyệt cho dashboard: **12/12 pass**;
- registry: 97 identity, 0 bản trùng sau khi sửa cách chuẩn hóa `101` và `101.0`.

Cảnh báo còn lại đến từ deprecation của dependency và phát hiện số nhân vật lý; không có test
nào fail. Các bộ test có mục tiêu không thay thế được lần chạy regression toàn repo.
