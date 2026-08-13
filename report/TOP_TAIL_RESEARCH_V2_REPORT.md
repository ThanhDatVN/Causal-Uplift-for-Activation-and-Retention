# Báo cáo top-tail research v2

Ngày hoàn tất: 2026-08-09  
Protocol: [`top_tail_research_protocol_v2.json`](../configs/top_tail_research_protocol_v2.json)  
Research basis: [`LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md`](../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)  
Inference guide: [`TOP_TAIL_POLICY_INFERENCE_GUIDE.md`](../docs/TOP_TAIL_POLICY_INFERENCE_GUIDE.md)

## 1. Quyết định

Giữ champion **Response**. Không causal candidate nào được promote.

Tất cả 16 causal point contrasts tại budget 1%/2% đều dương, nhưng không một pointwise 95% lower bound
và không một simultaneous 95% lower bound nào lớn hơn 0. Dấu point estimate là một giả thuyết đáng mang
sang dữ liệu randomized mới, không phải evidence về superiority trên dữ liệu hiện tại.

Quyết định máy đọc được:

```text
decision = retain_response_and_carry_hypothesis_to_new_preregistered_data
promotion_allowed = false
```

## 2. Phạm vi audit

Audit chỉ đọc hai frozen OOF artifact:

- `causal_foundation_screen_seed101`;
- `causal_foundation_screen_seed202`.

Cả hai dùng đúng **838.776 source rows**, population SHA-256
`2f9a75e0b5572f108993310af120552d129982dc2d4d2016ee2ed0f7a020806a`. Hai seed thay cách chia fold
trên cùng rows; chúng không phải hai sample/RCT độc lập.

Hard budget:

| Budget | Số người chính xác |
|---:|---:|
| 1% | 8.387 |
| 2% | 16.775 |

Family được đóng băng gồm Response và năm challenger. Simultaneous contrast family có:

```text
5 challenger × 2 fold seed × 2 budget = 20 cells.
```

Bootstrap ghép cặp dùng 200 draws, cùng row multiplicities cho mọi model/seed-view/budget. Critical value
maximum-standardized là **3,111821**. Interval có scope
`conditional_on_fixed_oof_scores`; không chứa model-refitting uncertainty.

## 3. Kết quả thống kê

Trong 20 cells có 16 cells thuộc bốn causal candidates:

| Kiểm tra | Kết quả |
|---|---:|
| Causal point delta > 0 | 16/16 |
| Pointwise 95% lower bound > 0 | 0/16 |
| Simultaneous 95% lower bound > 0 | 0/16 |
| Khoảng causal point delta | `+1,964e-6` đến `+8,166e-5` |

Hai ví dụ đại diện:

| Seed | Candidate | Budget | Delta vs Response | Pointwise 95% CI | Simultaneous 95% CI |
|---:|---|---:|---:|---:|---:|
| 101 | Anchored-R25 | 1% | `+2,938e-5` | `[−5,070e-5; +1,072e-4]` | `[−9,491e-5; +1,537e-4]` |
| 202 | DINA-CATE-Sentinel | 2% | `+5,518e-5` | `[−7,952e-5; +1,761e-4]` | `[−1,533e-4; +2,637e-4]` |

Không được diễn giải `16/16` như 16 replication độc lập: contrasts dùng cùng factual rows, chung nuisance
structure và budget được quan tâm sau khi primary whole-curve experiment đã được đọc.

## 4. Stability của membership

Overlap là tỷ lệ số thành viên chung trên đúng hard top-k giữa fold seed 101 và 202:

| Model | Overlap 1% | Overlap 2% | Gate tương lai |
|---|---:|---:|---:|
| Response | 80,52% | 80,76% | pass 75% |
| DINA-CATE-Sentinel | 61,31% | 65,47% | fail 75% |

Minimum causal overlap của toàn family là **61,31%**. Điều này cho thấy point policy value có thể cùng dấu
trong khi người được chọn thay đổi đáng kể khi chỉ thay outer folds. Training instability phải được xem là
một failure mode riêng, không được che bằng mean qua seeds.

## 5. Event support trong hard tail

| Seed | Model | Budget | Control events | Treated events | Support gate 100 control events |
|---:|---|---:|---:|---:|---:|
| 101 | Response | 1% | 141 | 1.122 | pass |
| 202 | Response | 1% | 137 | 1.117 | pass |
| 101 | Response | 2% | 169 | 1.409 | pass |
| 202 | Response | 2% | 167 | 1.419 | pass |
| 101 | DINA-CATE-Sentinel | 1% | 84 | 834 | fail |
| 202 | DINA-CATE-Sentinel | 1% | 91 | 857 | fail |
| 101 | DINA-CATE-Sentinel | 2% | 109 | 1.104 | pass |
| 202 | DINA-CATE-Sentinel | 2% | 110 | 1.126 | pass |

Minimum control events trong causal tail là **84**. Mỗi ví dụ trên có boundary tie size bằng 1, nên kết quả
không bị một tie block lớn chi phối; vấn đề chính là rare-event information và membership instability.

## 6. Vì sao không dùng kết quả này để chọn model

1. Budget 1%/2% là phát hiện hậu nghiệm sau khi primary area 1–30% không thắng.
2. Hai fold seed dùng cùng source rows.
3. Có nhiều challenger × budget × seed-view; pointwise interval không kiểm familywise selection.
4. Frozen-score bootstrap không chứa training/refitting uncertainty.
5. DINA không đạt stability/event gate ở top 1%.
6. Existing Sprint 2 confirmation đã được đọc trong lịch sử dự án và không thể trở thành holdout mới.

Kết luận phù hợp là “carry-forward hypothesis”, không phải “causal model thắng Response”.

## 7. Ràng buộc với vòng sau

Không model mới nào được thêm hồi tố vào 20-cell family này; muốn kiểm định thêm thì phải
đăng ký một protocol mới.

Thứ tự thực thi đã khóa và trạng thái từng bước:
[`../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md`](../planning/LATEST_CAUSAL_RESEARCH_AND_EXPERIMENT_PLAN_2026.md)
mục 9.

## 8. Artifact và provenance

Nguồn số chính thức:

- [`analysis_summary.json`](../output/improvement/top_tail_research_v2/analysis_summary.json);
- [`simultaneous_tail_differences.csv`](../output/improvement/top_tail_research_v2/simultaneous_tail_differences.csv);
- [`tail_event_support.csv`](../output/improvement/top_tail_research_v2/tail_event_support.csv);
- [`tail_membership_overlap.csv`](../output/improvement/top_tail_research_v2/tail_membership_overlap.csv).

Summary lưu protocol SHA, input manifest/NPZ SHA, bootstrap seed và code state. Namespace chính thức không
được ghi đè. Các thư mục `top_tail_research_v2_attempt*` là audit trail của lần sinh artifact trước khi
provenance guard hoàn chỉnh, không phải nguồn số ưu tiên.

Lệnh tái lập: [`../docs/REPRODUCTION.md`](../docs/REPRODUCTION.md) mục 7. Khi artifact chính
thức đã tồn tại, lệnh phải từ chối ghi đè; muốn chạy sensitivity phải dùng protocol và output
namespace mới.

## 9. Kiểm thử

Targeted hybrid/policy/protocol/synthetic/artifact/provenance suite tích hợp:

```text
89 passed, 8 dependency/environment warnings.
```

Full verification sau khi hoàn tất code và tài liệu:

```text
pytest: 258 passed, 17 dependency/environment warnings
web app browser: 23/23 passed
dashboard browser: 12/12 passed
compileall: passed
git diff --check: passed (chỉ có line-ending warnings từ Git trên Windows)
```

Các warning còn lại đến từ SHAP/Starlette/scikit-learn/SciPy và physical-core detection; không có test
failure. Targeted tests không được coi là thay thế full suite.
