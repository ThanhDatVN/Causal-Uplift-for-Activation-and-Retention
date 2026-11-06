"""Repeated development-only stability experiment for uplift policy rankings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from telco_churn.orange_benchmark import (
    SEED,
    _oof_scores,
    _random_scores,
    make_locked_split,
)
from telco_churn.orange_data import FEATURE_COLUMNS, load_orange
from telco_churn.uplift import (
    budget_table,
    cross_fit_potential_outcomes,
    curve_metrics,
    doubly_robust_scores,
    ipw_scores,
)

STABILITY_CANDIDATES = (
    "risk_logistic",
    "t_logistic",
    "s_hgb",
    "dr_hgb",
    "x_hgb",
)


def run_stability(
    data_path: Path,
    output_dir: Path,
    *,
    repeats: int = 5,
    folds: int = 3,
    seed: int = SEED,
) -> pd.DataFrame:
    if repeats < 2:
        raise ValueError("Use at least two repeats to estimate seed variability")
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = load_orange(data_path)
    manifest = make_locked_split(frame, seed=seed).set_index("row_id")
    development = manifest["split"].reindex(frame.index).eq("development").to_numpy()
    features = frame.loc[development, FEATURE_COLUMNS].reset_index(drop=True)
    treatment = frame.loc[development, "t"].to_numpy(dtype=int)
    outcome = frame.loc[development, "y"].to_numpy(dtype=int)
    ids = frame.index.to_numpy(dtype=str)[development]
    propensity = float(treatment.mean())
    records = []

    for repeat in range(repeats):
        repeat_seed = seed + 10_000 * repeat
        p0, p1 = cross_fit_potential_outcomes(
            features,
            treatment,
            outcome,
            folds=folds,
            seed=repeat_seed,
            kind="logistic",
        )
        ipw = ipw_scores(outcome, treatment, propensity)
        dr = doubly_robust_scores(outcome, treatment, p0, p1, propensity)
        scores = {"random": _random_scores(ids, repeat_seed)}
        for model in STABILITY_CANDIDATES:
            scores[model] = _oof_scores(
                model,
                features,
                treatment,
                outcome,
                propensity=propensity,
                folds=folds,
                seed=repeat_seed,
            )
        repeat_records = []
        for model, score in scores.items():
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
            repeat_records.append(
                {
                    "repeat": repeat,
                    "seed": repeat_seed,
                    "model": model,
                    "qini_dr": dr_curve["qini"],
                    "qini_ipw": ipw_curve["qini"],
                    "dr_uplift_at_20pct": at_20["dr_uplift"],
                    "ipw_uplift_at_20pct": at_20["ipw_uplift"],
                }
            )
        repeat_frame = pd.DataFrame(repeat_records)
        repeat_frame["qini_dr_rank"] = repeat_frame["qini_dr"].rank(ascending=False, method="min")
        records.extend(repeat_frame.to_dict("records"))

    raw = pd.DataFrame(records)
    raw.to_csv(output_dir / "repeated_oof_raw.csv", index=False)
    risk_reference = raw.loc[raw["model"].eq("risk_logistic"), ["repeat", "qini_dr"]].rename(
        columns={"qini_dr": "risk_logistic_qini_dr"}
    )
    deltas = raw.merge(risk_reference, on="repeat", how="left")
    deltas["qini_dr_delta_vs_risk_logistic"] = deltas["qini_dr"] - deltas["risk_logistic_qini_dr"]
    summary = (
        deltas.groupby("model", sort=False)
        .agg(
            qini_dr_mean=("qini_dr", "mean"),
            qini_dr_std=("qini_dr", "std"),
            qini_ipw_mean=("qini_ipw", "mean"),
            qini_ipw_std=("qini_ipw", "std"),
            qini_dr_positive_rate=("qini_dr", lambda values: float((values > 0).mean())),
            mean_rank=("qini_dr_rank", "mean"),
            uplift_at_20_mean=("dr_uplift_at_20pct", "mean"),
            uplift_at_20_std=("dr_uplift_at_20pct", "std"),
            delta_vs_risk_mean=("qini_dr_delta_vs_risk_logistic", "mean"),
            beats_risk_rate=(
                "qini_dr_delta_vs_risk_logistic",
                lambda values: float((values > 0).mean()),
            ),
        )
        .reset_index()
        .sort_values("qini_dr_mean", ascending=False)
    )
    summary.to_csv(output_dir / "repeated_oof_summary.csv", index=False)
    result = {
        "repeats": repeats,
        "folds": folds,
        "test_rows_touched": 0,
        "best_mean_qini_model": str(summary.iloc[0]["model"]),
        "best_mean_qini": float(summary.iloc[0]["qini_dr_mean"]),
        "risk_logistic_mean_qini": float(
            summary.loc[summary["model"].eq("risk_logistic"), "qini_dr_mean"].iloc[0]
        ),
    }
    (output_dir / "stability_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/churn-uplift-mlg.arff"))
    parser.add_argument("--output", type=Path, default=Path("reports/uplift/stability"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    summary = run_stability(
        args.data,
        args.output,
        repeats=args.repeats,
        folds=args.folds,
        seed=args.seed,
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
