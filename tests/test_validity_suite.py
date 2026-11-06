"""R00 identities and the R01 machinery (runbook §4, §9.1-9.2).

The full R01 gate is a research job with a declared budget (1,000 worlds per
scenario).  These tests cover what must hold regardless of budget: the
identities are exact, the generators match their declared truth, the gate
refuses to pass on a smoke-sized run, and the negative controls are wired so
that they actually break.
"""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.validity_suite import (
    COVERAGE_LOWER_BOUND,
    DELTA_MIN,
    SCENARIOS,
    ValidityReport,
    run_r00,
    run_r01,
    simulate_world,
)

_BY_ID = {spec.scenario_id: spec for spec in SCENARIOS}


# -- R00 --------------------------------------------------------------------
def test_every_declared_identity_holds_exactly() -> None:
    results = run_r00()
    assert len(results) == 6
    failures = [result for result in results if not result.passed]
    assert not failures, [(result.identity_id, result.detail) for result in failures]


def test_each_identity_reports_its_own_evidence() -> None:
    for result in run_r00():
        assert result.detail, f"{result.identity_id} passed without saying why"


# -- generators match their declared truth ----------------------------------
@pytest.mark.parametrize("scenario_id", ["V01", "V02", "V03", "V04", "V05", "V06", "B01", "V07"])
def test_the_generator_reproduces_the_declared_population_contrast(scenario_id: str) -> None:
    """Average the finite-frame truth over draws; it must find the declared value."""

    spec = _BY_ID[scenario_id]
    truths = [
        simulate_world(spec, np.random.default_rng([99, index]))["finite_truth"]
        for index in range(40)
    ]
    mean = float(np.mean(truths))
    spread = float(np.std(truths, ddof=1) / np.sqrt(len(truths)))
    assert mean == pytest.approx(spec.true_contrast, abs=max(4 * spread, 1e-6))


def test_v03_has_a_zero_average_effect_but_a_positive_policy_value() -> None:
    """The scenario that separates a weak null from a policy contrast."""

    spec = _BY_ID["V03"]
    world = simulate_world(spec, np.random.default_rng(5))
    assert world["finite_truth"] > 0
    assert spec.true_contrast == pytest.approx(0.005)


def test_v04_uses_a_stratum_varying_design_probability() -> None:
    world = simulate_world(_BY_ID["V04"], np.random.default_rng(7))
    shares = world["design"]["contact"].unique()
    assert sorted(round(float(value), 3) for value in shares) == [0.2, 0.8]


def test_v05_is_rare_and_imbalanced() -> None:
    world = simulate_world(_BY_ID["V05"], np.random.default_rng(11))
    assert world["events"] / _BY_ID["V05"].n_units < 0.02
    assert world["treatment"].mean() > 0.85


def test_v06_shares_the_treatment_draw_inside_a_cluster() -> None:
    world = simulate_world(_BY_ID["V06"], np.random.default_rng(13))
    cluster = world["cluster"]
    treatment = world["treatment"]
    assert cluster is not None
    for index in range(20):
        members = treatment[cluster == index]
        assert len(set(members.tolist())) == 1, "a cluster must share its assignment"


def test_the_boundary_scenario_sits_at_the_declared_margin() -> None:
    assert _BY_ID["B01"].true_contrast == pytest.approx(DELTA_MIN)


def test_v07_rewards_are_continuous_and_not_winsorised() -> None:
    world = simulate_world(_BY_ID["V07"], np.random.default_rng(17))
    reward = world["reward"]
    assert reward.min() < 0 < reward.max()
    assert float(np.abs(reward).max()) > 3.0, "a heavy tail must actually produce tails"


# -- gate semantics ---------------------------------------------------------
def test_a_smoke_sized_run_can_never_pass_the_gate() -> None:
    report = run_r01(worlds=5, scenarios=["V01"], include_identities=False)
    assert report.worlds < 1_000
    assert report.gate_passed is False
    assert report.status == "SMOKE_ONLY"


def test_the_gate_fails_when_an_identity_fails() -> None:
    report = run_r01(worlds=5, scenarios=["V01"], include_identities=True)
    report.worlds = 1_000  # pretend the budget was met
    report.identities[0] = type(report.identities[0])(
        identity_id="I1", title="broken", passed=False, detail="planted"
    )
    assert report.identities_passed is False
    assert report.gate_passed is False


def test_the_gate_fails_on_an_undercovering_mode() -> None:
    report = run_r01(worlds=5, scenarios=["V01"], include_identities=False)
    report.worlds = 1_000
    # Start from a clean slate: a tiny run has wide Wilson bounds everywhere,
    # which would mask the one failure being planted here.
    for summary in report.summaries:
        summary.coverage_ci_low = 0.99
    assert report.coverage_failures() == []
    report.summaries[0].coverage_ci_low = 0.5
    assert [item.mode for item in report.coverage_failures()] == [report.summaries[0].mode]
    assert report.gate_passed is False


def test_negative_controls_are_scored_but_never_gated() -> None:
    report = run_r01(worlds=8, scenarios=["V04", "V06"], include_identities=False)
    variants = {summary.variant for summary in report.summaries}
    assert "ipw_constant_propensity_negative_control" in variants
    assert "dr_constant_propensity_negative_control" in variants
    assert "iid_negative_control" in variants
    for summary in report.summaries:
        summary.coverage_ci_low = 0.0 if summary.variant.endswith("negative_control") else 0.99
    failures = report.coverage_failures()
    assert failures == [], "a negative control must not fail the gate"


def test_a_constant_propensity_breaks_ipw_and_double_robustness_absorbs_it() -> None:
    """The V04 control has to misbehave, or it is not a control."""

    report = run_r01(worlds=40, scenarios=["V04"], include_identities=False)
    by_variant = {summary.variant: summary for summary in report.summaries}
    broken = by_variant["ipw_constant_propensity_negative_control"]
    absorbed = by_variant["dr_constant_propensity_negative_control"]
    assert abs(broken.bias_vs_finite_frame) > 100 * broken.mc_se
    assert broken.coverage < 0.2
    # Same wrong propensity, but a correct outcome model: the contrast survives.
    assert abs(absorbed.bias_vs_finite_frame) < 5 * absorbed.mc_se


def test_clustering_breaks_the_iid_interval() -> None:
    report = run_r01(worlds=60, scenarios=["V06"], include_identities=False)
    by_key = {(summary.mode, summary.variant): summary for summary in report.summaries}
    for mode in ("ipw", "dr_correct", "dr_misspecified"):
        clustered = by_key[(mode, "cluster_robust")]
        iid = by_key[(mode, "iid_negative_control")]
        assert iid.coverage < clustered.coverage, mode
        assert iid.mean_ci_width < clustered.mean_ci_width, mode


def test_the_report_names_what_it_did_not_run() -> None:
    report = run_r01(worlds=3, scenarios=["V01"], include_identities=False)
    payload = report.to_dict()
    assert set(payload["not_run"]) == {"V08_batch_cap", "V09_two_stage_recruitment"}
    assert "G06" in payload["not_run"]["V08_batch_cap"]
    assert payload["scenarios_run"] == ["V01"]
    assert len(payload["scenarios_declared"]) == len(SCENARIOS)


def test_an_unknown_scenario_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown scenario"):
        run_r01(worlds=2, scenarios=["V99"], include_identities=False)


def test_thresholds_match_the_plan() -> None:
    assert COVERAGE_LOWER_BOUND == 0.92
    empty = ValidityReport(worlds=1_000, seed=1, started_at="now")
    assert empty.gate_passed is True, "no scored mode means nothing failed"
    assert empty.status == "PASS"


def test_a_scenario_draws_the_same_worlds_whatever_else_is_requested() -> None:
    """Seeding is keyed on scenario identity, not on position in the run.

    Position-keyed seeding meant `--scenarios V03` and a full run scored V03
    on different worlds, so two runs of the same frozen generator were not
    comparable. That defeats the purpose of freezing it.
    """

    alone = run_r01(worlds=10, scenarios=["V03"], include_identities=False)
    together = run_r01(worlds=10, scenarios=["V01", "V03", "V05"], include_identities=False)
    left = next(s for s in alone.summaries if s.scenario_id == "V03" and s.mode == "dr_correct")
    right = next(s for s in together.summaries if s.scenario_id == "V03" and s.mode == "dr_correct")
    assert left.coverage == right.coverage
    assert left.bias_vs_finite_frame == right.bias_vs_finite_frame
    assert left.mean_ci_width == right.mean_ci_width


def test_the_cohort_size_can_be_swept_without_touching_the_mechanism() -> None:
    """A declared sample-size sweep changes n and nothing else."""

    small = run_r01(worlds=6, scenarios=["V03"], include_identities=False, n_units=2_000)
    large = run_r01(worlds=6, scenarios=["V03"], include_identities=False, n_units=8_000)
    left = next(s for s in small.summaries if s.mode == "dr_correct")
    right = next(s for s in large.summaries if s.mode == "dr_correct")
    # Same declared truth, more units, so a narrower interval.
    assert left.true_contrast == right.true_contrast
    assert right.mean_ci_width < left.mean_ci_width


# -- V09 two-stage recruitment ---------------------------------------------
def test_v09_recruitment_only_variance_is_a_negative_control_that_breaks() -> None:
    """The recruitment-only interval must under-cover, or G03 had no point."""

    from telco_churn.recruitment_validation import run_v09

    report = run_v09(worlds=40, seed=20260921)
    by_role = {}
    for item in report.readouts:
        by_role.setdefault(item.is_negative_control, []).append(item)

    controls = by_role[True]
    primaries = by_role[False]
    assert controls and primaries

    # At q = 1 the recruitment-only standard error is exactly zero, so the
    # interval is a point and covers a noisy target essentially never.
    boundary = [item for item in controls if item.q_design.startswith("q=1")]
    assert boundary, "the q=1 boundary cell must be scored"
    for item in boundary:
        assert item.mean_ci_width == 0.0
        assert item.coverage < 0.1

    # Every recruitment-only readout must be narrower than its superpopulation
    # counterpart: that is the whole claim.
    for control in controls:
        match = next(
            item
            for item in primaries
            if item.study == control.study and item.q_design == control.q_design
        )
        assert control.mean_ci_width < match.mean_ci_width


def test_v09_seeding_is_stable_across_processes() -> None:
    """String hash() is per-process randomised; the namespace must not use it."""

    from telco_churn.recruitment_validation import run_v09

    first = run_v09(worlds=6, seed=7)
    second = run_v09(worlds=6, seed=7)
    assert [item.coverage for item in first.readouts] == [item.coverage for item in second.readouts]
    assert [item.bias for item in first.readouts] == [item.bias for item in second.readouts]


def test_v09_gate_needs_both_a_covering_primary_and_a_broken_control() -> None:
    from telco_churn.recruitment_validation import run_v09

    report = run_v09(worlds=6, seed=3)
    assert report.gate_passed is False, "six worlds can never satisfy the gate"
    payload = report.to_dict()
    assert payload["status"] == "SMOKE_ONLY"
    assert "negative controls" in payload["scope_note"]
