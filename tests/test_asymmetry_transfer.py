"""The transfer study: the solver, the matching, and honest prediction scoring.

The study exists to try to break the asymmetry index, so the thing worth
testing is that it *can* report a break.  A prediction-scorer that returns
``held: True`` whatever the data would make the whole study decorative, so
most of these tests feed it results it must call falsified.
"""

from __future__ import annotations

import pytest

from telco_churn.asymmetry_transfer import (
    DESIGN_FAMILIES,
    TARGET_ASYMMETRY,
    TransferReport,
    TransferResult,
    render_markdown,
    run_transfer,
    solve_propensity,
)
from telco_churn.policy_comparison import design_asymmetry_index


# -- the solver ------------------------------------------------------------
@pytest.mark.parametrize("target", TARGET_ASYMMETRY)
@pytest.mark.parametrize("family", DESIGN_FAMILIES, ids=lambda f: f[0])
def test_every_shipped_design_reaches_its_target(target, family) -> None:
    """A row in the table must actually have the A it claims."""

    _label, n_units, acted, rate = family
    propensity = solve_propensity(target, n_units=n_units, acted_fraction=acted, event_rate=rate)
    assert propensity is not None, "the shipped grid must be feasible"
    realised = abs(
        design_asymmetry_index(
            n_units=n_units, propensity=propensity, event_rate=rate, acted_fraction=acted
        )
    )
    assert realised == pytest.approx(target, rel=1e-4)


def test_an_unreachable_target_returns_none_rather_than_a_fake_row() -> None:
    """A huge frame with plenty of events cannot be made that asymmetric."""

    assert solve_propensity(50.0, n_units=10_000_000, acted_fraction=1.0, event_rate=0.5) is None


def test_the_solver_stays_on_the_upper_branch() -> None:
    """A is symmetric about 0.5; the solver must not return the mirror root."""

    for target in TARGET_ASYMMETRY:
        propensity = solve_propensity(target, n_units=10_000, acted_fraction=0.5, event_rate=0.005)
        assert propensity > 0.5


def test_the_product_is_what_the_solver_sees() -> None:
    """n, h and rate enter only through their product, so equal products tie."""

    shared = {
        "baseline": (10_000, 0.5, 0.005),
        "narrow": (10_000, 0.25, 0.010),
        "whole": (10_000, 1.0, 0.0025),
        "small": (2_500, 0.5, 0.020),
    }
    solved = {
        name: solve_propensity(0.3, n_units=n, acted_fraction=h, event_rate=r)
        for name, (n, h, r) in shared.items()
    }
    assert len(set(solved.values())) == 1, solved


def test_the_shipped_grid_spans_more_than_one_product() -> None:
    """Permuting within one product would not test the product claim itself."""

    products = {round(n * h * r, 6) for _label, n, h, r in DESIGN_FAMILIES}
    assert len(products) >= 3
    assert max(products) / min(products) >= 10


# -- prediction scoring, the part that must be able to say "no" ------------
def _result(**overrides) -> TransferResult:
    base = {
        "arm": "constant_propensity",
        "family": "baseline",
        "target_asymmetry": 0.10,
        "realised_asymmetry": 0.10,
        "n_units": 10_000,
        "acted_fraction": 0.5,
        "event_rate": 0.005,
        "propensity": 0.62,
        "worlds": 1000,
        "coverage": 0.950,
        "coverage_ci_low": 0.935,
        "coverage_ci_high": 0.963,
        "mean_skewness": 9.0,
        "bias": 0.0,
        "mc_se": 1e-6,
    }
    base.update(overrides)
    return TransferResult(**base)


def _report(*results: TransferResult) -> TransferReport:
    report = TransferReport(worlds=1000, seed=1, started_at="now")
    report.results = list(results)
    return report


def test_p1_is_falsified_when_matched_designs_disagree() -> None:
    report = _report(
        _result(family="baseline", coverage=0.950),
        _result(family="small_frame", coverage=0.880),
    )
    scored = report.score_p1_transfer()
    assert scored["held"] is False
    assert scored["levels"]["A=0.1"]["agrees"] is False


def test_p1_holds_when_matched_designs_agree() -> None:
    report = _report(
        _result(family="baseline", coverage=0.950),
        _result(family="small_frame", coverage=0.948),
    )
    assert report.score_p1_transfer()["held"] is True


def test_p1_ignores_a_level_with_only_one_design() -> None:
    """One design cannot disagree with itself; it must not count as support."""

    report = _report(_result(family="baseline", coverage=0.80))
    assert report.score_p1_transfer()["levels"] == {}


def test_p2_is_falsified_when_a_licensed_design_fails() -> None:
    report = _report(_result(target_asymmetry=0.10, coverage=0.880, coverage_ci_low=0.860))
    scored = report.score_p2_threshold()
    assert scored["held"] is False


def test_p2_is_falsified_when_an_unlicensed_design_covers() -> None:
    report = _report(_result(target_asymmetry=0.55, coverage=0.950, coverage_ci_low=0.935))
    assert report.score_p2_threshold()["held"] is False


def test_p2_holds_on_the_pattern_it_predicts() -> None:
    report = _report(
        _result(target_asymmetry=0.20, coverage=0.948, coverage_ci_low=0.933),
        _result(target_asymmetry=0.55, coverage=0.900, coverage_ci_low=0.880),
    )
    assert report.score_p2_threshold()["held"] is True


def test_p3_is_falsified_when_the_varying_arm_does_not_undercover() -> None:
    report = _report(
        _result(arm="constant_propensity", coverage=0.949),
        _result(arm="varying_propensity", coverage=0.951),
    )
    scored = report.score_p3_out_of_scope()
    assert scored["held"] is False
    assert scored["comparisons"][0]["undercovers"] is False


def test_p3_needs_a_varying_arm_to_hold_at_all() -> None:
    """With no out-of-scope arm there is no evidence, so it cannot 'hold'."""

    assert _report(_result()).score_p3_out_of_scope()["held"] is False


def test_p3_holds_when_the_varying_arm_breaks() -> None:
    report = _report(
        _result(arm="constant_propensity", coverage=0.950),
        _result(arm="varying_propensity", coverage=0.860),
    )
    assert report.score_p3_out_of_scope()["held"] is True


def test_the_summary_flag_requires_every_prediction() -> None:
    report = _report(
        _result(arm="constant_propensity", coverage=0.950),
        _result(arm="varying_propensity", coverage=0.951),
    )
    assert report.to_dict()["all_predictions_held"] is False


# -- the run ---------------------------------------------------------------
def test_a_design_is_reproducible_on_its_own() -> None:
    """Seeding is keyed on the cell, not on its position in the loop."""

    families = (("baseline", 2_000, 0.5, 0.02), ("small_frame", 1_000, 0.5, 0.04))
    full = run_transfer(worlds=5, targets=(0.3,), families=families)
    alone = run_transfer(worlds=5, targets=(0.3,), families=families[1:])
    from_full = next(
        r for r in full.results if r.family == "small_frame" and r.arm == "constant_propensity"
    )
    assert from_full.coverage == alone.results[0].coverage


def test_the_out_of_scope_arm_is_run_and_labelled() -> None:
    report = run_transfer(worlds=4, targets=(0.3,), families=(("baseline", 2_000, 0.5, 0.02),))
    arms = {r.arm for r in report.results}
    assert arms == {"constant_propensity", "varying_propensity"}


def test_the_varying_arm_really_is_more_skewed() -> None:
    """The mechanism behind P3, measured rather than asserted."""

    report = run_transfer(worlds=12, targets=(0.55,), families=(("baseline", 10_000, 0.5, 0.005),))
    constant = next(r for r in report.results if r.arm == "constant_propensity")
    varying = next(r for r in report.results if r.arm == "varying_propensity")
    assert abs(varying.mean_skewness) > abs(constant.mean_skewness)


def test_an_infeasible_design_is_recorded_not_dropped() -> None:
    report = run_transfer(worlds=3, targets=(9.0,), families=(("huge", 100_000, 1.0, 0.4),))
    assert report.results == []
    assert report.infeasible and "cannot reach" in report.infeasible[0]["reason"]


def test_the_artifact_records_the_realised_index_not_only_the_target() -> None:
    report = run_transfer(worlds=3, targets=(0.3,), families=(("baseline", 2_000, 0.5, 0.02),))
    payload = report.to_dict()
    for entry in payload["results"]:
        assert entry["realised_asymmetry"] == pytest.approx(entry["target_asymmetry"], rel=1e-3)


def test_the_markdown_names_every_prediction_and_its_verdict() -> None:
    report = run_transfer(worlds=3, targets=(0.3,), families=(("baseline", 2_000, 0.5, 0.02),))
    rendered = render_markdown(report)
    for name in ("P1_transfer", "P2_threshold", "P3_out_of_scope"):
        assert name in rendered
    assert "out-of-scope" in rendered


def test_the_scope_note_declares_the_out_of_scope_arm() -> None:
    report = run_transfer(worlds=3, targets=(0.3,), families=(("baseline", 2_000, 0.5, 0.02),))
    note = report.to_dict()["scope_note"]
    assert "declared out-of-scope control" in note
