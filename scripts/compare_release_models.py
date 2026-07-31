"""Paired 500-bootstrap comparison cho toàn bộ 5 model release trong một pass."""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation import _weighted_qini_score, qini_score
from src.paths import OUTPUT_DIR

MODELS = ["Response", "S-Learner", "T-Learner", "X-Learner", "DR-Learner"]


def _slug(name: str) -> str:
    return name.lower().replace("-", "_")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    holdout = np.load(OUTPUT_DIR / "cate" / "holdout_test_yt.npz")
    y = holdout["Y"].astype("float64")
    t = holdout["T"].astype("float64")
    scores = {
        model: np.load(
            OUTPUT_DIR
            / "optimization"
            / "cate"
            / f"cate_{_slug(model)}_sprint1_release.npy"
        )
        for model in MODELS
    }
    orders = {
        model: np.argsort(score, kind="mergesort")[::-1]
        for model, score in scores.items()
    }
    perfect = y * t - y * (1 - t)
    perfect_order = np.argsort(perfect, kind="mergesort")[::-1]
    observed = {
        model: qini_score(y, t, score)
        for model, score in scores.items()
    }

    rng = np.random.default_rng(args.seed)
    bootstrap = {model: [] for model in MODELS}
    for iteration in range(args.n_boot):
        idx = rng.integers(0, len(y), size=len(y))
        weight = np.bincount(idx, minlength=len(y)).astype("float64", copy=False)
        for model in MODELS:
            bootstrap[model].append(
                _weighted_qini_score(
                    y,
                    t,
                    scores[model],
                    weight,
                    orders[model],
                    perfect_order,
                )
            )
        if (iteration + 1) % 100 == 0:
            print(f"[bootstrap] {iteration + 1}/{args.n_boot}", flush=True)

    matrix = pd.DataFrame(bootstrap)
    rows = []
    for model_a in MODELS:
        for model_b in MODELS:
            if MODELS.index(model_a) >= MODELS.index(model_b):
                continue
            difference = matrix[model_a] - matrix[model_b]
            rows.append(
                {
                    "model_a": model_a,
                    "model_b": model_b,
                    "observed_qini_a": observed[model_a],
                    "observed_qini_b": observed[model_b],
                    "observed_difference_a_minus_b": (
                        observed[model_a] - observed[model_b]
                    ),
                    "difference_ci_low": float(np.percentile(difference, 2.5)),
                    "difference_ci_high": float(np.percentile(difference, 97.5)),
                    "bootstrap_probability_a_greater_b": float(
                        np.mean(difference > 0)
                    ),
                    "n_boot": args.n_boot,
                }
            )
    sprint_dir = OUTPUT_DIR / "sprint1"
    matrix.to_csv(sprint_dir / "model_qini_bootstrap_draws_release.csv", index=False)
    comparison = pd.DataFrame(rows)
    comparison.to_csv(
        sprint_dir / "model_pairwise_bootstrap_release.csv",
        index=False,
    )
    print(
        comparison.loc[comparison["model_a"] == "Response"].to_string(index=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
