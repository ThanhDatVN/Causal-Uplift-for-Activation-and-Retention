# Benchmark lịch sử

`streamB_bgnbd.py` thuộc hướng **Incremental CLV** — bài toán chưa mở. Nó dùng BG/NBD trên
Online Retail II, không liên quan tới pipeline causal uplift đang chạy.

Điều kiện mở hướng đó và cảnh báo surrogate paradox:
[`../../planning/RESEARCH_LANDSCAPE_2026.md`](../../planning/RESEARCH_LANDSCAPE_2026.md)
mục 3.2 và [`../../planning/incremental_value_product/README.md`](../../planning/incremental_value_product/README.md).

Benchmark đang dùng nằm ở thư mục cha: `bench_causal_forest.py`, `bench_metalearners.py`,
`results.csv`. Chúng được `scripts/bench_harness.py` và
`scripts/assess_causal_forest_feasibility.py` đọc.
