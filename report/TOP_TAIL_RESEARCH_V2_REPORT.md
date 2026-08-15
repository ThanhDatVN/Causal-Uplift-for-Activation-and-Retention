# Báo cáo top-tail research v2

- **Ngày:** 09/08/2026
- **Protocol:** [`top_tail_research_protocol_v2.json`](../configs/top_tail_research_protocol_v2.json)
- **Nguồn số:** `output/improvement/top_tail_research_v2/`
- **Cơ sở nghiên cứu:** [`LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md`](../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)
- **Hướng dẫn suy luận:** [`TOP_TAIL_POLICY_INFERENCE_GUIDE.md`](../docs/TOP_TAIL_POLICY_INFERENCE_GUIDE.md)

## 1. Quyết định

Giữ champion **Response**. Không causal candidate nào được promote.

Cả 16 chênh lệch point estimate của nhóm causal tại budget 1% và 2% đều dương, nhưng không một
cận dưới 95% pointwise nào và không một cận dưới 95% simultaneous nào vượt quá 0. Dấu của
point estimate là một giả thuyết đáng mang sang dữ liệu randomized mới, không phải bằng chứng
về tính vượt trội trên dữ liệu hiện có.

Quyết định máy đọc được:

```text
decision = retain_response_and_carry_hypothesis_to_new_preregistered_data
promotion_allowed = false
```

## 2. Phạm vi của lần kiểm

Lần kiểm này chỉ đọc hai artifact OOF đã đóng băng:

- `causal_foundation_screen_seed101`;
- `causal_foundation_screen_seed202`.

Cả hai dùng đúng **838.776 source row**, với SHA-256 của tập dân số là
`2f9a75e0b5572f108993310af120552d129982dc2d4d2016ee2ed0f7a020806a`. Hai seed chỉ đổi cách chia
fold trên cùng những dòng đó; chúng **không** phải hai mẫu độc lập và càng không phải hai RCT
độc lập.

Số người được chọn tại mỗi mức budget, cắt cứng:

| Budget | Số người chính xác |
|---:|---:|
| 1% | 8.387 |
| 2% | 16.775 |

Họ giả thuyết được đóng băng trước gồm Response và năm challenger, cho ra:

```text
5 challenger × 2 fold seed × 2 budget = 20 ô.
```

Bootstrap ghép cặp dùng 200 lần rút, và mọi model, mọi seed, mọi mức budget đều dùng chung một
bộ trọng số dòng để giữ đúng tính ghép cặp. Giá trị tới hạn theo lối chuẩn hóa cực đại là
**3,111821**. Khoảng tin cậy ở đây có phạm vi `conditional_on_fixed_oof_scores`: nó đo bất định
của mẫu đánh giá với bộ điểm đã cố định, và **không** bao gồm bất định do huấn luyện lại model.

## 3. Kết quả thống kê

Trong 20 ô có 16 ô thuộc bốn causal candidate:

| Kiểm tra | Kết quả |
|---|---:|
| Causal point delta > 0 | 16/16 |
| Pointwise 95% lower bound > 0 | 0/16 |
| Simultaneous 95% lower bound > 0 | 0/16 |
| Khoảng causal point delta | `+1,964e-6` đến `+8,166e-5` |

Hai ví dụ đại diện:

| Seed | Candidate | Budget | Delta vs Response | Pointwise 95% CI | Simultaneous 95% CI |
|---:|---|---:|---:|---:|---:|
| 101 | Anchored-R25 | 1% | `+2,938e-5` | `[-5,070e-5; +1,072e-4]` | `[-9,491e-5; +1,537e-4]` |
| 202 | DINA-CATE-Sentinel | 2% | `+5,518e-5` | `[-7,952e-5; +1,761e-4]` | `[-1,533e-4; +2,637e-4]` |

Không được đọc `16/16` như 16 lần lặp lại độc lập. Ba lý do, mỗi lý do đủ để bác cách đọc đó:
các chênh lệch được tính trên **cùng** những dòng dữ liệu thực tế; chúng dùng chung một bộ
nuisance; và mức budget 1–2% chỉ được chú ý **sau** khi thí nghiệm chính trên toàn dải đã được
đọc.

## 4. Độ ổn định của tập người được chọn

Overlap là tỷ lệ thành viên chung trong đúng nhóm top-k cắt cứng, giữa fold seed 101 và 202:

| Model | Overlap 1% | Overlap 2% | Gate tương lai |
|---|---:|---:|---:|
| Response | 80,52% | 80,76% | pass 75% |
| DINA-CATE-Sentinel | 61,31% | 65,47% | fail 75% |

Overlap thấp nhất của cả họ causal là **61,31%**. Con số đó cho thấy giá trị policy có thể giữ
nguyên dấu trong khi **danh sách người được chọn đổi đi đáng kể**, dù chỉ thay cách chia fold
bên ngoài. Bất ổn khi huấn luyện vì vậy phải được coi là một kiểu thất bại riêng, không được
che đi bằng cách lấy trung bình qua các seed.

## 5. Số sự kiện trong phần đuôi

| Seed | Model | Budget | Control events | Treated events | Support gate 100 control events |
|---:|---|---:|---:|---:|---:|
| 101 | Response | 1% | 141 | 1.122 | pass |
| 202 | Response | 1% | 137 | 1.117 | pass |
| 101 | Response | 2% | 169 | 1.409 | pass |
| 202 | Response | 2% | 167 | 1.419 | pass |
| 101 | DINA-CATE-Sentinel | 1% | 84 | 834 | fail |
| 202 | DINA-CATE-Sentinel | 1% | 91 | 857 | fail |
| 101 | DINA-CATE-Sentinel | 2% | 109 | 1.104 | pass |
| 202 | DINA-CATE-Sentinel | 2% | 110 | 1.126 | pass |

Số sự kiện control ít nhất trong phần đuôi của nhóm causal là **84**. Ở mọi ví dụ trên, số điểm
bằng nhau tại đúng ngưỡng cắt đều bằng 1, nên kết quả không bị một khối điểm trùng nhau chi
phối. Hai vấn đề thật sự là lượng thông tin ít ỏi của sự kiện hiếm, và tính bất ổn của danh
sách người được chọn.

## 6. Giới hạn — vì sao không dùng kết quả này để chọn model

1. Budget 1% và 2% là phát hiện hậu nghiệm, nảy ra sau khi diện tích chính trên dải 1–30%
   không cho challenger nào thắng.
2. Hai fold seed chạy trên cùng một tập source row, nên chúng không phải hai lần lặp độc lập.
3. Có nhiều tổ hợp challenger × budget × seed; khoảng tin cậy pointwise không kiểm soát được
   việc chọn lọc trong cả họ.
4. Bootstrap trên bộ điểm đã đóng băng không bao gồm bất định do huấn luyện lại model.
5. DINA không đạt gate ổn định và gate số sự kiện ở mức top 1%.
6. Confirmation Sprint 2 đã được đọc trong lịch sử dự án, nên nó không thể trở thành một
   holdout mới.

Cách kết luận phù hợp là *mang giả thuyết sang vòng sau*, không phải *causal model thắng
Response*.

## 7. Ràng buộc với vòng sau

Không model mới nào được thêm hồi tố vào họ 20 ô này; muốn kiểm định thêm thì phải đăng ký một
protocol mới.

Thứ tự thực thi đã khóa và trạng thái từng bước:
[`../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md`](../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)
mục 9.

## 8. Artifact và xuất xứ

Nguồn số chính thức:

- [`analysis_summary.json`](../output/improvement/top_tail_research_v2/analysis_summary.json);
- [`simultaneous_tail_differences.csv`](../output/improvement/top_tail_research_v2/simultaneous_tail_differences.csv);
- [`tail_event_support.csv`](../output/improvement/top_tail_research_v2/tail_event_support.csv);
- [`tail_membership_overlap.csv`](../output/improvement/top_tail_research_v2/tail_membership_overlap.csv).

File summary lưu SHA của protocol, SHA của manifest và NPZ đầu vào, seed bootstrap và trạng
thái code. Namespace chính thức không được ghi đè. Các thư mục `top_tail_research_v2_attempt*`
là dấu vết kiểm toán của những lần sinh artifact trước khi guard xuất xứ hoàn chỉnh; chúng
không phải nguồn số ưu tiên.

Lệnh tái lập: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 7. Khi artifact chính
thức đã tồn tại, lệnh phải từ chối ghi đè; muốn chạy phân tích độ nhạy thì phải dùng protocol
và namespace output mới.

## 9. Kiểm thử

Bộ test có mục tiêu cho hybrid, policy, protocol, dữ liệu sinh, artifact và xuất xứ:

```text
89 passed, 8 dependency/environment warnings.
```

Kiểm chứng đầy đủ sau khi hoàn tất code và tài liệu:

```text
pytest: 258 passed, 17 dependency/environment warnings
web app browser: 23/23 passed
dashboard browser: 12/12 passed
compileall: passed
git diff --check: passed (chỉ có line-ending warnings từ Git trên Windows)
```

Các cảnh báo còn lại đến từ SHAP, Starlette, scikit-learn, SciPy và bước phát hiện số nhân vật
lý; không có test nào fail. Bộ test có mục tiêu không thay thế được lần chạy đầy đủ.
