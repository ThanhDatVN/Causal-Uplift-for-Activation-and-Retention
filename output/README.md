# Bố cục artifact

Thư mục này chứa **kết quả đã chạy**, không chứa code. Bố cục chia theo **vai trò**, vì
mỗi nhóm có một mức tin cậy khác nhau và trộn chúng khi trích số là lỗi đã xảy ra thật.

```text
output/
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
| `holdout/` | 1 | `final_test_yt.npz` — 2.096.940 dòng `Y` và `T`. Mọi model so với nhau đều chấm trên đúng file này. **Đây là mảng duy nhất được commit** (259 KB sau khi nén int8), để ai clone repo cũng tái lập được bảng so sánh cặp |
| `sprint1/` | 1 | data manifest, balance SMD, arm summary, policy decile, paired bootstrap, score diagnostics |
| `sprint2/` | 2 | protocol manifest, calibration comparison, paired Qini bootstrap, policy value/sensitivity/budget curve |
| `sprint3/` | 3 | confirmation metrics, paired comparisons, budget curve, promotion decision, protocol manifest |
| `optimization/` | 1 | kết quả tuning và final test năm model. Điểm số release ở `optimization/cate/*_sprint1_release.npy` |
| `improvement/` | 3 | registry, OOF metrics theo stage, shortlist, chẩn đoán proxy |
| `causal_forest/` | — | `preflight_{0p2,0p3,0p5}/` ba mốc Kaggle · `release/` bảng metric và so sánh cặp · `analysis/` learning curve và năm biểu đồ |

Quy tắc: số trong báo cáo phải truy được về một file trong nhóm này.

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

Repo mang **116 file, 2,3 MB** — toàn bộ CSV, JSON, PNG, HTML và manifest. Đủ để đọc mọi
kết quả mà không cần chạy lại gì.

Bị chặn: **67 file, 1,67 GB** mảng dự đoán `.npy` và `.npz`. Chúng tái tạo lại được từ dữ
liệu gốc cộng cấu hình đã chốt, và commit chúng làm repo nặng gấp bảy trăm lần.

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
| `run_sprint3_confirmation.py` | `sprint3/` |
| `kaggle_causal_forest_gate.py` | `causal_forest/preflight_<frac>/` |
| `evaluate_causal_forest.py` | `causal_forest/release/` |
| `analyze_causal_forest_release.py` | `causal_forest/analysis/` |
| `plot_causal_forest_release.py` | `causal_forest/analysis/*.png` |
| `export_dashboard_data.py`, `build_dashboard.py` | `product/` |
| `build_champion_scorer.py` | `product/webapp/` |
