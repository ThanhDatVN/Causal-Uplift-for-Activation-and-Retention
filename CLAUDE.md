# Bối cảnh nhanh cho agent/người mới đọc repo

## Mục tiêu

Project dùng Criteo randomized campaign để xếp hạng khách hàng theo incremental
conversion do quảng cáo. Estimand là CATE của `conversion`; không dùng `visit` và
`exposure` vì đây là post-treatment variables.

## Trạng thái chính thức — 29/07/2026

Sprint 1 đã chạy lại từ đầu:

- audit 13.979.592 dòng;
- sample 50%; bên trong sample dùng fit/validation/test 56/14/30, tương đương khoảng
  28/7/15% full data, stratify treatment–outcome;
- candidate selection bằng validation seeds 43/44/45;
- release năm model trên 50% dữ liệu, chung test 2.096.940 dòng;
- 500 bootstrap cho CI, paired bootstrap cho model differences;
- policy deciles và benchmark Causal Forest.

Release configs: `configs/sprint1_release_5models.json`.

Release Qini:

| Model | Qini |
|---|---:|
| Response baseline | 0.187886 |
| S baseline | 0.177204 |
| X under7, classifier + fixed propensity + xấp xỉ `1/k` | 0.167168 |
| DR baseline | 0.153967 |
| T baseline | 0.142021 |

Chỉ cải tiến X vượt baseline trong final ablation. Response đứng đầu ranking nhưng
không phải CATE estimator đầy đủ. Response chỉ được so sánh theo các metric được báo cáo;
không suy rộng kết quả sang tiêu chí chưa đánh giá.

## Tài liệu và artifact có hiệu lực

Điểm vào: `docs/PROJECT_GUIDE.md` (hướng dẫn toàn diện), `docs/README.md` và
`planning/README.md` (chỉ mục có trạng thái từng tài liệu).

- `report/SPRINT_1_FINAL_REPORT.md`
- `report/SPRINT_2_FINAL_REPORT.md`
- `report/SPRINT_3_FINAL_REPORT.md`
- `docs/PROJECT_GUIDE.md`
- `docs/SPRINT_1_THEORY_AND_METHOD_GUIDE.md`
- `docs/SPRINT_2_METHOD_AND_PRODUCT_GUIDE.md`
- `docs/SPRINT_3_METHOD_GUIDE.md`
- `docs/WEBAPP.md`
- `docs/KAGGLE_RUNBOOK_COMPLETE.md`
- `planning/RESEARCH_LANDSCAPE_2026.md`
- `output/sprint1/`, `output/sprint2/`, `output/sprint3/`, `output/improvement/`
- `output/optimization/*sprint1_release*`

Tài liệu lịch sử, không dùng làm nguồn số: `docs/archive/TUTORIAL.md`,
`docs/archive/KAGGLE_CAUSAL_FOREST.md`, `docs/archive/COLAB_CAUSAL_FOREST.md`, `planning/RUN_PLAN.md`,
`planning/CAUSAL_UPLIFT_PLAN.md`, `report/archive/week-01/`, `notebooks/`.

Các kết quả trong `report/archive/week-01/`, notebook, HTML explainer và dashboard có thể là
historical. Không lặp lại claim “top 10% giữ 85% uplift”; release estimate là 72,7%.

## Causal Forest

Không chạy thẳng 50%. Benchmark 20% research profile đạt peak 8,16 GB; dự phóng 50%
17,5 GB, budget bảo thủ 24 GB. Trên Kaggle đọc RAM/CPU live, chạy `kaggle-safe` 20%,
sau đó 30%, chỉ chạy 50% nếu peak RAM dưới 75%.

Notebook soạn sẵn: `notebooks/kaggle_causal_forest.ipynb`. Hướng dẫn từng bước và bảng
"chạy ở đâu": `docs/NOTEBOOK_GUIDE.md`. Runbook lý do thiết kế:
`docs/KAGGLE_RUNBOOK_COMPLETE.md`. Ba điểm dễ sai:

- `econml==0.16.0` yêu cầu `scikit-learn<1.7`; image Kaggle thường mới hơn. Phải ghim
  rồi **restart kernel**.
- Gate (`kaggle_causal_forest_gate.py`) chỉ kiểm tra tài nguyên và toàn vẹn artifact;
  `"quality_not_assessed": true` nằm ngay trong manifest. Chấm điểm bằng
  `scripts/evaluate_causal_forest.py`.
- **Chỉ stage 50% mới so được với bảng release.** Ở `frac=0.50, test_size=0.30,
  seed=42`, holdout trùng khít final test Sprint 1 (đã kiểm chứng: 2.096.940 dòng, `Y`
  và `T` giống hệt từng phần tử). Stage 20% và 30% dùng tập test khác nên Qini không so
  trực tiếp với số release được.

## Sprint 3 canonical release (05/08/2026)

- Official report: `report/SPRINT_3_FINAL_REPORT.md`.
- Official artifacts: `output/sprint3/`, `output/improvement/`.
- Protocol đăng ký trước: `configs/sprint3_improvement_protocol.json`.
- Metric chính đổi từ Qini sang `policy_area_dr`: trung bình trapezoid của DR gross
  policy value trên dải budget 1–30%. Qini/AUUC vẫn được báo cáo để so lịch sử.
- Development pool = Sprint 2 `fit + validation` (5.591.836 dòng), 3-fold
  cross-fitting, fold seed 101 và 202.
- 12 candidate screening ở 20%; 6 finalist full development; 9 model/ensemble trên
  retrospective confirmation.
- **Không challenger nào đạt promotion rule. Champion giữ nguyên Response.**
  `oof_seeds_won = 0/2` với tất cả; mọi chênh lệch confirmation đều âm.
- Response confirmation: `policy_area_dr = 0,000912`, AUTOC `0,003823`,
  Qini `0,192989`.
- **Metric bất đồng cần nhớ:** trên confirmation, Qini xếp Ensemble-QAgg
  (`0,209845`), S-Under7 (`0,205904`) và X-Renormalized (`0,201812`) cao hơn
  Response (`0,192989`), trong khi `policy_area_dr` và AUTOC xếp Response cao nhất.
  Không trích Qini Sprint 3 rời khỏi ngữ cảnh này.
- Rank-Learner (ICLR 2026) mạnh nhất trong nhóm CATE ở screening 20% nhưng tụt hạng
  ở full data và chậm gấp 19–59 lần; ba biến thể đều có CI dưới 0 trên confirmation.
- Causal Q-aggregation hội tụ về `X-Renormalized 0,5 / S-Under7 0,5`; DR loss giữa
  hai model chỉ chênh khoảng `7e-6` tương đối, tức DR risk gần như không phân biệt
  được model trên outcome hiếm này.
- Resource: full OOF peak RSS 3,20 GB; RAM khả dụng hệ thống tụt xuống 1,55 GB, dưới
  gate 2,0 GB đã đăng ký. Gate hiện chỉ kiểm tra trước khi chạy.
- Web app: `webapp/`, runbook `docs/WEBAPP.md`, scorer `output/webapp/`.
- pytest 139/139 pass.

### Vì sao Response thắng — đã có lời giải thích trong tài liệu

Rà soát 05/08/2026 (`planning/RESEARCH_LANDSCAPE_2026.md`) cho thấy kết quả này là
chế độ đã được mô tả trước, không phải dị thường:

- Fernández-Loría & Provost, JMLR 2022: *causal bias–variance tradeoff* — outcome
  prediction có bias nhưng variance nhỏ hơn nhiều; khi variance của CATE đủ lớn nó
  ra ít quyết định sai hơn.
- Fernández-Loría & Loría, arXiv 2206.12532: proxy xếp hạng đúng khi phản ánh
  dominant moderator; nêu riêng bối cảnh discrete choice nơi xu hướng hành động khi
  không can thiệp điều tiết mức bị thuyết phục.
- Diemert et al., AdKDD 2018 (nhóm tạo dataset): khuyến nghị dùng `visit` thay
  `conversion` vì tín hiệu uplift của `conversion` quá yếu.
- VALOR 2026 đặt tên *prognostic dominance* và *counterfactual gradient collapse*.

Khi trình bày kết quả, dẫn kèm các nguồn này; không viết "thử nhiều thứ và không cái
nào chạy".

**Phân biệt bắt buộc:** dùng `visit` làm **outcome** là một estimand khác và hợp lệ;
dùng `visit` làm **feature** vẫn là leakage và vẫn bị cấm.

## Sprint 2 canonical release (31/07/2026)

- Official report: `report/SPRINT_2_FINAL_REPORT.md`.
- Official artifacts: `output/sprint2/`.
- Dashboard: `output/dashboard.html`, schema `sprint2-dashboard-v1`.
- Complementary pool split 60/20/20; confirmation 1.397.959 rows. Tập này đã được dùng
  cho báo cáo Sprint 2 nên các vòng model mới phải gọi là retrospective confirmation.
- Champion is Response top-k selected on validation.
- X-Renormalized minus Response confirmation Qini = 0.008768,
  paired 500-bootstrap CI [-0.018626, 0.038772].
- At budget 10%, value=1, cost=0.0005, Response DR net/customer = 0.000799,
  CI [0.000608, 0.000977].
- All value/cost outputs are assumption scenarios, not actual profit.
- Causal Forest Kaggle 20/30/50 remains pending. Local 0.1% is code-path smoke only.
- Resource-gated profile has `inference=False`; do not require or claim `effect_interval()`.

## Quy tắc khi sửa/chạy

- Không tune thêm trên test Sprint 1.
- Giữ split/feature contract để so sánh công bằng.
- Từ Sprint 3, metric chính là `policy_area_dr`; Qini/AUUC/AUTOC/calibration là bằng
  chứng phụ. Không dùng classification accuracy làm metric chính. Không đổi kết luận
  bằng cách chọn metric sau khi xem kết quả.
- Mọi claim model A hơn B phải dùng paired CI.
- Confirmation Sprint 2 đã bị quan sát ở Sprint 2 và Sprint 3; mọi vòng mới trên tập
  đó phải gọi là retrospective confirmation.
- Mọi run mới phải ghi vào `output/improvement/registry.csv`, kể cả run thất bại.
- Under-sampling formula/xấp xỉ phải dẫn Nyberg et al.; không coi scale `k` là đẳng thức.
- Score âm là dự đoán model-dependent, không phải principal stratum quan sát được.
- Dashboard tĩnh Sprint 2 chỉ đọc `output/sprint2/` qua `output/dashboard_data.json`.
  Web app đọc `output/sprint1|2|3/` và `output/improvement/` qua `webapp/service.py`.
- Vòng cải tiến model mới phải theo `planning/SPRINT_3_EXECUTION_AND_WEB_PLAN.md`;
  `planning/SPRINT_1_2_MODEL_IMPROVEMENT_PLAN.md` là bản gốc đã thực hiện xong.
- Trước khi hiện thực phương pháp mới, đối chiếu `planning/RESEARCH_LANDSCAPE_2026.md`.
  Nguồn ở mức xác minh `C` (chỉ có metadata) không được hiện thực; phải nâng lên `A`
  (đọc được công thức) trước.

## Văn phong tài liệu

- Dùng metric, split, interval, runtime hoặc trạng thái artifact thay cho tính từ tự đánh giá.
- Không dùng emoji, câu hỏi tu từ, chữ in hoa để nhấn mạnh hoặc giọng quảng bá.
- Viết “đạt/không đạt gate”, “CI chứa/không chứa 0”, “đã/chưa có artifact”.
- Phân biệt rõ biến quan sát, estimate, input kịch bản và kết quả semi-synthetic.
- Tên phương pháp như `honest splitting` và `doubly robust` được giữ vì là thuật ngữ kỹ thuật.

## Câu lệnh kiểm tra nhanh

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe scripts\audit_criteo.py --balance-frac 0.05 --seed 42
.venv\Scripts\python.exe scripts\evaluate_selected_five_models.py `
  --selected configs\sprint1_release_5models.json --frac 0.50 --n-boot 500
```

Web app và vòng cải tiến:

```powershell
.venv\Scripts\python.exe scripts\serve_webapp.py --port 8000
node scripts\smoke_webapp_browser.mjs
.venv\Scripts\python.exe scripts\run_oof_experiment.py --pool-frac 0.01 --stage smoke --n-boot 50 `
  --output-dir output\improvement\smoke
```
