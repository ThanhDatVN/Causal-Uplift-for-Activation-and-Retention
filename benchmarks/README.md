# Benchmark tài nguyên

Thư mục này **không** sinh ra kết quả khoa học nào. Nó trả lời đúng một câu hỏi kỹ thuật:
*chạy được không, và tốn bao nhiêu RAM.*

Nguồn số chính thức nằm ở [`../output/`](../output/) và [`../report/`](../report/).

## Vì sao tồn tại

Causal Forest trên `5,59` triệu dòng có thể tốn hàng chục GB. Trước khi bỏ hàng giờ chạy trên
Kaggle, cần biết trước mức tài nguyên ở các quy mô nhỏ để ngoại suy.

Chính bước đo này dẫn tới `resource_gate` trong protocol: ngưỡng RAM không phải con số ước
chừng mà lấy từ đường cong đo được ở đây.

| File | Vai trò |
|---|---|
| [bench_causal_forest.py](bench_causal_forest.py) | đo `CausalForestDML` theo `frac`, `n_estimators`, `min_samples_leaf`, `cv` |
| [bench_metalearners.py](bench_metalearners.py) | đo T/X/DR-learner trên cùng mẫu, để so tài nguyên |
| `results.csv` | một dòng mỗi lần chạy: thời gian, peak RSS, exit code, đường dẫn log |
| `logs/` | log đầy đủ của từng lần chạy |

## Chạy

```powershell
.venv\Scripts\python.exe benchmarks\bench_causal_forest.py --frac 0.005 --n-estimators 20 --min-samples-leaf 50 --cv 2
.venv\Scripts\python.exe benchmarks\bench_metalearners.py --frac 0.05 --model xlearner
```

`results.csv` được **ghi thêm**, không ghi đè — kể cả dòng có `exit_code = 1`. Cùng lý do với
registry thí nghiệm: một lần chạy thất bại là dữ liệu, không phải rác. Dòng đầu tiên của file
chính là một lần `exit_code = 1`, và nó cho biết ngưỡng nào làm tiến trình chết.

## Đọc `results.csv`

| Cột | Nghĩa |
|---|---|
| `tag` | tên lần đo, dùng để nhóm |
| `args` | tham số đầy đủ — đủ để chạy lại |
| `exit_code` | `0` là xong, khác `0` là chết giữa chừng |
| `wall_time_s` | thời gian thực |
| `peak_rss_mb` | **đỉnh bộ nhớ** — con số quan trọng nhất |
| `poll_samples` | số lần lấy mẫu RAM; quá ít thì đỉnh có thể bị bỏ sót |

`poll_samples` đáng chú ý: đỉnh RAM được đo bằng cách lấy mẫu định kỳ, nên một đỉnh rất ngắn
có thể lọt giữa hai lần lấy mẫu. Với lần chạy ngắn, `peak_rss_mb` là **cận dưới** của đỉnh
thật.

## Kết quả đã dùng

Ba mốc Causal Forest trong `report/04_CAUSAL_FOREST.md` mục 5 dẫn số từ đây: tăng dữ liệu
từ `20%` lên `50%` làm RSS tăng `2,3` lần và thời gian tăng `2,9` lần — gần tuyến tính, và
**không** tạo bước nhảy nào về chất lượng xếp hạng.

Dự phóng tuyến tính từ mốc `20%` cho `13,74` GB ở mốc `50%`; thực tế `12,73` GB. Dự phóng hơi
bảo thủ, tức đúng chiều mong muốn cho một gate tài nguyên.
