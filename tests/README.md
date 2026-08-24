# Chỉ mục kiểm thử

`293` test trên `28` file. Chúng không được viết để đạt độ phủ code, mà để **khóa các bất
biến** — những điều kiện mà nếu vỡ thì một kết quả sai vẫn trông như kết quả đúng.

Bảng dưới xếp theo **loại bất biến được bảo vệ**, không theo bảng chữ cái. Đọc cột "Bắt được
gì" trước; đó là lý do file đó tồn tại.

```powershell
.venv\Scripts\python.exe -m pytest tests -q          # 293 test
```

## Tầng 1 — đúng về toán

Kiểm rằng công thức được hiện thực đúng, thường bằng cách đối chiếu với một nguồn độc lập
hoặc với dữ liệu sinh có đáp án biết trước.

| File | Test | Bắt được gì |
|---|---:|---|
| [test_evaluation.py](test_evaluation.py) | 15 | Qini và AUUC lệch khỏi `scikit-uplift` — một hiện thực độc lập |
| [test_ranking_metrics.py](test_ranking_metrics.py) | 14 | TOC/RATE/AUTOC và transformed outcome sai công thức |
| [test_policy_evaluation.py](test_policy_evaluation.py) | 17 | `policy_area_dr`, đường cong ngân sách và DR risk sai |
| [test_policy.py](test_policy.py) | 5 | top-k và DR effect signal sai |
| [test_calibration.py](test_calibration.py) | 4 | hiệu chỉnh sau undersampling không khôi phục đúng thang |
| [test_synthetic_rct.py](test_synthetic_rct.py) | 7 | pipeline không khôi phục được hiệu ứng đã biết trên dữ liệu sinh |

`test_synthetic_rct.py` là tầng bảo vệ mạnh nhất trong nhóm: nó sinh dữ liệu với `τ` **biết
trước**, rồi kiểm pipeline có tìm lại được không. Trên dữ liệu thật không có đáp án để đối
chiếu, nên đây là chỗ duy nhất kiểm được tính đúng đắn đầu-cuối.

## Tầng 2 — model chạy đúng

| File | Test | Bắt được gì |
|---|---:|---|
| [test_baselines.py](test_baselines.py) | 8 | S/T/X/DR-learner trả về giá trị không hữu hạn hoặc sai hình dạng |
| [test_rank_learner.py](test_rank_learner.py) | 10 | Rank-Learner sai ở phần pairwise |
| [test_hybrid.py](test_hybrid.py) | 9 | hybrid stacker không tất định, hoặc vỡ trên outcome hiếm |
| [test_ensemble.py](test_ensemble.py) | 10 | Q-aggregation và rank average sai trọng số |
| [test_causal_foundation_candidates.py](test_causal_foundation_candidates.py) | 8 | DINA, Anchored R, Pattern R sai gradient hoặc sai thang |
| [test_data_optimized_candidates.py](test_data_optimized_candidates.py) | 5 | biểu diễn sentinel dạng nén cho kết quả khác dạng dày |

## Tầng 3 — dữ liệu và chẩn đoán

| File | Test | Bắt được gì |
|---|---:|---|
| [test_data.py](test_data.py) | 14 | hợp đồng dữ liệu vỡ; split chồng lấn; `stratified_complement` sai |
| [test_eda.py](test_eda.py) | 27 | mọi chẩn đoán ở `src/eda.py` — balance, overlap, power, heterogeneity |
| [test_proxy_diagnostic.py](test_proxy_diagnostic.py) | 8 | chẩn đoán proxy-ordering sai |

## Tầng 4 — kỷ luật thí nghiệm

Đây là nhóm đặc thù của repo này. Nó không kiểm toán học mà kiểm **quy trình**: những luật đã
đăng ký có thực sự được cưỡng chế không.

| File | Test | Bắt được gì |
|---|---:|---|
| [test_protocol_guards.py](test_protocol_guards.py) | 13 | protocol bị sửa; gate không kích hoạt; candidate không khai báo đủ |
| [test_experiment_integrity.py](test_experiment_integrity.py) | 9 | hash split lệch; registry thiếu trường; cross-fitting sai |
| [test_resource_gate.py](test_resource_gate.py) | 7 | resource gate không dừng khi vượt ngưỡng **trong lúc** chạy |
| [test_improvement_selection.py](test_improvement_selection.py) | 18 | promotion rule áp sai; shortlist chọn sai |
| [test_causal_forest_rare_outcome.py](test_causal_forest_rare_outcome.py) | 12 | giao ước của protocol `causal-forest-rare-outcome-v1` bị vi phạm |

`test_resource_gate.py` tồn tại vì một lỗi thật: gate ban đầu chỉ kiểm **trước** khi chạy, và
Sprint 3 gặp trường hợp RAM tụt xuống `1,55` GB **trong lúc** chạy mà không bị bắt.

## Tầng 5 — artifact đã phát hành không trôi

| File | Test | Bắt được gì |
|---|---:|---|
| [test_release_consistency.py](test_release_consistency.py) | 7 | code đánh giá mới cho ra số khác artifact đã phát hành |
| [test_causal_foundation_artifacts.py](test_causal_foundation_artifacts.py) | 4 | artifact vòng causal foundation bị sửa hoặc thiếu |
| [test_top_tail_research_artifacts.py](test_top_tail_research_artifacts.py) | 4 | artifact vòng top-tail bị ghi đè |

Nhóm này chống lại một lỗi âm thầm: refactor code đánh giá làm đổi số, trong khi báo cáo vẫn
ghi số cũ. Không có nhóm này thì báo cáo và code trôi khỏi nhau mà không ai biết.

## Tầng 6 — sản phẩm

| File | Test | Bắt được gì |
|---|---:|---|
| [test_webapp.py](test_webapp.py) | 22 | API trả sai schema; scorer lỗi; endpoint vỡ |
| [test_webapp_accessibility.py](test_webapp_accessibility.py) | 12 | tương phản dưới AA; mất focus style; tab thiếu ARIA |
| [test_sprint2_product.py](test_sprint2_product.py) | 6 | dashboard và dữ liệu export lệch nhau |

Ngoài pytest còn hai bộ acceptance chạy bằng trình duyệt thật:

```powershell
node scripts\smoke_webapp_browser.mjs      # 30/30
node scripts\smoke_dashboard_browser.mjs   # 12/12
```

## Tầng 7 — tài liệu

| File | Test | Bắt được gì |
|---|---:|---|
| [test_documentation_integrity.py](test_documentation_integrity.py) | 9 | link hỏng; đường dẫn trong backtick không tồn tại; số test lệch tài liệu; gạch nối U+2011; thiếu chỉ mục thư mục |
| [test_notebook_integrity.py](test_notebook_integrity.py) | 9 | notebook commit khi chưa chạy; execution count nhảy cóc; mục train bị gỡ |

Cả hai nhóm này ra đời từ lỗi đã xảy ra thật. Ví dụ: `X-Calibrated` từng xuất hiện `0` lần ở
dạng ASCII và `6` lần với gạch nối U+2011, nên `grep` theo tên candidate đã đăng ký không tìm
ra chỗ nào.

## File hỗ trợ

| File | Vai trò |
|---|---|
| [conftest.py](conftest.py) | fixture dùng chung: `full_df`, `sample_5pct`, `sample_1pct` |
| [repo_state.py](repo_state.py) | phân biệt "file thiếu vì lỗi" với "file thiếu vì `.gitignore`" — hỏi thẳng git thay vì giữ danh sách cứng |
| [synthetic_rct.py](synthetic_rct.py) | sinh RCT có `τ` biết trước, dùng cho tầng 1 |

## Hai môi trường, hai tập test

CI **không** có dữ liệu Criteo, scorer `.joblib` hay các file `.npz` — chúng bị `.gitignore`
loại. Nên CI chạy tập con:

```powershell
pytest tests --ignore=tests\test_data.py --ignore=tests\test_baselines.py --ignore=tests\test_webapp.py
```

`293` test ở local, `233` trên CI. `repo_state.py` tồn tại để một đường dẫn vắng mặt **đúng
theo thiết kế** không bị báo là lỗi tài liệu — trộn hai loại đó lại sẽ làm CI đỏ vì lý do sai,
và lâu dài dẫn tới thói quen bỏ qua CI đỏ.

## Quy ước khi thêm test

- Docstring nói **lỗi nào từng xảy ra hoặc có thể xảy ra**, không mô tả lại tên hàm.
- Thông báo `assert` phải in ra giá trị thật, để đọc log là biết sai ở đâu.
- Test đọc artifact phải đi qua `repo_state.py`, không tự giả định file tồn tại.
- Thêm test thì cập nhật số trong `README.md` và `docs/REPRODUCTION.md` — có một test kiểm
  đúng việc đó.
