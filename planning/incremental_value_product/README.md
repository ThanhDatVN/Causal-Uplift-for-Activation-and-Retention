# Kế hoạch Tổng thể Sản phẩm Giá trị Tăng thêm (Incremental Value Product — Master Plan)

Thư mục này là **source of record cho hướng phát triển sau causal uplift v0.1**.

## Mục tiêu chung

Xây **Incremental Value Studio**: hệ thống hỗ trợ growth/CRM manager quyết định nên tác động lên
khách hàng nào, với ngân sách nào, để tối đa hóa **giá trị ròng tăng thêm do treatment** thay vì
predicted conversion hoặc predicted CLV thuần túy.

Tên đề tài kỹ thuật:

> **Tối ưu hóa Giá trị Khách hàng Tăng thêm do Tác động Nhân quả**
> *(Causal Incremental Customer Value Optimization)*

Câu hỏi nghiên cứu:

> Có nên target khách dựa trên phần customer value tăng thêm do treatment thay vì predicted CLV
> hoặc conversion propensity? Chính sách đó tạo thêm bao nhiêu giá trị ròng trên holdout và ổn định
> đến đâu khi thay đổi horizon, cost, margin và budget?

## Trạng thái đầu vào

- Causal uplift hiện tại có pipeline Criteo, 5 model, Qini/AUUC/bootstrap và dashboard.
- Kiểm tra ngày 2026-07-28: **24/24 test pass**.
- Causal Forest cloud run, operational segmentation, đồng bộ tài liệu và Git release chưa hoàn thành.
- Probabilistic CLV mới có benchmark BG/NBD + Gamma-Gamma; chưa có package/test/notebook chính thức.

Roadmap năm tuần **chỉ bắt đầu sau khi causal được freeze/tag `causal-v0.1`**.

## Bản đồ tài liệu

| File | Câu hỏi được trả lời |
|---|---|
| [`01_PRODUCT_VISION.md`](01_PRODUCT_VISION.md) | Tầm nhìn sản phẩm (Product Vision): sản phẩm là gì, ai dùng, demo điều gì? |
| [`02_RESEARCH_DATA_METHODS.md`](02_RESEARCH_DATA_METHODS.md) | Nghiên cứu, dữ liệu và phương pháp (Research, Data and Methods) |
| [`03_TECHNICAL_ARCHITECTURE.md`](03_TECHNICAL_ARCHITECTURE.md) | Kiến trúc kỹ thuật (Technical Architecture): code, hợp đồng dữ liệu, pipeline, app |
| [`04_EXPERIMENT_PROTOCOL.md`](04_EXPERIMENT_PROTOCOL.md) | Giao thức thí nghiệm (Experiment Protocol): split, baseline, metric, chọn model |
| [`05_ROADMAP_5_WEEKS.md`](05_ROADMAP_5_WEEKS.md) | Lộ trình 5 tuần (5-Week Roadmap): lịch Day 1–30, tiêu chí hoàn tất, cắt scope |
| [`06_READING_LIST.md`](06_READING_LIST.md) | Danh mục đọc và học (Reading List) |
| [`07_PORTFOLIO_CV.md`](07_PORTFOLIO_CV.md) | Định hướng portfolio và CV (Portfolio and CV Direction) |
| [`08_SOURCE_AUDIT.md`](08_SOURCE_AUDIT.md) | Kiểm tra nguồn và sổ đăng ký trích dẫn (Source Audit) |
| [`09_COMPETITIVE_PORTFOLIO_EXECUTION.md`](09_COMPETITIVE_PORTFOLIO_EXECUTION.md) | Đặc tả evidence cho DA/DS/AI Engineer |
| [`10_END_TO_END_EXECUTION_PLAYBOOK.md`](10_END_TO_END_EXECUTION_PLAYBOOK.md) | Sổ tay thực thi đầu-cuối (End-to-End Execution Playbook) |
| [`11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md`](11_FEASIBILITY_INFRASTRUCTURE_DATA_METHODS.md) | Tính khả thi: hạ tầng, dữ liệu, phương pháp (Feasibility) |

## Các quyết định đã khóa

1. Không join Criteo và Online Retail II như cùng khách hàng.
2. Headline metric là **incremental value at horizon**; projected iCLV là lớp ngoại suy riêng.
3. Online Retail II chỉ chứng minh probabilistic CLV; không chứng minh causal effect.
4. Hillstrom chỉ chứng minh randomized monetary uplift ngắn hạn; không gọi là lifetime value.
5. Semi-synthetic longitudinal RCT được phép dùng cho integration/ground truth, nhưng phải gắn nhãn.
6. Champion được chọn theo out-of-sample policy net value, không chỉ theo Qini.
7. Product, policy evaluation và reproducibility là P0; thêm model là P1/P2.

## Quy ước song ngữ

- Viết tiếng Việt trước, tiếng Anh trong ngoặc ở lần xuất hiện đầu: **giá trị tăng thêm
  (incremental value)**, **giao thức thí nghiệm (experiment protocol)**.
- Giữ nguyên tên thuật toán, API, tên file và biến code: `CausalForestDML`, `BG/NBD`, `run_id`.
- **Incremental Value Studio** là tên thương hiệu của ứng dụng; mô tả tiếng Việt là *Nền tảng Giá trị
  Tăng thêm*.
- Khi viết CV/README tiếng Anh, dùng tên tiếng Anh trong ngoặc; khi thuyết trình, dùng tên tiếng Việt
  trước để bảo vệ mạch lập luận.

## Cổng đóng causal trước Day 1

Hard cap 2–3 ngày:

- chốt Causal Forest hoặc scope-out có lý do;
- đổi claim segmentation ba/bốn nhóm cho đúng code;
- chạy lại toàn bộ suite và xác nhận trạng thái 24/24 trong tài liệu public;
- đồng bộ model trong dashboard/report;
- tạo commit đầu tiên và tag `causal-v0.1`;
- freeze output + model/data card.

## Release đích

- `causal-v0.1`: causal uplift độc lập, có protocol, artifact và lệnh tái lập.
- `clv-v0.2`: probabilistic CLV có temporal validation.
- `v1.0`: Incremental Value Studio có policy optimizer, CI, export và public demo.

## Nguyên tắc vận hành

- Mỗi số trong README/slide/CV phải trace về một artifact.
- Mỗi ngày phải tạo ít nhất một artifact kiểm tra được.
- Final holdout chỉ mở một lần sau khi freeze protocol/model.
- Không hy sinh validation và product để chạy thêm model.
- Không để toàn bộ report sang tuần cuối.
