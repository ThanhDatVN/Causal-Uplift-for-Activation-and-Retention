# Kế hoạch vòng tiếp theo — sau Sprint 3

Trạng thái: **chưa mở**. Tài liệu này đăng ký phạm vi và lý do trước khi chạy bất cứ
thứ gì, theo quy tắc trong `planning/README.md`.

Dự án có **ba sprint**. Đây không phải Sprint 4. Đây là vòng công việc tiếp nối sau khi
Sprint 3 đã chốt champion, gồm hai phần tách bạch:

- **Phần A** — hoàn tất hạng mục Causal Forest đang chạy trên Kaggle. Đây là việc *đã
  cam kết*, chỉ còn chờ kết quả.
- **Phần B** — vòng cải tiến mới. Chưa cam kết; mở hay không là quyết định riêng.

---

## 1. Vì sao kế hoạch này trông như thế này

Sprint 3 đã trả lời xong câu hỏi "có learner nào tốt hơn Response trên `conversion`
không". Câu trả lời dứt khoát, và nó định hình toàn bộ phạm vi bên dưới.

Screening 12 candidate, so từng cặp với Response bằng paired percentile bootstrap trên
cùng OOF rows:

| Outcome | Thách thức có CI chứa 0 | Khoảng cách của thách thức tốt nhất |
|---|---|---|
| `conversion` | **0/12** | 8,8% thấp hơn Response |
| `visit` | **4/6** | 1,9% thấp hơn Response |

Trên `conversion`, mọi CI đều nằm **hoàn toàn dưới 0**. Đây không phải "chưa đủ bằng
chứng để kết luận" mà là thua có ý nghĩa thống kê. Rank-Learner (ICLR 2026), DR, R, X,
S, T và ensemble Causal Q-aggregation đều không sống sót.

Số liệu gốc: `output/improvement/screen/paired_comparisons.csv` và
`output/improvement/screen_visit/paired_comparisons.csv`.

Nút thắt là dữ liệu, không phải model. `conversion rate = 0,002917`; nhánh control chỉ
có 4.063 conversion. Diễn giải lý thuyết đã có trong `RESEARCH_LANDSCAPE_2026.md`:
causal bias–variance tradeoff (Fernández-Loría & Provost, JMLR 2022), prognostic
dominance và counterfactual gradient collapse (VALOR 2026).

**Hệ quả cho kế hoạch:** thêm learner thứ 13 không đổi được kết luận. Dư địa nằm ở
estimand, ở tầng quyết định, và ở việc chỉ ra giới hạn của champion hiện tại.

---

## 2. Phần A — Hoàn tất Causal Forest — **ĐÃ XONG 06/08/2026**

Báo cáo đầy đủ: `report/CAUSAL_FOREST_REPORT.md`.

### A.1 Kết quả

Ba stage đều `passed`. Trên final test Sprint 1, Causal Forest **hoà** với Response:
`policy_area_dr = 0,001006` nhưng CI `[−6,0e-05; 5,8e-05]` chứa 0;
Qini `0,174678`, CI `[−0,0370; 0,0107]` cũng chứa 0. Champion không đổi.

Chấm chung bảng với năm model release vì dùng chung holdout (đã kiểm chứng từng phần
tử). Ghi chú xuất xứ: nó chạy muộn hơn và không qua quy trình chọn ứng viên trên
validation.

| Mốc | Peak RSS | RAM | Fit | Qini | So được với release |
|---|---:|---:|---:|---:|:---:|
| 20% | 5,52 GB | 17,6% | 8,5 phút | 0,178964 | không |
| 30% | 7,88 GB | 25,1% | 13,9 phút | 0,175315 | không |
| 50% | 12,73 GB | 40,6% | 25,0 phút | 0,174678 | **có** |

Session Kaggle cấp 31,35 GB RAM và 4 logical CPU — đủ cho cả ba stage trong 48 phút.
Quyết định không mua Colab Pro ở Sprint 2 vì thế là đúng.

Điểm CATE **không suy biến**: 912.579 giá trị phân biệt, cách ngưỡng đăng ký (10) năm
bậc độ lớn.

### A.2 Đã làm

1. ✅ Stage 20%, 30%, 50% trên Kaggle.
2. ✅ Tải zip, giải nén vào `output/causal_forest/`.
3. ✅ Chấm điểm bằng `evaluate_causal_forest.py` — bước trước đây chưa từng chạy.
4. ✅ Ghi ba run vào `output/improvement/registry.csv`.
5. ✅ Learning curve, phân bố điểm, năm biểu đồ (`analyze_` và `plot_causal_forest_release.py`).

Một việc còn để ngỏ: bản chấm điểm dùng **IPW signal**. Chạy thêm
`--signal dr` sẽ cho ước lượng variance thấp hơn, nhưng phải nạp lại Criteo và fit
nuisance nên tốn khoảng 16 phút. Kết luận hoà/không hoà nhiều khả năng không đổi vì CI
hiện tại rộng hơn chênh lệch hai bậc độ lớn.

### A.3 Chỉ stage 50% mới so được với bảng release

Ở `frac=0.50, test_size=0.30, seed=42`, holdout trùng khít final test Sprint 1:
2.096.940 dòng, `Y` và `T` giống hệt từng phần tử (đã kiểm chứng). Stage 20% và 30%
dùng tập test khác; `evaluate_causal_forest.py` tự phát hiện và in `[mode] standalone`.

### A.4 Ngoài Qini, phải xem độ phân tán điểm CATE

`min_samples_leaf=500` với conversion rate 0,002917 nghĩa là mỗi lá trung bình chứa
**1,4 conversion**, rồi honest splitting chia đôi tiếp giữa hai nhánh. Ước lượng ở từng
lá vì thế rất nhiễu.

Nếu điểm CATE gần như hằng số thì model đã **suy biến**, khác hẳn với "xếp hạng kém".
Hai kết luận này không được viết lẫn lộn. Early-stop rule Sprint 3 đã có ngưỡng
`constant_score_unique_threshold = 10` cho tình huống tương tự.

### A.5 Cập nhật những file nào khi có kết quả

Các chỗ đang ghi trạng thái "chưa chạy" và phải sửa đồng thời:

| File | Chỗ cần sửa |
|---|---|
| `CLAUDE.md` | dòng "Causal Forest Kaggle 20/30/50 remains pending" |
| `README.md` | mục "Causal Forest — hạng mục còn thiếu duy nhất" |
| `report/SPRINT_1_FINAL_REPORT.md` | bảng Qini release — thêm dòng Causal Forest kèm ghi chú xuất xứ (chạy muộn hơn, không qua chọn ứng viên trên validation) |
| `report/SPRINT_3_FINAL_REPORT.md` | mục trạng thái hạng mục còn thiếu |
| `report/weekly/WEEK_06.md` | mục việc còn lại |
| `planning/sprints.md` | quyết định cắt scope, ghi đã hoàn tất |
| `output/README.md` | thêm `output/causal_forest/` vào bảng artifact |
| `docs/COMPONENT_REVIEW_GUIDE.md` | checklist "ghi trạng thái chưa chạy" |
| `output/improvement/registry.csv` | thêm run |

Ba câu **không** được viết:

1. So Qini stage 20% hoặc 30% với `0,187886` của Response — khác tập test.
2. "Gate pass nghĩa là model tốt" — manifest có sẵn `"quality_not_assessed": true`.
3. "Causal Forest cho khoảng tin cậy cá nhân" — profile `kaggle-safe` đặt
   `inference=False`, không gọi `effect_interval()` được.

### A.6 Điều kiện hoàn tất Phần A

- [ ] Stage 50% `passed`, hoặc có lý do tài nguyên ghi rõ vì sao dừng ở 30%
- [ ] `evaluate_causal_forest.py` đã chạy, có Qini kèm CI 500 bootstrap
- [ ] Độ phân tán điểm CATE đã kiểm, phân biệt rõ "suy biến" với "xếp hạng kém"
- [ ] Chín file ở bảng A.5 đã cập nhật đồng bộ
- [ ] `pytest tests -q` vẫn pass

---

## 2bis. Phân tích độ nhạy — dữ kiện quyết định hướng đi

Sau khi Causal Forest chạy xong, câu hỏi "có model nào hơn Response trên Criteo
`conversion` không" trả lời được bằng số học chứ không bằng thêm thí nghiệm.

Từ CI paired bootstrap ở `output/causal_forest_release/cf_paired_comparisons_frac_0.5.csv`,
với `n = 2.096.940`:

| Metric | Giá trị Response | Chênh lệch CF − Response | Nửa độ rộng CI | MDE tương đối | Số dòng cần để phân biệt |
|---|---:|---:|---:|---:|---:|
| `policy_area_dr` | 0,00100516 | `+4,96e-07` | `5,90e-05` | **5,9%** | `2,97e10` = **2.123× toàn bộ Criteo** |
| Qini | 0,187886 | `−1,32e-02` | `2,39e-02` | 12,7% | `6,85e06` = **3,3× holdout hiện tại** |

Hai kết luận rất khác nhau:

**Trên metric chính, hai model không bao giờ phân biệt được.** CI rộng gấp 119 lần
chênh lệch. Cần 2.123 lần toàn bộ dataset — con số này không phải "khó", mà là không tồn
tại. Response và Causal Forest **tương đương về mặt vận hành** trên `policy_area_dr`.

Điều đó đóng hẳn hướng "tìm model tốt hơn trên Criteo `conversion`". Không phải vì đã thử
hết, mà vì phép đo không đủ phân giải để công nhận kết quả kể cả khi có.

**Trên Qini thì ngược lại — thiếu hụt chỉ là 3,3 lần.** Holdout hiện tại là 15% dữ liệu
(30% của mẫu 50%). Criteo có 13.979.592 dòng. Đánh giá cross-fitted trên toàn bộ dữ liệu
cho cỡ mẫu đánh giá gấp khoảng 6,7 lần, tức CI hẹp lại khoảng `sqrt(6,7) ≈ 2,6` lần —
đủ để CI của chênh lệch Qini loại trừ 0.

Nghĩa là: **một cải tiến về thiết kế đánh giá, không phải về model, có thể giải quyết
được một so sánh hiện đang hoà.** Rẻ, không cần dữ liệu mới, không cần model mới.

*Giới hạn của ngoại suy này:* nó giả định chênh lệch giữ nguyên khi `n` tăng và CI co
theo `1/sqrt(n)`. Dùng toàn bộ dữ liệu để đánh giá đòi hỏi cross-fitting, tức model được
huấn luyện trên tập khác — nên đây là **ước lượng cỡ mẫu**, không phải bảo đảm.

---

## 3. Phần B — Vòng cải tiến mới

Ba hướng dưới đây xếp theo giá trị kỳ vọng. Không bắt buộc làm cả ba.

### B.1 Vòng `visit` đầy đủ — giá trị cao nhất

**Nội dung.** Chạy lại đúng protocol Sprint 3 với `outcome = visit`: full development
pool, hai fold seed 101/202, 3-fold cross-fitting, retrospective confirmation, cùng bộ
metric và cùng promotion rule.

**Căn cứ.** Diemert et al., AdKDD 2018 — chính nhóm tạo dataset — khuyến nghị dùng
`visit` thay `conversion` vì tín hiệu uplift của `conversion` quá yếu. Screening 20% đã
xác nhận bằng số: 4/6 thách thức trở nên không phân biệt được với Response.

**Ba điều bắt buộc phát biểu khi báo cáo.**

1. Đây là **estimand khác**, trả lời câu hỏi khác: quảng cáo có gây ra lượt truy cập,
   không phải có gây ra đơn hàng. Không được trình bày như "đã cải tiến model
   conversion".
2. Dùng `visit` làm **outcome** là hợp lệ. Dùng `visit` làm **feature** vẫn là leakage
   và vẫn bị cấm. Ranh giới này không được nhoè.
3. Ở screening, ngay trên `visit` cũng **không có model nào thắng** Response — chỉ hoà.
   Nên kết quả kỳ vọng là *phép so sánh mạnh hơn*, không phải *xếp hạng tốt hơn*.

**Vì sao đáng làm dù nhiều khả năng vẫn không có challenger thắng.** Kết luận thu được
là: cùng một giao thức, trên `conversion` loại sạch 12 thách thức, trên `visit` cho ra
hoà. Điều đó chứng minh giao thức **phản ứng đúng với độ mạnh tín hiệu** chứ không phải
luôn luôn nói không. Đây là bằng chứng mạnh hơn việc tìm được một model nhỉnh hơn 2%.

**Chuẩn bị.** `scripts/run_oof_experiment.py` đã có sẵn cờ `--outcome {conversion,visit}`.

Trước khi chạy phải tạo và đăng ký một file protocol mới trong `configs/`, đặt tên
next_round_visit_protocol.json, sao theo mẫu `configs/sprint3_improvement_protocol.json`
với hai thay đổi: `estimand.outcome` thành `visit`, và `estimand.excluded_post_treatment`
vẫn giữ `visit` — vì nó bị loại ở vai trò **feature**, độc lập với việc nó được dùng làm
outcome. File này **chưa tồn tại**; tạo nó là hành động mở vòng.

### B.1bis Đánh giá cross-fitted trên toàn bộ dữ liệu — rẻ nhất

**Xuất phát từ mục 2bis.** Đây là hướng duy nhất tăng được độ phân giải của phép đo mà
không cần dữ liệu mới, model mới, hay estimand mới.

**Nội dung.** Thay holdout đơn 15% bằng đánh giá cross-fitted trên cả 13.979.592 dòng:
chia K fold, mỗi fold huấn luyện trên phần còn lại rồi chấm trên chính fold đó, ghép lại
thành một bộ điểm out-of-fold phủ toàn dữ liệu. Bootstrap paired trên bộ điểm đó.

**Lợi ích ước tính.** Cỡ mẫu đánh giá gấp khoảng 6,7 lần, CI hẹp lại khoảng 2,6 lần. Đủ
để chênh lệch Qini giữa Response và Causal Forest loại trừ 0. **Không** đủ cho
`policy_area_dr` — ở đó thiếu hụt là 2.123 lần, ngoài tầm với.

**Điều phải phát biểu rõ khi báo cáo.** Kết quả sẽ là: hai model phân biệt được theo
Qini nhưng vẫn không phân biệt được theo metric chính. Đó không phải mâu thuẫn cần giấu
— đó là phát hiện. Hai metric có độ nhạy khác nhau hai bậc độ lớn trên cùng bộ dữ liệu.

**Chi phí.** Cao hơn vẻ ngoài: mỗi fold phải fit lại Causal Forest trên ~11 triệu dòng.
Ở mốc 50% một lần fit mất 25 phút và 12,73 GB. Với K=5, ước tính 2,5–3 giờ và RSS tương
tự vì mỗi fold chạy tuần tự. Vẫn nằm trong một session Kaggle.

**Rủi ro.** Cross-fitting thay đổi model được đánh giá (huấn luyện trên tập khác holdout
đơn), nên kết quả **không** đặt cạnh bảng release Sprint 1 được. Phải báo cáo như một
phép đo riêng, không phải bản cập nhật của bảng cũ.

### B.2 Tầng quyết định

Metric chính là `policy_area_dr` trên dải budget 1–30%. Champion đã cố định, dư địa nằm
ở chỗ **dùng điểm số thế nào**:

- Hiệu chuẩn điểm thành giá trị gia tăng kỳ vọng trên mỗi khách hàng, để chọn budget
  theo kinh tế thay vì theo phân vị. Break-even hiện có: `0,009059`.
- Chính sách theo phân khúc thay vì một ngưỡng top-k duy nhất.

Hướng này không đụng vào trần thông tin của `conversion` nên không bị chặn bởi lý do ở
mục 1.

**Ràng buộc.** Mọi output value/cost vẫn là **kịch bản giả định**, không phải lợi nhuận
thực. Câu này đã có trong `report/SPRINT_2_FINAL_REPORT.md` và phải giữ.

### B.3 Chỉ ra chỗ Response xếp sai

Chẩn đoán proxy-ordering trong repo **không đạt điều kiện ở mọi mức `beta_max`**
(`output/improvement/proxy_diagnostic/`). Về lý thuyết không có bảo đảm Response xếp
hạng đúng, dù thực nghiệm nó thắng. `theta_max = 0,886` đến từ 1.313 dòng, tức 0,023%
dữ liệu — nền thống kê rất mỏng, phải nói rõ khi trích.

Việc cần làm: xác định *phân khúc nào* Response xếp sai, từ đó thử một chính sách lai —
xếp theo Response nhưng loại phân khúc có dấu hiệu hiệu ứng âm.

Đây là hướng rủi ro nhất trong ba hướng và cũng là hướng duy nhất có thể cải thiện thật
sự chất lượng xếp hạng trên `conversion`.

---

## 4. Ba hướng không làm

| Hướng | Lý do loại |
|---|---|
| Thêm meta-learner mới trên `conversion` | 12 candidate, 0/12 sống sót. Cái thứ 13 không đổi được kết luận |
| Tune hyperparameter trên `conversion` | Nút thắt là 4.063 control conversion, không phải dung lượng model |
| Deep learning cho CATE | Thêm variance, đúng chiều ngược với lập luận bias–variance của Fernández-Loría & Provost |

Ghi ở đây để lần sau không phải tranh luận lại. Nếu muốn mở lại một trong ba, phải nêu
bằng chứng mới chứ không nêu lại kỳ vọng cũ.

---

## 5. Quy tắc áp dụng cho cả hai phần

Không có ngoại lệ nào so với Sprint 3:

- Đăng ký protocol, metric, gate và promotion rule **trước** khi chạy.
- Không tune thêm trên test Sprint 1.
- Không đổi metric sau khi xem kết quả. Metric chính là `policy_area_dr`;
  Qini/AUUC/AUTOC/calibration là bằng chứng phụ.
- Mọi claim "A hơn B" phải kèm paired CI.
- Confirmation Sprint 2 đã bị quan sát ở Sprint 2 và Sprint 3; mọi vòng mới trên tập đó
  phải gọi là **retrospective confirmation**.
- Mọi run phải ghi vào `output/improvement/registry.csv`, kể cả run thất bại.
- Trước khi hiện thực phương pháp mới, đối chiếu `RESEARCH_LANDSCAPE_2026.md`. Nguồn ở
  mức xác minh `C` không được hiện thực; phải nâng lên `A` trước.
- Resource gate: `min_available_ram_gb = 2,0`, `max_system_memory_percent = 75`. Ở
  Sprint 3, RAM khả dụng đã tụt xuống 1,55 GB trong lúc chạy full OOF — gate hiện chỉ
  kiểm **trước** khi chạy, đây là hạn chế đã biết.

---

## 6. Thứ tự đề nghị

1. **Phần A** — đang chạy, hoàn tất trước. Đây là cam kết cũ.
2. **B.1** nếu mở vòng mới. Chi phí biết trước, kết luận rõ ràng dù thắng hay hoà.
3. **B.2** nếu muốn nghiêng về sản phẩm.
4. **B.3** chỉ khi chấp nhận rủi ro không ra kết quả.

Không chạy song song B.1 và B.3: cả hai đều đụng full development pool và resource gate
cấm `no_parallel_full_data_runs`.
