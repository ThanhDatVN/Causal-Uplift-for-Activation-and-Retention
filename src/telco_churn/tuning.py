"""Development-only regularization/feature ablation for the stable risk policy baseline."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from telco_churn.orange_benchmark import SEED, make_locked_split
from telco_churn.orange_data import (
    EXPECTED_CATEGORICAL,
    EXPECTED_NUMERIC,
    FEATURE_COLUMNS,
    load_orange,
)
from telco_churn.uplift import (
    _preprocessor,
    budget_table,
    cross_fit_potential_outcomes,
    curve_metrics,
    doubly_robust_scores,
    ipw_scores,
)

C_VALUES = (0.01, 0.03, 0.10, 0.30, 1.0, 3.0)


def feature_sets() -> dict[str, tuple[str, ...]]:
    return {
        "factors_only": EXPECTED_CATEGORICAL,
        "pc20_plus_factors": EXPECTED_NUMERIC[:20] + EXPECTED_CATEGORICAL,
        "pc40_plus_factors": EXPECTED_NUMERIC[:40] + EXPECTED_CATEGORICAL,
        "all_178": FEATURE_COLUMNS,
    }


def _risk_logistic_oof(
    features: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    c_value: float,
    folds: int,
    seed: int,
) -> np.ndarray:
    joint = treatment * 2 + outcome
    score = np.zeros(len(features), dtype=float)
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train, valid in splitter.split(features, joint):
        control_train = treatment[train] == 0
        train_positions = train[control_train]
        model = Pipeline(
            [
                ("preprocess", _preprocessor(features, dense=False)),
                (
                    "model",
                    LogisticRegression(
                        C=c_value,
                        max_iter=2_000,
                        solver="liblinear",
                        random_state=seed,
                    ),
                ),
            ]
        ).fit(features.iloc[train_positions], outcome[train_positions])
        score[valid] = model.predict_proba(features.iloc[valid])[:, 1]
    return score


def run_tuning(
    data_path: Path,
    output_dir: Path,
    *,
    repeats: int = 3,
    folds: int = 3,
    seed: int = SEED,
) -> tuple[pd.DataFrame, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = load_orange(data_path)
    manifest = make_locked_split(frame, seed=seed).set_index("row_id")
    development = manifest["split"].reindex(frame.index).eq("development").to_numpy()
    full_features = frame.loc[development, FEATURE_COLUMNS].reset_index(drop=True)
    treatment = frame.loc[development, "t"].to_numpy(dtype=int)
    outcome = frame.loc[development, "y"].to_numpy(dtype=int)
    ids = frame.index.to_numpy(dtype=str)[development]
    propensity = float(treatment.mean())
    records = []

    for repeat in range(repeats):
        repeat_seed = seed + 50_000 * repeat
        p0, p1 = cross_fit_potential_outcomes(
            full_features,
            treatment,
            outcome,
            folds=folds,
            seed=repeat_seed,
            kind="logistic",
        )
        dr = doubly_robust_scores(outcome, treatment, p0, p1, propensity)
        ipw = ipw_scores(outcome, treatment, propensity)
        for set_name, columns in feature_sets().items():
            features = full_features.loc[:, columns]
            for c_value in C_VALUES:
                score = _risk_logistic_oof(
                    features,
                    treatment,
                    outcome,
                    c_value=c_value,
                    folds=folds,
                    seed=repeat_seed,
                )
                dr_curve = curve_metrics(score, dr)
                ipw_curve = curve_metrics(score, ipw)
                at_20 = budget_table(
                    score,
                    ids,
                    outcome,
                    treatment,
                    ipw,
                    dr,
                    budgets=(0.20,),
                ).iloc[0]
                records.append(
                    {
                        "repeat": repeat,
                        "seed": repeat_seed,
                        "feature_set": set_name,
                        "feature_count": len(columns),
                        "C": c_value,
                        "qini_dr": dr_curve["qini"],
                        "qini_ipw": ipw_curve["qini"],
                        "dr_uplift_at_20pct": at_20["dr_uplift"],
                    }
                )

    raw = pd.DataFrame(records)
    raw.to_csv(output_dir / "risk_logistic_tuning_raw.csv", index=False)
    summary = (
        raw.groupby(["feature_set", "feature_count", "C"], as_index=False)
        .agg(
            qini_dr_mean=("qini_dr", "mean"),
            qini_dr_std=("qini_dr", "std"),
            qini_ipw_mean=("qini_ipw", "mean"),
            qini_ipw_std=("qini_ipw", "std"),
            uplift_at_20_mean=("dr_uplift_at_20pct", "mean"),
            uplift_at_20_std=("dr_uplift_at_20pct", "std"),
        )
        .sort_values("qini_dr_mean", ascending=False)
    )
    summary.to_csv(output_dir / "risk_logistic_tuning_summary.csv", index=False)

    best = summary.iloc[0]
    best_standard_error = float(best["qini_dr_std"] / math.sqrt(repeats))
    one_se_floor = float(best["qini_dr_mean"] - best_standard_error)
    eligible = summary[summary["qini_dr_mean"].ge(one_se_floor)].copy()
    # Within one standard error, prefer fewer inputs, then stronger regularization.
    recommended = eligible.sort_values(
        ["feature_count", "C", "qini_dr_mean"], ascending=[True, True, False]
    ).iloc[0]
    decision = {
        "selection_scope": "development only; do not reuse the already-opened holdout",
        "repeats": repeats,
        "folds": folds,
        "configs": len(summary),
        "best_mean_config": {
            "feature_set": str(best["feature_set"]),
            "C": float(best["C"]),
            "qini_dr_mean": float(best["qini_dr_mean"]),
            "qini_dr_std": float(best["qini_dr_std"]),
        },
        "one_standard_error_floor": one_se_floor,
        "recommended_future_challenger": {
            "feature_set": str(recommended["feature_set"]),
            "feature_count": int(recommended["feature_count"]),
            "C": float(recommended["C"]),
            "qini_dr_mean": float(recommended["qini_dr_mean"]),
            "qini_dr_std": float(recommended["qini_dr_std"]),
        },
        "promotion_status": "requires a new future campaign/holdout",
        "test_rows_touched": 0,
    }
    (output_dir / "tuning_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    return summary, decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/churn-uplift-mlg.arff"))
    parser.add_argument("--output", type=Path, default=Path("reports/uplift/tuning"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    summary, decision = run_tuning(
        args.data,
        args.output,
        repeats=args.repeats,
        folds=args.folds,
        seed=args.seed,
    )
    print(summary.head(12).to_string(index=False))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
