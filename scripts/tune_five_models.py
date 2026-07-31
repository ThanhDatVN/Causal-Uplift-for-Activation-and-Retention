"""Tune 5 model hiện có mà không dùng final holdout để chọn cấu hình.

Protocol:
1. Tạo final holdout 30% giống pipeline baseline.
2. Chỉ tách phần train còn lại thành fit/validation ở nhiều seed.
3. Chọn cấu hình bằng median Qini và số seed thắng baseline; AUUC,
   transformed-outcome MSE và EUCE là guard.
4. Tuỳ chọn ``--evaluate-test``: refit winner trên toàn bộ train rồi chấm
   final holdout đúng 1 lần cho run đã pre-specify.

Ví dụ:
    .venv/Scripts/python.exe scripts/tune_five_models.py --frac 0.10
    .venv/Scripts/python.exe scripts/tune_five_models.py --frac 0.50 --evaluate-test
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Windows terminals can default to cp1252, which cannot render the Vietnamese CLI
# descriptions. Keep ``--help`` usable without requiring callers to set PYTHONUTF8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.baselines import (
    fit_dr_learner,
    fit_response_baseline,
    fit_s_learner,
    fit_t_learner,
    fit_x_learner,
)
from src.data import (
    load_criteo_full,
    rare_outcome_undersample,
    stratified_sample,
    train_test_holdout,
    train_validation_split,
    xty,
)
from src.evaluation import (
    auuc_score,
    bootstrap_ci,
    paired_bootstrap_difference_ci,
    qini_score,
    transformed_outcome_mse,
    uplift_calibration_error,
)
from src.paths import OUTPUT_DIR


BASE_PARAMS = {}
REGULARIZED_PARAMS = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 1000,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "colsample_bytree": 0.9,
}
SMOOTH_FINAL_PARAMS = {
    **REGULARIZED_PARAMS,
    "min_child_samples": 2500,
    "reg_lambda": 10.0,
}


CANDIDATES = {
    "Response": [
        {"name": "baseline", "params": BASE_PARAMS},
        {"name": "regularized", "params": REGULARIZED_PARAMS},
        {"name": "under25_regularized", "params": REGULARIZED_PARAMS, "under": 25.0},
    ],
    "S-Learner": [
        {"name": "baseline", "outcome": "regressor", "params": BASE_PARAMS},
        {"name": "regularized_regression", "outcome": "regressor", "params": REGULARIZED_PARAMS},
        {"name": "regularized_probability", "outcome": "classifier", "params": REGULARIZED_PARAMS},
        {
            "name": "under25_probability",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "under": 25.0,
        },
    ],
    "T-Learner": [
        {"name": "baseline", "outcome": "regressor", "params": BASE_PARAMS},
        {"name": "regularized_regression", "outcome": "regressor", "params": REGULARIZED_PARAMS},
        {"name": "regularized_probability", "outcome": "classifier", "params": REGULARIZED_PARAMS},
        {
            "name": "under7_probability",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "under": 7.0,
        },
        {
            "name": "under25_probability",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "under": 25.0,
        },
    ],
    "X-Learner": [
        {
            "name": "baseline",
            "outcome": "regressor",
            "params": BASE_PARAMS,
            "propensity": "estimated",
        },
        {
            "name": "fixed_propensity",
            "outcome": "regressor",
            "params": BASE_PARAMS,
            "propensity": "fixed",
        },
        {
            "name": "probability_fixed",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "cate_params": SMOOTH_FINAL_PARAMS,
            "propensity": "fixed",
        },
        {
            "name": "under7_probability_fixed",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "cate_params": SMOOTH_FINAL_PARAMS,
            "propensity": "fixed",
            "under": 7.0,
        },
        {
            "name": "under25_probability_fixed",
            "outcome": "classifier",
            "params": REGULARIZED_PARAMS,
            "cate_params": SMOOTH_FINAL_PARAMS,
            "propensity": "fixed",
            "under": 25.0,
        },
    ],
    "DR-Learner": [
        {"name": "baseline", "discrete": False, "params": BASE_PARAMS, "propensity": "fixed"},
        {
            "name": "binary_outcome",
            "discrete": True,
            "params": REGULARIZED_PARAMS,
            "final_params": SMOOTH_FINAL_PARAMS,
            "propensity": "fixed",
        },
        {
            "name": "binary_outcome_mc3",
            "discrete": True,
            "params": REGULARIZED_PARAMS,
            "final_params": SMOOTH_FINAL_PARAMS,
            "propensity": "fixed",
            "mc_iters": 3,
            "mc_agg": "median",
        },
        {
            "name": "binary_estimated_propensity",
            "discrete": True,
            "params": REGULARIZED_PARAMS,
            "final_params": SMOOTH_FINAL_PARAMS,
            "propensity": "estimated",
        },
    ],
}

SHORTLIST = {
    "Response": {"baseline", "regularized"},
    "S-Learner": {"baseline", "regularized_regression"},
    "T-Learner": {"baseline", "regularized_probability", "under7_probability"},
    "X-Learner": {"baseline", "probability_fixed", "under7_probability_fixed"},
    "DR-Learner": {"baseline", "binary_outcome"},
}


def _fit_and_score(model_name, config, fit_df, eval_df, seed):
    under = float(config.get("under", 1.0))
    model_df = rare_outcome_undersample(fit_df, factor=under, seed=seed) if under > 1 else fit_df
    X_fit, T_fit, Y_fit = xty(model_df)
    X_eval, T_eval, Y_eval = xty(eval_df)

    started = time.time()
    if model_name == "Response":
        model = fit_response_baseline(X_fit, Y_fit, seed=seed, model_params=config["params"])
        score = model.effect(X_eval)
    elif model_name == "S-Learner":
        model = fit_s_learner(
            X_fit,
            T_fit,
            Y_fit,
            seed=seed,
            outcome_model=config["outcome"],
            model_params=config["params"],
        )
        score = model.effect(X_eval).ravel() / under
    elif model_name == "T-Learner":
        model = fit_t_learner(
            X_fit,
            T_fit,
            Y_fit,
            seed=seed,
            outcome_model=config["outcome"],
            model_params=config["params"],
        )
        score = model.effect(X_eval).ravel() / under
    elif model_name == "X-Learner":
        model = fit_x_learner(
            X_fit,
            T_fit,
            Y_fit,
            seed=seed,
            outcome_model=config["outcome"],
            model_params=config["params"],
            cate_model_params=config.get("cate_params"),
            propensity=config["propensity"],
        )
        score = model.effect(X_eval).ravel() / under
    else:
        if under > 1:
            raise ValueError("Không undersample outcome cho DR-Learner nếu chưa sửa sampling weights")
        model = fit_dr_learner(
            X_fit,
            T_fit,
            Y_fit,
            cv=3,
            seed=seed,
            discrete_outcome=config["discrete"],
            regression_params=config["params"],
            final_params=config.get("final_params"),
            propensity=config["propensity"],
            mc_iters=config.get("mc_iters"),
            mc_agg=config.get("mc_agg", "mean"),
        )
        score = model.effect(X_eval).ravel()

    elapsed = time.time() - started
    row = {
        "model": model_name,
        "candidate": config["name"],
        "n_fit": len(model_df),
        "undersample_factor": under,
        "fit_seconds": round(elapsed, 3),
        "qini_score": qini_score(Y_eval, T_eval, score),
        "auuc_score": auuc_score(Y_eval, T_eval, score),
        "transformed_outcome_mse": (
            np.nan
            if model_name == "Response"
            else transformed_outcome_mse(Y_eval, T_eval, score)
        ),
        "uplift_calibration_error": (
            np.nan
            if model_name == "Response"
            else uplift_calibration_error(Y_eval, T_eval, score, n_bins=10)
        ),
        "cate_mean": float(np.mean(score)),
        "cate_std": float(np.std(score)),
    }
    return row, np.asarray(score, dtype="float64")


def _summarize_candidates(results):
    baseline = (
        results.loc[results["candidate"] == "baseline", ["model", "validation_seed", "qini_score"]]
        .rename(columns={"qini_score": "baseline_qini"})
    )
    with_delta = results.merge(baseline, on=["model", "validation_seed"], how="left")
    with_delta["qini_delta_vs_baseline"] = (
        with_delta["qini_score"] - with_delta["baseline_qini"]
    )
    with_delta["beats_baseline"] = with_delta["qini_delta_vs_baseline"] > 0
    summary = (
        with_delta.groupby(["model", "candidate"], sort=False)
        .agg(
            validation_seeds=("validation_seed", "nunique"),
            qini_median=("qini_score", "median"),
            qini_mean=("qini_score", "mean"),
            qini_std=("qini_score", "std"),
            qini_min=("qini_score", "min"),
            qini_max=("qini_score", "max"),
            median_delta_vs_baseline=("qini_delta_vs_baseline", "median"),
            mean_delta_vs_baseline=("qini_delta_vs_baseline", "mean"),
            seed_wins_vs_baseline=("beats_baseline", "sum"),
            auuc_mean=("auuc_score", "mean"),
            fit_seconds_total=("fit_seconds", "sum"),
        )
        .reset_index()
    )
    return with_delta, summary


def _select_winners(summary, min_median_delta: float, min_seed_wins: int):
    """Chọn candidate ổn định; fallback baseline nếu uplift chỉ thắng may rủi."""
    winners = {}
    for model_name, group in summary.groupby("model", sort=False):
        ranked = group.sort_values(
            ["qini_median", "qini_mean", "qini_min"],
            ascending=False,
        )
        candidate = ranked.iloc[0]
        stable = bool(
            candidate["candidate"] == "baseline"
            or (
                candidate["median_delta_vs_baseline"] >= min_median_delta
                and candidate["seed_wins_vs_baseline"] >= min_seed_wins
            )
        )
        winner_name = candidate["candidate"] if stable else "baseline"
        winners[model_name] = next(
            config for config in CANDIDATES[model_name] if config["name"] == winner_name
        )
    return winners


def _jsonable(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frac", type=float, default=0.10)
    parser.add_argument("--test-size", type=float, default=0.30)
    parser.add_argument("--validation-size", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--validation-seeds",
        default="43,44,45",
        help="danh sách seed cách nhau bởi dấu phẩy; dùng nhiều seed để tránh chọn may rủi",
    )
    parser.add_argument(
        "--validation-seed",
        type=int,
        default=None,
        help="tương thích lệnh cũ; nếu đặt thì override --validation-seeds",
    )
    parser.add_argument("--min-median-delta", type=float, default=0.005)
    parser.add_argument("--min-seed-wins", type=int, default=2)
    parser.add_argument("--evaluate-test", action="store_true")
    parser.add_argument("--n-boot-test", type=int, default=100)
    parser.add_argument(
        "--shortlist-only",
        action="store_true",
        help="chỉ chạy baseline + winner screening để kiểm tra robustness ở validation seed khác",
    )
    args = parser.parse_args()

    started = time.time()
    df = stratified_sample(load_criteo_full(dtype_f32=True), frac=args.frac, seed=args.seed)
    train_df, test_df = train_test_holdout(df, test_size=args.test_size, seed=args.seed)
    validation_seeds = (
        [args.validation_seed]
        if args.validation_seed is not None
        else [int(value.strip()) for value in args.validation_seeds.split(",") if value.strip()]
    )
    if not validation_seeds:
        raise ValueError("Cần ít nhất một validation seed")
    required_seed_wins = min(args.min_seed_wins, len(validation_seeds))
    print(
        f"[split] frac={args.frac} train={len(train_df):,} final_test={len(test_df):,} "
        f"validation_seeds={validation_seeds}",
        flush=True,
    )

    rows = []
    for validation_seed in validation_seeds:
        fit_df, validation_df = train_validation_split(
            train_df,
            validation_size=args.validation_size,
            seed=validation_seed,
        )
        print(
            f"[validation-split] seed={validation_seed} fit={len(fit_df):,} "
            f"validation={len(validation_df):,}",
            flush=True,
        )
        for model_name, configs in CANDIDATES.items():
            if args.shortlist_only:
                configs = [
                    config for config in configs if config["name"] in SHORTLIST[model_name]
                ]
            for config in configs:
                row, _ = _fit_and_score(
                    model_name, config, fit_df, validation_df, args.seed
                )
                row["validation_seed"] = validation_seed
                rows.append(row)
                print(
                    f"[validation] seed={validation_seed} {model_name:10s} "
                    f"{config['name']:30s} qini={row['qini_score']:.5f} "
                    f"auuc={row['auuc_score']:.5f} time={row['fit_seconds']:.1f}s",
                    flush=True,
                )

    result = pd.DataFrame(rows)
    result, summary = _summarize_candidates(result)
    winners = _select_winners(
        summary,
        min_median_delta=args.min_median_delta,
        min_seed_wins=required_seed_wins,
    )
    optimization_dir = OUTPUT_DIR / "optimization"
    optimization_dir.mkdir(parents=True, exist_ok=True)
    frac_slug = str(args.frac).replace(".", "p")
    seed_slug = "-".join(str(value) for value in validation_seeds)
    run_slug = f"frac_{frac_slug}_vseeds_{seed_slug}"
    if args.shortlist_only:
        run_slug += "_shortlist"
    validation_csv = optimization_dir / f"validation_results_{run_slug}.csv"
    result.to_csv(validation_csv, index=False)
    summary_csv = optimization_dir / f"candidate_summary_{run_slug}.csv"
    summary.to_csv(summary_csv, index=False)
    selected_json = optimization_dir / f"selected_configs_{run_slug}.json"
    selected_json.write_text(
        json.dumps(_jsonable(winners), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {validation_csv}", flush=True)
    print(f"[write] {summary_csv}", flush=True)
    print(f"[write] {selected_json}", flush=True)
    for model_name, config in winners.items():
        print(f"[winner] {model_name:10s} -> {config['name']}", flush=True)

    if args.evaluate_test:
        test_rows = []
        cate_dir = optimization_dir / "cate"
        cate_dir.mkdir(exist_ok=True)
        for model_name, config in winners.items():
            winner_row, winner_score = _fit_and_score(
                model_name, config, train_df, test_df, args.seed
            )
            baseline_config = CANDIDATES[model_name][0]
            if config["name"] == "baseline":
                baseline_score = winner_score
                baseline_qini = winner_row["qini_score"]
            else:
                baseline_row, baseline_score = _fit_and_score(
                    model_name, baseline_config, train_df, test_df, args.seed
                )
                baseline_qini = baseline_row["qini_score"]
            _, T_test, Y_test = xty(test_df)
            qini_low, qini_high = bootstrap_ci(
                Y_test,
                T_test,
                winner_score,
                n_boot=args.n_boot_test,
                seed=args.seed,
            )
            difference = paired_bootstrap_difference_ci(
                winner_score,
                baseline_score,
                Y_test,
                T_test,
                n_boot=args.n_boot_test,
                seed=args.seed,
            )
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
                }
            )
            test_rows.append(winner_row)
            slug = model_name.lower().replace("-", "_")
            np.save(cate_dir / f"cate_{slug}_optimized.npy", winner_score)
            print(
                f"[final] {model_name:10s} winner={config['name']:30s} "
                f"qini={winner_row['qini_score']:.5f} "
                f"CI=[{qini_low:.5f},{qini_high:.5f}] "
                f"delta={winner_row['qini_delta_vs_baseline']:+.5f} "
                f"delta_CI=[{difference['ci_low']:.5f},{difference['ci_high']:.5f}]",
                flush=True,
            )
        final_csv = optimization_dir / f"final_test_results_{run_slug}.csv"
        pd.DataFrame(test_rows).to_csv(final_csv, index=False)
        print(f"[write] {final_csv}", flush=True)

    print(f"[done] total={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
