import numpy as np

from telco_churn.evaluation import (
    budget_metrics,
    calibration_diagnostics,
    probability_metrics,
    top_k_indices,
)


def test_top_k_uses_stable_customer_id_tie_break() -> None:
    selected = top_k_indices([0.8, 0.8, 0.1], ["B", "A", "C"], 1 / 3)
    assert selected.tolist() == [1]


def test_budget_metrics_have_expected_recall_precision_and_lift() -> None:
    table = budget_metrics(
        [1, 0, 1, 0],
        [0.9, 0.8, 0.2, 0.1],
        ["a", "b", "c", "d"],
        budgets=(0.5,),
    ).iloc[0]
    assert table["k"] == 2
    assert table["precision_at_budget"] == 0.5
    assert table["recall_at_budget"] == 0.5
    assert table["lift_at_budget"] == 1.0


def test_good_probabilities_beat_prevalence_brier() -> None:
    metrics = probability_metrics([0, 0, 1, 1], [0.05, 0.2, 0.8, 0.95])
    assert metrics["average_precision"] == 1.0
    assert metrics["brier_skill_score"] > 0
    assert np.isfinite(list(metrics.values())).all()


def test_calibration_diagnostics_are_finite_and_bounded() -> None:
    diagnostics = calibration_diagnostics(
        [0, 0, 0, 1, 1, 1],
        [0.05, 0.20, 0.35, 0.55, 0.75, 0.90],
        bins=3,
    )
    assert np.isfinite(list(diagnostics.values())).all()
    assert diagnostics["calibration_slope"] > 0
    assert 0 <= diagnostics["ece_equal_frequency"] <= 1
