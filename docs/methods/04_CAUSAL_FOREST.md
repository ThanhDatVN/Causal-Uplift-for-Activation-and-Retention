# Causal Forest — phương pháp, cấu hình và ràng buộc của outcome hiếm

- **Vòng sinh ra tài liệu:** hai vòng Causal Forest — vòng 4 và vòng 8
- **Protocol vòng thứ hai:** [`../../configs/causal_forest_rare_outcome_protocol_v1.json`](../../configs/causal_forest_rare_outcome_protocol_v1.json)
- **Hiện thực:** [`../../scripts/train_causal_forest.py`](../../scripts/train_causal_forest.py),
  `CausalForestDML` của EconML 0.16
- **Kết quả:** [`../../report/04_CAUSAL_FOREST.md`](../../report/04_CAUSAL_FOREST.md) và
  [`../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md`](../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md)
- **Đọc trước:** [`03_EVALUATION_PROTOCOL.md`](03_EVALUATION_PROTOCOL.md) —
  **đọc tiếp:** [`05_DATA_REPRESENTATION.md`](05_DATA_REPRESENTATION.md)

Bốn meta-learner ở [`01_UPLIFT_FOUNDATIONS.md`](01_UPLIFT_FOUNDATIONS.md)
đều **ghép các model thông thường lại**: fit outcome model rồi lấy hiệu, hoặc fit trên
pseudo-outcome. Causal Forest là thuật toán chuyên dụng duy nhất trong dự án — nó sửa
thẳng **tiêu chí chia nhánh của cây**.

Chính cơ chế này xung đột với outcome hiếm, theo số học trình bày ở mục 2.

## 1. Khác biệt cốt lõi: chia nhánh theo cái gì

Một cây hồi quy thông thường chia nhánh để **giảm sai số dự đoán** của `Y`. Nó tìm điểm
cắt làm hai nhánh con thuần nhất nhất về giá trị outcome.

Causal Forest chia nhánh để **tối đa hoá chênh lệch hiệu ứng** giữa hai nhánh con. Nó
không quan tâm dự đoán `Y` chính xác; nó quan tâm tìm ra chỗ mà `τ(x)` khác nhau.

Hệ quả trực tiếp: một cây thông thường có thể rất chính xác mà hoàn toàn vô dụng cho
targeting — nó sẽ tách nhóm *hay mua* khỏi nhóm *ít mua*, chứ không tách nhóm *bị thuyết
phục* khỏi nhóm *chắc chắn mua*. Đây là dạng cụ thể của vấn đề trung tâm cả dự án.

## 2. Honest splitting, và cái giá của nó

Causal Forest dùng **honest splitting**: dữ liệu trong mỗi cây bị chia đôi.

| Nửa | Dùng để |
|---|---|
| Nửa thứ nhất | quyết định **chia ở đâu** |
| Nửa thứ hai | ước lượng **hiệu ứng trong từng lá** |

Vì sao cần: nếu dùng cùng dữ liệu cho cả hai việc, cây sẽ tìm ra những điểm cắt trông như
có hiệu ứng lớn chỉ vì nhiễu, rồi ước lượng hiệu ứng trên chính nhiễu đó. Honest splitting
làm ước lượng trong lá không thiên lệch.

**Cái giá:** mỗi lá chỉ còn **một nửa** số quan sát để ước lượng. Với outcome hiếm, đây
không phải chi tiết nhỏ — nó là ràng buộc bó chặt nhất, và mục 3 định lượng nó.

## 3. Số học quyết định mọi thứ: bao nhiêu sự kiện trong một lá

Đây là phép tính nên làm **trước** khi chọn cấu hình, không phải sau khi thấy kết quả xấu.

Criteo có treatment `85/15` và tỷ lệ conversion ở nhánh control `0,1938%`. Một lá có
`min_samples_leaf` quan sát thì kỳ vọng số **sự kiện control** trong lá là:

```text
su_kien_control_moi_la = min_samples_leaf × 0,15 × 0,001938
```

Áp vào ba profile trong `train_causal_forest.py`:

| `--profile` | `min_samples_leaf` | Sự kiện control / lá | Sau honest splitting |
|---|---:|---:|---:|
| `research` | 200 | `0,058` | `0,029` |
| `kaggle-safe` | 500 | `0,145` | `0,073` |
| `rare-outcome` | 10.000 | `2,907` | `1,454` |

Với `kaggle-safe`, kỳ vọng chỉ `0,073` sự kiện control mỗi lá sau honest splitting —
**đại đa số lá có nhánh control rỗng**, và hiệu `treated - control` được lấy với một vế
gần như không có thông tin.

Với `research` còn tệ hơn — `0,029`. Đó là lý do profile `research` **không** phải bản cải
tiến cho bài toán này dù tên nghe như vậy: nó nặng hơn về tài nguyên và đi **sai hướng**
trên đúng ràng buộc đang bó.

`rare-outcome` nâng lên `1,454`. Vẫn ít, nhưng khác về bản chất: lá điển hình bắt đầu có
sự kiện để so.

## 4. Ba profile — tham số đầy đủ

Khai báo trong `scripts/train_causal_forest.py`, hằng số `PROFILES`:

| Tham số | `kaggle-safe` | `research` | `rare-outcome` |
|---|---:|---:|---:|
| `n_estimators` | 200 | 500 | 500 |
| `min_samples_leaf` | 500 | 200 | **10.000** |
| `cv` | 2 | 3 | 3 |
| `max_samples` | 0,25 | 0,45 | 0,45 |
| `inference` | `False` | `True` | `False` |

**`cv`** là số fold cross-fitting cho nuisance bên trong DML. `CausalForestDML` fit hai
model phụ — outcome và treatment — rồi làm việc trên phần dư. Cross-fitting ở đây phục vụ
cùng mục đích như ở các vòng meta-learner: mỗi dòng chỉ được dùng phần dư từ model không
fit trên nó.

**`max_samples`** là tỷ lệ mẫu mỗi cây được thấy — cơ chế subsampling của forest.

**`inference=False`** tắt phần ước lượng phương sai của EconML. Hệ quả quan trọng:
`effect_interval()` **không gọi được**, nên **không có khoảng tin cậy cho từng cá nhân**.
Mọi CI trong hai báo cáo Causal Forest là CI của **metric**, thu bằng bootstrap trên tập
đánh giá — không phải CI của hiệu ứng trên từng khách hàng.

Bật `inference=True` tốn thêm rất nhiều RAM, và ở quy mô `5,59` triệu dòng thì vượt ngân
sách tài nguyên đã đăng ký.

## 5. Hai split, và vì sao không so chung bảng được

`--split` chọn dữ liệu fit và dữ liệu chấm:

| `--split` | Fit trên | Predict trên | So được với |
|---|---|---|---|
| `sprint1` | train của sample Sprint 1 | final test `2.096.940` dòng | bảng release năm model |
| `sprint3` | development Sprint 2/3, `5.591.836` dòng | confirmation `1.397.959` dòng | bảng confirmation Sprint 3 |

**Không** đặt kết quả hai split cạnh nhau. Chúng khác tập đánh giá, và ở vòng đầu còn khác
cả tín hiệu chấm điểm — mục 6.

## 6. Tín hiệu chấm điểm đổi kết quả nhiều hơn model

Phát hiện của vòng `rare-outcome` nằm ở **cách đo**, không ở Causal Forest.

Vòng đầu chấm bằng **IPW signal**; vòng `rare-outcome` chấm lại bằng **DR signal đã đóng
băng**. Cùng bộ điểm, cùng những dòng dữ liệu, chỉ đổi tín hiệu:

- chênh lệch đo được giữa Causal Forest và Response **đổi 69 lần**;
- Response tụt từ hạng 2 xuống hạng 4 trên sáu model;
- trong khi **mọi paired CI trong nhóm đầu vẫn chứa 0**.

Bài học vận hành, áp cho mọi so sánh chứ không riêng Causal Forest: **cố định và ghi rõ
tín hiệu chấm điểm trước khi so sánh bất cứ thứ gì**, ngang hàng với việc cố định metric.
Chi tiết số: [`../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md`](../../report/08_CAUSAL_FOREST_RARE_OUTCOME.md) mục 5.

## 7. Kiểm bắt buộc trước khi tin một lần chạy

Cấu hình ở mục 3 hoàn toàn có thể sinh ra **điểm gần như hằng số** — mọi lá cho cùng một
ước lượng vì không lá nào có đủ thông tin. Khi đó model vẫn chạy, vẫn xuất file, và mọi
metric vẫn ra số.

Nên kiểm suy biến là bước bắt buộc, không phải tuỳ chọn:

```text
so_gia_tri_phan_biet >= 10        ← nguong da dang ky o Sprint 3
```

Ở mốc `50%`, Causal Forest cho `912.579` giá trị phân biệt trên `2.096.940` dòng — cách
ngưỡng năm bậc độ lớn. Model không suy biến.

Kiểm thứ hai: trung bình điểm phải gần ATE quan sát. Thực tế `0,000980` so với ATE
`0,001152` — mức hiệu chuẩn tổng thể hợp lý.

## 8. Ràng buộc tài nguyên

Fit chạy trên Kaggle vì RAM local không đủ cho development pool `5.591.836` dòng.
`scripts/kaggle_causal_forest_gate.py` bọc lần chạy bằng một gate tài nguyên; nó **không**
đánh giá chất lượng, chỉ kiểm toàn vẹn artifact và trần RAM.

Ba mốc dữ liệu đã đo:

| Mốc | Train | Peak RSS | RAM | Fit |
|---|---:|---:|---:|---:|
| 20% | 1.957.143 | 5,52 GB | 17,6% | 8,5 phút |
| 30% | 2.935.713 | 7,88 GB | 25,1% | 13,9 phút |
| 50% | 4.892.857 | 12,73 GB | 40,6% | 25,0 phút |

Tài nguyên tăng gần tuyến tính theo dữ liệu (`RSS ×2,3`, thời gian `×2,9` khi đi từ 20%
lên 50%) mà **không** có bước nhảy nào về chất lượng xếp hạng. Đó là dấu hiệu của trần
thông tin do outcome hiếm, không phải của thiếu dữ liệu.

Ở vòng `rare-outcome`, gate **fail** vì RAM đỉnh chạm `90,8%` (28,46 GB trên 31,35 GB) so với ngưỡng `75%` — nhưng
điểm số vẫn hợp lệ vì artifact đã ghi xong trước khi gate được đánh giá. Lần fail đó được
ghi lại thay vì bỏ qua; xem cell cuối của
[`../../notebooks/04_causal_forest_rare_outcome.ipynb`](../../notebooks/04_causal_forest_rare_outcome.ipynb).

## 9. Điều phương pháp này **không** cho biết

- **Không có khoảng tin cậy cá nhân** với hai profile đang dùng (`inference=False`).
- **Không có ablation.** Bốn meta-learner được chọn cấu hình qua validation; Causal Forest
  chạy đúng hai điểm cấu hình đã đăng ký trước. Bảng sáu model vì thế là so sánh **không
  cân bằng** về công sức tinh chỉnh — điều này được ghi trong báo cáo.
- **Không kết luận về cấu hình khác.** Muốn thử tham số khác thì đăng ký trước và chạy như
  một run mới, không tinh chỉnh sau khi nhìn kết quả.

## 10. Chạy lại

Lệnh đầy đủ: [`REPRODUCTION.md`](../REPRODUCTION.md) mục 8 và 8bis.

Notebook của hai lần chạy Kaggle:
[`03_causal_forest.ipynb`](../../notebooks/03_causal_forest.ipynb) và
[`04_causal_forest_rare_outcome.ipynb`](../../notebooks/04_causal_forest_rare_outcome.ipynb).
