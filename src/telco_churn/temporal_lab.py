"""Temporal, drift, and known-counterfactual retention policy laboratory."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.model_selection import train_test_split

from telco_churn.simulation import (
    OFFER_COST,
    ORACLE_COLUMNS,
    SIMULATION_SEED,
    TEMPORAL_FEATURES,
    simulate_customer_months,
    simulation_summary,
)
from telco_churn.uplift import (
    doubly_robust_scores,
    fit_policy_model,
    top_fraction_mask,
)

MODEL_CANDIDATES = ("risk_hgb", "t_hgb", "s_hgb", "dr_hgb", "x_hgb")
BUDGETS = (0.10, 0.20, 0.30)


def validate_point_in_time_schema(frame: pd.DataFrame) -> None:
    forbidden = {
        "treatment",
        "treatment_propensity",
        "churn_next_30d",
        *ORACLE_COLUMNS,
    }
    overlap = forbidden.intersection(TEMPORAL_FEATURES)
    missing = set(TEMPORAL_FEATURES).difference(frame.columns)
    if overlap:
        raise ValueError(f"Post-treatment/oracle leakage in features: {sorted(overlap)}")
    if missing:
        raise ValueError(f"Missing temporal features: {sorted(missing)}")


def _stable_random_score(ids: pd.Series, months: pd.Series, seed: int) -> np.ndarray:
    hashed = pd.util.hash_pandas_object(
        ids.astype(str) + ":" + months.astype(str) + f":{seed}", index=False
    )
    return hashed.to_numpy(dtype=np.uint64) / np.iinfo(np.uint64).max


def _score_models(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    *,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    x_train = train.loc[:, TEMPORAL_FEATURES]
    x_eval = evaluation.loc[:, TEMPORAL_FEATURES]
    treatment = train["treatment"].to_numpy(dtype=int)
    outcome = train["churn_next_30d"].to_numpy(dtype=int)
    propensity = float(train["treatment"].mean())
    scores = {
        "random": _stable_random_score(
            evaluation["customer_id"], evaluation["snapshot_month"], seed
        ),
        "oracle_uplift": evaluation["true_cate_prevented_churn"].to_numpy(),
        "oracle_value": evaluation["true_net_value"].to_numpy(),
    }
    cate_predictions: dict[str, np.ndarray] = {}
    fitted: dict[str, Any] = {}
    for model_name in MODEL_CANDIDATES:
        model = fit_policy_model(
            model_name,
            x_train,
            treatment,
            outcome,
            propensity=propensity,
            seed=seed,
        )
        raw_score, _, _ = model.predict(x_eval)
        fitted[model_name] = model
        scores[model_name] = raw_score
        if not model_name.startswith("risk_"):
            cate_predictions[model_name] = raw_score
            scores[f"value_{model_name}"] = (
                raw_score * evaluation["gross_margin_6m"].to_numpy() - OFFER_COST
            )
    return scores, cate_predictions, fitted


def _evaluation_effect_score(
    train: pd.DataFrame, evaluation: pd.DataFrame, seed: int
) -> np.ndarray:
    nuisance = fit_policy_model(
        "t_logistic",
        train.loc[:, TEMPORAL_FEATURES],
        train["treatment"].to_numpy(dtype=int),
        train["churn_next_30d"].to_numpy(dtype=int),
        propensity=float(train["treatment"].mean()),
        seed=seed,
    )
    _, p0, p1 = nuisance.predict(evaluation.loc[:, TEMPORAL_FEATURES])
    return doubly_robust_scores(
        evaluation["churn_next_30d"].to_numpy(dtype=int),
        evaluation["treatment"].to_numpy(dtype=int),
        p0,
        p1,
        float(train["treatment"].mean()),
    )


def policy_truth_table(
    scores: dict[str, np.ndarray],
    frame: pd.DataFrame,
    estimated_effect: np.ndarray,
    *,
    budgets: tuple[float, ...] = BUDGETS,
) -> pd.DataFrame:
    ids = (frame["customer_id"].astype(str) + ":" + frame["snapshot_month"].astype(str)).to_numpy()
    true_cate = frame["true_cate_prevented_churn"].to_numpy()
    true_value = frame["true_net_value"].to_numpy()
    margin = frame["gross_margin_6m"].to_numpy()
    rows = []
    rows.append(
        {
            "policy": "no_contact",
            "budget_fraction": 0.0,
            "selected_n": 0,
            "estimated_net_value": 0.0,
            "estimated_net_value_per_contact": 0.0,
            "estimated_value_per_contact_ci95_low": 0.0,
            "estimated_value_per_contact_ci95_high": 0.0,
            "true_net_value": 0.0,
            "true_net_value_per_contact": 0.0,
            "true_mean_cate": 0.0,
            "true_expected_churns_prevented": 0.0,
            "harmful_offer_share": 0.0,
            "regret_vs_oracle_value": 0.0,
        }
    )
    oracle_value = scores["oracle_value"]
    for budget in budgets:
        oracle_mask = top_fraction_mask(oracle_value, ids, budget)
        oracle_total = float(true_value[oracle_mask].sum())
        for name, score in scores.items():
            selected = top_fraction_mask(score, ids, budget)
            estimated_total = float(
                (estimated_effect[selected] * margin[selected] - OFFER_COST).sum()
            )
            estimated_contribution = estimated_effect * margin - OFFER_COST
            estimated_mean = float(estimated_contribution[selected].mean())
            selected_groups = pd.DataFrame(
                {
                    "customer_id": frame.loc[selected, "customer_id"].to_numpy(),
                    "contribution": estimated_contribution[selected],
                }
            )
            centered = selected_groups["contribution"] - estimated_mean
            cluster_residual = centered.groupby(selected_groups["customer_id"]).sum()
            cluster_count = len(cluster_residual)
            cluster_variance = (
                cluster_count
                / (cluster_count - 1)
                * float(np.square(cluster_residual).sum())
                / selected.sum() ** 2
                if cluster_count > 1
                else math.nan
            )
            cluster_se = math.sqrt(cluster_variance)
            true_total = float(true_value[selected].sum())
            rows.append(
                {
                    "policy": name,
                    "budget_fraction": budget,
                    "selected_n": int(selected.sum()),
                    "estimated_net_value": estimated_total,
                    "estimated_net_value_per_contact": estimated_mean,
                    "estimated_value_per_contact_ci95_low": estimated_mean
                    - 1.959963984540054 * cluster_se,
                    "estimated_value_per_contact_ci95_high": estimated_mean
                    + 1.959963984540054 * cluster_se,
                    "true_net_value": true_total,
                    "true_net_value_per_contact": true_total / selected.sum(),
                    "true_mean_cate": float(true_cate[selected].mean()),
                    "true_expected_churns_prevented": float(true_cate[selected].sum()),
                    "harmful_offer_share": float((true_cate[selected] < 0).mean()),
                    "regret_vs_oracle_value": oracle_total - true_total,
                }
            )
    result = pd.DataFrame(rows)
    best_oracle = max(
        0.0,
        float(result.loc[result["policy"].eq("oracle_value"), "true_net_value"].max()),
    )
    result["regret_vs_best_oracle_available"] = best_oracle - result["true_net_value"]
    return result


def cate_diagnostics(predictions: dict[str, np.ndarray], evaluation: pd.DataFrame) -> pd.DataFrame:
    truth = evaluation["true_cate_prevented_churn"].to_numpy()
    rows = []
    for name, prediction in predictions.items():
        correlation = spearmanr(prediction, truth).statistic
        rows.append(
            {
                "model": name,
                "pehe": float(np.sqrt(np.mean((prediction - truth) ** 2))),
                "cate_bias": float(np.mean(prediction - truth)),
                "spearman_with_true_cate": float(correlation),
            }
        )
    return pd.DataFrame(rows)


def population_stability_index(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    reference = pd.to_numeric(reference, errors="raise")
    current = pd.to_numeric(current, errors="raise")
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_share = pd.cut(reference, edges, include_lowest=True).value_counts(
        normalize=True, sort=False
    )
    cur_share = pd.cut(current, edges, include_lowest=True).value_counts(normalize=True, sort=False)
    ref = np.clip(ref_share.to_numpy(), 1e-6, None)
    cur = np.clip(cur_share.to_numpy(), 1e-6, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def _risk_protocol_comparison(frame: pd.DataFrame, *, seed: int) -> pd.DataFrame:
    # A row-random split mixes post-drift rows into training. The temporal split
    # is the valid estimate for a model trained before the regime change.
    controls = frame[frame["treatment"].eq(0)].reset_index(drop=True)
    random_train, random_test = train_test_split(
        controls,
        test_size=0.20,
        random_state=seed,
        stratify=controls["churn_next_30d"],
    )
    temporal_train = controls[controls["month_index"].le(11)]
    temporal_test = controls[controls["month_index"].ge(15)]
    rows = []
    for protocol, train, test in (
        ("invalid_row_random_mixed_time", random_train, random_test),
        ("valid_out_of_time", temporal_train, temporal_test),
    ):
        model = fit_policy_model(
            "risk_hgb",
            train.loc[:, TEMPORAL_FEATURES],
            np.zeros(len(train), dtype=int),
            train["churn_next_30d"].to_numpy(dtype=int),
            propensity=0.5,
            seed=seed,
        )
        probability = model.predict(test.loc[:, TEMPORAL_FEATURES])[0]
        y = test["churn_next_30d"].to_numpy(dtype=int)
        prevalence = float(y.mean())
        brier = brier_score_loss(y, probability)
        average_precision = average_precision_score(y, probability)
        rows.append(
            {
                "protocol": protocol,
                "train_rows": len(train),
                "test_rows": len(test),
                "test_month_min": int(test["month_index"].min()),
                "test_month_max": int(test["month_index"].max()),
                "average_precision": average_precision,
                "average_precision_lift": average_precision / prevalence,
                "brier_score": brier,
                "brier_skill_score": 1 - brier / (prevalence * (1 - prevalence)),
                "prevalence": prevalence,
            }
        )
    return pd.DataFrame(rows)


def _rolling_backtest(
    frame: pd.DataFrame,
    policy_name: str,
    budget: float,
    *,
    seed: int,
) -> pd.DataFrame:
    base_name = policy_name.removeprefix("value_")
    rows = []
    for month in range(15, 18):
        train = frame[frame["month_index"].lt(month)].reset_index(drop=True)
        test = frame[frame["month_index"].eq(month)].reset_index(drop=True)
        if base_name == "no_contact":
            score = np.zeros(len(test))
        elif base_name == "random":
            score = _stable_random_score(test["customer_id"], test["snapshot_month"], seed + month)
        else:
            model = fit_policy_model(
                base_name,
                train.loc[:, TEMPORAL_FEATURES],
                train["treatment"].to_numpy(dtype=int),
                train["churn_next_30d"].to_numpy(dtype=int),
                propensity=float(train["treatment"].mean()),
                seed=seed + month,
            )
            score = model.predict(test.loc[:, TEMPORAL_FEATURES])[0]
            if policy_name.startswith("value_"):
                score = score * test["gross_margin_6m"].to_numpy() - OFFER_COST
        ids = (test["customer_id"] + ":" + test["snapshot_month"].astype(str)).to_numpy()
        selected = (
            np.zeros(len(test), dtype=bool)
            if budget == 0
            else top_fraction_mask(score, ids, budget)
        )
        true_value = test["true_net_value"].to_numpy()
        true_cate = test["true_cate_prevented_churn"].to_numpy()
        oracle_totals = [0.0]
        for candidate_budget in BUDGETS:
            candidate = top_fraction_mask(true_value, ids, candidate_budget)
            oracle_totals.append(float(true_value[candidate].sum()))
        best_oracle_value = max(oracle_totals)
        rows.append(
            {
                "month_index": month,
                "snapshot_month": str(test["snapshot_month"].min().date()),
                "training_rows": len(train),
                "active_customers": len(test),
                "selected_n": int(selected.sum()),
                "true_net_value": float(true_value[selected].sum()),
                "oracle_net_value": best_oracle_value,
                "regret": float(best_oracle_value - true_value[selected].sum()),
                "true_mean_cate": float(true_cate[selected].mean()) if selected.any() else 0.0,
                "harmful_offer_share": (
                    float((true_cate[selected] < 0).mean()) if selected.any() else 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot_policy_value(table: pd.DataFrame, path: Path, title: str) -> None:
    subset = table[table["budget_fraction"].eq(0.20)].sort_values("true_net_value")
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#2b6cb0" if value >= 0 else "#c53030" for value in subset["true_net_value"]]
    ax.barh(subset["policy"], subset["true_net_value"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set(title=title, xlabel="True net value in synthetic currency units")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _report(
    summary: dict[str, Any],
    selected: dict[str, Any],
    test_row: pd.Series,
    test_policies: pd.DataFrame,
    protocols: pd.DataFrame,
    rolling: pd.DataFrame,
) -> str:
    random_ap = protocols.loc[
        protocols["protocol"].eq("invalid_row_random_mixed_time"), "average_precision"
    ].iloc[0]
    temporal_ap = protocols.loc[
        protocols["protocol"].eq("valid_out_of_time"), "average_precision"
    ].iloc[0]
    random_bss = protocols.loc[
        protocols["protocol"].eq("invalid_row_random_mixed_time"), "brier_skill_score"
    ].iloc[0]
    temporal_bss = protocols.loc[
        protocols["protocol"].eq("valid_out_of_time"), "brier_skill_score"
    ].iloc[0]
    at_20 = test_policies[test_policies["budget_fraction"].eq(0.20)].set_index("policy")
    risk = at_20.loc["risk_hgb"]
    uplift = at_20.loc["s_hgb"]
    oracle = at_20.loc["oracle_value"]
    return "\n".join(
        [
            "# Temporal retention laboratory — known-counterfactual mock data",
            "",
            "> Đây là mechanism test, không phải bằng chứng hiệu quả kinh doanh ngoài đời.",
            "",
            "## Pain point được làm rõ bằng số",
            "",
            f"Generator tạo {summary['rows']:,} customer-month của {summary['unique_customers']:,} "
            f"khách. Sau regime change, true ATE đổi từ {summary['true_ate_pre_drift']:.3%} thành "
            f"{summary['true_ate_post_drift']:.3%}; tỷ lệ offer gây hại tăng từ "
            f"{summary['harmful_offer_share_pre_drift']:.1%} lên "
            f"{summary['harmful_offer_share_post_drift']:.1%}. Một churn score vẫn có thể tốt trong "
            "khi chính sách giữ chân đã mất tác dụng.",
            "",
            f"Row-random AP = {random_ap:.4f}, out-of-time AP = {temporal_ap:.4f}, nhưng base rate "
            "cũng đổi nên AP thô không thể dùng để kết luận drift. Brier skill giảm từ "
            f"{random_bss:.4f} xuống {temporal_bss:.4f}; đây mới là bằng chứng calibration gần như "
            "mất hết giá trị sau regime change. Chỉ protocol out-of-time hợp lệ cho deployment.",
            "",
            "## Policy được khóa",
            "",
            f"Validation DR chọn `{selected['policy']}` ở {selected['budget_fraction']:.0%} capacity. "
            f"Trên test, true net value = {test_row['true_net_value']:.2f}, true expected prevented "
            f"churn = {test_row['true_expected_churns_prevented']:.2f}, harmful contacts = "
            f"{test_row['harmful_offer_share']:.1%}, regret so với best oracle khả dụng = "
            f"{test_row['regret_vs_best_oracle_available']:.2f}.",
            "",
            "Ở cùng 20% capacity trên test, risk targeting tạo true value "
            f"{risk['true_net_value']:.2f} và gửi offer có hại cho "
            f"{risk['harmful_offer_share']:.1%} nhóm được chọn. S-learner tạo "
            f"{uplift['true_net_value']:.2f}, harmful contacts {uplift['harmful_offer_share']:.1%}; "
            f"oracle value là {oracle['true_net_value']:.2f}. Đây là phép đo cụ thể của khoảng cách "
            "risk ≠ persuadability, không phải nhận xét định tính.",
            "",
            "## Continuous rolling refit",
            "",
            rolling.round(4).to_string(index=False),
            "",
            "## Điều generator cố ý mô phỏng",
            "",
            "- Snapshot trước treatment; label churn trong 30 ngày sau quyết định.",
            "- Randomized offer propensity 0.5 và heterogeneous response có cả persuadable lẫn "
            "sleeping-dog/do-not-disturb customers.",
            "- Price shock, outage regime và offer fatigue làm outcome drift lẫn treatment-effect drift.",
            "- `true_*` và potential outcomes chỉ nằm trong audit layer; schema test cấm đưa chúng vào model.",
            "- Customer churn sẽ rời risk set ở tháng sau, nên số active customer giảm theo thời gian.",
            "",
            "## Không được suy diễn",
            "",
            "Các hệ số, tiền tệ và response curve do code đặt ra. Chúng chứng minh pipeline có thể phát hiện "
            "risk ≠ persuadability, leakage và drift; chúng không ước lượng Orange, IBM hay bất kỳ telco thật nào.",
            "",
        ]
    )


def run_temporal_lab(
    output_dir: Path,
    *,
    customers: int = 6_000,
    seed: int = SIMULATION_SEED,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures").mkdir(exist_ok=True)
    frame = simulate_customer_months(customers=customers, months=18, seed=seed)
    validate_point_in_time_schema(frame)
    train = frame[frame["month_index"].le(11)].reset_index(drop=True)
    validation = frame[frame["month_index"].between(12, 14)].reset_index(drop=True)
    test = frame[frame["month_index"].ge(15)].reset_index(drop=True)

    validation_scores, validation_cate, _ = _score_models(train, validation, seed=seed)
    validation_effect = _evaluation_effect_score(train, validation, seed + 1_000)
    validation_policy = policy_truth_table(validation_scores, validation, validation_effect)
    validation_policy.to_csv(output_dir / "validation_policy_search.csv", index=False)
    cate_diagnostics(validation_cate, validation).to_csv(
        output_dir / "validation_cate_diagnostics.csv", index=False
    )
    selectable = validation_policy[
        ~validation_policy["policy"].isin(["oracle_uplift", "oracle_value"])
    ]
    evidence_positive = selectable[selectable["estimated_value_per_contact_ci95_low"].gt(0)]
    selected_row = (
        evidence_positive.sort_values("estimated_net_value", ascending=False).iloc[0]
        if not evidence_positive.empty
        else selectable[selectable["policy"].eq("no_contact")].iloc[0]
    )
    selected = {
        "policy": str(selected_row["policy"]),
        "budget_fraction": float(selected_row["budget_fraction"]),
        "selection_metric": (
            "maximum DR-estimated net value among policies with cluster-robust "
            "95% lower bound > 0; otherwise no_contact"
        ),
    }

    refit = frame[frame["month_index"].le(14)].reset_index(drop=True)
    test_scores, test_cate, _ = _score_models(refit, test, seed=seed + 2_000)
    test_effect = _evaluation_effect_score(refit, test, seed + 3_000)
    test_policy = policy_truth_table(test_scores, test, test_effect)
    test_policy.to_csv(output_dir / "test_policy_truth.csv", index=False)
    cate_diagnostics(test_cate, test).to_csv(output_dir / "test_cate_diagnostics.csv", index=False)
    protocols = _risk_protocol_comparison(frame, seed=seed)
    protocols.to_csv(output_dir / "split_protocol_comparison.csv", index=False)
    drift_rows = []
    for column in (
        "monthly_charge",
        "usage_gb_last_month",
        "outages_90d",
        "complaint_last_month",
        "observed_loyalty_score",
    ):
        drift_rows.append(
            {
                "feature": column,
                "psi_train_vs_test": population_stability_index(train[column], test[column]),
            }
        )
    pd.DataFrame(drift_rows).to_csv(output_dir / "drift_psi.csv", index=False)
    rolling = _rolling_backtest(
        frame,
        selected["policy"],
        selected["budget_fraction"],
        seed=seed + 4_000,
    )
    rolling.to_csv(output_dir / "rolling_backtest.csv", index=False)
    _plot_policy_value(
        test_policy,
        output_dir / "figures" / "test_policy_value_at_20pct.png",
        "Known-truth policy value after drift (20% capacity)",
    )

    test_selected = test_policy[
        test_policy["policy"].eq(selected["policy"])
        & test_policy["budget_fraction"].eq(selected["budget_fraction"])
    ].iloc[0]
    summary = simulation_summary(frame)
    result = {
        "simulation": summary,
        "split": {
            "train_months": "0-11",
            "validation_months": "12-14",
            "test_months": "15-17",
            "train_rows": len(train),
            "validation_rows": len(validation),
            "test_rows": len(test),
        },
        "selected": selected,
        "test": test_selected.to_dict(),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(result, indent=2, default=_json_value) + "\n", encoding="utf-8"
    )
    (output_dir / "TEMPORAL_LAB_REPORT.md").write_text(
        _report(summary, selected, test_selected, test_policy, protocols, rolling),
        encoding="utf-8",
    )
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/temporal_lab"))
    parser.add_argument("--customers", type=int, default=6_000)
    parser.add_argument("--seed", type=int, default=SIMULATION_SEED)
    args = parser.parse_args()
    result = run_temporal_lab(args.output, customers=args.customers, seed=args.seed)
    print(json.dumps(result, indent=2, default=_json_value))


if __name__ == "__main__":
    main()
