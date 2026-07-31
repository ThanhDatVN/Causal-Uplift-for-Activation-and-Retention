# 09 — Đặc tả bằng chứng cho portfolio (Portfolio Evidence Specification)

## Định vị theo bằng chứng từ artifact (Positioning)

Trình bày uplift, CLV và dashboard như các thành phần của một **decisioning product**, không
như ba notebook độc lập:

> *Incremental Value Studio converts randomized-experiment and customer-transaction evidence into a
> cost-aware targeting decision, with uncertainty, provenance and a runnable interface.*

Vị trí khớp trực tiếp nhất với artifact dự kiến là **Growth / Decisioning Data Scientist**.
Các nhánh DA và AI/ML Engineer cần thêm evidence tương ứng trong bảng bên dưới. Không ghi
GenAI/agent trong phạm vi nếu chưa có agent và evaluation riêng. Market snapshot trong
[`08_SOURCE_AUDIT.md`](08_SOURCE_AUDIT.md) ghi các nhóm kỹ năng cần có: SQL,
metrics/experimentation, Python, dashboard/communication, API/container/CI và reliability.

## Bản đồ năng lực theo vị trí

| Vị trí | Recruiter/hiring manager cần thấy | Bằng chứng bắt buộc từ dự án | Artifact chưa đủ để chứng minh nếu chỉ có |
|---|---|---|---|
| Data Analyst | metric definition, SQL, cohort/funnel, A/B readout, dashboard, recommendation rõ | metric dictionary; SQL queries/dbt-style marts; data-quality report; dashboard; executive case study | notebook EDA và chart không có quyết định |
| Data Scientist | estimand, baseline, split đúng, uncertainty, model comparison, business trade-off | experiment protocol frozen; temporal validation; DR/IPW/direct comparison; bootstrap CI; negative result; model card | Qini cao hoặc model phức tạp mà không policy evaluation |
| AI/ML Engineer | code modular, contracts, tests, API/app, container, CI, observability, reproducibility | Python package; Pydantic contracts; Docker health check; GitHub Actions; run metadata; smoke/integration tests; optional FastAPI | Streamlit file đơn lẻ hoặc notebook chạy trên máy cá nhân |

## Bảng điểm phát hành v1.0 (Release Scorecard)

Mục tiêu là **>= 80/100** và không có mục P0 bị thiếu. Không công bố “production-ready”; gọi là
**production-minded, reproducible portfolio application**.

| Pillar | Điểm | Evidence phải có |
|---|---:|---|
| Business decision clarity | 20 | problem statement; action rule; cost/budget/horizon scenario; CSV action list |
| Data/analytics quality | 20 | data card; metric dictionary; SQL/data mart; cleaning/cohort audit; no-leakage checks |
| Statistical/scientific rigor | 25 | estimand; protocol; observed-data limitation; baseline; CI/robustness; semi-synthetic ground-truth label |
| ML/software engineering | 25 | package boundaries; typed contracts; tests; CI; Docker health check; immutable artifacts/logs |
| Communication & traceability | 10 | 2–3 minute video; 1-page exec summary; limitations; source/provenance in UI |

### Điều kiện phát hành P0 (Required Release Gates)

1. README có một câu business value, architecture figure, screenshot/GIF, quickstart 3 lệnh và limitation.
2. `make demo` hoặc một lệnh tương đương tạo sample artifacts và chạy dashboard.
3. `docker build` + `docker run` pass health check; CI chạy lint, unit test, integration smoke test.
4. Mỗi run có `config`, `data_manifest`, `model_registry`, metrics và source provenance.
5. Dashboard không recompute model ngầm; chỉ đọc artifact immutable và hiển thị `run_id`.
6. Final policy table chứa baseline, point estimate, CI, budget/cost/horizon, caveat và export được.
7. Report ghi các kết quả không đạt điều kiện và limitation, không lựa chọn số sau khi đã
   xem kết quả.

## Dashboard demo: năm màn hình bắt buộc (Required Screens)

| Màn hình | Câu hỏi của user | Tín hiệu role |
|---|---|---|
| 1. Decision Overview | “Nên target bao nhiêu người, giá trị tăng thêm bao nhiêu dưới budget này?” | DA + DS |
| 2. Customer Strategy | “Ai được target, vì sao, có bao nhiêu người bị loại vì net value âm?” | DA + product thinking |
| 3. Evidence Lab | “Model/policy nào thắng baseline và CI có đủ tin?” | DS |
| 4. Scenario Lab | “Nếu cost, margin, horizon hoặc budget đổi thì policy có đổi không?” | DS + business judgment |
| 5. Governance | “Số này đến từ run/data nào, assumptions và limitations gì?” | AI/ML Engineer + trust |

**Demo data mode:** phải có dataset/artifact nhỏ, synthetic hoặc public-safe để người xem chạy ngay.
Không hiển thị raw customer ID/PII. Mọi monetary value phải ghi currency, horizon và revenue-vs-margin
definition ngay cạnh KPI.

## Bằng chứng kỹ thuật (Engineering Track)

### Bắt buộc (Mandatory)

- `src/` domain layer tách khỏi Streamlit;
- Pydantic schema cho scenario request, artifact manifest và export rows;
- CLI `run`, `score`, `validate-artifact`, `demo`;
- structured JSON log: `run_id`, data version, latency, status, error class;
- `GET /health` trong app/container;
- deterministic seed + sample fixture;
- GitHub Actions: format/lint, tests, Docker build, smoke test;
- pre-commit hoặc tương đương; dependency lock; security/PII note.

### Mở rộng AI Engineer có điều kiện (Conditional Extension) — chỉ sau khi P0 đạt

Build FastAPI thin service với ba endpoint trong `03_TECHNICAL_ARCHITECTURE.md`. Nó phải serve
**precomputed policy artifacts**, có OpenAPI docs, Pydantic validation, contract tests và graceful
error messages. Chỉ tính hạng mục này là bằng chứng API/service engineering khi có contract
test và smoke test; việc thêm LLM không tự tạo bằng chứng AI engineering.

### Trợ lý bằng chứng tùy chọn (Optional Evidence Copilot) — P2, không làm trước release

Nếu ứng tuyển AI Engineer thiên GenAI, thêm một copilot chỉ được phép trả lời từ `run metadata`, model
card và source audit. Nó không được tính policy value, không tự target customer, không tạo
số ngoài artifact và phải
hiển thị citation/run ID. Tạo golden-question evaluation set, pass-rate/latency/failure dashboard trước
khi đưa vào demo. Nếu không có evaluation, không đưa copilot vào headline.

## Nhánh Data Analyst (DA Track): bổ sung SQL và lớp chỉ số (Metric Layer)

Kế hoạch hiện đã có Python/causal artifacts nhưng chưa có đủ bằng chứng SQL cho vị trí DA.
P0 cần thêm:

```text
sql/
  staging_transactions.sql
  int_customer_daily.sql
  mart_customer_rfm.sql
  mart_policy_candidates.sql
  quality_checks.sql
docs/METRIC_DICTIONARY.md
```

Mỗi metric có owner/definition/grain/window/exclusion logic. Dashboard phải cho thấy một decision,
không chỉ visualization: ví dụ “top 10% policy tạo expected net value X với CI Y; không target nhóm
negative value”. Với public datasets, dùng DuckDB + SQL files là đủ; không cần dựng warehouse cloud.

## Nhánh Data Scientist (DS Track): đóng góp nghiên cứu kiểm chứng được

- Pre-register protocol trước final holdout; lưu change log nếu thay đổi.
- Luôn so direct policy với propensity, predicted CLV, conversion CATE và `CATE × CLV` heuristic.
- Báo cáo direct/IPW/DR side-by-side; khác biệt giữa estimator là diagnostic cần điều tra,
  không chọn estimator chỉ vì point estimate cao hơn.
- Dùng semi-synthetic chỉ để đo recovery/regret với ground truth; real data chỉ claim đúng observed horizon.
- Có unit test cho DGP truth, leakage, treatment propensity, policy cost/budget và artifact schema.

## Gói bàn giao cho nhà tuyển dụng (Delivery Package)

| Thời lượng xem | Artifact | Thông tin chính |
|---|---|---|
| 15 giây | README hero + GIF | “Công cụ chọn khách theo incremental net value, không chỉ likelihood to buy.” |
| 60 giây | deployed dashboard | “Tôi thay budget/cost/horizon và xem action list có provenance.” |
| 3 phút | video demo | “Tôi giải thích decision, evidence, limitation và hành động tiếp theo.” |
| 10 phút | technical report + code | “Tôi kiểm soát leakage, uncertainty, data versioning và deployment.” |
| phỏng vấn | decision log | “Tôi biết vì sao không dùng/không claim điều mà data không support.” |

## Thay đổi ưu tiên trong 5 tuần

1. **Tuần 1:** data card, source audit, SQL marts và cleaning audit trước model challenger.
2. **Tuần 2:** temporal validation/model card trước Bayesian extension.
3. **Tuần 3:** holdout-safe policy evaluation + decision table trước thêm causal model.
4. **Tuần 4:** dashboard năm màn hình, Docker/CI/health/provenance; FastAPI chỉ khi app core green.
5. **Tuần 5:** release scorecard, fresh-machine reproduction, demo/video/case study; optional Copilot chỉ
   khi tất cả P0 pass.

## Hạng mục loại khỏi phạm vi P0 (Scope Exclusions)

LLM/RAG, React rewrite, Kubernetes, multi-cloud và model bổ sung nằm ngoài P0 nếu các release
gate chưa đạt. P0 yêu cầu app chạy lại được, đọc artifact cố định, có validation và có
deployment/runbook. Tài liệu này quyết định ưu tiên khi roadmap khác có hạng mục xung đột.
