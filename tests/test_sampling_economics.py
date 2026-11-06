"""R08: the sampling design, and the two ways it could be flattered.

The enriched design is the repo's own claimed contribution, so the tests
here are adversarial toward it: the inclusion probabilities must be a real
design (same expected recruitment, nothing dropped), and the comparison must
be at equal precision rather than at equal N, where enrichment wins for free.
"""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.sampling_economics import (
    AGREEMENT_RESERVE,
    COST_MODEL,
    DESIGNS,
    DISAGREEMENT_FRACTIONS,
    FRAME_SIZE,
    MAX_DISAGREEMENT_INCLUSION,
    READOUTS,
    TARGET_RECRUITMENT_SHARE,
    DesignSummary,
    SamplingEconomicsReport,
    _frame,
    inclusion_probabilities,
    render_markdown,
    run_sampling_economics,
)


def _disagrees(fraction: float, n: int = FRAME_SIZE) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    mask[: int(n * fraction)] = True
    return mask


# -- the design ------------------------------------------------------------
@pytest.mark.parametrize("fraction", DISAGREEMENT_FRACTIONS)
def test_both_designs_recruit_the_same_number_in_expectation(fraction: float) -> None:
    """Otherwise the comparison is between budgets, not between designs."""

    mask = _disagrees(fraction)
    for design in DESIGNS:
        probability, _constants = inclusion_probabilities(mask, design)
        assert probability.sum() == pytest.approx(FRAME_SIZE * TARGET_RECRUITMENT_SHARE, rel=1e-6)


@pytest.mark.parametrize("fraction", DISAGREEMENT_FRACTIONS)
def test_the_agreement_region_is_never_dropped(fraction: float) -> None:
    """A design that never looks outside D cannot estimate the frame contrast."""

    probability, constants = inclusion_probabilities(_disagrees(fraction), "enriched")
    assert constants["q_agreement"] > 0
    assert probability[~_disagrees(fraction)].min() > 0


@pytest.mark.parametrize("fraction", DISAGREEMENT_FRACTIONS)
def test_enrichment_never_exceeds_its_declared_ceiling(fraction: float) -> None:
    _probability, constants = inclusion_probabilities(_disagrees(fraction), "enriched")
    assert constants["q_disagreement"] <= MAX_DISAGREEMENT_INCLUSION


def test_enrichment_puts_more_weight_on_the_disagreement_region() -> None:
    for fraction in DISAGREEMENT_FRACTIONS:
        _p, constants = inclusion_probabilities(_disagrees(fraction), "enriched")
        assert constants["q_disagreement"] > constants["q_agreement"]


def test_enrichment_has_less_room_as_disagreement_grows() -> None:
    """At d = 0.5 the formula can barely enrich, and the study must show that."""

    small = inclusion_probabilities(_disagrees(0.05), "enriched")[1]
    large = inclusion_probabilities(_disagrees(0.50), "enriched")[1]
    assert large["q_disagreement"] < small["q_disagreement"]


def test_the_uniform_design_is_flat() -> None:
    probability, _constants = inclusion_probabilities(_disagrees(0.2), "uniform")
    assert set(np.unique(probability)) == {TARGET_RECRUITMENT_SHARE}


def test_a_frame_with_no_disagreement_falls_back_rather_than_dividing_by_zero() -> None:
    probability, constants = inclusion_probabilities(np.zeros(100, dtype=bool), "enriched")
    assert constants.get("degenerate") is True
    assert set(np.unique(probability)) == {TARGET_RECRUITMENT_SHARE}


def test_an_unknown_design_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown design"):
        inclusion_probabilities(_disagrees(0.2), "wishful")


def test_the_reserve_is_what_keeps_the_agreement_region_alive() -> None:
    """q_agree tracks the declared reserve rather than being an accident."""

    _p, constants = inclusion_probabilities(_disagrees(0.20), "enriched")
    assert constants["q_agreement"] == pytest.approx(AGREEMENT_RESERVE, abs=1e-9)


# -- the generator ---------------------------------------------------------
def test_the_effect_lives_where_the_policies_disagree() -> None:
    """Enriching toward a region with no effect would be enriching toward noise."""

    frame = _frame(0.2, np.random.default_rng(1))
    assert frame["finite_truth"] > 0
    assert (frame["policy_1"][frame["disagrees"]] == "contact").all()
    assert (frame["policy_1"][~frame["disagrees"]] == "hold").all()


def test_the_realised_disagreement_share_is_close_to_the_nominal_one() -> None:
    for fraction in DISAGREEMENT_FRACTIONS:
        frame = _frame(fraction, np.random.default_rng(2))
        assert float(frame["disagrees"].mean()) == pytest.approx(fraction, abs=0.02)


# -- the comparison --------------------------------------------------------
@pytest.fixture(scope="module")
def economics():
    return run_sampling_economics(worlds=40, seed=11)


def test_every_design_fraction_and_readout_is_scored(economics) -> None:
    seen = {(row.disagreement_fraction, row.design, row.readout) for row in economics.summaries}
    assert seen == {
        (fraction, design, readout)
        for fraction in DISAGREEMENT_FRACTIONS
        for design in DESIGNS
        for readout, _t, _truth, _c in READOUTS
    }


def test_each_interval_is_scored_against_the_truth_it_targets() -> None:
    """The finite-frame variance treats scores as fixed, so it means the census."""

    by_name = {name: (target, truth) for name, target, truth, _c in READOUTS}
    assert by_name["finite_vs_census"] == ("finite_frame", "census")
    assert by_name["super_vs_effect"] == ("superpopulation", "effect")


def test_the_mismatched_pairing_is_declared_a_control() -> None:
    """Pairing the narrow interval with the effect is the reader's mistake."""

    control = [name for name, _t, _truth, is_control in READOUTS if is_control]
    assert control == ["finite_vs_effect"]


def test_the_control_fires_where_enrichment_makes_it_bite(economics) -> None:
    """Enrichment shrinks recruitment variance until score noise dominates.

    That is exactly where treating the scores as fixed is most wrong, so the
    control is expected to fire for the enriched design and need not for the
    uniform one.
    """

    enriched = [
        row for row in economics.summaries if row.is_negative_control and row.design == "enriched"
    ]
    assert enriched, "the control must be scored for the enriched design"
    assert any(row.coverage < 0.85 for row in enriched)


def test_a_control_is_never_gated(economics) -> None:
    for row in economics.summaries:
        if row.is_negative_control:
            assert row.passes is True


def test_the_realised_recruitment_is_not_forced_to_the_target(economics) -> None:
    """Bernoulli inclusion fluctuates; rounding it back would bias the weights."""

    exact = FRAME_SIZE * TARGET_RECRUITMENT_SHARE
    assert any(row.mean_recruited != exact for row in economics.summaries)


def test_enrichment_recruits_more_from_the_disagreement_region(economics) -> None:
    for fraction in DISAGREEMENT_FRACTIONS:
        rows = {
            row.design: row for row in economics.summaries if row.disagreement_fraction == fraction
        }
        assert (
            rows["enriched"].mean_recruited_in_disagreement
            > rows["uniform"].mean_recruited_in_disagreement
        )


def test_cost_is_priced_from_the_forward_looking_interval(economics) -> None:
    """Pricing the narrow interval would buy precision the design lacks."""

    by_key = {
        (row.disagreement_fraction, row.design): row
        for row in economics.summaries
        if row.readout == "super_vs_effect"
    }
    for entry in economics.to_dict()["cost_at_matched_precision"].values():
        fraction = entry["disagreement_fraction"]
        expected = max(by_key[(fraction, design)].mean_half_width for design in DESIGNS)
        assert entry["target_half_width"] == pytest.approx(expected)


def test_cost_is_compared_at_a_common_precision_not_at_equal_n(economics) -> None:
    """The comparison both designs could be flattered by, done properly."""

    for entry in economics.to_dict()["cost_at_matched_precision"].values():
        target = entry["target_half_width"]
        assert target > 0
        # Both designs are costed against the *same* target.
        assert entry["uniform"]["target_half_width"] == pytest.approx(target)
        assert entry["enriched"]["target_half_width"] == pytest.approx(target)


def test_the_enriched_design_is_charged_for_its_screening(economics) -> None:
    """It has to look at the whole frame to find its region; that is a cost."""

    for entry in economics.to_dict()["cost_at_matched_precision"].values():
        assert entry["enriched"]["n_screened"] >= entry["enriched"]["n_recruited"]
        assert entry["uniform"]["n_screened"] == entry["uniform"]["n_recruited"]


def test_the_report_declares_its_prices_as_declared(economics) -> None:
    payload = economics.to_dict()
    assert "declared prices" in payload["cost_source"]
    assert payload["cost_model"] == COST_MODEL
    assert "not a profit claim" in payload["scope_note"]


def test_undercovering_designs_are_named_rather_than_averaged(economics) -> None:
    payload = economics.to_dict()
    assert isinstance(payload["designs_that_undercover"], list)
    assert payload["all_gated_readouts_cover"] == (not payload["designs_that_undercover"])
    assert all("finite_vs_effect" not in entry for entry in payload["designs_that_undercover"]), (
        "a declared control must never be listed as a failure"
    )


def test_the_markdown_reports_the_regime_where_enrichment_cannot_help(economics) -> None:
    rendered = render_markdown(economics)
    assert "0.50" in rendered
    assert "converge" in rendered
    assert "matched precision" in rendered.lower()


def test_an_empty_report_costs_nothing_rather_than_crashing() -> None:
    report = SamplingEconomicsReport(worlds=0, seed=1, started_at="now")
    assert report.cost_at_matched_precision() == {}


def test_a_half_scored_cell_is_skipped_rather_than_half_compared() -> None:
    report = SamplingEconomicsReport(worlds=5, seed=1, started_at="now")
    report.summaries = [
        DesignSummary(
            disagreement_fraction=0.2,
            design="uniform",
            readout="super_vs_effect",
            variance_target="superpopulation",
            truth="effect",
            is_negative_control=False,
            worlds=5,
            coverage=0.95,
            coverage_ci_low=0.93,
            coverage_ci_high=0.97,
            mean_half_width=0.01,
            mean_recruited=2000.0,
            mean_recruited_in_disagreement=400.0,
            q_disagreement=0.2,
            q_agreement=0.2,
            bias=0.0,
            mc_se=0.001,
            per_unit_variance=0.5,
        )
    ]
    assert report.cost_at_matched_precision() == {}
