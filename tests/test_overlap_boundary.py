"""The overlap boundary sweep: generator, grid and boundary extraction.

The sweep itself is a research job with a declared budget.  These tests cover
what has to hold regardless of budget: the generator hits the event rate and
propensity it claims, the grid is seeded per cell so a cell is reproducible on
its own, and the boundary summary reports the crossing rather than hiding it.
"""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.overlap_boundary import (
    EVENT_RATES,
    N_UNITS,
    PROPENSITIES,
    BoundaryReport,
    CellResult,
    _draw,
    run_sweep,
)


# -- the generator ---------------------------------------------------------
@pytest.mark.parametrize("rate", EVENT_RATES)
def test_the_generator_hits_the_declared_event_rate(rate: float) -> None:
    """p0 = rate * (0.2 + 1.6 sigmoid(...)) averages to rate by symmetry."""

    observed = [
        _draw(rate, 0.5, np.random.default_rng([1, index]))["events"] / N_UNITS
        for index in range(12)
    ]
    assert float(np.mean(observed)) == pytest.approx(rate, rel=0.15)


@pytest.mark.parametrize("propensity", PROPENSITIES)
def test_the_generator_hits_the_declared_propensity(propensity: float) -> None:
    world = _draw(0.035, propensity, np.random.default_rng(4))
    treated = (world["action"] == "contact").mean()
    assert treated == pytest.approx(propensity, abs=0.02)


def test_every_probability_stays_feasible_without_clipping() -> None:
    """The effect is a fraction of the rate, so p0 - tau never leaves [0, 1]."""

    for rate in EVENT_RATES:
        for propensity in PROPENSITIES:
            world = _draw(rate, propensity, np.random.default_rng(7))
            treated_mean = world["means"]["contact"].to_numpy()
            control_mean = world["means"]["hold"].to_numpy()
            assert ((treated_mean >= 0) & (treated_mean <= 1)).all()
            assert ((control_mean >= 0) & (control_mean <= 1)).all()


def test_imbalance_shrinks_the_control_arm() -> None:
    balanced = _draw(0.035, 0.5, np.random.default_rng(9))["control_events"]
    skewed = _draw(0.035, 0.95, np.random.default_rng(9))["control_events"]
    assert skewed < balanced / 5, "an e=0.95 design leaves very few control events"


def test_the_policy_only_acts_on_half_the_frame() -> None:
    world = _draw(0.035, 0.5, np.random.default_rng(11))
    acted = (world["policy_1"] != world["policy_0"]).mean()
    assert acted == pytest.approx(0.5, abs=0.03)
    assert world["finite_truth"] > 0


# -- the sweep -------------------------------------------------------------
def test_a_cell_is_reproducible_on_its_own() -> None:
    """Seeding is keyed on the cell, not on its position in the grid."""

    full = run_sweep(worlds=6, propensities=(0.5, 0.9), event_rates=(0.035,), methods=("normal",))
    alone = run_sweep(worlds=6, propensities=(0.9,), event_rates=(0.035,), methods=("normal",))
    from_full = next(c for c in full.cells if c.propensity == 0.9)
    assert from_full.coverage == alone.cells[0].coverage
    assert from_full.bias == alone.cells[0].bias


def test_the_grid_covers_every_requested_combination() -> None:
    report = run_sweep(
        worlds=4,
        propensities=(0.5, 0.8),
        event_rates=(0.005, 0.035),
        methods=("normal", "skewness_adjusted_t"),
    )
    assert len(report.cells) == 2 * 2 * 2
    assert {c.imbalance for c in report.cells} == {0.0, 0.3}


def test_skewness_grows_with_imbalance() -> None:
    """The mechanism behind the boundary, measured rather than asserted."""

    report = run_sweep(
        worlds=8, propensities=(0.5, 0.8, 0.95), event_rates=(0.035,), methods=("normal",)
    )
    by_imbalance = {c.imbalance: c.mean_score_skewness for c in report.cells}
    assert by_imbalance[0.0] < by_imbalance[0.3] < by_imbalance[0.45]
    assert set(by_imbalance) == {0.0, 0.3, 0.45}, "imbalance must be a clean key"


# -- the boundary summary --------------------------------------------------
def _cell(imbalance: float, *, coverage: float, method: str = "normal") -> CellResult:
    return CellResult(
        propensity=0.5 + imbalance,
        imbalance=imbalance,
        event_rate=0.035,
        method=method,
        worlds=1000,
        coverage=coverage,
        coverage_ci_low=coverage - 0.015,
        coverage_ci_high=coverage + 0.013,
        width_ratio=1.0,
        mean_score_skewness=0.0,
        mean_control_events=100.0,
        bias=0.0,
        mc_se=0.001,
    )


def test_the_boundary_names_the_crossing() -> None:
    report = BoundaryReport(worlds=1000, seed=1, started_at="now")
    report.cells = [
        _cell(0.0, coverage=0.950),
        _cell(0.2, coverage=0.948),
        _cell(0.4, coverage=0.900),
    ]
    entry = report.boundary_by_rate()["normal@0.035"]
    assert entry["largest_passing_imbalance"] == 0.2
    assert entry["smallest_failing_imbalance"] == 0.4
    assert entry["all_pass"] is False


def test_a_method_that_never_fails_is_reported_as_such() -> None:
    report = BoundaryReport(worlds=1000, seed=1, started_at="now")
    report.cells = [_cell(value, coverage=0.950) for value in (0.0, 0.2, 0.4)]
    entry = report.boundary_by_rate()["normal@0.035"]
    assert entry["all_pass"] is True
    assert entry["smallest_failing_imbalance"] is None


def test_the_report_refuses_to_generalise_beyond_its_generator() -> None:
    report = run_sweep(worlds=3, propensities=(0.5,), event_rates=(0.035,), methods=("normal",))
    note = report.to_dict()["scope_note"]
    assert "not a general theorem" in note


# -- the asymmetry index ---------------------------------------------------
def test_the_index_is_zero_at_a_balanced_design() -> None:
    report = run_sweep(worlds=3, propensities=(0.5,), event_rates=(0.005,), methods=("normal",))
    assert report.cells[0].asymmetry_index == pytest.approx(0.0, abs=1e-12)


def test_the_index_orders_cells_that_imbalance_cannot() -> None:
    """Same imbalance, different event rate: A tells them apart, imbalance cannot."""

    report = run_sweep(
        worlds=3, propensities=(0.8,), event_rates=(0.005, 0.035), methods=("normal",)
    )
    rare, common = sorted(report.cells, key=lambda c: c.event_rate)
    assert rare.imbalance == common.imbalance, "imbalance is blind to the event rate"
    assert rare.asymmetry_index > common.asymmetry_index


def test_the_summary_reports_whether_the_index_separates_rather_than_claiming_it() -> None:
    report = BoundaryReport(worlds=1000, seed=1, started_at="now")
    report.cells = [
        _cell(0.0, coverage=0.950),
        _cell(0.2, coverage=0.948),
        _cell(0.4, coverage=0.900),
    ]
    entry = report.boundary_by_asymmetry()["normal"]
    assert entry["separates"] is True
    assert entry["licensed_threshold"] == entry["largest_passing_asymmetry"]
    assert entry["n_failing"] == 1


def test_a_straddling_cell_is_named_and_the_licence_withheld() -> None:
    """If a passing cell sits above a failing one, A is not a usable rule."""

    report = BoundaryReport(worlds=1000, seed=1, started_at="now")
    # 0.2 fails while the more asymmetric 0.4 passes: no clean crossing.
    report.cells = [
        _cell(0.0, coverage=0.950),
        _cell(0.2, coverage=0.900),
        _cell(0.4, coverage=0.950),
    ]
    entry = report.boundary_by_asymmetry()["normal"]
    assert entry["separates"] is False
    assert entry["licensed_threshold"] is None
    assert entry["straddling_cells"], "the offending cells must be named"


def test_the_artifact_carries_the_index_for_every_cell() -> None:
    report = run_sweep(worlds=3, propensities=(0.5, 0.9), event_rates=(0.005,), methods=("normal",))
    payload = report.to_dict()
    assert payload["acted_fraction"] == 0.5
    assert all("asymmetry_index" in cell for cell in payload["cells"])
    assert "boundary_by_asymmetry" in payload
