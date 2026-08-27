# Runbook tái lập

- **Phạm vi:** lệnh chạy lại của cả tám vòng thí nghiệm, cộng web app, kiểm thử và Docker
- **Vai trò từng script:** [`../scripts/README.md`](../scripts/README.md)
- **Thư mục ghi ra của từng script:** [`../output/README.md`](../output/README.md)
- **Kết quả mong đợi:** tám báo cáo trong [`../report/`](../report/)

Toàn bộ phần vận hành gom về một chỗ. Trước đây các lệnh này nằm rải rác trong từng báo
cáo; báo cáo nay chỉ giữ kết quả và diễn giải.

## Điều kiện tiên quyết

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Mọi run cần file Criteo v2.1 đặt ở `data/criteo-research-uplift-v2.1.csv.gz` với SHA-256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

Pipeline tự đối chiếu hash này và dừng nếu lệch. Hash split cũng được đối chiếu với
manifest Sprint 2 trước mỗi run, nên một thay đổi ngầm ở tầng dữ liệu sẽ làm run dừng chứ
không âm thầm cho ra số khác.

## Thứ tự chạy

Các vòng dưới đây độc lập nhau và đọc chung một nguồn dữ liệu. Chỉ có ràng buộc: chẩn đoán
dữ liệu nên chạy trước vì mọi vòng sau đều dẫn số từ nó.

## 1. Chẩn đoán dữ liệu

Khoảng 2,5 phút trên toàn bộ 13.979.592 dòng, sinh 17 artifact trong `output/eda/`.

```powershell
.venv\Scripts\python.exe scripts\run_eda_profile.py
```

## 2. Sprint 1 — nền tảng và bảng năm model

```powershell
.venv\Scripts\python.exe scripts\audit_criteo.py --balance-frac 0.05 --seed 42
.venv\Scripts\python.exe scripts\tune_five_models.py
.venv\Scripts\python.exe scripts\evaluate_selected_five_models.py
.venv\Scripts\python.exe scripts\compare_release_models.py
.venv\Scripts\python.exe scripts\build_sprint1_artifacts.py
```

`evaluate_selected_five_models.py` là nguồn Sprint 1 chính thức; `train_baselines.py` và
`build_comparison.py` là lần chạy đời đầu, giữ lại để truy vết chứ không dùng cho release.

## 3. Sprint 2 — policy, calibration và dashboard

```powershell
.venv\Scripts\python.exe scripts\run_sprint2_local.py --pool-frac 1 --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_qini_bootstrap.py --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_main_policy.py --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_policy_budget_curve.py --n-boot 500
.venv\Scripts\python.exe scripts\finalize_sprint2_summary.py
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

## 4. Sprint 3 — vòng cải tiến có đăng ký trước

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.01 --stage smoke --n-boot 50 --output-dir output\improvement\smoke
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.20 --stage screen --n-boot 300 --output-dir output\improvement\screen
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 1.0 --stage finalist --fold-seed 101 --n-boot 200 --candidates "Response,X-Renormalized,S-Under7,Rank-K05,Rank-K1,Rank-K2" --output-dir output\improvement\finalist
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 1.0 --stage finalist --fold-seed 202 --n-boot 200 --candidates "Response,X-Renormalized,S-Under7,Rank-K05,Rank-K1,Rank-K2" --output-dir output\improvement\finalist_seed202
.venv\Scripts\python.exe scripts\compare_improvement_candidates.py --run-dir output\improvement\finalist --run-dir output\improvement\finalist_seed202 --n-boot 200 --shortlist-size 4 --output-dir output\improvement\finalist_comparison
.venv\Scripts\python.exe scripts\run_sprint3_confirmation.py --shortlist output\improvement\finalist_comparison\shortlist.json --oof-run-dir output\improvement\finalist_comparison --n-boot 500
.venv\Scripts\python.exe scripts\build_champion_scorer.py
```

## 5. Data optimization v1

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py `
  --protocol configs\data_optimization_protocol_v1.json `
  --pool-frac 0.15 --pool-seed 77 --fold-seed 101 --n-boot 200 `
  --stage screen --output-dir output\improvement\data_opt_screen_seed101

.venv\Scripts\python.exe scripts\run_oof_experiment.py `
  --protocol configs\data_optimization_protocol_v1.json `
  --pool-frac 0.15 --pool-seed 77 --fold-seed 202 --n-boot 30 `
  --stage screen --output-dir output\improvement\data_opt_screen_seed202

.venv\Scripts\python.exe scripts\compare_improvement_candidates.py `
  --protocol configs\data_optimization_protocol_v1.json `
  --run-dir output\improvement\data_opt_screen_seed101 `
  --run-dir output\improvement\data_opt_screen_seed202 `
  --n-boot 100 --output-dir output\improvement\data_opt_comparison

.venv\Scripts\python.exe scripts\analyze_data_optimization.py
```

## 6. Causal foundation v1

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py `
  --protocol configs\causal_foundation_protocol_v1.json `
  --pool-frac 0.15 --fold-seed 101 --stage screen --n-boot 200 `
  --output-dir output\improvement\causal_foundation_screen_seed101
.venv\Scripts\python.exe scripts\analyze_causal_foundation.py
```

Lệnh finalist chạy process-isolated và bước `merge_oof_runs.py` được liệt kê đầy đủ ở
[`../scripts/README.md`](../scripts/README.md). Bước phân tích không fit model và không đọc
confirmation.

## 7. Top-tail research v2

```powershell
.venv\Scripts\python.exe scripts\analyze_top_tail_evidence.py
```

Khi artifact chính thức đã tồn tại, lệnh này **từ chối ghi đè**. Muốn chạy sensitivity thì
phải khai báo protocol mới và output namespace mới.

## 8. Causal Forest trên Kaggle

Chấm điểm và phân tích artifact tải về:

```powershell
# Chấm điểm chính thức (nạp lại Criteo, đối chiếu holdout, paired bootstrap)
.venv\Scripts\python.exe scripts\evaluate_causal_forest.py `
  --stage-dir output\causal_forest\preflight_0p5 --n-boot 500 --signal ipw

# Learning curve ba mốc, phân bố điểm, tài nguyên
.venv\Scripts\python.exe scripts\analyze_causal_forest_release.py

# Năm biểu đồ
.venv\Scripts\python.exe scripts\plot_causal_forest_release.py
```

Bản notebook của lần chạy: [`../notebooks/03_causal_forest.ipynb`](../notebooks/03_causal_forest.ipynb).

### 8bis. Cấu hình `rare-outcome` trên split Sprint 2/3

Protocol: [`../configs/causal_forest_rare_outcome_protocol_v1.json`](../configs/causal_forest_rare_outcome_protocol_v1.json).
Notebook: [`../notebooks/04_causal_forest_rare_outcome.ipynb`](../notebooks/04_causal_forest_rare_outcome.ipynb).

Lý do tồn tại: cấu hình `kaggle-safe` đã chạy dùng `min_samples_leaf=500`, cho kỳ vọng chỉ
`0,145` sự kiện control mỗi lá. Cấu hình này nâng lên khoảng `2,9`. Profile `research` sẵn có
**không** phải bản sửa cho vấn đề đó — nó dùng `min_samples_leaf=200`, đi sai hướng.

Fit chạy trên Kaggle (RAM local không đủ cho development pool 5.591.836 dòng):

```powershell
# Smoke code path truoc, khoang 2 phut
.venv\Scripts\python.exe scripts\train_causal_forest.py `
  --split sprint3 --profile rare-outcome --train-subsample 0.02 `
  --n-estimators 8 --cv 2 --output-dir output\development\cf_sprint3_smoke

# Run that - chay tren Kaggle qua notebook o tren
.venv\Scripts\python.exe scripts\kaggle_causal_forest_gate.py `
  --data-path <criteo> --frac 0.5 --split sprint3 --profile rare-outcome `
  --output-root output\causal_forest --max-ram-fraction 0.75
```

Chấm điểm chạy ở **local**, vì cần `output/sprint3/confirmation_predictions.npz` (bị
`.gitignore` loại):

```powershell
.venv\Scripts\python.exe scripts\evaluate_causal_forest.py `
  --stage-dir output\causal_forest\sprint3_rare_outcome `
  --score-name cate_causal_forest_rare_outcome.npy --n-boot 500
```

Script đối chiếu `source_index` trùng khít từng phần tử với bảng confirmation Sprint 3, dùng
đúng DR signal đã đóng băng, rồi so với cả chín model bằng paired bootstrap.

**Tài nguyên đo được, lần chạy 13/08/2026 trên Kaggle CPU 31,35 GB:**

| | |
|---|---|
| Wall time | 107,4 phút |
| Peak RSS | 28,46 GB = `0,908` |
| Gate `0,75` | **fail** |
| Artifact | 1.397.959 dòng, finite và aligned — **hợp lệ** |

Gate fail thuần tuý vì ngưỡng RAM, không phải vì artifact hỏng. Bộ nhớ bị chi phối bởi
`n_estimators × max_samples × n_rows` — số subsample giữ cho từng cây — chứ không phải độ sâu
cây; so với `kaggle-safe` tích đó tăng khoảng `5,1` lần.

Muốn qua gate mà **không đổi kết quả**: hạ `--n-jobs`. Đã kiểm chứng fit với `n_jobs=1` và
`n_jobs=2` cho điểm số giống hệt từng bit, nên đây là tham số vận hành chứ không phải tham số
model.

### Gate tài nguyên đã dùng để quyết định chạy

Quy trình dưới đây được đăng ký **trước** khi chạy, dựa trên benchmark tài nguyên ở
[`../report/01_SPRINT_1_FOUNDATION.md`](../report/01_SPRINT_1_FOUNDATION.md) mục 8. Ghi lại vì
nó là lý do ba mốc 20/30/50% tồn tại thay vì chạy thẳng 50%.

1. Đọc RAM/CPU live của session.
2. Chạy profile `kaggle-safe` ở 20%; chỉ tiếp tục nếu peak RAM dưới 75% RAM khả dụng.
3. Chạy 30%; lặp lại điều kiện.
4. Mới chạy 50% với `inference=False`, 200 cây, cross-validation 2-fold, `max_samples=0.25`.
5. Nếu không đạt, dừng ở 20–30% và báo cáo learning curve.

## 9. Web application

```powershell
.venv\Scripts\python.exe scripts\build_champion_scorer.py
.venv\Scripts\python.exe scripts\serve_webapp.py --port 8000
node scripts\smoke_webapp_browser.mjs
```

Mở `http://127.0.0.1:8000`; OpenAPI docs ở `/docs`.

## 10. Kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest tests -q          # 294 test
node scripts\smoke_webapp_browser.mjs                # 30 acceptance check
node scripts\smoke_dashboard_browser.mjs             # 12 acceptance check
```

CI công khai chạy `233` test không cần dữ liệu Criteo, cộng acceptance của dashboard —
`output/product/dashboard.html` là file tracked nên kiểm được. Acceptance của **web app**
không chạy trên CI vì nó cần champion scorer `.joblib` bị `.gitignore` loại.

Nên **CI xanh không thay thế được** lần chạy đầy đủ trên máy có dữ liệu.

## 11. Chạy trong Docker

Cách này bỏ qua bước dựng `.venv` và cố định luôn cả phiên bản hệ điều hành lẫn thư viện
hệ thống — `libgomp1` mà LightGBM cần là một trong số đó.

Image chứa **code và dependency**, không chứa dữ liệu. `data/` và `output/` được mount lúc
chạy. Hai lý do: `data/` có giấy phép riêng của Criteo nên không phân phối lại trong image,
và `output/` phải đọc được ở **trạng thái thật** chứ không phải bản chụp lúc build — nếu
bake vào thì con số trong container và con số trên đĩa trôi khỏi nhau mà không ai biết.

```powershell
docker compose build                 # lan dau khoang 40 phut, phu thuoc toc do mang

docker compose run --rm tests        # 249 test, khoang 20 giay
docker compose run --rm tests-full   # tap day du, can data/ tren dia
docker compose up webapp             # mo http://localhost:8000
```

Image khoảng `1,57 GB`. Đã kiểm: `249/249` test chạy trong container, và `/api/models`
trong container trả về **đúng từng chữ số** như `output/sprint3/confirmation_metrics.csv`
trên đĩa — đó là bằng chứng mount hoạt động chứ không phải bản chụp lúc build.

| Service | Cần `data/` | Mount `output/` | Dùng khi |
|---|:-:|---|---|
| `tests` | không | đọc–ghi | kiểm nhanh môi trường dựng đúng |
| `tests-full` | **có** | đọc–ghi | trước khi phát hành |
| `webapp` | không | **chỉ đọc** | xem sản phẩm |

`webapp` mount `output/` chỉ-đọc vì nó không bao giờ ghi; đó là ràng buộc được cưỡng chế ở
tầng filesystem chứ không chỉ là quy ước.

Trên Linux, nếu `output/` trên máy thuộc về uid khác `1000` thì service ghi thư mục tạm sẽ
lỗi quyền. Chạy kèm uid của bạn:

```bash
docker compose run --rm --user "$(id -u):$(id -g)" tests
```

Hai bộ acceptance trình duyệt **không** chạy trong image: nó không cài Node và Chrome, để
image gọn. Chạy chúng ở host.
