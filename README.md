# Đo lường uplift nhân quả và tối ưu policy marketing

Dự án trả lời: **nên target ai dựa trên tác động tăng thêm của treatment, thay vì chỉ dự
đoán ai có khả năng conversion?**

Pipeline dùng [Criteo Uplift Prediction Dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)
(13,98 triệu dòng, randomized incrementality test), so sánh response/CATE learners, đo
uncertainty và phát hành một dashboard policy chạy được.

## Thành quả hiện tại

### Sprint 1 — model/evaluation foundation

- data/schema/balance audit;
- Response, S/T/X‑Learner, DR‑Learner;
- validation nhiều seed và final holdout chung;
- Qini/AUUC cross-check với `scikit-uplift`;
- 500 paired percentile bootstrap;
- Causal Forest resource benchmark.

Nguồn: [Sprint 1 report](report/SPRINT_1_FINAL_REPORT.md).

### Sprint 2 — decision product

- confirmation mới 1.397.959 dòng, không tái sử dụng test Sprint 1;
- X‑Renormalized, τ-isotonic và T‑LocalExact ablation;
- Response top-k champion được chọn trên validation;
- offline policy value bằng IPW/DR, 500 paired bootstrap;
- cost/value sensitivity và break-even;
- dashboard HTML self-contained, 11/11 browser acceptance pass;
- data card, model card, decision contract;
- Kaggle Causal Forest gated package.

Nguồn chính: [Sprint 2 report](report/SPRINT_2_FINAL_REPORT.md).

Kế hoạch vòng cải tiến tiếp theo:
[Sprint 1–2 model improvement plan](planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md).
Kết quả rà soát code/tài liệu trước lần push đầu tiên:
[Repository audit 31/07/2026](report/REPOSITORY_AUDIT_2026-07-31.md).

## Kết quả Sprint 2

| Model | Qini confirmation |
|---|---:|
| X‑Renormalized | 0,191557 |
| X‑Calibrated | 0,188528 |
| Response | 0,182789 |
| T‑LocalExact | 0,117668 |

X‑Renormalized − Response = `0,008768`, paired 95% CI
`[-0,018626; 0,038772]`: chưa đủ bằng chứng thay champion Response đã chọn trên validation.

Tại budget 10%, `value=1`, `cost=0,0005`, Response policy đạt DR net/customer
`0,000799`, 95% CI `[0,000608; 0,000977]`; Δ so random CI
`[0,000582; 0,000928]`.

Các số này là **conversion-equivalent scenario**, không phải actual revenue/profit.

## Demo

Mở trực tiếp [dashboard.html](output/dashboard.html) hoặc build lại:

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

Screenshot: [dashboard_screenshot.png](output/dashboard_screenshot.png).

Dashboard cho phép:

- chọn budget 0/1/5/10/20/30%;
- nhập population, value/conversion và cost/contact;
- xem DR incremental conversion + CI;
- xem break-even cost;
- replay low-cost, high-cost và treat-none;
- export CSV có run ID/assumption fields.

## Cấu trúc chính

```text
src/
  data.py          data contract, split, rare-outcome sampling
  baselines.py     Response, S/T/X/DR và corrected classifiers
  calibration.py   probability restoration, tau-isotonic
  evaluation.py    Qini, AUUC, EUCE, paired bootstrap
  policy.py        top-k, cost-aware, IPW/DR value
scripts/
  run_sprint2_local.py
  rebuild_sprint2_*.py
  export_dashboard_data.py
  build_dashboard.py
  smoke_dashboard_browser.mjs
  kaggle_causal_forest_gate.py
output/sprint2/    release evidence
docs/              method guide, contract, cards, runbook
report/            Sprint 1/2 reports
```

## Chạy kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

## Chạy lại Sprint 2

```powershell
.venv\Scripts\python.exe scripts\run_sprint2_local.py `
  --pool-frac 1.0 --n-boot 500 --output-dir output\sprint2
```

Run cần file Criteo v2.1 với SHA‑256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

## Causal Forest

Local 0,1% code-path smoke đã pass. Kaggle 20% → 30% → 50% chưa chạy vì cần session và
dataset attachment bên ngoài. Không có Causal Forest trong release hiện tại.

Runbook: [KAGGLE_CAUSAL_FOREST.md](docs/KAGGLE_CAUSAL_FOREST.md).

## Đọc theo thứ tự

1. [Sprint 2 final report](report/SPRINT_2_FINAL_REPORT.md)
2. [Decision contract](docs/DECISION_CONTRACT.md)
3. [Method & product guide](docs/SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md)
4. [Data card](docs/data_cards/CRITEO_V2_1.md)
5. [Model card](docs/model_cards/SPRINT_2_POLICY_RELEASE.md)
6. [Kế hoạch cải tiến model Sprint 1–2](planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md)
7. [Sprint 3 roadmap](planning/sprints.md)

## Phạm vi suy luận và giới hạn dữ liệu

- Response là ranking policy score, không phải calibrated individual CATE.
- Không quan sát principal stratum cá nhân.
- Balance diagnostics không tự chứng minh randomization; cần upstream provenance.
- Confirmation không được dùng để tune.
- Criteo không có outcome để kết luận incremental CLV hoặc observed profit.
