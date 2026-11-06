"""R06: the selection procedure measured on itself.

The whole point of this stage is that it must be able to catch the workflow
cheating, so the tests are about resolution and about honesty of scope: the
study must have enough power to see a promotion at all, it must isolate
selection from modelling, and it must refuse to call itself a gate.
"""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.selection_stress import (
    MECHANISMS,
    RECIPES,
    SelectionStressReport,
    WorldOutcome,
    _fit_recipes,
    _recipe_score,
    _sample,
    render_markdown,
    run_selection_stress,
)


# -- the generator ---------------------------------------------------------
def test_the_null_mechanism_really_has_no_effect() -> None:
    sample = _sample(5_000, 0.0, np.random.default_rng(1))
    assert (sample["tau"] == 0.0).all()


def test_only_the_first_covariate_carries_the_effect() -> None:
    """So a recipe reading x2 is looking at nothing, by construction."""

    sample = _sample(5_000, 0.35, np.random.default_rng(1))
    high, low = sample["x1"] >= 0.5, sample["x1"] < 0.5
    assert sample["tau"][high].mean() > sample["tau"][low].mean()
    top, bottom = sample["x2"] >= 0.5, sample["x2"] < 0.5
    assert sample["tau"][top].mean() == pytest.approx(sample["tau"][bottom].mean(), abs=2e-3)


def test_every_probability_stays_feasible() -> None:
    for scale in (0.0, 0.35):
        sample = _sample(5_000, scale, np.random.default_rng(2))
        treated = sample["p0"] - sample["tau"]
        assert ((treated >= 0) & (treated <= 1)).all()


# -- the recipes -----------------------------------------------------------
def test_every_declared_recipe_scores() -> None:
    rng = np.random.default_rng(3)
    train = _sample(4_000, 0.35, rng)
    other = _sample(4_000, 0.35, rng)
    fit = _fit_recipes(train)
    for recipe in RECIPES:
        scores = _recipe_score(recipe, other, fit)
        assert len(scores) == len(other["x1"])
        assert np.isfinite(scores).all()


def test_an_unknown_recipe_is_refused() -> None:
    rng = np.random.default_rng(3)
    sample = _sample(200, 0.0, rng)
    with pytest.raises(ValueError, match="unknown recipe"):
        _recipe_score("wishful_thinking", sample, _fit_recipes(sample))


def test_the_recipes_are_fitted_on_train_only() -> None:
    """The constants come from the training sample and nothing else."""

    rng = np.random.default_rng(4)
    train_a = _sample(4_000, 0.35, rng)
    train_b = _sample(4_000, 0.35, rng)
    assert _fit_recipes(train_a) != _fit_recipes(train_b)


# -- resolution: the study must be able to fail ---------------------------
@pytest.fixture(scope="module")
def stressed():
    return run_selection_stress(worlds=30, seed=7)


def test_the_study_has_enough_resolution_to_promote_at_all(stressed) -> None:
    """A scenario that never promotes cannot detect promotion inflation.

    An earlier draft used 4,000 rows and a 2% effect and promoted in zero
    worlds out of every arm, which looks like a clean result and is actually
    an absence of measurement.
    """

    alternative = [row for row in stressed.summaries() if row.mechanism == "weak_heterogeneous"]
    assert any(row.promotion_rate > 0 for row in alternative)


def test_both_arms_are_scored_for_both_mechanisms(stressed) -> None:
    seen = {(row.mechanism, row.arm) for row in stressed.summaries()}
    assert seen == {
        (mechanism, arm)
        for mechanism, _scale in MECHANISMS
        for arm in ("one_candidate", "four_candidates")
    }


def test_regret_is_zero_by_construction_under_the_null(stressed) -> None:
    """With no effect anywhere, no choice can be worse than another."""

    for row in stressed.summaries():
        if row.mechanism == "null_effect":
            assert row.mean_regret == pytest.approx(0.0, abs=1e-12)


def test_the_one_candidate_arm_carries_no_selection(stressed) -> None:
    for outcome in stressed.outcomes:
        assert outcome.fixed_recipe == RECIPES[0]


def test_the_chosen_recipe_is_always_one_of_the_declared_four(stressed) -> None:
    assert {outcome.chosen_of_four for outcome in stressed.outcomes} <= set(RECIPES)


def test_regret_is_never_negative(stressed) -> None:
    """The oracle best cannot be worse than what the selector picked."""

    for outcome in stressed.outcomes:
        assert outcome.selection_regret >= -1e-12


# -- refusing to overclaim -------------------------------------------------
def test_the_artifact_refuses_to_call_itself_a_gate(stressed) -> None:
    payload = stressed.to_dict()
    assert payload["is_a_gate"] is False
    assert "cannot be scored" in payload["gate_refusal_reason"]


def test_the_refusal_quotes_its_own_resolution(stressed) -> None:
    """The reason has to carry the number, or it is just a disclaimer."""

    reason = stressed.to_dict()["gate_refusal_reason"]
    assert "+-" in reason and "binomial" in reason


def test_the_selection_cost_is_reported_per_mechanism(stressed) -> None:
    cost = stressed.to_dict()["selection_cost"]
    assert set(cost) == {name for name, _scale in MECHANISMS}
    for entry in cost.values():
        assert "promotion_inflation" in entry
        assert "coverage_loss" in entry


def test_the_markdown_says_it_is_not_a_gate(stressed) -> None:
    rendered = render_markdown(stressed)
    assert "not a gate" in rendered.lower()
    assert "what selection cost" in rendered.lower()


# -- the bookkeeping -------------------------------------------------------
def test_a_world_records_both_arms_side_by_side() -> None:
    outcome = WorldOutcome(
        mechanism="null_effect",
        world=0,
        chosen_of_four="both",
        fixed_recipe="x1_only",
        selected_estimate=0.01,
        selected_truth=0.0,
        selected_promoted=True,
        selected_covered=False,
        fixed_estimate=0.001,
        fixed_truth=0.0,
        fixed_promoted=False,
        fixed_covered=True,
        best_possible_truth=0.0,
    )
    payload = outcome.to_dict()
    assert payload["selection_regret"] == 0.0
    assert payload["selected_promoted"] is True
    assert payload["fixed_promoted"] is False


def test_an_empty_report_summarises_to_nothing_rather_than_crashing() -> None:
    report = SelectionStressReport(worlds_per_mechanism=0, seed=1, started_at="now")
    assert report.summaries() == []
    assert report.selection_cost() == {}
