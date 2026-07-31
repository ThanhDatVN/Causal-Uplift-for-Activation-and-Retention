"""Run the local, leakage-safe part of Sprint 2 end to end.

Default protocol:
1. Reconstruct the exact 50% Criteo sample used in Sprint 1 and keep its complement.
2. Split that untouched complement into fit/validation/confirmation = 60/20/20.
3. Compare the historical X-Learner ``effect / k`` approximation with exact
   arm-wise probability restoration and validation-only tau-isotonic calibration.
4. Evaluate fixed-budget and cost-aware policies on confirmation with IPW and DR.

The script never reads Sprint 1 final-test predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import lightgbm
import numpy as np
import pandas as pd
import psutil
import sklearn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.baselines import (
    fit_response_baseline,
    fit_t_learner_exact_undersampling,
    fit_x_learner,
)
from src.calibration import TauIsotonicCalibrator, negative_keep_probability
from src.data import (
    FEATURES,
    load_criteo_full,
    rare_outcome_undersample,
    stratified_complement,
    stratified_sample,
    train_test_holdout,
    validate_criteo_schema,
    xty,
)
from src.evaluation import (
    auuc_score,
    paired_qini_bootstrap_matrix,
    qini_score,
    transformed_outcome_mse,
    uplift_calibration_error,
)
from src.paths import CRITEO_PATH, OUTPUT_DIR, REPO_ROOT
from src.policy import (
    bootstrap_policy_values,
    cost_aware_policy,
    doubly_robust_effect_signal,
    ipw_effect_signal,
    policy_value_from_signal,
    top_budget_policy,
)


RUN_ID = "sprint2-local-exact-calibration-v1"
MODEL_LABELS = {
    "Response": "Response propensity (ranking baseline)",
    "X-Renormalized": "X-Learner / k (stratified renormalization)",
    "X-Calibrated": "X-Learner / k + validation tau-isotonic",
    "T-LocalExact": "T-Learner exact local-neighborhood restoration",
}


class _MemorySampler:
    def __init__(self, interval_seconds: float = 0.25):
        self.interval_seconds = interval_seconds
        self.peak_process_rss = 0
        self.minimum_system_available = psutil.virtual_memory().available
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        process = psutil.Process()
        while not self._stop.wait(self.interval_seconds):
            self.peak_process_rss = max(
                self.peak_process_rss,
                process.memory_info().rss,
            )
            self.minimum_system_available = min(
                self.minimum_system_available,
                psutil.virtual_memory().available,
            )

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.peak_process_rss = max(
            self.peak_process_rss,
            psutil.Process().memory_info().rss,
        )


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_indices(frame: pd.DataFrame) -> str:
    values = np.sort(frame.index.to_numpy(dtype="<i8", copy=True))
    return hashlib.sha256(values.tobytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _score_metrics(
    split_name: str,
    model_name: str,
    score: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    is_cate: bool,
) -> dict:
    return {
        "split": split_name,
        "model": model_name,
        "model_label": MODEL_LABELS[model_name],
        "n": len(score),
        "qini_score": qini_score(y, t, score),
        "auuc_score": auuc_score(y, t, score),
        "transformed_outcome_mse": (
            transformed_outcome_mse(y, t, score) if is_cate else np.nan
        ),
        "uplift_calibration_error": (
            uplift_calibration_error(y, t, score, n_bins=10)
            if is_cate
            else np.nan
        ),
        "score_mean": float(np.mean(score)),
        "score_std": float(np.std(score)),
        "score_min": float(np.min(score)),
        "score_max": float(np.max(score)),
        "negative_score_fraction": float(np.mean(score < 0)),
        "unique_score_count": int(np.unique(score).size),
    }


def _parse_float_list(raw: str, name: str) -> list[float]:
    result = [float(value.strip()) for value in raw.split(",") if value.strip()]
    if not result:
        raise ValueError(f"{name} cần ít nhất một giá trị")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pool-frac",
        type=float,
        default=1.0,
        help="Tỷ lệ của untouched Sprint 2 pool; 1.0 là release run, nhỏ hơn dùng smoke test.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pool-seed", type=int, default=51)
    parser.add_argument("--split-seed", type=int, default=52)
    parser.add_argument("--confirmation-seed", type=int, default=53)
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--budgets", default="0.01,0.05,0.10,0.20,0.30")
    parser.add_argument("--costs", default="0,0.00025,0.0005,0.001")
    parser.add_argument("--value-per-conversion", type=float, default=1.0)
    parser.add_argument("--main-budget", type=float, default=0.10)
    parser.add_argument("--main-cost", type=float, default=0.0005)
    parser.add_argument(
        "--min-available-ram-gb",
        type=float,
        default=2.5,
        help="Fail-fast gate before a full-pool local run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "sprint2",
    )
    args = parser.parse_args()

    if not 0 < args.pool_frac <= 1:
        raise ValueError("--pool-frac phải nằm trong (0, 1]")
    budgets = _parse_float_list(args.budgets, "--budgets")
    costs = _parse_float_list(args.costs, "--costs")
    if any(not 0 <= value <= 1 for value in budgets):
        raise ValueError("Mọi budget phải nằm trong [0, 1]")
    if any(value < 0 for value in costs):
        raise ValueError("Mọi contact cost phải >= 0")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    initial_memory = psutil.virtual_memory()
    initial_available_gb = initial_memory.available / 2**30
    if args.pool_frac == 1.0 and initial_available_gb < args.min_available_ram_gb:
        raise MemoryError(
            f"Full local run cần ít nhất {args.min_available_ram_gb:.1f} GB RAM "
            f"khả dụng tại gate; hiện có {initial_available_gb:.1f} GB. "
            "Đóng ứng dụng không cần thiết hoặc chạy package trên Kaggle."
        )
    memory_sampler = _MemorySampler()
    memory_sampler.start()
    release_config = json.loads(
        (REPO_ROOT / "configs" / "sprint1_release_5models.json").read_text(
            encoding="utf-8"
        )
    )
    x_config = release_config["X-Learner"]
    factor = float(x_config["under"])

    print("[data] loading and validating Criteo v2.1", flush=True)
    full = load_criteo_full(dtype_f32=True)
    schema = validate_criteo_schema(full)
    if not schema["valid"]:
        raise ValueError(f"Data contract failed: {schema}")
    full_assignment_probability = float(full["treatment"].mean())
    pool = stratified_complement(
        full,
        selected_frac=0.50,
        seed=args.seed,
        preserve_index=True,
    )
    del full
    if args.pool_frac < 1:
        pool = stratified_sample(
            pool,
            frac=args.pool_frac,
            seed=args.pool_seed,
            preserve_index=True,
        )
    print(f"[data] untouched pool rows={len(pool):,}", flush=True)

    fit_df, remainder = train_test_holdout(
        pool,
        test_size=0.40,
        seed=args.split_seed,
        preserve_index=True,
    )
    validation_df, confirmation_df = train_test_holdout(
        remainder,
        test_size=0.50,
        seed=args.confirmation_seed,
        preserve_index=True,
    )
    del remainder, pool
    split_frames = {
        "fit": fit_df,
        "validation": validation_df,
        "confirmation": confirmation_df,
    }
    split_rows = {name: len(frame) for name, frame in split_frames.items()}
    split_hashes = {
        name: _sha256_indices(frame) for name, frame in split_frames.items()
    }
    for name, frame in split_frames.items():
        print(
            f"[split] {name:12s} n={len(frame):,} "
            f"treatment={frame['treatment'].mean():.6f} "
            f"conversion={frame['conversion'].mean():.6f}",
            flush=True,
        )

    confirmation_source_index = confirmation_df.index.to_numpy(
        dtype="int64",
        copy=True,
    )
    X_fit_original, _, Y_fit_original = xty(fit_df, dtype="float32")
    X_validation, T_validation, Y_validation = xty(
        validation_df,
        dtype="float32",
    )
    X_confirmation, T_confirmation, Y_confirmation = xty(
        confirmation_df,
        dtype="float32",
    )
    del validation_df, confirmation_df, split_frames

    print("[fit] Response ranking baseline", flush=True)
    response = fit_response_baseline(
        X_fit_original,
        Y_fit_original,
        seed=args.seed,
        model_params=release_config["Response"]["params"],
    )
    response_validation = response.effect(X_validation).ravel()
    response_confirmation = response.effect(X_confirmation).ravel()
    del response, X_fit_original, Y_fit_original

    base_rates = fit_df.groupby("treatment")["conversion"].mean()
    sampled_df = rare_outcome_undersample(
        fit_df,
        factor=factor,
        seed=args.seed,
    )
    keep_probabilities = {}
    for arm in [0, 1]:
        original_negatives = int(
            ((fit_df["treatment"] == arm) & (fit_df["conversion"] == 0)).sum()
        )
        sampled_negatives = int(
            ((sampled_df["treatment"] == arm) & (sampled_df["conversion"] == 0)).sum()
        )
        keep_probabilities[arm] = sampled_negatives / original_negatives
    del fit_df
    X_sampled, T_sampled, Y_sampled = xty(sampled_df, dtype="float32")
    print(
        f"[undersampling] factor={factor:g} n={len(sampled_df):,} "
        f"s0={keep_probabilities[0]:.8f} s1={keep_probabilities[1]:.8f}",
        flush=True,
    )

    print("[fit] X-Learner stratified renormalization /k", flush=True)
    x_renormalized_model = fit_x_learner(
        X_sampled,
        T_sampled,
        Y_sampled,
        seed=args.seed,
        outcome_model=x_config["outcome"],
        model_params=x_config["params"],
        cate_model_params=x_config["cate_params"],
        propensity=x_config["propensity"],
    )
    x_renormalized_validation = (
        x_renormalized_model.effect(X_validation).ravel() / factor
    )
    x_renormalized_confirmation = (
        x_renormalized_model.effect(X_confirmation).ravel() / factor
    )
    del x_renormalized_model

    print("[fit] T-Learner exact local-neighborhood restoration", flush=True)
    t_exact_model = fit_t_learner_exact_undersampling(
        X_sampled,
        T_sampled,
        Y_sampled,
        negative_keep_prob_control=keep_probabilities[0],
        negative_keep_prob_treatment=keep_probabilities[1],
        seed=args.seed,
        model_params=x_config["params"],
    )
    t_exact_validation = t_exact_model.effect(X_validation).ravel()
    t_exact_confirmation = t_exact_model.effect(X_confirmation).ravel()
    mu0_confirmation = t_exact_model.models[0].predict(X_confirmation)
    mu1_confirmation = t_exact_model.models[1].predict(X_confirmation)
    del t_exact_model, X_sampled, T_sampled, Y_sampled, sampled_df

    print(
        "[calibration] fitting post-hoc tau-isotonic on X score, validation only",
        flush=True,
    )
    calibrator = TauIsotonicCalibrator().fit(
        x_renormalized_validation,
        Y_validation,
        T_validation,
        propensity=full_assignment_probability,
    )
    x_calibrated_validation = calibrator.predict(x_renormalized_validation)
    x_calibrated_confirmation = calibrator.predict(x_renormalized_confirmation)
    del X_validation, X_confirmation

    score_sets = {
        "Response": (response_validation, response_confirmation, False),
        "X-Renormalized": (
            x_renormalized_validation,
            x_renormalized_confirmation,
            True,
        ),
        "X-Calibrated": (
            x_calibrated_validation,
            x_calibrated_confirmation,
            True,
        ),
        "T-LocalExact": (
            t_exact_validation,
            t_exact_confirmation,
            True,
        ),
    }
    metric_rows = []
    for model_name, (validation_score, confirmation_score, is_cate) in score_sets.items():
        metric_rows.append(
            _score_metrics(
                "validation",
                model_name,
                validation_score,
                Y_validation,
                T_validation,
                is_cate,
            )
        )
        metric_rows.append(
            _score_metrics(
                "confirmation",
                model_name,
                confirmation_score,
                Y_confirmation,
                T_confirmation,
                is_cate,
            )
        )
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(output_dir / "calibration_comparison.csv", index=False)

    print(f"[bootstrap] paired Qini comparisons n={args.n_boot}", flush=True)
    qini_bootstrap = paired_qini_bootstrap_matrix(
        {
            "Response": response_confirmation,
            "X-Renormalized": x_renormalized_confirmation,
            "X-Calibrated": x_calibrated_confirmation,
            "T-LocalExact": t_exact_confirmation,
        },
        Y_confirmation,
        T_confirmation,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    bootstrap_names = qini_bootstrap["model_names"]
    paired_rows = []
    for model_a, model_b in [
        ("T-LocalExact", "X-Renormalized"),
        ("X-Calibrated", "X-Renormalized"),
        ("X-Renormalized", "Response"),
        ("Response", "X-Calibrated"),
    ]:
        index_a = bootstrap_names.index(model_a)
        index_b = bootstrap_names.index(model_b)
        differences = (
            qini_bootstrap["draws"][:, index_a]
            - qini_bootstrap["draws"][:, index_b]
        )
        paired_rows.append(
            {
                "model_a": model_a,
                "model_b": model_b,
                "metric": "normalized_qini",
                "n_boot": args.n_boot,
                "observed_difference": (
                    qini_bootstrap["observed"][index_a]
                    - qini_bootstrap["observed"][index_b]
                ),
                "ci_low": np.quantile(differences, 0.025),
                "ci_high": np.quantile(differences, 0.975),
                "score_a_ci_low": qini_bootstrap["ci_low"][index_a],
                "score_a_ci_high": qini_bootstrap["ci_high"][index_a],
                "score_b_ci_low": qini_bootstrap["ci_low"][index_b],
                "score_b_ci_high": qini_bootstrap["ci_high"][index_b],
                "probability_difference_positive": float(
                    np.mean(differences > 0)
                ),
                "n_valid_bootstrap": qini_bootstrap["n_valid_bootstrap"],
            }
        )
    pd.DataFrame(paired_rows).to_csv(
        output_dir / "paired_qini_bootstrap.csv",
        index=False,
    )

    ipw_signal = ipw_effect_signal(
        Y_confirmation,
        T_confirmation,
        propensity=full_assignment_probability,
    )
    dr_signal = doubly_robust_effect_signal(
        Y_confirmation,
        T_confirmation,
        mu0_confirmation,
        mu1_confirmation,
        propensity=full_assignment_probability,
    )
    score_by_policy = {
        "Response top-k": response_confirmation,
        "X-Renormalized top-k": x_renormalized_confirmation,
        "X-Calibrated top-k": x_calibrated_confirmation,
        "T-LocalExact top-k": t_exact_confirmation,
    }
    rng = np.random.default_rng(args.seed)
    random_score = rng.random(len(Y_confirmation))

    sensitivity_rows = []
    for budget in budgets:
        fixed_policies = {
            "Treat none": np.zeros(len(Y_confirmation), dtype="int8"),
            "Random top-k": top_budget_policy(random_score, budget),
            **{
                name: top_budget_policy(score, budget)
                for name, score in score_by_policy.items()
            },
        }
        for cost in costs:
            policies = {
                **fixed_policies,
                "X-Calibrated cost-aware": cost_aware_policy(
                    x_calibrated_confirmation,
                    budget_fraction=budget,
                    value_per_conversion=args.value_per_conversion,
                    contact_cost=cost,
                ),
            }
            for policy_name, policy in policies.items():
                target_fraction = float(np.mean(policy))
                gross_ipw = policy_value_from_signal(policy, ipw_signal)
                gross_dr = policy_value_from_signal(policy, dr_signal)
                sensitivity_rows.append(
                    {
                        "run_id": RUN_ID,
                        "policy": policy_name,
                        "budget_fraction": budget,
                        "contact_cost_assumption": cost,
                        "value_per_conversion_assumption": args.value_per_conversion,
                        "target_fraction": target_fraction,
                        "gross_incremental_conversions_per_customer_ipw": gross_ipw,
                        "gross_incremental_conversions_per_customer_dr": gross_dr,
                        "net_scenario_value_per_customer_ipw": (
                            gross_ipw * args.value_per_conversion
                            - target_fraction * cost
                        ),
                        "net_scenario_value_per_customer_dr": (
                            gross_dr * args.value_per_conversion
                            - target_fraction * cost
                        ),
                        "is_monetary_observation": False,
                        "interpretation": "conversion-equivalent assumption scenario",
                    }
                )
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(output_dir / "policy_sensitivity.csv", index=False)

    print(
        f"[bootstrap] main policy scenario budget={args.main_budget:g} "
        f"cost={args.main_cost:g}",
        flush=True,
    )
    main_policies = {
        "Treat none": np.zeros(len(Y_confirmation), dtype="int8"),
        "Random top-k": top_budget_policy(random_score, args.main_budget),
        **{
            name: top_budget_policy(score, args.main_budget)
            for name, score in score_by_policy.items()
        },
        "X-Calibrated cost-aware": cost_aware_policy(
            x_calibrated_confirmation,
            budget_fraction=args.main_budget,
            value_per_conversion=args.value_per_conversion,
            contact_cost=args.main_cost,
        ),
    }
    main_names = list(main_policies)
    dr_contributions = np.column_stack(
        [
            policy
            * (
                args.value_per_conversion * dr_signal
                - args.main_cost
            )
            for policy in main_policies.values()
        ]
    )
    bootstrap = bootstrap_policy_values(
        dr_contributions,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    random_index = main_names.index("Random top-k")
    main_rows = []
    for index, (policy_name, policy) in enumerate(main_policies.items()):
        difference_draws = (
            bootstrap["draws"][:, index]
            - bootstrap["draws"][:, random_index]
        )
        main_rows.append(
            {
                "run_id": RUN_ID,
                "policy": policy_name,
                "budget_fraction": args.main_budget,
                "contact_cost_assumption": args.main_cost,
                "value_per_conversion_assumption": args.value_per_conversion,
                "target_fraction": float(np.mean(policy)),
                "ipw_net_scenario_value_per_customer": policy_value_from_signal(
                    policy,
                    ipw_signal,
                    args.value_per_conversion,
                    args.main_cost,
                ),
                "dr_net_scenario_value_per_customer": bootstrap["mean"][index],
                "dr_ci_low": bootstrap["ci_low"][index],
                "dr_ci_high": bootstrap["ci_high"][index],
                "dr_delta_vs_random": (
                    bootstrap["mean"][index] - bootstrap["mean"][random_index]
                ),
                "dr_delta_vs_random_ci_low": np.quantile(
                    difference_draws,
                    0.025,
                ),
                "dr_delta_vs_random_ci_high": np.quantile(
                    difference_draws,
                    0.975,
                ),
                "n_boot": args.n_boot,
                "is_monetary_observation": False,
            }
        )
    pd.DataFrame(main_rows).to_csv(
        output_dir / "policy_value_comparison.csv",
        index=False,
    )

    np.savez_compressed(
        output_dir / "confirmation_predictions.npz",
        source_index=confirmation_source_index,
        treatment=T_confirmation.astype("int8"),
        conversion=Y_confirmation.astype("int8"),
        response_score=response_confirmation.astype("float32"),
        x_renormalized=x_renormalized_confirmation.astype("float32"),
        x_calibrated=x_calibrated_confirmation.astype("float32"),
        t_local_exact=t_exact_confirmation.astype("float32"),
        mu0_local_exact=mu0_confirmation.astype("float32"),
        mu1_local_exact=mu1_confirmation.astype("float32"),
    )

    memory_sampler.stop()
    manifest = {
        "run_id": RUN_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "local_complete",
        "scope": (
            "Untouched complement of Sprint 1 50% sample; final test Sprint 1 "
            "was not read or reused."
        ),
        "data": {
            "path": CRITEO_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256_file(CRITEO_PATH),
            "schema_contract": schema,
            "sprint1_selected_fraction": 0.50,
            "sprint1_sampling_seed": args.seed,
            "sprint2_complement_pool_fraction_used": args.pool_frac,
        },
        "split": {
            "protocol": "fit/validation/confirmation = 60/20/20 of Sprint 2 pool",
            "split_seed": args.split_seed,
            "confirmation_seed": args.confirmation_seed,
            "rows": split_rows,
            "source_index_sha256": split_hashes,
        },
        "model": {
            "release_config_source": "configs/sprint1_release_5models.json",
            "x_learner_config": x_config,
            "undersampling_factor": factor,
            "base_conversion_rate_by_arm": {
                str(key): float(value) for key, value in base_rates.items()
            },
            "theoretical_negative_keep_probability_by_arm": {
                str(arm): negative_keep_probability(base_rates.loc[arm], factor)
                for arm in [0, 1]
            },
            "realized_negative_keep_probability_by_arm": {
                str(key): value for key, value in keep_probabilities.items()
            },
            "tau_isotonic_fit_split": "validation",
            "method_scope": {
                "x_renormalized": (
                    "paper-recommended calibration pairing for stratified undersampling"
                ),
                "x_tau_isotonic": (
                    "method-agnostic post-processing ablation; theoretically sound "
                    "but not the paper's preferred stratified pairing"
                ),
                "t_local_exact": (
                    "direct Eq. 12 scope: restore two arm probabilities then subtract"
                ),
            },
        },
        "evaluation": {
            "confirmation_only": True,
            "propensity": full_assignment_probability,
            "n_boot": args.n_boot,
            "budgets": budgets,
            "contact_cost_assumptions": costs,
            "value_per_conversion_assumption": args.value_per_conversion,
            "monetary_outcome_available": False,
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "lightgbm": lightgbm.__version__,
            "logical_cpu_count": psutil.cpu_count(),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "system_ram_total_gb": initial_memory.total / 2**30,
            "system_ram_available_at_start_gb": initial_available_gb,
            "peak_process_rss_gb": memory_sampler.peak_process_rss / 2**30,
            "minimum_system_available_ram_gb": (
                memory_sampler.minimum_system_available / 2**30
            ),
        },
        "external_status": {
            "causal_forest_kaggle": (
                "pending external Kaggle session; local artifacts do not claim completion"
            ),
            "git_release_tag": (
                "not created because repository currently has no commits"
            ),
        },
        "elapsed_seconds": time.time() - started,
    }
    (output_dir / "protocol_manifest.json").write_text(
        json.dumps(_jsonable(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "status": "local_complete",
        "elapsed_seconds": time.time() - started,
        "confirmation_rows": split_rows["confirmation"],
        "confirmation_metrics": metrics.loc[
            metrics["split"] == "confirmation"
        ].to_dict(orient="records"),
        "main_policy_scenario": main_rows,
        "limitations": [
            "Criteo has no revenue, margin, or treatment cost; scenario value is not actual profit.",
            "Causal Forest cloud learning curve remains pending until a Kaggle session is provided.",
            "No individual principal stratum is observed; policies are score-based offline rules.",
        ],
    }
    (output_dir / "sprint2_local_summary.json").write_text(
        json.dumps(_jsonable(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {output_dir}", flush=True)
    print(f"[done] elapsed={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
