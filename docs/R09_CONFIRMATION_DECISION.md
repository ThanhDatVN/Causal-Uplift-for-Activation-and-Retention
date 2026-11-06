# R09 — quyết định **không** mở split confirmation

Ngày: 21/09/2026. Người quyết định: agent phát triển. Trạng thái: **KHÔNG MỞ**, có chủ đích, không phải "chưa kịp làm".

Split confirmation của Hillstrom (20% dữ liệu, `SPLIT_SALT = "hillstrom-v4.1"`) **chưa từng được đọc một lần nào**. Manifest hiện tại ghi `confirmation_outcomes_read: false`. Tài liệu này ghi lại lý do giữ nguyên như vậy.

## Runbook đòi gì trước khi mở

> *"Trước mở confirmation phải ký manifest: dataset hash/IDs, target sign/horizon, **model recipes/settings**, preprocessing, policy/capacity/cost, evaluator, primary contrast, margin, CI method, secondary multiplicity và stop rules."*

Điều kiện gạch chân là chỗ hỏng. Không có **recipe nào đáng ký**.

## Bốn lý do, mỗi lý do đủ để hoãn

### 1. Không có cấu hình nào ổn định để đóng băng (R03)

R03 chạy 3 family × 8 cấu hình × 3 outer × 3 inner. **Không family nào** chọn được cùng một cấu hình qua ba fold:

| family | chọn theo từng fold | biên độ |
|---|---|---|
| M01 | `C=1,0`; `C=1,0`; `C=0,01` | 100 lần |
| M03 | `C=0,03`; `C=3,0`; `C=0,03` | 100 lần |
| M07 | `α=0,1`; `α=100`; `α=0,1` | 1.000 lần |

Ký một manifest đòi hỏi viết ra **một** con số. Dữ liệu development không cung cấp được nó. Chọn đại một trong ba rồi ký là biến một lần bắn duy nhất thành một lần tung đồng xu.

### 2. Người thắng không lặp lại sang nhánh còn lại của chính dataset đó (S35)

| | Mens E-Mail | Womens E-Mail |
|---|---|---|
| Ai thắng | **M01** thắng cả tám | **M03**, +0,001412 so M01 |
| M01 xếp | nhất | gần bét |
| Learning curve của M03 | không có | **đơn điệu tăng** |
| final_stage ridge→hgb | +0,000349 (1,4 se) | **−0,000492 (3,3 se)** |

Cùng dataset, cùng khách hàng, cùng thời kỳ, cùng giao thức, cùng cỡ mẫu — **hai người thắng khác nhau**. Confirmation trên nhánh Mens sẽ xác nhận một kết luận mà nhánh Womens đã bác bỏ, và ngược lại.

### 3. Evaluator mới chỉ đạt qua một biến thể chọn hậu nghiệm (S27)

Cổng coverage đạt ở 2.000 world, nhưng chỉ với `--effective-df-floor 1`, và biến thể ấy được chọn **sau khi** thấy nó là biến thể đạt. Bản `validity_confirm` cùng phương pháp, cùng power, vẫn FAIL. Cổng tự in cảnh báo này vào mọi artifact:

> `SELECTED AFTER LOOKING: 1 other run(s) at the same 2000 worlds disagree ... needs independent confirmation`

Đo một kết quả confirmatory bằng một cây thước chưa được xác nhận độc lập là tiêu ngân sách bằng chứng cho một con số không diễn giải được.

### 4. Không có thành phần nào tạo ra khác biệt đo được (R04, R05)

R04: không yếu tố nào trong biểu diễn / tầng cuối / allocator lay chuyển kết quả trên nhánh Mens. R05: gấp 4 lần dữ liệu huấn luyện không cải thiện gì. Nghĩa là **chưa có giả thuyết cụ thể nào để xác nhận** — chỉ có một bảng xếp hạng mà ta vừa biết là không bền.

## Vì sao "cứ mở đi rồi biết" là sai

Split confirmation dùng được **một lần**. Mở nó ra sẽ:

- tiêu ngân sách bằng chứng lớn nhất còn lại của dự án,
- cho một con số mà, dù ra sao, cũng **không giải thích được**: nếu M01 thắng thì nó xác nhận nhánh Mens hay chỉ trùng hợp? nếu M03 thắng thì R02 sai ở đâu?
- và không thể làm lại. Không có cách nào "đóng" nó lại.

Một thí nghiệm confirmatory trả lời một câu hỏi đã phát biểu trước. Hiện tại câu hỏi ấy chưa phát biểu được.

## Điều kiện để mở

Cả bốn, không phải ba:

1. **Một recipe ổn định.** Cùng một cấu hình được chọn ở đa số fold, hoặc một quy tắc chọn đã khai báo (ví dụ "luôn dùng `C=0,3`") được biện minh **trước** khi nhìn.
2. **Người thắng lặp lại.** Cùng một family thắng trên cả Mens và Womens, hoặc trên ≥2 dataset độc lập dưới cùng giao thức (R10).
3. **Evaluator được xác nhận độc lập.** Một lần chạy R01 trên seed chưa dùng với recipe khoá **trước**, không phải biến thể chọn sau khi nhìn.
4. **Manifest ký đủ** theo runbook §R09, gồm margin và stop rule, đóng băng trước khi mở.

## Thứ tự làm tiếp

R10 (miền độc lập) đứng trước R09. Nếu người thắng không lặp lại qua miền thì confirmation không có gì để xác nhận; nếu có thì manifest tự viết ra được.

Không có gì trong tài liệu này ngăn việc mở confirmation về sau. Nó chỉ ghi rằng mở **hôm nay** sẽ tiêu một lần bắn duy nhất vào một câu hỏi chưa hỏi được.
