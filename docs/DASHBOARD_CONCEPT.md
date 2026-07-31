# Dashboard release — Causal Targeting Lab

## Mục tiêu

Cho stakeholder trả lời bốn câu hỏi trong một màn hình:

1. nên target bao nhiêu phần trăm;
2. incremental conversion offline ước lượng là bao nhiêu và uncertainty thế nào;
3. contact cost nào làm scenario âm;
4. số nào là dữ liệu quan sát, số nào là assumption.

## Artifact boundary

`scripts/export_dashboard_data.py` chỉ đọc `output/sprint2/` đã freeze. Nó không download,
không train model và không đọc artifact exploration cũ. `scripts/build_dashboard.py`
inline JSON thành `output/dashboard.html`; file chạy không cần server.

## Nội dung

- Response top-k champion, được chọn trên validation.
- Budget 0/1/5/10/20/30%.
- DR gross effect + 500-bootstrap CI.
- Value/conversion và cost/contact cùng đơn vị do user nhập.
- Break-even contact cost.
- Model Qini confirmation và paired CI quyết định.
- Provenance/hash, limitations và trạng thái Causal Forest.
- CSV export có run ID và assumption fields.

Không có “4 principal strata” cá nhân. Score âm không được gọi là Sleeping Dog.

## Acceptance

```powershell
.venv\Scripts\python.exe scripts\export_dashboard_data.py
.venv\Scripts\python.exe scripts\build_dashboard.py
node scripts\smoke_dashboard_browser.mjs
```

Browser smoke replay default, low-cost, high-cost và treat-none; kết quả hiện tại 11/11
pass. Screenshot: `output/dashboard_screenshot.png`.
