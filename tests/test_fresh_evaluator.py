"""Checks for the new-family evaluator stress protocol."""

import numpy as np

from telco_churn.fresh_evaluator import (
    SCENARIOS,
    draw_world,
    family_false_failure_bound,
    run,
)


def test_new_family_has_a_known_null_and_variable_assignment() -> None:
    null = draw_world(SCENARIOS[0], n_units=1_000, rng=np.random.default_rng(1))
    varying = draw_world(SCENARIOS[2], n_units=1_000, rng=np.random.default_rng(2))
    assert null[-1] == 0.0
    assert np.allclose(null[2]["contact"], 0.85)
    assert varying[2]["contact"].min() < 0.3
    assert varying[2]["contact"].max() > 0.7
    assert varying[-1] > 0


def test_smoke_cannot_promote_evidence_and_is_reproducible() -> None:
    first = run(worlds=4, n_units=500)
    second = run(worlds=4, n_units=500)
    assert first["status"] == "SMOKE_ONLY"
    assert first["release_gate"] == "NOT_EVALUATED"
    assert first["cellwise_diagnostic_pass"] is None
    assert first["readouts"] == second["readouts"]


def test_second_family_contains_harm_and_has_known_positive_net_truth() -> None:
    piecewise = draw_world(SCENARIOS[5], n_units=10_000, rng=np.random.default_rng(3))
    null = draw_world(SCENARIOS[3], n_units=10_000, rng=np.random.default_rng(3))
    assert null[-1] == 0.0
    assert piecewise[-1] > 0
    assert np.all(np.isin(piecewise[2]["contact"].unique(), [0.12, 0.88]))
    assert family_false_failure_bound(worlds=2_000, n_coverage=6, n_null=2) < 0.05
