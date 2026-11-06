# Demo script — 4 minutes (predictive track)

> Archived walkthrough. Use the current [English portfolio release](../PORTFOLIO_RELEASE_2026_EN.md) and [three-minute script](../PORTFOLIO_INTERVIEW_WALKTHROUGH_EN.md). This older script refers to a 30-day risk horizon that IBM does not validate. The refreshed index computes `ENGINEERING_FOUNDATION` from engineering gates only; causal evaluator confirmation and the partner trial remain unmet.

> Cập nhật 21/09/2026: phần 3:15–4:00 dùng số đo mới nhất, và có thêm một nhánh 60 giây cho decision console. Bản demo cho causal/decision track nằm trong [VERIFICATION_V4_1.md](VERIFICATION_V4_1.md).

## 0:00–0:40 — Problem and guardrail

“Tại snapshot đầu tháng, hệ thống xếp hạng nguy cơ churn 30 ngày và giúp analyst chọn contact list theo
capacity/assumption. IBM sample không có timestamp hay treatment/control, nên mọi business value là mô
phỏng; model này không chứng minh offer sẽ cứu khách.”

Mở `README.md`, sơ đồ kiến trúc và data card. Nêu 7.043 customers, prevalence 26,54%, raw/split hash.

## 0:40–1:20 — Data and notebook

Mở `notebooks/01_data_audit_eda.ipynb`: 11 blanks đều tenure=0, target imbalance, Contract Cramér's V
0,410, cohort 0–6 tháng + month-to-month churn 55,2%. Nhấn mạnh association không phải cause.

Mở `02_leak_free_processing.ipynb`: frozen manifest, in-fold imputation/OHE/scaling, unknown category,
không dùng ID/target làm feature.

## 1:20–2:15 — Benchmark decision

Mở benchmark report. Dummy chứng minh accuracy trap. Logistic CV AP 0,6592; CatBoost 0,6680. Dù CatBoost
test AP 0,6766, nó không vượt predeclared +0,01 CV gate, nên giữ Logistic. Nêu raw Logistic thắng
sigmoid/isotonic theo OOF Brier; không calibration vì “có calibration” nghe hay hơn.

Tại 10% capacity: contact 141, bắt 101/374 churners, recall 27,0%, precision 71,6%, lift 2,70×. Mở
slice table và 15 error cases; nêu senior selection disparity cần governance.

## 2:15–3:15 — Product flow

```powershell
python -m telco_churn.batch `
  --input data/raw/Telco-Customer-Churn.csv `
  --output reports/batch/campaign.csv `
  --budget-fraction 0.10

python -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000
```

Mở `/docs`, gọi `/health/ready`, `/v1/model-info`, `/v1/predict`, rồi
`/v1/campaigns/preview`. Chỉ rõ response có model version và simulated-value warning; input mâu thuẫn
phone/internet trả 422.

## 3:15–4:00 — Engineering evidence and close

Nêu **205 tests**, Ruff, GitHub Actions, MLflow SQLite lineage, Postgres migration, Docker non-root and
golden parity delta 0 (đo lại 21/09: 9,54e−17 trên 50 record). Latency host p95 **17,05 ms** / 1.000
requests / 0 errors (đo 21/09). Kết thúc bằng production gaps:
real point-in-time data, temporal test, experiment treatment/control, monitoring và legal review.

### Nhánh 60 giây — decision console

```powershell
python -m telco_churn.dashboard   # http://127.0.0.1:8050
```

Mở console: release tier `ENGINEERING_FOUNDATION` **được tính từ cổng**, không phải tự nhận; hai cổng
đang `NOT_MET` và lý do nằm ngay cạnh. Kéo capacity slider trên Orange holdout để thấy interval rộng ra
khi budget nhỏ, và chỉ ra điểm `locked` là điểm duy nhất được khai báo trước. Đóng bằng mục cuối trang:
danh sách phát biểu mà bằng chứng hiện tại **không** cho phép nói.

Không nói “accuracy 85%”, “revenue saved”, “AI predicts who to retain” hoặc “fair model”. Dùng đúng:
“frozen-test AP”, “simulated expected value”, “risk ranking”, “slice audit”.
