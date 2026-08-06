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

### Sprint 3 — vòng cải tiến model và web application

- protocol đăng ký trước: metric chính, gate, promotion rule;
- 3-fold cross-fitting OOF trên 5.591.836 dòng, hai fold seed;
- 12 candidate screening, gồm R‑Learner, DR ablation và Rank‑Learner (ICLR 2026);
- causal Q‑aggregation và hai ensemble baseline;
- experiment registry ghi cả run bị dừng sớm;
- web application có API, batch scoring và export.

Nguồn: [Sprint 3 report](report/SPRINT_3_FINAL_REPORT.md),
[method guide](docs/SPRINT_3_METHOD_GUIDE.md).
Kết quả rà soát code/tài liệu trước lần push đầu tiên:
[Repository audit 31/07/2026](report/archive/REPOSITORY_AUDIT_2026-07-31.md).

## Kết quả Sprint 3

Metric chính là `policy_area_dr`: trung bình conversion tăng thêm trên mỗi khách
hàng ở dải budget 1–30%, chấm bằng doubly robust signal.

| Model | `policy_area_dr` | AUTOC | Qini |
|---|---:|---:|---:|
| Response | 0,000912 | 0,003823 | 0,192989 |
| Ensemble‑QAgg | 0,000911 | 0,003271 | 0,209845 |
| Ensemble‑RankAverage | 0,000908 | 0,003332 | 0,195022 |
| S‑Under7 | 0,000896 | 0,003116 | 0,205904 |
| X‑Renormalized | 0,000890 | 0,003283 | 0,201812 |
| Rank‑K2 | 0,000862 | 0,002454 | 0,184993 |
| Rank‑K1 | 0,000852 | 0,002400 | 0,185657 |
| Rank‑K05 | 0,000848 | 0,002388 | 0,186454 |

**Không challenger nào đạt promotion rule; champion giữ nguyên Response.** Không
challenger nào thắng Response ở cả hai fold seed OOF, và không paired 95% CI nào có
lower bound lớn hơn 0.

Lưu ý metric bất đồng: theo Qini, ba model xếp trên Response; theo metric chính và
AUTOC, Response đứng đầu. Metric hierarchy được đăng ký **trước** khi chạy chính là
để tình huống này không trở thành lựa chọn hậu nghiệm.

Kết quả "một model không phải CATE estimator xếp hạng tốt hơn mọi CATE learner" là
chế độ đã được mô tả trong tài liệu, không phải dị thường: *causal bias–variance
tradeoff* (Fernández-Loría & Provost, JMLR 2022), điều kiện proxy phản ánh dominant
moderator (arXiv 2206.12532), và chính nhóm tạo Criteo đã khuyến nghị dùng `visit`
thay `conversion` vì tín hiệu uplift của `conversion` quá yếu (Diemert et al., AdKDD
2018). Rà soát đầy đủ:
[research landscape](planning/RESEARCH_LANDSCAPE_2026.md).

Tại budget 10%, `value=1`, `cost=0,0005`, Response đạt DR net/customer `0,000856`,
95% CI `[0,000675; 0,001044]`; Δ so random CI `[0,000638; 0,000994]`. Với một triệu
khách hàng, top 10% tương ứng khoảng `906` incremental conversions, CI `[725; 1.094]`.

Các số này là **conversion-equivalent scenario**, không phải actual revenue/profit.

## Demo

Web application đầy đủ tính năng:

```powershell
.venv\Scripts\python.exe scripts\build_champion_scorer.py
.venv\Scripts\python.exe scripts\serve_webapp.py --port 8000
node scripts\smoke_webapp_browser.mjs
```

Mở `http://127.0.0.1:8000`; OpenAPI docs ở `/docs`. Runbook:
[WEBAPP.md](docs/WEBAPP.md). Screenshot:
[webapp_screenshot.png](output/screenshots/webapp_screenshot.png).

App có sáu tab: tổng quan release, so sánh model kèm paired CI, budget/policy
explorer, uplift theo decile và chẩn đoán cân bằng, batch scoring từ CSV, và bảng
bằng chứng kèm experiment registry và export CSV.

Dashboard tĩnh Sprint 2 vẫn dùng được cho bản demo một file:

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

## Cấu trúc chính

```text
src/
  data.py               data contract, split, rare-outcome sampling
  baselines.py          Response, S/T/X/DR và corrected classifiers
  calibration.py        probability restoration, tau-isotonic
  evaluation.py         Qini, AUUC, EUCE, paired bootstrap
  policy.py             top-k, cost-aware, IPW/DR value
  ranking_metrics.py    TOC/RATE/AUTOC, outcome adjustment, paired bootstrap
  policy_evaluation.py  budget-value curve, policy_area_dr, expected-random
  rank_learner.py       pairwise orthogonal ranking (ICLR 2026)
  candidates.py         danh mục candidate dùng chung một feature contract
  ensemble.py           causal Q-aggregation, best-single, rank average
  experiment.py         cross-fitting, resource monitor, registry
  scoring.py            scorer lưu được cho batch scoring
  proxy_diagnostic.py   khi nào proxy xếp hạng đúng theo CATE
scripts/
  run_oof_experiment.py            cross-fitting OOF cho toàn bộ candidate
  compare_improvement_candidates.py ensemble + shortlist
  run_sprint3_confirmation.py      retrospective confirmation + promotion rule
  build_champion_scorer.py         fit và lưu champion scorer
  serve_webapp.py                  chạy web app
  run_proxy_diagnostic.py          chẩn đoán proxy-ordering
  evaluate_causal_forest.py        chấm điểm artifact Causal Forest
  smoke_webapp_browser.mjs         acceptance headless cho web app
  run_sprint2_local.py, rebuild_sprint2_*.py, build_dashboard.py
  kaggle_causal_forest_gate.py
webapp/                 API FastAPI + SPA không CDN
output/                 artifact đã chạy — xem output/README.md
docs/                   method guide, contract, cards, runbook — xem docs/README.md
planning/               kế hoạch và scoping — xem planning/README.md
report/                 Sprint 1/2/3 reports
report/weekly/          sáu báo cáo tiến độ theo tuần
```

Mỗi thư mục lớn có `README.md` riêng ghi vai trò và trạng thái từng file:
[scripts](scripts/README.md) · [output](output/README.md) · [docs](docs/README.md) ·
[planning](planning/README.md) · [report](report/README.md).

## Chạy kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest tests -q          # 139 test
node scripts\smoke_webapp_browser.mjs                # 23 acceptance check
```

## Chạy lại

Sprint 2:

```powershell
.venv\Scripts\python.exe scripts\run_sprint2_local.py `
  --pool-frac 1.0 --n-boot 500 --output-dir output\sprint2
```

Sprint 3 (lệnh đầy đủ trong [báo cáo](report/SPRINT_3_FINAL_REPORT.md) mục 12):

```powershell
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.20 --stage screen `
  --n-boot 300 --output-dir output\improvement\screen
```

Run cần file Criteo v2.1 với SHA‑256:

```text
2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc
```

## Causal Forest — đã chạy xong

Kaggle 20% → 30% → 50% đã chạy và đã chấm điểm. Báo cáo đầy đủ:
[CAUSAL_FOREST_REPORT.md](report/CAUSAL_FOREST_REPORT.md).

Đây là **benchmark riêng**, không phải thành viên của bộ release Sprint 1. Nó chạy sau
khi cả ba sprint đã chốt, dùng chung holdout final test Sprint 1 nên so sánh cặp hợp lệ,
nhưng không đi qua cùng quy trình chọn ứng viên. Bảng release Sprint 1 giữ nguyên năm
model.

So sánh cặp với champion trên 2.096.940 dòng (holdout trùng khít đã kiểm chứng):

| | Causal Forest | Response | Chênh lệch | CI 95% |
|---|---:|---:|---:|---|
| `policy_area_dr` | 0,001006 | 0,001005 | `+4,96e-07` | `[−6,0e-05; 5,8e-05]` |
| Qini | 0,174678 | 0,187886 | `−0,013208` | `[−0,0370; 0,0107]` |

CI chứa 0 trên cả hai metric, nên đây là **hoà**. Champion giữ nguyên Response. Causal
Forest vượt rõ X, DR, T theo metric chính, và không suy biến — 912.579 giá trị điểm phân
biệt.

**Notebook để chạy lại:** [`notebooks/kaggle_causal_forest.ipynb`](notebooks/kaggle_causal_forest.ipynb)
— 23 cell, chạy được `Save & Run All`, không cần restart kernel.

## Đọc theo thứ tự

Bắt đầu bằng [**Sprint 1 report**](report/SPRINT_1_FINAL_REPORT.md) — nền tảng và bảng model, có
trình tự đọc theo thời gian bạn có (15 phút / 1 giờ / nửa ngày), kiến trúc split, giải
thích từng module, metric, model, web app và danh mục bẫy khi đọc kết quả.

Sau đó:

1. [Sprint 3 final report](report/SPRINT_3_FINAL_REPORT.md)
2. [Sprint 3 method guide](docs/SPRINT_3_METHOD_GUIDE.md)
3. [Web app runbook](docs/WEBAPP.md)
4. [Decision contract](docs/DECISION_CONTRACT.md)
5. [Sprint 2 final report](report/SPRINT_2_FINAL_REPORT.md)
6. [Data card](docs/data_cards/CRITEO_V2_1.md) và [model card](docs/model_cards/SPRINT_2_POLICY_RELEASE.md)
7. [Kế hoạch Sprint 3](planning/SPRINT_3_EXECUTION_AND_WEB_PLAN.md)
8. [Bối cảnh nghiên cứu và bài toán lân cận](planning/RESEARCH_LANDSCAPE_2026.md)

Chỉ mục đầy đủ kèm trạng thái từng tài liệu: [docs/README.md](docs/README.md) và
[planning/README.md](planning/README.md).

## Phạm vi suy luận và giới hạn dữ liệu

- Response là ranking policy score, không phải calibrated individual CATE.
- Không quan sát principal stratum cá nhân.
- Balance diagnostics không tự chứng minh randomization; cần upstream provenance.
- Confirmation Sprint 2 đã được quan sát ở Sprint 2 và Sprint 3; kết quả trên tập đó
  là retrospective confirmation, không phải prospective unseen test.
- Không có claim SOTA: không challenger nào trong vòng cải tiến thắng được baseline,
  và benchmark bên ngoài dùng outcome khác nên không so trực tiếp được.
- Criteo không có outcome để kết luận incremental CLV hoặc observed profit.
