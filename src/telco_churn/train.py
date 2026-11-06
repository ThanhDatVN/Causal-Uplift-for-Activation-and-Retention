"""Run the locked benchmark, select/calibrate a champion, and create evaluation artifacts."""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.inspection import permutation_importance
from sklearn.metrics import precision_recall_curve, roc_curve
from sklearn.model_selection import (
    RandomizedSearchCV,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
)

from telco_churn.data import (
    anonymize_customer_id,
    create_or_load_split_manifest,
    load_modeling_data,
    split_by_manifest,
    split_manifest_metadata,
)
from telco_churn.evaluation import (
    budget_metrics,
    calibration_diagnostics,
    probability_metrics,
    reliability_table,
    slice_metrics,
    stratified_bootstrap_delta,
    top_k_indices,
)
from telco_churn.features import build_estimator, parameter_space
from telco_churn.policy import scenario_summary
from telco_churn.schema import DATA_SHA256, FEATURE_COLUMNS, SPLIT_SEED

MODEL_NAMES = (
    "dummy_prior",
    "dummy_most_frequent",
    "logistic",
    "logistic_no_sensitive",
    "hist_gradient_boosting",
    "catboost",
)


def _json_safe_params(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value if value is None or isinstance(value, (str, int, float, bool)) else repr(value)
        for key, value in parameters.items()
    }


def _fit_search(
    name: str,
    x_development: pd.DataFrame,
    y_development: pd.Series,
    *,
    quick: bool,
    seed: int,
) -> tuple[Any, dict[str, Any], float, float]:
    estimator = build_estimator(name, seed=seed)
    space, iterations = parameter_space(name, quick=quick)
    start = time.perf_counter()
    if not space:
        estimator.fit(x_development, y_development)
        return estimator, {}, math.nan, time.perf_counter() - start
    inner_splits = 3 if quick else 5
    search = RandomizedSearchCV(
        estimator,
        param_distributions=space,
        n_iter=iterations,
        scoring="average_precision",
        cv=StratifiedKFold(n_splits=inner_splits, shuffle=True, random_state=seed),
        random_state=seed,
        n_jobs=-1,
        refit=True,
        return_train_score=True,
        error_score="raise",
    )
    search.fit(x_development, y_development)
    return (
        search.best_estimator_,
        _json_safe_params(search.best_params_),
        float(search.best_score_),
        time.perf_counter() - start,
    )


def _stability_scores(
    estimator: Any,
    x_development: pd.DataFrame,
    y_development: pd.Series,
    *,
    quick: bool,
    seed: int,
) -> dict[str, float]:
    cv = RepeatedStratifiedKFold(
        n_splits=3 if quick else 5,
        n_repeats=1 if quick else 3,
        random_state=seed + 1,
    )
    scores = cross_validate(
        clone(estimator),
        x_development,
        y_development,
        cv=cv,
        scoring={
            "average_precision": "average_precision",
            "roc_auc": "roc_auc",
            "brier_score": "neg_brier_score",
            "log_loss": "neg_log_loss",
        },
        n_jobs=-1,
        return_train_score=False,
        error_score="raise",
    )
    result = {}
    for metric in ("average_precision", "roc_auc", "brier_score", "log_loss"):
        values = scores[f"test_{metric}"]
        if metric in {"brier_score", "log_loss"}:
            values = -values
        result[f"cv_{metric}_mean"] = float(np.mean(values))
        result[f"cv_{metric}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    result["cv_fits"] = len(scores["test_average_precision"])
    return result


def _calibration_candidates(
    model_name: str,
    estimator: Any,
    x_development: pd.DataFrame,
    y_development: pd.Series,
    *,
    quick: bool,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    outer_cv = StratifiedKFold(
        n_splits=3 if quick else 5,
        shuffle=True,
        random_state=seed + 2,
    )
    methods = ("none", "sigmoid") if quick else ("none", "sigmoid", "isotonic")
    predictions: dict[str, np.ndarray] = {}
    rows = []
    for method in methods:
        candidate = clone(estimator)
        if method != "none":
            candidate = CalibratedClassifierCV(
                estimator=candidate,
                method=method,
                cv=3,
                ensemble=True,
            )
        probability = cross_val_predict(
            candidate,
            x_development,
            y_development,
            cv=outer_cv,
            method="predict_proba",
            n_jobs=-1,
        )[:, 1]
        predictions[method] = probability
        rows.append(
            {
                "model": model_name,
                "calibration": method,
                **probability_metrics(y_development, probability),
            }
        )
    table = pd.DataFrame(rows)
    uncalibrated_ap = float(table.loc[table["calibration"].eq("none"), "average_precision"].iloc[0])
    eligible = table[table["average_precision"] >= uncalibrated_ap - 0.005]
    selected_index = eligible["brier_score"].idxmin()
    table["selected_for_model"] = False
    table.loc[selected_index, "selected_for_model"] = True
    return table, predictions


def _with_calibration(estimator: Any, method: str) -> Any:
    if method == "none":
        return clone(estimator)
    return CalibratedClassifierCV(
        estimator=clone(estimator),
        method=method,
        cv=5,
        ensemble=True,
    )


def _mlflow_run(
    name: str,
    parameters: dict[str, Any],
    metrics: dict[str, float],
    *,
    split_hash: str,
) -> str:
    with mlflow.start_run(run_name=name) as run:
        mlflow.set_tags(
            {
                "dataset_sha256": DATA_SHA256,
                "split_sha256": split_hash,
                "benchmark_protocol": "v1",
            }
        )
        if parameters:
            mlflow.log_params(parameters)
        mlflow.log_metrics(
            {
                key: float(value)
                for key, value in metrics.items()
                if isinstance(value, (int, float)) and np.isfinite(value)
            }
        )
        return run.info.run_id


def _save_plots(
    y_test: pd.Series,
    champion_probability: np.ndarray,
    logistic_probability: np.ndarray,
    customer_ids: pd.Series,
    reliability: pd.DataFrame,
    importance: pd.DataFrame,
    output_dir: Path,
) -> None:
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    curves = (
        (("Champion = Logistic reference", champion_probability, "#2563eb"),)
        if np.allclose(champion_probability, logistic_probability)
        else (
            ("Champion", champion_probability, "#2563eb"),
            ("Logistic reference", logistic_probability, "#6b7280"),
        )
    )
    for label, probability, color in curves:
        precision, recall, _ = precision_recall_curve(y_test, probability)
        false_positive_rate, true_positive_rate, _ = roc_curve(y_test, probability)
        axes[0].plot(recall, precision, label=label, color=color)
        axes[1].plot(false_positive_rate, true_positive_rate, label=label, color=color)
    axes[0].axhline(y_test.mean(), color="#b45309", linestyle="--", label="Prevalence")
    axes[0].set(title="Precision–recall", xlabel="Recall", ylabel="Precision")
    axes[1].plot([0, 1], [0, 1], color="#b45309", linestyle="--", label="Random")
    axes[1].set(title="ROC", xlabel="False-positive rate", ylabel="True-positive rate")
    for axis in axes:
        axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "pr_roc_curves.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(5.5, 5))
    axis.plot([0, 1], [0, 1], color="#6b7280", linestyle="--", label="Perfect calibration")
    axis.plot(
        reliability["mean_predicted"],
        reliability["observed_rate"],
        marker="o",
        color="#2563eb",
        label="Champion",
    )
    for index, row in enumerate(reliability.itertuples()):
        offset = (4, 5) if index % 2 == 0 else (4, -10)
        axis.annotate(
            f"n={row.n}",
            (row.mean_predicted, row.observed_rate),
            xytext=offset,
            textcoords="offset points",
            fontsize=7,
        )
    axis.set(
        title="Reliability on frozen test",
        xlabel="Mean predicted probability",
        ylabel="Observed churn rate",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "calibration_curve.png", dpi=160)
    plt.close(figure)

    budgets = np.linspace(0.01, 1.0, 100)
    recall_values = [
        budget_metrics(y_test, champion_probability, customer_ids, budgets=(budget,)).iloc[0][
            "recall_at_budget"
        ]
        for budget in budgets
    ]
    figure, axis = plt.subplots(figsize=(6.4, 4.5))
    axis.plot(budgets, recall_values, color="#2563eb", label="Champion gains")
    axis.plot([0, 1], [0, 1], color="#6b7280", linestyle="--", label="Random ranking")
    axis.set(title="Cumulative gains", xlabel="Contacted fraction", ylabel="Recall of churners")
    axis.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    axis.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "cumulative_gains.png", dpi=160)
    plt.close(figure)

    top = importance.head(12).sort_values("importance_mean")
    figure, axis = plt.subplots(figsize=(7.5, 5))
    axis.barh(top["feature"], top["importance_mean"], xerr=top["importance_std"], color="#2563eb")
    axis.set(title="Permutation importance on frozen test", xlabel="Decrease in Average Precision")
    figure.tight_layout()
    figure.savefig(figure_dir / "permutation_importance.png", dpi=160)
    plt.close(figure)


def _error_cases(
    x_test: pd.DataFrame,
    y_test: pd.Series,
    probability: np.ndarray,
    customer_ids: pd.Series,
) -> pd.DataFrame:
    selected_indices = set(top_k_indices(probability, customer_ids, 0.10).tolist())
    selected = np.array([index in selected_indices for index in range(len(y_test))])
    frame = x_test.copy()
    frame["actual_churn"] = y_test.to_numpy()
    frame["risk_30d"] = probability
    frame["selected_at_10pct"] = selected
    frame["anonymous_customer_id"] = customer_ids.map(anonymize_customer_id).to_numpy()
    frame["row_index"] = np.arange(len(frame))

    false_positives = frame[(frame["selected_at_10pct"]) & frame["actual_churn"].eq(0)].nlargest(
        5, "risk_30d"
    )
    false_positives = false_positives.assign(
        case_type="high_risk_false_positive",
        review_hypothesis=(
            "Risk factors were predictive but not causal/deterministic; inspect missing intervention "
            "and post-snapshot behavior."
        ),
    )
    false_negatives = frame[(~frame["selected_at_10pct"]) & frame["actual_churn"].eq(1)].nsmallest(
        5, "risk_30d"
    )
    false_negatives = false_negatives.assign(
        case_type="low_risk_false_negative",
        review_hypothesis=(
            "Observed churn is not explained by static account fields; investigate service events, "
            "complaints and point-in-time feature gaps."
        ),
    )
    used = set(false_positives["row_index"]) | set(false_negatives["row_index"])
    boundary = np.partition(probability, -max(1, math.ceil(len(probability) * 0.10)))[
        -max(1, math.ceil(len(probability) * 0.10))
    ]
    near = frame[~frame["row_index"].isin(used)].copy()
    near["boundary_distance"] = (near["risk_30d"] - boundary).abs()
    near = near.nsmallest(5, "boundary_distance").assign(
        case_type="near_budget_boundary",
        review_hypothesis=(
            "Selection is sensitive to budget/tie policy; analyst should not interpret the cutoff "
            "as a natural risk boundary."
        ),
    )
    columns = [
        "anonymous_customer_id",
        "case_type",
        "actual_churn",
        "risk_30d",
        "selected_at_10pct",
        "tenure",
        "Contract",
        "InternetService",
        "PaymentMethod",
        "MonthlyCharges",
        "review_hypothesis",
    ]
    return pd.concat([false_positives, false_negatives, near], ignore_index=True)[columns]


def _benchmark_report(
    benchmark: pd.DataFrame,
    calibration: pd.DataFrame,
    budget: pd.DataFrame,
    bootstrap: pd.DataFrame,
    scenario: pd.DataFrame,
    metadata: dict[str, Any],
) -> str:
    champion_row = benchmark[benchmark["model"].eq("champion_calibrated")].iloc[0]
    logistic_row = benchmark[benchmark["model"].eq("logistic_calibrated")].iloc[0]
    lines = [
        "# Benchmark Report — Frozen Test",
        "",
        "> Test set was opened after model, hyperparameter, calibration and complexity-gate rules "
        "were fixed. IBM sample has no timestamps; this is not out-of-time validation.",
        "",
        "## Decision",
        "",
        f"- Champion: **{metadata['champion_model']} + {metadata['calibration']} calibration**.",
        f"- Complexity gate: **{metadata['complexity_gate_decision']}**.",
        f"- Frozen test: {metadata['test_rows']:,} rows; development: {metadata['development_rows']:,} rows.",
        f"- Test Average Precision: **{champion_row['test_average_precision']:.4f}**; logistic reference "
        f"**{logistic_row['test_average_precision']:.4f}**.",
        f"- Test ROC-AUC: **{champion_row['test_roc_auc']:.4f}**; Brier: "
        f"**{champion_row['test_brier_score']:.4f}**.",
        "",
        "## Model matrix",
        "",
        "| Model | CV AP mean±sd | Test AP | Test ROC-AUC | Test Brier | Test log loss |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in benchmark.itertuples():
        cv_text = (
            f"{row.cv_average_precision_mean:.4f}±{row.cv_average_precision_std:.4f}"
            if pd.notna(row.cv_average_precision_mean)
            else "—"
        )
        lines.append(
            f"| {row.model} | {cv_text} | {row.test_average_precision:.4f} | "
            f"{row.test_roc_auc:.4f} | {row.test_brier_score:.4f} | {row.test_log_loss:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Calibration candidates on development OOF predictions",
            "",
            "| Model | Method | AP | Brier | Log loss | Selected for model |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in calibration.itertuples():
        lines.append(
            f"| {row.model} | {row.calibration} | {row.average_precision:.4f} | "
            f"{row.brier_score:.4f} | {row.log_loss:.4f} | {row.selected_for_model} |"
        )
    lines.extend(
        [
            "",
            "## Budget matrix on frozen test",
            "",
            "| Budget | Contacts | Captured churners | Precision | Recall | Lift |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in budget.itertuples():
        lines.append(
            f"| {row.budget_fraction:.0%} | {row.k} | {row.true_positives} | "
            f"{row.precision_at_budget:.1%} | {row.recall_at_budget:.1%} | "
            f"{row.lift_at_budget:.2f}× |"
        )
    lines.extend(
        [
            "",
            "The ranking diagnostic uses `ceil(fraction * N)` to preserve the published "
            "budget curve. The hard campaign scenario below uses `floor(fraction * N)` "
            "so contacts cannot exceed the stated cap.",
        ]
    )
    lines.extend(
        [
            "",
            "## Paired stratified bootstrap: champion minus logistic",
            "",
            "| Delta metric | Mean | 95% CI |",
            "|---|---:|---:|",
        ]
    )
    for row in bootstrap.itertuples():
        lines.append(
            f"| {row.metric_delta_champion_minus_logistic} | {row.mean:.4f} | "
            f"[{row.ci95_low:.4f}, {row.ci95_high:.4f}] |"
        )
    lines.extend(
        [
            "",
            "## Simulated business scenarios at 10% capacity",
            "",
            "| Scenario | Save-rate assumption | Selected/capacity | Budget use | Simulated EV |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in scenario.itertuples():
        lines.append(
            f"| {row.name} | {row.save_rate:.0%} | {row.selected_customers}/{row.budget_capacity} | "
            f"{row.budget_utilization:.1%} | {row.simulated_total_expected_value:.2f} |"
        )
    lines.extend(
        [
            "",
            "The value table is scenario analysis, not measured retention uplift or revenue saved. "
            "The dataset has no treatment/control outcomes.",
            "",
            "## Artifact inventory",
            "",
            "- `benchmark_table.csv`, `calibration_candidates.csv`, `calibration_diagnostics.csv`, `budget_metrics.csv`",
            "- `bootstrap_delta.csv`, `slice_metrics.csv`, `permutation_importance.csv`",
            "- `error_cases.csv` (15 anonymized cases), `scenario_summary.csv`",
            "- `test_predictions.csv`, `reliability_table.csv`, `figures/`",
            "- immutable model bundle and `model_metadata.json` under `artifacts/models/`",
            "",
        ]
    )
    return "\n".join(lines)


def run_training(
    data_path: Path,
    output_dir: Path,
    model_dir: Path,
    *,
    quick: bool = False,
    seed: int = SPLIT_SEED,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    split_path = Path("data/splits/split_manifest.csv")
    features, target, customer_ids, _ = load_modeling_data(data_path)
    manifest = create_or_load_split_manifest(customer_ids, target, split_path, seed=seed)
    (
        x_development,
        x_test,
        y_development,
        y_test,
        _ids_development,
        ids_test,
    ) = split_by_manifest(features, target, customer_ids, manifest)
    split_meta = split_manifest_metadata(split_path)

    tracking_path = Path("mlflow.db").resolve().as_posix()
    mlflow.set_tracking_uri(f"sqlite:///{tracking_path}")
    mlflow.set_experiment("telcochurn-locked-benchmark")

    best_estimators: dict[str, Any] = {}
    benchmark_rows: list[dict[str, Any]] = []
    mlflow_run_ids: dict[str, str] = {}
    for name in MODEL_NAMES:
        estimator, best_params, search_score, fit_seconds = _fit_search(
            name,
            x_development,
            y_development,
            quick=quick,
            seed=seed,
        )
        best_estimators[name] = deepcopy(estimator)
        stability = _stability_scores(
            estimator,
            x_development,
            y_development,
            quick=quick,
            seed=seed,
        )
        row = {
            "model": name,
            "search_best_cv_average_precision": search_score,
            "search_fit_seconds": fit_seconds,
            "best_params_json": json.dumps(best_params, sort_keys=True),
            **stability,
        }
        benchmark_rows.append(row)
        mlflow_run_ids[name] = _mlflow_run(
            name,
            best_params,
            stability,
            split_hash=str(split_meta["sha256"]),
        )
        print(f"{name}: CV AP={stability['cv_average_precision_mean']:.4f}")

    benchmark = pd.DataFrame(benchmark_rows)
    complex_models = benchmark[benchmark["model"].isin(["hist_gradient_boosting", "catboost"])]
    best_complex_name = str(
        complex_models.sort_values("cv_average_precision_mean", ascending=False).iloc[0]["model"]
    )

    calibration_tables = []
    calibration_predictions: dict[str, dict[str, np.ndarray]] = {}
    for name in ("logistic", best_complex_name):
        table, predictions = _calibration_candidates(
            name,
            best_estimators[name],
            x_development,
            y_development,
            quick=quick,
            seed=seed,
        )
        calibration_tables.append(table)
        calibration_predictions[name] = predictions
    calibration = pd.concat(calibration_tables, ignore_index=True)

    selected_calibration = {
        name: str(
            calibration[calibration["model"].eq(name) & calibration["selected_for_model"]][
                "calibration"
            ].iloc[0]
        )
        for name in ("logistic", best_complex_name)
    }
    calibration_brier = {
        name: float(
            calibration[calibration["model"].eq(name) & calibration["selected_for_model"]][
                "brier_score"
            ].iloc[0]
        )
        for name in ("logistic", best_complex_name)
    }
    cv_ap = benchmark.set_index("model")["cv_average_precision_mean"]
    complex_wins = (
        cv_ap[best_complex_name] >= cv_ap["logistic"] + 0.01
        and calibration_brier[best_complex_name] <= calibration_brier["logistic"] + 0.005
    )
    champion_name = best_complex_name if complex_wins else "logistic"
    complexity_decision = (
        "complex model passed the +0.01 AP / +0.005 Brier gate"
        if complex_wins
        else "logistic retained; complex model did not clear the predeclared gate"
    )
    champion_calibration = selected_calibration[champion_name]
    logistic_calibration = selected_calibration["logistic"]

    # Model choice is now immutable. Only from this point is the frozen test evaluated.
    for name, estimator in best_estimators.items():
        probability = estimator.predict_proba(x_test)[:, 1]
        metrics = probability_metrics(y_test, probability)
        for key, value in metrics.items():
            benchmark.loc[benchmark["model"].eq(name), f"test_{key}"] = value
        with mlflow.start_run(run_id=mlflow_run_ids[name]):
            mlflow.log_metrics({f"test_{key}": value for key, value in metrics.items()})
        print(f"{name}: frozen-test AP={metrics['average_precision']:.4f}")

    final_champion = _with_calibration(best_estimators[champion_name], champion_calibration)
    final_champion.fit(x_development, y_development)
    champion_probability = final_champion.predict_proba(x_test)[:, 1]
    champion_metrics = probability_metrics(y_test, champion_probability)

    final_logistic = _with_calibration(best_estimators["logistic"], logistic_calibration)
    final_logistic.fit(x_development, y_development)
    logistic_probability = final_logistic.predict_proba(x_test)[:, 1]
    logistic_metrics = probability_metrics(y_test, logistic_probability)

    for label, source_name, metrics in (
        ("logistic_calibrated", "logistic", logistic_metrics),
        ("champion_calibrated", champion_name, champion_metrics),
    ):
        source = benchmark[benchmark["model"].eq(source_name)].iloc[0]
        benchmark = pd.concat(
            [
                benchmark,
                pd.DataFrame(
                    [
                        {
                            "model": label,
                            "search_best_cv_average_precision": source[
                                "search_best_cv_average_precision"
                            ],
                            "search_fit_seconds": source["search_fit_seconds"],
                            "best_params_json": source["best_params_json"],
                            **{
                                column: source[column]
                                for column in benchmark.columns
                                if column.startswith("cv_")
                            },
                            **{f"test_{key}": value for key, value in metrics.items()},
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    budget = budget_metrics(y_test, champion_probability, ids_test)
    reliability = reliability_table(y_test, champion_probability)
    calibration_diagnostic = pd.DataFrame([calibration_diagnostics(y_test, champion_probability)])
    slices = slice_metrics(x_test, y_test, champion_probability, ids_test)
    bootstrap = stratified_bootstrap_delta(
        y_test,
        champion_probability,
        logistic_probability,
        ids_test,
        repeats=200 if quick else 2_000,
        seed=seed,
    )
    scenarios = scenario_summary(
        ids_test,
        champion_probability,
        x_test["MonthlyCharges"],
        budget_fraction=0.10,
    )
    errors = _error_cases(x_test, y_test, champion_probability, ids_test)

    importance_result = permutation_importance(
        final_champion,
        x_test,
        y_test,
        scoring="average_precision",
        n_repeats=5 if quick else 30,
        random_state=seed,
        n_jobs=-1,
    )
    importance = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance_mean": importance_result.importances_mean,
            "importance_std": importance_result.importances_std,
        }
    ).sort_values("importance_mean", ascending=False)

    model_path = model_dir / "champion.joblib"
    metadata = {
        "artifact_version": "1.0.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "champion_model": champion_name,
        "calibration": champion_calibration,
        "complexity_gate_decision": complexity_decision,
        "feature_columns": FEATURE_COLUMNS,
        "dataset_sha256": DATA_SHA256,
        "split_manifest_sha256": split_meta["sha256"],
        "split_seed": seed,
        "development_rows": len(x_development),
        "test_rows": len(x_test),
        "benchmark_protocol": "v1",
        "test_metrics": champion_metrics,
        "budget_10pct": budget[budget["budget_fraction"].eq(0.10)].iloc[0].to_dict(),
        "best_params": json.loads(
            benchmark[benchmark["model"].eq(champion_name)]["best_params_json"].iloc[0]
        ),
        "mlflow_run_ids": mlflow_run_ids,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "limitations": [
            "IBM sample is small/fictitious and has no timestamp for out-of-time validation.",
            "No treatment/control outcomes; business value is scenario-based, not causal uplift.",
            "Probabilities are not validated for a real telecom population.",
        ],
    }
    bundle = {"model": final_champion, "metadata": metadata}
    joblib.dump(bundle, model_path)
    (model_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=float), encoding="utf-8"
    )

    predictions = pd.DataFrame(
        {
            "anonymous_customer_id": ids_test.map(anonymize_customer_id),
            "actual_churn": y_test,
            "champion_probability": champion_probability,
            "logistic_probability": logistic_probability,
        }
    )
    benchmark.to_csv(output_dir / "benchmark_table.csv", index=False)
    calibration.to_csv(output_dir / "calibration_candidates.csv", index=False)
    budget.to_csv(output_dir / "budget_metrics.csv", index=False)
    reliability.to_csv(output_dir / "reliability_table.csv", index=False)
    calibration_diagnostic.to_csv(output_dir / "calibration_diagnostics.csv", index=False)
    slices.to_csv(output_dir / "slice_metrics.csv", index=False)
    bootstrap.to_csv(output_dir / "bootstrap_delta.csv", index=False)
    scenarios.to_csv(output_dir / "scenario_summary.csv", index=False)
    errors.to_csv(output_dir / "error_cases.csv", index=False)
    importance.to_csv(output_dir / "permutation_importance.csv", index=False)
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    _save_plots(
        y_test,
        champion_probability,
        logistic_probability,
        ids_test,
        reliability,
        importance,
        output_dir,
    )
    report = _benchmark_report(benchmark, calibration, budget, bootstrap, scenarios, metadata)
    (output_dir / "BENCHMARK_REPORT.md").write_text(report, encoding="utf-8")
    champion_run_id = _mlflow_run(
        "champion_calibrated",
        {"model": champion_name, "calibration": champion_calibration},
        {
            **{f"test_{key}": value for key, value in champion_metrics.items()},
            **{
                f"budget_10pct_{key}": value
                for key, value in metadata["budget_10pct"].items()
                if isinstance(value, (int, float)) and np.isfinite(value)
            },
        },
        split_hash=str(split_meta["sha256"]),
    )
    metadata["champion_mlflow_run_id"] = champion_run_id
    bundle["metadata"] = metadata
    joblib.dump(bundle, model_path)
    (model_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=float), encoding="utf-8"
    )
    with mlflow.start_run(run_id=champion_run_id):
        mlflow.log_artifact(str(model_path), artifact_path="model_bundle")
        mlflow.log_artifact(str(output_dir / "BENCHMARK_REPORT.md"), artifact_path="evaluation")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/Telco-Customer-Churn.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/benchmark"))
    parser.add_argument("--model-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--quick", action="store_true", help="Run a smaller smoke benchmark")
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    metadata = run_training(
        arguments.data,
        arguments.output,
        arguments.model_dir,
        quick=arguments.quick,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
