# Bối cảnh nhanh cho agent/người mới đọc repo

## Mục tiêu

Project dùng Criteo randomized campaign để xếp hạng khách hàng theo incremental
conversion do quảng cáo. Estimand là CATE của `conversion`; không dùng `visit` và
`exposure` vì đây là post-treatment variables.

## Trạng thái chính thức — 29/07/2026

Sprint 1 đã chạy lại từ đầu:

- audit 13.979.592 dòng;
- sample 50%; bên trong sample dùng fit/validation/test 56/14/30, tương đương khoảng
  28/7/15% full data, stratify treatment–outcome;
- candidate selection bằng validation seeds 43/44/45;
- release năm model trên 50% dữ liệu, chung test 2.096.940 dòng;
- 500 bootstrap cho CI, paired bootstrap cho model differences;
- policy deciles và benchmark Causal Forest.

Release configs: `configs/sprint1_release_5models.json`.

Release Qini:

| Model | Qini |
|---|---:|
| Response baseline | 0.187886 |
| S baseline | 0.177204 |
| X under7, classifier + fixed propensity + xấp xỉ `1/k` | 0.167168 |
| DR baseline | 0.153967 |
| T baseline | 0.142021 |

Chỉ cải tiến X vượt baseline trong final ablation. Response đứng đầu ranking nhưng
không phải CATE estimator đầy đủ. Response chỉ được so sánh theo các metric được báo cáo;
không suy rộng kết quả sang tiêu chí chưa đánh giá.

## Tài liệu và artifact có hiệu lực

- `report/SPRINT_1_FINAL_REPORT.md`
- `docs/SPRINT_1_THEORY_AND_METHOD_GUIDE.md`
- `docs/KAGGLE_CAUSAL_FOREST.md`
- `output/sprint1/`
- `output/optimization/*sprint1_release*`

Các kết quả trong `report/week-01/`, notebook, HTML explainer và dashboard có thể là
historical. Không lặp lại claim “top 10% giữ 85% uplift”; release estimate là 72,7%.

## Causal Forest

Không chạy thẳng 50%. Benchmark 20% research profile đạt peak 8,16 GB; dự phóng 50%
17,5 GB, budget bảo thủ 24 GB. Trên Kaggle đọc RAM/CPU live, chạy `kaggle-safe` 20%,
sau đó 30%, chỉ chạy 50% nếu peak RAM dưới 75%.

## Sprint 2 canonical release (31/07/2026)

- Official report: `report/SPRINT_2_FINAL_REPORT.md`.
- Official artifacts: `output/sprint2/`.
- Dashboard: `output/dashboard.html`, schema `sprint2-dashboard-v1`.
- Complementary pool split 60/20/20; confirmation 1.397.959 rows. Tập này đã được dùng
  cho báo cáo Sprint 2 nên các vòng model mới phải gọi là retrospective confirmation.
- Champion is Response top-k selected on validation.
- X-Renormalized minus Response confirmation Qini = 0.008768,
  paired 500-bootstrap CI [-0.018626, 0.038772].
- At budget 10%, value=1, cost=0.0005, Response DR net/customer = 0.000799,
  CI [0.000608, 0.000977].
- All value/cost outputs are assumption scenarios, not actual profit.
- Causal Forest Kaggle 20/30/50 remains pending. Local 0.1% is code-path smoke only.
- Resource-gated profile has `inference=False`; do not require or claim `effect_interval()`.

## Quy tắc khi sửa/chạy

- Không tune thêm trên test Sprint 1.
- Giữ split/feature contract để so sánh công bằng.
- Dùng Qini/AUUC + calibration + policy value; không dùng classification accuracy làm
  metric chính.
- Mọi claim model A hơn B phải dùng paired CI.
- Under-sampling formula/xấp xỉ phải dẫn Nyberg et al.; không coi scale `k` là đẳng thức.
- Score âm là dự đoán model-dependent, không phải principal stratum quan sát được.
- Dashboard release chỉ đọc `output/sprint2/` thông qua `output/dashboard_data.json`.
- Vòng cải tiến model mới phải theo
  `planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md`.

## Văn phong tài liệu

- Dùng metric, split, interval, runtime hoặc trạng thái artifact thay cho tính từ tự đánh giá.
- Không dùng emoji, câu hỏi tu từ, chữ in hoa để nhấn mạnh hoặc giọng quảng bá.
- Viết “đạt/không đạt gate”, “CI chứa/không chứa 0”, “đã/chưa có artifact”.
- Phân biệt rõ biến quan sát, estimate, input kịch bản và kết quả semi-synthetic.
- Tên phương pháp như `honest splitting` và `doubly robust` được giữ vì là thuật ngữ kỹ thuật.

## Câu lệnh kiểm tra nhanh

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe scripts\audit_criteo.py --balance-frac 0.05 --seed 42
.venv\Scripts\python.exe scripts\evaluate_selected_five_models.py `
  --selected configs\sprint1_release_5models.json --frac 0.50 --n-boot 500
```
