# Handoff (D08) — đọc kết luận từ kết quả, không phải từ trí nhớ

Ngày: 21/09/2026. Tài liệu này là D08 theo [MASTER_PLAN §16](MASTER_PLAN.md): *"Một reviewer đọc được claim từ result mà không cần đoán notebook state."*

Nó viết cho người **chưa** theo dõi dự án. Nếu bạn chỉ đọc một tài liệu, đọc cái này; nếu bạn cần kiểm một con số, mỗi dòng dưới đây trỏ tới lệnh sinh ra nó.

## 1. Dự án này rốt cuộc biết gì

Ba nhóm kết luận, xếp theo độ vững.

### Vững — đo được, có lý thuyết, đã kiểm ngoài mẫu

| Kết luận | Số | Ở đâu |
|---|---|---|
| Skewness của trung bình DR có dạng đóng `γ = (1−2e)/√(n·h·rate·e(1−e))` | khớp số đo trong **8–22%**, và **bằng 0 đúng ở thiết kế cân bằng** | [RELATED_WORK.md §3](../RELATED_WORK.md), [test_design_asymmetry.py](../../tests/test_design_asymmetry.py) |
| Imbalance **một mình** không phải quy tắc cổng dùng được | cùng imbalance 0,30: trượt ở rate 0,5% và 1,0%, **đạt** ở 3,5% | [OVERLAP_BOUNDARY.md](../../reports/v4/overlap_boundary/OVERLAP_BOUNDARY.md) |
| Thiết kế lấy mẫu làm giàu rẻ hơn thật, ở **cùng độ chính xác** | **26%** chi phí ở bất đồng thấp, **59%** ở bất đồng cao | [SAMPLING_ECONOMICS.md](../../reports/v4/sampling_economics/SAMPLING_ECONOMICS.md) |
| Giao thức ba mẫu chặn được winner's curse | nhìn 4 candidate thay vì 1: false promotion **0,023 so 0,043** | [SELECTION_STRESS.md](../../reports/v4/selection_stress/SELECTION_STRESS.md) |
| **Ở ~6.500 sự kiện, cả bảy causal learner thắng baseline** và baseline **đứng bét** | M06 hơn M01 **+0,003334** | [EXTERNAL_REPLICATION.md](../../reports/v4/replication_lenta/EXTERNAL_REPLICATION.md) |
| **Bất ổn hyperparameter không phải vấn đề đếm sự kiện** | 21× event, **vẫn** không family nào ổn định | cùng file (dự đoán P2 **bị bác bỏ**) |

### Có điều kiện — đúng trong phạm vi đã đo, chưa chuyển được ra ngoài

| Kết luận | Điều kiện |
|---|---|
| Cổng coverage **ĐẠT** 9/9 scenario ở 2.000 world | Qua **biến thể chọn hậu nghiệm**; bản cùng power với sàn df mặc định vẫn FAIL. Mọi artifact mang dòng `SELECTED AFTER LOOKING` |
| Ngưỡng của chỉ số bất đối xứng | Đo trên lưới sinh ra nó là **0,584**; trên 28 thiết kế ngoài mẫu **không chuyển được**, nên cổng tự siết xuống **0,100** |
| Không chiến lược refresh nào thắng cả ba cơ chế drift | Thế giới mock, phần thưởng là churn tránh được, **không có sổ tiền** |

### Đã bị chính dữ liệu bác bỏ, rồi thay bằng một phát biểu mạnh hơn

**Kết luận ứng dụng gốc không lặp lại.** R02–R05 trên nhánh Mens của Hillstrom đều nói "baseline xếp hạng theo outcome thắng mọi causal learner". Chạy lại toàn bộ giao thức trên nhánh **Womens** — cùng khách hàng, cùng chiến dịch — thì **M03 thắng** (+0,001412) và M03 có learning curve đơn điệu. Bốn đợt đồng thuận vì chúng dùng **cùng một cohort**, không vì kết luận vững.

**Rồi R10 giải thích tại sao**, trên một miền độc lập với 21 lần số sự kiện:

| dataset | event | ai thắng |
|---|---:|---|
| Hillstrom Mens | 302 | M01 (baseline) |
| Hillstrom Womens | 251 | M03 |
| **Lenta** (SMS bán lẻ) | **6.498** | **cả bảy** causal learner; **M01 bét, giá trị âm** |

Phát biểu hiện hành: **ở ~300 sự kiện thứ hạng là nhiễu; ở ~6.500 sự kiện causal learner thắng dứt khoát.** Hai điểm đầu mâu thuẫn nhau ở cùng cỡ event — đó chính là nội dung chữ "nhiễu".

Chi tiết: [STAGE_LOG S35 và S38](STAGE_LOG.md).

## 2. Tái hiện

Môi trường được khoá và có bộ kiểm:

```bash
python -m telco_churn.environment --strict   # 180 gói, 3 lock file
python -m pytest -q                          # 626 test
python -m ruff check .
```

Các đợt chạy, theo thứ tự phụ thuộc. Thời gian là thực đo trên máy phát triển.

| Lệnh | Sinh ra | Thời gian |
|---|---|---|
| `python -m telco_churn.validity_suite --worlds 2000 --seed 20260925 --interval-method skewness_adjusted_t --effective-df-floor 1 --output-dir reports/v4/validity_unshrunk` | Cổng R00/R01 | ~25 phút |
| `python -m telco_churn.overlap_boundary --worlds 1000` | Lưới ranh giới, 36 cell | 11 phút |
| `python -m telco_churn.asymmetry_transfer --worlds 1000` | Kiểm `A` ngoài mẫu, 28 thiết kế | 24 phút |
| `python -m telco_churn.batch_validation --worlds 500` | V08 | 24 phút |
| `python -m telco_churn.screening` | R02 | ~1 phút |
| `python -m telco_churn.bounded_tuning` | R03 | 36 giây |
| `python -m telco_churn.component_factorial` | R04 | 6 giây |
| `python -m telco_churn.learning_curves` | R05 | 12 giây |
| `python -m telco_churn.selection_stress --worlds 300` | R06 | 3 phút |
| `python -m telco_churn.temporal_replay --worlds 40` | R07 | 6 giây |
| `python -m telco_churn.sampling_economics --worlds 1000` | R08 | 4 phút |
| `python -m telco_churn.external_replication --rows 60000` | R10 | **45 phút** |
| `python -m telco_churn.figures` | 4 hình | 5 giây |
| `python -m telco_churn.evidence` | Chỉ mục bằng chứng + release tier | 2 giây |

Dữ liệu thô **không** được phân phối lại. Hai tệp cần tải riêng, cả hai đều có digest ghim:

```bash
python -m telco_churn.hillstrom_data fetch     # 64.000 hàng
curl -L -o data/raw/lenta.csv.gz https://sklift.s3.eu-west-2.amazonaws.com/lenta_dataset.csv.gz
python -m telco_churn.lenta_data check         # xác minh sha256
```

## 3. Chi phí

Khoảng **6 CPU-giờ** trên ngân sách 150 mà kế hoạch dự trù. Đợt đắt nhất là V08 (24 phút) và `asymmetry_transfer` (24 phút). Không đợt nào cần GPU. Dung lượng dữ liệu thô: 145 MB (Lenta) + 4 MB (Hillstrom).

## 4. Chỉ mục artifact

`python -m telco_churn.evidence` in ra chỉ mục đầy đủ và **cờ artifact cũ hơn module sinh ra nó** — nếu bạn thấy một artifact bị gắn cờ, số của nó vẫn đúng với lần chạy đó nhưng code đã đổi từ sau.

Trạng thái hôm nay: **9/10 cổng PASS**, release tier `RESEARCH_REPLICATED`. Cổng duy nhất chưa chạy là prospective partner trial, cần một đối tác và một sổ chi phí thật — nằm ngoài phạm vi dự án theo ràng buộc đã khai báo (không chiến dịch trực tiếp, không liên hệ khách hàng).

## 5. Rủi ro còn mở

Xếp theo mức độ ảnh hưởng tới kết luận.

1. **Evaluator chưa được xác nhận độc lập.** Cổng đạt qua một biến thể chọn sau khi nhìn. Cần một lần chạy R01 trên seed chưa dùng với recipe khoá **trước**. Cho tới lúc đó mọi kết quả đo bằng nó đều thừa hưởng điều kiện này.
2. **Hai dataset là mức tối thiểu.** Kết luận ứng dụng lật giữa hai nhánh của *một* thí nghiệm ở ~300 event, và chỉ ổn định ở ~6.500 event trên *một* miền thứ hai. Ngưỡng sự kiện nằm giữa 300 và 6.500 — **chưa được định vị**, và một điểm ở mỗi phía không vẽ được đường.
2b. **Bất ổn hyperparameter chưa có lời giải.** P2 bị bác bỏ: 21× dữ liệu không sửa được. Nguyên nhân nằm ở tiêu chí chọn bên trong, và chưa ai chẩn đoán nó.
3. **Chỉ số `A` chỉ đúng với `e` hằng số.** Thiết kế có propensity phụ thuộc X không được phủ, và cổng **tin lời khai của caller** — nó không tự phát hiện được sự khác biệt. Nhánh control của [S25](STAGE_LOG.md) cho thấy khai `e` trung bình sẽ đánh giá thấp rủi ro ở vùng sát ngưỡng.
4. **Mọi chi phí là giá khai báo.** Không dataset nào trong kho có sổ chi phí. Mọi con số kinh tế là **tỷ lệ ở cùng độ chính xác**, không phải lợi nhuận.
5. **Split confirmation chưa mở, có chủ đích.** [R09_CONFIRMATION_DECISION.md](../R09_CONFIRMATION_DECISION.md) ghi bốn lý do và bốn điều kiện để mở.
6. **`temporal_replay` là thế giới mock.** Nó trả lời "chiến lược refresh nào bền dưới cơ chế nào", không trả lời "drift thật xảy ra bao lâu một lần".

## 6. Nếu bạn tiếp nhận dự án này

Thứ tự tôi đề nghị, và lý do:

1. **Xác nhận evaluator độc lập.** Rẻ (~25 phút), và nó gỡ điều kiện khỏi mọi kết quả khác.
2. **Đọc [RESEARCH_READINESS.md](RESEARCH_READINESS.md) §2** trước khi viết bất cứ thứ gì. Ứng viên A (phương pháp) gần đích hơn ứng viên B nhiều, và ứng viên B vừa yếu đi đáng kể.
3. **Định vị ngưỡng sự kiện.** Hiện có một điểm ở 300 (nhiễu) và một ở 6.500 (rõ). Quét Lenta ở 500/1.000/2.000/4.000 event là rẻ và sẽ cho đường cong thay vì hai điểm.
3b. **Chẩn đoán bất ổn hyperparameter**, vì thêm dữ liệu đã được chứng minh là không sửa.
4. **Đừng mở split confirmation** cho tới khi bốn điều kiện ở R09 được thoả.

Điều đáng giữ nhất của kho này không phải một kết quả nào cả, mà là việc **nó bắt được chính nó sai năm lần trong một ngày** — khoảng có bề rộng 0, một SE dùng nhầm loại, một lần chấm sai target, một kết luận bốn-đợt-đồng-thuận không lặp lại, và một scenario mà chiến lược đọc được sự thật nên không đo được gì. Cơ chế làm được điều đó — negative control có khai báo, dự đoán đăng ký trước, cổng tự tố cáo khi nó chọn sau khi nhìn — là thứ nên giữ khi mọi số cụ thể đã cũ.
