# Báo cáo Sprint 2 — Từ mô hình causal đến policy và dashboard

**Run ID:** `sprint2-local-exact-calibration-v1`
**Trạng thái:** Local pipeline + dashboard hoàn thành; Causal Forest Kaggle pending
**Nguồn số chính thức:** `output/sprint2/`

## 1. Kết quả điều hành

Sprint 2 đã biến nghiên cứu uplift thành sản phẩm quyết định chạy được:

- tạo confirmation set mới 1.397.959 dòng, không tái sử dụng final test Sprint 1;
- thử X‑Learner renormalization, τ-isotonic và exact local restoration;
- khóa Response top-k làm operational champion từ validation;
- chấm policy bằng IPW/DR và 500 paired bootstrap;
- tạo dashboard self-contained, 11/11 browser acceptance checks pass;
- đóng gói gate Causal Forest cho Kaggle, nhưng không claim cloud result khi chưa chạy.

Kết quả model: X‑Renormalized có Qini confirmation cao nhất (`0,191557`),
nhưng hơn Response `0,008768` với CI `[-0,018626; 0,038772]`. Chưa đủ bằng chứng đổi
champion đã chọn trên validation.

## 2. Data protocol và chống leakage

Sprint 1 đã dùng stratified 50%, seed 42. Sprint 2 tái dựng đúng sample đó và chỉ lấy
phần bù:

| Split | Rows | Treatment rate | Conversion rate |
|---|---:|---:|---:|
| fit | 4.193.877 | 0,850000 | 0,002917 |
| validation | 1.397.959 | 0,850000 | 0,002916 |
| confirmation | 1.397.959 | 0,850001 | 0,002916 |

Hash của ba source-index được lưu trong manifest. Pipeline Sprint 2 không đọc prediction
hay Y/T của final test Sprint 1.

## 3. Phương pháp và evidence audit

| Thành phần | Nguồn đã đọc | Phạm vi dùng |
|---|---|---|
| Stratified undersampling, renormalization, τ-isotonic, exact restoration | Nyberg & Klami 2023, mục 3.1–3.3 | Công thức và giới hạn compatibility |
| S/T/X learner | Künzel et al. 2019 | Cấu trúc meta-learner |
| DR policy value | Dudík et al. 2011 | Outcome + propensity correction |
| Statistical policy learning | Athey & Wager 2021 | Policy value/uncertainty framing |
| CausalForestDML API | EconML 0.16 docs | cross-validation, honest forest, inference/resource profile |
| Dataset provenance | Criteo AI Lab | Randomized incrementality source |

Nguồn trực tiếp:

- Nyberg & Klami,
  [Data Mining and Knowledge Discovery 2023](https://link.springer.com/article/10.1007/s10618-023-00917-9).
- Künzel et al.,
  [PNAS 2019](https://doi.org/10.1073/pnas.1804597116).
- Dudík et al.,
  [ICML 2011](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/).
- Athey & Wager,
  [Econometrica 2021](https://doi.org/10.3982/ECTA15732).
- [EconML CausalForestDML 0.16](https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html).
- [Criteo dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/).

Không có claim nào rằng Nyberg đã empirical-validate exact correction bên trong
X‑Learner. Ablation ở mẫu 10% không vượt baseline; release chuyển exact restoration sang
T‑Learner/double-classifier đúng phạm vi Eq. 12.

## 4. Model results

| Model | Qini | AUUC | EUCE |
|---|---:|---:|---:|
| X‑Renormalized | 0,191557 | 0,006189 | 0,000462 |
| X‑Calibrated | 0,188528 | 0,006084 | 0,000240 |
| Response | 0,182789 | 0,005912 | không áp dụng |
| T‑LocalExact | 0,117668 | 0,003798 | 0,000957 |

Paired Qini:

| A − B | Δ | 95% CI | Kết luận |
|---|---:|---:|---|
| X‑Renormalized − Response | 0,008768 | [-0,018626; 0,038772] | chưa phân biệt |
| X‑Calibrated − X‑Renormalized | -0,003029 | [-0,010774; 0,004700] | chưa phân biệt |
| T‑LocalExact − X‑Renormalized | -0,073889 | [-0,107381; -0,035891] | CI nằm hoàn toàn dưới 0 |

Calibration cải thiện scale EUCE nhưng không chứng minh ranking tốt hơn. Kết quả cho thấy
phương pháp “exact” không tự động cải thiện ranking so với phép xấp xỉ đang dùng cho rare
outcome.

## 5. Policy result

Main scenario: budget 10%, value/conversion = 1, cost/contact = 0,0005.

| Policy | DR net/customer | 95% CI | Δ vs random 95% CI |
|---|---:|---:|---:|
| Response top-k | 0,000799 | [0,000608; 0,000977] | [0,000582; 0,000928] |
| X‑Renormalized top-k | 0,000825 | [0,000649; 0,001001] | [0,000611; 0,000951] |
| X‑Calibrated top-k | 0,000826 | [0,000652; 0,001004] | [0,000611; 0,000953] |
| T‑LocalExact top-k | 0,000671 | [0,000501; 0,000829] | [0,000464; 0,000777] |
| Random top-k | 0,000040 | [-0,000017; 0,000096] | — |

Policy point estimates không được dùng để đổi champion sau confirmation. Product dùng
Response vì selection contract đã khóa.

Với một triệu khách hàng, Response top 10% tương ứng khoảng `848,9` incremental
conversions gross, 95% CI `[657,8; 1.027,0]`. Đây là phép scale với assumption population
tương tự confirmation, không phải forecast đã deploy.

## 6. Product output

- `output/product/dashboard.html`: app demo self-contained.
- `output/product/dashboard_data.json`: schema release.
- `output/product/screenshots/dashboard_screenshot.png`: bằng chứng visual.
- `scripts/smoke_dashboard_browser.mjs`: replay bốn scenario.
- `docs/DECISION_CONTRACT.md`: rule, formula và guardrails.
- data/model cards trong `docs/data_cards/` và `docs/model_cards/`.

Dashboard chỉ dùng artifact freeze, không train/download implicit.

## 7. Infrastructure

Full local Sprint 2:

- model/policy pipeline runtime `395,9` giây; nâng Qini inference từ 300 lên 500
  resamples bằng frozen predictions cần thêm `302,6` giây;
- 6 physical / 12 logical CPUs;
- total RAM 15,19 GB;
- peak process RSS 2,74 GB;
- minimum system available RAM 1,81 GB.

Causal Forest local smoke 0,1% pass. Kaggle run vẫn cần external session/dataset
attachment; xem `docs/KAGGLE_RUNBOOK_COMPLETE.md`. `inference=False` của safe profile có
nghĩa không yêu cầu `effect_interval()`.

## 8. Quality evidence

- formula inversion tests cho undersampling;
- synthetic truth tests cho IPW/DR;
- split disjoint/exhaustive test;
- clone/finite tests cho exact outcome adapters;
- multi-model paired bootstrap pairing test;
- dashboard 11/11 headless-browser acceptance;
- full pytest `49/49` pass ở release audit cuối.

## 9. Hạng mục chưa hoàn thành và phạm vi không được suy rộng

- Causal Forest Kaggle 20/30/50 chưa chạy. *(Cập nhật 06/08/2026: đã chạy xong sau khi
  báo cáo này chốt. Kết quả và giới hạn diễn giải ở `report/CAUSAL_FOREST_REPORT.md`;
  kết luận của Sprint 2 giữ nguyên vì nó phản ánh bằng chứng có tại thời điểm chốt.)*
- Chưa có production A/B test của learned policy.
- Chưa có actual monetary outcome hoặc long-term CLV.
- Report này được tạo trước commit đầu tiên; trạng thái repository hiện tại được ghi trong
  `report/archive/repository-audit-2026-07-31.md`.
- Random comparator là một ranking cố định bằng seed 42; CI hiện tại chưa tích hợp biến
  thiên qua nhiều random-policy seed.
- Demo video/GIF thuộc Sprint 3 packaging.

## 10. Lệnh tái lập

```powershell
.venv\Scripts\python.exe scripts\run_sprint2_local.py --pool-frac 1 --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_qini_bootstrap.py --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_main_policy.py --n-boot 500
.venv\Scripts\python.exe scripts\rebuild_sprint2_policy_budget_curve.py --n-boot 500
.venv\Scripts\python.exe scripts\finalize_sprint2_summary.py
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
.venv\Scripts\python.exe -m pytest tests -q
```

## 11. Bàn giao sang Sprint 3

Ưu tiên: clean-run/CI, README, video 60–90 giây, final report/slides,
link audit và release tag sau khi repository có commit. Incremental CLV chỉ mở sau khi
causal product được đóng gói; không gắn revenue giả vào Criteo.
