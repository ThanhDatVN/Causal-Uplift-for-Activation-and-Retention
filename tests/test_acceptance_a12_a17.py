"""Acceptance tests A12, A14, A16 and A17 from MASTER_PLAN §"Acceptance tests".

These four were unrunnable until the machinery they check existed.  Each one
states the failure it is guarding against, because an acceptance test whose
name is the only description of it is not an acceptance test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.batch_validation import run_v08
from telco_churn.hillstrom_data import (
    POST_TREATMENT_COLUMNS,
    assert_no_post_treatment_features,
)
from telco_churn.policy_comparison import batch_policy_contrast
from telco_churn.problem_contract import ContractViolation

HOLD = "hold"
CONTACT = "contact"


# -- A12: the capped batch interval must target the batch it claims -------
#
# "Repeated batch draws, cap 20%, model scores frozen -> V08 CI scores the
#  future-batch truth; the fixed-vector CI may not promote its own scope."
def test_a12_the_future_batch_interval_covers_the_future_batch_truth() -> None:
    report = run_v08(worlds=40, seed=4242)
    for item in report.summaries:
        if item.readout == "future_vs_super":
            assert item.coverage_ci_high >= 0.92, (
                f"{item.regime}: the future-batch interval must cover the "
                f"superpopulation truth, got {item.coverage}"
            )


def test_a12_the_fixed_vector_interval_may_not_promote_its_own_scope() -> None:
    """The conditional interval read as forward-looking must be caught.

    This is the half of A12 that matters: a narrow interval that silently
    claims a wider target. V08 scores it as a declared control, and where
    the distinction is material it must visibly fail.
    """

    report = run_v08(worlds=40, seed=4242)
    material = [
        item for item in report.summaries if item.readout == "finite_vs_super" and item.material
    ]
    assert material, "no regime made the two scopes distinguishable"
    for item in material:
        assert item.coverage < 0.92, (
            "the batch-conditional interval scored against the superpopulation "
            f"truth must under-cover, got {item.coverage}"
        )


# -- A14: bootstrap draws keep duplicate occurrences ----------------------
#
# "Same original row appears in multiple draws -> keep occurrences; paired
#  sample/tie order reproducible; do not ingest-dedup bootstrap draws."
def _batch(n: int = 400, *, seed: int = 11):
    rng = np.random.default_rng(seed)
    effect = 0.01 * (2 * rng.integers(0, 2, n) - 1)
    scores = pd.DataFrame({HOLD: np.zeros(n), CONTACT: effect + rng.normal(0, 0.05, n)})
    challenger = effect + rng.normal(0, 0.001, n)
    return scores, challenger, np.zeros(n), [f"u{index:04d}" for index in range(n)]


def test_a14_a_duplicated_row_is_not_deduplicated_by_the_allocator() -> None:
    """A resample that dropped duplicates would shrink its own sample.

    The allocator breaks ties on unit id, so two copies of one account share
    an id. If it deduplicated them the effective resample size would fall
    below n and the interval would be wrong in a way nothing else catches.
    """

    scores, challenger, baseline, ids = _batch(200)
    doubled_scores = pd.concat([scores, scores], ignore_index=True)
    doubled = batch_policy_contrast(
        doubled_scores,
        score_1=np.concatenate([challenger, challenger]),
        score_0=np.concatenate([baseline, baseline]),
        unit_id=[*ids, *ids],
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=100,
    )
    # 400 rows, not 200: the duplicate occurrences were kept.
    assert doubled.n_units == 400
    assert doubled.capacity == 80


def test_a14_the_resample_is_reproducible_under_a_seed() -> None:
    batch = _batch(300)
    left = batch_policy_contrast(
        batch[0],
        score_1=batch[1],
        score_0=batch[2],
        unit_id=batch[3],
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=200,
        seed=7,
    )
    right = batch_policy_contrast(
        batch[0],
        score_1=batch[1],
        score_0=batch[2],
        unit_id=batch[3],
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=200,
        seed=7,
    )
    assert (left.ci_low, left.ci_high) == (right.ci_low, right.ci_high)


def test_a14_tie_breaking_does_not_depend_on_row_order() -> None:
    """Ties resolved by position would make a resample order-dependent."""

    n = 300
    scores = pd.DataFrame({HOLD: np.zeros(n), CONTACT: np.zeros(n)})
    tied = np.zeros(n)  # every score identical: only the tie rule decides
    ids = [f"u{index:04d}" for index in range(n)]
    order = np.random.default_rng(3).permutation(n)
    first = batch_policy_contrast(
        scores,
        score_1=tied,
        score_0=tied,
        unit_id=ids,
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=20,
    )
    second = batch_policy_contrast(
        scores.iloc[order].reset_index(drop=True),
        score_1=tied[order],
        score_0=tied[order],
        unit_id=[ids[index] for index in order],
        action_if_selected=CONTACT,
        action_if_not=HOLD,
        capacity_fraction=0.2,
        resamples=20,
    )
    assert first.n_selected_policy_1 == second.n_selected_policy_1
    assert first.delta == pytest.approx(second.delta)


# -- A16: a renamed post-treatment column must still be rejected ----------
#
# "`visit`, `spend` or a renamed post-treatment column enters X -> feature
#  provenance rejects; dropping the name `conversion` alone is not enough."
def test_a16_every_declared_post_treatment_column_is_rejected() -> None:
    for column in POST_TREATMENT_COLUMNS:
        with pytest.raises(ValueError):
            assert_no_post_treatment_features(["recency", column])


def test_a16_dropping_only_the_outcome_name_is_not_enough() -> None:
    """`visit` and `spend` are consequences too, not just `conversion`."""

    assert {"visit", "spend"} <= set(POST_TREATMENT_COLUMNS)
    with pytest.raises(ValueError, match="visit"):
        assert_no_post_treatment_features(["recency", "visit"])


def test_a16_the_second_domain_has_its_own_gate_not_a_shared_one() -> None:
    """Lenta's post-treatment columns are different ones, and are named."""

    from telco_churn.lenta_data import (
        POST_TREATMENT_COLUMNS as LENTA_POST,
    )
    from telco_churn.lenta_data import (
        assert_no_post_treatment_features as lenta_gate,
    )

    assert "response_sms" in LENTA_POST
    assert set(LENTA_POST) != set(POST_TREATMENT_COLUMNS), (
        "each domain declares its own consequences; sharing one list would "
        "silently let a column through in whichever domain it was not written for"
    )
    with pytest.raises(ValueError):
        lenta_gate(["age", "response_viber"])


def test_a16_a_clean_feature_list_passes_both_gates() -> None:
    from telco_churn.lenta_data import assert_no_post_treatment_features as lenta_gate

    assert_no_post_treatment_features(["recency", "log1p_history", "newbie"])
    lenta_gate(["age", "cheque_count_12m_g20"])


# -- A17: degenerate columns are handled explicitly -----------------------
#
# "Numeric column all-missing in train; unseen category at evaluation ->
#  fitted fallback/token behaviour explicit, finite outputs or declared
#  unsupported; do not learn from evaluation."
def _cohort(n: int = 600, *, seed: int = 5):
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
    reward = (rng.random(n) < 0.12).astype(float)
    return features, treatment, reward


def test_a17_an_all_missing_numeric_column_does_not_produce_nan_scores() -> None:
    from telco_churn.candidates import build_candidate

    features, treatment, reward = _cohort()
    features["all_missing"] = np.nan
    model = build_candidate("M01", seed=1).fit(features, treatment, reward)
    scores = model.score(features)
    assert np.isfinite(scores).all(), "an all-missing column must not leak NaN into scores"


def test_a17_an_unseen_category_at_evaluation_is_handled_not_learned_from() -> None:
    """The encoder is fitted on train only, so a new level cannot teach it."""

    from telco_churn.candidates import build_candidate

    features, treatment, reward = _cohort()
    model = build_candidate("M01", seed=1).fit(features, treatment, reward)

    unseen = features.copy()
    unseen.loc[unseen.index[:10], "channel"] = "Carrier Pigeon"
    scores = model.score(unseen)
    assert np.isfinite(scores).all()
    # Rows whose only change is the unseen level must not move the others.
    untouched = model.score(features)
    assert np.allclose(scores[10:], untouched[10:]), (
        "an unseen level at evaluation changed the scores of other rows, which "
        "means the encoder refitted on evaluation data"
    )


def test_a17_a_degenerate_arm_is_refused_rather_than_silently_fitted() -> None:
    """A T-learner with one empty arm is unsupported, and says so."""

    from telco_churn.candidates import build_candidate

    features, treatment, reward = _cohort(200)
    treatment = np.zeros(200, dtype=int)  # no treated arm at all
    with pytest.raises(ValueError, match="too little signal|arm"):
        build_candidate("M05", seed=1).fit(features, treatment, reward)


def test_a17_a_dr_learner_will_not_invent_a_propensity() -> None:
    from telco_churn.candidates import build_candidate

    features, treatment, reward = _cohort(300)
    with pytest.raises(ValueError, match="propensity"):
        build_candidate("M07", seed=1).fit(features, treatment, reward, propensity=None)


def test_a17_a_degenerate_propensity_is_refused_by_the_contract() -> None:
    from telco_churn.policy_comparison import design_asymmetry_index

    with pytest.raises(ContractViolation, match="propensity"):
        design_asymmetry_index(n_units=1000, propensity=0.0, event_rate=0.1)
