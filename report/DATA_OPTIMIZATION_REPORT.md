# Báo cáo tối ưu từ phân tích dữ liệu — protocol v1

Ngày chốt: 2026-08-09  
Protocol: `configs/data_optimization_protocol_v1.json`  
Phạm vi bằng chứng: development OOF, **không đọc confirmation**

## 1. Kết luận điều hành

Vòng này bắt đầu từ bốn vấn đề quan sát được trong EDA và kết quả Sprint 3, sau đó ánh xạ
mỗi vấn đề sang một can thiệp có thể kiểm chứng. Kết quả:

- `Response-Sentinel` đứng đầu theo metric chính ở cả seed 101 và 202;
- mức tăng trung bình so với Response là `2,5434e-06`, tương đối `0,298%`;
- paired 95% CI ở seed chính là `[-8,1058e-06; 1,2925e-05]`, vẫn chứa 0;
- `Response-Sentinel` **đạt gate đi tiếp**, nhưng **chưa được promote**;
- champion hiện hành vẫn là **Response**;
- Funnel-S và Funnel-S-Sentinel bị loại ở screening;
- bước hợp lệ tiếp theo là một randomized confirmation campaign mới, không tái sử dụng
  confirmation Sprint 2 đã được quan sát.

Quyết định máy đọc được nằm ở
`output/improvement/data_opt_comparison/optimization_decision.json`. Bảng vấn đề → can thiệp →
kết quả nằm ở `problem_resolution.csv` cùng thư mục.

## 2. Vì sao quay lại từ bước phân tích dữ liệu

### 2.1 Outcome conversion hiếm

Conversion rate toàn bộ dữ liệu là `0,2917%`. Development pool đầy đủ chỉ có 1.625 conversion
ở control. Trong screen 15%, còn 244 control conversion — vừa vượt gate đăng ký trước là 200,
nhưng vẫn là chế độ phương sai cao.

Can thiệp: phân rã

```text
P(conversion=1 | X,T)
= P(visit=1 | X,T) × P(conversion=1 | visit=1,X,T)
```

`visit` chỉ là auxiliary training outcome và sample mask. Hàm `predict` vẫn chỉ nhận `f0..f11`;
không có post-treatment feature ở thời điểm ra quyết định.

### 2.2 Cấu trúc sentinel-like

EDA cho thấy 6/12 feature có hơn 90% khối lượng tại đúng một giá trị, chỉ có 53 pattern
“ở mode/khác mode”, và heterogeneity theo các pattern này có ý nghĩa. Cấu trúc này có thể khó
được biểu diễn ổn định khi conversion hiếm.

Can thiệp: trong từng OOF fold, chỉ từ `X_train`:

1. ước lượng mode và mode share của từng cột;
2. thêm cờ bằng mode cho các cột đủ ngưỡng;
3. thêm tổng số cờ trên mỗi dòng.

Augmenter không đọc treatment hay outcome; mode của validation fold không được dùng khi fit.

### 2.3 Prognostic dominance

EDA mô tả `corr(p0, tau)=0,98384`; trong dữ liệu này, ranking theo baseline risk gần trùng ranking
theo uplift. Đây là lý do Response là baseline khó vượt, không phải dấu hiệu đủ để đổi estimand.

Can thiệp quy trình: Response là reference bắt buộc. Một challenger chỉ đi tiếp nếu
`policy_area_dr` lớn hơn Response trên **mọi** fold seed đã đăng ký.

### 2.4 Metric không đồng thuận

Sprint 3 đã cho thấy model có thể tốt hơn theo Qini nhưng kém hơn theo policy value. Vì sản phẩm
ra quyết định theo budget 1–30%, protocol tiếp tục khóa `policy_area_dr` làm metric chính; AUTOC,
Qini và DR risk chỉ là metric phụ.

## 3. Thay đổi trong pipeline

| Thành phần | Thay đổi | Guard |
|---|---|---|
| Split/cache | Cache v4 lưu auxiliary outcome theo đúng `source_index`; có đường nâng v3 → v4 | kiểm tra SHA dữ liệu, SHA cache, split hash, độ dài và binary domain |
| Feature | `SentinelFeatureAugmenter` fit riêng trong mỗi fold | chỉ đọc `X_train`, không đọc `T/Y` |
| Candidate | `funnel_s_learner` học visit và conversion-given-visit | `visit` không phải input lúc scoring; assert `conversion <= visit` |
| Cross-fitting | 3 fold, seed 101 và 202 | mọi dòng được score bởi model không fit trên dòng đó |
| Selection | gate thắng Response trên từng seed | không dùng mean top-N để thay gate |
| Provenance | protocol path ghi trong run manifest; artifact quyết định băm SHA input | không đọc confirmation trong script phân tích |
| Tài nguyên | bỏ split không dùng sau subsample, giữ resource monitor | cả hai screen đều đạt gate RAM |

Sprint 3 và artifact đã phát hành không bị ghi đè. Đây là protocol riêng, có ID
`data-optimization-v1`.

## 4. Thiết kế screening

| Thuộc tính | Giá trị |
|---|---:|
| Development fraction | 15% |
| Số dòng | 838.776 |
| Treated / control | 712.960 / 125.816 |
| Conversion treated / control | 2.203 / 244 |
| Cross-fitting | 3 fold |
| Fold seed | 101 và 202 |
| Budget grid | 1%, 2%, 5%, 10%, 15%, 20%, 25%, 30% |
| Bootstrap seed chính | 100 lần |
| Bootstrap seed phụ | 30 lần, chỉ kiểm tra độ lặp dấu |

Screen 15% là bằng chứng development OOF, không phải confirmation và không phải release test.

## 5. Kết quả model

| Model | Seed 101 | Seed 202 | Mean `policy_area_dr` | Δ mean vs Response |
|---|---:|---:|---:|---:|
| **Response-Sentinel** | **0,000858831** | **0,000855201** | **0,000857016** | **+0,000002543** |
| Response | 0,000856779 | 0,000852166 | 0,000854473 | 0 |
| X-Renormalized | 0,000847377 | 0,000816124 | 0,000831750 | −0,000022722 |
| Funnel-S-Sentinel | 0,000826904 | 0,000789146 | 0,000808025 | −0,000046448 |
| Funnel-S | 0,000825798 | 0,000781736 | 0,000803767 | −0,000050706 |
| S-Under7 | 0,000826134 | 0,000778575 | 0,000802355 | −0,000052118 |
| S-Sentinel-Under7 | 0,000814791 | 0,000759424 | 0,000787107 | −0,000067365 |

Hai kết luận kỹ thuật quan trọng:

1. sentinel flags cho Response có cùng dấu dương ở cả hai seed, nhưng thêm sentinel vào S-Learner
   lại giảm `1,5247e-05` trung bình so với S-Under7;
2. funnel giảm từ `4,6448e-05` đến `5,0706e-05` so với Response, nên việc tăng prevalence của
   intermediate target không chuyển thành policy ranking tốt hơn cho conversion.

## 6. Suy luận thống kê và quyết định

So sánh paired `Response-Sentinel − Response` tại seed chính:

| Thước đo | Giá trị |
|---|---:|
| Point difference | `+2,0520e-06` |
| 95% CI | `[-8,1058e-06; 1,2925e-05]` |
| Bootstrap probability difference > 0 | `0,70` |
| AUTOC difference | `+2,4873e-05` |
| AUTOC 95% CI | `[-2,6180e-05; 8,1354e-05]` |

CI chứa 0 nên chưa có bằng chứng để nói challenger tốt hơn. Tuy nhiên gate “đi tiếp” chỉ yêu cầu
point estimate dương trên cả hai seed; `Response-Sentinel` đạt điều kiện này với chênh lệch
`+2,0520e-06` và `+3,0349e-06`.

```text
EDA → protocol riêng → smoke → OOF seed 101/202 → gate từng seed
                                                    ├─ Funnel: loại
                                                    └─ Response-Sentinel: đi tiếp
                                                                          ↓
                                                        randomized confirmation mới
```

Trạng thái cuối vòng:

- `advances_to_new_confirmation = true`;
- `promoted = false`;
- `promotion_decision = hold_response_champion`.

## 7. Giải quyết từng vấn đề

| Vấn đề | Kết quả | Quyết định |
|---|---|---|
| Conversion hiếm | funnel hợp lệ về code nhưng kém hơn Response khoảng 5,4–5,9% tương đối | loại funnel; không tuning tiếp trên cùng screen |
| Sentinel-like structure | giúp Response khoảng 0,30%, không giúp S-Learner | giữ duy nhất Response-Sentinel để xác nhận mới |
| Prognostic dominance | chỉ một challenger thắng point estimate ở cả hai seed; CI chưa tách khỏi 0 | giữ Response làm champion |
| Metric disagreement | QAgg ưu tiên funnel theo DR loss nhưng policy mean kém Response `3,3792e-05` | không dùng DR risk/Qini để override metric chính |
| Shortlist top-N | có thể cho model thua reference đi tiếp | đã thay bằng gate theo từng seed và sinh `advancement_decision.csv` |

Không thực hiện thêm vòng tuning hậu nghiệm trên cùng screen. Nếu đổi feature, hyperparameter hay
metric sau khi đã thấy bảng này, phải đăng ký protocol v2 và xem đó là một vòng development mới.

## 8. Tài nguyên và kiểm chứng

| Run | Elapsed | Peak process RSS | Min RAM available | Max system memory | Gate |
|---|---:|---:|---:|---:|---|
| seed 101 | 336,6 s | 0,633 GB | 4,314 GB | 71,6% | pass |
| seed 202 | 218,9 s | 0,621 GB | 4,258 GB | 72,0% | pass |

Các kiểm thử mới bao phủ:

- fit/transform sentinel fold-local;
- auxiliary outcome còn thẳng hàng sau undersampling;
- funnel phục hồi ranking trên RCT tổng hợp;
- invariant `conversion <= visit`;
- cache v3 → v4 và căn chỉnh `source_index`;
- gate advancement phải thắng trên mọi seed.

Kết quả kiểm chứng cuối:

- `194/194` test Python pass;
- `23/23` acceptance check của web app pass;
- `12/12` acceptance check của dashboard pass;
- `git diff --check` và compile toàn bộ `src/`, `scripts/`, `tests/` pass.

Các warning còn lại đến từ deprecation của dependency và phát hiện số physical core trong môi
trường sandbox; không có warning nào làm test fail.

## 9. Tái lập

Lệnh đầy đủ: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 5.

## 10. Giới hạn còn lại

- 244 control conversions đủ qua gate screening, không đủ để biến chênh lệch 0,30% thành kết luận
  chắc chắn.
- Seed 202 chỉ có 30 bootstrap replicate; nó dùng để kiểm tra dấu, không phải interval chính.
- `visit` là post-treatment; cách dùng ở đây chỉ dựa vào chain-rule factorization cho prediction,
  không diễn giải hệ số qua visit là direct/mediated causal effect.
- Feature ẩn danh ngăn diễn giải business moderator.
- Criteo không có revenue, margin, contact cost hay retention horizon.
- Không có dữ liệu randomized mới trong repository, nên không thể hoàn tất promotion ở vòng này.

## 11. Artifact nguồn

- `output/eda/run_manifest.json`
- `output/eda/prognostic_dominance.json`
- `output/improvement/data_opt_screen_seed101/`
- `output/improvement/data_opt_screen_seed202/`
- `output/improvement/data_opt_comparison/candidate_aggregate.csv`
- `output/improvement/data_opt_comparison/paired_comparisons.csv`
- `output/improvement/data_opt_comparison/advancement_decision.csv`
- `output/improvement/data_opt_comparison/problem_resolution.csv`
- `output/improvement/data_opt_comparison/optimization_decision.json`
