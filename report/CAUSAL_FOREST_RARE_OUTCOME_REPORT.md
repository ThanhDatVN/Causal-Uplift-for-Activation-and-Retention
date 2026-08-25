# Causal Forest cấu hình `rare-outcome` — báo cáo kết quả

- **Ngày:** 14/08/2026
- **Protocol:** [`causal_forest_rare_outcome_protocol_v1.json`](../configs/causal_forest_rare_outcome_protocol_v1.json) — đăng ký **trước** khi chạy
- **Nguồn số:** `output/causal_forest/sprint3_rare_outcome/`,
  `output/causal_forest/release/cf_sprint3_*`, `output/causal_forest/signal_sensitivity/`
- **Notebook:** [`04_causal_forest_rare_outcome.ipynb`](../notebooks/04_causal_forest_rare_outcome.ipynb)

## 1. Kết luận

**Champion giữ nguyên Response.** Causal Forest đứng đầu theo metric chính nhưng chênh lệch có
CI chứa 0, nên đây là hòa.

| | |
|---|---|
| `policy_area_dr` Causal Forest | `0,000914` — hạng **1/10** |
| `policy_area_dr` Response | `0,000912` — hạng 2/10 |
| Δ paired | `+1,198e-06` |
| CI 95% | `[-1,516e-05; +1,971e-05]` — **chứa 0** |
| `P(Δ > 0)` | `0,558` |
| Promotion rule | **không đạt** |

Nhưng báo cáo này có một phát hiện quan trọng hơn kết quả model, ở mục 5: **thay tín hiệu chấm
điểm làm đổi hẳn khoảng cách đo được giữa các model, trên cùng một bộ điểm và cùng những dòng
dữ liệu.**

## 2. Vì sao mở vòng này

Cấu hình `kaggle-safe` đã chạy ba mốc 20/30/50% dùng `min_samples_leaf=500`. Với treatment
85/15 và conversion rate control `0,1938%`, số sự kiện control kỳ vọng trong một lá là:

```text
500 x 0,15 x 0,001938 = 0,145
```

Honest splitting còn chia đôi tiếp, còn khoảng `0,073`. Nghĩa là **đại đa số lá có nhánh control
rỗng**, trong khi Causal Forest ước lượng chính hiệu số treated - control trong từng lá. Đó là
một cấu hình bị đặt sai cho outcome hiếm, và bất kỳ ai đọc báo cáo Causal Forest cũ đều có thể
phản bác rằng model thua vì lý do đó — phản bác ấy **đúng**.

Hạng mục này đã nằm trong backlog từ vòng causal foundation v1: *"Causal Forest: event-aware
minimum leaf, balanced/honest sampling, leaf shrinkage"*.

Profile `research` sẵn có trong repo **không** phải bản sửa: nó dùng `min_samples_leaf=200`, tức
`0,058` sự kiện control mỗi lá — đi sai hướng trên đúng ràng buộc đang bó.

## 3. Cấu hình và dữ liệu

| Tham số | `kaggle-safe` (cũ) | `rare-outcome` (vòng này) |
|---|---:|---:|
| `min_samples_leaf` | 500 | **10.000** |
| Sự kiện control mỗi lá | 0,145 | **2,906** |
| `n_estimators` | 200 | 500 |
| `max_samples` | 0,25 | 0,45 |
| `cv` | 2 | 3 |
| `inference` | False | False |

`model_y` và `model_t` giữ nguyên. Không đổi sang nuisance dạng classifier vì Sprint 3 đã thử
`discrete_outcome=True` cho DR/R-Learner và không cải thiện.

Split khác hẳn ba mốc cũ: fit trên **development Sprint 2/3** (5.591.836 dòng), predict trên
**confirmation** (1.397.959 dòng). Nhờ vậy điểm số đặt chung được bảng confirmation Sprint 3.

Ba ràng buộc toàn vẹn đều đạt trước khi chấm điểm:

- hash source-index của fit/validation/confirmation khớp manifest Sprint 2;
- `source_index` trùng khít **từng phần tử đúng thứ tự** với `confirmation_predictions.npz`;
- `Y` và `T` khớp tuyệt đối với confirmation đã đóng băng.

Điểm số được chấm bằng **DR signal đã đóng băng của Sprint 3**, không fit lại nuisance. Nhờ vậy
chênh lệch giữa hai model không thể lẫn với chênh lệch giữa hai tín hiệu chấm điểm.

## 4. Kết quả

### 4.1 Bảng metric trên confirmation

| Model | `policy_area_dr` | AUTOC | Qini | Score âm | Giá trị phân biệt |
|---|---:|---:|---:|---:|---:|
| **Causal Forest** | **0,000914** | 0,003763 | 0,189986 | 11,9% | 516.404 |
| Response | 0,000912 | **0,003823** | 0,192989 | 0,0% | 321.249 |
| Ensemble-QAgg | 0,000911 | 0,003271 | **0,209845** | 16,8% | 425.169 |
| Ensemble-RankAverage | 0,000908 | 0,003332 | 0,195022 | 0,0% | 431.891 |
| S-Under7 | 0,000896 | 0,003116 | 0,205904 | 2,5% | 368.900 |
| X-Renormalized | 0,000890 | 0,003283 | 0,201812 | 23,7% | 396.407 |
| Ensemble-BestSingle | 0,000890 | 0,003283 | 0,201812 | 23,7% | 396.407 |
| Rank-K2 | 0,000862 | 0,002454 | 0,184993 | 83,4% | 171.861 |
| Rank-K1 | 0,000852 | 0,002400 | 0,185657 | 82,2% | 178.617 |
| Rank-K05 | 0,000848 | 0,002388 | 0,186454 | 80,2% | 168.476 |

Bất đồng metric lặp lại đúng như các vòng trước: Causal Forest đứng đầu theo metric chính, nhưng
Response dẫn theo AUTOC và Ensemble-QAgg dẫn theo Qini. Thứ tự metric được đăng ký trước chính
là để tình huống này không trở thành lựa chọn hậu nghiệm.

### 4.2 So sánh cặp

500 paired bootstrap, mọi model dùng chung bootstrap weights.

| So với | Δ `policy_area_dr` | CI 95% | Kết luận |
|---|---:|---|---|
| Response | `+1,198e-06` | `[-1,516e-05; +1,971e-05]` | hòa |
| Ensemble-QAgg | `+2,32e-06` | `[-4,84e-05; +5,34e-05]` | hòa |
| Ensemble-RankAverage | `+5,85e-06` | `[-4,32e-05; +5,52e-05]` | hòa |
| S-Under7 | `+1,80e-05` | `[-4,62e-05; +8,11e-05]` | hòa |
| X-Renormalized | `+2,38e-05` | `[-2,42e-05; +7,29e-05]` | hòa |
| Ensemble-BestSingle | `+2,38e-05` | `[-2,42e-05; +7,29e-05]` | hòa |
| Rank-K2 | `+5,16e-05` | `[+2,52e-05; +8,18e-05]` | **CF vượt rõ** |
| Rank-K1 | `+6,17e-05` | `[+2,34e-05; +9,80e-05]` | **CF vượt rõ** |
| Rank-K05 | `+6,51e-05` | `[+2,26e-05; +1,072e-04]` | **CF vượt rõ** |

Causal Forest vượt rõ cả ba biến thể Rank-Learner và hòa với sáu model còn lại. Không có lower
bound nào dương so với Response, nên điều kiện promotion hỏng.

### 4.3 Can thiệp có hiệu lực đúng như thiết kế

| | `kaggle-safe` | `rare-outcome` |
|---|---:|---:|
| Sự kiện control mỗi lá | 0,145 | **2,906** |
| Tỷ lệ score âm | 19,6% | **11,9%** |

Log huấn luyện ghi thẳng con số đầu:
`[leaf] min_samples_leaf=10000 -> ky vong 2.906 su kien control moi la`.

Tỷ lệ score âm giảm gần một nửa là điều mong đợi: lá có sự kiện control thật thì ước lượng hiệu
số bớt bị nhiễu đẩy xuống âm. Model **không** suy biến — 516.404 giá trị phân biệt trên 1.397.959
dòng.

Tài nguyên: 107,4 phút, peak RSS `28,46` GB = `90,8%` của 31,35 GB, **vượt gate 75%**. Gate fail
thuần tuý vì ngưỡng RAM; `exit_code = 0`, artifact đủ số dòng, finite và aligned. Bộ nhớ bị chi
phối bởi `n_estimators × max_samples × n_rows` — số subsample giữ cho từng cây — chứ không phải
độ sâu cây; tích đó tăng khoảng `5,1` lần so với cấu hình cũ.

## 5. Phát hiện chính — tín hiệu chấm điểm đổi kết quả

Vòng này để lại một kết quả vượt ra ngoài phạm vi Causal Forest.

Ba mốc cũ được chấm bằng **IPW signal**. Để tách ảnh hưởng của tín hiệu khỏi ảnh hưởng của cấu
hình, artifact `kaggle-safe` cũ được chấm **lại** bằng DR signal, trên **đúng cùng những dòng đó
và đúng cùng bộ điểm** — không fit lại gì.

| Cấu hình / tập test | Signal | Δ vs Response | Nửa độ rộng CI | `P(Δ>0)` |
|---|---|---:|---:|---:|
| `kaggle-safe` / holdout Sprint 1 | IPW | `+4,96e-07` | `5,90e-05` | 0,504 |
| `kaggle-safe` / holdout Sprint 1 | **DR** | `+3,40e-05` | `4,59e-05` | **0,924** |
| `rare-outcome` / confirmation | DR đóng băng | `+1,20e-06` | `1,74e-05` | 0,558 |

Hai dòng đầu khác nhau **duy nhất** ở tín hiệu chấm điểm. Chênh lệch point estimate đổi **69
lần**, và `P(Δ>0)` đi từ gần như tung đồng xu `0,504` lên `0,924`.

Bảng xếp hạng cũng đổi. Trên cùng holdout Sprint 1:

| Hạng | Theo IPW | Theo DR |
|---:|---|---|
| 1 | Causal Forest | Causal Forest |
| 2 | **Response** | S-Learner |
| 3 | S-Learner | X-Learner |
| 4 | X-Learner | **Response** |
| 5 | DR-Learner | DR-Learner |
| 6 | T-Learner | T-Learner |

**Response tụt từ hạng 2 xuống hạng 4.**

### Cách đọc đúng, và cách đọc sai

Đọc sai: "vậy Response không phải model tốt nhất". Không được kết luận thế. Paired CI giữa
Causal Forest, S-Learner, X-Learner và Response theo DR **đều chứa 0**, nên bốn model này không
phân biệt được với nhau. Việc đổi thứ hạng nằm hoàn toàn trong nhiễu.

Đọc đúng: **thứ hạng theo point estimate không ổn định khi đổi tín hiệu chấm điểm.** Cả hai tín
hiệu đều không chệch cho `τ(X)` trên RCT, nhưng phương sai khác nhau rất xa, nên trên một mẫu hữu
hạn chúng cho hai bức tranh khác nhau. Đây là lý do dự án chuyển sang DR signal từ Sprint 3, và
vòng này là bằng chứng số trực tiếp cho quyết định đó.

### Hệ quả: con số "2.123×" không vững

`planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md` mục 10.1 tính rằng cần
`2.123×` toàn bộ Criteo mới phân biệt được Causal Forest với Response. Con số đó dùng công thức
`n · (nửa CI / Δ)²` với Δ đo bằng **IPW**.

Cùng công thức, cùng dữ liệu, chỉ đổi sang DR signal thì ra `3,81e06` dòng — tức khoảng **1,8×**
holdout hiện tại. Chênh nhau gần **7.800 lần**.

Cả hai con số đều **không đáng tin**, vì cùng một lý do: chúng chia cho một point estimate mà
chính nó không phân biệt được với 0. Khi `Δ → 0` do nhiễu, "số dòng cần thêm" tiến ra vô cùng;
điều đó phản ánh sự bất định của `Δ`, không phản ánh một yêu cầu dữ liệu có thật.

**Khuyến nghị:** bỏ cách diễn đạt "cần `N×` dữ liệu" khi CI còn chứa 0. Phát biểu đúng và vững là
phát biểu về độ rộng CI: trên confirmation, độ phân giải hiện tại là `±1,74e-05` trên thang
`policy_area_dr`, trong khi chênh lệch giữa các model hàng đầu nằm ở bậc `1e-06`.

## 6. Điều rút ra được

**1. Sửa cấu hình đúng chỗ có tác dụng đo được, nhưng không đủ để đổi kết luận.** Số sự kiện
control mỗi lá tăng 20 lần và tỷ lệ score âm giảm gần một nửa; Causal Forest lên hạng 1 theo
metric chính. Nhưng chênh lệch với Response vẫn ở bậc `1e-06` trong khi độ phân giải là `1e-05`.
Trần nằm ở tín hiệu, không ở cấu hình model — đúng như báo cáo Causal Forest cũ đã nghiêng về.

**2. Giá trị của vòng này chủ yếu là đóng một lỗ hổng lập luận.** Trước đây có thể phản bác rằng
Causal Forest thua vì lá quá nhỏ cho outcome hiếm. Nay phản bác đó đã được kiểm chứng và bác bỏ
bằng số: sửa đúng ràng buộc ấy, kết quả vẫn hòa. Kết luận "hòa" từ chỗ là một cấu hình bị đặt sai
trở thành một kết luận vững.

**3. Chọn tín hiệu chấm điểm quan trọng ngang chọn model.**
Cùng một bộ điểm, cùng những dòng dữ liệu, đổi từ IPW sang DR làm chênh lệch đo được đổi 69 lần
và làm Response tụt hai bậc. Mọi so sánh model chỉ có nghĩa khi tín hiệu chấm điểm được cố định
và ghi rõ — đó là lý do vòng này dùng DR signal **đã đóng băng** thay vì tự tính lại.

**4. "Cần N× dữ liệu" là một cách nói dễ gây hiểu nhầm.** Nó chia cho một đại lượng không phân
biệt được với 0, nên rất nhạy với nhiễu. Nên báo cáo độ rộng CI thay vì tỷ lệ dữ liệu cần thêm.

**5. Gate tài nguyên cần tách hai loại thất bại.** Run này fit xong, artifact hợp lệ, nhưng gate
báo `failed` vì RAM. Nếu đọc `status` mà không đọc `artifact_contract` thì sẽ bỏ đi một kết quả
dùng được. Notebook đã được sửa để đóng gói artifact **trước** khi kết luận.

## 7. Giới hạn

- **Đây là development evidence, không phải randomized confirmation mới.** Confirmation Sprint 2
  đã được quan sát ở Sprint 2 và Sprint 3, nên nó không còn là tập chưa từng nhìn.
- **Không thay dòng Causal Forest trong bảng release Sprint 1.** Đó là tập test khác và signal
  khác; hai kết quả không đặt chung bảng được.
- **Một cấu hình không đại diện cho họ Causal Forest.** `min_samples_leaf=10000` là một điểm; các
  hạng mục backlog còn lại — balanced/honest sampling, leaf shrinkage, sentinel contract — chưa
  thử.
- **Chưa đi qua promotion rule của Sprint 3.** Muốn vậy phải có `build_causal_forest()` trong
  `src/candidates.py` để chạy 3 fold × 2 fold seed; hiện Causal Forest mới được chấm rời.
- **Run vượt ngân sách RAM đã đăng ký.** Chạy ở 90,8% là sát mép; muốn tái lập an toàn trên Kaggle
  Free thì hạ `--n-jobs`, đã kiểm chứng không đổi điểm số.
- **Phần mục 5 là re-scoring artifact đã đóng băng**, không phải thí nghiệm mới. Nó cho thấy độ
  nhạy của phép đo, không cho thấy model nào tốt hơn.

## 8. Artifact

| Đường dẫn | Nội dung |
|---|---|
| `output/causal_forest/sprint3_rare_outcome/` | Điểm CATE, holdout, `gate_manifest.json`, `train.log` của run |
| `output/causal_forest/release/cf_sprint3_metrics.csv` | Bảng metric 10 model |
| `output/causal_forest/release/cf_sprint3_paired_comparisons.csv` | So sánh cặp 500 bootstrap |
| `output/causal_forest/release/cf_sprint3_summary.json` | Quyết định máy đọc được, cấu hình thực tế đã chạy |
| `output/causal_forest/signal_sensitivity/` | Artifact cũ chấm lại bằng DR signal — nguồn số của mục 5 |

Lệnh tái lập: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 8bis.
