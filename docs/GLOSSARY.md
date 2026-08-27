# Bảng thuật ngữ

- **Phạm vi:** 89 thuật ngữ, mọi thuật ngữ xuất hiện trong `report/`, `docs/` và `src/`
- **Cách sắp xếp:** theo **chủ đề**, 11 mục — thuật ngữ cùng nhóm cần đọc cùng nhau
- **Quy ước viết:** [README.md](README.md) mục "Quy tắc viết tài liệu"

Giữ nguyên tiếng Anh cho tên định danh trong code và thuật ngữ chưa có tương đương ổn định;
phần còn lại dịch.

---

## 1. Đại lượng nhân quả

| Thuật ngữ | Nghĩa |
|---|---|
| **Kết quả tiềm năng** (potential outcome) | `Y(1)` là kết quả nếu được treatment, `Y(0)` nếu không. Với mỗi người chỉ một trong hai quan sát được |
| **Phản thực** (counterfactual) | Vế không quan sát được của cặp trên |
| **Bài toán thiếu dữ liệu cơ bản** | `Y(1) - Y(0)` không bao giờ quan sát được ở mức cá nhân. Hạn chế logic, không phải hạn chế kỹ thuật |
| **ATE** | `E[Y(1) - Y(0)]` — hiệu ứng trung bình toàn quần thể. Criteo: `0,11519` điểm phần trăm |
| **CATE**, `τ(x)` | `E[Y(1) - Y(0) \| X = x]` — hiệu ứng trung bình trong nhóm có đặc trưng `x`. **Đại lượng đích của dự án** |
| `p₀(x)` | Xác suất outcome **khi không** treatment. Criteo: `τ(x) ≈ 0,53 · p₀(x)` |
| **Estimand** | Đại lượng ta muốn ước lượng, phát biểu trước khi chọn phương pháp. Của dự án: hiệu ứng tăng thêm lên `conversion` |
| **Uplift** | Tên gọi khác của CATE trong ngữ cảnh marketing |

## 2. Thiết kế thí nghiệm

| Thuật ngữ | Nghĩa |
|---|---|
| **RCT** / randomized incrementality test | Thí nghiệm gán treatment ngẫu nhiên. Criteo v2.1 là một RCT |
| **Treatment**, `T` | Can thiệp. Ở đây: có được quảng cáo hay không |
| **Arm** / nhánh | Nhóm treated (`T=1`) hoặc control (`T=0`) |
| **Exchangeability** | `T` độc lập với `(Y(0), Y(1))`. Điều kiện làm hiệu hai trung bình bằng ATE |
| **Propensity**, `e(x)` | `P(T = 1 \| X = x)`. Criteo: hằng số `0,85` **theo thiết kế**, không ước lượng |
| **Confounding** | Biến vừa ảnh hưởng ai được treatment vừa ảnh hưởng outcome. RCT loại bỏ nó |
| **Overlap** | Mọi nhóm đều có cả hai nhánh. Bắt buộc để tính được hiệu |
| **SMD** | Chênh lệch trung bình chuẩn hóa giữa hai nhánh. Criteo: trung vị `0,0177`, lớn nhất `0,0490` |
| **Biến hậu can thiệp** | Biến xảy ra **sau** treatment. `visit` và `exposure` — **cấm** làm feature |

## 3. Họ model

Phân biệt hai mức, vì bảng kết quả và tài liệu phương pháp nói ở hai mức khác nhau:

| Thuật ngữ | Nghĩa |
|---|---|
| **Họ model** (family) | Thuật toán và cơ chế của nó. Dự án có **12 họ**; mỗi họ được mô tả ở một guide trong [methods/](methods/) |
| **Candidate** | Một **cấu hình cụ thể đã đăng ký để chạy** = họ + tiền xử lý + siêu tham số. Tên trong mọi bảng kết quả là tên candidate, không phải tên họ. Dự án đã chạy **31 candidate**. Trường `family` trong `configs/*.json` ghi họ của từng cái |

Nhiều candidate có thể cùng một họ: `DR-Regression`, `DR-Binary`, `DR-Binary-MC2` đều là
DR-Learner với ba cấu hình nuisance khác nhau. Bảng ánh xạ đầy đủ candidate → họ → vòng:
[README.md](README.md) mục "Candidate và họ model".

Cơ chế từng họ:

| Thuật ngữ | Cơ chế |
|---|---|
| **Response** | Dự đoán `P(Y=1 \| X)`, bỏ qua `T`. **Champion hiện hành.** Không phải CATE estimator |
| **Meta-learner** | Nhóm phương pháp ghép các model thông thường để ước lượng CATE |
| **S-learner** | Một model trên `(X, T)`, lấy `f(x,1) - f(x,0)` |
| **T-learner** | Hai model riêng cho hai nhánh, lấy `μ₁(x) - μ₀(x)` |
| **X-learner** | Impute hiệu ứng bằng model nhánh đối diện, kết hợp theo propensity |
| **DR-learner** | Học trên pseudo-outcome doubly robust |
| **Causal Forest** | Sửa tiêu chí chia nhánh của cây để tối đa hóa chênh lệch hiệu ứng |
| **Honest splitting** | Dùng nửa dữ liệu chọn điểm chia, nửa còn lại ước lượng giá trị lá |
| **Nuisance**, `μ₁`/`μ₀` | Model phụ dự đoán `Y` cho từng nhánh. Cross-fit **một lần**, dùng chung mọi candidate |
| **Funnel S-learner** | Phân rã `P(conv) = P(visit) x P(conv \| visit)`. `visit` chỉ là auxiliary outcome, **không** vào feature |
| **Rank-Learner** | Học trực tiếp thứ hạng bằng pairwise Neyman-orthogonal loss, thay vì học `τ` rồi xếp |
| **DINA** | Học hiệu ứng trên thang log-odds — thang tham số tự nhiên của outcome nhị phân — rồi đổi về chênh lệch xác suất |
| **Anchored R-learner** | Giữ neo tiên lượng `p₀`, chỉ học phần dư đã co lại theo hệ số `0,25` |
| **Pattern R-learner** | Gộp một phần phần dư theo `53` pattern sentinel, thay vì để mỗi pattern học riêng |
| **Sentinel augmentation** | Thêm cờ nhị phân `x_j == mode_j`. Fit chỉ từ `X` của fold train, không đọc nhãn |
| **Hybrid stacker** | Prognostic–causal logistic stacking. **Đã hiện thực, chưa có run nào trong registry** |
| **Ensemble** | Tổ hợp nhiều model. Dự án có Q-aggregation, best-single, rank average |

## 4. Tín hiệu chấm điểm

Ba cách gán cho mỗi dòng một con số đại diện đóng góp hiệu ứng. **Đổi tín hiệu làm đổi thứ
hạng** — xem `report/08_CAUSAL_FOREST_RARE_OUTCOME.md` mục 5.

| Thuật ngữ | Công thức | Tính chất |
|---|---|---|
| **Hiệu hai trung bình** | `mean(Y \| T=1) - mean(Y \| T=0)` trong nhóm | Đơn giản, chỉ định nghĩa cho nhóm |
| **IPW** | `Y·T/p - Y·(1-T)/(1-p)` | Không chệch, **phương sai lớn** |
| **DR signal**, `Γ` | `μ₁-μ₀ + T(Y-μ₁)/p - (1-T)(Y-μ₀)/(1-p)` | Không chệch, phương sai thấp hơn. **Tín hiệu chính** |
| **Doubly robust** | Đúng nếu **một trong hai** — model outcome hoặc propensity — đúng | |
| **Transformed outcome** | Biến đổi `Y` thành một đại lượng có kỳ vọng bằng `τ` | |
| **Adjusted transformed outcome** | Bản trừ đi outcome gộp để giảm phương sai | |

## 5. Metric đánh giá

| Thuật ngữ | Đo gì | Vai trò |
|---|---|---|
| **`policy_area_dr`** | Diện tích trung bình của DR policy value trên dải budget `1–30%` | **Metric chính** từ Sprint 3 |
| **Qini** | Diện tích giữa đường uplift tích lũy và đường ngẫu nhiên, dải `0–100%` | Metric phụ. Từng là metric chính ở Sprint 1–2 |
| **AUUC** | Gần Qini, khác cách chuẩn hóa | Metric phụ |
| **TOC** | `mean(Γ \| top q) - mean(Γ)` — mức vượt trội của top `q` so với trung bình | Nền của RATE/AUTOC |
| **RATE / AUTOC** | Diện tích dưới đường TOC | Metric phụ chính |
| **EUCE** | Sai số hiệu chuẩn. Chỉ áp dụng cho model ở thang CATE | Chẩn đoán |
| **DR risk** | Sai số bình phương giữa `τ̂(x)` và `Γ` | Chọn trọng số ensemble |
| **Policy value** | Giá trị kỳ vọng khi target top `b` theo một điểm số | Nền của `policy_area_dr` |
| **Budget curve** | Đường ngân sách → giá trị | Hiển thị ở tab Policy |
| **Break-even** | Chi phí liên hệ làm giá trị ròng bằng 0 | Đầu ra sản phẩm |

## 6. Suy luận thống kê

| Thuật ngữ | Nghĩa |
|---|---|
| **Sai số chuẩn** (SE) | Độ lệch chuẩn của phân phối mẫu. Với tỷ lệ: `căn(p(1-p)/n)` |
| **Khoảng tin cậy** (CI) | Khoảng dựng sao cho 95% số lần lặp lại chứa giá trị thật |
| **Bootstrap** | Lấy mẫu lại **có hoàn lại** từ chính dữ liệu để ước lượng phân phối mẫu |
| **Percentile bootstrap** | CI bằng cách cắt 2,5% mỗi đầu của các giá trị bootstrap |
| **Paired bootstrap** | Mọi model dùng **chung một bộ trọng số dòng** trong mỗi lần rút, rồi tính hiệu. **Bắt buộc** cho mọi so sánh |
| **Simultaneous band** | CI đảm bảo mức tin cậy cho **toàn bộ họ** so sánh cùng lúc. Top-tail v2 dùng giá trị tới hạn `3,111821` |
| **Familywise** | Thuộc về cả họ so sánh, không phải từng so sánh riêng |
| **Power** | Khả năng phát hiện một hiệu ứng có thật. Cỡ mẫu cần tỷ lệ `1/δ²` |
| **`conditional_on_fixed_oof_scores`** | Nhãn ghi rằng CI **không** bao gồm bất định do huấn luyện lại model |

## 7. Kỷ luật thí nghiệm

| Thuật ngữ | Nghĩa |
|---|---|
| **Pre-registration** | Ghi metric, gate và luật quyết định vào `configs/` **trước** khi chạy. SHA được lưu trong manifest |
| **Protocol** | File JSON khai báo toàn bộ lựa chọn của một vòng |
| **Gate** | Điều kiện tự động chặn hoặc dừng. Ba loại: early stop, resource gate, selection guard |
| **Early stop** | Dừng candidate khi score không hữu hạn, hằng số, hoặc bị dominate |
| **Promotion rule** | Bốn điều kiện phải thỏa **đồng thời** để đổi champion |
| **Champion / challenger** | Model đang dùng / model đang thách thức |
| **Registry** | `output/improvement/registry.csv` — ghi **mọi** run, kể cả run hỏng. Hiện `97` dòng |
| **`run_id`** | Định danh một lần chạy, có trong mọi artifact của nó |
| **Cross-fitting** | Chia `k` fold; mỗi dòng được chấm bởi model **không** fit trên dòng đó |
| **OOF** | Out-of-fold — điểm thu được từ cross-fitting |
| **Fold seed** | Hạt giống quyết định cách chia fold. Dự án đòi thắng ở **cả hai** seed `101` và `202` |
| **Resource gate** | Ngưỡng RAM, kiểm **liên tục** trong lúc chạy |

## 8. Vai trò dữ liệu

| Thuật ngữ | Số dòng | Vai trò |
|---|---:|---|
| **Development pool** | `5.591.836` | Cross-fitting OOF, chọn shortlist |
| **Confirmation** | `1.397.959` | Áp promotion rule **đúng một lần** |
| **Final test Sprint 1** | `2.096.940` | Bằng chứng lịch sử, không tái sử dụng |
| **Retrospective confirmation** | | Tên gọi bắt buộc cho kết quả trên tập confirmation đã bị đọc ở Sprint 2. **Không** phải holdout mới |
| **Stratified complement** | | Lấy đúng phần bù của một sample để đảm bảo không chồng lấn |

## 8bis. Chẩn đoán

Không phải model, cũng không phải metric. Chúng trả lời *"phép đo có đáng tin không"*.

| Thuật ngữ | Nó kiểm điều gì |
|---|---|
| **SMD** | Chênh lệch trung bình giữa hai nhánh, chuẩn hoá theo độ lệch chuẩn. `< 0,1` là cân bằng tốt |
| **Propensity AUC** | Model đoán được nhánh từ `X` tới đâu. Gần `0,5` là phù hợp với randomization |
| **Proxy-ordering diagnostic** | Khi nào xếp theo một proxy cho **đúng** thứ tự xếp theo `τ`. Bị chi phối bởi **giá trị lớn nhất** của chặn CATE, không phải trung bình |
| **Power / MDE** | Cỡ mẫu tối thiểu để phát hiện một hiệu ứng cho trước |
| **Score degeneracy check** | Số giá trị phân biệt của điểm. Ngưỡng đã đăng ký: `>= 10` |
| **Membership overlap** | Tỷ lệ người trùng nhau trong top-k giữa hai fold seed. Đo bất ổn khi huấn luyện |
| **Event support** | Số sự kiện thật trong nhóm được chọn. Ít sự kiện thì CI rộng bất kể model nào |

## 9. Đặc thù dữ liệu Criteo

| Thuật ngữ | Nghĩa |
|---|---|
| **Point mass** | Rất nhiều dòng có cùng một giá trị. Criteo: 6/12 feature có >90% khối lượng ở một giá trị |
| **Sentinel** | Giá trị dùng để đánh dấu "không có dữ liệu" thay vì để trống. `53` pattern trên `4.096` khả năng |
| **Prognostic dominance** | Tín hiệu tiên lượng lấn át tín hiệu nhân quả. **Nguyên nhân gốc** của kết quả dự án |
| **Outcome hiếm** | Tỷ lệ sự kiện rất thấp. Criteo `conversion`: `0,2917%` |
| **Undersampling** | Giữ toàn bộ dòng dương, bỏ bớt dòng âm. Ký hiệu `under7` nghĩa là `k = 7` |
| **Calibration** | Hiệu chỉnh để điểm số về đúng thang xác suất. τ-isotonic là một cách |

## 10. Bốn nhóm khách hàng lý thuyết

| Nhóm | `Y(0)` | `Y(1)` | Nên tiếp cận |
|---|:-:|:-:|---|
| Chắc chắn mua (*sure thing*) | 1 | 1 | Không — họ mua sẵn rồi |
| **Bị thuyết phục** (*persuadable*) | 0 | 1 | **Có** — nhóm duy nhất tạo giá trị |
| Không bao giờ mua (*lost cause*) | 0 | 0 | Không |
| Bị làm phiền (*sleeping dog*) | 1 | 0 | Tuyệt đối không |

**Không xác định được nhóm của một cá nhân cụ thể** — hệ quả của bài toán thiếu dữ liệu cơ
bản. Chỉ nói được về tỷ lệ ở mức nhóm.

---

## Đọc tiếp

| Cần gì | Mở |
|---|---|
| Mạch phát triển toàn dự án | [END_TO_END_WORKFLOW.md](END_TO_END_WORKFLOW.md) |
| Công thức metric chi tiết | [methods/03_EVALUATION_PROTOCOL.md](methods/03_EVALUATION_PROTOCOL.md) |
| Lý thuyết nền và năm họ meta-learner | [methods/01_UPLIFT_FOUNDATIONS.md](methods/01_UPLIFT_FOUNDATIONS.md) |
| Luật ra quyết định | [DECISION_CONTRACT.md](DECISION_CONTRACT.md) |
