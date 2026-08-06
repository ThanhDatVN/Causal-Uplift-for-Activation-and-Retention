# Chỉ mục script

27 script, nhóm theo vai trò. Không script nào được di chuyển khỏi thư mục này: các lệnh
tái lập trong `report/SPRINT_1|2|3_FINAL_REPORT.md` trích dẫn đúng đường dẫn hiện tại, và
đổi đường dẫn sẽ làm lệnh trong báo cáo lịch sử không chạy được nữa.

Mọi script đều tự thêm repo root vào `sys.path`, nên chạy được từ bất kỳ thư mục nào.

## Đang dùng — vòng cải tiến Sprint 3

| Script | Vai trò |
|---|---|
| `run_oof_experiment.py` | Cross-fitting OOF cho toàn bộ candidate. Entrypoint chính của vòng cải tiến. |
| `compare_improvement_candidates.py` | Dựng ensemble, xếp hạng, chốt shortlist. Không đọc confirmation. |
| `run_sprint3_confirmation.py` | Retrospective confirmation + áp promotion rule. Chạy **đúng một lần**. |
| `run_proxy_diagnostic.py` | Chẩn đoán khi nào proxy xếp hạng đúng theo CATE. |

## Đang dùng — sản phẩm

| Script | Vai trò |
|---|---|
| `build_champion_scorer.py` | Fit champion trên development pool, lưu joblib cho web app. |
| `serve_webapp.py` | Chạy web app bằng uvicorn. |
| `smoke_webapp_browser.mjs` | Acceptance headless cho web app, 23 check. |
| `export_dashboard_data.py` | Dựng payload cho dashboard tĩnh Sprint 2. |
| `build_dashboard.py` | Dựng `dashboard.html` self-contained. |
| `smoke_dashboard_browser.mjs` | Acceptance headless cho dashboard tĩnh, 11 check. |

## Đang dùng — Causal Forest

| Script | Vai trò |
|---|---|
| `train_causal_forest.py` | Fit `CausalForestDML` theo profile `kaggle-safe`. |
| `kaggle_causal_forest_gate.py` | Gate tài nguyên và toàn vẹn artifact. **Không** đánh giá chất lượng. |
| `evaluate_causal_forest.py` | Chấm điểm artifact tải về từ Kaggle. Tự phát hiện có so được với bảng release không. |

Runbook: `docs/KAGGLE_RUNBOOK_COMPLETE.md`.

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
| `train_baselines.py` | Lần chạy baseline đầu tiên; kết quả ở `report/archive/week-01-baseline-results.md`. Nguồn Sprint 1 chính thức là `evaluate_selected_five_models.py`. |
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
