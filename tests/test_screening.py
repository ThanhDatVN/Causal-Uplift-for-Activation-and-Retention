"""R02 screening harness: the gate, the protocol, the failure bookkeeping (WP09).

The point of these tests is not which candidate wins -- that is R02's output,
not its contract.  They check that the stage cannot start behind a failed
evaluator gate, that every candidate is scored on the same folds, that a
failed fit is recorded rather than dropped, and that the shortlist takes one
representative per family instead of filling a quota.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from telco_churn.screening import (
    BASELINE_ID,
    CAPACITY_FRACTION,
    OUTER_FOLDS,
    CohortDesign,
    ScreeningReport,
    _licensed_asymmetry,
    assert_gate_open,
    gate_status,
    render_markdown,
    run_screening,
)


def _cohort(n: int = 1200, *, seed: int = 5):
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        {
            "recency": rng.integers(1, 12, n).astype(float),
            "log1p_history": rng.normal(5.0, 1.0, n),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Web", "Phone"], n),
        }
    )
    treatment = rng.integers(0, 2, n)
    probability = np.clip(
        0.10 + 0.08 * (features["recency"].to_numpy() < 6) * treatment, 0.01, 0.95
    )
    reward = (rng.random(n) < probability).astype(float)
    unit_id = [f"u{index}" for index in range(n)]
    return features, treatment, reward, unit_id


def _write_gate(tmp_path, *, passed: bool, method: str = "skewness_adjusted_t") -> None:
    target = tmp_path / "reports/v4/validity"
    target.mkdir(parents=True, exist_ok=True)
    (target / "validity_suite.json").write_text(
        json.dumps(
            {
                "gate_passed": passed,
                "status": "PASS" if passed else "FAIL",
                "worlds_per_scenario": 1000,
                "interval_method": method,
                "coverage_failures": [] if passed else ["V05:dr_correct:primary"],
                "promotion_failures": [],
            }
        ),
        encoding="utf-8",
    )
    if passed:
        _write_boundary(tmp_path, method=method)


# -- the gate --------------------------------------------------------------
def test_screening_refuses_to_run_when_the_gate_failed(tmp_path) -> None:
    _write_gate(tmp_path, passed=False)
    with pytest.raises(RuntimeError, match="gated on R01"):
        assert_gate_open(tmp_path)


def test_screening_refuses_to_run_when_no_gate_artifact_exists(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="no R01 artifact"):
        assert_gate_open(tmp_path)


def test_the_gate_opens_once_r01_passes(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    passed, detail = gate_status(tmp_path)
    assert passed is True
    assert "skewness_adjusted_t" in detail and "1000 worlds" in detail


def test_the_failed_gate_message_names_the_failing_readouts(tmp_path) -> None:
    _write_gate(tmp_path, passed=False)
    _, detail = gate_status(tmp_path)
    assert "1 undercovering" in detail


def test_a_forced_run_is_stamped_as_ungated(tmp_path) -> None:
    _write_gate(tmp_path, passed=False)
    features, treatment, reward, unit_id = _cohort(600)
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        require_gate=False,
        candidates=["M01", "M05"],
    )
    assert "GATE NOT PASSED" in report.gate_detail
    assert "GATE NOT PASSED" in json.dumps(report.to_dict())


# -- the protocol ----------------------------------------------------------
@pytest.fixture
def screened(tmp_path):
    _write_gate(tmp_path, passed=True)
    features, treatment, reward, unit_id = _cohort()
    return run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01", "M03", "M05", "M07"],
    )


def test_every_candidate_is_scored_on_the_same_number_of_folds(screened) -> None:
    for result in screened.completed:
        assert len(result.fold_values) == OUTER_FOLDS, result.candidate_id


def test_the_baseline_is_its_own_zero(screened) -> None:
    baseline = next(r for r in screened.results if r.candidate_id == BASELINE_ID)
    assert baseline.mean_delta_vs_baseline == 0.0
    assert baseline.fold_deltas_vs_baseline == [0.0] * OUTER_FOLDS


def test_deltas_are_paired_across_the_same_folds(screened) -> None:
    baseline = next(r for r in screened.results if r.candidate_id == BASELINE_ID)
    other = next(r for r in screened.completed if r.candidate_id != BASELINE_ID)
    expected = [
        candidate - base
        for candidate, base in zip(other.fold_values, baseline.fold_values, strict=True)
    ]
    assert other.fold_deltas_vs_baseline == pytest.approx(expected)


def test_the_cap_is_respected_on_every_fold(screened) -> None:
    for result in screened.completed:
        for selected, total in zip(result.n_selected, result.n_selected, strict=True):
            assert selected <= total  # the allocator's own cap check is in test_a13
        assert all(count > 0 for count in result.n_selected)


def test_the_report_records_the_cohort_and_the_protocol(screened) -> None:
    payload = screened.to_dict()
    assert payload["protocol"]["capacity_fraction"] == CAPACITY_FRACTION
    assert payload["protocol"]["split"].startswith("development only")
    assert payload["cohort"]["n_events"] > 0
    assert "not confirmatory" in payload["scope_note"]


# -- failure bookkeeping ---------------------------------------------------
def test_a_candidate_that_cannot_fit_is_recorded_not_dropped(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    features, treatment, reward, unit_id = _cohort(400)
    # A DR learner with an impossible propensity fails; it must still appear.
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=0.0,
        root=tmp_path,
        candidates=["M01", "M07"],
        require_gate=False,
    )
    failed = {result.candidate_id: result for result in report.failed}
    assert "M07" in failed
    assert failed["M07"].status == "FIT_FAILED"
    assert "propensity" in failed["M07"].error
    assert "M07" in json.dumps(report.to_dict()), "a failure stays in the report"


def test_an_unknown_candidate_is_recorded_rather_than_silently_skipped(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    features, treatment, reward, unit_id = _cohort(300)
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01", "M99"],
    )
    assert any(result.status == "UNKNOWN_CANDIDATE" for result in report.results)


# -- the shortlist ---------------------------------------------------------
def test_the_shortlist_takes_one_representative_per_family(screened) -> None:
    assert len(screened.shortlist) <= 3
    families = {
        result.family for result in screened.completed if result.candidate_id in screened.shortlist
    }
    # outcome_ranking, one of s/t, and dr: never two from the same slot.
    assert len(families) == len(screened.shortlist)


def test_an_empty_family_is_left_empty(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    features, treatment, reward, unit_id = _cohort(500)
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01"],  # only the outcome-ranking family
    )
    assert report.shortlist == ["M01"], "no filling the quota from another family"


def test_the_markdown_names_the_gate_and_every_candidate(screened) -> None:
    rendered = render_markdown(screened)
    assert "Gate:" in rendered
    for result in screened.results:
        assert result.candidate_id in rendered
    assert "not a confirmation result" in rendered


def test_an_empty_report_renders_without_a_shortlist() -> None:
    report = ScreeningReport(
        dataset="none",
        started_at="now",
        gate_detail="n/a",
        capacity_fraction=0.2,
        outer_folds=3,
        n_units=0,
        n_treated=0,
        n_events=0,
        propensity=0.5,
    )
    assert "none" in render_markdown(report)


# -- the validated design region -------------------------------------------
def _write_region_gate(tmp_path, *, validated_imbalance=0.3, failing_imbalance=0.4) -> None:
    """A gate that failed overall but validated part of the design space."""

    target = tmp_path / "reports/v4/validity_confirm"
    target.mkdir(parents=True, exist_ok=True)
    (target / "validity_suite.json").write_text(
        json.dumps(
            {
                "gate_passed": False,
                "status": "FAIL",
                "worlds_per_scenario": 2000,
                "interval_method": "skewness_adjusted_t",
                "coverage_failures": ["V05:dr_correct:primary"],
                "promotion_failures": [],
                "validated_design_region": {
                    "validated_scenarios": ["V01", "V03", "V04", "V05B"],
                    "failing_scenarios": ["V05"],
                    "max_propensity_imbalance_validated": validated_imbalance,
                    "min_event_rate_validated": 0.005,
                    "smallest_failing_imbalance": failing_imbalance,
                },
            }
        ),
        encoding="utf-8",
    )


def test_a_balanced_cohort_opens_the_gate_inside_the_validated_region(tmp_path) -> None:
    _write_region_gate(tmp_path)
    passed, detail = gate_status(tmp_path, cohort_propensity=0.4987)
    assert passed is True
    assert "inside the region validated by" in detail
    assert "V05B" in detail


def test_an_imbalanced_cohort_stays_blocked(tmp_path) -> None:
    _write_region_gate(tmp_path)
    passed, detail = gate_status(tmp_path, cohort_propensity=0.9)
    assert passed is False
    assert "not inside the validated region" in detail


def test_a_cohort_that_declares_nothing_gets_the_whole_gate_verdict(tmp_path) -> None:
    """Silence is not consent: no declared design means no regional licence."""

    _write_region_gate(tmp_path)
    passed, _ = gate_status(tmp_path, cohort_propensity=None)
    assert passed is False


def test_the_region_cannot_license_past_the_smallest_failing_design(tmp_path) -> None:
    """If the failing scenario is no worse than the validated ones, no licence."""

    _write_region_gate(tmp_path, validated_imbalance=0.4, failing_imbalance=0.4)
    passed, _ = gate_status(tmp_path, cohort_propensity=0.5)
    assert passed is False


def test_a_whole_gate_pass_does_not_license_an_unvalidated_propensity(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    passed, detail = gate_status(tmp_path, cohort_propensity=0.9)
    assert passed is False
    assert "PASS" in detail


def test_the_gate_reads_the_best_powered_artifact(tmp_path) -> None:
    """A later, smaller run must not override an earlier, larger one."""

    _write_region_gate(tmp_path)  # 2000 worlds, in validity_confirm
    small = tmp_path / "reports/v4/validity"
    small.mkdir(parents=True, exist_ok=True)
    (small / "validity_suite.json").write_text(
        json.dumps(
            {
                "gate_passed": False,
                "status": "FAIL",
                "worlds_per_scenario": 200,
                "interval_method": "normal",
                "coverage_failures": ["V01:ipw:primary"],
                "promotion_failures": [],
            }
        ),
        encoding="utf-8",
    )
    _, detail = gate_status(tmp_path, cohort_propensity=0.5)
    assert "2000 worlds" in detail


# -- the measured boundary licence -----------------------------------------
def _write_boundary(tmp_path, *, threshold=0.202, separates=True, method="skewness_adjusted_t"):
    target = tmp_path / "reports/v4/overlap_boundary"
    target.mkdir(parents=True, exist_ok=True)
    (target / "overlap_boundary.json").write_text(
        json.dumps(
            {
                "study": "overlap_boundary_sweep",
                "worlds_per_cell": 1000,
                "boundary_by_asymmetry": {
                    method: {
                        "method": method,
                        "n_cells": 18,
                        "n_failing": 7,
                        "largest_passing_asymmetry": threshold,
                        "smallest_failing_asymmetry": threshold + 0.01,
                        "separates": separates,
                        "straddling_cells": [] if separates else [{"propensity": 0.8}],
                        "licensed_threshold": threshold if separates else None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_a_declared_design_inside_the_measured_boundary_is_licensed(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path)
    design = CohortDesign(
        n_units=34_092, propensity=0.4987, event_rate=302 / 34_092, acted_fraction=0.2
    )
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is True
    assert "asymmetry index" in detail and "measured to cover" in detail


def test_a_declared_design_outside_the_measured_boundary_is_refused(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path)
    design = CohortDesign(n_units=10_000, propensity=0.9, event_rate=0.005, acted_fraction=0.5)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is False
    assert "exceeds" in detail


def test_the_measured_rule_governs_even_when_it_is_the_stricter_one(tmp_path) -> None:
    """The point of the change: imbalance alone licenses a cohort A refuses.

    A design balanced enough to clear ``imbalance <= 0.30`` can still be far
    outside the measured region once its event rate and frame size are taken
    into account.  The old rule would wave it through.
    """

    _write_region_gate(tmp_path)
    _write_boundary(tmp_path)
    rare = CohortDesign(n_units=2_000, propensity=0.75, event_rate=0.002, acted_fraction=0.2)
    assert abs(0.75 - 0.5) <= 0.30, "the imbalance rule would license this cohort"
    assert gate_status(tmp_path, cohort_propensity=0.75)[0] is True
    passed, detail = gate_status(tmp_path, cohort_design=rare)
    assert passed is False, "the measured rule must override the weaker one"
    assert "exceeds" in detail


def test_no_sweep_means_no_measured_licence(tmp_path) -> None:
    _write_region_gate(tmp_path)
    design = CohortDesign(n_units=10_000, propensity=0.5, event_rate=0.05)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is False
    assert "no boundary sweep on disk" in detail


def test_a_sweep_that_found_no_ordering_licenses_nothing(tmp_path) -> None:
    """If A did not separate the sweep's own cells, it is not a rule."""

    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, separates=False)
    design = CohortDesign(n_units=10_000, propensity=0.5, event_rate=0.05)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is False
    assert "does not order" in detail


def test_a_sweep_for_another_interval_method_does_not_transfer(tmp_path) -> None:
    _write_region_gate(tmp_path)  # the gate ran skewness_adjusted_t
    _write_boundary(tmp_path, method="normal")
    design = CohortDesign(n_units=10_000, propensity=0.5, event_rate=0.05)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is False
    assert "did not score" in detail


def test_a_design_with_no_overlap_is_refused_rather_than_crashing(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path)
    design = CohortDesign(n_units=10_000, propensity=0.0, event_rate=0.05)
    assert design.asymmetry_index == float("inf")
    assert design.to_dict()["asymmetry_index"] is None
    assert gate_status(tmp_path, cohort_design=design)[0] is False


def test_a_whole_gate_pass_still_checks_a_supplied_design(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    design = CohortDesign(n_units=100, propensity=0.99, event_rate=0.001, acted_fraction=0.2)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is False
    assert "PASS" in detail and "exceeds" in detail


def test_a_whole_gate_pass_licenses_an_in_region_design(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    design = CohortDesign(n_units=10_000, propensity=0.5, event_rate=0.05)
    passed, detail = gate_status(tmp_path, cohort_design=design)
    assert passed is True
    assert "measured to cover" in detail


def test_the_screening_report_records_the_design_it_was_licensed_on(tmp_path) -> None:
    _write_gate(tmp_path, passed=True)
    features, treatment, reward, unit_id = _cohort(600)
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01"],
    )
    declared = report.to_dict()["cohort"]["declared_design"]
    assert declared is not None
    assert declared["acted_fraction"] == CAPACITY_FRACTION
    assert declared["asymmetry_index"] is not None


def test_the_declared_rate_is_the_rarer_tail_not_the_mean(tmp_path) -> None:
    """A mostly-one reward is rare in its zeros; the index must see that."""

    _write_gate(tmp_path, passed=True)
    features, treatment, _, unit_id = _cohort(600)
    rng = np.random.default_rng(3)
    mostly_one = (rng.random(600) > 0.02).astype(float)  # 2% zeros
    report = run_screening(
        features,
        treatment,
        mostly_one,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01"],
    )
    declared = report.to_dict()["cohort"]["declared_design"]
    assert declared["event_rate"] < 0.1, "0.98 would have been the wrong rate"


# -- disclosing method selection -------------------------------------------
def _write_sized_gate(tmp_path, folder, *, worlds, passed, method):
    target = tmp_path / "reports/v4" / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / "validity_suite.json").write_text(
        json.dumps(
            {
                "gate_passed": passed,
                "status": "PASS" if passed else "FAIL",
                "worlds_per_scenario": worlds,
                "interval_method": method,
                "coverage_failures": [] if passed else ["V05:dr_correct:primary"],
                "promotion_failures": [],
            }
        ),
        encoding="utf-8",
    )


def test_a_pass_chosen_over_an_equally_powered_failure_says_so(tmp_path) -> None:
    """Preferring the passing method at equal power is choosing after looking."""

    _write_sized_gate(
        tmp_path, "validity_confirm", worlds=2000, passed=False, method="skewness_adjusted_t"
    )
    _write_sized_gate(
        tmp_path, "validity_unshrunk", worlds=2000, passed=True, method="skewness_adjusted_t"
    )
    _write_boundary(tmp_path)
    passed, detail = gate_status(tmp_path)
    assert passed is True
    assert "SELECTED AFTER LOOKING" in detail
    assert "validity_confirm" in detail
    assert "needs independent confirmation" in detail


def test_a_better_powered_pass_needs_no_such_warning(tmp_path) -> None:
    _write_sized_gate(
        tmp_path, "validity_confirm", worlds=1000, passed=False, method="skewness_adjusted_t"
    )
    _write_sized_gate(
        tmp_path, "validity_unshrunk", worlds=2000, passed=True, method="skewness_adjusted_t"
    )
    passed, detail = gate_status(tmp_path)
    assert passed is True
    assert "SELECTED AFTER LOOKING" not in detail


def test_agreeing_runs_at_equal_power_need_no_warning(tmp_path) -> None:
    _write_sized_gate(
        tmp_path, "validity_confirm", worlds=2000, passed=True, method="skewness_adjusted_t"
    )
    _write_sized_gate(tmp_path, "validity_unshrunk", worlds=2000, passed=True, method="normal")
    _, detail = gate_status(tmp_path)
    assert "SELECTED AFTER LOOKING" not in detail


def test_the_warning_survives_into_a_forced_screening_report(tmp_path) -> None:
    _write_sized_gate(
        tmp_path, "validity_confirm", worlds=2000, passed=False, method="skewness_adjusted_t"
    )
    _write_sized_gate(
        tmp_path, "validity_unshrunk", worlds=2000, passed=True, method="skewness_adjusted_t"
    )
    _write_boundary(tmp_path)
    features, treatment, reward, unit_id = _cohort(400)
    report = run_screening(
        features,
        treatment,
        reward,
        unit_id,
        dataset="fixture",
        propensity=float(treatment.mean()),
        root=tmp_path,
        candidates=["M01"],
    )
    assert "SELECTED AFTER LOOKING" in json.dumps(report.to_dict())


# -- the out-of-sample ceiling ---------------------------------------------
def _write_transfer(tmp_path, rows) -> None:
    """rows: (target_asymmetry, passes) pairs for the constant arm."""

    target = tmp_path / "reports/v4/asymmetry_transfer"
    target.mkdir(parents=True, exist_ok=True)
    (target / "asymmetry_transfer.json").write_text(
        json.dumps(
            {
                "study": "asymmetry_index_transfer",
                "worlds_per_design": 1000,
                "results": [
                    {
                        "arm": "constant_propensity",
                        "target_asymmetry": value,
                        "passes": ok,
                    }
                    for value, ok in rows
                ],
            }
        ),
        encoding="utf-8",
    )


def test_the_transfer_study_tightens_a_sweep_that_was_too_generous(tmp_path) -> None:
    """The sweep is the grid the index was fitted on; the transfer study is not."""

    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.584)
    _write_transfer(tmp_path, [(0.10, False), (0.20, False), (0.55, False)])
    threshold, why = _licensed_asymmetry(tmp_path, "skewness_adjusted_t")
    assert threshold < 0.10
    assert threshold == np.nextafter(0.10, -np.inf)
    assert "tightened from 0.584" in why


def test_a_transfer_study_that_agrees_leaves_the_sweep_alone(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.20)
    _write_transfer(tmp_path, [(0.10, True), (0.20, True), (0.55, False)])
    threshold, why = _licensed_asymmetry(tmp_path, "skewness_adjusted_t")
    assert threshold == 0.20
    assert "tightened" not in why
    assert "transfer study covered every design" in why


def test_the_sweep_governs_when_no_transfer_study_has_run(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.584)
    threshold, why = _licensed_asymmetry(tmp_path, "skewness_adjusted_t")
    assert threshold == 0.584
    assert "transfer" not in why


def test_a_cohort_between_the_two_thresholds_is_now_refused(tmp_path) -> None:
    """The regression this exists to prevent: licensing on the fitted grid."""

    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.584)
    _write_transfer(tmp_path, [(0.10, False), (0.55, False)])
    between = CohortDesign(n_units=10_000, propensity=0.70, event_rate=0.005, acted_fraction=0.5)
    assert 0.10 < between.asymmetry_index < 0.584
    assert gate_status(tmp_path, cohort_design=between)[0] is False


def test_a_cohort_far_below_every_observed_failure_is_still_licensed(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.584)
    _write_transfer(tmp_path, [(0.10, False), (0.55, False)])
    hillstrom = CohortDesign(
        n_units=34_092, propensity=0.4987, event_rate=302 / 34_092, acted_fraction=0.2
    )
    assert hillstrom.asymmetry_index < 0.01
    assert gate_status(tmp_path, cohort_design=hillstrom)[0] is True


def test_an_unreadable_transfer_artifact_does_not_silently_widen_the_licence(tmp_path) -> None:
    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.20)
    target = tmp_path / "reports/v4/asymmetry_transfer"
    target.mkdir(parents=True, exist_ok=True)
    (target / "asymmetry_transfer.json").write_text("{not json", encoding="utf-8")
    threshold, _ = _licensed_asymmetry(tmp_path, "skewness_adjusted_t")
    assert threshold == 0.20  # falls back to the sweep, never above it


def test_the_out_of_scope_arm_is_not_counted_as_evidence(tmp_path) -> None:
    """Only the constant-propensity arm is in scope for the index."""

    _write_region_gate(tmp_path)
    _write_boundary(tmp_path, threshold=0.20)
    target = tmp_path / "reports/v4/asymmetry_transfer"
    target.mkdir(parents=True, exist_ok=True)
    (target / "asymmetry_transfer.json").write_text(
        json.dumps(
            {
                "worlds_per_design": 1000,
                "results": [
                    {"arm": "constant_propensity", "target_asymmetry": 0.20, "passes": True},
                    {"arm": "varying_propensity", "target_asymmetry": 0.05, "passes": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    threshold, _ = _licensed_asymmetry(tmp_path, "skewness_adjusted_t")
    assert threshold == 0.20, "the declared out-of-scope arm must not set the ceiling"
