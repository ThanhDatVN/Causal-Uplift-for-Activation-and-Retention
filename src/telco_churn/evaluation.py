"""Evaluation metrics, uncertainty, budget curves, and slice reporting."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

DEFAULT_BUDGETS = (0.05, 0.10, 0.20, 0.30)


def probability_metrics(y_true: Iterable[int], probability: Iterable[float]) -> dict[str, float]:
    y = np.asarray(y_true, dtype=int)
    score = np.asarray(probability, dtype=float)
    prediction = (score >= 0.5).astype(int)
    prevalence = float(y.mean())
    reference_brier = float(np.mean((y - prevalence) ** 2))
    brier = float(brier_score_loss(y, score))
    return {
        "average_precision": float(average_precision_score(y, score)),
        "roc_auc": float(roc_auc_score(y, score)),
        "brier_score": brier,
        "brier_skill_score": float(1 - brier / reference_brier),
        "log_loss": float(log_loss(y, score, labels=[0, 1])),
        "accuracy_at_0_5": float(accuracy_score(y, prediction)),
        "precision_at_0_5": float(precision_score(y, prediction, zero_division=0)),
        "recall_at_0_5": float(recall_score(y, prediction, zero_division=0)),
        "f1_at_0_5": float(f1_score(y, prediction, zero_division=0)),
        "prevalence": prevalence,
    }


def top_k_indices(
    probability: Iterable[float],
    customer_ids: Iterable[str],
    budget_fraction: float,
) -> np.ndarray:
    if not 0 < budget_fraction <= 1:
        raise ValueError("budget_fraction must be in (0, 1]")
    score = np.asarray(probability, dtype=float)
    ids = np.asarray(customer_ids, dtype=str)
    if score.size != ids.size:
        raise ValueError("probability and customer_ids must have equal length")
    k = max(1, math.ceil(score.size * budget_fraction))
    order = np.lexsort((ids, -score))
    return order[:k]


def budget_metrics(
    y_true: Iterable[int],
    probability: Iterable[float],
    customer_ids: Iterable[str],
    budgets: Iterable[float] = DEFAULT_BUDGETS,
) -> pd.DataFrame:
    y = np.asarray(y_true, dtype=int)
    score = np.asarray(probability, dtype=float)
    ids = np.asarray(customer_ids, dtype=str)
    positives = int(y.sum())
    prevalence = float(y.mean())
    rows: list[dict[str, Any]] = []
    for budget in budgets:
        selected = top_k_indices(score, ids, budget)
        true_positives = int(y[selected].sum())
        precision = true_positives / len(selected)
        recall = true_positives / positives if positives else math.nan
        rows.append(
            {
                "budget_fraction": float(budget),
                "k": len(selected),
                "true_positives": true_positives,
                "precision_at_budget": precision,
                "recall_at_budget": recall,
                "lift_at_budget": precision / prevalence if prevalence else math.nan,
                "contacts_per_captured_churner": (
                    len(selected) / true_positives if true_positives else math.inf
                ),
            }
        )
    return pd.DataFrame(rows)


def reliability_table(
    y_true: Iterable[int], probability: Iterable[float], bins: int = 10
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "target": np.asarray(y_true, dtype=int),
            "probability": np.asarray(probability, dtype=float),
        }
    )
    try:
        frame["bin"] = pd.qcut(frame["probability"], q=bins, duplicates="drop")
    except ValueError:
        frame["bin"] = pd.cut(frame["probability"], bins=bins, duplicates="drop")
    return (
        frame.groupby("bin", observed=True)
        .agg(
            n=("target", "size"),
            mean_predicted=("probability", "mean"),
            observed_rate=("target", "mean"),
        )
        .reset_index()
        .assign(bin=lambda item: item["bin"].astype(str))
    )


def calibration_diagnostics(
    y_true: Iterable[int], probability: Iterable[float], bins: int = 10
) -> dict[str, float]:
    """Return calibration-in-the-large, slope, and equal-frequency ECE diagnostics."""
    y = np.asarray(y_true, dtype=int)
    score = np.asarray(probability, dtype=float)
    clipped = np.clip(score, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    recalibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=2_000).fit(logits, y)
    table = reliability_table(y, score, bins=bins)
    absolute_gap = (table["observed_rate"] - table["mean_predicted"]).abs()
    return {
        "calibration_intercept": float(recalibrator.intercept_[0]),
        "calibration_slope": float(recalibrator.coef_[0, 0]),
        "ece_equal_frequency": float((table["n"] / len(y) * absolute_gap).sum()),
        "max_calibration_error": float(absolute_gap.max()),
        "ece_bins": bins,
    }


def slice_metrics(
    features: pd.DataFrame,
    y_true: Iterable[int],
    probability: Iterable[float],
    customer_ids: Iterable[str],
    columns: Iterable[str] = ("gender", "SeniorCitizen", "Contract", "InternetService"),
    budget_fraction: float = 0.10,
) -> pd.DataFrame:
    y = np.asarray(y_true, dtype=int)
    score = np.asarray(probability, dtype=float)
    ids = np.asarray(customer_ids, dtype=str)
    globally_selected = set(top_k_indices(score, ids, budget_fraction).tolist())
    rows: list[dict[str, Any]] = []
    for column in columns:
        for level in sorted(features[column].astype(str).unique()):
            mask = features[column].astype(str).eq(level).to_numpy()
            indices = np.flatnonzero(mask)
            slice_y = y[indices]
            slice_score = score[indices]
            selected_count = sum(int(index in globally_selected) for index in indices)
            row: dict[str, Any] = {
                "feature": column,
                "level": level,
                "n": int(mask.sum()),
                "positives": int(slice_y.sum()),
                "prevalence": float(slice_y.mean()),
                "brier_score": float(brier_score_loss(slice_y, slice_score)),
                "selection_rate_at_global_10pct": selected_count / len(indices),
            }
            row["average_precision"] = (
                float(average_precision_score(slice_y, slice_score))
                if len(np.unique(slice_y)) == 2
                else math.nan
            )
            row["roc_auc"] = (
                float(roc_auc_score(slice_y, slice_score))
                if len(np.unique(slice_y)) == 2
                else math.nan
            )
            selected_positive = sum(
                int(y[index]) for index in indices if index in globally_selected
            )
            row["recall_at_global_10pct"] = (
                selected_positive / int(slice_y.sum()) if slice_y.sum() else math.nan
            )
            rows.append(row)
    return pd.DataFrame(rows)


def stratified_bootstrap_delta(
    y_true: Iterable[int],
    champion_probability: Iterable[float],
    baseline_probability: Iterable[float],
    customer_ids: Iterable[str],
    *,
    repeats: int = 2_000,
    seed: int = 20260913,
) -> pd.DataFrame:
    y = np.asarray(y_true, dtype=int)
    champion = np.asarray(champion_probability, dtype=float)
    baseline = np.asarray(baseline_probability, dtype=float)
    ids = np.asarray(customer_ids, dtype=str)
    positive_indices = np.flatnonzero(y == 1)
    negative_indices = np.flatnonzero(y == 0)
    rng = np.random.default_rng(seed)
    records: list[tuple[float, float, float]] = []
    for _ in range(repeats):
        sample = np.concatenate(
            [
                rng.choice(positive_indices, size=len(positive_indices), replace=True),
                rng.choice(negative_indices, size=len(negative_indices), replace=True),
            ]
        )
        rng.shuffle(sample)
        sample_y = y[sample]
        champion_budget = budget_metrics(
            sample_y, champion[sample], ids[sample], budgets=(0.10,)
        ).iloc[0]
        baseline_budget = budget_metrics(
            sample_y, baseline[sample], ids[sample], budgets=(0.10,)
        ).iloc[0]
        records.append(
            (
                average_precision_score(sample_y, champion[sample])
                - average_precision_score(sample_y, baseline[sample]),
                brier_score_loss(sample_y, champion[sample])
                - brier_score_loss(sample_y, baseline[sample]),
                champion_budget["recall_at_budget"] - baseline_budget["recall_at_budget"],
            )
        )
    samples = pd.DataFrame(
        records,
        columns=["average_precision_delta", "brier_score_delta", "recall_at_10pct_delta"],
    )
    summary = []
    for column in samples.columns:
        summary.append(
            {
                "metric_delta_champion_minus_logistic": column,
                "mean": samples[column].mean(),
                "ci95_low": samples[column].quantile(0.025),
                "ci95_high": samples[column].quantile(0.975),
                "bootstrap_repeats": repeats,
            }
        )
    return pd.DataFrame(summary)
