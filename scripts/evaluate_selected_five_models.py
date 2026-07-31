"""Refit các config đã chọn bằng multi-seed validation và chấm final holdout.

Script không chạy lại tuning. Dùng khi validation artifacts đã tồn tại:

    python scripts/evaluate_selected_five_models.py \
      --selected output/optimization/selected_configs_frac_0p5_vseeds_43-44-45_shortlist.json \
      --frac 0.50 --n-boot 500
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.tune_five_models import CANDIDATES, _fit_and_score
from src.data import load_criteo_full, stratified_sample, train_test_holdout, xty
from src.evaluation import bootstrap_ci, paired_bootstrap_difference_ci
from src.paths import OUTPUT_DIR


def _find_config(model_name: str, selected: dict) -> dict:
    selected_name = selected[model_name]["name"]
    return next(
        config
        for config in CANDIDATES[model_name]
        if config["name"] == selected_name
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, required=True)
    parser.add_argument("--frac", type=float, default=0.50)
    parser.add_argument("--test-size", type=float, default=0.30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-boot", type=int, default=500)
    args = parser.parse_args()

    selected = json.loads(args.selected.read_text(encoding="utf-8"))
    started = time.time()
    df = stratified_sample(
        load_criteo_full(dtype_f32=True),
        frac=args.frac,
        seed=args.seed,
    )
    train_df, test_df = train_test_holdout(
        df,
        test_size=args.test_size,
        seed=args.seed,
    )
    _, T_test, Y_test = xty(test_df)
    print(
        f"[split] train={len(train_df):,} final_test={len(test_df):,} "
        f"n_boot={args.n_boot}",
        flush=True,
    )

    rows = []
    predictions = {}
    optimization_dir = OUTPUT_DIR / "optimization"
    cate_dir = optimization_dir / "cate"
    cate_dir.mkdir(parents=True, exist_ok=True)

    for model_name in CANDIDATES:
        config = _find_config(model_name, selected)
        winner_row, winner_score = _fit_and_score(
            model_name,
            config,
            train_df,
            test_df,
            args.seed,
        )
        baseline_config = CANDIDATES[model_name][0]
        if config["name"] == "baseline":
            baseline_score = winner_score
            baseline_qini = winner_row["qini_score"]
            qini_low, qini_high = bootstrap_ci(
                Y_test,
                T_test,
                winner_score,
                n_boot=args.n_boot,
                seed=args.seed,
            )
            difference = {
                "ci_low": 0.0,
                "ci_high": 0.0,
                "probability_difference_positive": 0.0,
            }
        else:
            baseline_row, baseline_score = _fit_and_score(
                model_name,
                baseline_config,
                train_df,
                test_df,
                args.seed,
            )
            baseline_qini = baseline_row["qini_score"]
            difference = paired_bootstrap_difference_ci(
                winner_score,
                baseline_score,
                Y_test,
                T_test,
                n_boot=args.n_boot,
                seed=args.seed,
            )
            qini_low = difference["score_a_ci_low"]
            qini_high = difference["score_a_ci_high"]

        winner_row.update(
            {
                "qini_ci_low": qini_low,
                "qini_ci_high": qini_high,
                "baseline_qini": baseline_qini,
                "qini_delta_vs_baseline": winner_row["qini_score"] - baseline_qini,
                "qini_delta_ci_low": difference["ci_low"],
                "qini_delta_ci_high": difference["ci_high"],
                "bootstrap_probability_delta_positive": difference[
                    "probability_difference_positive"
                ],
                "sample_frac": args.frac,
                "n_test": len(test_df),
                "n_boot": args.n_boot,
            }
        )
        rows.append(winner_row)
        predictions[model_name] = winner_score
        slug = model_name.lower().replace("-", "_")
        np.save(cate_dir / f"cate_{slug}_sprint1_release.npy", winner_score)
        print(
            f"[final] {model_name:10s} candidate={config['name']:28s} "
            f"qini={winner_row['qini_score']:.5f} "
            f"CI=[{qini_low:.5f},{qini_high:.5f}] "
            f"delta={winner_row['qini_delta_vs_baseline']:+.5f} "
            f"delta_CI=[{difference['ci_low']:.5f},{difference['ci_high']:.5f}]",
            flush=True,
        )

    results = pd.DataFrame(rows).sort_values("qini_score", ascending=False)
    output_path = optimization_dir / f"final_test_results_{args.selected.stem}.csv"
    results.to_csv(output_path, index=False)
    results.to_csv(OUTPUT_DIR / "qini_comparison_sprint1.csv", index=False)
    print(f"[write] {output_path}", flush=True)
    print(f"[done] total={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
