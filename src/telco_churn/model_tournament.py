"""Development-only tournament for retention-policy model families.

The tournament compares ranking policies, not just churn classifiers. Positive
effects always mean prevented churn, Y(0) - Y(1). The locked holdout is never read.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from telco_churn.orange_benchmark import SEED, _oof_scores, _random_scores, make_locked_split
from telco_churn.orange_data import FEATURE_COLUMNS, load_orange
from telco_churn.uplift import (
    budget_table,
    cross_fit_potential_outcomes,
    curve_metrics,
    doubly_robust_scores,
    ipw_scores,
    top_fraction_mask,
)

BUDGETS = (0.10, 0.20, 0.30)

CANDIDATES: dict[str, dict[str, Any]] = {
    "risk_logistic": {
        "family": "risk",
        "base_learner": "logistic",
        "complexity": 1,
        "hypothesis": "stable low-variance baseline can proxy persuadability",
    },
    "risk_rf": {
        "family": "risk",
        "base_learner": "random_forest",
        "complexity": 4,
        "hypothesis": "nonlinear control risk improves policy ranking",
    },
    "risk_hgb": {
        "family": "risk",
        "base_learner": "hist_gradient_boosting",
        "complexity": 4,
        "hypothesis": "regularized boosting finds nonlinear control-risk segments",
    },
    "risk_catboost": {
        "family": "risk",
        "base_learner": "catboost_native_categories",
        "complexity": 5,
        "hypothesis": "ordered boosting improves mixed numeric/factor risk ranking",
    },
    "s_logistic": {
        "family": "s_learner",
        "base_learner": "logistic_with_treatment_interactions",
        "complexity": 2,
        "hypothesis": "shared structure lowers variance while explicit interactions recover CATE",
    },
    "s_hgb": {
        "family": "s_learner",
        "base_learner": "hist_gradient_boosting",
        "complexity": 5,
        "hypothesis": "one nonlinear response surface shares information across arms",
    },
    "t_logistic": {
        "family": "t_learner",
        "base_learner": "logistic",
        "complexity": 3,
        "hypothesis": "separate regularized arm models recover linear heterogeneity",
    },
    "t_hgb": {
        "family": "t_learner",
        "base_learner": "hist_gradient_boosting",
        "complexity": 6,
        "hypothesis": "separate nonlinear response surfaces recover heterogeneous effects",
    },
    "t_catboost": {
        "family": "t_learner",
        "base_learner": "catboost_native_categories",
        "complexity": 7,
        "hypothesis": "native factors improve separate arm response models",
    },
    "to_hgb": {
        "family": "transformed_outcome",
        "base_learner": "hist_gradient_boosting",
        "complexity": 5,
        "hypothesis": "direct IPW pseudo-outcome learning captures CATE despite higher variance",
    },
    "dr_hgb": {
        "family": "dr_learner",
        "base_learner": "hist_gradient_boosting",
        "complexity": 7,
        "hypothesis": "orthogonal pseudo-outcomes reduce nuisance-model bias",
    },
    "dr_extratrees": {
        "family": "dr_learner",
        "base_learner": "extra_trees",
        "complexity": 7,
        "hypothesis": "bagged effect regression reduces nonlinear CATE variance",
    },
    "r_hgb": {
        "family": "r_learner",
        "base_learner": "hist_gradient_boosting",
        "complexity": 7,
        "hypothesis": "Robinson residualization isolates treatment heterogeneity",
    },
    "x_hgb": {
        "family": "x_learner",
        "base_learner": "hist_gradient_boosting",
        "complexity": 8,
        "hypothesis": "effect imputation benefits from the 75/25 treatment imbalance",
    },
}

QUICK_CANDIDATES = (
    "risk_logistic",
    "risk_hgb",
    "s_logistic",
    "s_hgb",
    "t_logistic",
    "dr_hgb",
    "r_hgb",
    "x_hgb",
)


def _mean_interval(values: pd.Series) -> tuple[float, float, float]:
    clean = values.dropna().astype(float)
    mean = float(clean.mean())
    if len(clean) < 2:
        return mean, math.nan, math.nan
    standard_error = float(clean.std(ddof=1) / math.sqrt(len(clean)))
    half_width = float(student_t.ppf(0.975, df=len(clean) - 1) * standard_error)
    return mean, mean - half_width, mean + half_width


def select_candidate(summary: pd.DataFrame, *, repeats: int) -> dict[str, Any]:
    """Apply predeclared stability gates and a one-standard-error complexity rule."""
    table = summary[summary["model"].ne("random")].copy()
    table["basic_gate"] = (
        table["qini_dr_mean"].gt(0)
        & table["qini_ipw_mean"].gt(0)
        & table["qini_dr_positive_rate"].ge(math.ceil(0.8 * repeats) / repeats)
        & table["dr_uplift_20_mean"].gt(0)
    )
    eligible = table[table["basic_gate"]]
    if eligible.empty:
        return {
            "development_champion": "no_candidate",
            "reason": "no model passed DR/IPW sign, repeat-stability, and uplift@20 gates",
            "one_standard_error_floor": None,
            "causal_replacement": "none",
        }

    best = eligible.sort_values("qini_dr_mean", ascending=False).iloc[0]
    one_se_floor = float(best["qini_dr_mean"] - best["qini_dr_se"])
    within_one_se = eligible[eligible["qini_dr_mean"].ge(one_se_floor)]
    champion = within_one_se.sort_values(
        ["complexity", "qini_dr_mean"], ascending=[True, False]
    ).iloc[0]

    causal = table[
        table["family"].ne("risk")
        & table["basic_gate"]
        & table["delta_vs_risk_ci95_low"].gt(0)
        & table["beats_risk_rate"].ge(0.8)
    ].sort_values("qini_dr_mean", ascending=False)
    return {
        "development_champion": str(champion["model"]),
        "mean_best_model": str(best["model"]),
        "one_standard_error_floor": one_se_floor,
        "selection_reason": "simplest model within one SE of best eligible mean Qini-DR",
        "causal_replacement": "none" if causal.empty else str(causal.iloc[0]["model"]),
        "causal_replacement_gate": (
            "paired Qini-DR delta lower 95% CI > 0 and wins at least 80% of repeats"
        ),
    }


def run_tournament(
    data_path: Path,
    output_dir: Path,
    *,
    repeats: int = 3,
    folds: int = 3,
    seed: int = SEED,
    profile: str = "full",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if repeats < 2:
        raise ValueError("At least two repeats are required for a stability estimate")
    if profile not in {"quick", "full"}:
        raise ValueError("profile must be 'quick' or 'full'")
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = load_orange(data_path)
    manifest = make_locked_split(frame, seed=seed).set_index("row_id")
    development = manifest["split"].reindex(frame.index).eq("development").to_numpy()
    features = frame.loc[development, FEATURE_COLUMNS].reset_index(drop=True)
    treatment = frame.loc[development, "t"].to_numpy(dtype=int)
    outcome = frame.loc[development, "y"].to_numpy(dtype=int)
    ids = frame.index.to_numpy(dtype=str)[development]
    propensity = float(treatment.mean())
    candidate_names = list(CANDIDATES) if profile == "full" else list(QUICK_CANDIDATES)
    metric_records: list[dict[str, Any]] = []
    budget_records: list[dict[str, Any]] = []
    prediction_records: list[pd.DataFrame] = []

    for repeat in range(repeats):
        repeat_seed = seed + 100_000 * repeat
        p0, p1 = cross_fit_potential_outcomes(
            features,
            treatment,
            outcome,
            folds=folds,
            seed=repeat_seed,
            kind="logistic",
        )
        evaluator_ipw = ipw_scores(outcome, treatment, propensity)
        evaluator_dr = doubly_robust_scores(outcome, treatment, p0, p1, propensity)
        scores: dict[str, np.ndarray] = {"random": _random_scores(ids, repeat_seed)}
        runtimes = {"random": 0.0}
        for name in candidate_names:
            started = time.perf_counter()
            scores[name] = _oof_scores(
                name,
                features,
                treatment,
                outcome,
                propensity=propensity,
                folds=folds,
                seed=repeat_seed,
            )
            runtimes[name] = time.perf_counter() - started

        risk_at_20 = top_fraction_mask(scores["risk_logistic"], ids, 0.20)
        prediction_records.append(
            pd.DataFrame(
                {
                    "repeat": repeat,
                    "row_id": ids,
                    "treatment": treatment,
                    "outcome": outcome,
                    "evaluator_ipw": evaluator_ipw,
                    "evaluator_dr": evaluator_dr,
                    **{f"score_{name}": values for name, values in scores.items()},
                }
            )
        )
        for name, score in scores.items():
            dr_curve = curve_metrics(score, evaluator_dr)
            ipw_curve = curve_metrics(score, evaluator_ipw)
            selected_20 = top_fraction_mask(score, ids, 0.20)
            union = np.logical_or(selected_20, risk_at_20).sum()
            overlap = float(np.logical_and(selected_20, risk_at_20).sum() / union)
            metric_records.append(
                {
                    "repeat": repeat,
                    "seed": repeat_seed,
                    "model": name,
                    "family": CANDIDATES.get(name, {}).get("family", "random"),
                    "base_learner": CANDIDATES.get(name, {}).get("base_learner", "random"),
                    "complexity": CANDIDATES.get(name, {}).get("complexity", 0),
                    "qini_dr": dr_curve["qini"],
                    "auuc_dr": dr_curve["auuc"],
                    "qini_ipw": ipw_curve["qini"],
                    "score_std": float(np.std(score)),
                    "unique_score_fraction": float(len(np.unique(score)) / len(score)),
                    "policy_jaccard_vs_risk_at_20": overlap,
                    "runtime_seconds": runtimes[name],
                }
            )
            budget = budget_table(
                score,
                ids,
                outcome,
                treatment,
                evaluator_ipw,
                evaluator_dr,
                budgets=BUDGETS,
            )
            budget.insert(0, "model", name)
            budget.insert(0, "repeat", repeat)
            budget_records.extend(budget.to_dict("records"))

    raw = pd.DataFrame(metric_records)
    budgets = pd.DataFrame(budget_records)
    predictions = pd.concat(prediction_records, ignore_index=True)
    raw["rank_qini_dr"] = raw.groupby("repeat")["qini_dr"].rank(ascending=False, method="min")
    reference = raw.loc[raw["model"].eq("risk_logistic"), ["repeat", "qini_dr"]].rename(
        columns={"qini_dr": "risk_qini_dr"}
    )
    raw = raw.merge(reference, on="repeat", how="left")
    raw["delta_vs_risk"] = raw["qini_dr"] - raw["risk_qini_dr"]
    raw.to_csv(output_dir / "tournament_raw.csv", index=False)
    budgets.to_csv(output_dir / "tournament_budgets.csv", index=False)
    predictions.to_csv(output_dir / "tournament_oof_predictions.csv", index=False)

    budget_20 = budgets[budgets["budget_fraction"].eq(0.20)]
    rows: list[dict[str, Any]] = []
    for name, part in raw.groupby("model", sort=False):
        qini_mean, qini_low, qini_high = _mean_interval(part["qini_dr"])
        delta_mean, delta_low, delta_high = _mean_interval(part["delta_vs_risk"])
        at_20 = budget_20[budget_20["model"].eq(name)]
        metadata = CANDIDATES.get(name, {})
        rows.append(
            {
                "model": name,
                "family": metadata.get("family", "random"),
                "base_learner": metadata.get("base_learner", "random"),
                "complexity": metadata.get("complexity", 0),
                "hypothesis": metadata.get("hypothesis", "negative control"),
                "qini_dr_mean": qini_mean,
                "qini_dr_std": float(part["qini_dr"].std(ddof=1)),
                "qini_dr_se": float(part["qini_dr"].std(ddof=1) / math.sqrt(repeats)),
                "qini_dr_ci95_low": qini_low,
                "qini_dr_ci95_high": qini_high,
                "qini_ipw_mean": float(part["qini_ipw"].mean()),
                "qini_ipw_std": float(part["qini_ipw"].std(ddof=1)),
                "qini_dr_positive_rate": float(part["qini_dr"].gt(0).mean()),
                "mean_rank": float(part["rank_qini_dr"].mean()),
                "delta_vs_risk_mean": delta_mean,
                "delta_vs_risk_ci95_low": delta_low,
                "delta_vs_risk_ci95_high": delta_high,
                "beats_risk_rate": float(part["delta_vs_risk"].gt(0).mean()),
                "dr_uplift_20_mean": float(at_20["dr_uplift"].mean()),
                "dr_uplift_20_std": float(at_20["dr_uplift"].std(ddof=1)),
                "ipw_uplift_20_mean": float(at_20["ipw_uplift"].mean()),
                "policy_jaccard_vs_risk_at_20_mean": float(
                    part["policy_jaccard_vs_risk_at_20"].mean()
                ),
                "runtime_seconds_mean": float(part["runtime_seconds"].mean()),
            }
        )
    summary = pd.DataFrame(rows).sort_values("qini_dr_mean", ascending=False)
    decision = select_candidate(summary, repeats=repeats)
    summary["basic_gate"] = (
        summary["qini_dr_mean"].gt(0)
        & summary["qini_ipw_mean"].gt(0)
        & summary["qini_dr_positive_rate"].ge(math.ceil(0.8 * repeats) / repeats)
        & summary["dr_uplift_20_mean"].gt(0)
    )
    summary.to_csv(output_dir / "tournament_summary.csv", index=False)
    decision.update(
        {
            "profile": profile,
            "candidate_count": len(candidate_names),
            "repeats": repeats,
            "folds": folds,
            "development_rows": len(features),
            "test_rows_touched": 0,
            "primary_metric": "mean normalized Qini using a common cross-fitted DR evaluator",
            "sensitivity_metric": "mean normalized Qini using known-propensity IPW",
            "operational_capacity": 0.20,
            "gate_positive_repeat_rate": math.ceil(0.8 * repeats) / repeats,
            "promotion_status": "future challenger only; requires a new campaign/holdout",
        }
    )
    (output_dir / "tournament_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    return summary, decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/churn-uplift-mlg.arff"))
    parser.add_argument("--output", type=Path, default=Path("reports/uplift/tournament"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--profile", choices=("quick", "full"), default="full")
    args = parser.parse_args()
    summary, decision = run_tournament(
        args.data,
        args.output,
        repeats=args.repeats,
        folds=args.folds,
        seed=args.seed,
        profile=args.profile,
    )
    print(summary.to_string(index=False))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
