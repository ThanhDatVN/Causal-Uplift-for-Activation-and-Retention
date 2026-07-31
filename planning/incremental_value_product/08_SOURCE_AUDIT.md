# 08 — Kiểm tra Nguồn và Sổ đăng ký Trích dẫn (Source Audit and Citation Registry)

**Trạng thái:** metadata/abstract hoặc documentation chính chủ đã được kiểm tra ngày **2026-07-29**.
`Verified` không có nghĩa toàn bộ paper đã được đọc; trước khi viết claim học thuật chi tiết, phải đọc
phần phương pháp/kết quả liên quan và lưu note theo template ở `06_READING_LIST.md`.

## Quy ước dùng nguồn

- **Primary paper:** dùng cho claim lý thuyết/phương pháp.
- **Official dataset page:** dùng cho schema, provenance, license và scope dữ liệu.
- **Official implementation docs:** dùng cho API/assumption của package; không thay thế paper.
- Không dùng blog, benchmark thứ ba hoặc Wikipedia làm citation chính cho claim trong report/CV.

## Sổ đăng ký nguồn (Registry)

| Key | Nguồn đã kiểm tra | Loại | Được phép dùng để chứng minh | Không được suy ra |
|---|---|---|---|---|
| `Fader2005` | [Fader, Hardie & Lee (2005), Marketing Science, DOI](https://doi.org/10.1287/mksc.1040.0098) | Primary paper | BG/NBD là alternative cho Pareto/NBD trong customer-base analysis | Causal effect của campaign hoặc observed margin |
| `Schmittlein1987` | [Schmittlein, Morrison & Colombo (1987), Management Science, DOI](https://doi.org/10.1287/mnsc.33.1.1) | Primary paper | Pareto/NBD, probability customer còn active | CLV của từng khách là observed fact |
| `HardieBGNBD` | [BG/NBD derivation note](https://brucehardie.com/notes/039/bgnbd_derivation__2019-11-06.pdf) | Author technical note | likelihood, probability alive, expected transactions | empirical validity trên Online Retail II nếu chưa temporal validate |
| `HardieGammaGamma` | [Gamma-Gamma note](https://www.brucehardie.com/notes/025/gamma_gamma.pdf) | Author technical note | monetary-value model và independence assumption | correlation threshold là bảo chứng tuyệt đối |
| `Diemert2018` | [Criteo AI Lab dataset + citation](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) | Official dataset/paper landing page | benchmark gốc: randomized incrementality tests, visit/conversion labels, citation paper | schema/row count của file local v2.1 nếu chưa manifest |
| `WagerAthey2018` | [Wager & Athey (2018), JASA, DOI](https://doi.org/10.1080/01621459.2017.1319839) | Primary paper | causal forest, heterogeneity estimation và asymptotic inference under assumptions | individual counterfactual ground truth hoặc policy value tự động tối ưu |
| `Kunzel2019` | [Künzel et al. (2019), PNAS, DOI](https://doi.org/10.1073/pnas.1804597116) | Primary paper | S/T/X meta-learners cho CATE | one learner luôn phù hợp mọi imbalance/outcome |
| `AtheyWager2021` | [Athey & Wager (2021), Econometrica, DOI](https://doi.org/10.3982/ECTA15732) | Primary paper | constrained policy learning, utilitarian regret framing | offline policy value là production lift |
| `Dudik2011` | [Dudík et al., *Doubly Robust Policy Evaluation and Learning* (ICML 2011 / Microsoft Research)](https://www.microsoft.com/en-us/research/publication/doubly-robust-policy-evaluation-and-learning-2/) | Primary paper landing page | direct, IPW và DR policy evaluation under logged partial feedback | DR remains valid when overlap/data split fails |
| `CriteoDataset` | [Criteo Uplift Prediction Dataset](https://ailab.criteo.com/criteo-uplift-prediction-dataset/) | Official dataset page | original public dataset provenance and intended benchmark | values not documented for the downloaded revision |
| `OnlineRetailII` | [UCI Online Retail II, DOI](https://doi.org/10.24432/C5CG6D) | Official dataset page | 1,067,371 transactions, 2009–2011, UK retailer, wholesale caveat, cancellations, CC BY 4.0 | randomized treatment, costs, gross margin or causal effect |
| `Hillstrom` | [TensorFlow Datasets: Hillstrom](https://tensorflow.google.cn/datasets/catalog/hillstrom) | Official dataset mirror/docs | 64,000 customers, 3 randomized email/control arms, two-week tracked outcomes, `spend` field | long-term CLV or persistent retention effect |
| `PyMCMarketingCLV` | [PyMC-Marketing CLV Quickstart](https://www.pymc-marketing.io/en/stable/notebooks/clv/clv_quickstart.html) | Official implementation docs | RFM definitions, temporal train/test helper, Bayesian/MAP workflow, one-time-buyer limitation | benchmark performance on this project’s data |
| `EconMLDRPolicy` | [EconML DRPolicyForest docs](https://www.pywhy.org/EconML/_autosummary/econml.policy.DRPolicyForest.html) | Official implementation docs | DR counterfactual-outcome construction and policy objective in this package | a complete validation protocol or causal identification by itself |
| `Tran2024` | [Tran, Bibaut & Kallus (2024), PMLR](https://proceedings.mlr.press/v235/tran24b.html) | Primary paper | inference on long-term effects of long-term treatments from short-term experiments, under its stated assumptions | extrapolation beyond observed horizon without its assumptions |
| `GoogleMLTest2017` | [Breck et al. (2017), Google Research](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/) | Production-ML research | test/monitoring dimensions that reduce ML technical debt | this project is a production service merely because it has a dashboard |
| `GoogleRulesML` | [Google Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml/) | Official engineering guidance | baseline-first, data dependency and training-serving-skew guard rails | a substitute for domain validation or a deployment runbook |
| `StreamlitDocker` | [Streamlit Docker deployment guide](https://docs.streamlit.io/deploy/tutorials/docker) | Official implementation docs | container/health-check deployment pattern for the demo | availability/security SLO achieved without testing it |
| `FastAPI` | [FastAPI feature documentation](https://fastapi.tiangolo.com/features/) | Official implementation docs | OpenAPI/Pydantic-backed API contract direction | FastAPI itself makes a system production-ready |
| `MarketDA2026` | [Match Group Data Analyst posting](https://jobs.lever.co/matchgroup/3c12c050-2719-43e6-a69e-fdb971f399a7) | Job-posting snapshot, retrieved 2026-07-29 | current signal for SQL, metric, A/B-test, dashboard and stakeholder communication | universal hiring requirement or salary/market claim |
| `MarketDS2026` | [HighLevel Experimentation & Causal Inference posting](https://jobs.lever.co/gohighlevel/0129e5bc-74e4-4f7c-9983-891da20542e8) | Job-posting snapshot, retrieved 2026-07-29 | current signal for experiment design, causal rigor, SQL/Python and decision-grade readout | requirements for every DS level/company |
| `MarketAIE2026` | [OpenGov Applied AI Engineer posting](https://jobs.ashbyhq.com/opengov/1a653285-4ca7-4fa3-ac0a-1712c30d68a6/) | Job-posting snapshot, retrieved 2026-07-29 | current signal for Python API, Docker, CI/CD, reliability/observability and AI workflow integration | this causal project proves deep LLM/agent specialization |
| `KaggleGPU2026` | [Kaggle efficient GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage) | Official platform documentation, checked 2026-07-29 | free GPU quota is weekly and demand-dependent; GPU benefits GPU-enabled libraries, not generic pandas/scikit-learn workloads | a specific Kaggle GPU/RAM/session is guaranteed |
| `ColabFAQ2026` | [Google Colab FAQ](https://research.google.com/colaboratory/faq.html) | Official platform documentation, checked 2026-07-29 | free/paid resource, GPU type, high-memory availability and limits are dynamic; paid plans increase availability via compute units | Colab Pro guarantees a specific GPU, RAM profile or uninterrupted run |

## Cách dùng trích dẫn theo artifact (Citation Usage by Artifact)

| Artifact | Citation keys tối thiểu |
|---|---|
| CLV notebook/report | `Fader2005`, `Schmittlein1987`, `HardieBGNBD`, `HardieGammaGamma`, `OnlineRetailII` |
| Causal monetary notebook/report | `Diemert2018` hoặc `Hillstrom`, `Kunzel2019`, `WagerAthey2018` |
| Policy evaluation report | `AtheyWager2021`, `Dudik2011`, `EconMLDRPolicy` nếu dùng package |
| Bayesian CLV appendix | `PyMCMarketingCLV` + primary BTYD source |
| Long-horizon/projection appendix | `Tran2024` và một limitation statement rõ ràng |
| Engineering/deployment appendix | `GoogleMLTest2017`, `GoogleRulesML`, `StreamlitDocker`, `FastAPI` |
| Portfolio positioning note | `MarketDA2026`, `MarketDS2026`, `MarketAIE2026` với retrieval date, không coi là universal rule |

## Khoảng trống nghiên cứu được giữ có chủ ý (Research Gaps)

1. Không có public dataset trong scope này vừa có customer-level transactions dài hạn, randomized
   treatment và realized margin/cost đầy đủ. Vì vậy real-data evidence được tách thành CLV forecasting
   (Online Retail II) và short-horizon causal monetary effect (Hillstrom); integration recovery dùng
   semi-synthetic DGP.
2. `projected incremental CLV` là extrapolation có model assumptions; chỉ headline khi có observed-horizon
   result đi kèm và uncertainty/sensitivity đầy đủ.
3. Thư viện không phải bằng chứng thực nghiệm. Mọi số liệu của repo phải sinh từ run artifact đã versioned.
