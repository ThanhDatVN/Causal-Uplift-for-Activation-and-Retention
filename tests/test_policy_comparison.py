"""Paired policy contrasts and the enriched sampling design (E20, V4-02)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.policy_comparison import (
    action_pair_strata,
    cost_to_precision,
    disagreement_mask,
    dr_action_scores,
    enriched_sampling_contrast,
    ipw_action_scores,
    paired_contrast,
    unpaired_contrast,
)
from telco_churn.problem_contract import ContractViolation

ACTIONS = ["dunning_only", "payment_support_call"]


def _scores(n: int, *, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"dunning_only": rng.normal(0, 1, n), "payment_support_call": rng.normal(0.2, 1, n)}
    )


def test_identical_policies_have_zero_delta_and_zero_standard_error() -> None:
    scores = _scores(300)
    policy = ["payment_support_call" if index % 4 else "dunning_only" for index in range(300)]
    contrast = paired_contrast(scores, policy, policy)
    assert contrast.delta == 0.0
    assert contrast.se == 0.0
    assert (contrast.ci_low, contrast.ci_high) == (0.0, 0.0)
    assert contrast.n_disagreement == 0
    assert contrast.is_identical is True


def test_unpaired_analysis_reports_uncertainty_that_is_not_there() -> None:
    scores = _scores(300)
    policy = ["payment_support_call" if index % 4 else "dunning_only" for index in range(300)]
    assert unpaired_contrast(scores, policy, policy).se > 0


def test_contrast_comes_only_from_the_disagreement_region() -> None:
    n = 100
    paired_gain = np.zeros(n)
    paired_gain[:10] = 5.0
    scores = pd.DataFrame({"dunning_only": np.zeros(n), "payment_support_call": paired_gain})
    challenger = ["payment_support_call"] * 10 + ["dunning_only"] * (n - 10)
    bau = ["dunning_only"] * n
    contrast = paired_contrast(scores, challenger, bau)
    # Delta equals P(D=1) * mean gain on D=1 exactly.
    assert contrast.delta == pytest.approx(0.10 * 5.0)
    assert contrast.share_changed == pytest.approx(0.10)
    assert contrast.n_disagreement == 10


def test_fixed_deployment_overhead_shifts_the_point_but_not_the_standard_error() -> None:
    scores = _scores(200)
    policy = ["dunning_only"] * 200
    contrast = paired_contrast(scores, policy, policy, fixed_overhead_per_account=0.5)
    assert contrast.delta == 0.0
    assert contrast.se == 0.0
    assert contrast.delta_net == -0.5
    assert contrast.delta_net_per_1000 == -500.0


def test_a_missing_score_is_refused_rather_than_averaged_away() -> None:
    n = 20
    scores = _scores(n)
    scores.loc[3, "payment_support_call"] = np.nan
    with pytest.raises(ContractViolation, match="missing or infinite"):
        paired_contrast(scores, ["payment_support_call"] * n, ["dunning_only"] * n)


def test_clustered_standard_error_exceeds_the_pooled_one() -> None:
    per_cluster, n_clusters = 8, 25
    effect = np.repeat(np.linspace(-1, 1, n_clusters), per_cluster)
    scores = pd.DataFrame({"dunning_only": np.zeros(len(effect)), "payment_support_call": effect})
    challenger = ["payment_support_call"] * len(effect)
    bau = ["dunning_only"] * len(effect)
    cluster = np.repeat([f"c{index}" for index in range(n_clusters)], per_cluster)
    clustered = paired_contrast(scores, challenger, bau, cluster=cluster)
    pooled = paired_contrast(scores, challenger, bau)
    assert clustered.n_clusters == n_clusters
    assert clustered.se > pooled.se


def test_unsupported_action_is_refused_rather_than_imputed() -> None:
    scores = _scores(10)
    with pytest.raises(ContractViolation, match="no column in the score frame"):
        paired_contrast(scores, ["grace_extension"] * 10, ["dunning_only"] * 10)


def test_doubly_robust_scores_reduce_to_the_outcome_model_without_residuals() -> None:
    n = 6
    predicted = pd.DataFrame(
        {"dunning_only": np.full(n, 0.3), "payment_support_call": np.full(n, 0.8)}
    )
    propensity = pd.DataFrame(
        {"dunning_only": np.full(n, 0.5), "payment_support_call": np.full(n, 0.5)}
    )
    action = ["dunning_only", "payment_support_call"] * 3
    reward = [0.3, 0.8] * 3  # residual is exactly zero
    scores = dr_action_scores(reward, action, propensity, predicted)
    assert np.allclose(scores.to_numpy(), predicted.to_numpy())


def test_inverse_probability_scores_recover_a_hand_computed_value() -> None:
    propensity = pd.DataFrame({"dunning_only": [0.5, 0.5], "payment_support_call": [0.5, 0.5]})
    scores = ipw_action_scores([4.0, 10.0], ["dunning_only", "payment_support_call"], propensity)
    assert scores["dunning_only"].tolist() == [8.0, 0.0]
    assert scores["payment_support_call"].tolist() == [0.0, 20.0]


def test_propensity_must_be_a_valid_distribution() -> None:
    propensity = pd.DataFrame({"dunning_only": [0.5], "payment_support_call": [0.2]})
    with pytest.raises(ContractViolation, match="sum to one"):
        ipw_action_scores([1.0], ["dunning_only"], propensity)


def test_action_pair_strata_sum_back_to_the_whole_cohort_delta() -> None:
    n = 40
    gain = np.zeros(n)
    gain[:10] = 2.0
    scores = pd.DataFrame({"dunning_only": np.zeros(n), "payment_support_call": gain})
    challenger = ["payment_support_call"] * 10 + ["dunning_only"] * 30
    bau = ["dunning_only"] * n
    table = action_pair_strata(scores, challenger, bau)
    contrast = paired_contrast(scores, challenger, bau)
    assert table["contribution_to_delta"].sum() == pytest.approx(contrast.delta)
    assert table.loc[table["is_disagreement"], "n_units"].sum() == 10


def test_disagreement_mask_requires_a_common_cohort() -> None:
    with pytest.raises(ContractViolation, match="same cohort"):
        disagreement_mask(["a", "b"], ["a"])


# -- sampling design --------------------------------------------------------
def _sampling_fixture() -> tuple[pd.DataFrame, list[str], list[str], np.ndarray, np.ndarray]:
    n = 200
    gain = np.zeros(n)
    gain[:20] = 4.0
    gain[20:40] = 1.0
    scores = pd.DataFrame({"dunning_only": np.zeros(n), "payment_support_call": gain})
    challenger = ["payment_support_call"] * 40 + ["dunning_only"] * (n - 40)
    bau = ["dunning_only"] * n
    inclusion = np.full(n, 1.0)
    inclusion[20:40] = 0.25
    sampled = np.zeros(n, dtype=bool)
    sampled[:20] = True
    sampled[20:25] = True
    return scores, challenger, bau, inclusion, sampled


def test_inclusion_weights_recover_the_whole_frame_contrast() -> None:
    scores, challenger, bau, inclusion, sampled = _sampling_fixture()
    result = enriched_sampling_contrast(
        scores, challenger, bau, sampled=sampled, inclusion_probability=inclusion
    )
    assert result.delta == pytest.approx(0.5)
    assert result.frame_size == 200
    assert result.n_sampled == 25
    assert result.n_sampled_disagreement == 25


def test_dropping_the_inclusion_weight_biases_the_estimate() -> None:
    scores, _, _, _, sampled = _sampling_fixture()
    gain = scores["payment_support_call"].to_numpy()
    naive = gain[sampled].sum() / len(gain)
    assert naive == pytest.approx(0.425)
    assert naive != pytest.approx(0.5)


def test_zero_inclusion_on_a_disagreement_unit_is_unidentified() -> None:
    scores, challenger, bau, inclusion, sampled = _sampling_fixture()
    inclusion[0] = 0.0
    sampled[0] = False
    with pytest.raises(ContractViolation, match="not identified"):
        enriched_sampling_contrast(
            scores, challenger, bau, sampled=sampled, inclusion_probability=inclusion
        )


def test_zero_inclusion_on_the_agreement_region_is_allowed() -> None:
    scores, challenger, bau, inclusion, sampled = _sampling_fixture()
    inclusion[40:] = 0.0
    sampled[40:] = False
    result = enriched_sampling_contrast(
        scores, challenger, bau, sampled=sampled, inclusion_probability=inclusion
    )
    assert result.delta == pytest.approx(0.5)


def test_census_recruitment_has_zero_sampling_variance() -> None:
    scores, challenger, bau, _, _ = _sampling_fixture()
    n = len(scores)
    result = enriched_sampling_contrast(
        scores,
        challenger,
        bau,
        sampled=np.ones(n, dtype=bool),
        inclusion_probability=np.ones(n),
    )
    assert result.se == 0.0
    assert result.ci_low == result.ci_high == pytest.approx(result.delta)


def test_cost_to_precision_prices_the_screening_burden() -> None:
    cheap = cost_to_precision(
        1.0,
        target_half_width=0.1,
        cost_per_screened=0.01,
        cost_per_recruited=1.0,
        cost_per_outcome=2.0,
        screening_ratio=1.0,
    )
    expensive = cost_to_precision(
        1.0,
        target_half_width=0.1,
        cost_per_screened=0.01,
        cost_per_recruited=1.0,
        cost_per_outcome=2.0,
        screening_ratio=50.0,
    )
    assert cheap["n_recruited"] == expensive["n_recruited"]
    assert expensive["total_cost"] > cheap["total_cost"]
    # Sample size scales with the variance, up to the ceiling on whole units.
    quadrupled = cost_to_precision(
        4.0,
        target_half_width=0.1,
        cost_per_screened=0.0,
        cost_per_recruited=1.0,
        cost_per_outcome=0.0,
    )
    assert quadrupled["n_recruited"] == pytest.approx(4 * cheap["n_recruited"], rel=0.01)
