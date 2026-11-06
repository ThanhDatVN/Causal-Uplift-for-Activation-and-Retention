# Triển khai — hai dịch vụ, một cây nguồn

Ngày: 21/09/2026. Tài liệu này mô tả **cách triển khai đã được chạy và kiểm**, không phải một kiến trúc dự kiến. Mọi số trong đây đến từ [reports/deployment/DEPLOYMENT_SMOKE.md](../reports/deployment/DEPLOYMENT_SMOKE.md).

Phạm vi bị giới hạn có chủ đích. Triển khai ở đây nghĩa là **chạy được hai dịch vụ decision-support trên máy/mạng tin cậy**. Nó không phải là:

- không phải production serving có SLA, autoscaling hay on-call;
- không phải quyền gửi ưu đãi: không dịch vụ nào gọi campaign system, gửi email hay cấp discount;
- không phải nâng hạng bằng chứng: console phục vụ đúng bằng chứng `CONDITIONAL` mà nó phục vụ trước khi được đóng gói. Đóng container không làm một khoảng tin cậy hẹp lại.

## 1. Hai dịch vụ

| Dịch vụ | Cổng | Nội dung | Phụ thuộc runtime |
|---|---:|---|---|
| `api` | 8000 | Scoring `P(churn)` theo schema đã khóa, campaign preview có cảnh báo simulated | fastapi, uvicorn, numpy, pandas, scikit-learn, joblib |
| `console` | 8050 | [Decision console](archive/VERIFICATION_V4_1.md#5-hai-thành-phần-mới): cổng, mutation, coverage, capacity curve, mechanism lab | fastapi, uvicorn, numpy, pandas |
| `postgres` | 5432 | Schema vận hành (`sql/001_initial.sql`), tmpfs, dùng cho migration/replay | — |

Console **không** cài CatBoost, scikit-learn, scipy, mlflow hay matplotlib. Một khung nhìn chỉ-đọc trên kết quả đã lưu không có lý do gì mang theo training stack: đó là vài trăm MB và một bề mặt tấn công không dùng tới. Để làm được điều đó, `bootstrap_selected_effect` đã chuyển sang `telco_churn/resampling.py` (chỉ NumPy) và `telco_churn/uplift.py` re-export nguyên tên — **một** implementation, mọi import cũ giữ nguyên.

Kích thước image đo được: `api` 724 MB, `console` 480 MB.

## 2. Chạy

```powershell
docker compose up --build -d
docker compose ps                      # cả ba phải healthy
python -m telco_churn.deployment_smoke `
  --dsn "postgresql://telco:local-development-only@127.0.0.1:5432/telco_churn"
docker compose down -v
```

Không có Docker thì chạy trực tiếp; mặc định host là `127.0.0.1` cho cả hai:

```powershell
python -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000
python -m telco_churn.dashboard        # http://127.0.0.1:8050
```

Biến môi trường: `TELCO_MODEL_PATH` (api), `TELCO_ARTIFACT_ROOT`, `TELCO_CONSOLE_HOST`, `TELCO_CONSOLE_PORT` (console). Bind console ra ngoài loopback thì nó in cảnh báo — xem §5.

## 3. Image console là một evidence snapshot bất biến

Artifact được **nướng vào image** lúc build. `GET /api/deployment` trả về `evidence_snapshot`: SHA-256 rút gọn của cặp `(key, sha256)` của từng artifact được khai báo, sắp xếp theo key. Hệ quả:

- hai container build từ cùng reports có **cùng** id và trả lời như nhau;
- đổi một artifact thì id đổi, nên không thể âm thầm phục vụ bằng chứng khác;
- báo cáo deployment smoke so id của container với id tính lại trên host và **ghi rõ khi lệch**. Lệch không tự động là lỗi: triển khai một snapshot cũ có chủ đích là hợp lệ, miễn là nói ra.

Báo cáo deployment smoke bị loại khỏi chính id đó — nó mô tả một *lần triển khai* của bằng chứng, không phải bằng chứng; đưa vào sẽ làm địa chỉ tự tham chiếu và không image nào khớp được sau lần smoke kế tiếp.

Muốn console đọc reports sống thay vì snapshot: mount đè `/app/reports`, và chấp nhận rằng image không còn định danh nội dung nó phục vụ.

## 4. Kết quả kiểm — 12/12 pass

`python -m telco_churn.deployment_smoke` chạy với stack đang lên:

| Check | Kết quả |
|---|---|
| `api_live`, `api_ready` | 200 |
| `api_model_info` | artifact_version 1.0.0 |
| `api_rejects_invalid_input` | record mâu thuẫn phone/lines → **422**, không được score |
| `host_container_parity` | max \|host − container\| = **1,110e−16** trên 50 record (ngưỡng 1e−12) |
| `console_live`, `console_ready` | 200, release tier `ENGINEERING_FOUNDATION` |
| `console_deployment_info` | snapshot `ac7dafbe5fea32a4`, 12/12 artifact, read-only |
| `evidence_snapshot_matches_host` | container = host |
| `console_exposes_no_write_path` | POST `/api/evidence` → 405 |
| `locked_decision_reproduced` | DR triển khai 0,0333090725 so công bố 0,0333090725, lệch **1,4e−17**, quyết định `no_launch` |
| `database_schema` | 4 bảng, migration đã áp |

Kiểm thêm bằng `docker compose exec`, ghi lại ở đây vì chúng là claim về cấu hình chứ không phải về HTTP:

- cả hai container chạy **uid 65532**, không phải root;
- filesystem read-only có hiệu lực: `touch /app/reports/v4/tampered.json` → `Read-only file system`;
- trong image console: `catboost`, `sklearn`, `scipy`, `mlflow`, `matplotlib` đều **absent**.

Đây đóng một mục đã treo trong ledger: “Docker compose chưa smoke lại ở snapshot cuối”. Parity host↔container giờ là số đo, không phải ký ức.

### Drift detector đã kích hoạt thật một lần

Giữa hai lần chạy, host sinh `run_report.json` mới (một lần `research_runner --profile smoke`), trong khi image console vẫn mang bản cũ. Check tương ứng báo đúng:

```
[skip] evidence_snapshot_matches_host: container 88e731be5bdf55a6 vs host ac7dafbe5fea32a4
       -- the deployment is serving a different snapshot
```

Không fail run — triển khai một snapshot cũ là hợp lệ — nhưng cũng không im lặng. Build lại console rồi chạy lại thì hai id trùng nhau và báo cáo về 12/12. Đây là hành vi đã quan sát, không phải thiết kế trên giấy.

## 5. Ranh giới vận hành

Không dịch vụ nào có authentication. API trả risk score theo khách hàng; console phục vụ nguyên văn bằng chứng nghiên cứu, gồm cả những con số `CONDITIONAL` rất dễ bị trích sai. Vì vậy:

- compose bind **127.0.0.1** cho cả ba cổng; `read_only`, `cap_drop: ALL`, `no-new-privileges` cho hai dịch vụ ứng dụng;
- console phục vụ `robots.txt` chặn toàn bộ;
- `GET /api/deployment` trả kèm `security_note` và `operational_bounds` để một người mở API thấy giới hạn mà không cần đọc repo;
- đưa ra mạng dùng chung thì phải có reverse proxy làm TLS + auth trước, và đó là quyết định của chủ dự án, không phải mặc định.

Mật khẩu Postgres trong `compose.yaml` là local-development-only và volume là tmpfs: database này dùng để kiểm migration/replay, không phải system of record.

## 6. Việc chưa làm

- **Registry/CD**: chưa push image đi đâu, chưa có pipeline build-publish. Cần quyết định registry và quyền trước.
- **Policy bundle serving**: API hiện chỉ có `risk_30d`; endpoint cho causal policy bundle chưa có contract (N10 còn mở).
- **Concurrency/SLA**: mọi số latency là sequential localhost. Chưa có load test, chưa có SLA.
- **Secrets**: chưa có secret manager; mật khẩu dev nằm thẳng trong compose, đúng cho local và chỉ local.
- **Deployment smoke chưa nằm trong CI**: nó cần stack đang chạy. Có thể thêm một job dựng compose, nhưng chưa làm.
