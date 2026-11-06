# Data card — Orange Belgium churn uplift (OpenML 45580)

## Tóm tắt

| Thuộc tính | Giá trị đã kiểm tra |
|---|---|
| Nguồn | Orange Belgium / Machine Learning Group, ULB; OpenML dataset 45580 |
| File | `churn-uplift-mlg.arff` — không commit vào repo |
| MD5 | `bd328613c1c4ef793ab04cd4dd1c6db0` |
| Kích thước | 11.896 hàng, 178 feature, `y`, `t` |
| Feature | 160 principal components số + 18 factor ẩn danh |
| Treatment | 9.010/11.896 = 75,74% được xếp vào target group |
| Control | 2.886/11.896 = 24,26% |
| Outcome | `y=1`: churn trong cửa sổ hai tháng sau campaign |
| Churn control | 105/2.886 = 3,638% |
| Churn treatment | 303/9.010 = 3,363% |
| Missing / duplicate row | 0 / 0 |
| License | CC BY-NC-ND; không giả định quyền dùng thương mại hay redistribute |

Nguồn chính thức: [OpenML metadata/API](https://www.openml.org/search?type=data&id=45580),
[bài báo dataset](https://arxiv.org/abs/2312.07206), và
[code tác giả](https://github.com/TheoVerhelst/Churn-Uplift-Dataset-Paper).[^1]

## Quá trình tạo dữ liệu

Dataset gộp ba retention campaign từ tháng 9 đến tháng 12/2020. Hệ thống cũ dự báo churn, chọn tập
khách high-risk, rồi ngẫu nhiên giữ lại một phần làm control; target group được chuyển cho call center để
liên hệ, đề xuất offer hoặc tariff plan theo lịch sử. Churn được quan sát trong hai tháng sau campaign.[^1]

Vì vậy estimand hợp lệ là intention-to-treat trong **tập high-risk đủ điều kiện đã được chọn**, không phải:

- hiệu quả nếu gọi toàn bộ customer base;
- treatment-on-the-treated của một offer cụ thể;
- tác động của một discount amount xác định;
- hiệu quả dài hạn quá hai tháng.

## Schema và semantics

- `PC1`–`PC160`: phép chiếu PCA của feature số gốc; không có business meaning công khai.
- `FACTOR1`–`FACTOR18`: categorical feature và level đều đã ẩn danh.
- `t=1`: target assignment; `t=0`: randomized control trong eligible risk pool.
- `y=1`: churn, là outcome xấu. Repo định nghĩa uplift dương là `E[Y(0)-Y(1)|X]`, tức churn được ngăn.
- `row_id`: ID kỹ thuật do loader tạo từ source order đã khóa checksum; không phải customer ID.

Loader ở `telco_churn.orange_data` kiểm tra checksum, số hàng, đúng thứ tự 160 PC + 18 factor + `y,t`,
missing và binary domains trước khi cho benchmark chạy.

## Chất lượng và randomization audit

Full sample difference-in-means là +0,275 điểm phần trăm churn được ngăn, 95% Wald CI
[-0,503; +1,053] điểm phần trăm. Không thể xem chênh lệch thô này là bằng chứng campaign có hiệu quả.
Bài báo gốc dùng classifier two-sample test, thu được loss 23,82% so với tỷ lệ control 24,26% và
permutation p-value 0,26; tác giả kết luận feature không dự báo được assignment tốt hơn null.[^1]

Repo còn xuất standardized mean differences và categorical share differences. Max đơn lẻ lần lượt là
0,220 và 0,176, nhưng có 178 feature và nhiều level nên max không phải một global randomization test;
không được chọn vài imbalance lớn hậu nghiệm rồi tuyên bố randomization thất bại.

## Split và sử dụng

- Frozen holdout: 20%, stratify theo joint `(t,y)`, seed `20260914`.
- Development: 9.516; test: 2.380.
- Manifest SHA-256:
  `e2828178d09952fe97d3a360a7511ae75f600949546ab4aaa1ffc06862f4efe3`.
- Model selection và capacity selection chỉ dùng development OOF.
- Test chỉ mở sau khi policy được khóa; các model còn lại trên test mang nhãn exploratory.

Không có timestamp/campaign/customer ID trong public file, nên không thể group split theo customer,
rolling-origin backtest hay kiểm tra interference/carryover. Mock temporal lab tồn tại để test các cơ chế
đó, không để lấp khoảng trống external validity.

## Privacy, license và prohibited use

PCA và generic factor labels bảo vệ confidentiality nhưng làm mất khả năng đưa ra reason code nghiệp vụ.
Không dùng feature importance để nói “nguyên nhân churn”, không tái nhận dạng, không commit raw file,
không dùng dataset cho quyết định khách hàng thật. License OpenML ghi `CC BY-NC-ND`; người dùng phải tự
xác minh quyền sử dụng trong tổ chức và không suy rộng license của source code sang raw data.

## Reproducibility

```powershell
python -m telco_churn.orange_data fetch
python -m telco_churn.orange_data validate
python -m telco_churn.orange_benchmark
```

Artifacts: `reports/uplift/`; model nghiên cứu: `artifacts/models/orange_retention_policy.joblib`.

[^1]: Théo Verhelst et al., “[A churn prediction dataset from the telecom sector: a new benchmark for uplift modeling](https://arxiv.org/abs/2312.07206),” ECML PKDD proceedings; dataset and campaign description, Tables 1–5.
