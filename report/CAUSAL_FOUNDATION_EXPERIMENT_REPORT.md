# Báo cáo causal foundation v1

Ngày hoàn tất: 2026-08-09  
Protocol: `configs/causal_foundation_protocol_v1.json`  
Research khóa trước: `planning/CAUSAL_FOUNDATION_RESEARCH.md`

> **Follow-up:** phát hiện hậu nghiệm 1–2% đã được audit bằng paired simultaneous band trong
> [`TOP_TAIL_RESEARCH_V2_REPORT.md`](TOP_TAIL_RESEARCH_V2_REPORT.md). Audit không tìm thấy superiority
> evidence và không thay quyết định giữ Response của báo cáo lịch sử này.

## 1. Kết luận

Không causal learner mới nào thắng Response trên cả hai fold seed ở screen 15%. Binary DINA và
Anchored Pattern R đổi dấu theo seed; hai Anchored R tự do giảm `policy_area_dr` có hệ thống.

`Response-Sentinel` là candidate duy nhất qua screen point-estimate gate, nhưng full-development
đảo kết quả:

| Stage | Seed | Response | Response-Sentinel | Delta Sentinel − Response |
|---|---:|---:|---:|---:|
| Screen 15% | 101 | 0,000856779 | 0,000858831 | +2,052e-6 |
| Screen 15% | 202 | 0,000852166 | 0,000855201 | +3,035e-6 |
| Full | 101 | 0,000851809 | 0,000853022 | +1,213e-6 |
| Full | 202 | 0,000870409 | 0,000868334 | −2,075e-6 |

Full mean delta là `−4,310e-7`; stability gate thất bại. Champion giữ nguyên **Response**. Không
đọc confirmation Sprint 2, không chạy randomized confirmation mới và không chạy lại Causal Forest.

## 2. Research và protocol

Research review được hoàn tất trước khi protocol sinh kết quả. Ba giả thuyết:

1. Binary DINA học effect trên log-odds natural-parameter scale;
2. Anchored R giữ prognostic ranking và chỉ học residual đã shrink 0,25;
3. Anchored Pattern R partial-pool residual theo 53 sentinel structures.

Estimand vẫn là absolute conversion CATE. DINA chỉ dùng log odds ratio bên trong estimator rồi đổi
về probability difference. `visit`/`exposure` không làm feature; propensity cố định `0,85`.

Gate được khóa:

- smoke chỉ kiểm tra code path;
- screen dùng cùng 838.776 source rows, 244 control conversions, fold seed 101/202;
- candidate phải có `policy_area_dr > Response` ở cả hai seed;
- full-development chỉ chạy finalist và Response;
- promotion cần randomized confirmation mới với paired 95% CI lower bound > 0.

Ensemble được giữ làm diagnostic ở screen nhưng selection guard cưỡng chế
`diagnostic_ensemble_not_eligible`.

## 3. Kiểm thử trước dữ liệu thật

Các test mới xác nhận:

- DINA gradient/Hessian khớp finite differences;
- DINA khôi phục heterogeneous log-odds CATE ranking trên DGP tổng hợp;
- Anchored R khôi phục absolute CATE ranking trên DGP tổng hợp;
- Pattern R nhận ra sentinel moderator;
- invalid shrinkage, prior và probability clip bị từ chối;
- cross-seed comparison từ chối khác source rows/manifest contract;
- process-isolated OOF merge từ chối khác nuisance arrays;
- compact sentinel input cho LightGBM cho prediction giống dense input tuyệt đối.

Targeted suites đều pass trước các lần chạy tương ứng. Full repository suite được ghi ở mục 10 sau
khi hoàn tất tài liệu.

## 4. Smoke và resource audit

Attempt smoke 2% dừng ở 75,1% system RAM. Vì chỉ là code-path stage và chưa đủ event để chọn model,
protocol ghi amendment về 1%; run chính thức hoàn tất 55.919 dòng nhưng chỉ có 16 control
conversions, nên không số smoke nào được dùng để kết luận chất lượng.

Screen attempt đầu dừng sau shared nuisance, trước candidate score, ở 75,8% với 3,68 GB còn lại.
Trần tương đối được đồng bộ dần với hard floor tuyệt đối 2 GB; mọi amendment có reason/evidence trong
protocol. Không candidate/hyperparameter/metric nào đổi.

Full combined run cho thấy high-water tích lũy giữa candidates. Finalist được chạy process-isolated,
OOF chỉ ghép sau exact contract checks. Dense sentinel augmentation tiếp tục chạm hard floor, nên
transform được preallocate rồi chuyển sang compact mixed dtype. Peak của successful component nằm
trong guard; mọi manifest hoàn tất có `resource_gate_passed=true`.

## 5. Screen 15%

| Candidate | Mean `policy_area_dr` | Mean delta vs Response | Min delta | Gate |
|---|---:|---:|---:|---|
| Response-Sentinel | 0,000857016 | +2,543e-6 | +2,052e-6 | advance |
| Response | 0,000854473 | — | — | reference |
| Anchored-Pattern-R | 0,000851566 | −2,907e-6 | −1,480e-5 | fail: seed instability |
| DINA-CATE-Sentinel | 0,000849705 | −4,768e-6 | −2,033e-5 | fail: seed instability |
| Anchored-R25-Sentinel | 0,000830633 | −2,384e-5 | −3,635e-5 | fail: systematic regression |
| Anchored-R25 | 0,000828917 | −2,556e-5 | −4,301e-5 | fail: systematic regression |

Paired CI so với Response đều chứa 0. Ví dụ seed 101:

- Response-Sentinel: `+2,052e-6`, CI `[−8,868e-6; 1,373e-5]`, `P(delta>0)=0,64`;
- DINA: `+1,080e-5`, CI `[−7,758e-5; 1,175e-4]`, `P(delta>0)=0,53`;
- Anchored R25: `−4,301e-5`, CI `[−9,597e-5; 2,891e-6]`, `P(delta>0)=0,03`.

Seed 202 làm DINA đổi dấu thành `−2,033e-5`; Pattern R đổi từ `−1,480e-5` thành
`+8,986e-6`. Không được chọn seed có lợi.

## 6. Bất đồng metric và budget

DINA có AUTOC trung bình `0,003174`, cao hơn Response `0,003086`, nhưng Qini trung bình chỉ
`0,174370` so với `0,183628` và primary policy area thấp hơn. DINA cũng có calibration error
`0,000582–0,000720`, score standard deviation khoảng `0,0092`, lớn hơn Anchored R khoảng `0,004`.
Natural-parameter likelihood không tự loại finite-sample ranking variance.

Một phát hiện hậu nghiệm cần lưu cho research mới: cả bốn causal candidates đều có gross policy
value cao hơn Response tại budget 1% và 2%, trên cả seed 101 lẫn 202—4/4 so sánh mỗi model.
Nhưng primary metric đã khóa là diện tích 1–30%; Anchored R và Pattern R mất lợi thế ở phần budget
rộng. Không được dùng quan sát 1–2% để đảo quyết định hiện tại. Nếu business constraint thật là
extreme-low budget, phải đăng ký protocol mới.

## 7. Full-development finalist

Full pool có 5.591.836 dòng và 1.625 control conversions.

| Seed | Delta Sentinel − Response | Paired 95% CI | `P(delta>0)` |
|---:|---:|---:|---:|
| 101, 200 bootstrap | +1,213e-6 | `[−2,323e-6; 4,377e-6]` | 0,74 |
| 202, 100 bootstrap | −2,075e-6 | `[−6,186e-6; 1,267e-6]` | 0,09 |

Không CI nào loại 0 và sign không ổn định. `Response-Sentinel` không qua full stability gate; không
có finalist nào đủ điều kiện đi randomized confirmation.

## 8. Giải quyết từng giả thuyết

| Vấn đề | Can thiệp | Kết quả | Kinh nghiệm |
|---|---|---|---|
| Binary likelihood/scale mismatch | DINA log-odds + đổi về absolute CATE | đổi dấu theo seed, mean thấp hơn Response | đúng scale chưa đủ; cần shrink/calibrate effect và kiểm soát variance |
| Prognostic dominance | Anchored R25 | thua cả hai seed theo area | risk anchor không bảo toàn ranking khi flexible residual nhiễu ở budget rộng |
| Residual interaction variance | Sentinel flags cho Anchored R | cải thiện seed 101 so với R25 nhưng vẫn thua Response | representation giúp một phần, không khắc phục causal residual variance |
| Sparse sentinel moderators | Pattern partial pooling | thắng seed 202, thua seed 101 | coarse moderator có tín hiệu nhưng fold-sensitive |
| EDA point masses | Response-Sentinel | qua screen, thất bại full stability | effect rất nhỏ; screen point win không phải promotion evidence |

## 9. Quyết định và backlog

Quyết định máy đọc được nằm ở
`output/improvement/causal_foundation_analysis/analysis_summary.json`: giữ Response; không causal
candidate advance; không full candidate advance.

Protocol mới, nếu mở, nên ưu tiên:

1. xác nhận business budget 1–2% rồi đăng ký metric riêng;
2. DINA effect shrinkage/calibration được chọn trên synthetic hoặc inner validation độc lập;
3. event-aware inner folds/leaf constraints theo positive từng arm;
4. residual learner chỉ được rerank extreme top thay vì toàn bộ 1–30%;
5. Causal Forest: event-aware minimum leaf, balanced/honest sampling, leaf shrinkage, sentinel
   contract và cùng OOF artifact schema.

Các mục Causal Forest để sau khi hoàn thiện code nền tảng; chưa có Kaggle run mới trong vòng này.

## 10. Artifact, tái lập và kiểm thử cuối

Nguồn số:

- `output/improvement/causal_foundation_comparison/` — screen aggregate/gate/paired CI;
- `output/improvement/causal_foundation_finalist_comparison/` — full aggregate và seed 101 CI;
- `output/improvement/causal_foundation_finalist_seed202_comparison/` — seed 202 CI;
- `output/improvement/causal_foundation_analysis/` — hypothesis table, budget deltas, decision JSON;
- các thư mục `*_attempt*` — audit trail cho resource stop, không dùng để xếp hạng.

Lệnh phân tích không fit model và không đọc confirmation:

```powershell
.venv\Scripts\python.exe scripts\analyze_causal_foundation.py
```

Lệnh screen/finalist đầy đủ và process-isolated merge được liệt kê ở
[script index](../scripts/README.md). Theory/implementation chi tiết ở
[method guide](../docs/CAUSAL_FOUNDATION_METHOD_GUIDE.md).

Kiểm thử cuối:

- `pytest`: **212/212 pass**;
- web app browser acceptance: **23/23 pass**;
- dashboard browser acceptance: **12/12 pass**;
- registry: 97 identity, 0 duplicate sau khi sửa canonicalization `101`/`101.0`.

Cảnh báo còn lại là deprecation/physical-core detection từ dependency; không test failure. Targeted
tests không được coi là thay thế cho regression suite toàn repo.
