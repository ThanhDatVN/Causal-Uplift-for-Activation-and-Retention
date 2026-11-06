"""Assignment-integrity diagnostics on synthetic designs (session 3).

The Orange file is not redistributed, so these tests use two synthetic designs
with a known answer: one truly randomized, one where a covariate drives
assignment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.assignment_audit import (
    SUPPORT_THRESHOLDS,
    audit_assignment,
    cross_fitted_propensity,
)


def _randomized(
    n: int = 1200, *, share: float = 0.75, seed: int = 4
) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"x{i}" for i in range(6)])
    treatment = (rng.uniform(size=n) < share).astype(int)
    return features, treatment


def _confounded(n: int = 1200, seed: int = 4) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"x{i}" for i in range(6)])
    logit = 1.2 + 2.0 * features["x0"] - 1.5 * features["x1"]
    probability = 1.0 / (1.0 + np.exp(-logit))
    treatment = (rng.uniform(size=n) < probability).astype(int)
    return features, treatment


def test_cross_fitting_leaves_a_randomized_design_unpredictable() -> None:
    features, treatment = _randomized()
    propensity = cross_fitted_propensity(features, treatment, folds=3, seed=1)
    from sklearn.metrics import roc_auc_score

    assert roc_auc_score(treatment, propensity) == pytest.approx(0.5, abs=0.06)


def test_a_covariate_driven_design_is_detected() -> None:
    features, treatment = _confounded()
    report = audit_assignment(features, treatment, folds=3, permutations=9, seed=2)
    assert report["treatment_predictability"]["oof_roc_auc"] > 0.75
    assert report["permutation_test"]["p_value_add_one"] <= 0.1
    assert report["treatment_predictability"]["log_loss_improvement"] > 0


def test_a_randomized_design_is_not_flagged() -> None:
    features, treatment = _randomized()
    report = audit_assignment(features, treatment, folds=3, permutations=9, seed=2)
    assert report["permutation_test"]["p_value_add_one"] > 0.05
    assert abs(report["treatment_predictability"]["log_loss_improvement"]) < 0.02


def test_the_permutation_p_value_is_never_zero() -> None:
    features, treatment = _confounded()
    report = audit_assignment(features, treatment, folds=3, permutations=4, seed=2)
    permutation = report["permutation_test"]
    assert permutation["p_value_add_one"] >= 1 / (permutation["permutations"] + 1)
    assert permutation["p_value_add_one"] > 0


def test_support_and_effective_sample_size_are_reported() -> None:
    features, treatment = _confounded()
    report = audit_assignment(features, treatment, folds=3, permutations=2, seed=2)
    propensity = report["estimated_propensity"]
    thresholds = [row["min_action_propensity"] for row in propensity["support"]]
    assert tuple(thresholds) == SUPPORT_THRESHOLDS
    # A design driven by covariates pushes some units out of support.
    assert propensity["support"][0]["n_outside_support"] > 0
    assert propensity["effective_sample_size_estimated_e"] > 0
    assert propensity["effective_sample_size_constant_e"] > 0


def test_the_report_states_what_it_cannot_settle() -> None:
    features, treatment = _randomized()
    report = audit_assignment(features, treatment, folds=3, permutations=2, seed=2)
    limits = " ".join(report["interpretation_limits"])
    assert "not distinguishable" in limits
    assert "does not demonstrate" in limits


def test_inputs_are_validated() -> None:
    features, treatment = _randomized(200)
    with pytest.raises(ValueError, match="same length"):
        audit_assignment(features, treatment[:100], folds=2, permutations=1)
    with pytest.raises(ValueError, match="binary"):
        audit_assignment(features, np.full(len(features), 2), folds=2, permutations=1)


def test_extreme_weights_are_flagged_as_an_unusable_repair() -> None:
    """ESS collapse means estimating e(X) relocates the problem into the variance."""

    from telco_churn.assignment_audit import _ess_verdict

    collapsed = _ess_verdict(
        {
            "estimated_propensity": {
                "effective_sample_size_estimated_e": 4.0,
                "effective_sample_size_constant_e": 8743.0,
            }
        }
    )
    assert collapsed["ess_collapsed"] is True
    assert collapsed["reweighting_is_a_usable_repair"] is False
    assert "not a repair" in collapsed["note"]

    healthy = _ess_verdict(
        {
            "estimated_propensity": {
                "effective_sample_size_estimated_e": 8000.0,
                "effective_sample_size_constant_e": 8743.0,
            }
        }
    )
    assert healthy["ess_collapsed"] is False
    assert "remain assumptions" in healthy["note"]
