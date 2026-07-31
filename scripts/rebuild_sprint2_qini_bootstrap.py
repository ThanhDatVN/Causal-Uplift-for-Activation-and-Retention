"""Rebuild Sprint 2 paired-Qini inference from frozen confirmation predictions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation import paired_qini_bootstrap_matrix
from src.paths import OUTPUT_DIR


PAIRS = [
    ("T-LocalExact", "X-Renormalized"),
    ("X-Calibrated", "X-Renormalized"),
    ("X-Renormalized", "Response"),
    ("Response", "X-Calibrated"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions",
        type=Path,
        default=OUTPUT_DIR / "sprint2" / "confirmation_predictions.npz",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "sprint2" / "paired_qini_bootstrap.csv",
    )
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    frozen = np.load(args.predictions)
    scores = {
        "Response": frozen["response_score"],
        "X-Renormalized": frozen["x_renormalized"],
        "X-Calibrated": frozen["x_calibrated"],
        "T-LocalExact": frozen["t_local_exact"],
    }
    result = paired_qini_bootstrap_matrix(
        scores,
        frozen["conversion"],
        frozen["treatment"],
        n_boot=args.n_boot,
        seed=args.seed,
    )
    names = result["model_names"]
    rows = []
    for model_a, model_b in PAIRS:
        index_a = names.index(model_a)
        index_b = names.index(model_b)
        differences = result["draws"][:, index_a] - result["draws"][:, index_b]
        rows.append(
            {
                "model_a": model_a,
                "model_b": model_b,
                "metric": "normalized_qini",
                "n_boot": args.n_boot,
                "observed_difference": (
                    result["observed"][index_a] - result["observed"][index_b]
                ),
                "ci_low": np.quantile(differences, 0.025),
                "ci_high": np.quantile(differences, 0.975),
                "score_a_ci_low": result["ci_low"][index_a],
                "score_a_ci_high": result["ci_high"][index_a],
                "score_b_ci_low": result["ci_low"][index_b],
                "score_b_ci_high": result["ci_high"][index_b],
                "probability_difference_positive": float(
                    np.mean(differences > 0)
                ),
                "n_valid_bootstrap": result["n_valid_bootstrap"],
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"[write] {args.output} ({result['n_valid_bootstrap']} valid draws)")


if __name__ == "__main__":
    main()
