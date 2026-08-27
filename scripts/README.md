# Chỉ mục script

Trang này ghi **vai trò** của từng script. Lệnh chạy theo thứ tự nằm ở
[`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md).

Không script nào được di chuyển khỏi thư mục này: runbook trích dẫn đúng đường dẫn hiện tại,
và đổi đường dẫn sẽ làm mọi lệnh tái lập không chạy được nữa.

Mọi script đều tự thêm repo root vào `sys.path`, nên chạy được từ bất kỳ thư mục nào.

## Đang dùng — phân tích dữ liệu

| Script | Vai trò |
|---|---|
| `run_eda_profile.py` | Đóng băng toàn bộ chẩn đoán dữ liệu vào `output/eda/`: toàn vẹn nguồn, cardinality/sentinel, cân bằng, ATE kèm CI, công suất, heterogeneity theo tầng, prognostic dominance. Phần trình bày ở `notebooks/01_eda_criteo.ipynb`. |

`audit_criteo.py` sinh manifest và balance SMD cho Sprint 1 và vẫn là nguồn của
`output/sprint1/data_manifest.json`; `run_eda_profile.py` không ghi đè lên nó, mà mở rộng
phạm vi chẩn đoán và ghi sang thư mục riêng.

## Đang dùng — vòng cải tiến Sprint 3

| Script | Vai trò |
|---|---|
| `run_oof_experiment.py` | Cross-fitting OOF cho toàn bộ candidate. Entrypoint chính của vòng cải tiến. |
| `compare_improvement_candidates.py` | Dựng ensemble, xếp hạng, chốt shortlist. Không đọc confirmation. |
| `run_sprint3_confirmation.py` | Retrospective confirmation + áp promotion rule. Chạy **đúng một lần**. |
| `run_proxy_diagnostic.py` | Chẩn đoán khi nào proxy xếp hạng đúng theo CATE. |
| `migrate_release_artifacts_v2.py` | Migration idempotent cho registry/provenance, condition 4 và random-policy uncertainty của artifact lịch sử; không fit model. |

## Đang dùng — data optimization v1

| Script | Vai trò |
|---|---|
| `run_oof_experiment.py --protocol configs/data_optimization_protocol_v1.json` | Chạy bảy candidate EDA-driven; lưu protocol path và auxiliary outcome provenance. |
| `compare_improvement_candidates.py --protocol configs/data_optimization_protocol_v1.json` | Áp gate thắng Response trên từng fold seed; sinh `advancement_decision.csv`. |
| `analyze_data_optimization.py` | Gộp EDA, hai seed OOF, paired bootstrap và gate thành `problem_resolution.csv` + `optimization_decision.json`; không fit model, không đọc confirmation. |

## Đang dùng — causal foundation v1

| Script | Vai trò |
|---|---|
| `run_oof_experiment.py --protocol configs/causal_foundation_protocol_v1.json` | Chạy Response/Sentinel, Binary DINA, Anchored R25 và Anchored Pattern R theo cùng OOF contract. |
| `compare_improvement_candidates.py --no-ensembles` | So sánh finalist hai model mà không tạo diagnostic ensemble; contract check bắt buộc cùng source rows/protocol. |
| `merge_oof_runs.py` | Ghép candidate chạy process-isolated; từ chối nếu source, outcome, treatment, nuisance hoặc DR signal khác từng phần tử. |
| `analyze_causal_foundation.py` | Sinh `hypothesis_outcomes.csv`, `budget_deltas.csv` và `analysis_summary.json`; không fit model, không đọc confirmation. |

## Đang dùng — top-tail research v2

| Script | Vai trò |
|---|---|
| `analyze_top_tail_evidence.py` | Audit hậu nghiệm hard budget 1%/2% trên frozen OOF: một simultaneous band cho 20 cells, event support, membership overlap và provenance hashes. Không fit model, không chọn/promotion candidate; từ chối ghi đè output chính thức. |

Full finalist phải chạy tách process trên máy RAM hạn chế, sau đó ghép:

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py `
  --protocol configs\causal_foundation_protocol_v1.json --pool-frac 1 `
  --fold-seed 101 --stage finalist --n-boot 2 --candidates Response `
  --output-dir output\improvement\causal_foundation_finalist_seed101_response
.venv\Scripts\python.exe scripts\run_oof_experiment.py `
  --protocol configs\causal_foundation_protocol_v1.json --pool-frac 1 `
  --fold-seed 101 --stage finalist --n-boot 2 --candidates Response-Sentinel `
  --output-dir output\improvement\causal_foundation_finalist_seed101_sentinel
.venv\Scripts\python.exe scripts\merge_oof_runs.py `
  --run-dir output\improvement\causal_foundation_finalist_seed101_response `
  --run-dir output\improvement\causal_foundation_finalist_seed101_sentinel `
  --output-dir output\improvement\causal_foundation_finalist_seed101 `
  --allow-legacy-manifests
```

`n-boot=2` ở component chỉ hoàn thiện local artifact. Paired inference chính thức chạy một lần sau
khi ghép: 200 draw cho seed 101 và 100 draw cho seed 202.
Flag legacy chỉ tái lập artifact lịch sử trước manifest schema v2; merged output bị gắn
`legacy_diagnostic_not_eligible_for_advancement`. Run mới không được dùng flag này.

## Đang dùng — sản phẩm

| Script | Vai trò |
|---|---|
| `build_champion_scorer.py` | Fit champion trên development pool, lưu joblib cho web app. |
| `serve_webapp.py` | Chạy web app bằng uvicorn. |
| `smoke_webapp_browser.mjs` | Acceptance headless cho web app, **30 check**. Chỉ chạy ở local: cần champion scorer `.joblib` bị `.gitignore` loại. |
| `find_chrome.mjs` | Tìm Chrome hoặc Edge trên Windows, Linux và macOS. Hai script acceptance dùng chung; đặt `CHROME_PATH` để ghi đè. |
| `export_dashboard_data.py` | Dựng payload cho dashboard tĩnh Sprint 2. |
| `build_dashboard.py` | Dựng `dashboard.html` self-contained. |
| `smoke_dashboard_browser.mjs` | Acceptance headless cho dashboard tĩnh, 12 check. **Chạy cả trên CI** vì `dashboard.html` là file tracked. Screenshot tạm được tạo mới và kiểm kích thước mỗi run. |

## Đang dùng — Causal Forest

| Script | Vai trò |
|---|---|
| `train_causal_forest.py` | Fit `CausalForestDML`. Ba profile (`kaggle-safe`, `research`, `rare-outcome`) và hai split (`sprint1`, `sprint3`). |
| `kaggle_causal_forest_gate.py` | Gate tài nguyên và toàn vẹn artifact. **Không** đánh giá chất lượng. |
| `evaluate_causal_forest.py` | Chấm điểm artifact tải về từ Kaggle. Tự phát hiện so được với bảng release Sprint 1 hay bảng confirmation Sprint 3. |
| `analyze_causal_forest_release.py` | Learning curve ba mốc, phân bố điểm và tài nguyên. Đọc artifact đã chấm, **không** fit lại. |
| `plot_causal_forest_release.py` | Năm biểu đồ vào `output/causal_forest/analysis/`. |

Hai trục cấu hình, chọn độc lập nhau:

| `--split` | Fit trên | Predict trên | So được với |
|---|---|---|---|
| `sprint1` | train của sample Sprint 1 | test 30% của sample đó | bảng release năm model, khi `--frac 0.50 --seed 42` |
| `sprint3` | development Sprint 2/3, 5.591.836 dòng | confirmation, 1.397.959 dòng | bảng confirmation Sprint 3, dùng DR signal đã đóng băng |

| `--profile` | `min_samples_leaf` | Sự kiện control mỗi lá | Ghi chú |
|---|---:|---:|---|
| `kaggle-safe` | 500 | 0,145 | Cấu hình đã chạy ba mốc 20/30/50% |
| `research` | 200 | 0,058 | Benchmark tài nguyên Sprint 1; **đi sai hướng** cho outcome hiếm |
| `rare-outcome` | 10.000 | 2,904 | Đăng ký ở `configs/causal_forest_rare_outcome_protocol_v1.json` |

`--train-subsample` chỉ dùng cho smoke code path; giá trị được ghi vào artifact nên một lần
smoke không thể bị nhầm thành run thật.

Runbook: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 8. Kết quả ba mốc:
[`../report/04_CAUSAL_FOREST.md`](../report/04_CAUSAL_FOREST.md). Notebook của lần
chạy: [`../notebooks/03_causal_forest.ipynb`](../notebooks/03_causal_forest.ipynb).

## Tái lập release cũ — vẫn chạy được, đừng đổi đường dẫn

| Script | Sinh ra |
|---|---|
| `audit_criteo.py` | Audit dữ liệu, balance SMD, propensity AUC |
| `tune_five_models.py` | Tuning Sprint 1 trên validation nhiều seed |
| `evaluate_selected_five_models.py` | Final test Sprint 1, 500 bootstrap |
| `compare_release_models.py` | Paired bootstrap giữa 5 model Sprint 1 |
| `build_sprint1_artifacts.py` | Policy decile và score diagnostics Sprint 1 |
| `run_sprint2_local.py` | Toàn bộ Sprint 2 trong một lệnh |
| `rebuild_sprint2_qini_bootstrap.py` | Chạy lại riêng phần Qini bootstrap Sprint 2 |
| `rebuild_sprint2_main_policy.py` | Chạy lại riêng kịch bản policy chính |
| `rebuild_sprint2_policy_budget_curve.py` | Chạy lại riêng đường cong ngân sách |
| `finalize_sprint2_summary.py` | Gộp summary Sprint 2 |

Ba script `rebuild_sprint2_*` tồn tại để chạy lại phần bootstrap **mà không train lại
model**, dùng prediction đã đóng băng. Đây là lý do nâng bootstrap từ 300 lên 500 chỉ tốn
302,6 giây.

## Lịch sử — giữ để truy vết, không dùng cho release mới

| Script | Trạng thái |
|---|---|
| `train_baselines.py` | Lần chạy baseline đầu tiên; điểm số đời đầu nằm ở `output/legacy/`. Nguồn Sprint 1 chính thức là `evaluate_selected_five_models.py`. |
| `build_comparison.py` | Dựng bảng so sánh 6 model theo kế hoạch cũ; Sprint 3 dùng chuỗi `run_oof_experiment` → `compare_improvement_candidates` → `run_sprint3_confirmation`. |
| `bench_harness.py` | Harness đo runtime/RAM thời kỳ đầu. |
| `assess_causal_forest_feasibility.py` | Benchmark tài nguyên Causal Forest 1/5/10/20%; đã dùng để ra quyết định không chạy 50% local. |

## Quy ước chung

- Script **không** ghi đè artifact của sprint khác.
- Script ghi log ra stdout bằng UTF-8; console Windows mặc định cp1252 nên các script mới
  đều gọi `sys.stdout.reconfigure(encoding="utf-8")`.
- Script chạy lâu đều in tiến độ theo fold/candidate để dừng giữa chừng vẫn biết đang ở đâu.
- Đường dẫn output mặc định nằm trong chính script, không hard-code ở nơi khác. Bảng "ai
  ghi vào đâu" ở `output/README.md`.
