# Suy luận cho policy hard-budget ở top-tail

- **Vòng sinh ra tài liệu:** vòng 7 — top-tail research v2
- **Ngày cập nhật:** 09/08/2026
- **Protocol:** [`../../configs/top_tail_research_protocol_v2.json`](../../configs/top_tail_research_protocol_v2.json)
- **Hiện thực:** [`../../src/policy_evaluation.py`](../../src/policy_evaluation.py),
  [`../../scripts/analyze_top_tail_evidence.py`](../../scripts/analyze_top_tail_evidence.py)
- **Kết quả:** [`../../report/07_TOP_TAIL_RESEARCH.md`](../../report/07_TOP_TAIL_RESEARCH.md)
- **Đọc trước:** [`06_RARE_OUTCOME_LEARNERS.md`](06_RARE_OUTCOME_LEARNERS.md)

Vòng 7 kiểm định riêng tín hiệu quan sát được ở ngân sách 1–2%. Tài liệu này mô tả cách suy
luận cho một **họ so sánh đã đóng băng**: hard top-k chính xác, khoảng tin cậy ghép cặp và
đồng thời, cùng các điều kiện mà một chênh lệch có ý nghĩa thống kê vẫn chưa đủ để triển khai.

## 1. Đại lượng cần ước lượng

Với score `s_j(x)` và budget cố định `b`, policy lấy đúng:

```text
k = floor(n*b)
pi_jb(x_i) = 1 nếu i nằm trong k score cao nhất, ngược lại bằng 0.
```

Đại lượng đích là gross incremental conversion ITT trên toàn quần thể:

```text
psi_jb = E[pi_jb(X) {Y(1)-Y(0)}].
```

Đây không phải CATE trung bình của nhóm top. `psi_jb` đã nhân với tỷ lệ được target, nên có đơn vị
incremental conversion trên mỗi khách hàng của quần thể.

## 2. Effect signal và factual evaluation

Trên randomized holdout với propensity biết trước `e=0,85`, dùng cross-fitted nuisance:

```text
Gamma = mu1-mu0
        + T/e       * (Y-mu1)
        - (1-T)/(1-e) * (Y-mu0).

psi_hat_jb = mean[pi_jb(X) * Gamma].
```

Policy score và nuisance không được fit bằng outcome của chính dòng đang chấm. Evaluation phải dùng factual
`T,Y`; không thay bằng trung bình counterfactual do chính outcome model dự đoán. Cảnh báo này phù hợp với
winner's-curse failure được phân tích bởi
[Bastani, Bastani & McLaughlin (2026)](https://arxiv.org/abs/2602.08892).

## 3. Paired bootstrap

Hai policy được so trên cùng những dòng dữ liệu, nên chênh lệch đúng là:

```text
Delta_jb = psi_jb - psi_reference,b.
```

Mỗi lần rút bootstrap dùng **cùng bội số dòng** cho mọi model, seed-view và ngân sách. Làm như vậy giữ
covariance ghép cặp; bootstrap riêng từng model rồi trừ hai interval sẽ rộng/sai cấu trúc hơn.

Trong lần rà soát hồi cứu, hai fold seed có cùng dòng nguồn. Chúng được xem như hai training views của
cùng sample, không phải hai sample độc lập. Script cố ý dùng cùng RNG seed/draw count để row bootstrap của
hai view căn hàng.

## 4. Simultaneous maximum-standardized band

Giả sử họ so sánh có các ô `c=1..C`. Từ bootstrap draw `r`:

```text
D_hat_c      = observed paired difference
D_star_rc    = bootstrap paired difference
se_c         = std_r(D_star_rc)
Z_r          = max_c |D_star_rc - D_hat_c| / se_c
q            = empirical quantile_(1-alpha)(Z_r)

simultaneous CI_c = D_hat_c ± q * se_c.
```

Nếu một cell có zero bootstrap variance, implementation chỉ cho phép nó khi mọi deviation bằng 0; nếu
không sẽ fail thay vì chia cho 0. Một critical value duy nhất được dùng cho toàn họ. Đây là finite
frozen-family analogue của việc chọn policy bằng valid simultaneous lower confidence bound trong
[Policy Learning with Confidence](https://arxiv.org/abs/2502.10653).

`paired_policy_difference_band()` trả cả pointwise và simultaneous intervals, nhưng gate dùng
simultaneous lower bound. Họ so sánh phải được định nghĩa trước khi đọc kết quả.

## 5. Phạm vi suy luận

Band hiện tại có scope:

```text
conditional_on_fixed_oof_scores
```

Nó phản ánh sampling uncertainty của factual evaluation **có điều kiện trên OOF scores đã đóng băng**.
Nó không refit model trong mỗi bootstrap draw, nên không chứa toàn bộ algorithm/training uncertainty.
Training instability được báo riêng bằng:

- sign/delta qua registered fold seeds;
- top-k overlap fraction;
- Jaccard;
- clip fraction và coefficient stability cho hybrid tương lai.

Không được gọi interval này là unconditional confidence interval cho cả quá trình model selection.

## 6. Event-support và cutoff diagnostics

`top_tail_event_support()` báo cho mỗi model/budget:

- `tail_rows`, `treated_rows`, `control_rows`;
- `treated_events`, `control_events`;
- `boundary_tie_size`.

`top_tail_overlap()` báo overlap fraction và Jaccard giữa hai score views. Protocol tương lai yêu cầu tối
thiểu 100 control events trong evaluation tail và overlap ít nhất 0,75. Đây là guard thực nghiệm, không
phải theorem phổ quát.

Tie lớn tại cutoff có nghĩa policy không thật sự phân biệt được các row quanh ngưỡng. Khi đó exact hard-k
phụ thuộc stable-order convention; phải báo tie thay vì che nó bằng một curve nội suy.

## 7. Quy tắc diễn giải

| Tình huống | Kết luận được phép |
|---|---|
| Point delta dương, pointwise CI chứa 0 | Có tín hiệu, chưa có superiority evidence |
| Pointwise lower bound > 0 nhưng simultaneous lower bound ≤ 0 | Không qua familywise gate |
| Simultaneous lower bound > 0 nhưng overlap/event gate fail | Chênh lệch có ý nghĩa thống kê nhưng chưa đủ điều kiện triển khai |
| Qua mọi gate hồi cứu trên dữ liệu đã đọc | Vẫn không phải confirmation; cần randomized data mới |
| Hybrid causal coefficient shrink gần 0 | Dữ liệu không chứng minh causal score bổ sung baseline risk; không phải bằng chứng tau(x) tuyệt đối đồng nhất |

Qini, AUUC, AUTOC/RATE, calibration và CATE error trả lời câu hỏi khác. Chúng là sensitivity diagnostics,
không được dùng để đảo hard-budget decision sau khi xem kết quả.

## 8. Artifact contract

Một audit hoàn chỉnh ghi:

- `simultaneous_tail_differences.csv` — mọi cell, point/simultaneous CI, SE, critical value;
- `tail_event_support.csv` — row/event/tie theo arm;
- `tail_membership_overlap.csv` — stability giữa registered fold seeds;
- `analysis_summary.json` — decision, scope, protocol/input hashes và code state.

Namespace output là bằng chứng bất biến. Runner từ chối ghi đè; sensitivity run phải dùng protocol và
namespace mới.

## 9. Tái lập

Bản rà soát chính thức, dùng đúng 200 lần bootstrap đã đăng ký:

```powershell
.venv\Scripts\python.exe scripts\analyze_top_tail_evidence.py
```

Nếu namespace chính thức đã tồn tại, lệnh phải fail. Để kiểm tra code path mà không thay evidence chính,
dùng một output directory mới nhưng không được diễn giải nó như protocol result.

Test liên quan:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests\test_policy_evaluation.py `
  tests\test_synthetic_rct.py `
  tests\test_top_tail_research_artifacts.py `
  tests\test_protocol_guards.py `
  tests\test_improvement_selection.py `
  -q -p no:cacheprovider `
  --basetemp output\pytest_tmp_top_tail
```
