# Chạy Causal Forest (model còn lại) trên Colab

> **Trạng thái: phương án fallback/lịch sử.** Luồng hiện hành dùng resource gate trong
> `planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md` và ưu tiên Kaggle khi session đáp ứng RAM.
> Các mốc 30%/50%, 24 GB và 90 phút bên dưới là ngoại suy từ benchmark 20%, không phải cam kết
> tài nguyên hay runtime của Colab. Resource của Colab thay đổi theo thời điểm và loại tài khoản.
> Bảng release cuối phải được dựng lại bằng `scripts/build_comparison.py`; notebook không được dùng
> holdout test để chọn champion.

> Có thể upload file **`notebooks/colab_causal_forest.ipynb`** lên
> [colab.research.google.com](https://colab.research.google.com) (File → Upload notebook) → đổi runtime
> **High-RAM** → **Run all**. Khỏi copy tay. Các cell bên dưới là bản markdown của chính notebook đó.

5 model baseline đã chạy local rồi — notebook **chỉ chạy model thứ 6 (Causal Forest)**, rồi **ghép với
5 CATE baseline** để ra bảng so sánh + biểu đồ đủ 6 model, lưu Google Drive.

**Để có bảng + biểu đồ đủ 6 model:** upload 5 file `output/cate/cate_{response,s_learner,t_learner,x_learner,dr_learner}.npy`
lên Drive `MyDrive/causal_uplift_results/cate/` trước khi Run all. (Nếu không, notebook vẫn chạy Causal
Forest và sinh `cate_causal_forest.npy` để ghép ở local bằng `scripts/build_comparison.py`.)

Code **tự chứa** — không cần clone repo.

> **Vì sao phải khớp chính xác:** holdout được xác định bởi `seed=42` + `frac=0.50` + cách stratify.
> Code dưới lặp lại **y hệt** `src/data.py` nên tập test ở Colab trùng từng dòng với tập test baseline
> đã chạy local → CATE ghép được. **Đừng đổi `FRAC`, `SEED`, `TEST_SIZE`.**

## Chuẩn bị runtime
- Runtime > Change runtime type > chọn **High-RAM** (hoặc GPU A100/L4 — GPU không được dùng nhưng đi
  kèm ~53GB RAM hệ thống, đủ). Causal Forest ở 50% cần ~24GB **RAM hệ thống** (không phải RAM GPU).

---

### Cell 1 — Cài thư viện (khớp version local)
```python
!pip -q install econml==0.16.0 lightgbm==4.5.0
```

### Cell 2 — Tải dataset thẳng từ HuggingFace (~311MB, ~1-2 phút, không cần upload)
```python
!wget -q https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz -O criteo.csv.gz
!ls -lh criteo.csv.gz
```

### Cell 3 — (TÙY CHỌN) Dev-verify RAM ở 30% trước
> Cell này đo peak RAM/runtime ở 30%. Không ghép CATE từ 30% với holdout 50%. Chỉ bỏ qua
> preflight nếu runtime đã có manifest tài nguyên tương đương từ cùng cấu hình.
```python
# đổi FRAC=0.30 trong Cell 4 rồi chạy; chỉ tăng sample nếu peak RAM nằm dưới resource gate
# đổi lại FRAC=0.50 và chạy chính thức.
```

### Cell 4 — Holdout + fit Causal Forest + lưu CATE (bản chính thức)
```python
import time, numpy as np, pandas as pd
from sklearn.model_selection import train_test_split

# ---- THAM SỐ: PHẢI khớp train_baselines.py, đừng đổi ----
FRAC, SEED, TEST_SIZE = 0.50, 42, 0.30
FEATURES = [f"f{i}" for i in range(12)]

# ---- load (y hệt src/data.py::load_criteo_full) ----
t0 = time.time()
dtype = {f: "float32" for f in FEATURES}
dtype.update({"treatment": "int8", "conversion": "int8", "visit": "int8", "exposure": "int8"})
df = pd.read_csv("criteo.csv.gz", dtype=dtype)
print(f"[load] {len(df):,} dòng, {time.time()-t0:.0f}s")

# ---- stratified_sample (y hệt src/data.py) ----
if FRAC < 1.0:
    rng = np.random.default_rng(SEED)
    parts = []
    for _, g in df.groupby(["treatment", "conversion"], sort=False):
        n = max(1, int(round(len(g) * FRAC)))
        idx = rng.choice(g.index.values, size=min(n, len(g)), replace=False)
        parts.append(df.loc[idx])
    df = pd.concat(parts, ignore_index=True)
print(f"[sample] frac={FRAC} -> {len(df):,} dòng")

# ---- train_test_holdout (y hệt src/data.py) ----
strata = df["treatment"].astype(str) + "_" + df["conversion"].astype(str)
train_df, test_df = train_test_split(df, test_size=TEST_SIZE, random_state=SEED,
                                     shuffle=True, stratify=strata)
train_df = train_df.reset_index(drop=True); test_df = test_df.reset_index(drop=True)
print(f"[holdout] train={len(train_df):,} test={len(test_df):,}")

def xty(d):
    return (d[FEATURES].to_numpy("float64"), d["treatment"].to_numpy("float64"),
            d["conversion"].to_numpy("float64"))
X_tr, T_tr, Y_tr = xty(train_df)
X_te, T_te, Y_te = xty(test_df)

# ---- fit CausalForestDML (cấu hình production, khớp scripts/train_causal_forest.py) ----
from econml.dml import CausalForestDML
print("[fit] bắt đầu (ngoại suy ~90 phút ở 50%)...")
t = time.time()
model = CausalForestDML(
    n_estimators=500, min_samples_leaf=200, discrete_treatment=True,
    honest=True, inference=True, cv=3, random_state=SEED,
)
model.fit(Y=Y_tr, T=T_tr, X=X_tr)
print(f"[fit] xong {time.time()-t:.0f}s")

# ---- lưu CATE trên tập test (khớp từng dòng với holdout local) ----
cate = model.effect(X_te).ravel()
np.save("cate_causal_forest.npy", cate.astype("float64"))
print(f"[save] cate_causal_forest.npy (n={len(cate):,}, mean={cate.mean():.6f})")
```

### Cell 5 — Tải file về máy
```python
from google.colab import files
files.download("cate_causal_forest.npy")
```

---

## Ở máy local — ghép vào ma trận 6 model
1. Đặt `cate_causal_forest.npy` vừa tải vào thư mục **`output/cate/`** (cạnh các `cate_*.npy` khác).
2. Chạy:
```bash
.venv/Scripts/python.exe scripts/build_comparison.py --n-boot 500
.venv/Scripts/python.exe scripts/export_dashboard_data.py
.venv/Scripts/python.exe scripts/build_dashboard.py
```
→ `output/qini_comparison.csv` (đủ 6 model), `output/qini_curve.png`, `output/segments.csv`,
dashboard cập nhật.

## Kiểm tra khớp holdout (nếu nghi ngờ)
`cate_causal_forest.npy` phải có **đúng số dòng** với tập test local. `build_comparison.py` đọc
`output/cate/holdout_test_yt.npz` (đã lưu khi chạy baseline) — nếu số dòng lệch, tức là `FRAC`/`SEED`
ở Colab khác local. Số dòng test kỳ vọng ở 50%: **2.096.940**.
