"""Sáu model nền của Sprint 1 chạy đúng và không suy biến.

Kiểm ở mức hợp đồng chứ không kiểm chất lượng dự báo: hàm phải trả về giá trị **hữu hạn**,
đúng hình dạng, và `clone` được theo giao ước của scikit-learn.

Hai điểm đặc thù của dự án:

- **Probability regressor phải trả xác suất, không trả nhãn cứng.** Trả nhãn cứng vẫn chạy
  được nhưng phá mọi metric xếp hạng phía sau.
- **Undersampling phải giữ outcome phụ khớp hàng.** Khi bỏ bớt dòng âm, nếu mảng outcome
  phụ không được lọc theo cùng chỉ số thì dữ liệu lệch hàng một cách âm thầm.
"""

import numpy as np
from sklearn.base import clone

from src.baselines import (
    BinaryProbabilityRegressor,
    UndersamplingCorrectedProbabilityRegressor,
    fit_t_learner_exact_undersampling,
    fit_t_learner,
    fit_x_learner,
    fit_x_learner_exact_undersampling,
)
from src.calibration import negative_keep_probability
from src.data import FEATURES, rare_outcome_undersample

import pytest

# Ca file can data/criteo-research-uplift-v2.1.csv.gz: fit model tren mau Criteo.
# Khong co du lieu thi chay: pytest -m "not requires_criteo"
pytestmark = pytest.mark.requires_criteo


def _xty(sample_df):
    X = sample_df[FEATURES].to_numpy(dtype="float64")
    T = sample_df["treatment"].to_numpy(dtype="float64")
    Y = sample_df["conversion"].to_numpy(dtype="float64")
    return X, T, Y


def test_t_learner_effect_finite(sample_1pct):
    X, T, Y = _xty(sample_1pct)
    model = fit_t_learner(X, T, Y, seed=42)
    cate = model.effect(X[:100])
    assert len(cate) == 100
    assert np.isfinite(cate).all()


def test_x_learner_effect_finite(sample_1pct):
    X, T, Y = _xty(sample_1pct)
    model = fit_x_learner(X, T, Y, seed=42)
    cate = model.effect(X[:100])
    assert len(cate) == 100
    assert np.isfinite(cate).all()


def test_t_and_x_learner_cate_mean_agree(sample_1pct):
    X, T, Y = _xty(sample_1pct)
    t_model = fit_t_learner(X, T, Y, seed=42)
    x_model = fit_x_learner(X, T, Y, seed=42)

    t_mean = np.mean(t_model.effect(X[:2000]))
    x_mean = np.mean(x_model.effect(X[:2000]))

    rel_diff = abs(t_mean - x_mean) / max(abs(t_mean), abs(x_mean), 1e-8)
    assert rel_diff < 0.5


def test_probability_regressor_returns_probabilities_not_hard_labels():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(500, 3))
    probability = 1 / (1 + np.exp(-X[:, 0]))
    y = (rng.random(500) < probability).astype(int)
    model = BinaryProbabilityRegressor(
        model_params={"n_estimators": 30, "verbose": -1, "random_state": 42}
    ).fit(X, y)
    prediction = model.predict(X[:100])

    assert np.all((0 <= prediction) & (prediction <= 1))
    assert len(np.unique(prediction)) > 2


def test_x_learner_fixed_propensity_effect_finite(sample_1pct):
    X, T, Y = _xty(sample_1pct)
    model = fit_x_learner(X, T, Y, seed=42, propensity="fixed")
    cate = model.effect(X[:100])

    assert len(cate) == 100
    assert np.isfinite(cate).all()


def test_corrected_probability_regressor_is_cloneable():
    estimator = UndersamplingCorrectedProbabilityRegressor(
        negative_keep_prob=0.2,
        model_params={"n_estimators": 10, "verbose": -1},
    )
    cloned = clone(estimator)
    assert cloned.negative_keep_prob == 0.2


def test_x_learner_exact_undersampling_effect_and_outcomes_finite(sample_1pct):
    factor = 7.0
    base_rate = sample_1pct.groupby("treatment")["conversion"].mean()
    sampled = rare_outcome_undersample(sample_1pct, factor=factor, seed=42)
    X, T, Y = _xty(sampled)
    model = fit_x_learner_exact_undersampling(
        X,
        T,
        Y,
        negative_keep_prob_control=negative_keep_probability(base_rate.loc[0], factor),
        negative_keep_prob_treatment=negative_keep_probability(base_rate.loc[1], factor),
        seed=42,
        model_params={"n_estimators": 30, "verbose": -1},
        cate_model_params={"n_estimators": 30, "verbose": -1},
    )
    X_eval = sample_1pct[FEATURES].to_numpy(dtype="float64")[:100]
    cate = model.effect(X_eval)
    mu0 = model.models[0].predict(X_eval)
    mu1 = model.models[1].predict(X_eval)

    assert np.isfinite(cate).all()
    assert np.isfinite(mu0).all() and np.isfinite(mu1).all()
    assert np.all((0 <= mu0) & (mu0 <= 1))
    assert np.all((0 <= mu1) & (mu1 <= 1))


def test_t_learner_exact_undersampling_effect_and_outcomes_finite(sample_1pct):
    factor = 7.0
    base_rate = sample_1pct.groupby("treatment")["conversion"].mean()
    sampled = rare_outcome_undersample(sample_1pct, factor=factor, seed=42)
    X, T, Y = _xty(sampled)
    model = fit_t_learner_exact_undersampling(
        X,
        T,
        Y,
        negative_keep_prob_control=negative_keep_probability(base_rate.loc[0], factor),
        negative_keep_prob_treatment=negative_keep_probability(base_rate.loc[1], factor),
        seed=42,
        model_params={"n_estimators": 30, "verbose": -1},
    )
    X_eval = sample_1pct[FEATURES].to_numpy(dtype="float64")[:100]
    effect = model.effect(X_eval)
    mu0 = model.models[0].predict(X_eval)
    mu1 = model.models[1].predict(X_eval)

    np.testing.assert_allclose(effect.ravel(), mu1 - mu0)
    assert np.isfinite(effect).all()
    assert np.all((0 <= mu0) & (mu0 <= 1))
    assert np.all((0 <= mu1) & (mu1 <= 1))
