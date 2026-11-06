"""The declared screening candidates M01-M08 and baselines B01-B03 (WP08).

These tests are about the *contract*, not about which model wins: the registry
is closed, the score kinds are distinguishable, the DR learners refuse to
invent a propensity, and a learner that cannot be fitted says so instead of
returning zeros.  Which candidate scores best is R02's question, and R02 is
gated on R01.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.candidates import (
    BASELINES,
    CANDIDATES,
    HGB_SETTINGS,
    LOGISTIC_C,
    RIDGE_ALPHA,
    build_candidate,
    candidate_ids,
)


def _cohort(n: int = 900, *, seed: int = 4) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """A small randomised cohort with a real, heterogeneous effect."""

    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        {
            "recency": rng.integers(1, 12, n).astype(float),
            "log1p_history": rng.normal(5.0, 1.0, n),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Web", "Phone", "Multichannel"], n),
        }
    )
    treatment = rng.integers(0, 2, n)
    base = 0.10 + 0.05 * features["newbie"].to_numpy()
    effect = 0.08 * (features["recency"].to_numpy() < 6)
    probability = np.clip(base + effect * treatment, 0.01, 0.95)
    reward = (rng.random(n) < probability).astype(float)
    return features, treatment, reward


# -- the registry is closed ------------------------------------------------
def test_the_eight_candidates_are_declared_with_their_questions() -> None:
    assert [spec.candidate_id for spec in CANDIDATES] == [f"M0{i}" for i in range(1, 9)]
    assert all(spec.question.endswith("?") for spec in CANDIDATES)
    assert all(spec.family for spec in CANDIDATES)


def test_dr_ridge_exists_and_is_distinct_from_dr_hgb() -> None:
    """M07 was missing from this codebase entirely until WP08."""

    by_id = {spec.candidate_id: spec for spec in CANDIDATES}
    assert by_id["M07"].name == "DR-Ridge"
    assert by_id["M08"].name == "DR-HGB"
    assert by_id["M07"].family == by_id["M08"].family == "dr_learner"


def test_the_three_baselines_are_declared_and_two_need_no_fitting() -> None:
    assert [spec.candidate_id for spec in BASELINES] == ["B01", "B02", "B03"]
    assert [spec.trainable for spec in BASELINES] == [False, False, True]


def test_an_undeclared_candidate_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown candidate"):
        build_candidate("M99")


def test_candidate_ids_separates_models_from_baselines() -> None:
    assert candidate_ids() == [f"M0{i}" for i in range(1, 9)]
    assert "B01" in candidate_ids(include_baselines=True)


def test_the_runbook_hyperparameters_are_the_ones_used() -> None:
    assert LOGISTIC_C == 0.3
    assert RIDGE_ALPHA == 10.0
    assert HGB_SETTINGS["max_iter"] == 200
    assert HGB_SETTINGS["max_leaf_nodes"] == 15
    assert HGB_SETTINGS["min_samples_leaf"] == 100
    assert HGB_SETTINGS["l2_regularization"] == 10.0
    assert HGB_SETTINGS["early_stopping"] is False, "screening compares fixed iteration counts"


# -- fitting and scoring ---------------------------------------------------
@pytest.mark.parametrize("candidate_id", [f"M0{i}" for i in range(1, 9)])
def test_every_candidate_fits_and_scores_one_value_per_row(candidate_id: str) -> None:
    features, treatment, reward = _cohort()
    candidate = build_candidate(candidate_id, seed=1)
    candidate.fit(features, treatment, reward, propensity=float(treatment.mean()))
    scores = candidate.score(features)
    assert scores.shape == (len(features),)
    assert np.isfinite(scores).all()


def test_scoring_before_fitting_is_refused() -> None:
    features, _, _ = _cohort(50)
    with pytest.raises(ValueError, match="has not been fitted"):
        build_candidate("M05").score(features)


@pytest.mark.parametrize("candidate_id", ["M07", "M08"])
def test_a_dr_learner_refuses_to_invent_a_propensity(candidate_id: str) -> None:
    features, treatment, reward = _cohort(300)
    with pytest.raises(ValueError, match="needs the design propensity"):
        build_candidate(candidate_id).fit(features, treatment, reward)


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.2])
def test_a_dr_learner_refuses_an_infeasible_propensity(bad: float) -> None:
    features, treatment, reward = _cohort(300)
    with pytest.raises(ValueError, match="strictly inside"):
        build_candidate("M07").fit(features, treatment, reward, propensity=bad)


def test_a_non_binary_treatment_is_refused() -> None:
    features, _, reward = _cohort(100)
    arms = np.full(len(features), 2)
    with pytest.raises(ValueError, match="binary"):
        build_candidate("M05").fit(features, arms, reward, propensity=0.5)


def test_mismatched_lengths_are_refused() -> None:
    features, treatment, reward = _cohort(100)
    with pytest.raises(ValueError, match="same length"):
        build_candidate("M01").fit(features, treatment[:50], reward)


# -- score kinds stay distinguishable --------------------------------------
def test_outcome_rankers_are_labelled_differently_from_effect_learners() -> None:
    assert build_candidate("M01").score_kind == "outcome_ranking"
    assert build_candidate("M02").score_kind == "outcome_ranking"
    for candidate_id in ("M03", "M04", "M05", "M06", "M07", "M08"):
        assert build_candidate(candidate_id).score_kind == "reward_difference"


def test_an_effect_learner_recovers_the_sign_of_a_real_effect() -> None:
    """A positive reward effect must produce positive scores on average."""

    features, treatment, reward = _cohort(3000, seed=9)
    for candidate_id in ("M03", "M05", "M07"):
        candidate = build_candidate(candidate_id, seed=2)
        candidate.fit(features, treatment, reward, propensity=float(treatment.mean()))
        assert candidate.score(features).mean() > 0, candidate_id


def test_the_effect_learners_agree_with_the_constant_baseline_on_average() -> None:
    """The mean estimated effect should land near the training ATE."""

    features, treatment, reward = _cohort(4000, seed=11)
    constant = build_candidate("B03").fit(features, treatment, reward)
    target = constant.score(features)[0]
    for candidate_id in ("M03", "M05", "M07"):
        candidate = build_candidate(candidate_id, seed=3)
        candidate.fit(features, treatment, reward, propensity=float(treatment.mean()))
        assert candidate.score(features).mean() == pytest.approx(target, abs=0.03), candidate_id


# -- baselines -------------------------------------------------------------
def test_the_no_contact_baseline_never_produces_a_positive_score() -> None:
    features, _, _ = _cohort(100)
    assert (build_candidate("B01").score(features) == 0).all()


def test_the_random_baseline_replays_identically_and_needs_ids() -> None:
    features, _, _ = _cohort(200)
    ids = [f"acct-{index}" for index in range(len(features))]
    first = build_candidate("B02").score(features, unit_id=ids)
    second = build_candidate("B02").score(features, unit_id=ids)
    assert np.array_equal(first, second)
    with pytest.raises(ValueError, match="needs unit ids"):
        build_candidate("B02").score(features)


def test_the_constant_baseline_uses_training_data_only() -> None:
    features, treatment, reward = _cohort(2000, seed=13)
    candidate = build_candidate("B03").fit(features, treatment, reward)
    scores = candidate.score(features)
    assert len(set(scores.round(12))) == 1, "a constant effect must be constant"
    expected = reward[treatment == 1].mean() - reward[treatment == 0].mean()
    assert scores[0] == pytest.approx(expected)


def test_the_constant_baseline_needs_both_arms() -> None:
    features, _, reward = _cohort(100)
    with pytest.raises(ValueError, match="both arms"):
        build_candidate("B03").fit(features, np.ones(len(features), dtype=int), reward)
