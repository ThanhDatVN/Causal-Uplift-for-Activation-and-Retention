# Tài liệu lịch sử — docs

Bốn tài liệu dưới đây đã bị thay thế. Chúng được giữ vì các báo cáo sprint và tài liệu
kế hoạch đã trích dẫn chúng; xoá đi sẽ làm hỏng đường dẫn trong tài liệu lịch sử.

**Không dùng làm nguồn số hay hướng dẫn thực thi.**

| Tài liệu | Thay bằng | Vì sao thay |
|---|---|---|
| `TUTORIAL.md` | `report/SPRINT_1_FINAL_REPORT.md` + `docs/SPRINT_1_THEORY_AND_METHOD_GUIDE.md` | Số trong đó là số Sprint 2; báo cáo sprint là nguồn số chính thức |
| `KAGGLE_CAUSAL_FOREST.md` | [`../KAGGLE_RUNBOOK_COMPLETE.md`](../KAGGLE_RUNBOOK_COMPLETE.md) | Bản cũ thiếu bước chấm điểm, thiếu cách ghim `scikit-learn<1.7`, thiếu cảnh báo chỉ stage 50% mới so được với release |
| `COLAB_CAUSAL_FOREST.md` | [`../KAGGLE_RUNBOOK_COMPLETE.md`](../KAGGLE_RUNBOOK_COMPLETE.md) | Nút thắt là CPU và system RAM, không phải GPU; Colab không giải quyết đúng vấn đề |
| `DASHBOARD_CONCEPT.md` | [`../WEBAPP.md`](../WEBAPP.md) mục "Dashboard tĩnh Sprint 2" | 40 dòng mô tả dashboard tĩnh, gộp vào cùng tài liệu với web app để so sánh được hai sản phẩm |
| `uplift-modeling-explainer.html` | `report/SPRINT_1_FINAL_REPORT.md` | Explainer thời kỳ đầu, chưa có Sprint 2/3 |

Ba file `.md` đã được rút gọn thành stub: giữ lại phần nội dung vẫn đúng, và trỏ sang tài
liệu hiện hành. Chúng không còn chứa hướng dẫn thực thi trùng lặp có thể trôi khỏi thực tế.
