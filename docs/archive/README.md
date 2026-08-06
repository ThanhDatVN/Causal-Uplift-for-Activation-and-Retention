# Tài liệu lịch sử — docs

Bốn tài liệu từng nằm trong thư mục này đã bị **xoá và gộp vào chính trang này**. Chúng
là stub chuyển hướng ≤46 dòng, nội dung thật đã nằm ở tài liệu hiện hành; giữ chúng chỉ
tạo thêm chỗ để thông tin trôi khỏi thực tế — và điều đó đã xảy ra:
`KAGGLE_CAUSAL_FOREST.md` vẫn ghi Causal Forest "chưa chạy" nhiều ngày sau khi nó chạy
xong.

**Không dùng trang này làm nguồn số hay hướng dẫn thực thi.**

| Tài liệu cũ | Thay bằng | Vì sao thay |
|---|---|---|
| `TUTORIAL.md` | [`../../report/SPRINT_1_FINAL_REPORT.md`](../../report/SPRINT_1_FINAL_REPORT.md) + [`../SPRINT_1_THEORY_AND_METHOD_GUIDE.md`](../SPRINT_1_THEORY_AND_METHOD_GUIDE.md) | Số trong đó là số Sprint 2; báo cáo sprint là nguồn số chính thức |
| `KAGGLE_CAUSAL_FOREST.md` | `docs/KAGGLE_RUNBOOK_COMPLETE.md` | Bản cũ thiếu bước chấm điểm, thiếu cách ghim `scikit-learn<1.7`, thiếu cảnh báo chỉ stage 50% mới so được với release |
| `COLAB_CAUSAL_FOREST.md` | `docs/KAGGLE_RUNBOOK_COMPLETE.md` | Xem mục dưới |
| `DASHBOARD_CONCEPT.md` | `docs/WEBAPP.md` mục "Dashboard tĩnh Sprint 2" | Mô tả dashboard tĩnh, gộp cạnh phần web app để so sánh được hai sản phẩm |
| `uplift-modeling-explainer.html` | [`../../report/SPRINT_1_FINAL_REPORT.md`](../../report/SPRINT_1_FINAL_REPORT.md) | Explainer thời kỳ đầu, chưa có Sprint 2/3 |

## Quyết định vẫn còn giá trị: vì sao không dùng Colab

Đây là phần duy nhất trong bốn file cũ mang thông tin không có ở chỗ khác, nên giữ lại
nguyên văn ý.

`CausalForestDML` của EconML bị chặn bởi **CPU và system RAM**, không phải GPU. Colab Pro
chủ yếu bán thêm GPU và thời lượng session; nó không giải quyết đúng nút thắt. Mua Colab
Pro chỉ để chạy `CausalForestDML` là chi tiền cho tài nguyên không được dùng.

Quyết định này về sau được thực tế xác nhận: session Kaggle miễn phí cấp 31,35 GB RAM và
4 logical CPU, đủ chạy cả ba mốc 20/30/50% trong 48 phút với peak RAM 40,6%. Kết quả:
[`../../report/CAUSAL_FOREST_REPORT.md`](../../report/CAUSAL_FOREST_REPORT.md).

## Nếu cần đọc nội dung cũ

Chúng nằm trong lịch sử git. Lệnh lấy lại một file bất kỳ:

```powershell
git log --oneline --all -- docs/archive/KAGGLE_CAUSAL_FOREST.md
git show <commit>:docs/archive/KAGGLE_CAUSAL_FOREST.md
```
