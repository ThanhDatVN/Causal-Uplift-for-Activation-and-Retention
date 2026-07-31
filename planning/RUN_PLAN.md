# RUN PLAN — Chạy đủ 6 model & sinh kết quả cuối cùng

> **Superseded 29/07/2026:** không dùng runbook này cho release mới. Dùng
> [`../README.md`](../README.md) để tái lập 5 model Sprint 1 và
> [`../docs/KAGGLE_CAUSAL_FOREST.md`](../docs/KAGGLE_CAUSAL_FOREST.md) cho challenger
> Causal Forest có preflight.

> Runbook tái lập toàn bộ pipeline. **Trạng thái:** Bước 1 (5 model local @50%) đã chạy xong —
> kết quả ở `report/week-01/baseline-results.md`. Còn Bước 2 (Causal Forest trên Colab) → Bước 3-4.

## Lineup 6 model (đã chốt)

Các model được sắp theo target và cơ chế ước lượng để comparison table có baseline xác định:

| # | Model | Loại | Chạy ở đâu | Hàm code |
|---|---|---|---|---|
| 1 | **Response baseline** | Xếp hạng theo xác suất response, không sử dụng treatment | Local | `src/baselines.py::fit_response_baseline` |
| 2 | **S-Learner** | Meta-learner (1 model, T là feature) | Local | `fit_s_learner` |
| 3 | **T-Learner** | Meta-learner (2 model tách) — *baseline mốc so sánh* | Local | `fit_t_learner` |
| 4 | **X-Learner** | Meta-learner (cải tiến cho treatment lệch) | Local | `fit_x_learner` |
| 5 | **DR-Learner** | Doubly Robust (propensity RCT cố định ≈0.85) | Local | `fit_dr_learner` |
| 6 | **Causal Forest** | CausalForestDML (honest, có inference) | **Colab Pro** | `scripts/train_causal_forest.py` |

Holdout chung: **sample 50%**, `test_size=0.30`, `seed=42`, stratify theo `(treatment, conversion)`.
Vì holdout xác định theo seed, model chạy local và Causal Forest chạy Colab vẫn dùng **chung đúng một tập test** → so sánh công bằng.

---

## BƯỚC 1 — Chạy 5 model local (laptop)

```bash
.venv/Scripts/python.exe scripts/train_baselines.py --frac 0.50 --n-boot 500
```

- **Thời gian dự kiến:** ~13–18 phút. Phần nặng là bootstrap 500 lần trên tập test ~2,1M dòng (không phải train — fit chỉ vài chục giây).
- **Sinh ra:**
  - `output/qini_comparison.csv` — ma trận so sánh 5 model local
  - `output/qini_curve.png` — Qini curve 5 model chồng nhau
  - `output/segments_baseline.csv` — phân khúc sơ bộ
  - `output/cate/cate_*.npy` + `output/cate/holdout_test_yt.npz` — CATE + holdout đã lưu (để ghép Causal Forest sau, KHÔNG phải train lại)

**Kiểm tra sau khi xong:** mở CSV, xác nhận `sample_frac=0.5` và `n_test` ≈ 2,1 triệu (nếu vẫn thấy `0.01` là đang xem file smoke cũ chưa bị ghi đè).

---

## BƯỚC 2 — Chạy Causal Forest trên Colab Pro

> Runbook lịch sử này dùng Colab cho Causal Forest. Có thể upload
> `notebooks/colab_causal_forest.ipynb` và chạy theo
> [`docs/COLAB_CAUSAL_FOREST.md`](../docs/COLAB_CAUSAL_FOREST.md). Runbook hiện hành dùng
> Kaggle gate trong `docs/KAGGLE_CAUSAL_FOREST.md`.

1. Colab: **Runtime > Change runtime type > High-RAM** (~51GB).
2. Clone repo + cài đặt + đưa `data/criteo-research-uplift-v2.1.csv.gz` vào `data/` (upload hoặc mount Drive).
3. Chạy preflight 30% trước:
   ```bash
   !python scripts/train_causal_forest.py --frac 0.30   # đo RAM và runtime ở 30%
   ```
   Chỉ chạy 50% nếu peak RAM nằm dưới resource gate đã đặt và process kết thúc với artifact
   hợp lệ. Nếu không, dừng ở 30%; không thay holdout sau khi đã xem kết quả.
4. Chạy chính thức:
   ```bash
   !python scripts/train_causal_forest.py --frac 0.50
   ```
   - Thời gian ngoại suy: ~90 phút. RAM ngoại suy: ~24GB.
5. Tải `output/cate/cate_causal_forest.npy` về máy, đặt vào `output/cate/` (cùng chỗ các CATE baseline).

**Điều kiện ghép artifact:** `--frac` và `--seed` ở Bước 2 phải khớp Bước 1
(`0.50` và `42`); nếu không, các prediction không dùng chung test indices.

---

## BƯỚC 3 — Ghép thành bảng so sánh cuối cùng (local)

```bash
.venv/Scripts/python.exe scripts/build_comparison.py --n-boot 500
```

- Đọc mọi `output/cate/cate_*.npy` (5 baseline + Causal Forest) + holdout đã lưu, đánh giá **tất cả trên cùng tập test**, không train lại.
- **Sinh ra (kết quả CUỐI CÙNG của Sprint 2):**
  - `output/qini_comparison.csv` — ma trận model với Qini/AUUC, CI riêng và paired CI của
    `ΔQini` so T-Learner; không gọi bootstrap tail heuristic là p-value
  - `output/qini_curve.png` — 6 đường Qini chồng nhau
  - `output/segments.csv` — score-sign diagnostic của CATE model; không phải bốn
    principal strata quan sát được
- Thời gian: ~15–20 phút (bootstrap 6 model + 5 paired).

---

## BƯỚC 4 — Xuất dữ liệu cho dashboard sản phẩm (local)

```bash
.venv/Scripts/python.exe scripts/export_dashboard_data.py
```

- Sinh `output/dashboard_data.json` từ Sprint 2 release artifacts để dashboard HTML đọc.
- Nhanh (đọc CATE đã lưu, không train lại).

---

## Còn lại sau khi chạy Causal Forest (Colab)

- [ ] Ghi peak RAM/runtime quan sát được của Causal Forest vào run manifest; không thay số
  ngoại suy bằng point estimate nếu cloud run chưa hoàn tất.
- [ ] `build_comparison.py` → ma trận đủ 6 model; `build_dashboard.py` → cập nhật dashboard.
- [ ] Viết `02_causal_uplift.ipynb` gọi lại các hàm + vẽ biểu đồ + nhận xét.
- [ ] Bổ sung test cho S/DR/Response baseline.

Kết quả 5 model local @50% (đã chạy): `report/week-01/baseline-results.md`.
