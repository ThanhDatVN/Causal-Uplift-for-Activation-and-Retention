# Chỉ mục notebook

Bốn notebook, đánh số theo thứ tự đọc. Số cũng là thứ tự thời gian của giai đoạn mà chúng
trình bày. Mạch phát triển đầy đủ:
[`../docs/END_TO_END_WORKFLOW.md`](../docs/END_TO_END_WORKFLOW.md).

| Notebook | Giai đoạn | Chế độ chạy | Output lưu sẵn |
|---|---|---|---|
| [`01_eda_criteo.ipynb`](01_eda_criteo.ipynb) | 0 — chẩn đoán dữ liệu | local, **trên toàn bộ 13.979.592 dòng**, khoảng 2,5 phút | 25/25 code cell, 9 biểu đồ |
| [`02_modeling_and_evaluation.ipynb`](02_modeling_and_evaluation.ipynb) | 3 — vòng Sprint 3 | local; mục 1–7 và 8–17 đọc artifact đóng băng, **mục 7bis huấn luyện thật** | 22/22 code cell, 5 biểu đồ |
| [`03_causal_forest.ipynb`](03_causal_forest.ipynb) | 4 — Causal Forest ba mốc | **Kaggle**, `Save & Run All`, 53,2 phút | 10/10 code cell |
| [`04_causal_forest_rare_outcome.ipynb`](04_causal_forest_rare_outcome.ipynb) | 8 — cấu hình `rare-outcome` | **Kaggle**, 107,4 phút | 0/10 code cell — **chưa nhúng output** |

## Hai chế độ, và vì sao phải phân biệt

**Notebook local (`01`, `02`)** chạy được trên máy dev và mang theo output đã chạy. Test
[`../tests/test_notebook_integrity.py`](../tests/test_notebook_integrity.py) cưỡng chế hai
điều với chúng: mọi code cell phải có `execution_count`, và các số đó phải là `1..N` tăng
dần — tức đúng trạng thái sau một lần `Run All` trên kernel sạch.

**Notebook Kaggle (`03`, `04`)** chỉ điều phối một job trên session Kaggle vì RAM local
không đủ cho development pool `5.591.836` dòng. Chúng nằm ngoài phạm vi hai kiểm tra trên,
và trạng thái output của chúng được ghi ở bảng trên thay vì bị cưỡng chế bằng test.

`04` hiện **chưa nhúng output**. Bằng chứng lần chạy nằm ở
`output/causal_forest/sprint3_rare_outcome/train.log`, nhưng mở notebook ra thì nó trông
như chưa từng chạy. Cách sửa: chạy lại `Save & Run All` trên Kaggle rồi tải bản có output
về, không phải sửa tay.

## Nguyên tắc: notebook trình bày, script tính

Notebook không phải nơi sinh ra nguồn số. Mọi con số chính thức đến từ một script trong
[`../scripts/`](../scripts/) và nằm trong [`../output/`](../output/) kèm `run_id`,
`commit_sha` và hash split. Tách như vậy để một con số trong báo cáo truy được về **đúng
một lần chạy**, thay vì về một phiên notebook không ai tái lập được.

Ngoại lệ có chủ ý là **mục 7bis của `02`**: nó huấn luyện thật ở quy mô 15% pool bằng đúng
những hàm mà [`../scripts/run_oof_experiment.py`](../scripts/run_oof_experiment.py) gọi,
rồi đối chiếu kết quả với một artifact đã đóng băng. Mục đó tồn tại để việc tách trình bày
khỏi tính toán **kiểm chứng được** chứ không chỉ được tuyên bố — metric chính khớp ở bậc
`1e-17`.
