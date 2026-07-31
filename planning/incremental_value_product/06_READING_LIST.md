# 06 — Danh mục Đọc và Học (Reading List)

Không đọc để “sưu tầm paper”. Mỗi nguồn chỉ tạo một note một trang:

- estimand;
- assumptions;
- estimator;
- validation;
- failure modes;
- phần nào dùng trong code.

Trước khi trích vào report, đối chiếu citation key và phạm vi claim trong
[`08_SOURCE_AUDIT.md`](08_SOURCE_AUDIT.md). Danh sách dưới đây ưu tiên paper/dataset chính chủ;
documentation package chỉ dùng cho implementation.

## P0 — Bắt buộc

### CLV xác suất (Probabilistic CLV)

1. Fader, Hardie & Lee (2005), *Marketing Science*:
   [“Counting Your Customers” the Easy Way](https://pubsonline.informs.org/doi/10.1287/mksc.1040.0098)
   - Key `Fader2005`. Đọc behavioral story, likelihood assumptions, BG/NBD vs Pareto/NBD.
2. Schmittlein, Morrison & Colombo (1987), *Management Science*:
   [“Counting Your Customers: Who-Are They and What Will They Do Next?”](https://doi.org/10.1287/mnsc.33.1.1)
   - Key `Schmittlein1987`. Đọc dropout/active-customer story của Pareto/NBD.
3. Bruce Hardie:
   [BG/NBD derivation](https://brucehardie.com/notes/039/bgnbd_derivation__2019-11-06.pdf)
   - Key `HardieBGNBD`. Đọc probability alive và expected transactions.
4. Bruce Hardie:
   [Gamma-Gamma note](https://www.brucehardie.com/notes/025/gamma_gamma.pdf)
   - Key `HardieGammaGamma`. Đọc frequency–monetary independence và expected transaction value.
5. PyMC-Marketing:
   [CLV Quickstart](https://www.pymc-marketing.io/en/stable/notebooks/clv/clv_quickstart.html)
   - Key `PyMCMarketingCLV`. Đọc `rfm_train_test_split`, MAP vs MCMC, calibration và one-time-buyer limitation.

### Nhân quả/chính sách tác động (Causal/Policy)

6. Künzel et al. (2019), *PNAS*:
   [Meta-learners for Estimating Heterogeneous Treatment Effects](https://doi.org/10.1073/pnas.1804597116)
   - Key `Kunzel2019`. Đọc S/T/X learner construction, imbalance caveat và experiment protocol.
7. Wager & Athey (2018), *JASA*:
   [Estimation and Inference of Heterogeneous Treatment Effects using Random Forests](https://doi.org/10.1080/01621459.2017.1319839)
   - Key `WagerAthey2018`. Đọc honest forest, consistency và interval interpretation.
8. Athey & Wager (2021), *Econometrica*:
   [Policy Learning with Observational Data](https://doi.org/10.3982/ECTA15732)
   - Key `AtheyWager2021`. Đọc policy value, welfare/regret và business constraints.
9. Dudík et al. (2011), *ICML*:
   [Doubly Robust Policy Evaluation and Learning](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/)
   - Key `Dudik2011`. Đọc direct method, IPW, DR estimator và failure modes.
10. EconML:
   [DRPolicyForest](https://www.pywhy.org/EconML/_autosummary/econml.policy.DRPolicyForest.html)
   - Key `EconMLDRPolicy`. Chỉ đọc API/objective sau khi đã đọc paper DR.

### Bộ dữ liệu (Dataset)

11. [Criteo dataset description + Diemert et al. citation](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)
    - Key `Diemert2018`/`CriteoDataset`. Đọc data version, unit, labels, randomization design.
12. [UCI Online Retail II](https://doi.org/10.24432/C5CG6D)
    - Key `OnlineRetailII`. Đọc timeframe, cancellation code, missingness, wholesale caveat, license.
13. [Hillstrom dataset description](https://tensorflow.google.cn/datasets/catalog/hillstrom)
    - Key `Hillstrom`. Đọc ba arm randomization và hai-week outcome window.

## P1 — Theo nhu cầu triển khai

1. [PyMC-Marketing Pareto/NBD](https://www.pymc-marketing.io/en/stable/notebooks/clv/pareto_nbd.html)
   - Chỉ mở nếu BG/NBD sensitivity cho one-time buyer/wholesale cho thấy cần challenger.
2. Chernozhukov et al. (2018), *The Econometrics Journal*:
   [Double/debiased machine learning for treatment and structural parameters](https://doi.org/10.1111/ectj.12097).
   - Dùng khi cần giải thích cross-fitting/Neyman orthogonality, không chỉ vì dùng tên “DR”.
3. Nyberg, Kuśmierczyk & Klami (2021), *PMLR*:
   [Uplift Modeling with High Class Imbalance](https://proceedings.mlr.press/v157/nyberg21a.html).
   - Dùng khi thử undersampling trên Criteo; bắt buộc đánh giá lại calibration sau undersampling.
4. Breck et al. (2017), Google Research:
   [The ML Test Score](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/).
   - Dùng để chọn release gates cho test, monitoring, data/model dependencies; không cần cố đạt đủ 28 test.
5. Google for Developers:
   [Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml/).
   - Dùng để giữ baseline/feature pipeline đơn giản, chống training-serving skew và technical debt.
6. [Streamlit Docker deployment](https://docs.streamlit.io/deploy/tutorials/docker) và
   [FastAPI features](https://fastapi.tiangolo.com/features/).
   - Implementation references cho dashboard/API; không phải paper phương pháp.

## P2 — Chỉ đọc nếu mở rộng scope

1. Tran, Bibaut & Kallus (2024):
   [Inferring the Long-Term Causal Effects of Long-Term Treatments from Short-Term Experiments](https://proceedings.mlr.press/v235/tran24b.html)
   - Key `Tran2024`. Chỉ cần khi claim repeated/long-term treatment ngoài observed horizon.
2. MT-LIFT/X5, causal survival hoặc off-policy RL. Không đưa vào 5-week critical path nếu chưa có
   public data thỏa monetary + long-horizon + randomized-treatment requirement.

## Lịch đọc

| Tuần | Nguồn |
|---|---|
| Week 1 | Fader 2005, Schmittlein 1987, BG/NBD note, Gamma-Gamma note, UCI; tạo data card |
| Week 2 | PyMC CLV quickstart, Pareto/NBD docs nếu chạy challenger; đọc temporal-validation failure modes |
| Week 3 | Künzel, Wager–Athey, Athey–Wager, Dudík, Hillstrom; freeze policy protocol |
| Week 4 | EconML policy docs theo implementation; đối chiếu API với estimator trong protocol |
| Week 5 | Chỉ tra cứu để sửa report/limitations; không mở research branch mới |

## Quy tắc trích dẫn (Citation Rules)

- Chỉ trích claim đã đọc đúng đoạn.
- Nếu chỉ đọc abstract/docs, ghi rõ.
- Không gắn paper vào thuật toán tự suy diễn.
- Implementation dựa vào library source phải ghi là implementation reference.
- Không đưa số benchmark bên ngoài vào README nếu không tái lập/đối chiếu được.
- Metadata/abstract đã xác minh không thay thế việc đọc paper: không viết theorem/assumption chi tiết
  nếu chưa có note dẫn đúng section/page.
