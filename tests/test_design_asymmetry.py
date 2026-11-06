"""The closed-form design asymmetry index, checked against the estimator.

This is the one place in the repo where a formula claims to predict a measured
quantity, so the tests do not merely exercise the arithmetic: they simulate,
score with the real DR code path, and compare.  The contract is the tolerance.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from telco_churn.policy_comparison import (
    _gather,
    design_asymmetry_index,
    dr_action_scores,
)
from telco_churn.problem_contract import ContractViolation
from telco_churn.validity_suite import _sigmoid

N = 10_000


def _measured_skewness(propensity: float, *, seed: int, worlds: int = 6) -> float:
    """Realised skewness of the paired DR mean on the V05 generator."""

    values = []
    for index in range(worlds):
        rng = np.random.default_rng([seed, index])
        x1 = rng.integers(0, 2, size=N)
        rng.integers(0, 2, size=N)  # keep the stream aligned with V05
        z = rng.standard_normal(N)
        p0 = 0.001 + 0.008 * _sigmoid(0.8 * (2 * x1 - 1) + 0.5 * z)
        tau = np.full(N, 0.0005)
        treatment = (rng.random(N) < propensity).astype(int)
        reward = 1.0 - (rng.random(N) < p0 - tau * treatment).astype(float)
        design = pd.DataFrame(
            {"hold": np.full(N, 1 - propensity), "contact": np.full(N, propensity)}
        )
        mean = pd.DataFrame({"hold": 1 - p0, "contact": 1 - (p0 - tau)})
        scores = dr_action_scores(reward, np.where(treatment == 1, "contact", "hold"), design, mean)
        paired = _gather(scores, np.where(x1 == 1, "contact", "hold")) - _gather(
            scores, np.full(N, "hold")
        )
        centred = paired - paired.mean()
        values.append(float(np.mean(centred**3) / np.mean(centred**2) ** 1.5) / math.sqrt(N))
    return float(np.mean(values))


# -- the property the formula exists for -----------------------------------
def test_a_balanced_design_is_predicted_to_be_symmetric() -> None:
    """(1 - 2e) is exactly zero at e = 0.5, however rare the outcome."""

    for rate in (0.5, 0.05, 0.005, 0.0005):
        assert design_asymmetry_index(
            n_units=N, propensity=0.5, event_rate=rate, acted_fraction=0.5
        ) == pytest.approx(0.0, abs=1e-12)


def test_a_balanced_design_really_is_symmetric() -> None:
    """The prediction above, measured: rarity alone does not skew the mean."""

    assert abs(_measured_skewness(0.5, seed=7)) < 0.02


@pytest.mark.parametrize(
    ("propensity", "tolerance"),
    [(0.6, 0.35), (0.7, 0.35), (0.8, 0.30), (0.9, 0.25), (0.95, 0.25)],
)
def test_the_formula_tracks_the_measured_skewness(propensity: float, tolerance: float) -> None:
    """Predicted and realised agree in magnitude to within the stated band.

    The spike model drops the augmentation term, so it over-predicts by a
    roughly constant factor; the tolerance is the honest width of that gap,
    not a band widened until the test passed.
    """

    predicted = design_asymmetry_index(
        n_units=N, propensity=propensity, event_rate=0.005, acted_fraction=0.5
    )
    measured = _measured_skewness(propensity, seed=7)
    assert abs(measured) == pytest.approx(abs(predicted), rel=tolerance)
    assert abs(measured) < abs(predicted), "the spike model is an upper bound here"


def test_the_prediction_is_monotone_in_imbalance() -> None:
    values = [
        abs(design_asymmetry_index(n_units=N, propensity=e, event_rate=0.005, acted_fraction=0.5))
        for e in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
    ]
    assert values == sorted(values)
    assert values[0] == 0.0


def test_rarity_and_sample_size_enter_only_as_amplifiers() -> None:
    """n, rate and acted_fraction appear only through their product."""

    base = design_asymmetry_index(n_units=N, propensity=0.9, event_rate=0.005, acted_fraction=0.5)
    for scaled in (
        design_asymmetry_index(
            n_units=2 * N, propensity=0.9, event_rate=0.0025, acted_fraction=0.5
        ),
        design_asymmetry_index(n_units=N, propensity=0.9, event_rate=0.01, acted_fraction=0.25),
        design_asymmetry_index(n_units=N // 2, propensity=0.9, event_rate=0.01, acted_fraction=0.5),
    ):
        assert scaled == pytest.approx(base)


def test_four_times_the_data_halves_the_asymmetry() -> None:
    base = design_asymmetry_index(n_units=N, propensity=0.9, event_rate=0.005)
    bigger = design_asymmetry_index(n_units=4 * N, propensity=0.9, event_rate=0.005)
    assert bigger == pytest.approx(base / 2)


# -- the designs the repo actually ran -------------------------------------
def test_the_shipped_designs_land_where_the_documents_say() -> None:
    """V05 is the failing design; Hillstrom's primary is nowhere near it."""

    v05 = design_asymmetry_index(n_units=N, propensity=0.9, event_rate=0.005, acted_fraction=0.5)
    hillstrom = design_asymmetry_index(
        n_units=34_092, propensity=0.4987, event_rate=302 / 34_092, acted_fraction=0.2
    )
    assert abs(v05) == pytest.approx(0.533, abs=0.01)
    assert abs(hillstrom) < 0.01
    assert abs(hillstrom) < abs(v05) / 100


# -- the contract ----------------------------------------------------------
@pytest.mark.parametrize("propensity", [0.0, 1.0, -0.1, 1.2])
def test_a_degenerate_propensity_is_refused(propensity: float) -> None:
    with pytest.raises(ContractViolation, match="propensity"):
        design_asymmetry_index(n_units=N, propensity=propensity, event_rate=0.01)


def test_an_impossible_event_rate_is_refused() -> None:
    with pytest.raises(ContractViolation, match="event_rate"):
        design_asymmetry_index(n_units=N, propensity=0.5, event_rate=1.5)


def test_an_empty_frame_is_refused() -> None:
    with pytest.raises(ContractViolation, match="n_units"):
        design_asymmetry_index(n_units=0, propensity=0.5, event_rate=0.01)


def test_a_design_with_no_events_is_infinitely_asymmetric_not_a_crash() -> None:
    assert design_asymmetry_index(n_units=N, propensity=0.9, event_rate=0.0) == float("inf")
