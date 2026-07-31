"""Tạo bảng policy/diagnostic từ 5 CATE score Sprint 1 đã freeze."""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import OUTPUT_DIR


MODELS = ["Response", "S-Learner", "T-Learner", "X-Learner", "DR-Learner"]


def _slug(name: str) -> str:
    return name.lower().replace("-", "_")


def _difference_stats(y: np.ndarray, t: np.ndarray) -> dict:
    treated = y[t == 1]
    control = y[t == 0]
    rate_t = float(treated.mean())
    rate_c = float(control.mean())
    difference = rate_t - rate_c
    standard_error = math.sqrt(
        rate_t * (1 - rate_t) / len(treated)
        + rate_c * (1 - rate_c) / len(control)
    )
    return {
        "n_treatment": int(len(treated)),
        "n_control": int(len(control)),
        "conversion_treatment": rate_t,
        "conversion_control": rate_c,
        "observed_uplift_rate": difference,
        "uplift_ci_low": difference - 1.96 * standard_error,
        "uplift_ci_high": difference + 1.96 * standard_error,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bins", type=int, default=10)
    args = parser.parse_args()

    holdout = np.load(OUTPUT_DIR / "cate" / "holdout_test_yt.npz")
    y = holdout["Y"].astype("float64")
    t = holdout["T"].astype("float64")
    sprint_dir = OUTPUT_DIR / "sprint1"
    sprint_dir.mkdir(parents=True, exist_ok=True)

    scores = {
        model: np.load(
            OUTPUT_DIR
            / "optimization"
            / "cate"
            / f"cate_{_slug(model)}_sprint1_release.npy"
        )
        for model in MODELS
    }

    rows = []
    diagnostics = []
    for model, score in scores.items():
        order = np.argsort(score, kind="mergesort")[::-1]
        chunks = np.array_split(order, args.bins)
        full = _difference_stats(y, t)
        full_incremental = full["observed_uplift_rate"] * len(y)
        for decile, chunk in enumerate(chunks, start=1):
            cumulative = np.concatenate(chunks[:decile])
            decile_stats = _difference_stats(y[chunk], t[chunk])
            cumulative_stats = _difference_stats(y[cumulative], t[cumulative])
            cumulative_incremental = (
                cumulative_stats["observed_uplift_rate"] * len(cumulative)
            )
            rows.append(
                {
                    "model": model,
                    "decile": decile,
                    "target_fraction": decile / args.bins,
                    "n_decile": len(chunk),
                    "mean_score_decile": float(np.mean(score[chunk])),
                    **{f"decile_{key}": value for key, value in decile_stats.items()},
                    "n_targeted_cumulative": len(cumulative),
                    "mean_score_cumulative": float(np.mean(score[cumulative])),
                    **{
                        f"cumulative_{key}": value
                        for key, value in cumulative_stats.items()
                    },
                    "estimated_incremental_conversions_cumulative": cumulative_incremental,
                    "incremental_conversions_ci_low": (
                        cumulative_stats["uplift_ci_low"] * len(cumulative)
                    ),
                    "incremental_conversions_ci_high": (
                        cumulative_stats["uplift_ci_high"] * len(cumulative)
                    ),
                    "share_of_full_incremental_estimate": (
                        cumulative_incremental / full_incremental
                        if full_incremental != 0
                        else np.nan
                    ),
                }
            )
        diagnostics.append(
            {
                "model": model,
                "score_mean": float(np.mean(score)),
                "score_std": float(np.std(score)),
                "score_min": float(np.min(score)),
                "score_max": float(np.max(score)),
                "negative_score_fraction": float(np.mean(score < 0)),
                "near_zero_fraction_abs_lt_1e_4": float(np.mean(np.abs(score) < 1e-4)),
                "full_holdout_uplift_rate": full["observed_uplift_rate"],
                "full_holdout_incremental_estimate": full_incremental,
            }
        )

    policy = pd.DataFrame(rows)
    diagnostics_frame = pd.DataFrame(diagnostics)
    correlation = pd.DataFrame(scores).corr(method="spearman")
    policy.to_csv(sprint_dir / "policy_deciles_release.csv", index=False)
    diagnostics_frame.to_csv(sprint_dir / "score_diagnostics_release.csv", index=False)
    correlation.to_csv(sprint_dir / "score_spearman_release.csv")

    top_decile = policy.loc[policy["decile"] == 1].copy()
    summary = {
        row["model"]: {
            "top_10_incremental_conversion_estimate": float(
                row["estimated_incremental_conversions_cumulative"]
            ),
            "top_10_incremental_ci": [
                float(row["incremental_conversions_ci_low"]),
                float(row["incremental_conversions_ci_high"]),
            ],
            "share_of_full_incremental_estimate": float(
                row["share_of_full_incremental_estimate"]
            ),
        }
        for row in top_decile.to_dict(orient="records")
    }
    (sprint_dir / "policy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(top_decile[
        [
            "model",
            "estimated_incremental_conversions_cumulative",
            "incremental_conversions_ci_low",
            "incremental_conversions_ci_high",
            "share_of_full_incremental_estimate",
        ]
    ].to_string(index=False), flush=True)
    print(f"[write] {sprint_dir}", flush=True)


if __name__ == "__main__":
    main()
