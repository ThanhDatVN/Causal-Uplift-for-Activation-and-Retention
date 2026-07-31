# Sprint 2 dashboard acceptance checklist

**Run:** `sprint2-local-exact-calibration-v1`
**Artifact:** `output/dashboard.html`
**Browser smoke:** 11/11 pass

| Scenario | Input | Expected | Kết quả |
|---|---|---|---|
| Default | top 10%, value=1, cost=0,0005 | net dương, CI hiện rõ | Pass |
| Low cost | top 10%, cost=0,00025 | “Scenario dương” | Pass |
| High cost | top 10%, cost=0,02 | net âm + warning ngoài grid | Pass |
| Treat none | budget 0% | target=0, value=0 | Pass |

Các check khác:

- [x] Champion hiển thị `Response`.
- [x] Không có principal-strata customer cards.
- [x] Causal Forest hiển thị `PENDING`.
- [x] 6+ dashboard cards render.
- [x] Negative net dùng warning style.
- [x] Screenshot tạo được.
- [x] HTML self-contained.

Kết nối browser in-app của phiên phát triển không khả dụng, nên acceptance dùng Chrome
headless local. Kết quả được ghi từ automated browser check, không phải manual check. Có thể mở trực tiếp
`output/dashboard.html` để review visual.
