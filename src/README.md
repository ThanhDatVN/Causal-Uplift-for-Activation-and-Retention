# Chỉ mục thư viện dùng chung

`src/` là thư viện, không phải nơi chạy thí nghiệm. Nó **không** đọc tham số dòng lệnh,
**không** ghi vào `output/` và **không** biết mình đang phục vụ vòng nào. Việc điều phối
nằm ở [`../scripts/`](../scripts/); kết quả nằm ở [`../output/`](../output/).

Bảng dưới xếp theo **tầng pipeline**, không theo bảng chữ cái — đọc từ trên xuống là đi
đúng đường dữ liệu đi. Mạch phát triển của cả dự án:
[`../docs/END_TO_END_WORKFLOW.md`](../docs/END_TO_END_WORKFLOW.md).

## Tầng 1 — dữ liệu và split

| Module | Vai trò |
|---|---|
| [`paths.py`](paths.py) | Một chỗ duy nhất định nghĩa đường dẫn repo. Mọi module khác nhập từ đây thay vì ghép chuỗi |
| [`data.py`](data.py) | Nạp Criteo, đối chiếu SHA-256, stratified sample và **stratified complement**. Hàm complement là thứ đảm bảo confirmation Sprint 2 không chồng lấn test Sprint 1 |
| [`eda.py`](eda.py) | Chẩn đoán một randomized incrementality test: balance/SMD, overlap, propensity, power, heterogeneity theo tầng, prognostic dominance |

## Tầng 2 — model

| Module | Vai trò |
|---|---|
| [`baselines.py`](baselines.py) | Response, S/T/X-Learner, DR-Learner — họ model của Sprint 1 |
| [`calibration.py`](calibration.py) | Khôi phục thang xác suất sau stratified undersampling, và τ-isotonic |
| [`candidates.py`](candidates.py) | Danh mục candidate của các vòng cải tiến. `CandidateSpec.build` là entrypoint huấn luyện duy nhất mà runner gọi — cùng một hàm cho mọi vòng |
| [`rank_learner.py`](rank_learner.py) | Rank-Learner: pairwise Neyman-orthogonal ranking |
| [`hybrid.py`](hybrid.py) | Prognostic–causal logistic stacking. **Đã hiện thực, chưa có dòng nào trong registry** |
| [`ensemble.py`](ensemble.py) | Q-aggregation, best-single theo DR risk, rank average |

## Tầng 3 — đo lường

| Module | Vai trò |
|---|---|
| [`evaluation.py`](evaluation.py) | Qini, AUUC, uplift calibration error. Đối chiếu với `scikit-uplift` trong test |
| [`ranking_metrics.py`](ranking_metrics.py) | RATE/AUTOC, adjusted transformed outcome, paired bootstrap |
| [`policy.py`](policy.py) | Dựng policy top-k và doubly robust effect signal |
| [`policy_evaluation.py`](policy_evaluation.py) | `policy_area_dr` — **metric chính hiện hành** — đường cong ngân sách, DR risk, paired policy difference |
| [`proxy_diagnostic.py`](proxy_diagnostic.py) | Chẩn đoán khi nào một proxy dự báo xếp hạng đúng theo treatment effect |

## Tầng 4 — hạ tầng thí nghiệm và phát hành

| Module | Vai trò |
|---|---|
| [`experiment.py`](experiment.py) | Split có kiểm hash, `make_folds`, `ResourceMonitor`, registry, git state. Đây là chỗ cưỡng chế các luật của protocol |
| [`scoring.py`](scoring.py) | Scorer lưu xuống đĩa cho batch scoring của web app |

## Hai bất biến mà thư viện này giữ

**Nuisance được cross-fit một lần và dùng chung cho mọi candidate.** Nhờ vậy chênh lệch
giữa hai model không lẫn với chênh lệch giữa hai tín hiệu chấm điểm. Vòng
`rare-outcome` cho thấy điều này quan trọng tới mức nào: đổi IPW sang DR trên **cùng** bộ
điểm làm chênh lệch đo được đổi `69` lần.

**Mọi so sánh đều đi qua paired bootstrap.** Không hàm nào trong `src/` trả về một phát
biểu "A hơn B" mà không kèm khoảng tin cậy.
