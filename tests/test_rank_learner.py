import numpy as np
import pytest

from src.policy_evaluation import policy_area_from_scores
from src.rank_learner import RankLearner, cross_fitted_dr_score
from src.ranking_metrics import autoc_score
from tests.synthetic_rct import make_synthetic_rct


def test_cross_fitted_dr_score_recovers_ate():
    data = make_synthetic_rct(n=60_000, base_rate=0.10, effect_scale=0.05, seed=40)
    result = cross_fitted_dr_score(
        data.X,
        data.treatment,
        data.outcome,
        propensity=data.propensity,
        n_folds=3,
        seed=1,
    )
    standard_error = float(
        np.std(result["dr_score"], ddof=1) / np.sqrt(len(result["dr_score"]))
    )
    assert abs(float(np.mean(result["dr_score"])) - data.ate) < 4 * standard_error
    assert np.isfinite(result["plugin_tau"]).all()
    assert np.all((result["mu0"] >= 0) & (result["mu0"] <= 1))
    assert np.all((result["mu1"] >= 0) & (result["mu1"] <= 1))


def test_rank_learner_ranks_better_than_random_on_holdout():
    train = make_synthetic_rct(n=60_000, base_rate=0.10, effect_scale=0.05, seed=41)
    test = make_synthetic_rct(n=60_000, base_rate=0.10, effect_scale=0.05, seed=42)
    model = RankLearner(
        seed=7,
        rank_params={"n_estimators": 120, "min_child_samples": 200},
        nuisance_params={"n_estimators": 120, "min_child_samples": 200},
    ).fit(train.X, train.treatment, train.outcome, propensity=train.propensity)
    score = model.predict(test.X)

    oracle_signal = (
        test.mu1
        - test.mu0
        + test.treatment * (test.outcome - test.mu1) / test.propensity
        - (1 - test.treatment) * (test.outcome - test.mu0) / (1 - test.propensity)
    )
    rng = np.random.default_rng(0)
    assert autoc_score(oracle_signal, score) > autoc_score(
        oracle_signal,
        rng.random(len(score)),
    )
    assert policy_area_from_scores(oracle_signal, score) > policy_area_from_scores(
        oracle_signal,
        rng.random(len(score)),
    )
    # Score phải tương quan dương với tau thật, không chỉ tốt hơn ngẫu nhiên.
    assert np.corrcoef(score, test.tau)[0, 1] > 0.3


def test_rank_learner_score_is_finite_and_not_constant():
    data = make_synthetic_rct(n=30_000, base_rate=0.08, effect_scale=0.04, seed=43)
    model = RankLearner(
        seed=3,
        rank_params={"n_estimators": 60, "min_child_samples": 200},
        nuisance_params={"n_estimators": 60, "min_child_samples": 200},
    ).fit(data.X, data.treatment, data.outcome, propensity=data.propensity)
    score = model.predict(data.X)
    assert np.isfinite(score).all()
    assert np.unique(score).size > 100
    assert model.kappa_ > 0


def test_rank_learner_is_reproducible_for_same_seed():
    data = make_synthetic_rct(n=20_000, base_rate=0.08, effect_scale=0.04, seed=44)
    params = {
        "rank_params": {"n_estimators": 40, "min_child_samples": 200},
        "nuisance_params": {"n_estimators": 40, "min_child_samples": 200},
    }
    first = RankLearner(seed=5, **params).fit(
        data.X, data.treatment, data.outcome, propensity=data.propensity
    )
    second = RankLearner(seed=5, **params).fit(
        data.X, data.treatment, data.outcome, propensity=data.propensity
    )
    np.testing.assert_allclose(first.predict(data.X), second.predict(data.X))


def test_rank_learner_rejects_mismatched_lengths():
    data = make_synthetic_rct(n=2_000, seed=45)
    model = RankLearner()
    with pytest.raises(ValueError):
        model.fit(
            data.X,
            data.treatment[:-1],
            data.outcome,
            propensity=data.propensity,
        )


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        RankLearner().predict(np.zeros((4, 3)))
