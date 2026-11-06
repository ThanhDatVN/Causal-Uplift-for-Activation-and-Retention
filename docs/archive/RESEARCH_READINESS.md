# Mức sẵn sàng nghiên cứu — còn thiếu gì để thành một bài có sức nặng

Ngày: 21/09/2026. Tài liệu này đối chiếu trạng thái thật với **hai** thước đo khác nhau, vì chúng không trùng nhau:

1. **Hoàn thành kế hoạch V4.1** — checklist R/WP/A/D/QG.
2. **Đủ tiêu chuẩn một bài nghiên cứu** — thứ mà kế hoạch V4.1 *không* nói tới, và đó mới là khoảng trống lớn nhất.

Mọi con số dưới đây đọc từ artifact trên đĩa. Nhật ký từng giai đoạn: [STAGE_LOG.md](STAGE_LOG.md).

## 1. Đối chiếu kế hoạch

Cập nhật 21/09/2026 sau đợt chạy dài. Nhật ký từng giai đoạn S21–S37: [STAGE_LOG.md](STAGE_LOG.md).

| Đợt | Trạng thái | Kết quả một dòng |
|---|---|---|
| R00, R01 | xong | Cổng coverage **ĐẠT** ở 2.000 world (S27), nhưng là **biến thể chọn hậu nghiệm** |
| R02 | xong | M01 thắng cả tám trên nhánh Mens |
| **R03** | **xong (S29)** | Tinh chỉnh cho **+0,00008** — không lật được R02. Nhưng **không family nào** chọn được cấu hình ổn định |
| **R04** | **xong (S30)** | **Không thành phần nào** lay chuyển; null fixture giữ đúng ±0,000000 |
| **R05** | **xong (S32)** | Gấp 4 lần dữ liệu **không** cải thiện; seed gần như tất định |
| **R06** | **xong (S31)** | Chọn 4 thay vì 1 **không** làm phồng false promotion. **Không phải cổng** (phân giải ±0,025) |
| **R07** | **xong (S34)**, bỏ chặn | **Không chiến lược nào thắng cả ba cơ chế**; `calibration_only` vô dụng với effect drift |
| **R08** | **xong (S33)** | Thiết kế làm giàu đạt cùng độ chính xác với **26% chi phí** ở `d` thấp, 59% ở `d` cao |
| **R09** | **quyết định KHÔNG mở** | Bốn lý do độc lập: [R09_CONFIRMATION_DECISION.md](../R09_CONFIRMATION_DECISION.md) |
| **R10** | **xong (S38)** | Lenta (SMS bán lẻ): **cả bảy** causal learner thắng M01, M01 bét. P1 và P3 đúng, **P2 sai** |
| **V08** | **xong, ĐẠT (S28)** | 4/4 readout phủ; tìm ra **hai lỗi thật** trong G06 khi dựng |
| V09 | xong | — |
| **Lặp lại nhánh Womens** | **xong (S35)** | **KẾT LUẬN ĐẢO NGƯỢC** — không phải R10. Cùng với S38 nó cho thấy ở ~300 event thứ hạng là nhiễu |

| Hạng mục | Trạng thái |
|---|---|
| Quality gate | **9/10 PASS**, release tier **RESEARCH_REPLICATED**. Còn NOT_RUN duy nhất: partner trial, cần đối tác và sổ chi phí thật — ngoài phạm vi theo ràng buộc đã khai báo |
| Test | **626 test**, ruff sạch. Thêm **A12, A14, A16, A17** — bốn acceptance test trước đây không chạy được vì thiếu bộ máy chúng kiểm ([test_acceptance_a12_a17.py](../../tests/test_acceptance_a12_a17.py)) |
| Hình | 4 hình, vẽ từ artifact và chỉ từ artifact |
| Compute | ~5 CPU-giờ trên ngân sách 150 |

## 2. Hai ứng viên bài báo, hai nhu cầu khác nhau

Repo đang chứa hai kết quả có bản chất khác hẳn nhau. Nhầm chúng làm một là rủi ro lớn nhất hiện tại, vì cái yếu hơn sẽ kéo cái mạnh hơn xuống.

### Ứng viên A — bài phương pháp (đã phát biểu lại, khiêm tốn hơn và đúng hơn)

Phát biểu **cũ**, đã bỏ: *"DR mất coverage vì lệch propensity, không vì outcome hiếm"*. Nó không sai nhưng nó mơ hồ, và nó tự xếp mình vào văn liệu weak overlap — nơi mà repo này **không** ở (xem [RELATED_WORK.md](../RELATED_WORK.md) §2).

Phát biểu **mới**:

> Ở overlap **hoàn hảo nhưng không cân bằng** — `e` hằng số, trọng số bị chặn, semiparametric bound hữu hạn — khoảng Wald DR vẫn mất coverage. Đại lượng chi phối có **dạng đóng**, `A = |1−2e|/√(n·h·rate·e(1−e))`, và trên lưới 36 cell nó phân tách **hoàn hảo** vùng phủ khỏi vùng không phủ, trong khi imbalance thì không.

Bằng chứng đã có:

| Bằng chứng | Số liệu |
|---|---|
| Công thức vs số đo | khớp trong **8–22%** trên `e` ∈ [0,5; 0,95], và **bằng 0 đúng ở e=0,5** |
| Lưới 36 cell × 1.000 world | `A` phân tách **18/18** cell cho `normal`; ngưỡng kẹp trong (0,202; 0,212] |
| Imbalance **không** phân tách | imbalance 0,30 trượt ở rate 0,5% và 1,0% nhưng **đạt** ở 3,5% |
| `N_eff` **không** phân tách | cặp trùng `N_eff = 10` cho hai phán quyết ngược nhau |
| Hiệu chỉnh Edgeworth mua được | vùng dùng được rộng ra **2,9 lần** (A 0,20 → 0,58) |
| Ba phương pháp khoảng đã thử | normal, studentized bootstrap B=499, Edgeworth + df hữu hiệu |
| Bias ở mọi cell hỏng | trong 1–2 MCSE, tức lỗi của khoảng chứ không phải estimator |

**Đóng góp còn lại sau khi trừ đi văn liệu** — phải nói thẳng, vì phần lớn đã có người làm:

| Không phải đóng góp | Đóng góp thật |
|---|---|
| Hiện tượng DR hỏng dưới overlap kém — Ma và cộng sự (2026) đã đo tới coverage 34% | Dạng đóng `A` cho chế độ `e` **hằng số**, kiểm bằng số trên chính estimator |
| Chặn Berry–Esseen — Qiu (2025) đã chứng minh | Chuyên biệt hoá: bốn thừa số gộp thành **một** số dùng được |
| Remedy thresholding — Dorn (2025), và ở đây vô nghĩa | Ngưỡng **đo được**, và một cổng gác **cơ khí** từ chối thiết kế ngoài vùng |

**Còn thiếu để đăng được:**

| Thiếu | Vì sao bắt buộc | Ước lượng |
|---|---|---|
| ~~Đối chiếu văn liệu weak/limited overlap~~ | **XONG 21/09 — và kết quả bác bỏ cách phát biểu hiện tại.** Xem [RELATED_WORK.md](../RELATED_WORK.md). Dorn (2025) đã chứng minh mệnh đề weak-overlap; quan trọng hơn, generator của repo dùng `e` **hằng số** nên **không** ở chế độ weak overlap. Ứng viên A phải phát biểu lại | xong |
| ~~Lưới ranh giới thay vì 2 điểm~~ | **XONG 21/09**, 36 cell × 1.000 world. `A` phân tách 18/18 cell cho `normal`, ngưỡng **0,20**; hiệu chỉnh Edgeworth mở rộng vùng **2,9 lần** lên 0,58. Imbalance và `N_eff` đều bị bác bỏ bằng số | xong |
| ~~Phát biểu giải tích~~ | **XONG 21/09.** Qiu (2025) đã chứng minh chặn Berry–Esseen cho đúng chế độ này; phần của repo là rút gọn `γ = (1−2e)/√(n·h·rate·e(1−e))`, khớp số đo trong 15% và **kiểm bằng test** ([test_design_asymmetry.py](../../tests/test_design_asymmetry.py)) | xong |
| **Hoặc phương pháp chạy được, hoặc mệnh đề bất khả** | Hiện tại là "ba cách đều không đủ", chưa phải kết luận. Công thức `γ` cho biết **vì sao**: ở `A ≈ 0,53` phân phối gần Poisson chứ không phải chuẩn-nhiễu-nhẹ, nên hiệu chỉnh một-số-hạng không thể đủ | phụ thuộc lưới |
| ~~Hình~~ | **XONG 21/09**, bốn hình trong [reports/v4/figures](../../reports/v4/figures), vẽ từ artifact và chỉ từ artifact, 12 test | xong |
| **Kiểm `A` ngoài họ generator này** | Ngưỡng đo trên **một** cơ chế với `e` hằng số. Thiết kế có `e(X)` thay đổi chưa được kiểm, và cổng hiện tin lời khai của caller | 8 giờ + compute |

### Ứng viên B — bài ứng dụng (yếu hơn, có một lỗ hổng phải vá trước)

> ~~Trong regime ít sự kiện, xếp hạng theo outcome đối chứng thắng các causal learner.~~

Phát biểu gốc **bị bác bỏ** ngày 21/09 (S35), rồi **lời giải thích đằng sau nó được xác nhận** (S38). Phát biểu hiện hành, và nó mạnh hơn cả hai bản trước:

> **Ở ~300 sự kiện, thứ hạng giữa các họ model là nhiễu; ở ~6.500 sự kiện, causal learner thắng dứt khoát.**

Bằng chứng là ba điểm trên hai dataset độc lập, cùng một giao thức:

| dataset | event | ai thắng | ghi chú |
|---|---:|---|---|
| Hillstrom Mens | 302 | **M01** (baseline) | causal learner thua cả tám |
| Hillstrom Womens | 251 | **M03** | cùng khách hàng, cùng chiến dịch, **ngược kết quả** |
| **Lenta** (SMS bán lẻ) | **6.498** | **cả bảy** causal learner | **M01 đứng bét, giá trị âm** |

Hai điểm đầu mâu thuẫn nhau ở cùng cỡ event — đó chính là nội dung "thứ hạng là nhiễu". Điểm thứ ba ở 21 lần số event thì không mâu thuẫn với gì cả: M06 (T-HGB) hơn baseline **+0,003334**.

**Một dự đoán đăng ký trước đã bị bác bỏ, và nó quan trọng:** bất ổn hyperparameter **không** biến mất ở 21× event. Không family nào chọn được cấu hình ổn định qua ba fold trên Lenta, y như trên Hillstrom. Đó không phải vấn đề đếm sự kiện, và thêm dữ liệu không sửa được — lý do chính để [không mở confirmation](../R09_CONFIRMATION_DECISION.md) vẫn nguyên vẹn.

| Thiếu | Ghi chú |
|---|---|
| ~~R03 bounded tuning~~ | **XONG (S29)** — và nó xác nhận kết luận R02 thay vì lật ngược |
| **Số dataset** | 2 là mỏng, và hai cái chạy **hai protocol khác nhau** (Orange dùng Qini-DR theo V3; Hillstrom dùng policy value theo V4.1), nên chưa phải replication sạch. Cần ≥4 dataset cùng một protocol — Criteo-UPLIFT, Lenta, MegaFon, X5 đều public |
| **R09 confirmation** | Split confirmation của Hillstrom **chưa mở lần nào**. Không có nó thì mọi số là development |
| **Power tính trước** | Chưa có power analysis cho so sánh chính |
| **R04 component study** | Không có nó thì không trả lời được *vì sao* baseline thắng, chỉ nói được *rằng* nó thắng |

## 3. Thiếu chung, và không nằm trong kế hoạch V4.1

Kế hoạch rất mạnh về validity nhưng im lặng về mấy thứ một bài báo bắt buộc phải có:

- ~~**Related work.**~~ **Xong 21/09** — [RELATED_WORK.md](../RELATED_WORK.md). Kết quả: phần lớn hiện tượng đã có tên, và repo đang gọi sai tên; ứng viên A phải phát biểu lại khiêm tốn hơn.
- **Một câu hỏi nghiên cứu duy nhất, phát biểu trước.** Claim ledger phân loại bằng chứng nhưng không pre-register câu hỏi chính của bài.
- ~~**Hình.**~~ **Xong 21/09** — bốn hình, `telco_churn.figures`. Mỗi giá trị đọc từ artifact; thiếu artifact thì bỏ qua kèm lý do.
- **Reviewer độc lập.** §15 cho phép ghi `self-reviewed` — hợp lệ cho repo, không hợp lệ cho bài báo.
- **Kiểm `A` ngoài họ generator đã quét.** Đây giờ là khoảng trống lớn nhất của ứng viên A: một công thức khớp trên một cơ chế là một quan sát, không phải một quy luật.
- **`make reproduce`** chạy từ raw tới hình. Repo đã có lock, manifest và artifact hash (tốt hơn phần lớn paper) nhưng chưa có một lệnh duy nhất.

## 4. "Đủ sức nặng" là bao nhiêu

| Chiều | Hiện tại | Ngưỡng tối thiểu |
|---|---|---|
| Dataset thật | **2, cùng protocol** (Hillstrom + Lenta), cộng một nhánh thứ hai làm kiểm ổn định | ≥4, cùng protocol |
| Monte Carlo | 9 scenario × 2.000 world, 32 readout | đủ — đây là điểm mạnh nhất |
| Confirmation | chưa mở | 1 lần, đóng băng trước |
| Replication ngoài domain | **1 (Lenta)**, ba dự đoán đăng ký trước, 2/3 đúng | ≥1 ✓ |
| Compute | ~3 CPU-giờ | 150 theo kế hoạch |

## 5. Thứ tự đề xuất

Làm **ứng viên A trước**: nó gần đích hơn, bằng chứng sạch hơn, và không phụ thuộc vào việc xin thêm dữ liệu.

1. ~~Tra văn liệu weak overlap~~ — **xong**, và nó đổi cách phát biểu: xem [RELATED_WORK.md](../RELATED_WORK.md).
2. ~~Phát biểu giải tích~~ — **xong**, `γ = (1−2e)/√(n·h·rate·e(1−e))`, đã ship thành `design_asymmetry_index` có test.
3. ~~Quét lưới ranh giới~~ — **xong**, ngưỡng `A ≤ 0,20` (`normal`) và `≤ 0,58` (Edgeworth không chặn df).
4. ~~Sửa cổng gác~~ — **xong** (S23): `CohortDesign` + ngưỡng đọc từ artifact, và cổng tự tố cáo khi PASS là chọn hậu nghiệm.
5. Chỉ sau đó quay lại ứng viên B, bắt đầu bằng **R03**.

Không mở R09 trước khi R03 và R04 đóng băng recipe: split confirmation chỉ dùng được một lần.
