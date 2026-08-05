# Tuần 4 — Dashboard acceptance, độ nhạy chi phí và giải thích cho người dùng

**Sprint:** 2
**Trọng tâm theo kế hoạch:** Dashboard acceptance, sensitivity, giải thích cho người dùng
**Deliverable đã chốt:** Demo checklist, bản nháp video
**Trạng thái:** Đạt

---

## 1. Kế hoạch tuần

Đóng gói Sprint 2 thành một demo chạy được và kiểm tra được: dashboard self-contained,
bảng độ nhạy chi phí, guard phân biệt biến quan sát với input kịch bản, và acceptance test
tự động thay vì kiểm tra bằng mắt.

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Data contract cho dashboard | `scripts/export_dashboard_data.py`, schema `sprint2-dashboard-v1` |
| Dashboard self-contained | `scripts/build_dashboard.py` → `output/dashboard.html` |
| Acceptance tự động | `scripts/smoke_dashboard_browser.mjs`, 11/11 pass |
| Độ nhạy chi phí | `output/sprint2/policy_sensitivity.csv` |
| Đường cong ngân sách | `scripts/rebuild_sprint2_policy_budget_curve.py` |
| Nâng bootstrap | 300 → 500 resample |
| Card tài liệu | data card, model card |

## 3. Cách hoạt động

### 3.1 Ranh giới artifact — dashboard không được tự tính lại gì

Nguyên tắc: dashboard **chỉ đọc artifact đã freeze**, không train, không download ngầm.

`export_dashboard_data.py` là cửa duy nhất. Nó kiểm tra sáu file bắt buộc tồn tại rồi mới
dựng payload; thiếu file thì `FileNotFoundError` với tên file cụ thể.

Có một guard đáng chú ý — script tự kiểm tra lại quyết định chọn champion:

```python
champion = ranking_candidates.sort_values(
    ["qini_score", "auuc_score"], ascending=False
).iloc[0]["model"]
if champion != "Response":
    raise ValueError(
        "Dashboard contract expects the validation-selected Response champion; "
        f"artifact currently selects {champion!r}. Review before changing UI."
    )
```

Nó chọn champion từ **validation** (không phải confirmation) và raise nếu kết quả không
khớp giả định đang mã hóa trong UI. Nếu ai đó đổi model mà quên đổi giao diện, build sẽ
dừng thay vì hiển thị sai.

### 3.2 Bảng độ nhạy — lưới budget × cost

`policy_sensitivity.csv` là tích Descartes của năm budget `{1, 5, 10, 20, 30}%` và bốn mức
chi phí `{0; 0,00025; 0,0005; 0,001}`, cho mỗi policy. Mỗi dòng ghi:

- `gross_incremental_conversions_per_customer_dr` — đại lượng ước lượng được;
- `net_scenario_value_per_customer_dr` — sau khi trừ chi phí giả định;
- `is_monetary_observation: False` — cờ cứng trong dữ liệu;
- `interpretation: "conversion-equivalent assumption scenario"`.

Hai trường cuối là **một phần của dữ liệu**, không phải chú thích trong slide. Bất kỳ ai
đọc CSV cũng thấy ngay đây không phải doanh thu quan sát.

### 3.3 Chi phí hòa vốn

```
break_even_contact_cost = value_per_conversion × G(b) / b
```

`G(b)` là conversion tăng thêm trên mỗi khách hàng khi target top `b`. Đây là mức chi phí
làm giá trị ròng bằng 0.

Ở budget 1%, break-even là `0,0526`; ở 30% là `0,0031`. Chênh 17 lần. Ý nghĩa vận hành:
target hẹp chịu được chi phí liên hệ cao hơn nhiều, vì nhóm đầu bảng có uplift lớn hơn.

### 3.4 Acceptance test bằng headless browser

`smoke_dashboard_browser.mjs` khởi động Chrome headless với `--dump-dom`, render dashboard
ở bốn kịch bản qua query param, rồi kiểm tra nội dung **đã render** — không phải kiểm tra
mã nguồn.

Bốn kịch bản: mặc định, chi phí thấp, chi phí cao, không target ai.

Vì sao dùng `--dump-dom` thay vì đọc file HTML: dashboard tính giá trị bằng JavaScript khi
tải. Đọc file chỉ kiểm tra được template; dump DOM kiểm tra được **kết quả tính toán**.

Kết quả 11/11 pass, kèm screenshot làm bằng chứng.

### 3.5 Guard phân biệt observed và assumption

Ba lớp:

1. **Banner phạm vi** ngay đầu trang: giá trị và chi phí là input kịch bản.
2. **Cờ trong dữ liệu:** `is_monetary_observation: False` trong mọi dòng CSV.
3. **Export có run ID và cột assumption**, nên file tải về không tách rời khỏi ngữ cảnh.

### 3.6 Nâng bootstrap từ 300 lên 500

Chi phí thêm: 302,6 giây, dùng **frozen predictions** — không fit lại model. Đây là lý do
`rebuild_sprint2_*.py` tách riêng: cho phép chạy lại phần bootstrap mà không chạy lại phần
train.

## 4. Kết quả

Đường cong ngân sách của Response trên confirmation:

| Budget | Gross/khách hàng | CI 95% | Chi phí hòa vốn |
|---:|---:|---:|---:|
| 1% | 0,000526 | [0,000392; 0,000662] | 0,052604 |
| 5% | 0,000835 | [0,000664; 0,001002] | 0,016702 |
| 10% | 0,000849 | [0,000658; 0,001027] | 0,008489 |
| 20% | 0,000908 | [0,000732; 0,001092] | 0,004541 |
| 30% | 0,000943 | [0,000749; 0,001134] | 0,003142 |

Hạ tầng full local Sprint 2: runtime 395,9 giây cho model/policy; 6 CPU vật lý / 12 luồng;
RAM 15,19 GB; peak process RSS 2,74 GB; RAM khả dụng thấp nhất 1,81 GB.

Chất lượng: 49/49 pytest pass; 11/11 browser acceptance.

## 5. Quyết định và lý do

1. **Giữ dashboard tĩnh self-contained**, không dựng FastAPI ở Sprint 2. Kế hoạch ghi rõ:
   ưu tiên demo không lỗi và provenance rõ hơn kiến trúc phức tạp.
2. **Không đưa Causal Forest vào dashboard** khi chưa có artifact cloud. Trạng thái
   `pending_external_kaggle_session` hiển thị công khai.
3. **Nâng bootstrap lên 500** vì chi phí chỉ 5 phút trên prediction đã đóng băng.

## 6. Chưa xong và rủi ro

- Comparator random vẫn là một ranking seed 42.
- Chưa có A/B test production.
- Video demo chưa quay.
- Causal Forest vẫn pending.

## 7. Chuẩn bị cho tuần sau

Sprint 2 đã đóng. Trước khi packaging, có một vấn đề phương pháp chưa giải quyết: **Qini là
metric ranking, không trả lời trực tiếp câu hỏi ngân sách**, và cả ba model đầu bảng đều
chưa tách được khỏi nhau. Tuần 5 sẽ xử lý điều này.

## 8. Câu hỏi cần mentor phản biện

Mức chi tiết kỹ thuật và sản phẩm đã đủ để kiểm tra quyết định chưa, hay cần một vòng cải
tiến model có giao thức chặt hơn trước khi đóng gói?

*Câu trả lời dẫn tới việc đổi phạm vi Tuần 5–6.*
