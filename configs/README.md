# Chỉ mục protocol

Mỗi file ở đây là một **giao ước đăng ký trước**: nó ghi metric, gate và luật quyết định
**trước** khi vòng thí nghiệm tương ứng chạy dòng đầu tiên.

Sau khi chạy, SHA-256 của file được ghi vào manifest của run. Nên không thể sửa protocol rồi
tuyên bố nó vốn như vậy — xem [`../docs/END_TO_END_WORKFLOW.md`](../docs/END_TO_END_WORKFLOW.md)
mục 3.4.

> **Không sửa file trong thư mục này.** Chúng là artifact có provenance. Một vòng mới cần luật
> khác thì tạo protocol **mới**, không sửa cái cũ. Ngoại lệ duy nhất đã dùng là
> `integrity_revision` của Sprint 3, và nó được ghi rõ ngay trong file.

## Sáu protocol, theo thứ tự thời gian

| Protocol | `protocol_id` | Đăng ký | Candidate | Vòng |
|---|---|---|---:|---|
| [sprint1_release_5models.json](sprint1_release_5models.json) | — | 29/07 | 5 | Sprint 1 — cấu hình năm model release |
| [sprint3_improvement_protocol.json](sprint3_improvement_protocol.json) | `sprint3-improvement-v1` | 05/08 | 12 | Sprint 3 — **protocol nền, định nghĩa metric chính** |
| [causal_forest_rare_outcome_protocol_v1.json](causal_forest_rare_outcome_protocol_v1.json) | `causal-forest-rare-outcome-v1` | 13/08 | 1 | Giai đoạn 8 — cấu hình lại Causal Forest |
| [data_optimization_protocol_v1.json](data_optimization_protocol_v1.json) | `data-optimization-v1` | 09/08 | 7 | Giai đoạn 5 — biểu diễn sentinel |
| [causal_foundation_protocol_v1.json](causal_foundation_protocol_v1.json) | `causal-foundation-v1` | 09/08 | 6 | Giai đoạn 6 — DINA, Anchored R, Pattern R |
| [top_tail_research_protocol_v2.json](top_tail_research_protocol_v2.json) | `top-tail-research-v2` | 09/08 | — | Giai đoạn 7 — audit phần đuôi `1–2%` |

`sprint1_release_5models.json` khác các file còn lại: nó chỉ chứa hyperparameter của năm
model, không chứa gate hay luật quyết định. Khái niệm protocol đăng ký trước chỉ xuất hiện
từ Sprint 3.

## Protocol nền — Sprint 3

Đây là file cần đọc trước, vì năm protocol sau đều dẫn chiếu hoặc kế thừa từ nó.

| Khai báo | Giá trị |
|---|---|
| Metric chính | `policy_area_dr` |
| Dải ngân sách | `[0,01 · 0,02 · 0,05 · 0,10 · 0,15 · 0,20 · 0,25 · 0,30]` |
| Propensity | `0,85` — hằng số **theo thiết kế**, không ước lượng lại |
| Cross-fitting | 3 fold, fold seed chính `101`, seed thứ hai `202` |
| Promotion rule | 4 điều kiện, phải thỏa **đồng thời** |
| Early stop | score không hữu hạn, hằng số, hoặc bị dominate ở mọi budget `5–20%` |
| Resource gate | ngưỡng RAM, kiểm liên tục |

Bốn điều kiện của promotion rule:

1. `policy_area_dr` OOF cao hơn Response ở **cả hai** fold seed;
2. point estimate trên retrospective confirmation cùng dấu;
3. paired 95% CI của chênh lệch có **cận dưới lớn hơn 0**;
4. không vi phạm resource gate; score hữu hạn và không suy biến; calibration hữu hạn nếu ở
   thang CATE.

Nếu không ai đạt: giữ Response. Điều đó cũng được viết trước, dưới khóa `fallback`.

## `integrity_revision` của Sprint 3

File Sprint 3 có một trường `integrity_revision` ghi ngày `09/08/2026`. Phạm vi của nó được
khai báo là *machine-readable clarification only* — làm rõ định dạng để máy đọc được, **không
đổi** metric, gate hay luật.

Đây là ngoại lệ duy nhất từng áp cho một protocol đã đăng ký, và nó được ghi ngay trong file
thay vì sửa lặng lẽ.

## Vì sao text trong protocol không dấu

Các chuỗi mô tả trong protocol viết tiếng Việt **không dấu**. Lý do: chúng được in ra console
Windows trong lúc chạy, và console mặc định dùng cp1252 nên không encode được tiếng Việt có
dấu.

Không sửa để thêm dấu — SHA của file nằm trong provenance của mọi run đã chạy. Web app dịch
sang tiếng Việt có dấu ở **tầng trình bày**, giữ nguyên văn trong thuộc tính `title`.

## Thêm một protocol mới

Trình tự bắt buộc, theo [`../planning/README.md`](../planning/README.md):

1. Viết protocol **trước**, kể cả metric chính và promotion rule.
2. Kiểm nguồn phương pháp đã ở mức xác minh `A` chưa — mức `B` và `C` **chưa được** hiện thực.
3. Chọn `protocol_id` mới và một namespace output mới; không ghi đè namespace cũ.
4. Chạy smoke trước, và **không** dùng kết quả smoke để chọn model.
5. Mọi run vào `output/improvement/registry.csv`, kể cả run hỏng.

Lệnh chạy cho từng vòng: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md).
