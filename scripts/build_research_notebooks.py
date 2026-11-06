"""Build the two research notebooks from compact, reviewable cell sources."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"


def notebook(cells: list, title: str) -> nbf.NotebookNode:
    return nbf.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
            "title": title,
        },
    )


orange_cells = [
    nbf.v4.new_markdown_cell(
        """# 03 — Orange Belgium causal-retention audit

**Decision question:** trong high-risk pool đã được hệ thống Orange chọn, target assignment có làm giảm
churn hai tháng và ranking nào nên dùng khi capacity hữu hạn?

Notebook này tách bốn việc: kiểm data/experiment, ước lượng average effect và power, chọn policy bằng
development OOF, rồi đọc đúng một locked holdout. Positive uplift luôn có nghĩa `Y(0)-Y(1)` — churn
được ngăn. Kết quả là intention-to-treat, không phải effect của một offer cụ thể.

Nguồn: [OpenML 45580](https://www.openml.org/search?type=data&id=45580) và
[dataset paper](https://arxiv.org/abs/2312.07206). Raw data CC BY-NC-ND không được commit."""
    ),
    nbf.v4.new_code_cell(
        """import json
from pathlib import Path

import pandas as pd
from IPython.display import Image, display

from telco_churn.orange_data import DEFAULT_PATH, EXPECTED_MD5, fetch_orange, file_md5, load_orange
from telco_churn.uplift import ate_with_wald_interval

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent

DATA = ROOT / DEFAULT_PATH
REPORT = ROOT / "reports/uplift"
if not DATA.exists():
    fetch_orange(DATA)

frame = load_orange(DATA)
print({"rows": len(frame), "columns": frame.shape[1], "md5": file_md5(DATA)})"""
    ),
    nbf.v4.new_markdown_cell(
        """## 1. Data contract và structural audit

Không có customer ID hoặc campaign timestamp công khai. `row_id` dưới đây chỉ là source-order key được
an toàn bởi checksum. Do đó không được group/time split hoặc suy ra khách nào lặp lại."""
    ),
    nbf.v4.new_code_cell(
        """audit = pd.Series({
    "rows": len(frame),
    "numeric_PC": sum(c.startswith("PC") for c in frame),
    "categorical_FACTOR": sum(c.startswith("FACTOR") for c in frame),
    "missing_cells": int(frame.isna().sum().sum()),
    "duplicate_rows": int(frame.duplicated().sum()),
    "treatment_rate": frame["t"].mean(),
    "churn_rate": frame["y"].mean(),
})
display(audit.to_frame("value"))
assert file_md5(DATA) == EXPECTED_MD5
assert frame.shape == (11_896, 180)
assert not frame.isna().any().any()"""
    ),
    nbf.v4.new_markdown_cell(
        """## 2. Treatment × outcome và average effect

Chênh lệch raw rate chỉ hợp lệ cho eligible high-risk pool. CI và event count phải đứng cạnh point
estimate vì outcome chỉ khoảng 3,4%."""
    ),
    nbf.v4.new_code_cell(
        """arm_table = frame.groupby("t")["y"].agg(n="size", churn_events="sum", churn_rate="mean")
display(arm_table)
ate = ate_with_wald_interval(frame["y"].to_numpy(), frame["t"].to_numpy())
display(pd.Series(ate).to_frame("value"))"""
    ),
    nbf.v4.new_markdown_cell("## 3. Power: effect nhỏ hơn độ phân giải của experiment"),
    nbf.v4.new_code_cell(
        """profile = json.loads((REPORT / "data_profile.json").read_text(encoding="utf-8"))
power = pd.Series(profile["power"])
display(power.to_frame("value"))
print(
    f"Observed effect = {power['ate_prevented_churn']:.3%}; "
    f"80% power MDE = {power['mde_80pct_power_two_sided_alpha_0_05']:.3%}; "
    f"required N at observed effect ≈ {int(power['required_n_for_observed_effect_80pct_power']):,}."
)"""
    ),
    nbf.v4.new_markdown_cell(
        """## 4. Assignment balance diagnostics

Max SMD không phải global randomization test khi có 178 feature/many levels. Dùng để tìm data join lỗi,
không cherry-pick một feature hậu nghiệm. Paper gốc báo classifier two-sample permutation p=0,26."""
    ),
    nbf.v4.new_code_cell(
        """numeric_balance = pd.read_csv(REPORT / "balance_numeric.csv")
categorical_balance = pd.read_csv(REPORT / "balance_categorical.csv")
display(numeric_balance.head(10))
display(categorical_balance.head(10))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 5. Frozen split và leakage boundary

Split 80/20 stratify joint `(t,y)`. Tất cả preprocessing/model/budget selection dùng development OOF;
holdout không quyết định model. Public data thiếu time nên đây vẫn không phải temporal validation."""
    ),
    nbf.v4.new_code_cell(
        """manifest = pd.read_csv(REPORT / "split_manifest.csv")
display(pd.crosstab([manifest["split"], manifest["treatment"]], manifest["outcome"], margins=True))
print("manifest_sha256:", profile["manifest_sha256"])"""
    ),
    nbf.v4.new_markdown_cell(
        """## 6. Development OOF benchmark

Risk, S-, T- và DR-learners được so bằng cùng folds. AUUC/Qini dùng DR score để giảm variance; IPW được
giữ như sensitivity check. Convention nằm trong `telco_churn.uplift.curve_metrics`."""
    ),
    nbf.v4.new_code_cell(
        """oof = pd.read_csv(REPORT / "oof_model_comparison.csv")
display(oof.sort_values("qini_dr", ascending=False))

budget = pd.read_csv(REPORT / "oof_budget_metrics.csv")
display(
    budget.sort_values("dr_incremental_churns_prevented", ascending=False)
          .head(12)[["model", "budget_fraction", "dr_uplift", "dr_ci95_low", "dr_ci95_high",
                     "dr_incremental_churns_prevented"]]
)"""
    ),
    nbf.v4.new_markdown_cell("## 7. Locked holdout decision"),
    nbf.v4.new_code_cell(
        """locked = json.loads((REPORT / "locked_policy_decision.json").read_text(encoding="utf-8"))
display(pd.Series({k: v for k, v in locked.items() if k != "gates"}).to_frame("value"))
display(pd.Series(locked["gates"]).to_frame("pass"))
assert locked["test_decision"] == 'no_launch'"""
    ),
    nbf.v4.new_code_cell(
        """display(Image(filename=str(REPORT / "figures/holdout_uplift_curves.png")))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 8. Kết luận không được sửa sau test

- Qini dương không đủ: DR và IPW CI đều qua 0, control chỉ có 15 churn events trong locked segment.
- Không có margin/contact/offer cost nên không báo profit; chỉ có break-even `uplift × value`.
- Không diễn giải PC/factor importance thành churn driver.
- Next action không phải thêm model tùy ý: tăng randomized control/events, chuẩn hóa offer, log delivery,
  cost, margin, campaign/customer/time IDs và chạy rolling evaluation.

Xem report đầy đủ ở `reports/uplift/CAUSAL_BENCHMARK_REPORT.md`."""
    ),
]


temporal_cells = [
    nbf.v4.new_markdown_cell(
        """# 04 — Temporal retention policy lab

Notebook dùng synthetic customer-month vì public Orange file không có time/customer ID và không quan sát
counterfactual. Mục tiêu là **test mechanism**: point-in-time safety, treatment-effect drift, risk ≠
persuadability, true policy value và regret. Không một con số nào ở đây là ROI telco thật."""
    ),
    nbf.v4.new_code_cell(
        """import json
from pathlib import Path

import pandas as pd
from IPython.display import Image, display

from telco_churn.simulation import ORACLE_COLUMNS, TEMPORAL_FEATURES, simulate_customer_months
from telco_churn.temporal_lab import validate_point_in_time_schema

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent

REPORT = ROOT / "reports/temporal_lab"
frame = simulate_customer_months(customers=6_000, months=18, seed=20260914)
validate_point_in_time_schema(frame)
summary = json.loads((REPORT / "summary.json").read_text(encoding="utf-8"))
display(pd.Series(summary["simulation"]).to_frame("value"))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 1. Point-in-time and oracle isolation

Mỗi row là active customer ở đầu tháng. Treatment được randomize sau snapshot; churn xảy ra trong 30
ngày. `true_*` và potential outcomes chỉ ở audit layer và bị schema test cấm làm feature."""
    ),
    nbf.v4.new_code_cell(
        """print("Model features:", TEMPORAL_FEATURES)
print("Oracle-only columns:", ORACLE_COLUMNS)
assert not set(ORACLE_COLUMNS).intersection(TEMPORAL_FEATURES)
assert "treatment" not in TEMPORAL_FEATURES
display(frame.head(3))"""
    ),
    nbf.v4.new_markdown_cell(
        "## 2. Risk-set integrity: churned customer không xuất hiện ở tháng sau"
    ),
    nbf.v4.new_code_cell(
        """last_month = frame.groupby("customer_id")["month_index"].max()
churned = frame[frame["churn_next_30d"].eq(1)].set_index("customer_id")
violations = (last_month.reindex(churned.index).to_numpy() > churned["month_index"].to_numpy()).sum()
print({"churn_rows": len(churned), "future_row_violations": int(violations)})
assert violations == 0"""
    ),
    nbf.v4.new_markdown_cell(
        "## 3. Regime change: outcome drift và treatment-effect drift khác nhau"
    ),
    nbf.v4.new_code_cell(
        """monthly = frame.groupby(["month_index", "post_drift"]).agg(
    active=("customer_id", "size"),
    churn_rate=("churn_next_30d", "mean"),
    true_ate=("true_cate_prevented_churn", "mean"),
    harmful_share=("true_cate_prevented_churn", lambda x: (x < 0).mean()),
).reset_index()
display(monthly)"""
    ),
    nbf.v4.new_markdown_cell(
        """## 4. Split protocol: AP thô không đủ để kết luận drift

Row-random trộn tương lai vào train. Out-of-time có prevalence khác, nên phải đọc AP lift và Brier skill,
không so AP raw một mình."""
    ),
    nbf.v4.new_code_cell(
        """protocols = pd.read_csv(REPORT / "split_protocol_comparison.csv")
display(protocols)"""
    ),
    nbf.v4.new_markdown_cell("## 5. Covariate drift triage"),
    nbf.v4.new_code_cell(
        """display(pd.read_csv(REPORT / "drift_psi.csv").sort_values("psi_train_vs_test", ascending=False))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 6. Temporal validation policy search

Policy selection dùng DR-estimated net value và cluster-robust CI theo customer. Nếu không policy nào có
lower 95% bound > 0, `no_contact` thắng — dù point estimate khác có vẻ dương."""
    ),
    nbf.v4.new_code_cell(
        """validation = pd.read_csv(REPORT / "validation_policy_search.csv")
display(
    validation.sort_values("estimated_net_value", ascending=False)
              .head(15)[["policy", "budget_fraction", "estimated_net_value",
                         "estimated_net_value_per_contact", "estimated_value_per_contact_ci95_low",
                         "estimated_value_per_contact_ci95_high", "true_net_value"]]
)
print("Locked:", summary["selected"])"""
    ),
    nbf.v4.new_markdown_cell("## 7. Known-truth test: risk vs causal vs oracle"),
    nbf.v4.new_code_cell(
        """test = pd.read_csv(REPORT / "test_policy_truth.csv")
at_20 = test[test["budget_fraction"].eq(0.20)].sort_values("true_net_value", ascending=False)
display(at_20[["policy", "selected_n", "true_net_value", "true_expected_churns_prevented",
               "harmful_offer_share", "regret_vs_oracle_value"]])
display(Image(filename=str(REPORT / "figures/test_policy_value_at_20pct.png")))"""
    ),
    nbf.v4.new_markdown_cell("## 8. CATE recovery không đồng nghĩa policy value"),
    nbf.v4.new_code_cell(
        """display(pd.read_csv(REPORT / "test_cate_diagnostics.csv").sort_values("pehe"))"""
    ),
    nbf.v4.new_markdown_cell("## 9. Continuous rolling decision"),
    nbf.v4.new_code_cell(
        """rolling = pd.read_csv(REPORT / "rolling_backtest.csv")
display(rolling)"""
    ),
    nbf.v4.new_markdown_cell(
        """## 10. Kết luận đúng phạm vi

- Ground truth chứng minh được risk targeting có thể âm sau effect drift và một uplift learner có thể
  giảm harmful contacts ở cùng capacity.
- Gate bảo thủ tránh expected loss nhưng có opportunity cost; cần persistent exploration và power lớn hơn
  để học segment hiệu quả, không nên tắt control.
- Thứ tự S/T/DR ở DGP này không phải leaderboard chung.
- Muốn claim thực tế phải thay generator bằng governed customer-month data, treatment assignment,
  delivery/cost/margin và future holdout từ doanh nghiệp."""
    ),
]


stability_cells = [
    nbf.v4.new_markdown_cell(
        """# 05 — Model stability, feature ablation and tuning

**Hypotheses:** (H1) X-learner có lợi khi treatment/control lệch 75/25; (H2) causal candidate chỉ đáng
giữ nếu thắng risk baseline qua nhiều seeds; (H3) feature compression/regularization phải tăng stability,
không chỉ một lucky Qini.

Tất cả thí nghiệm dùng 9.516 development rows. Holdout đã mở ở notebook 03 không được dùng để chọn lại
model; mọi winner mới chỉ là future challenger."""
    ),
    nbf.v4.new_code_cell(
        """import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
STABILITY = ROOT / "reports/uplift/stability"
TUNING = ROOT / "reports/uplift/tuning"
TOURNAMENT = ROOT / "reports/uplift/tournament"
ABLATION = ROOT / 'reports/uplift/component_ablation'"""
    ),
    nbf.v4.new_markdown_cell(
        """## 1. Repeated OOF protocol

5 repeats × 3 stratified folds. Mỗi repeat refit cross-fitted nuisance outcomes và toàn bộ risk/T/S/DR/X
scores. Primary là Qini-DR; IPW là sensitivity; supporting gồm positive-rate, mean rank, uplift@20 và
paired win-rate so với risk-logistic."""
    ),
    nbf.v4.new_code_cell(
        """stability_meta = json.loads((STABILITY / "stability_summary.json").read_text(encoding="utf-8"))
stability = pd.read_csv(STABILITY / "repeated_oof_summary.csv")
display(pd.Series(stability_meta).to_frame("value"))
display(stability)"""
    ),
    nbf.v4.new_markdown_cell("## 2. Seed distribution, không chỉ mean"),
    nbf.v4.new_code_cell(
        """raw = pd.read_csv(STABILITY / "repeated_oof_raw.csv")
order = stability.sort_values("qini_dr_mean", ascending=False)["model"].tolist()
fig, ax = plt.subplots(figsize=(9, 5))
raw.boxplot(column="qini_dr", by="model", ax=ax, grid=False, rot=35)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_title("Development-only Qini-DR across five seeds")
ax.set_xlabel("")
ax.set_ylabel("Qini-DR")
fig.suptitle("")
plt.tight_layout()
plt.show()"""
    ),
    nbf.v4.new_code_cell(
        """paired = raw.pivot(index="repeat", columns="model", values="qini_dr")
for model in [c for c in paired if c != "risk_logistic"]:
    paired[f"delta_{model}_vs_risk"] = paired[model] - paired["risk_logistic"]
display(paired[[c for c in paired if c.startswith("delta_")]])"""
    ),
    nbf.v4.new_markdown_cell(
        """## 3. Estimator agreement gate

Qini-IPW dương nhưng Qini-DR âm là instability signal, không phải cơ hội chọn estimator có kết quả đẹp.
S-HGB rơi đúng trường hợp này; X-HGB gần zero và không thắng risk ở seed nào."""
    ),
    nbf.v4.new_code_cell(
        """display(stability[["model", "qini_dr_mean", "qini_dr_std", "qini_ipw_mean",
                   "qini_ipw_std", "qini_dr_positive_rate", "mean_rank", "beats_risk_rate"]])"""
    ),
    nbf.v4.new_markdown_cell(
        """## 4. Risk-logistic tuning matrix

24 configs = 4 feature sets × 6 values of C; mỗi config chạy 3 seeds × 3 folds. Tuning objective vẫn là
policy Qini-DR, không phải AUC. `PC1..PCk` chỉ là variance-order ablation, không business feature
selection."""
    ),
    nbf.v4.new_code_cell(
        """tuning = pd.read_csv(TUNING / "risk_logistic_tuning_summary.csv")
decision = json.loads((TUNING / "tuning_decision.json").read_text(encoding="utf-8"))
display(tuning.head(15))
display(pd.Series(decision["recommended_future_challenger"]).to_frame("value"))"""
    ),
    nbf.v4.new_code_cell(
        """fig, ax = plt.subplots(figsize=(9, 5))
for feature_set, part in tuning.groupby("feature_set"):
    part = part.sort_values("C")
    ax.errorbar(part["C"], part["qini_dr_mean"], yerr=part["qini_dr_std"], marker="o", label=feature_set)
ax.set_xscale("log")
ax.axhline(0, color="black", linewidth=0.8)
ax.set(xlabel="Logistic C", ylabel="Repeated mean Qini-DR", title="Regularization × feature ablation")
ax.legend(fontsize=8)
ax.grid(alpha=0.2)
plt.tight_layout()
plt.show()"""
    ),
    nbf.v4.new_markdown_cell(
        """## 5. Full model-family tournament

14 cấu hình phủ risk/S/T/transformed-outcome/DR/R/X và Logistic/RF/HGB/CatBoost/ExtraTrees. Đây là
development-only screen; Qini-DR là primary, IPW là sensitivity, 20% là reference capacity. `basic_gate`
không đồng nghĩa đủ launch."""
    ),
    nbf.v4.new_code_cell(
        """tournament = pd.read_csv(TOURNAMENT / "tournament_summary.csv")
tournament_decision = json.loads(
    (TOURNAMENT / "tournament_decision.json").read_text(encoding="utf-8")
)
display(tournament[["model", "family", "qini_dr_mean", "qini_dr_std", "qini_ipw_mean",
                    "delta_vs_risk_mean", "delta_vs_risk_ci95_low", "beats_risk_rate",
                    "dr_uplift_20_mean", "runtime_seconds_mean", "basic_gate"]])
display(pd.Series(tournament_decision).to_frame("value"))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 6. Thuật toán con và evaluator sensitivity

Giữ nguyên policy OOF scores, thay common nuisance evaluator giữa Logistic, HGB và CatBoost. Brier/log-loss
chọn nuisance; minimum Qini qua evaluator chọn robust component. Không được lấy evaluator làm model ưa thích
đẹp hơn."""
    ),
    nbf.v4.new_code_cell(
        """nuisance = pd.read_csv(ABLATION / "nuisance_diagnostics_summary.csv")
robustness = pd.read_csv(ABLATION / "model_evaluator_robustness.csv")
components = pd.read_csv(ABLATION / "component_winners.csv")
display(nuisance)
display(robustness)
display(components)"""
    ),
    nbf.v4.new_markdown_cell(
        """## 7. Decision

- Risk-logistic mean Qini-DR 0,002668, dương 5/5, mean rank 1,0.
- X-HGB mean 0,000008, dương 2/5, thắng risk 0/5: H1 bị bác bỏ trên dataset này.
- S-HGB IPW/DR khác dấu: reject vì estimator sensitivity.
- Best tuning mean là all-178/C=3; one-standard-error rule giữ all-178/C=0,3 — đúng current baseline,
  tránh đổi model vì improvement nhỏ/variance lớn.
- Tournament/ablation winner là **future challenger**, không sửa champion cũ sau khi holdout đã mở. Một causal
  replacement còn phải có paired delta lower CI > 0, thắng ≥80% repeats và giữ dấu qua mọi evaluator.
- Không retest holdout. Challenger tiếp theo cần campaign/time split mới; nếu không có, dừng tuning."""
    ),
]


policy_cells = [
    nbf.v4.new_markdown_cell(
        """# 06 — Policy value, estimator disagreement and failure analysis

Notebook này không train model. Nó kiểm tra model scores có chuyển thành quyết định đáng tin hay không:
capacity, IPW/DR/raw difference, break-even cost, no-contact, harmful contacts và oracle regret."""
    ),
    nbf.v4.new_code_cell(
        """import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
REAL = ROOT / "reports/uplift"
MOCK = ROOT / "reports/temporal_lab"
locked = json.loads((REAL / "locked_policy_decision.json").read_text(encoding="utf-8"))"""
    ),
    nbf.v4.new_markdown_cell("## 1. Real holdout: ba estimators ở từng capacity"),
    nbf.v4.new_code_cell(
        """real = pd.read_csv(REAL / "holdout_exploratory_metrics.csv")
cols = ["model", "budget_fraction", "selected_n", "control_churn_rate", "treated_churn_rate",
        "difference_in_means_uplift", "ipw_uplift", "dr_uplift", "qini"]
display(real[cols].sort_values(["budget_fraction", "dr_uplift"], ascending=[True, False]))"""
    ),
    nbf.v4.new_markdown_cell(
        """Estimator disagreement là failure flag. Difference-in-means hợp lệ vì policy score trên
holdout không dùng test treatment/outcome; IPW dùng design propensity; DR thêm outcome nuisance. Với ít
events, chúng có thể lệch mạnh trong finite sample — không chọn estimator hậu nghiệm."""
    ),
    nbf.v4.new_code_cell(
        """real["ipw_dr_sign_disagreement"] = np.sign(real["ipw_uplift"]) != np.sign(real["dr_uplift"])
display(real.groupby("model")["ipw_dr_sign_disagreement"].agg(["sum", "count", "mean"]))"""
    ),
    nbf.v4.new_markdown_cell("## 2. Locked policy gates"),
    nbf.v4.new_code_cell(
        """display(pd.Series({k: v for k, v in locked.items() if k != "gates"}).to_frame("value"))
display(pd.Series(locked["gates"]).to_frame("pass"))"""
    ),
    nbf.v4.new_markdown_cell(
        """## 3. Break-even analysis không bịa CLV

Nếu một prevented churn có giá trị `V`, contact cost tối đa theo estimate là `uplift × V`. Vì cả IPW và
DR lower CI âm, lower-bound break-even cũng âm với mọi V dương; không có contact cost dương được dữ liệu
bảo đảm."""
    ),
    nbf.v4.new_code_cell(
        """values = np.array([100, 300, 600, 1000], dtype=float)
break_even = pd.DataFrame({
    "value_per_prevented_churn": values,
    "dr_point_max_contact_cost": locked["test_dr_uplift"] * values,
    "dr_lower95_max_contact_cost": locked["test_ci95_low"] * values,
    "ipw_point_max_contact_cost": locked["test_ipw_uplift"] * values,
    "ipw_lower95_max_contact_cost": locked["test_ipw_ci95_low"] * values,
})
display(break_even)"""
    ),
    nbf.v4.new_markdown_cell("## 4. Known-truth post-drift policy failure"),
    nbf.v4.new_code_cell(
        """mock = pd.read_csv(MOCK / "test_policy_truth.csv")
at_20 = mock[mock["budget_fraction"].eq(0.20)].sort_values("true_net_value", ascending=False)
display(at_20[["policy", "true_net_value", "true_expected_churns_prevented",
               "harmful_offer_share", "regret_vs_oracle_value"]])"""
    ),
    nbf.v4.new_code_cell(
        """comparison = at_20[at_20["policy"].isin(["risk_hgb", "s_hgb", "dr_hgb", "x_hgb",
                                                       "random", "oracle_value"])]
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].barh(comparison["policy"], comparison["true_net_value"])
axes[0].axvline(0, color="black", linewidth=.8)
axes[0].set_title("True net value @20%")
axes[1].barh(comparison["policy"], comparison["harmful_offer_share"])
axes[1].set_title("Harmful-contact share @20%")
plt.tight_layout()
plt.show()"""
    ),
    nbf.v4.new_markdown_cell(
        """## 5. Failure taxonomy và action

| Failure | Evidence | Correct action |
|---|---|---|
| Underpowered ATE | observed 0,275pp < MDE 1,112pp | larger/balanced RCT |
| Selected-arm event scarcity | 15 control churn events | collect control events; no launch |
| Estimator disagreement | IPW/DR sign differs for many policies | investigate overlap/nuisance; do not cherry-pick |
| Effect drift | mock ATE +0,649% → −0,105% | persistent control + rolling effect monitoring |
| Risk ≠ response | mock risk policy value −2.813 @20% | causal/value policy shadow test |
| Conservative opportunity cost | no-contact regret 6.806 vs oracle | continue randomized exploration with power target |
| Feature opacity | Orange PCA/factors anonymized | no causal reason codes/action playbook |

Decision tốt có thể là `NO_LAUNCH`; nhưng no-launch không đồng nghĩa ngừng học. Nó phải đi kèm sample-size
target, control allocation, treatment definition và next review date."""
    ),
]


def main() -> None:
    NOTEBOOKS.mkdir(exist_ok=True)
    nbf.write(
        notebook(orange_cells, "Orange causal-retention audit"),
        NOTEBOOKS / "03_orange_causal_audit.ipynb",
    )
    nbf.write(
        notebook(temporal_cells, "Temporal retention policy lab"),
        NOTEBOOKS / "04_temporal_policy_lab.ipynb",
    )
    nbf.write(
        notebook(stability_cells, "Model stability and tuning"),
        NOTEBOOKS / "05_model_stability_and_tuning.ipynb",
    )
    nbf.write(
        notebook(policy_cells, "Policy value and failure analysis"),
        NOTEBOOKS / "06_policy_value_and_failure_analysis.ipynb",
    )


if __name__ == "__main__":
    main()
