# Related work — và một sự đính chính về cách repo này đặt tên vấn đề

Ngày tra cứu: 21/09/2026. Tài liệu này lấp khoảng trống mà [RESEARCH_READINESS.md](archive/RESEARCH_READINESS.md) §3 gọi là "khoảng trống lớn nhất và rẻ nhất để lấp": trước khi viết một dòng nào về đóng góp, phải biết cái mình quan sát được đã có tên chưa.

Kết luận đi trước: **có, phần lớn đã có tên — nhưng repo này đang gọi sai tên.** Đó là phát hiện quan trọng nhất của bước tra cứu, và nó buộc phải sửa cách phát biểu ứng viên A.

## 1. Văn liệu nói gì

| Nguồn | Nói gì | Liên quan thế nào |
|---|---|---|
| Dorn (2025), *How Much Weak Overlap Can Doubly Robust T-Statistics Handle?* ([arXiv:2504.13273](https://arxiv.org/abs/2504.13273)) | Dưới overlap đủ yếu, **không tồn tại** estimator regular √n-consistent và estimator chuẩn có thể **không** tiệm cận chuẩn. Bản AIPW **có ngưỡng (thresholded)** thì tiệm cận chuẩn và khoảng Wald **hiệu chỉnh đúng**, kể cả khi nuisance ước lượng phi tham số. Mô phỏng: thresholded AIPW **over-reject vừa phải ở mẫu nhỏ**, không bác bỏ được coverage đúng ở mẫu lớn | Đây chính xác là câu hỏi ứng viên A định hỏi. Nó đã được trả lời, ở mức định lý |
| Ma, Sant'Anna, Sasaki & Ura (2026), *Doubly Robust Estimators with Weak Overlap* ([arXiv:2304.08974](https://arxiv.org/abs/2304.08974)) | Trọng số cực đoan làm SE phồng 2–6 lần hoặc đổi dấu điểm ước lượng. Với outcome model sai và trimming h=0,10, **coverage tụt còn 34%**. Đề xuất DR-BC: trim rồi bù lại phần bị trim bằng xấp xỉ đa thức | Cho thấy coverage collapse dưới overlap yếu là hiện tượng đã đo, ở mức nghiêm trọng hơn nhiều so với 0,929 của V05 |
| Khan & Tamer (2010), irregular identification | Khi `e(X)→0`, tốc độ hội tụ chậm hơn √n | Gốc lý thuyết của cả hai bài trên |
| Crump, Hotz, Imbens & Mitnik (2009), trimming | Đổi estimand sang vùng overlap thay vì sửa khoảng | Là "heuristic 10% fixed-trimming" mà Dorn so sánh |
| Anon. (2025), *Model-Agnostic Bounds for AIPW Estimators' Wald-CI Coverage in RCTs* ([arXiv:2512.18898](https://arxiv.org/abs/2512.18898)) | Chặn kiểu Berry–Esseen **phi tiệm cận** cho hiệu giữa coverage Wald và mức danh nghĩa; variance estimator cross-fit có xu hướng **ước lượng thừa**, bản không cross-fit **ước lượng thiếu** | Gần nhất với chế độ của repo: RCT, propensity biết trước. Đây là cái phải đọc kỹ trước khi phát biểu bất kỳ mệnh đề giải tích nào |

## 2. Sự đính chính: repo này **không** ở chế độ weak overlap

[STAGE_LOG.md](archive/STAGE_LOG.md) và [RESEARCH_READINESS.md](archive/RESEARCH_READINESS.md) đang nói nguyên nhân V05 mất coverage là "**lệch propensity**", và ngầm xếp nó vào văn liệu weak overlap. Đọc lại generator thì điều đó **không đúng**:

```python
design = pd.DataFrame(
    {HOLD: np.full(N_UNITS, 1.0 - propensity), CONTACT: np.full(N_UNITS, propensity)}
)
```

`e` là **hằng số** với mọi unit. Không có đuôi `e(X) → 0`. Ở cell xấu nhất (`e=0,95`) trọng số IPW bị chặn trên bởi 20; ở V05 (`e=0,9`) bị chặn bởi 10. Semiparametric bound **hữu hạn ở mọi nơi**. Theo đúng định nghĩa của Khan–Tamer, Dorn, và Ma và cộng sự thì overlap ở đây là **hoàn hảo**, chỉ là không cân bằng.

Hệ quả:

1. **Định lý của Dorn không áp dụng được để cứu V05.** Remedy của ông ấy là thresholding, mà ở đây không có gì để threshold: không unit nào có `e` gần 0.
2. **Ứng viên A không thể phát biểu là "DR hỏng dưới weak overlap".** Câu đó đã có người chứng minh, và dù sao thì nó cũng không mô tả cái repo này đo được.
3. Cái repo này đo được là một hiện tượng **hữu hạn mẫu** khác: score AIPW là hỗn hợp gần-0 với những gai hiếm độ lớn `1/(1-e)`, và số gai kỳ vọng ở nhánh nhỏ là `n·(1-e)·rate`. Ở V05 con số đó là `10.000 × 0,1 × 0,005 = 5`.

## 3. Mệnh đề giải tích — đã có sẵn, chỉ cần chuyên biệt hoá

Kế hoạch dự trù **8–16 giờ** để "phát biểu giải tích cho ngưỡng". Không cần: Qiu (2025) đã chứng minh nó cho **đúng** chế độ của repo này (RCT, propensity **biết trước**, AIPW, có/không cross-fit). Định lý 1 chặn

```
| P(coverage) − (1−α) − φ(z)·z·(σ† − σ#)/σ# |
        = O( K^{2/3}·{E‖Q̂−Q‖²}^{1/3} + {K·log n / n}^{1/2} )
```

Hai điều đọc ra được:

1. **Số hạng bậc nhất nằm ngoài dấu O** là `φ(z)·z·(σ† − σ#)/σ#` — sai số **tương đối của ước lượng phương sai**. Prop. 1: bản cross-fit có xu hướng **ước lượng thừa**, bản không cross-fit **ước lượng thiếu**. Đây là lời giải thích lý thuyết cho việc cross-fitting cải thiện coverage.
2. Với nuisance **đúng** (chính là V05 `dr_correct`), `E‖Q̂−Q‖² ≈ 0`, nên phần còn lại là số hạng Berry–Esseen cổ điển `ρ₃/(σ³√n)`.

### Một giả thuyết đã bị chính tôi bác bỏ, và ghi lại ở đây vì nó suýt vào docs

Bước rút gọn đầu tiên tôi làm chỉ đếm gai ở **nhánh đối chứng** (trọng số `1/(1−e)`), và cho

```
ρ₃/(σ³√n) = 1/√(N_eff),    N_eff = n·h·rate·(1−e)
```

Đo lại trên chính vector score của V05/V05B/V03/V01/V02 thì tỷ số `ρ₃/(σ³√n)·√N_eff` **đúng là hằng số** — 0,688 / 0,593 / 0,622 / 0,585 / 0,582 trên dải `N_eff` rộng 37 lần. Rút gọn không sai.

Nhưng nó là rút gọn của **mômen bậc ba tuyệt đối**, tức của *chặn* Berry–Esseen, chứ không của đại lượng thật sự lái coverage. Skewness đo được bác bỏ ngay:

| cell | `N_eff` | skewness của trung bình |
|---|---:|---:|
| V05 (e=0,9) | 2,38 | **0,436** |
| V05B (e=0,5) | 12,59 | **0,0087** |

Lệch **50 lần** trong khi `N_eff` chỉ lệch 5 lần. Giả thuyết "coverage là hàm của riêng `N_eff`" **sai**, và tôi đã kịp bác bỏ nó trước khi nó thành kết luận. Lý do: ở `e = 0,5` gai nhánh xử lý (`+1/e`) và gai nhánh đối chứng (`−1/(1−e)`) **cùng độ lớn**, nên mômen bậc ba **triệt tiêu** — trong khi mômen tuyệt đối thì không.

### Công thức đúng

Giữ cả hai nhánh:

```
E[d³] ≈ h·rate·[ 1/e² − 1/(1−e)² ]        σ² ≈ h·rate/(e(1−e))
```

rút gọn thành

> **γ = (1 − 2e) / √( n·h·rate·e·(1−e) )**

Kiểm bằng số trên chính estimator, 6 world mỗi điểm, generator V05 với `e` quét:

| `e` | γ dự đoán | γ đo được | tỷ số |
|---:|---:|---:|---:|
| 0,50 | 0,0000 | 0,0015 | — |
| 0,60 | −0,0820 | 0,0727 | 0,89 |
| 0,70 | −0,1766 | 0,1368 | 0,78 |
| 0,80 | −0,3050 | 0,2624 | 0,86 |
| 0,90 | −0,5440 | 0,5004 | 0,92 |
| 0,95 | −0,8454 | 0,7811 | 0,92 |

Khớp trong khoảng 8–22%, hệ số ổn định ~0,85 (phần thiếu là số hạng augmentation mà mô hình gai bỏ qua). Dấu ngược vì quy ước `reward = 1 − outcome`.

### Hệ quả — và S18 được minh oan

Thừa số `(1 − 2e)` **bằng đúng 0 ở thiết kế cân bằng, với mọi độ hiếm**. Nghĩa là:

| | |
|---|---|
| **Lệch propensity là điều kiện cần** | Hiếm một mình cho skewness bằng 0, dù `N_eff` nhỏ tới đâu |
| **Hiếm là bộ khuếch đại** | Nó vào qua `1/√(n·h·rate·e(1−e))` |
| **Cỡ mẫu cũng chỉ là bộ khuếch đại** | `n` vào cùng chỗ với `rate` |

Đây **đúng** là điều S18 kết luận từ V05 vs V05B — *"nguyên nhân là lệch propensity, hiếm chỉ khuếch đại"* — và giờ nó có công thức chứ không chỉ có hai điểm. Đính chính mà tôi định viết ở trên là **sai**; S18 đứng vững.

### Chỉ số bất đối xứng, và vì sao cổng gác hiện tại vẫn chưa đúng

Đặt

> **A = |1 − 2e| / √( n·h·rate·e·(1−e) )**  (bằng `2 × imbalance / √(n·h·rate·e(1−e))`)

Cổng gác hiện tại cấp phép theo **imbalance ≤ 0,30**, tức chỉ nhìn tử số. Nó bỏ qua `n`, `rate` và `h`. Một cohort lệch 0,25 nhưng `rate = 0,0005` sẽ được cấp phép **sai**; một cohort lệch 0,35 với hàng triệu event sẽ bị chặn **thừa**. `A` gộp cả bốn thừa số vào một số.

Giá trị `A` của những thiết kế đã biết:

| Thiết kế | `A` | coverage đo được |
|---|---:|---:|
| Hillstrom primary (e=0,4987; n=34.092; rate 0,0089; cap 20%) | **0,0007** | — (nằm sâu trong vùng an toàn) |
| V05B / V03 / V01 (e=0,5) | **0** | 0,948 / đạt / đạt |
| V05 (e=0,9; rate 0,005) | **0,533** | 0,929 |

Ngưỡng của `A` **chưa biết** — nó nằm đâu đó giữa 0 và 0,533, và đó chính là thứ lưới quét đang đo. Chưa sửa code cho tới khi có số.

### Chỗ lý thuyết vẫn chưa khớp

Sweep cỡ mẫu (S14) giữ `rate` và `e`, chỉ tăng `n` 16 lần, nên `A` giảm 4 lần. Thiếu hụt coverage chỉ giảm **2,1 lần** (0,030 → 0,014). Hai khả năng, và lưới phân biệt được:

- **(a)** Ở `A ≈ 0,53` khai triển Edgeworth chưa hợp lệ nên tốc độ tiệm cận chưa xuất hiện; các cell `A` nhỏ phải bám sát tỷ lệ tuyến tính với `A`.
- **(b)** Có số hạng thứ hai không co theo `n` — ứng viên là `φ(z)·z·(σ†−σ#)/σ#` của Qiu, tức lệch trong ước lượng phương sai.

Khác biệt này có hệ quả thực tế: dưới (a) thu thêm dữ liệu cuối cùng sẽ cứu được; dưới (b) **không bao giờ**, và phải sửa ước lượng phương sai. Câu **"thêm dữ liệu không giúp"** của S14 đang ngầm khẳng định (b) mà chưa phân biệt được.

## 4. Ứng viên A phải phát biểu lại thế nào

| Không dùng được | Dùng được |
|---|---|
| "DR mất coverage dưới weak overlap" — đã có định lý (Dorn 2025) | "Ở overlap **hoàn hảo nhưng không cân bằng** — `e` hằng số, trọng số bị chặn — khoảng Wald DR vẫn mất coverage, và văn liệu weak overlap không phủ chế độ này vì ở đó `e` bị chặn xa 0" |
| "Cần ngưỡng/trimming" — remedy đã biết, và ở đây vô nghĩa | "Ba họ khoảng (normal, Edgeworth+df hữu hiệu, bootstrap-t B=499) đều không đủ, và thêm 16× dữ liệu cũng không, nên đây không phải chuyện tốc độ hội tụ" |
| "Ranh giới ở imbalance 0,3" — imbalance đúng hướng nhưng thiếu `n`, `rate`, `h` | Ranh giới phát biểu theo `A = |1−2e|/√(n·h·rate·e(1−e))`, có công thức khớp số đo trong 15%, kèm bộ falsification 9 scenario × 2.000 world |

Đóng góp còn lại, nếu có, là **kỹ thuật vận hành**: một vùng thiết kế đo được cộng một cổng gác cơ khí từ chối chạy ngoài vùng đó — thứ mà cả Dorn lẫn Ma và cộng sự đều không cung cấp vì họ giải bài toán estimator, không giải bài toán quy trình. Đó là đóng góp khiêm tốn hơn nhiều so với cách repo đang tự mô tả, và phải nói đúng như vậy.

## 5. Việc phải làm tiếp theo, theo thứ tự

1. ~~Đọc kỹ arXiv:2512.18898~~ — **xong**, §3. Mệnh đề giải tích đã có; phần chuyên biệt hoá về `N_eff` là của repo.
2. Định vị ngưỡng của `A` trên artifact sweep: 18 cell mỗi phương pháp, so `A` với `1/√N_eff` xem cái nào giải thích được coverage.
3. Nếu `A` thắng: **sửa cổng gác** từ `imbalance ≤ 0,30` sang ngưỡng trên `A` — thay đổi code, không phải thay đổi văn bản.
4. Chỉ sau đó mới quyết định ứng viên A còn đóng góp gì.
