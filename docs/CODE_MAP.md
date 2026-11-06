# Bản đồ mã nguồn

Các tên module trong `src/telco_churn/` là điểm chạy công khai qua `python -m telco_churn.<module>`, entry point trong `pyproject.toml`, tài liệu nghiên cứu hoặc cả ba. Vì vậy mã nguồn vẫn giữ tên module ổn định. Thư mục `planner/` và `webui/` là tài nguyên tĩnh được đóng gói cùng package.

| Luồng | Điểm vào và thành phần chính |
|---|---|
| Demo giữ chân & Giải thích AI | `api.py` phục vụ `/planner/`; `assistant.py` cung cấp giải thích AI cho từng khách hàng (log-odds, kịch bản đối thực What-If) và trợ lý bằng chứng X09; `schema.py`, `features.py`, `train.py`, `batch.py`, `policy.py`, `allocation.py` xử lý dữ liệu và quyết định; `replay.py` kiểm chứng gói xuất. |
| Đọc bằng chứng | `dashboard.py` phục vụ `webui/`; `evidence.py` đọc các báo cáo, claim ledger và trạng thái gate; `assistant.py` phục vụ truy vấn bằng chứng có trích dẫn SHA-256. |
| Dữ liệu và benchmark | `data.py`, `orange_data.py`, `hillstrom_data.py`, `lenta_data.py` kiểm nguồn; `orange_benchmark.py`, `screening.py`, `model_tournament.py`, `external_replication.py` chạy các nhánh đánh giá. |
| Suy luận và thí nghiệm | `evaluation.py`, `uplift.py`, `policy_comparison.py`, `inference.py`, `validity_suite.py`, `r1_repair.py`, `fresh_evaluator.py` chứa estimator, gate và nghiên cứu kiểm định. Những module nghiên cứu khác giữ từng protocol riêng để tái hiện đúng lệnh đã công bố. |
| Vận hành | `environment.py` kiểm khóa môi trường; `research_runner.py` điều phối; `challenge_suite.py` kiểm các trường hợp sai; `deployment_smoke.py` kiểm dịch vụ. |

`scripts/` chứa các lệnh tái hiện và kiểm tra trình duyệt; `tests/` kiểm các hợp đồng tương ứng. Tên file trong `reports/` là output của các lần chạy đã ghi nhận và không được coi là mã nguồn.
