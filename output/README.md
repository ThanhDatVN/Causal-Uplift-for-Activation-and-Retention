# Bố cục artifact

Thư mục này chứa **kết quả đã chạy**, không chứa code. Mỗi thư mục con có một vai trò và
một mức tin cậy khác nhau; đừng trộn chúng khi trích số.

## Artifact release — dùng làm nguồn số chính thức

| Thư mục | Sprint | Nội dung |
|---|---|---|
| `sprint1/` | 1 | data manifest, balance SMD, arm summary, policy decile, paired bootstrap, score diagnostics |
| `sprint2/` | 2 | protocol manifest, calibration comparison, paired Qini bootstrap, policy value/sensitivity/budget curve |
| `sprint3/` | 3 | confirmation metrics, paired comparisons, budget curve, promotion decision, protocol manifest |
| `optimization/` | 1 | kết quả tuning và final test 5 model, gồm `final_test_results_sprint1_release_5models.csv` |
| `improvement/` | 3 | registry, OOF metrics theo stage, shortlist, chẩn đoán proxy |

Quy tắc: số trong báo cáo phải truy được về một file trong nhóm này.

## Artifact sản phẩm

| Đường dẫn | Nội dung |
|---|---|
| `dashboard.html` | Dashboard tĩnh Sprint 2, self-contained, mở trực tiếp bằng trình duyệt |
| `dashboard_data.json` | Payload của dashboard tĩnh, schema `sprint2-dashboard-v1` |
| `webapp/` | Champion scorer đã fit (`champion_scorer.joblib`) và metadata cho web app |
| `screenshots/` | Ảnh chụp bằng chứng của dashboard tĩnh và sáu tab web app |

## Artifact phát triển — **không** dùng làm nguồn số

| Thư mục | Vì sao không dùng |
|---|---|
| `improvement/smoke/`, `improvement/smoke_gate/` | Mẫu 0,5–1%, quá ít conversion ở control để xếp hạng model |
| `improvement/screen_visit/` | Outcome `visit` — **estimand khác**, chỉ dùng làm power diagnostic |
| `sprint2_smoke/`, `sprint2_benchmark_10pct/` | Chạy thử pipeline Sprint 2 ở mẫu nhỏ |
| `causal_forest_gate_smoke/` | Code-path smoke 0,1% cho Causal Forest; gate không đánh giá chất lượng |

## Artifact lịch sử

`cate/` và các file rời ở gốc (`qini_comparison.csv`, `qini_curve.png`,
`segments_baseline.csv`, `eda_summary.csv`, `qini_comparison_sprint1.csv`) do các script
đời đầu sinh ra (`train_baselines.py`, `build_comparison.py`, notebook EDA). Chúng được
giữ nguyên vị trí vì script sinh ra chúng ghi vào đúng đường dẫn đó và các báo cáo lịch sử
trích dẫn đúng đường dẫn đó.

Nguồn số Sprint 1 chính thức là `optimization/final_test_results_sprint1_release_5models.csv`,
không phải `qini_comparison.csv`.

## File không được commit

`.gitignore` loại `*.npy` và `*.npz` trong `output/` vì chúng tái lập được và làm repo
nặng. Cụ thể: prediction array của từng model, cache split, và `webapp/*.joblib`.

Muốn dựng lại:

```powershell
.venv\Scripts\python.exe scripts\build_champion_scorer.py        # scorer
.venv\Scripts\python.exe scripts\run_oof_experiment.py --help    # OOF prediction
```

## Ai ghi vào đâu

| Script | Ghi vào |
|---|---|
| `run_sprint2_local.py` | `sprint2/` |
| `run_oof_experiment.py` | `improvement/<stage>/` + `improvement/registry.csv` |
| `compare_improvement_candidates.py` | `improvement/<stage>_comparison/` |
| `run_sprint3_confirmation.py` | `sprint3/` + `improvement/registry.csv` |
| `run_proxy_diagnostic.py` | `improvement/proxy_diagnostic/` |
| `build_champion_scorer.py` | `webapp/` |
| `export_dashboard_data.py`, `build_dashboard.py` | `dashboard_data.json`, `dashboard.html` |
| `kaggle_causal_forest_gate.py` | `causal_forest/preflight_<frac>/` |
| `evaluate_causal_forest.py` | `causal_forest_release/` |
| `smoke_*_browser.mjs` | `screenshots/` |

Không script nào ghi đè artifact của sprint khác.
