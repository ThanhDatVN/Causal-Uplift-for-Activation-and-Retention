# Web application — Causal Targeting Lab

Tầng **nhắm mục tiêu** của dự án: nó biến bảng xếp hạng model thành một quyết định ngân sách
kèm khoảng tin cậy.

```powershell
.venv\Scripts\python.exe scripts\serve_webapp.py
```

## Ranh giới, đọc trước khi dùng

> Đây là tầng **nhắm mục tiêu**, đặt **sau** tầng **đo lường**. Nó **không thay thế**
> incrementality test.

Nhầm hai tầng này là cách một tổ chức tự thuyết phục mình rằng chiến dịch có hiệu quả bằng
chính model dùng để phân phối chiến dịch đó. Ranh giới được hiển thị ngay trên giao diện dưới
dạng banner "Phạm vi kết luận", không giấu trong tài liệu.

Hai giới hạn nữa, cũng hiển thị trên giao diện:

- **Mọi con số tiền là kịch bản conversion-equivalent.** Criteo không có doanh thu, biên lợi
  nhuận hay chi phí liên hệ; giá trị và chi phí là **input của người dùng**.
- **Điểm số chỉ dùng để xếp thứ tự.** Nó không phải xác suất conversion và không phải hiệu
  ứng ước lượng của một cá nhân.

## Kiến trúc

```text
webapp/
├── api.py        FastAPI — 12 endpoint, chỉ đọc artifact
├── service.py    tầng dịch vụ: nạp artifact, dựng bundle, tính kịch bản
└── static/
    ├── index.html   SPA sáu tab, không CDN
    ├── app.js       điều phối, gọi API, dựng bảng
    ├── charts.js    canvas thuần: line, bar, forest
    └── app.css      hệ màu hai theme, kèm token đã kiểm tương phản AA
```

**Không có bước huấn luyện nào khi nhận request.** Ứng dụng chỉ đọc artifact đã phát hành
trong `output/`. Nhờ vậy con số trên giao diện và con số trong `report/` không thể trôi khỏi
nhau — chúng đọc chung một file.

Không dùng CDN và không có dependency JavaScript ngoài. `charts.js` vẽ trực tiếp lên canvas,
khoảng 600 dòng, đủ cho ba loại biểu đồ mà sản phẩm cần.

## Endpoint

| Endpoint | Trả về |
|---|---|
| `GET /api/health` | trạng thái và schema version |
| `GET /api/meta` | champion, run id, hash dữ liệu, ghi chú phạm vi |
| `GET /api/models` | bảng metric của mọi model trên confirmation |
| `GET /api/models/pairwise` | chênh lệch ghép cặp kèm CI — nguồn của forest plot |
| `GET /api/policy/curve` | đường cong ngân sách và dải tin cậy |
| `GET /api/policy/comparison` | so với các comparator, gồm chọn ngẫu nhiên |
| `GET /api/policy/sensitivity` | giá trị ròng theo chi phí liên hệ giả định |
| `POST /api/policy/simulate` | kịch bản người dùng: budget, value, cost |
| `GET /api/segments/deciles` | uplift quan sát theo decile |
| `GET /api/diagnostics` | cân bằng hai nhánh, SMD, phân bố score |
| `GET /api/registry` | sổ đăng ký thực nghiệm |
| `GET /api/evidence` | mức bằng chứng của từng tập dữ liệu |

## Sáu tab

| Tab | Trả lời câu hỏi |
|---|---|
| **Tổng quan** | quyết định hiện hành là gì, và vì sao |
| **Model** | model nào hơn model nào, và có phân biệt được không |
| **Policy** | ở ngân sách này thì được bao nhiêu, hòa vốn ở đâu |
| **Phân khúc** | hiệu ứng tập trung ở đâu |
| **Chấm điểm** | chấm một danh sách khách hàng |
| **Bằng chứng** | mỗi con số đến từ artifact nào |

Ba khối được thêm để làm rõ kết luận, và cả ba sinh từ dữ liệu chứ không chép tay:

- **Khối kết luận** ở tab Tổng quan — số challenger, số CI vượt 0, khoảng cách tới ngưỡng;
- **Forest plot** ở tab Model — mọi CI của chênh lệch trên một hình, mốc 0 vẽ đậm;
- **Khối độ phân giải** — ngưỡng phân biệt được so với chênh lệch thực tế.

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest tests\test_webapp.py tests\test_webapp_accessibility.py -q
node scripts\smoke_webapp_browser.mjs
```

`22` test API, `12` test accessibility, `30` acceptance chạy trên Chrome headless.

Accessibility đã khóa bằng test: tương phản AA `4,5:1` cho mọi token chữ ở **cả hai** theme,
`:focus-visible`, `prefers-reduced-motion`, và mẫu tabs của WAI-ARIA đầy đủ — `aria-selected`,
`aria-controls`, roving tabindex, điều hướng bằng phím mũi tên.
