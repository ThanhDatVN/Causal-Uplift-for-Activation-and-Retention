"""Biểu diễn sentinel và họ funnel S-learner.

Vòng data optimization đưa cấu trúc sentinel thành feature tường minh. Bốn điều phải đúng:

- **Augmenter chỉ fit trên point mass thật sự chiếm ưu thế**, không tạo cờ cho mọi giá trị;
- **Undersampling giữ outcome phụ khớp hàng** — cùng lỗi lệch hàng như ở `test_baselines`;
- **Dạng nén cho dự đoán trùng khít dạng dày.** Chuyển sang dtype hỗn hợp là để tiết kiệm
  RAM; nếu nó đổi kết quả thì đó không còn là tối ưu mà là một model khác;
- **Funnel S-learner từ chối vi phạm bất biến hậu can thiệp** — nó dùng `visit` làm biến
  trung gian, nên phải có chốt chặn không cho `visit` lọt vào feature.
"""

import numpy as np
import pytest

from src.candidates import (
    FitContext,
    SentinelFeatureAugmenter,
    build_funnel_s_learner,
    build_response,
    rare_outcome_undersample_indices,
)


def test_sentinel_augmenter_fits_only_dominant_point_masses():
    X = np.array(
        [
            [0, 0, 5],
            [0, 1, 5],
            [0, 2, 5],
            [0, 3, 5],
            [1, 4, 5],
            [2, 5, 4],
        ],
        dtype="float32",
    )
    augmenter = SentinelFeatureAugmenter(
        min_mode_share=0.5,
        sample_size=100,
        seed=7,
    ).fit(X)
    transformed = augmenter.transform(X)

    np.testing.assert_array_equal(augmenter.active_columns_, [0, 2])
    assert transformed.shape == (6, 6)  # 3 raw + 2 flags + count
    np.testing.assert_array_equal(transformed[0, -3:], [1, 1, 2])
    np.testing.assert_array_equal(transformed[-1, -3:], [0, 0, 0])
    assert transformed.dtype == np.float32
    assert transformed.flags.c_contiguous
    compact = augmenter.transform_compact(X)
    np.testing.assert_array_equal(
        compact.to_numpy(dtype="float32"),
        transformed,
    )
    assert compact.iloc[:, -3:-1].dtypes.tolist() == [bool, bool]
    assert compact.iloc[:, -1].dtype == np.dtype("uint8")


def test_undersampling_keeps_auxiliary_outcome_aligned():
    treatment = np.repeat([0, 1], 20)
    outcome = np.tile([1, 0, 0, 0, 0], 8)
    visit = np.maximum(outcome, np.tile([0, 1], 20)).astype("int8")
    context = FitContext(
        X=np.arange(80, dtype="float32").reshape(40, 2),
        treatment=treatment,
        outcome=outcome,
        propensity=0.5,
        seed=11,
        params={"under": 2.0},
        auxiliary_outcomes={"visit": visit},
    )
    selected = rare_outcome_undersample_indices(
        treatment,
        outcome,
        factor=2.0,
        seed=11,
    )
    sampled, factor = context.undersampled()

    assert factor == 2.0
    np.testing.assert_array_equal(sampled.X, context.X[selected])
    np.testing.assert_array_equal(sampled.auxiliary_outcomes["visit"], visit[selected])


def test_compact_sentinel_frame_preserves_response_predictions():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(2_000, 3)).astype("float32")
    X[rng.random(len(X)) < 0.7, 0] = 0.0
    treatment = rng.binomial(1, 0.5, size=len(X)).astype("int8")
    outcome = rng.binomial(1, 0.1 + 0.1 * (X[:, 1] > 0)).astype("int8")
    common = {
        "feature_augmentation": "sentinel_flags",
        "sentinel_min_mode_share": 0.5,
        "params": {
            "n_estimators": 40,
            "min_child_samples": 20,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
    }

    def fit(threshold):
        context = FitContext(
            X=X,
            treatment=treatment,
            outcome=outcome,
            propensity=0.5,
            seed=13,
            params={**common, "sentinel_compact_threshold_rows": threshold},
        )
        return build_response(context)(X[:200])

    np.testing.assert_allclose(fit(10_000), fit(0), rtol=0.0, atol=0.0)


def test_funnel_s_learner_recovers_synthetic_conversion_ranking():
    rng = np.random.default_rng(42)
    n_train = 8_000
    n_test = 2_000
    X = rng.normal(size=(n_train + n_test, 2)).astype("float32")
    treatment = rng.binomial(1, 0.5, size=n_train + n_test).astype("int8")

    def sigmoid(value):
        return 1.0 / (1.0 + np.exp(-value))

    def probabilities(matrix, arm):
        visit_probability = sigmoid(
            -1.6 + 0.8 * matrix[:, 0] + 0.5 * arm + 0.7 * arm * matrix[:, 0]
        )
        conditional_conversion = sigmoid(
            -2.0 + 0.7 * matrix[:, 0] + 0.2 * arm + 0.5 * arm * matrix[:, 0]
        )
        return visit_probability, conditional_conversion

    observed_visit_p, observed_conversion_given_visit = probabilities(X, treatment)
    visit = rng.binomial(1, observed_visit_p).astype("int8")
    conversion = (
        visit * rng.binomial(1, observed_conversion_given_visit)
    ).astype("int8")

    train = slice(0, n_train)
    test = slice(n_train, None)
    context = FitContext(
        X=X[train],
        treatment=treatment[train],
        outcome=conversion[train],
        propensity=0.5,
        seed=9,
        params={
            "params": {
                "n_estimators": 100,
                "learning_rate": 0.08,
                "min_child_samples": 40,
                "reg_alpha": 0.0,
                "reg_lambda": 1.0,
            }
        },
        outcome_name="conversion",
        auxiliary_outcomes={"visit": visit[train]},
    )
    predict = build_funnel_s_learner(context)
    score = predict(X[test])
    visit0, conversion0 = probabilities(X[test], 0)
    visit1, conversion1 = probabilities(X[test], 1)
    true_tau = visit1 * conversion1 - visit0 * conversion0

    assert np.isfinite(score).all()
    assert np.std(score) > 0
    assert np.corrcoef(score, true_tau)[0, 1] > 0.65


def test_funnel_s_learner_rejects_post_treatment_invariant_violation():
    context = FitContext(
        X=np.zeros((4, 2), dtype="float32"),
        treatment=np.array([0, 0, 1, 1]),
        outcome=np.array([1, 0, 0, 1]),
        propensity=0.5,
        seed=1,
        outcome_name="conversion",
        auxiliary_outcomes={"visit": np.array([0, 1, 1, 1])},
    )
    with pytest.raises(ValueError, match="conversion <= visit"):
        build_funnel_s_learner(context)
