# Tuần 6 — Confirmation, quyết định champion, web application và đóng gói

**Sprint:** 3
**Trọng tâm theo kế hoạch cũ:** Release QA, quay demo, handoff phase 2
**Trọng tâm thực tế:** Retrospective confirmation, promotion rule, web application, chẩn đoán bổ sung
**Trạng thái:** Đạt phạm vi mới; video demo và slide chưa làm

---

## 6.1 Vì sao đổi phạm vi

Tiếp nối lý do ở Tuần 5. Kế hoạch gốc là QA + video + slide. Thực tế: sau khi vòng cải tiến
cho kết quả "không challenger nào thắng", việc cần làm không phải quay video mà là **đóng
quyết định cho đúng luật** và **đóng gói thành sản phẩm dùng được**.

Web application thay cho Docker/CI vì nó giải quyết đúng vấn đề mà Docker định giải quyết
(chạy được ở nơi khác, có entrypoint rõ ràng) và thêm được thứ Docker không có: batch
scoring, truy nguồn từng con số, và registry hiển thị được.

**Cái mất:** Docker, CI, video demo 60–90 giây và slide deck 6–8 trang. Ghi trong
`report/SPRINT_3_FINAL_REPORT.md` mục 11.

---

## 2. Đã làm gì

| Việc | Kết quả |
|---|---|
| Ensemble + shortlist | `scripts/compare_improvement_candidates.py` |
| Retrospective confirmation | `scripts/run_sprint3_confirmation.py`, chạy đúng một lần |
| Quyết định champion | `output/sprint3/promotion_decision.csv` |
| Web application | `webapp/`, 17 endpoint, 6 tab |
| Scorer cho batch scoring | `scripts/build_champion_scorer.py` |
| Chẩn đoán proxy | `src/proxy_diagnostic.py` |
| Resource gate liên tục | `src/experiment.py::ResourceMonitor` |
| Power diagnostic | Chạy lại pipeline với outcome `visit` |
| Rà soát nghiên cứu | `planning/RESEARCH_LANDSCAPE_2026.md` |
| Runbook Kaggle đầy đủ | `docs/KAGGLE_RUNBOOK_COMPLETE.md` |

## 3. Cách hoạt động

### 3.1 Chốt shortlist trước, xem confirmation sau

`compare_improvement_candidates.py` chỉ đọc OOF prediction đã lưu; nó **không** fit lại
model gốc và **không** đọc confirmation. Nó dựng ba ensemble, xếp hạng theo
`policy_area_dr` trung bình qua hai seed, rồi ghi `shortlist.json`.

Ensemble weights được học trên OOF, và điểm ensemble dùng để so sánh còn được cross-fit
**thêm một lớp nữa**: chia OOF thành hai phần, học weights trên phần này, chấm phần kia.
Nếu học weights trên toàn bộ rồi chấm lại chính nó, ước lượng sẽ lạc quan.

### 3.2 Confirmation — một lần, không quay lại

`run_sprint3_confirmation.py`:

1. đọc shortlist đã khóa;
2. fit nuisance trên **toàn bộ** development rồi predict confirmation — hai tập rời nhau
   nên không cần cross-fitting ở bước này;
3. refit từng finalist trên toàn bộ development;
4. dựng ensemble bằng weights **đã học trên development**, không học lại;
5. paired bootstrap 500;
6. áp promotion rule và ghi quyết định.

Một chi tiết dễ sai được xử lý: một ensemble trong shortlist có thể có member **không** tự
lọt vào shortlist. Member đó vẫn phải được refit, nếu không weights sẽ bị chuẩn hóa lại và
ensemble trên confirmation không còn là ensemble đã học trên development. Runner tự phát
hiện và bổ sung, in ra `[shortlist] thêm <member> vì là member của <ensemble>`.

### 3.3 Promotion rule — kiểm tra theo từng seed

Bốn điều kiện, khóa từ Tuần 5:

1. `policy_area_dr` OOF của challenger lớn hơn Response **ở từng fold seed**;
2. point estimate trên confirmation cùng dấu;
3. paired 95% CI của chênh lệch có lower bound **lớn hơn 0**;
4. không regression về runtime gate, calibration hoặc guardrail.

Điều kiện 1 được hiện thực bằng cách join theo `fold_seed` chứ không so hai giá trị đã gộp:

```python
seeds_won = [s for s in shared_seeds if challenger[s] > champion[s]]
condition_1 = bool(n_seeds >= 2 and len(seeds_won) == n_seeds)
```

Lý do: S-Under7 thắng ở seed 101 nhưng thua rõ ở seed 202. Gộp lại sẽ che mất.

### 3.4 Web application

Nguyên tắc: **không train khi nhận request**. App đọc artifact đã freeze. Endpoint duy nhất
chạy model là `/api/score`, dùng scorer đã fit sẵn lưu bằng joblib.

```
output/sprint1|2|3/, output/improvement/
    │  đọc + cache theo mtime
    ▼
webapp/service.py   ArtifactRepository
    ▼
webapp/api.py       FastAPI, 17 endpoint
    ▼
webapp/static/      SPA, không CDN, canvas chart tự viết
```

Thiếu artifact nào thì endpoint trả `unavailable` và `/api/health` liệt kê đúng file còn
thiếu. App không bịa giá trị thay thế.

Ngưỡng top-k trong batch scoring lấy từ **lưới phân vị của population** lưu trong metadata
scorer, không phải từ lô tải lên. Nhờ vậy một lô 100 dòng vẫn được target đúng tỷ lệ budget
của population.

### 3.5 Ba cải tiến bổ sung của tuần

**(a) Chẩn đoán proxy-ordering.** Ba sprint cho thấy Response thắng; câu hỏi tiếp theo là
*khi nào nó ngừng thắng*. Fernández-Loría & Loría (arXiv 2206.12532) cho một điều kiện đủ:

```
theta_max < (1 − beta_max) / 2
```

`theta_max` là xác suất baseline lớn nhất; `beta_max` là chặn trên của CATE lớn nhất.

**(b) Resource gate liên tục.** Tuần 5 ghi nhận RAM khả dụng tụt xuống 1,55 GB dưới ngưỡng
2,0 GB mà không có gì dừng. `ResourceMonitor` nay nhận `min_available_gb`, bật cờ khi vi
phạm, và runner gọi `raise_if_breached()` tại **điểm dừng an toàn** — giữa hai fold và giữa
hai candidate.

Vì sao không dừng ngay lập tức: một thread nền không thể ngắt an toàn một lệnh fit LightGBM
đang giữ bộ nhớ, và ngắt giữa chừng dễ để lại artifact hỏng. Dừng ở điểm an toàn vẫn ghi
được registry đầy đủ.

**(c) Power diagnostic bằng outcome `visit`.** Câu hỏi: giao thức không tách được challenger
nào — đó là do dữ liệu hay do pipeline thiếu power? Chạy lại đúng pipeline với outcome
`visit` (4,7% thay vì 0,29%) trả lời được.

Phân biệt bắt buộc: dùng `visit` làm **outcome** là một estimand khác và hợp lệ — chính
nhóm tạo dataset khuyến nghị. Dùng `visit` làm **feature** vẫn là leakage và vẫn bị cấm.

## 4. Kết quả

### 4.1 Retrospective confirmation (1.397.959 dòng, 500 bootstrap)

| Model | `policy_area_dr` | AUTOC | Qini |
|---|---:|---:|---:|
| **Response** | **0,000912** | **0,003823** | 0,192989 |
| Ensemble-QAgg | 0,000911 | 0,003271 | **0,209845** |
| Ensemble-RankAverage | 0,000908 | 0,003332 | 0,195022 |
| S-Under7 | 0,000896 | 0,003116 | 0,205904 |
| X-Renormalized | 0,000890 | 0,003283 | 0,201812 |
| Rank-K2 | 0,000862 | 0,002454 | 0,184993 |

**Quyết định: không challenger nào đạt promotion rule. Champion giữ nguyên Response.**

| Điều kiện | Số challenger đạt |
|---|---:|
| 1 — thắng ở cả hai fold seed OOF | 0/8 |
| 2 — chênh lệch confirmation cùng dấu dương | 0/8 |
| 3 — paired CI có lower bound > 0 | 0/8 |

### 4.2 Phát hiện quan trọng nhất: metric bất đồng

Trên confirmation, **Qini xếp ba model trên Response** (Ensemble-QAgg 0,2098; S-Under7
0,2059; X-Renormalized 0,2018 so với Response 0,1930), trong khi metric chính
`policy_area_dr` và AUTOC đều xếp Response cao nhất.

Nếu Qini vẫn là metric chính, kết luận đã đảo chiều. Đây đúng là tình huống mà việc đăng ký
trước metric hierarchy ở Tuần 5 được thiết kế để xử lý.

### 4.3 Q-aggregation và giới hạn của DR risk

Weights hội tụ về `X-Renormalized 0,5 / S-Under7 0,5` ở cả hai seed và cả hai inner fold —
rất ổn định. Nhưng lý do ổn định lại là một hạn chế: DR loss của hai model là `0,01448225`
và `0,01448235`, chênh lệch tương đối khoảng `7e-6`.

Với outcome hiếm, variance của pseudo-outcome áp đảo phần chênh lệch do CATE, nên mục tiêu
gần như phẳng và Q-aggregation về bản chất đang **lấy trung bình chứ không chọn**.

Hệ quả thực hành: DR risk không nên là metric chọn model trên dữ liệu kiểu này. Đây là bằng
chứng cụ thể ủng hộ quyết định đặt `policy_area_dr` làm metric chính.

### 4.4 Chẩn đoán proxy — kết quả và một kết quả âm của chính tôi

Trên development OOF (5.591.836 dòng):

| Đại lượng | Giá trị |
|---|---:|
| `theta_max` (baseline lớn nhất) | 0,885764 |
| Ngưỡng với `beta_max = 0,598` | 0,200783 |
| Điều kiện đủ có thỏa không | **Không** |

Độ nhạy: điều kiện **hỏng ở mọi lựa chọn `beta_max`**, kể cả `beta_max = 0` (ngưỡng 0,5).
Nguyên nhân là `theta_max`, không phải lựa chọn `beta_max`. Chỉ 1.313 dòng (0,023%) có
baseline ≥ 0,5.

Cách đọc đúng: đây là điều kiện **đủ**, không phải điều kiện **cần**. Điều kiện hỏng
**không** kết luận Response xếp hạng sai — bằng chứng thực nghiệm nói ngược lại. Nó chỉ nói
khung lý thuyết này không bao phủ trường hợp đang xét.

**Kết quả âm về mở rộng của chính tôi:** tôi thêm một bảng áp điều kiện cho từng nhóm
top-b, kỳ vọng điều kiện sẽ thỏa ở budget nhỏ. Nó **không** thỏa ở bất kỳ budget nào, vì
các cá nhân có baseline cực cao lại chính là những người Response xếp đầu bảng. Mở rộng này
không thêm thông tin trên dataset này, và điều đó được ghi lại thay vì bỏ đi.

Tương quan thứ hạng giữa Response và các CATE estimator: S-Under7 `0,800`, Rank-K05 `0,744`,
plug-in tau `0,560`, X-Renormalized `0,485`.

### 4.5 Web application

17 endpoint, 6 tab, 19 contract test, 23/23 headless-browser acceptance.

Kiểm chứng chức năng thật: chấm 2.000 dòng Criteo ở budget 10% → target 9,9% số dòng, tỷ lệ
conversion nhóm được target `0,04545` so với `0,00000` ở phần còn lại.

### 4.6 Chất lượng

- pytest: 51 → **132**, toàn bộ pass.
- Browser acceptance: 23/23 (web app) và 11/11 (dashboard tĩnh).
- Link tài liệu: 94/94 relative link resolve.

## 5. Quyết định và lý do

1. **Không nới promotion rule** dù kết quả là "không cải thiện". Nới rule sau khi xem kết
   quả là hợp lý hóa hậu nghiệm.
2. **Giữ Response làm champion** và phát hành challenger kèm CI.
3. **Không viết "thử nhiều thứ và không cái nào chạy".** Rà soát tài liệu cho thấy đây là
   chế độ đã được mô tả trước — xem `planning/RESEARCH_LANDSCAPE_2026.md`.

## 6. Chưa xong

- ~~**Causal Forest Kaggle 20/30/50**~~ — đã hoàn tất ngày 06/08/2026, sau khi tuần 6
  chốt. Ba stage `passed`, đã chấm điểm, kết quả hoà với Response trên cả hai metric.
  Xem `report/CAUSAL_FOREST_REPORT.md`.
- **Docker, CI, video demo, slide deck** — lệch khỏi kế hoạch gốc, xem mục 6.1.
- **pROCini (JMLR 2025)** — trang paper công khai không có công thức; không hiện thực từ
  suy đoán.
- **External validity (Hillstrom)** và **A/B test production** — chưa có.

## 7. Bàn giao

Hướng tiếp theo và điều kiện mở, xếp theo tỷ lệ giá trị trên chi phí, nằm trong
`planning/RESEARCH_LANDSCAPE_2026.md` mục 5.

## 8. Câu hỏi cần mentor phản biện

Kết quả "không cải thiện" sau một vòng cải tiến có giao thức chặt có giá trị báo cáo tương
đương một kết quả cải thiện không? Và nếu có, nên trình bày nó thế nào để không bị đọc thành
thất bại kỹ thuật?
