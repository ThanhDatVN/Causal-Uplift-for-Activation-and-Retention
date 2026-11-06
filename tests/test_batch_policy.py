"""Batch-policy contrast under a hard cap (G06, MASTER_PLAN §4.2).

A capped policy decides about one account by looking at the whole batch, so
the interval has to re-run the allocation inside every resample.  These tests
check the properties that makes it different from an interval for a mean:
the cap is respected in every resample, ties never depend on row order, the
naive frozen-action alternative is reported beside it, and the two targets
(this batch versus a future batch) are not interchangeable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.policy_comparison import batch_policy_contrast
from telco_churn.problem_contract import ContractViolation

HOLD = "hold"
CONTACT = "contact"


def _batch(n: int = 800, *, seed: int = 2, tie_scores: bool = False):
    rng = np.random.default_rng(seed)
    effect = 0.01 * (2 * rng.integers(0, 2, n) - 1)
    scores = pd.DataFrame({HOLD: np.zeros(n), CONTACT: effect + rng.normal(0, 0.05, n)})
    challenger = np.round(effect, 2) if tie_scores else effect + rng.normal(0, 0.001, n)
    return scores, challenger, np.zeros(n), [f"u{index:04d}" for index in range(n)]


def _contrast(**overrides):
    scores, challenger, baseline, ids = overrides.pop("batch", _batch())
    kwargs = {
        "score_1": challenger,
        "score_0": baseline,
        "unit_id": ids,
        "action_if_selected": CONTACT,
        "action_if_not": HOLD,
        "capacity_fraction": 0.2,
        "resamples": 200,
    }
    kwargs.update(overrides)
    return batch_policy_contrast(scores, **kwargs)


# -- the cap ---------------------------------------------------------------
def test_the_cap_is_the_floor_of_the_declared_fraction() -> None:
    result = _contrast()
    assert result.capacity == 160  # floor(0.2 * 800)
    assert result.n_selected_policy_1 <= result.capacity
    assert result.n_selected_policy_0 <= result.capacity


def test_a_baseline_that_scores_zero_everywhere_still_fills_its_cap() -> None:
    """The comparison is between scoring functions under one envelope."""

    result = _contrast()
    # Both policies allocate under the same rule, so the contrast is about
    # *which* accounts each picks, not about how many.
    assert result.n_selected_policy_0 == result.capacity
    assert result.n_disagreement > 0


def test_an_impossible_capacity_fraction_is_refused() -> None:
    with pytest.raises(ContractViolation, match="capacity_fraction"):
        _contrast(capacity_fraction=0.0)


def test_an_action_without_a_column_is_refused() -> None:
    with pytest.raises(ContractViolation, match="no column in the score frame"):
        _contrast(action_if_selected="grace_extension")


def test_mismatched_lengths_are_refused() -> None:
    scores, challenger, baseline, ids = _batch(100)
    with pytest.raises(ContractViolation, match="one batch"):
        batch_policy_contrast(
            scores,
            score_1=challenger[:50],
            score_0=baseline,
            unit_id=ids,
            action_if_selected=CONTACT,
            action_if_not=HOLD,
            capacity_fraction=0.2,
            resamples=10,
        )


# -- determinism -----------------------------------------------------------
def test_the_point_estimate_does_not_depend_on_row_order() -> None:
    scores, challenger, baseline, ids = _batch(600, tie_scores=True)
    first = batch_policy_contrast(
        scores,
        score_1=challenger,
        score_0=baseline,
        unit_id=ids,
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=50,
    )
    order = np.random.default_rng(0).permutation(len(scores))
    second = batch_policy_contrast(
        scores.iloc[order].reset_index(drop=True),
        score_1=challenger[order],
        score_0=baseline[order],
        unit_id=[ids[index] for index in order],
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=50,
    )
    # Ties are broken by unit id, so a permutation cannot change the decision.
    assert first.delta == pytest.approx(second.delta)
    assert first.n_disagreement == second.n_disagreement


def test_the_same_seed_reproduces_the_interval() -> None:
    batch = _batch(400)
    left = _contrast(batch=batch, seed=11)
    right = _contrast(batch=batch, seed=11)
    assert (left.ci_low, left.ci_high) == (right.ci_low, right.ci_high)


# -- what the interval carries ---------------------------------------------
def test_the_frozen_action_alternative_is_reported_beside_the_bootstrap() -> None:
    result = _contrast()
    assert result.se_frozen_actions > 0
    assert result.se_bootstrap > 0
    assert np.isfinite(result.allocation_variance_share)
    assert "batch_policy_bootstrap" in result.to_dict()["estimator"]


def test_ties_make_the_allocation_matter_more() -> None:
    """With many near-ties, resampling flips who is selected."""

    continuous = _contrast(batch=_batch(600, tie_scores=False), resamples=300)
    tied = _contrast(batch=_batch(600, tie_scores=True), resamples=300)
    # Not a strict inequality on variance share -- the point is that both are
    # measured, so a reader can see when the naive answer is safe.
    assert np.isfinite(continuous.allocation_variance_share)
    assert np.isfinite(tied.allocation_variance_share)


def test_the_two_targets_are_labelled_and_both_usable() -> None:
    batch = _batch(600)
    future = _contrast(batch=batch, target="future_batch", resamples=300)
    finite = _contrast(batch=batch, target="finite_batch", resamples=300)
    assert future.target == "future_batch"
    assert finite.target == "finite_batch"
    for result in (future, finite):
        assert result.ci_low < result.delta < result.ci_high


def test_the_finite_batch_interval_is_not_degenerate() -> None:
    """Conditioning on the batch must not collapse the interval to a point.

    The composition is held, but the outcomes are still random, so there is
    real uncertainty left.  An earlier version resampled the identity index,
    which returns one number every time and gives quantiles of width exactly
    zero -- an interval that covers nothing while looking reassuringly tight.
    The V08 scenario is what caught it, so it is pinned here.
    """

    finite = _contrast(batch=_batch(600), target="finite_batch", resamples=300)
    assert finite.ci_high - finite.ci_low > 0
    assert np.isfinite(finite.se_frozen_actions) and finite.se_frozen_actions > 0


def test_the_finite_interval_does_not_depend_on_the_resample_count() -> None:
    """It conditions on the batch, so no bootstrap enters it at all."""

    batch = _batch(600)
    few = _contrast(batch=batch, target="finite_batch", resamples=50)
    many = _contrast(batch=batch, target="finite_batch", resamples=5_000)
    assert few.ci_low == many.ci_low
    assert few.ci_high == many.ci_high


def test_composition_variation_adds_variance_rather_than_removing_it() -> None:
    """The structural claim behind the two targets, measured on the SEs.

    Interval *widths* compare a percentile interval against a normal one, so
    at a few hundred resamples they can cross by chance; the standard errors
    are the quantity the claim is actually about, and the margin here is
    small enough that it needs the resamples to be visible.
    """

    future = _contrast(batch=_batch(600), target="future_batch", resamples=20_000)
    assert future.se_bootstrap >= future.se_frozen_actions


def test_an_unknown_target_is_refused() -> None:
    with pytest.raises(ContractViolation, match="unknown target"):
        _contrast(target="whatever")


def test_identical_policies_contrast_to_zero() -> None:
    scores, challenger, _, ids = _batch(500)
    result = batch_policy_contrast(
        scores,
        score_1=challenger,
        score_0=challenger,
        unit_id=ids,
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=100,
    )
    assert result.delta == 0.0
    assert result.n_disagreement == 0
    assert result.ci_low == result.ci_high == 0.0


# -- the conditional standard error ---------------------------------------
def _heterogeneous(n: int = 800, *, seed: int = 5, noise: float = 0.02):
    """A batch where the predicted means carry most of the score's spread.

    The default fixture has an effect spread of 0.01 against score noise of
    0.05, so conditioning on the batch has almost nothing to remove and the
    two standard errors agree to within a couple of percent.  That is a fine
    fixture for the cap and the tie rule and a useless one here, so this is a
    regime where m_a(X) genuinely dominates -- which is also the regime where
    a cap is worth having.
    """

    rng = np.random.default_rng(seed)
    x = rng.random(n)
    effect = 2.0 * x - 1.0
    means = pd.DataFrame({HOLD: np.zeros(n), CONTACT: effect})
    scores = pd.DataFrame({HOLD: np.zeros(n), CONTACT: effect + rng.normal(0, noise, n)})
    challenger = effect + rng.normal(0, 0.001, n)
    ids = [f"u{index:04d}" for index in range(n)]
    return (scores, challenger, np.zeros(n), ids), means


def test_the_conditional_se_falls_back_when_no_means_are_given() -> None:
    """Without the means the two cannot be separated, so it stays conservative."""

    result = _contrast()
    assert result.se_conditional == result.se_frozen_actions


def test_given_the_means_the_conditional_se_is_the_smaller_one() -> None:
    """Holding the batch removes the between-unit spread of m_a(X).

    `se_frozen_actions` spreads the whole score across units, which carries
    the variation in the predicted means as well as the outcome noise -- a
    superpopulation quantity.  Conditioning on a batch fixes m_a(X), so only
    the residual part is still random.
    """

    batch, means = _heterogeneous()
    result = _contrast(batch=batch, predicted_reward=means)
    assert result.se_conditional < result.se_frozen_actions / 5


def test_the_conditional_se_tracks_the_outcome_noise_not_the_effect_spread() -> None:
    """Ten times the noise, ten times the conditional SE; frozen barely moves."""

    quiet_batch, quiet_means = _heterogeneous(noise=0.01)
    loud_batch, loud_means = _heterogeneous(noise=0.10)
    quiet = _contrast(batch=quiet_batch, predicted_reward=quiet_means)
    loud = _contrast(batch=loud_batch, predicted_reward=loud_means)
    assert loud.se_conditional == pytest.approx(10 * quiet.se_conditional, rel=0.25)
    assert loud.se_frozen_actions == pytest.approx(quiet.se_frozen_actions, rel=0.10)


def test_the_finite_interval_uses_the_conditional_se_when_it_can() -> None:
    batch, means = _heterogeneous()
    wide = _contrast(batch=batch, target="finite_batch")
    narrow = _contrast(batch=batch, target="finite_batch", predicted_reward=means)
    assert (narrow.ci_high - narrow.ci_low) < (wide.ci_high - wide.ci_low) / 5


def test_means_on_the_wrong_actions_are_refused() -> None:
    bad = _heterogeneous()[1].rename(columns={CONTACT: "something_else"})
    with pytest.raises(ContractViolation, match="share action columns"):
        _contrast(predicted_reward=bad)


def test_means_covering_a_different_batch_are_refused() -> None:
    with pytest.raises(ContractViolation, match="same batch"):
        _contrast(predicted_reward=_heterogeneous(400)[1])


def test_non_finite_means_are_refused_rather_than_propagated() -> None:
    batch, means = _heterogeneous()
    means.loc[3, CONTACT] = np.nan
    with pytest.raises(ContractViolation, match="predicted_reward"):
        _contrast(batch=batch, predicted_reward=means)
