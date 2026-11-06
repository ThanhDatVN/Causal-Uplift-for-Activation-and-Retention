import numpy as np
import pandas as pd

from telco_churn.model_tournament import select_candidate
from telco_churn.uplift import (
    CatBoostFrameClassifier,
    _augment_s_features,
    ate_with_wald_interval,
    bootstrap_selected_effect,
    curve_metrics,
    doubly_robust_scores,
    ipw_scores,
    required_sample_size,
    top_fraction_mask,
)


def test_s_learner_interactions_are_vectorized_and_point_in_time() -> None:
    features = pd.DataFrame({"numeric": [1.0, 2.0], "factor": ["a", "b"]})
    augmented = _augment_s_features(features, treatment=np.array([0, 1]), interactions=True)

    assert augmented["_treatment"].tolist() == [0, 1]
    assert augmented["_tx_numeric"].tolist() == [0.0, 2.0]
    assert "_tx_factor" not in augmented


def test_tournament_one_se_rule_prefers_simpler_eligible_model() -> None:
    table = pd.DataFrame(
        [
            {
                "model": "risk_logistic",
                "family": "risk",
                "complexity": 1,
                "qini_dr_mean": 0.010,
                "qini_dr_se": 0.002,
                "qini_ipw_mean": 0.009,
                "qini_dr_positive_rate": 1.0,
                "dr_uplift_20_mean": 0.02,
                "delta_vs_risk_ci95_low": 0.0,
                "beats_risk_rate": 0.0,
            },
            {
                "model": "dr_hgb",
                "family": "dr_learner",
                "complexity": 7,
                "qini_dr_mean": 0.011,
                "qini_dr_se": 0.002,
                "qini_ipw_mean": 0.010,
                "qini_dr_positive_rate": 1.0,
                "dr_uplift_20_mean": 0.02,
                "delta_vs_risk_ci95_low": -0.001,
                "beats_risk_rate": 2 / 3,
            },
        ]
    )

    decision = select_candidate(table, repeats=3)

    assert decision["mean_best_model"] == "dr_hgb"
    assert decision["development_champion"] == "risk_logistic"
    assert decision["causal_replacement"] == "none"


def test_effect_scores_use_prevented_churn_sign() -> None:
    outcome = np.array([1, 0, 0, 0])
    treatment = np.array([0, 0, 1, 1])
    ipw = ipw_scores(outcome, treatment, propensity=0.5)
    dr = doubly_robust_scores(
        outcome,
        treatment,
        p0=np.full(4, 0.25),
        p1=np.zeros(4),
        propensity=0.5,
    )

    assert ipw.mean() == 0.5
    assert dr.mean() == 0.5


def test_top_fraction_is_exact_and_tie_stable_by_id() -> None:
    mask = top_fraction_mask(np.array([0.9, 0.9, 0.2]), np.array(["b", "a", "c"]), fraction=1 / 3)
    assert mask.tolist() == [False, True, False]


def test_qini_rewards_correct_effect_ranking() -> None:
    effect = np.array([0.4, 0.3, -0.2, -0.1])
    correct = curve_metrics(np.array([4, 3, 2, 1]), effect)
    reversed_ranking = curve_metrics(np.array([1, 2, 3, 4]), effect)

    assert correct["qini"] > 0
    assert correct["qini"] > reversed_ranking["qini"]


def test_ate_and_power_calculation_are_auditable() -> None:
    outcome = np.array([1, 0, 1, 0, 0, 0, 0, 0])
    treatment = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    estimate = ate_with_wald_interval(outcome, treatment)
    smaller_effect_n = required_sample_size(0.05, 0.04, 0.5, 0.005)
    larger_effect_n = required_sample_size(0.05, 0.04, 0.5, 0.01)

    assert estimate["ate_prevented_churn"] == 0.5
    assert smaller_effect_n > larger_effect_n


def test_bootstrap_selected_effect_ignores_unselected_rows() -> None:
    result = bootstrap_selected_effect(
        np.array([True, True, False]),
        np.array([0.2, 0.4, -100.0]),
        repeats=100,
        seed=7,
    )
    assert np.isclose(result["estimate"], 0.3)
    assert result["ci95_low"] >= 0.2
    assert result["ci95_high"] <= 0.4


def test_catboost_wrapper_imputes_from_training_not_from_the_scoring_batch() -> None:
    """Regression for mutation Q04.

    Imputing from the incoming batch made a prediction depend on which other
    rows happened to be scored alongside it, so a chunked batch and the full
    frame could disagree for the same account.
    """

    values = np.concatenate([np.full(15, 1.0), np.full(15, 100.0)])
    frame = pd.DataFrame({"arrears": values, "segment": ["x"] * 15 + ["y"] * 15})
    frame.loc[0, "arrears"] = np.nan
    frame.loc[20, "arrears"] = np.nan
    outcome = (values > 50).astype(int)

    model = CatBoostFrameClassifier(seed=7, iterations=10, depth=2).fit(frame, outcome)
    assert model.numeric_fill_["arrears"] == np.median(values[~np.isnan(frame["arrears"])])

    whole = model.predict_proba(frame)[:, 1]
    chunked = np.concatenate(
        [
            model.predict_proba(frame.iloc[:15])[:, 1],
            model.predict_proba(frame.iloc[15:])[:, 1],
        ]
    )
    single_rows = np.concatenate(
        [model.predict_proba(frame.iloc[[index]])[:, 1] for index in range(len(frame))]
    )
    permutation = np.array(
        [
            7,
            2,
            9,
            0,
            4,
            1,
            8,
            3,
            6,
            5,
            19,
            12,
            25,
            20,
            24,
            11,
            28,
            13,
            26,
            15,
            29,
            22,
            18,
            10,
            14,
            21,
            17,
            23,
            16,
            27,
        ]
    )
    permuted = model.predict_proba(frame.iloc[permutation])[:, 1]

    assert np.array_equal(whole, chunked)
    assert np.array_equal(whole, single_rows)
    assert np.array_equal(whole[permutation], permuted)
