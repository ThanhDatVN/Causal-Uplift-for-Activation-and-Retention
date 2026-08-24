"""DINA, Anchored R và Pattern R — kiểm trước khi chạm dữ liệu thật.

Ba estimator này được hiện thực từ công thức, nên phải kiểm công thức trước khi tin kết quả:

- **Gradient và Hessian của DINA khớp sai phân hữu hạn.** Sai đạo hàm thì tối ưu hóa vẫn
  chạy và vẫn hội tụ về đâu đó, chỉ là sai chỗ.
- **Mỗi learner khôi phục đúng thứ hạng đã biết trên dữ liệu sinh** — DINA trên thang
  log-odds, Anchored R trên thang tuyệt đối, Pattern R nhận ra moderator dạng sentinel.
- **Tham số khóa không hợp lệ bị từ chối**: shrinkage, prior và ngưỡng cắt xác suất ngoài
  miền cho phép.

`test_sentinel_pattern_id_is_fold_local_and_stable` chặn một lỗi tinh vi: mã pattern phải
được tính **trong từng fold**, nếu không thông tin từ fold test rò sang fold train.
"""

import numpy as np
import pytest
from scipy.special import expit

from src.candidates import (
    BinaryDINALoss,
    FitContext,
    SentinelFeatureAugmenter,
    build_anchored_pattern_r_learner,
    build_anchored_r_learner,
    build_binary_dina_learner,
)


SMALL_NUISANCE = {
    "n_estimators": 60,
    "learning_rate": 0.08,
    "num_leaves": 15,
    "min_child_samples": 40,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
}
SMALL_FINAL = {
    "n_estimators": 80,
    "learning_rate": 0.06,
    "num_leaves": 7,
    "min_child_samples": 80,
    "reg_alpha": 0.0,
    "reg_lambda": 2.0,
}


def _sample_binary_outcome(
    rng: np.random.Generator,
    probability: np.ndarray,
) -> np.ndarray:
    return rng.binomial(1, probability).astype("int8")


def test_sentinel_pattern_id_is_fold_local_and_stable():
    X = np.array(
        [
            [0, 5, 9],
            [0, 6, 9],
            [0, 7, 8],
            [1, 8, 9],
        ],
        dtype="float32",
    )
    augmenter = SentinelFeatureAugmenter(min_mode_share=0.5).fit(X)

    np.testing.assert_array_equal(augmenter.active_columns_, [0, 2])
    np.testing.assert_array_equal(augmenter.pattern_id(X), [3, 3, 1, 2])
    np.testing.assert_array_equal(
        augmenter.pattern_id(np.array([[2, 0, 7]], dtype="float32")),
        [0],
    )


def test_binary_dina_loss_matches_finite_difference_derivatives():
    y = np.array([0.0, 1.0, 0.0, 1.0])
    z = np.array([-0.7, 0.3, -0.2, 0.8])
    offset = np.array([-2.0, -1.0, 0.5, 1.2])
    raw = np.array([-0.4, 0.2, 0.3, -0.1])
    objective = BinaryDINALoss(z, offset)
    gradient, hessian = objective(y, raw)

    def loss(value):
        eta = offset + z * value
        return np.logaddexp(0.0, eta) - y * eta

    epsilon = 1e-4
    numerical_gradient = (loss(raw + epsilon) - loss(raw - epsilon)) / (
        2.0 * epsilon
    )
    numerical_hessian = (
        loss(raw + epsilon) - 2.0 * loss(raw) + loss(raw - epsilon)
    ) / epsilon**2

    np.testing.assert_allclose(gradient, numerical_gradient, rtol=1e-6, atol=1e-7)
    np.testing.assert_allclose(hessian, numerical_hessian, rtol=2e-5, atol=2e-7)


def test_binary_dina_recovers_heterogeneous_log_odds_ranking():
    rng = np.random.default_rng(17)
    n_train = 10_000
    n_test = 3_000
    X = rng.normal(size=(n_train + n_test, 3)).astype("float32")
    treatment = rng.binomial(1, 0.7, size=len(X)).astype("int8")
    eta0 = -3.0 + 0.6 * X[:, 0] - 0.25 * X[:, 2]
    log_odds_effect = 0.3 + 0.9 * np.tanh(X[:, 1])
    p0 = expit(eta0)
    p1 = expit(eta0 + log_odds_effect)
    observed_probability = np.where(treatment == 1, p1, p0)
    outcome = _sample_binary_outcome(rng, observed_probability)

    context = FitContext(
        X=X[:n_train],
        treatment=treatment[:n_train],
        outcome=outcome[:n_train],
        propensity=0.7,
        seed=19,
        params={
            "inner_cv": 2,
            "probability_clip": 1e-4,
            "effect_clip": 3.0,
            "nuisance_params": SMALL_NUISANCE,
            "final_params": SMALL_FINAL,
        },
    )
    score = build_binary_dina_learner(context)(X[n_train:])
    true_cate = p1[n_train:] - p0[n_train:]

    assert np.isfinite(score).all()
    assert np.std(score) > 0
    assert np.corrcoef(score, true_cate)[0, 1] > 0.35


def test_anchored_r_learner_recovers_synthetic_absolute_cate_ranking():
    rng = np.random.default_rng(23)
    n_train = 12_000
    n_test = 3_000
    X = rng.normal(size=(n_train + n_test, 3)).astype("float32")
    treatment = rng.binomial(1, 0.65, size=len(X)).astype("int8")
    p0 = expit(-2.7 + 0.9 * X[:, 0] - 0.3 * X[:, 2])
    true_cate = 0.12 * p0 + 0.035 * np.tanh(X[:, 1])
    p1 = np.clip(p0 + true_cate, 0.001, 0.999)
    observed_probability = np.where(treatment == 1, p1, p0)
    outcome = _sample_binary_outcome(rng, observed_probability)

    context = FitContext(
        X=X[:n_train],
        treatment=treatment[:n_train],
        outcome=outcome[:n_train],
        propensity=0.65,
        seed=29,
        params={
            "inner_cv": 2,
            "residual_shrinkage": 0.25,
            "nuisance_params": SMALL_NUISANCE,
            "final_params": SMALL_FINAL,
        },
    )
    score = build_anchored_r_learner(context)(X[n_train:])

    assert np.isfinite(score).all()
    assert np.std(score) > 0
    assert np.corrcoef(score, true_cate[n_train:])[0, 1] > 0.25


def test_anchored_pattern_r_learner_recovers_sentinel_moderator():
    rng = np.random.default_rng(31)
    n_train = 14_000
    n_test = 3_000
    sentinel = rng.binomial(1, 0.75, size=n_train + n_test) == 1
    X = np.column_stack(
        [
            np.where(sentinel, 0.0, rng.normal(2.0, 0.2, size=len(sentinel))),
            rng.normal(size=len(sentinel)),
        ]
    ).astype("float32")
    treatment = rng.binomial(1, 0.6, size=len(X)).astype("int8")
    p0 = expit(-3.0 + 0.25 * X[:, 1])
    true_cate = np.where(sentinel, 0.01, 0.09)
    p1 = p0 + true_cate
    outcome = _sample_binary_outcome(
        rng,
        np.where(treatment == 1, p1, p0),
    )

    context = FitContext(
        X=X[:n_train],
        treatment=treatment[:n_train],
        outcome=outcome[:n_train],
        propensity=0.6,
        seed=37,
        params={
            "inner_cv": 2,
            "pattern_prior_weight": 10.0,
            "sentinel_min_mode_share": 0.5,
            "nuisance_params": SMALL_NUISANCE,
        },
    )
    score = build_anchored_pattern_r_learner(context)(X[n_train:])
    test_sentinel = sentinel[n_train:]

    assert np.isfinite(score).all()
    assert score[~test_sentinel].mean() > score[test_sentinel].mean() + 0.02


@pytest.mark.parametrize(
    ("builder", "params", "message"),
    [
        (build_anchored_r_learner, {"residual_shrinkage": 1.1}, "shrinkage"),
        (
            build_anchored_pattern_r_learner,
            {"pattern_prior_weight": -1.0},
            "prior_weight",
        ),
        (build_binary_dina_learner, {"probability_clip": 0.5}, "probability_clip"),
    ],
)
def test_foundation_learners_reject_invalid_locked_parameters(
    builder,
    params,
    message,
):
    context = FitContext(
        X=np.zeros((8, 2), dtype="float32"),
        treatment=np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype="int8"),
        outcome=np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype="int8"),
        propensity=0.5,
        seed=1,
        params=params,
    )

    with pytest.raises(ValueError, match=message):
        builder(context)
