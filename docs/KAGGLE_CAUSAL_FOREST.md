# Runbook Causal Forest trên Kaggle Free

## Trạng thái thực thi

- Local code-path smoke 0,1%: **pass** (4.194 score finite/aligned, peak process-tree
  2,08 GB, 65 giây).
- Kaggle 20% / 30% / 50%: **chưa chạy** vì workspace hiện không có Kaggle session hoặc
  dataset attachment.
- Sprint 2 local/dashboard không bị chặn; không được đưa Causal Forest vào bảng release
  trước khi có cloud artifact.

## Vì sao không chọn GPU để “sửa” runtime?

`CausalForestDML` trong pipeline dùng CPU parallelism (`n_jobs`) và system RAM; code không
cấu hình GPU cho forest. Kaggle cũng yêu cầu dùng accelerator hiệu quả và kiểm tra quota
thực tế, không bật GPU khi workload không dùng nó:
[Kaggle Efficient GPU Usage](https://www.kaggle.com/docs/efficient-gpu-usage).

EconML 0.16 mô tả cross-fitting, honest forest, `max_samples`, inference và `n_jobs` tại
[CausalForestDML API](https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html).

## Điều kiện vào

1. Tạo Kaggle Notebook và attach đúng file
   `criteo-research-uplift-v2.1.csv.gz`.
2. SHA‑256 phải bằng:
   `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`.
3. Copy/clone repository vào notebook.
4. Cài `econml==0.16.0`, LightGBM và psutil.
5. Đọc CPU/RAM live; không ghi cứng “Kaggle luôn có X GB”.

```python
import os, psutil
print(os.cpu_count())
print(psutil.virtual_memory())
```

## Gate tự động

Thay `<dataset-folder>` bằng đường dẫn attachment trong Kaggle session:

```bash
python scripts/kaggle_causal_forest_gate.py \
  --data-path /kaggle/input/<dataset-folder>/criteo-research-uplift-v2.1.csv.gz \
  --frac 0.20
```

Chỉ khi `preflight_0p2/gate_manifest.json` có `status=passed`:

```bash
python scripts/kaggle_causal_forest_gate.py \
  --data-path /kaggle/input/<dataset-folder>/criteo-research-uplift-v2.1.csv.gz \
  --frac 0.30
```

Chỉ khi 30% pass:

```bash
python scripts/kaggle_causal_forest_gate.py \
  --data-path /kaggle/input/<dataset-folder>/criteo-research-uplift-v2.1.csv.gz \
  --frac 0.50
```

Gate tự kiểm tra:

- checksum;
- không được nhảy qua stage trước;
- exit code;
- peak RSS toàn process tree <75% tổng RAM;
- score finite;
- score/Y/T cùng số dòng;
- log, runtime và artifact path.

Profile khóa: 200 trees, `min_samples_leaf=500`, CV=2, `max_samples=0.25`,
`inference=False`. Vì inference tắt, không gọi `effect_interval()`; uncertainty của
policy/model comparison dùng holdout bootstrap ở pipeline đánh giá.

## Stop rule

Dừng ở stage hiện tại nếu gate fail, session quota/time không đủ hoặc quality validation
không biện minh chi phí compute. Nếu chỉ hoàn tất learning curve 20–30%, báo cáo kết quả đó
cùng giới hạn tài nguyên; không tiếp tục một run 50% có nguy cơ bị dừng hoặc dùng final test để tuning.

Sau khi chạy, tải toàn bộ `/kaggle/working/output/causal_forest/` về repository để audit;
không chỉ chép một con số vào báo cáo.
