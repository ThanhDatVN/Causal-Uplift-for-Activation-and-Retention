# Nhật ký hàng ngày — Tuần 1

**2026-07-20**
- Ghi cấu hình máy local, cài Python 3.12.10, dựng `.venv`, cài `requirements.txt` đã pin.
- Tải Criteo Uplift Dataset qua HuggingFace.
- Đo runtime/RAM cho `CausalForestDML`/T-Learner/X-Learner/DR-Learner ở các mức sample 1–20%.
- Dựng cấu trúc thư mục dự án, `.gitignore` chặn `data/`.

**2026-07-21**
- Tái xác nhận môi trường + package versions.
- Cài `causalml==0.17.0` (optional).
- Research bổ sung nguồn tham khảo, kiểm tra link.
- Tách `CAUSAL_UPLIFT_PLAN.md` thành tài liệu độc lập.

**2026-07-22**
- Viết `src/paths.py`, `src/data.py` + `tests/test_data.py` (7 test dùng file Criteo local).
- Chạy notebook `01_eda_criteo.ipynb`, xuất `output/eda_summary.csv`.
- Viết `src/baselines.py` (T-Learner, X-Learner) + test.
- Viết `src/evaluation.py` (Qini/AUUC, bootstrap CI), đối chiếu với `sklift`; paired tail
  heuristic ở mốc này về sau được thay bằng paired CI của `ΔQini` trong release.

**2026-07-23**
- Bổ sung `uplift_curve`/`auuc_score` trong `evaluation.py`, đối chiếu `sklift`.
- Thêm guard edge-case cho các hàm đánh giá (không conversion → NaN có cảnh báo thay vì crash).
- `pytest tests/ -v` → 18 test pass tại mốc này; suite hiện tại đã mở rộng thành 24/24 pass.
