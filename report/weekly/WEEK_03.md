# Tuần 3 — Từ score sang quyết định: decision contract, policy value và dashboard đầu tiên

**Sprint:** 2
**Trọng tâm theo kế hoạch:** Decision contract, decile/policy table, dashboard đầu tiên
**Deliverable đã chốt:** Interactive prototype + scenario table
**Trạng thái:** Đạt

---

## 1. Kế hoạch tuần

Biến CATE ranking thành một màn hình ra quyết định có assumption minh bạch, thay vì chỉ
trình bày biểu đồ thuật toán. Người xem không biết causal inference vẫn phải trả lời được:
nên target bao nhiêu phần trăm, bằng chứng offline là gì, chi phí nào thì policy không còn
hợp lý, và con số nào chỉ là giả định.

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Tập dữ liệu mới | `stratified_complement` → pool Sprint 2, 60/20/20 |
| Ablation calibration | X-Renormalized, X-Calibrated, T-LocalExact |
| Policy value | IPW và DR signal, `src/policy.py` |
| Decision contract | `docs/DECISION_CONTRACT.md` |
| Pipeline một lệnh | `scripts/run_sprint2_local.py` |
| Dashboard đầu tiên | `scripts/build_dashboard.py` |

## 3. Cách hoạt động

### 3.1 Lấy phần bù — cơ chế chống tái dùng test Sprint 1

Đây là quyết định thiết kế quan trọng nhất của tuần.

Nếu Sprint 2 lấy một mẫu ngẫu nhiên mới từ toàn bộ dữ liệu, nó sẽ **chồng lấn** với final
test Sprint 1. Khi đó "confirmation" của Sprint 2 chứa những dòng đã được dùng để báo cáo
ở Sprint 1, và tính độc lập biến mất.

Giải pháp: tách `_stratified_sample_indices` thành helper riêng, rồi:

```python
selected_idx = _stratified_sample_indices(df, frac=0.50, seed=42)
complement = df.loc[~df.index.isin(selected_idx)]
```

Hàm này **tái dựng chính xác** mẫu Sprint 1 rồi lấy phần còn lại. Kết quả:

| Split | Rows | Treatment rate | Conversion rate |
|---|---:|---:|---:|
| fit | 4.193.877 | 0,850000 | 0,002917 |
| validation | 1.397.959 | 0,850000 | 0,002916 |
| confirmation | 1.397.959 | 0,850001 | 0,002916 |

Hash SHA-256 của source index cả ba split được lưu vào manifest. Từ Sprint 3, hash này
được **đối chiếu tự động** và pipeline dừng nếu lệch.

### 3.2 Ba ablation calibration — và câu hỏi chúng trả lời

Câu hỏi: undersampling `k=7` làm sai lệch scale của score. Cách sửa nào tốt hơn?

| Model | Cơ chế | Phạm vi nguồn |
|---|---|---|
| X-Renormalized | Chia score cho `k` | Xấp xỉ được Nyberg khuyến nghị cho stratified undersampling |
| X-Calibrated | X-Renormalized + tau-isotonic fit trên validation | Post-processing tổng quát, **không** phải pairing ưu tiên của paper |
| T-LocalExact | Khôi phục xác suất chính xác từng arm rồi trừ | Đúng phạm vi Eq. 12 của Nyberg & Klami (2023) |

**Công thức khôi phục chính xác:**

```
p = s·q / (1 − q·(1 − s))
```

`q` là xác suất trong dữ liệu đã undersample, `s` là xác suất giữ negative. Áp **riêng cho
từng arm** rồi mới lấy hiệu.

Ranh giới nguồn được ghi rõ: Nyberg & Klami nói S/X learner *có thể* tương thích với một số
phương pháp undersampling nhưng để phần đánh giá thực nghiệm cho nghiên cứu sau. Vì vậy
`fit_x_learner_exact_undersampling` được đánh dấu là **research ablation**, không phải
phương pháp đã được paper kiểm chứng. Release chuyển exact restoration sang T-Learner —
đúng phạm vi Eq. 12.

**Điểm quan trọng về tau-isotonic:** calibrator được fit trên **validation**, không phải
confirmation. Fit trên confirmation sẽ làm kết quả confirmation lạc quan giả tạo.
Isotonic giữ thứ tự không giảm nên **không đổi Qini**; nó chỉ sửa scale, tức chỉ ảnh hưởng
EUCE.

### 3.3 Policy value — chuyển từ ranking sang quyết định

Qini nói model xếp hạng tốt đến đâu. Nó **không** nói target 10% thì được bao nhiêu
conversion tăng thêm. Tuần này thêm hai tín hiệu:

**IPW:**
```
Γ_ipw = T·Y/p − (1−T)·Y/(1−p)
```

**Doubly robust (AIPW):**
```
Γ_dr = mu1 − mu0 + T·(Y − mu1)/p − (1−T)·(Y − mu0)/(1−p)
```

Cả hai có kỳ vọng bằng ATE. DR có variance thấp hơn nhiều khi `mu` học tốt — với outcome
0,29%, variance là kẻ thù chính nên DR là lựa chọn chính.

Giá trị policy:

```
value(π) = mean( π(x) · (value_per_conversion · Γ − contact_cost) )
```

`policy_value_from_signal` kiểm tra `π` là vector nhị phân và raise nếu không — chặn lỗi
truyền nhầm score vào chỗ của policy.

### 3.4 Decision contract — tài liệu khóa quy tắc trước khi có kết quả

`docs/DECISION_CONTRACT.md` ghi trước:

- **Đơn vị quyết định:** một khách hàng trong population phân phối tương tự confirmation.
- **Policy phát hành:** `Response top-k` — xếp theo score, target đúng top `k%`.
- **Lý do chọn Response:** model selection chỉ dùng validation; Response có Qini validation
  cao nhất trong nhóm triển khai được; trên confirmation, `X-Renormalized − Response` có CI
  chứa 0 nên chưa tách được; khi CI chứa 0 thì **giữ model ít thành phần hơn**.
- **Cấm:** dùng score Response để tuyên bố hiệu ứng cá nhân.

Điểm mấu chốt: quy tắc "CI chứa 0 thì giữ champion đơn giản hơn" được viết **trước** khi
xem confirmation. Nếu viết sau, nó chỉ là hợp lý hóa kết quả.

### 3.5 Pipeline một lệnh

`run_sprint2_local.py` chạy toàn bộ trong một lệnh và ghi manifest có: checksum dữ liệu,
hash ba split, cấu hình model, hệ số undersampling, keep probability lý thuyết và thực tế,
package version, peak RSS, RAM khả dụng thấp nhất, elapsed time.

Có một `_MemorySampler` chạy thread nền lấy mẫu mỗi 0,25 giây — tiền thân của
`ResourceMonitor` ở Sprint 3.

Fail-fast gate: nếu chạy full pool mà RAM khả dụng dưới 2,5 GB, script **raise ngay** thay
vì chạy 6 phút rồi chết vì OOM.

## 4. Kết quả

| Model | Qini | AUUC | EUCE |
|---|---:|---:|---:|
| X-Renormalized | 0,191557 | 0,006189 | 0,000462 |
| X-Calibrated | 0,188528 | 0,006084 | 0,000240 |
| Response | 0,182789 | 0,005912 | không áp dụng |
| T-LocalExact | 0,117668 | 0,003798 | 0,000957 |

Paired:

| A − B | Δ | CI 95% | Kết luận |
|---|---:|---:|---|
| X-Renormalized − Response | 0,008768 | [-0,018626; 0,038772] | chưa phân biệt |
| X-Calibrated − X-Renormalized | -0,003029 | [-0,010774; 0,004700] | chưa phân biệt |
| T-LocalExact − X-Renormalized | -0,073889 | [-0,107381; -0,035891] | CI dưới 0 |

Kết quả đáng chú ý: **phương pháp "exact" không tự động tốt hơn phép xấp xỉ.** T-LocalExact
dùng công thức khôi phục chính xác nhưng Qini thấp hơn hẳn X-Renormalized dùng xấp xỉ `1/k`.
Calibration cải thiện EUCE (0,000240 so với 0,000462) nhưng không cải thiện ranking.

Policy tại budget 10%, `value=1`, `cost=0,0005`:

| Policy | DR net/khách hàng | CI 95% |
|---|---:|---:|
| Response top-k | 0,000799 | [0,000608; 0,000977] |
| X-Renormalized top-k | 0,000825 | [0,000649; 0,001001] |
| Random top-k | 0,000040 | [-0,000017; 0,000096] |

## 5. Quyết định và lý do

1. **Champion là Response top-k**, chốt trên validation trước khi xem confirmation.
2. **Không đổi champion sau khi xem confirmation** dù X-Renormalized có point estimate cao
   hơn — CI chứa 0, và selection contract đã khóa.
3. **Mọi giá trị tiền là kịch bản giả định.** Criteo không có doanh thu, biên lợi nhuận hay
   chi phí liên hệ.

## 6. Chưa xong và rủi ro

- Dashboard mới ở mức prototype, chưa có acceptance test.
- Comparator random là **một ranking cố định seed 42**; CI chưa phản ánh biến thiên qua
  nhiều random policy.
- Causal Forest vẫn pending.

## 7. Chuẩn bị cho tuần sau

Tuần 4 cần: acceptance test tự động cho dashboard, bảng độ nhạy theo chi phí, và panel
giải thích phân biệt biến quan sát với input kịch bản.

## 8. Câu hỏi cần mentor phản biện

Assumption `contact_cost` và `conversion_value` nên đặt và đánh giá thế nào khi dataset
không có bất kỳ đại lượng tiền tệ nào?
