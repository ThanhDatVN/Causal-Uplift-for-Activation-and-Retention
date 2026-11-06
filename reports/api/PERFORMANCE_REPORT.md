# API Performance Report

## Result (re-measured 21/09/2026)

FastAPI chạy trên host local đạt p95 **17,05 ms**, dưới acceptance gate 100 ms. Có 0 lỗi trong 1.000
single-record requests sau 50 warmups.

| Measurement | 21/09/2026 | 13/09/2026 |
|---|---:|---:|
| First request (“cold-like”; process already started) | 32,61 ms | 54,45 ms |
| Warm p50 / p95 / p99 | 12,49 / 17,05 / 21,39 ms | 20,24 / 22,79 / 25,53 ms |
| Sequential throughput | 76,19 requests/s | 48,99 requests/s |
| Batch 100 records | 17,02 ms | 25,09 ms |
| Batch 1.000 records | 41,48 ms | 113,57 ms |
| Valid-request errors | 0 / 1.000 | 0 / 1.000 |

Hai lần đo trên cùng máy và cùng bundle; chênh lệch là **machine load tại thời điểm đo**, không phải
thay đổi code phục vụ inference. Cột 13/09 giữ nguyên làm lịch sử, không bị ghi đè.

Measured on Python 3.11.9, Windows 10 build 26200, AMD64 Family 25 Model 68. Client and server ran on
localhost; requests were sequential, not concurrent. The first request is not a full container/process
cold start. These figures verify the portfolio engineering gate and must not be presented as a
production SLA.

Raw measurement: `latency.json` (lần đo mới nhất). Reproduce after starting API:

```powershell
python -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000
python -m telco_churn.performance --requests 1000 --warmup 50
```
