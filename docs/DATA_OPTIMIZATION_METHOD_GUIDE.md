# Data optimization — biểu diễn sentinel và funnel S-learner

- **Hiện thực:** [`../src/candidates.py`](../src/candidates.py) —
  `SentinelFeatureAugmenter` và `build_funnel_s_learner`
- **Protocol:** [`../configs/data_optimization_protocol_v1.json`](../configs/data_optimization_protocol_v1.json)
- **Kết quả:** [`../report/DATA_OPTIMIZATION_REPORT.md`](../report/DATA_OPTIMIZATION_REPORT.md)

Bốn vòng trước đều can thiệp vào **model**. Vòng này can thiệp vào **dữ liệu đưa vào
model** — và đó là lý do nó tồn tại như một vòng riêng thay vì một tinh chỉnh.

Giả thuyết đăng ký trước: *hai failure mode mà bước chẩn đoán dữ liệu phát hiện có thể sửa
được ở tầng biểu diễn, không cần đổi estimator.*

## 1. Xử lý dữ liệu là một can thiệp, không phải bước chuẩn bị

Nguyên tắc chi phối cả vòng này, và nên áp cho mọi vòng sau:

> **Mọi phép biến đổi dữ liệu làm đổi kết quả đều là một can thiệp và phải qua gate.**
> Chỉ những phép **không** đổi kết quả — ép kiểu, đối chiếu checksum, đổi dtype để tiết
> kiệm RAM — mới thuộc về bước chuẩn bị.

Nếu coi sentinel augmentation là "làm sạch dữ liệu", nó sẽ được áp âm thầm cho mọi model
và không ai đo được nó có tác dụng không. Coi nó là **giả thuyết** thì nó chạy qua đúng bộ
gate như một model mới, và cho ra một câu trả lời dùng được.

## 2. Failure mode thứ nhất — point mass bị đọc như giá trị thật

Bước chẩn đoán đo được: **sáu trên mười hai đặc trưng có hơn 90% khối lượng dồn vào đúng
một giá trị**, và **bốn cặp đặc trưng có mask "nằm ở sentinel" trùng khít tuyệt đối** trên
gần 14 triệu dòng.

Trùng khít tuyệt đối là bằng chứng mạnh hơn tương quan cao: hai biến độc lập thật sự không
cư xử như vậy. Nó nói rằng cả hai cột được điền bởi **cùng một cơ chế** ở tầng thu thập.

Với model dạng cây, một point mass chiếm 90% khối lượng gây ra vấn đề cụ thể: cây không
cắt được bên trong khối đó, nên toàn bộ 90% rơi vào cùng một nhánh và đặc trưng đó gần như
mất tác dụng phân biệt. Thông tin thật — *"dòng này thiếu đặc trưng đó"* — không được nói
ra ở đâu cả.

### Cách can thiệp

`SentinelFeatureAugmenter` thêm một **cột cờ nhị phân** cho mỗi đặc trưng có point mass
vượt ngưỡng:

```text
sentinel_flag_j = 1  neu  x_j == mode_j
                  0  neu khac
```

Ba ràng buộc trong hiện thực, mỗi cái chặn một cách hỏng:

| Ràng buộc | Chặn điều gì |
|---|---|
| Fit **chỉ từ `X` của fold train** — không đọc treatment, không đọc outcome | rò rỉ nhãn vào bước biến đổi |
| `min_mode_share = 0,05` | tạo cờ cho mọi giá trị, làm nở chiều vô ích |
| Lấy mẫu `200.000` dòng để tìm mode | sort hàng triệu giá trị cho **mỗi** candidate |

**Vì sao tên là `sentinel` chứ không phải `missing`.** Criteo **không** xác nhận đây là giá
trị thiếu. Bằng chứng chỉ nói có cấu trúc point mass dùng chung cơ chế. Tên và API cố ý
giữ ở mức mô tả được quan sát, không suy diễn nguyên nhân.

## 3. Failure mode thứ hai — outcome hiếm làm mất tín hiệu trung gian

`conversion` chỉ có `0,2917%`. Nhưng bước chẩn đoán còn đo được một quan hệ chính xác:

```text
P(conversion = 1 | visit = 0) = 0        dung bang 0
```

`visit` là **điều kiện cần** của `conversion`, và `visit` xảy ra với tỷ lệ khoảng `4,7%` —
gấp **16 lần**. Có một tín hiệu mạnh hơn nằm trên đúng đường đi tới outcome, nhưng
`visit` **bị cấm làm feature** vì nó là biến hậu can thiệp.

### Cách can thiệp: phân rã, không phải thêm feature

Funnel S-learner dùng quy tắc nhân xác suất, áp riêng cho từng nhánh treatment:

```text
P(conversion=1 | X,T) = P(visit=1 | X,T) x P(conversion=1 | visit=1, X,T)
```

Hai classifier S-style:

| Model | Học trên | Học cái gì |
|---|---|---|
| Thứ nhất | **mọi** dòng | `visit` |
| Thứ hai | chỉ dòng đã `visit = 1` | `conversion` |

Điểm mấu chốt: **`visit` chỉ là auxiliary training outcome và sample mask** — nó không bao
giờ vào ma trận feature, và không có trong API `predict`. Nên score vẫn chỉ dùng `X` tiền
treatment, đúng luật, trong khi mô hình vẫn học được toàn bộ đường
`treatment → visit → conversion`.

Đây **không phải** mediator adjustment. Không có bước chặn hay điều chỉnh trung gian; hai
xác suất được nhân lại để khôi phục đúng đại lượng ban đầu.

### Chốt chặn được cưỡng chế

`build_funnel_s_learner` từ chối chạy nếu:

- `outcome_name != "conversion"` — công thức chỉ đúng cho outcome này;
- không có auxiliary outcome `visit`;
- dữ liệu vi phạm bất biến `conversion <= visit` — nếu tồn tại một dòng mua mà không ghé
  thăm thì phép phân rã sai ngay từ tiền đề.

Điều kiện thứ ba đáng chú ý: nó kiểm **tiền đề của công thức trên chính dữ liệu** thay vì
tin vào tài liệu. Test tương ứng:
`test_funnel_s_learner_rejects_post_treatment_invariant_violation`.

## 4. Bảy candidate — thiết kế ablation

Protocol đăng ký bảy candidate, và cách ghép chúng cho phép **tách riêng tác dụng của
sentinel**:

| Candidate | Họ | Có sentinel |
|---|---|:-:|
| `Response` | response | — |
| `Response-Sentinel` | response | **có** |
| `S-Under7` | s_learner | — |
| `S-Sentinel-Under7` | s_learner | **có** |
| `X-Renormalized` | x_learner | — |
| `Funnel-S` | funnel_s_learner | — |
| `Funnel-S-Sentinel` | funnel_s_learner | **có** |

Ba cặp có/không sentinel trên cùng một họ model. Đây là ablation đúng nghĩa: chênh lệch
trong mỗi cặp quy được cho **một** thay đổi.

## 5. Kết quả, và vì sao nó không đủ để promote

Chi tiết số ở báo cáo. Điều cần biết về **phương pháp**:

`Response-Sentinel` thắng point estimate ở **cả hai** fold seed tại bước sàng lọc — đủ để
qua gate điểm số. Nhưng khi chạy trên toàn development pool, nó **đổi dấu** giữa hai seed:

```text
Screen 15%  seed 101   +2,052e-6
Screen 15%  seed 202   +3,035e-6
Full        seed 101   +1,213e-6
Full        seed 202   -2,075e-6      ← doi dau
```

Trung bình ở mức full là `-4,310e-7`. Gate ổn định thất bại.

**Đây là lý do promotion rule đòi thắng ở *từng* seed thay vì thắng theo trung bình.** Lấy
trung bình bốn con số trên sẽ ra một số dương nhỏ và che mất việc dấu không ổn định.

Funnel S-learner cho `policy_area_dr` thấp hơn Response khoảng `5,4–5,9%`. Phân rã hợp lệ
về mặt xác suất, nhưng nhân hai ước lượng nhân hai nguồn sai số — và với `conversion` hiếm,
model thứ hai chỉ học trên `4,7%` số dòng.

## 6. Điều vòng này đóng lại

Giả thuyết *"biểu diễn dữ liệu là nút thắt"* bị bác. Cả hai can thiệp đều hợp lệ về mặt kỹ
thuật, cả hai đều không vượt được Response.

Kết hợp với vòng trước đó (thuật toán chuyên dụng) và vòng sau (estimator sai thang), ba
hướng sửa **độc lập** đều đóng — và đó là điều cho phép phát biểu mạnh hơn: ràng buộc nằm ở
**phép đo**, không ở model. Mạch đầy đủ:
[`END_TO_END_WORKFLOW.md`](END_TO_END_WORKFLOW.md) mục 3.3.

## 7. Chạy lại

[`REPRODUCTION.md`](REPRODUCTION.md) mục 5.
