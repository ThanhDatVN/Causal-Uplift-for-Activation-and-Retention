"""Ablate nuisance, base learner, meta learner, and policy-capacity components."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss

from telco_churn.model_tournament import CANDIDATES
from telco_churn.orange_benchmark import SEED, make_locked_split
from telco_churn.orange_data import FEATURE_COLUMNS, load_orange
from telco_churn.uplift import (
    cross_fit_potential_outcomes,
    curve_metrics,
    doubly_robust_scores,
    ipw_scores,
)

EVALUATOR_KINDS = ("logistic", "hgb", "catboost")


def _component_winners(robustness: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "risk base learner": [name for name in CANDIDATES if name.startswith("risk_")],
        "S-learner base learner": ["s_logistic", "s_hgb"],
        "T-learner base learner": ["t_logistic", "t_hgb", "t_catboost"],
        "DR second-stage learner": ["dr_hgb", "dr_extratrees"],
        "causal meta-learner": [
            "s_logistic",
            "s_hgb",
            "t_logistic",
            "t_hgb",
            "t_catboost",
            "to_hgb",
            "dr_hgb",
            "dr_extratrees",
            "r_hgb",
            "x_hgb",
        ],
    }
    rows: list[dict[str, Any]] = []
    for component, names in groups.items():
        available = robustness[robustness["model"].isin(names)].copy()
        if available.empty:
            continue
        ordered = available.sort_values(
            ["minimum_evaluator_qini", "qini_all_mean"], ascending=False
        )
        best = ordered.iloc[0]
        rows.append(
            {
                "component": component,
                "winner": best["model"],
                "selection_metric": "maximum worst-evaluator mean Qini-DR",
                "minimum_evaluator_qini": best["minimum_evaluator_qini"],
                "qini_all_mean": best["qini_all_mean"],
                "positive_across_all_evaluators": best["positive_across_all_evaluators"],
                "decision": (
                    "retain for confirmation"
                    if best["positive_across_all_evaluators"]
                    else "no robust winner"
                ),
            }
        )
    return pd.DataFrame(rows)


def run_component_ablation(
    data_path: Path,
    tournament_dir: Path,
    output_dir: Path,
    *,
    folds: int = 3,
    seed: int = SEED,
    evaluator_kinds: tuple[str, ...] = EVALUATOR_KINDS,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = tournament_dir / "tournament_oof_predictions.csv"
    if not predictions_path.exists():
        raise FileNotFoundError(f"Run the model tournament first: {predictions_path}")

    frame = load_orange(data_path)
    manifest = make_locked_split(frame, seed=seed).set_index("row_id")
    development = manifest["split"].reindex(frame.index).eq("development").to_numpy()
    features = frame.loc[development, FEATURE_COLUMNS].reset_index(drop=True)
    treatment = frame.loc[development, "t"].to_numpy(dtype=int)
    outcome = frame.loc[development, "y"].to_numpy(dtype=int)
    ids = frame.index.to_numpy(dtype=str)[development]
    propensity = float(treatment.mean())
    predictions = pd.read_csv(predictions_path, dtype={"row_id": str})
    score_columns = [column for column in predictions if column.startswith("score_")]
    model_names = [column.removeprefix("score_") for column in score_columns]
    repeats = sorted(predictions["repeat"].unique())
    metric_rows: list[dict[str, Any]] = []
    nuisance_rows: list[dict[str, Any]] = []

    for repeat in repeats:
        repeat_predictions = predictions[predictions["repeat"].eq(repeat)].reset_index(drop=True)
        if not np.array_equal(repeat_predictions["row_id"].to_numpy(), ids):
            raise ValueError("Tournament row IDs do not match the frozen development split")
        repeat_seed = seed + 100_000 * int(repeat)
        evaluator_ipw = ipw_scores(outcome, treatment, propensity)
        for kind in evaluator_kinds:
            p0, p1 = cross_fit_potential_outcomes(
                features,
                treatment,
                outcome,
                folds=folds,
                seed=repeat_seed,
                kind=kind,
            )
            factual = np.where(treatment == 1, p1, p0)
            evaluator_dr = doubly_robust_scores(outcome, treatment, p0, p1, propensity)
            nuisance_rows.append(
                {
                    "repeat": repeat,
                    "nuisance_model": kind,
                    "factual_average_precision": average_precision_score(outcome, factual),
                    "factual_brier": brier_score_loss(outcome, factual),
                    "factual_log_loss": log_loss(outcome, factual),
                    "dr_score_std": float(np.std(evaluator_dr)),
                    "dr_score_p01": float(np.quantile(evaluator_dr, 0.01)),
                    "dr_score_p99": float(np.quantile(evaluator_dr, 0.99)),
                }
            )
            for model, score_column in zip(model_names, score_columns, strict=True):
                score = repeat_predictions[score_column].to_numpy(dtype=float)
                dr_curve = curve_metrics(score, evaluator_dr)
                ipw_curve = curve_metrics(score, evaluator_ipw)
                metric_rows.append(
                    {
                        "repeat": repeat,
                        "model": model,
                        "nuisance_model": kind,
                        "qini_dr": dr_curve["qini"],
                        "qini_ipw": ipw_curve["qini"],
                    }
                )

    raw = pd.DataFrame(metric_rows)
    nuisance_raw = pd.DataFrame(nuisance_rows)
    raw.to_csv(output_dir / "evaluator_sensitivity_raw.csv", index=False)
    nuisance_raw.to_csv(output_dir / "nuisance_diagnostics_raw.csv", index=False)
    nuisance_summary = (
        nuisance_raw.groupby("nuisance_model", as_index=False)
        .agg(
            factual_ap_mean=("factual_average_precision", "mean"),
            factual_ap_std=("factual_average_precision", "std"),
            factual_brier_mean=("factual_brier", "mean"),
            factual_brier_std=("factual_brier", "std"),
            factual_log_loss_mean=("factual_log_loss", "mean"),
            dr_score_std_mean=("dr_score_std", "mean"),
        )
        .sort_values("factual_brier_mean")
    )
    nuisance_summary.to_csv(output_dir / "nuisance_diagnostics_summary.csv", index=False)

    by_evaluator = raw.groupby(["model", "nuisance_model"], as_index=False).agg(
        qini_mean=("qini_dr", "mean"), qini_std=("qini_dr", "std")
    )
    by_evaluator.to_csv(output_dir / "qini_by_evaluator.csv", index=False)
    robustness = (
        by_evaluator.groupby("model", as_index=False)
        .agg(
            qini_all_mean=("qini_mean", "mean"),
            qini_between_evaluator_std=("qini_mean", "std"),
            minimum_evaluator_qini=("qini_mean", "min"),
            maximum_evaluator_qini=("qini_mean", "max"),
            positive_evaluator_count=("qini_mean", lambda values: int((values > 0).sum())),
        )
        .sort_values("minimum_evaluator_qini", ascending=False)
    )
    robustness["positive_across_all_evaluators"] = robustness["positive_evaluator_count"].eq(
        len(evaluator_kinds)
    )
    robustness.to_csv(output_dir / "model_evaluator_robustness.csv", index=False)
    winners = _component_winners(robustness)
    winners.to_csv(output_dir / "component_winners.csv", index=False)

    best_nuisance = nuisance_summary.iloc[0]
    decision = {
        "development_rows": len(features),
        "test_rows_touched": 0,
        "repeats": len(repeats),
        "folds": folds,
        "nuisance_models": list(evaluator_kinds),
        "nuisance_selection": {
            "criterion": "lowest repeated OOF factual Brier; AP and DR-score variance are supporting",
            "winner": str(best_nuisance["nuisance_model"]),
            "factual_brier_mean": float(best_nuisance["factual_brier_mean"]),
            "factual_ap_mean": float(best_nuisance["factual_ap_mean"]),
        },
        "policy_robustness_gate": "positive mean Qini under every preregistered DR nuisance evaluator",
        "component_winners": winners.to_dict("records"),
        "warning": (
            "evaluator sensitivity is a robustness audit, not permission to choose the evaluator "
            "that makes a preferred policy look best"
        ),
    }
    (output_dir / "component_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/churn-uplift-mlg.arff"))
    parser.add_argument("--tournament", type=Path, default=Path("reports/uplift/tournament"))
    parser.add_argument("--output", type=Path, default=Path("reports/uplift/component_ablation"))
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use Logistic/HGB nuisance checks and skip the slower CatBoost evaluator",
    )
    args = parser.parse_args()
    decision = run_component_ablation(
        args.data,
        args.tournament,
        args.output,
        folds=args.folds,
        seed=args.seed,
        evaluator_kinds=("logistic", "hgb") if args.quick else EVALUATOR_KINDS,
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
