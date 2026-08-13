# Bố cục artifact

Thư mục này chứa **kết quả đã chạy**, không chứa code. Bố cục chia theo **vai trò**, vì
mỗi nhóm có một mức tin cậy khác nhau và trộn chúng khi trích số là lỗi đã xảy ra thật.

```text
output/
├── eda/             chẩn đoán dữ liệu — nguồn số của notebook 01
├── holdout/         tập test chung của Sprint 1 — mọi so sánh model dựa trên đây
├── sprint1/         nguồn số chính thức
├── sprint2/
├── sprint3/
├── optimization/    tuning và điểm số release của năm model
├── improvement/     registry, OOF metrics, chẩn đoán — Sprint 3
├── causal_forest/   ba mốc Kaggle, bảng so sánh, phân tích
├── product/         dashboard, web app, ảnh chụp
├── development/     smoke và benchmark — không dùng làm nguồn số
└── legacy/          artifact đời đầu, số đã bị thay thế
```

## Nguồn số chính thức

| Thư mục | Sprint | Nội dung |
|---|---|---|
| `eda/` | — | Chẩn đoán dữ liệu do `scripts/run_eda_profile.py` sinh, chạy trên toàn bộ 13.979.592 dòng. `run_manifest.json` ghi SHA-256 file nguồn, seed và phiên bản thư viện; notebook 01 assert khớp với file này trước khi diễn giải bất cứ số nào |
| `holdout/` | 1 | `final_test_yt.npz` — 2.096.940 dòng `Y` và `T`. Mọi model so với nhau đều chấm trên đúng file này. **Đây là mảng duy nhất được commit** (259 KB sau khi nén int8), để ai clone repo cũng tái lập được bảng so sánh cặp |
| `sprint1/` | 1 | data manifest, balance SMD, arm summary, policy decile, paired bootstrap, score diagnostics |
| `sprint2/` | 2 | protocol manifest, calibration comparison, paired Qini bootstrap, policy value/sensitivity/budget curve |
| `sprint3/` | 3 | confirmation metrics, paired comparisons, budget curve, promotion decision, protocol manifest |
| `optimization/` | 1 | kết quả tuning và final test năm model. Điểm số release ở `optimization/cate/*_sprint1_release.npy` |
| `improvement/` | 3 + data optimization/causal foundation | registry, OOF metrics theo stage, shortlist/gate, chẩn đoán và full finalist |
| `causal_forest/` | — | `preflight_{0p2,0p3,0p5}/` ba mốc Kaggle · `release/` bảng metric và so sánh cặp · `analysis/` learning curve và năm biểu đồ |

Quy tắc: số trong báo cáo phải truy được về một file trong nhóm này.

## Bên trong `eda/`

| File | Nội dung |
|---|---|
| `run_manifest.json` | SHA-256 file nguồn, schema contract, seed, phiên bản thư viện, thời gian chạy, và toàn bộ chỉ số tóm tắt |
| `eda_summary.csv` | 26 chỉ số headline — notebook 01 assert khớp với bảng này ở mục 1.1 |
| `feature_profile.csv` | Cardinality, `mode_share`, skew/kurtosis, số bin phân vị hiệu dụng của `f0`–`f11` |
| `sentinel_mask_agreement.csv` | Ma trận 12×12 tỉ lệ trùng mask sentinel. Bốn ô bằng `1,00` là bốn cặp dùng chung nguồn missingness |
| `sentinel_patterns.csv`, `sentinel_observed_per_row.csv` | 53 pattern missingness và phân bố số đặc trưng quan sát được mỗi dòng |
| `balance_smd.csv` | SMD và KS cho từng đặc trưng, xếp theo `abs_smd` giảm dần |
| `propensity_overlap_bins.csv`, `sample_representativity.csv` | Positivity theo bin, và sai lệch do lấy mẫu 5% |
| `arm_outcome_summary.csv`, `average_treatment_effect.csv` | Đếm sự kiện theo arm; ATE và risk ratio kèm CI 95% cho `conversion`/`visit`/`exposure` |
| `power_analysis.csv` | MDE và cỡ mẫu cần cho các mức hiệu ứng mục tiêu |
| `post_treatment_leakage.csv` | Bằng chứng số cho việc `visit`/`exposure` là biến hậu can thiệp |
| `effect_by_feature_bin.csv`, `heterogeneity_by_feature.csv` | Hiệu ứng theo phân vị từng đặc trưng, kèm Cochran `Q` và `I²` |
| `effect_by_sentinel_pattern.csv` | Hiệu ứng theo pattern missingness |
| `prognostic_dominance.json` | Tương quan mô tả trên 30 bin chồng lấn; suy luận riêng theo từng feature và 26 pattern sentinel rời nhau, gồm risk ratio và `Q` trên hai thang đo |

`run_eda_profile.py` ghi **riêng** vào thư mục này, không đụng `sprint1/data_manifest.json`
và `sprint1/balance_smd.csv` do `audit_criteo.py` sinh. Hai bộ dùng cùng công thức SMD nên
số khớp nhau; tách thư mục để lệnh tái lập trong báo cáo Sprint 1 vẫn trỏ đúng chỗ cũ.

## Hai file dễ nhầm nhau

| File | Là gì |
|---|---|
| `holdout/final_test_yt.npz` | Final test Sprint 1. Dùng để so **mọi** model với nhau |
| `causal_forest/preflight_*/holdout_test_yt.npz` | Holdout riêng của từng mốc Kaggle. Chỉ mốc `0p5` trùng khít file trên |

Tên khác nhau là cố ý. Lẫn hai file này thì mốc 20% và 30% sẽ bị đem so với bảng release,
mà chúng nằm trên tập test hoàn toàn khác.

## Sản phẩm

| Đường dẫn | Nội dung |
|---|---|
| `product/dashboard.html` | Dashboard tĩnh Sprint 2, self-contained, mở trực tiếp bằng trình duyệt |
| `product/dashboard_data.json` | Payload của dashboard, schema `sprint2-dashboard-v1` |
| `product/webapp/` | Champion scorer đã fit và metadata cho web app |
| `product/screenshots/` | Ảnh chụp bằng chứng của dashboard và sáu tab web app |

## Không dùng làm nguồn số

| Thư mục | Vì sao |
|---|---|
| `development/sprint2_smoke/`, `development/sprint2_benchmark_10pct/` | Chạy thử pipeline Sprint 2 ở mẫu nhỏ |
| `development/causal_forest_gate_smoke/` | Code-path smoke 0,1%; gate không đánh giá chất lượng |
| `improvement/smoke/`, `improvement/smoke_gate/` | Mẫu 0,5–1%, quá ít conversion ở control để xếp hạng model |
| `improvement/screen_visit/` | Outcome `visit` — **estimand khác**, chỉ dùng làm power diagnostic |
| `improvement/data_opt_smoke/` | Code-path smoke 2%; không dùng để chọn model |
| `improvement/causal_foundation_smoke/` | Code-path smoke 1%; chỉ 16 control conversions, không dùng để chọn model |

## Data optimization v1

| Đường dẫn | Vai trò |
|---|---|
| `improvement/data_opt_screen_seed101/` | Development OOF screen chính, 838.776 dòng, 200 bootstrap |
| `improvement/data_opt_screen_seed202/` | Development OOF seed phụ, cùng dòng, 30 bootstrap kiểm tra dấu |
| `improvement/data_opt_comparison/candidate_aggregate.csv` | Xếp hạng trung bình hai seed |
| `improvement/data_opt_comparison/paired_comparisons.csv` | Paired interval trên seed chính |
| `improvement/data_opt_comparison/advancement_decision.csv` | Gate thắng Response trên từng seed |
| `improvement/data_opt_comparison/problem_resolution.csv` | Ánh xạ vấn đề → can thiệp → kết quả |
| `improvement/data_opt_comparison/optimization_decision.json` | Quyết định cuối máy đọc được; Response giữ champion, Response-Sentinel đi tiếp |

Đây là development evidence. Không thư mục nào trong nhóm này là confirmation hay release.

## Causal foundation v1

| Đường dẫn | Vai trò |
|---|---|
| `improvement/causal_foundation_screen_seed101/` | OOF screen 15%, 838.776 dòng, seed chính, 200 bootstrap |
| `improvement/causal_foundation_screen_seed202/` | Cùng source rows, fold seed phụ, 100 bootstrap |
| `improvement/causal_foundation_comparison/` | Aggregate, screen advancement gate và diagnostic ensembles |
| `improvement/causal_foundation_finalist_seed101/` | OOF full đã ghép/contract-check cho Response và Response-Sentinel |
| `improvement/causal_foundation_finalist_seed202/` | OOF full seed phụ đã ghép/contract-check |
| `improvement/causal_foundation_finalist_comparison/` | Full aggregate, gate và paired CI seed 101 (200 draw) |
| `improvement/causal_foundation_finalist_seed202_comparison/` | Paired CI seed 202 (100 draw) |
| `improvement/causal_foundation_analysis/` | Hypothesis outcomes, budget deltas và quyết định máy đọc được |
| `improvement/causal_foundation_*attempt*/` | Resource-stop audit trail; không dùng để xếp hạng |

Kết luận: không causal candidate qua screen stability; Response-Sentinel qua screen nhưng không qua
full stability. Đây là development evidence, không phải randomized confirmation mới.

## Top-tail research v2

| Đường dẫn | Vai trò |
|---|---|
| `improvement/top_tail_research_v2/analysis_summary.json` | Decision, inference scope, protocol/input hashes, bootstrap seed và code state |
| `improvement/top_tail_research_v2/simultaneous_tail_differences.csv` | 20 paired model × seed × budget contrasts với pointwise và simultaneous intervals |
| `improvement/top_tail_research_v2/tail_event_support.csv` | Exact hard-k row/event count theo arm và tie size tại cutoff |
| `improvement/top_tail_research_v2/tail_membership_overlap.csv` | Overlap/Jaccard giữa fold seed 101 và 202 |
| `improvement/top_tail_research_v2_attempt*/` | Audit trail trước khi provenance/overwrite guard hoàn chỉnh; không phải nguồn số ưu tiên |

Kết luận: không simultaneous lower bound nào của causal candidate vượt 0; champion vẫn là Response.
Interval có điều kiện trên frozen OOF scores và không chứa model-refitting uncertainty.

## Artifact đời đầu

`legacy/` chứa kết quả lần chạy đầu tiên, đã bị thay thế:

| Đường dẫn | Đã bị thay bởi |
|---|---|
| `legacy/first_run_scores/cate_*.npy` | `optimization/cate/*_sprint1_release.npy` |
| `legacy/qini_comparison.csv`, `legacy/qini_comparison_sprint1.csv` | `report/SPRINT_1_FINAL_REPORT.md` mục 6 |
| `legacy/qini_curve.png`, `legacy/segments_baseline.csv`, `legacy/eda_summary.csv` | Artifact tương ứng trong `sprint1/` |

**Chỗ dễ trích nhầm nhất:** `legacy/first_run_scores/cate_response.npy` cho Qini
`0,179299`, còn điểm release `optimization/cate/cate_response_sprint1_release.npy` cho
`0,187886`. Hai lần chạy khác nhau; chỉ số sau là chính thức. Đây là lý do hai bộ điểm
được tách hẳn thư mục thay vì để cạnh nhau.

## Cái gì lên git, cái gì không

Git giữ các artifact đọc được trực tiếp — CSV, JSON, PNG, HTML và manifest — đủ để
đọc kết quả mà không cần fit lại model.

Các mảng dự đoán/cache lớn `.npy` và `.npz` bị chặn. Chúng tái tạo lại được từ dữ
liệu gốc cộng cấu hình đã chốt; cache split còn có manifest/hash để phát hiện stale
hoặc corruption trước khi tái sử dụng.

Ngoại lệ duy nhất là `holdout/final_test_yt.npz`. Nó chỉ chứa hai mảng nhị phân nên nén
`int8` xuống còn 259 KB — từ 32 MB, nhỏ hơn 126 lần. Giữ nó lại vì không có nó thì không
ai tái lập được bảng so sánh cặp mà không phải chạy lại toàn bộ pipeline.

Ngoài ra chặn hoàn toàn `development/` (smoke và benchmark), và ba file trong `legacy/`
đã bị thay thế.

## Script nào ghi ra đâu

| Script | Ghi vào |
|---|---|
| `evaluate_selected_five_models.py` | `optimization/` |
| `build_sprint1_artifacts.py` | `sprint1/` |
| `run_sprint2_local.py` | `sprint2/` |
| `run_oof_experiment.py` | `improvement/<stage>/` |
| `analyze_data_optimization.py` | `improvement/data_opt_comparison/` |
| `merge_oof_runs.py` | `improvement/causal_foundation_finalist_seed*/` |
| `analyze_causal_foundation.py` | `improvement/causal_foundation_analysis/` |
| `analyze_top_tail_evidence.py` | `improvement/top_tail_research_v2/` |
| `run_sprint3_confirmation.py` | `sprint3/` |
| `kaggle_causal_forest_gate.py` | `causal_forest/preflight_<frac>/` |
| `evaluate_causal_forest.py` | `causal_forest/release/` |
| `analyze_causal_forest_release.py` | `causal_forest/analysis/` |
| `plot_causal_forest_release.py` | `causal_forest/analysis/*.png` |
| `export_dashboard_data.py`, `build_dashboard.py` | `product/` |
| `build_champion_scorer.py` | `product/webapp/` |
