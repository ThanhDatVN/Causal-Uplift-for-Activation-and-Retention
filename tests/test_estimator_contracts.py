"""Acceptance tests A01-A06, A13, A15 from the V4.1 plan (gaps G01-G03).

Each test names the gap it closes.  They are cheap deterministic checks except
:func:`test_reported_variance_tracks_the_empirical_variance`, which is a small
Monte Carlo run with a declared budget -- it is the calibration check for the
variance decomposition, not the coverage gate, which needs a research job with
1,000 worlds per canonical scenario.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.allocation import allocate_batch, capacity_limit
from telco_churn.policy_comparison import (
    align_by_row_key,
    dr_action_scores,
    dr_action_scores_with_support,
    enriched_sampling_contrast,
    ipw_action_scores,
)
from telco_churn.problem_contract import ContractViolation

ACTIONS = ("dunning_only", "payment_support_call")


def _nuisance(n: int, *, keys: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.Index(keys) if keys is not None else pd.RangeIndex(n)
    propensity = pd.DataFrame(
        {"dunning_only": np.full(n, 0.5), "payment_support_call": np.full(n, 0.5)}, index=index
    )
    predicted = pd.DataFrame(
        {"dunning_only": np.zeros(n), "payment_support_call": np.zeros(n)}, index=index
    )
    return propensity, predicted


# -- A01: a known design probability is never silently replaced -------------
def test_a01_a_tiny_known_propensity_is_used_or_refused_but_never_rounded() -> None:
    rare = 0.0005
    propensity = pd.DataFrame({"dunning_only": [1.0 - rare], "payment_support_call": [rare]})
    predicted = pd.DataFrame({"dunning_only": [0.0], "payment_support_call": [0.0]})
    result = dr_action_scores_with_support([1.0], ["payment_support_call"], propensity, predicted)
    # 1 / 0.0005 = 2000 exactly, not 1 / 0.001 = 1000.
    assert result.scores.loc[0, "payment_support_call"] == pytest.approx(2000.0, abs=1e-9)
    assert result.support.support_policy == "unmodified"
    assert result.support.n_clipped == 0
    assert result.support.max_weight == pytest.approx(2000.0)

    with pytest.raises(ContractViolation, match="support floor"):
        dr_action_scores(
            [1.0],
            ["payment_support_call"],
            propensity,
            predicted,
            support_policy="reject",
            support_floor=1e-3,
        )

    sensitivity = dr_action_scores_with_support(
        [1.0],
        ["payment_support_call"],
        propensity,
        predicted,
        support_policy="clip",
        support_floor=1e-3,
    )
    assert sensitivity.support.n_clipped == 1
    assert sensitivity.scores.loc[0, "payment_support_call"] == pytest.approx(1000.0)


def test_a01_support_diagnostics_report_the_weight_concentration() -> None:
    propensity = pd.DataFrame(
        {"dunning_only": [0.5, 0.5, 0.999], "payment_support_call": [0.5, 0.5, 0.001]}
    )
    predicted = pd.DataFrame({"dunning_only": [0.0] * 3, "payment_support_call": [0.0] * 3})
    result = dr_action_scores_with_support(
        [1.0, 1.0, 1.0],
        ["dunning_only", "dunning_only", "payment_support_call"],
        propensity,
        predicted,
    )
    # One unit with weight 1000 against two with weight 2 collapses the ESS.
    assert result.support.effective_sample_size < 1.1
    assert result.support.ess_ratio < 0.4


def test_a01_unknown_support_policy_is_refused() -> None:
    propensity, predicted = _nuisance(2)
    with pytest.raises(ContractViolation, match="unknown support_policy"):
        dr_action_scores(
            [0.0, 1.0], list(ACTIONS), propensity, predicted, support_policy="whatever"
        )  # type: ignore[arg-type]


# -- A02: frames are joined on keys, never on position ----------------------
def test_a02_same_length_frames_in_a_different_row_order_are_refused() -> None:
    keys = [f"acct-{index}" for index in range(4)]
    propensity, predicted = _nuisance(4, keys=keys)
    predicted.loc[:, "payment_support_call"] = [0.1, 0.2, 0.3, 0.4]
    shuffled = predicted.iloc[[2, 0, 3, 1]]
    action = pd.Series(["payment_support_call"] * 4, index=keys)
    reward = pd.Series([1.0, 1.0, 1.0, 1.0], index=keys)

    with pytest.raises(ContractViolation, match="different order"):
        dr_action_scores(reward, action, propensity, shuffled)

    honest = dr_action_scores(reward, action, propensity, predicted)
    realigned = dr_action_scores(reward, action, propensity, shuffled, row_key=keys)
    assert np.array_equal(honest.to_numpy(), realigned.to_numpy())


def test_a02_a_frame_over_a_different_cohort_is_refused() -> None:
    keys = [f"acct-{index}" for index in range(4)]
    propensity, predicted = _nuisance(4, keys=keys)
    other = predicted.copy()
    other.index = [f"acct-{index}" for index in range(10, 14)]
    with pytest.raises(ContractViolation, match="different set of keys"):
        dr_action_scores([1.0] * 4, ["dunning_only"] * 4, propensity, other)


def test_a02_align_by_row_key_rejects_duplicates_and_gaps() -> None:
    keys = ["a", "b", "c"]
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=keys)
    assert list(align_by_row_key({"frame": frame}, row_key=["c", "a", "b"])["frame"]["x"]) == [
        3.0,
        1.0,
        2.0,
    ]
    with pytest.raises(ContractViolation, match="row_key repeats"):
        align_by_row_key({"frame": frame}, row_key=["a", "a", "b"])
    with pytest.raises(ContractViolation, match="not a permutation"):
        align_by_row_key({"frame": frame}, row_key=["a", "b", "z"])


def test_a02_duplicate_row_keys_are_refused() -> None:
    keys = ["a", "a", "b"]
    propensity, predicted = _nuisance(3, keys=keys)
    with pytest.raises(ContractViolation, match="duplicate row keys"):
        dr_action_scores([1.0] * 3, ["dunning_only"] * 3, propensity, predicted)


# -- A03: action labels must be unambiguous ---------------------------------
def test_a03_labels_that_collapse_to_the_same_string_are_refused() -> None:
    propensity = pd.DataFrame({1: [0.5, 0.5], "1": [0.5, 0.5]})
    predicted = pd.DataFrame({1: [0.0, 0.0], "1": [0.0, 0.0]})
    with pytest.raises(ContractViolation, match="collapse to the same label"):
        dr_action_scores([1.0, 1.0], [1, "1"], propensity, predicted)


def test_a03_duplicate_action_columns_are_refused() -> None:
    propensity = pd.DataFrame([[0.5, 0.5], [0.5, 0.5]], columns=["dunning_only", "dunning_only"])
    with pytest.raises(ContractViolation, match="collapse to the same label"):
        ipw_action_scores([1.0, 1.0], ["dunning_only", "dunning_only"], propensity)


def test_a03_an_unknown_action_label_is_refused() -> None:
    propensity, predicted = _nuisance(2)
    with pytest.raises(ContractViolation, match="no column in the score frame"):
        dr_action_scores([1.0, 1.0], ["grace_extension"] * 2, propensity, predicted)


# -- A04: non-finite inputs fail with their row keys ------------------------
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_a04_a_non_finite_reward_fails_with_the_offending_key(bad: float) -> None:
    keys = ["acct-0", "acct-1"]
    propensity, predicted = _nuisance(2, keys=keys)
    reward = pd.Series([1.0, bad], index=keys)
    with pytest.raises(ContractViolation, match="acct-1"):
        dr_action_scores(reward, pd.Series(list(ACTIONS), index=keys), propensity, predicted)


def test_a04_a_non_finite_nuisance_value_fails_rather_than_producing_nan() -> None:
    keys = ["acct-0", "acct-1"]
    propensity, predicted = _nuisance(2, keys=keys)
    predicted.loc["acct-1", "payment_support_call"] = np.inf
    with pytest.raises(ContractViolation, match="predicted_reward"):
        dr_action_scores(
            pd.Series([1.0, 1.0], index=keys),
            pd.Series(list(ACTIONS), index=keys),
            propensity,
            predicted,
        )


# -- A05: a census removes sampling noise, not outcome noise ----------------
def _noisy_frame(n: int = 400, *, seed: int = 11) -> tuple[pd.DataFrame, list[str], list[str]]:
    rng = np.random.default_rng(seed)
    gain = np.zeros(n)
    gain[: n // 2] = rng.normal(0.4, 1.5, n // 2)
    scores = pd.DataFrame({"dunning_only": np.zeros(n), "payment_support_call": gain})
    challenger = ["payment_support_call"] * (n // 2) + ["dunning_only"] * (n - n // 2)
    return scores, challenger, ["dunning_only"] * n


def test_a05_full_recruitment_does_not_collapse_the_total_interval() -> None:
    scores, challenger, bau = _noisy_frame()
    n = len(scores)
    census = enriched_sampling_contrast(
        scores,
        challenger,
        bau,
        sampled=np.ones(n, dtype=bool),
        inclusion_probability=np.ones(n),
        variance_target="superpopulation",
    )
    assert census.se_recruitment_only == 0.0
    assert census.se_superpopulation > 0.0
    assert census.se == census.se_superpopulation
    assert census.ci_low < census.delta < census.ci_high


def test_a05_the_finite_frame_target_is_labelled_as_recruitment_only() -> None:
    scores, challenger, bau = _noisy_frame()
    n = len(scores)
    conditional = enriched_sampling_contrast(
        scores,
        challenger,
        bau,
        sampled=np.ones(n, dtype=bool),
        inclusion_probability=np.ones(n),
    )
    assert conditional.variance_target == "finite_frame"
    assert conditional.se == 0.0
    assert "conditional on the realised score frame" in conditional.scope_note
    # The wider domain is still reported, so nobody has to re-derive it.
    assert conditional.se_superpopulation > 0.0


def test_a05_a_constant_contrast_has_no_uncertainty_in_either_domain() -> None:
    n = 100
    scores = pd.DataFrame({"dunning_only": np.zeros(n), "payment_support_call": np.full(n, 2.0)})
    result = enriched_sampling_contrast(
        scores,
        ["payment_support_call"] * n,
        ["dunning_only"] * n,
        sampled=np.ones(n, dtype=bool),
        inclusion_probability=np.ones(n),
        variance_target="superpopulation",
    )
    assert result.delta == pytest.approx(2.0)
    assert result.se_superpopulation == pytest.approx(0.0, abs=1e-12)


# -- A06: the reported variance is checked against redrawn worlds -----------
def test_a06_reported_variance_tracks_the_empirical_variance() -> None:
    """Small declared-budget Monte Carlo: 600 worlds, 200 units, Poisson recruitment."""

    rng = np.random.default_rng(20260921)
    worlds, n, q_value = 600, 200, 0.4
    truth_mean, truth_sd = 0.5, 1.2
    deltas, reported = [], []
    for _ in range(worlds):
        gain = np.zeros(n)
        gain[: n // 2] = rng.normal(truth_mean, truth_sd, n // 2)
        scores = pd.DataFrame({"a0": np.zeros(n), "a1": gain})
        challenger = ["a1"] * (n // 2) + ["a0"] * (n - n // 2)
        bau = ["a0"] * n
        q = np.where(np.arange(n) < n // 2, q_value, 1.0)
        sampled = rng.random(n) < q
        result = enriched_sampling_contrast(
            scores,
            challenger,
            bau,
            sampled=sampled,
            inclusion_probability=q,
            variance_target="superpopulation",
        )
        deltas.append(result.delta)
        reported.append(result.se)
    empirical = float(np.std(deltas, ddof=1))
    mean_reported = float(np.mean(reported))
    # Both the outcome draw and the recruitment draw are redrawn every world,
    # so the reported standard error has to match the spread it claims to
    # describe; 10% is the declared tolerance for this budget.
    assert mean_reported == pytest.approx(empirical, rel=0.10)


def test_a06_recruitment_only_variance_understates_a_redrawn_world() -> None:
    rng = np.random.default_rng(7)
    worlds, n = 300, 200
    deltas, recruitment_se = [], []
    for _ in range(worlds):
        gain = np.zeros(n)
        gain[: n // 2] = rng.normal(0.5, 1.2, n // 2)
        scores = pd.DataFrame({"a0": np.zeros(n), "a1": gain})
        result = enriched_sampling_contrast(
            scores,
            ["a1"] * (n // 2) + ["a0"] * (n - n // 2),
            ["a0"] * n,
            sampled=np.ones(n, dtype=bool),
            inclusion_probability=np.ones(n),
        )
        deltas.append(result.delta)
        recruitment_se.append(result.se_recruitment_only)
    assert float(np.std(deltas, ddof=1)) > 0.0
    assert max(recruitment_se) == 0.0  # a census: nothing left to resample


# -- A13: the cap is a floor and ties do not depend on row order ------------
@pytest.mark.parametrize(("n", "expected"), [(1, 0), (4, 0), (5, 1), (6, 1), (10, 2), (7043, 1408)])
def test_a13_capacity_is_the_floor_of_the_declared_fraction(n: int, expected: int) -> None:
    assert capacity_limit(n, 0.2) == expected


def test_a13_all_equal_scores_give_the_same_decision_in_any_row_order() -> None:
    ids = [f"acct-{index:02d}" for index in range(10)]
    scores = [1.0] * 10
    baseline = allocate_batch(ids, scores, fraction=0.2)
    permuted_index = [7, 2, 9, 0, 4, 1, 8, 3, 6, 5]
    permuted = allocate_batch(
        [ids[index] for index in permuted_index],
        [scores[index] for index in permuted_index],
        fraction=0.2,
    )
    assert baseline.capacity == 2
    assert sorted(baseline.selected_ids()) == sorted(permuted.selected_ids())
    assert baseline.selected_ids() == ["acct-00", "acct-01"]


def test_a13_the_cap_is_never_exceeded_and_negative_value_is_never_forced() -> None:
    ids = [f"acct-{index:02d}" for index in range(20)]
    scores = [5.0, 4.0, 3.0] + [-1.0] * 17
    allocation = allocate_batch(ids, scores, fraction=0.2)
    assert allocation.capacity == 4
    assert allocation.n_selected == 3  # only three units carry positive value
    assert allocation.unused_slots == 1
    assert set(allocation.frame.loc[~allocation.frame["selected"], "reason"]) == {
        "non_positive_value"
    }


def test_a13_ineligible_units_are_reported_with_their_reason() -> None:
    ids = ["a", "b", "c", "d", "e"]
    allocation = allocate_batch(
        ids, [9.0, 8.0, 7.0, 6.0, 5.0], fraction=0.4, eligible=[False, True, True, True, True]
    )
    assert allocation.capacity == 2
    assert allocation.selected_ids() == ["b", "c"]
    reasons = dict(zip(allocation.frame["unit_id"], allocation.frame["reason"], strict=True))
    assert reasons["a"] == "not_eligible"
    assert reasons["d"] == "capacity_exhausted"


def test_a13_a_missing_score_is_not_treated_as_a_low_score() -> None:
    with pytest.raises(ContractViolation, match="finite"):
        allocate_batch(["a", "b"], [1.0, np.nan], fraction=0.5)


# -- A15: exact identities under a constant reward --------------------------
def test_a15_doubly_robust_contrast_is_exactly_zero_for_a_constant_reward() -> None:
    n = 9
    constant = 3.5
    # Deliberately unbalanced realised treatment: 7 of 9 took the same action.
    action = ["dunning_only"] * 7 + ["payment_support_call"] * 2
    propensity = pd.DataFrame(
        {"dunning_only": np.full(n, 0.6), "payment_support_call": np.full(n, 0.4)}
    )
    predicted = pd.DataFrame(
        {"dunning_only": np.full(n, constant), "payment_support_call": np.full(n, constant)}
    )
    scores = dr_action_scores([constant] * n, action, propensity, predicted)
    contrast = scores["payment_support_call"] - scores["dunning_only"]
    assert np.abs(contrast.to_numpy()).max() == 0.0


def test_a15_inverse_probability_scores_are_not_zero_in_every_realisation() -> None:
    n = 9
    constant = 3.5
    action = ["dunning_only"] * 7 + ["payment_support_call"] * 2
    propensity = pd.DataFrame(
        {"dunning_only": np.full(n, 0.6), "payment_support_call": np.full(n, 0.4)}
    )
    scores = ipw_action_scores([constant] * n, action, propensity)
    delta = float((scores["payment_support_call"] - scores["dunning_only"]).mean())
    # IPW is unbiased in expectation but not exactly zero for this realisation,
    # so a test that asserts zero here would be asserting the wrong identity.
    assert delta != 0.0


def test_a05_a_sample_with_no_disagreement_unit_is_refused() -> None:
    """Zero estimate with zero standard error would be certainty from no data."""

    scores, challenger, bau = _noisy_frame(n=100)
    n = len(scores)
    q = np.full(n, 0.5)
    sampled = np.zeros(n, dtype=bool)
    sampled[n // 2 :] = True  # only agreement units were recruited
    with pytest.raises(ContractViolation, match="not estimable"):
        enriched_sampling_contrast(
            scores, challenger, bau, sampled=sampled, inclusion_probability=q
        )
