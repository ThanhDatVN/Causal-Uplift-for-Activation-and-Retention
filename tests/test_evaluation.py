"""Metric xếp hạng, đối chiếu với một hiện thực độc lập.

Qini, AUUC và uplift curve được so trực tiếp với `scikit-uplift`. Đây là tầng bảo vệ mạnh
nhất cho nhóm metric: hai hiện thực viết độc lập khó sai giống hệt nhau.

Ngoài ra có ba **negative control** — trường hợp mà kết quả đúng đã biết trước:

- hai bộ điểm giống hệt nhau phải cho chênh lệch đúng bằng 0 và CI suy biến;
- dữ liệu không có conversion phải trả `nan` hoặc báo lỗi rõ ràng, không crash;
- transformed outcome phải có kỳ vọng có điều kiện đúng bằng hiệu ứng thật.

Negative control quan trọng ngang positive test: một metric luôn trả về số đẹp thì không
phân biệt được với một metric hỏng.
"""

import numpy as np
import pytest
from sklift.metrics import (
    qini_auc_score,
    qini_curve as sklift_qini_curve,
    uplift_auc_score,
    uplift_curve as sklift_uplift_curve,
)

from src.evaluation import (
    auuc_score,
    bootstrap_ci,
    paired_bootstrap_difference_ci,
    paired_bootstrap_compare,
    paired_qini_bootstrap_matrix,
    qini_curve,
    qini_score,
    transformed_outcome,
    transformed_outcome_mse,
    uplift_calibration_error,
    uplift_curve,
)


def _synthetic_uplift_data(n=200, seed=0):
    rng = np.random.default_rng(seed)
    treatment = rng.integers(0, 2, size=n).astype(float)
    uplift_score = rng.normal(size=n)  # continuous -> ~0 probability of exact ties
    base_rate = 0.2 + 0.3 * (uplift_score > 0) * treatment
    y_true = (rng.random(n) < base_rate).astype(float)
    return y_true, treatment, uplift_score


@pytest.fixture(scope="module")
def synthetic_data():
    return _synthetic_uplift_data()


def test_qini_curve_matches_sklift(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data

    ours = qini_curve(y_true, treatment, uplift_score)
    ref_n, ref_qini = sklift_qini_curve(y_true, uplift_score, treatment)

    np.testing.assert_allclose(ours["n_targeted"].to_numpy(), ref_n)
    np.testing.assert_allclose(ours["qini"].to_numpy(), ref_qini, atol=1e-9)


def test_qini_score_matches_sklift(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data

    ours = qini_score(y_true, treatment, uplift_score)
    ref = qini_auc_score(y_true, uplift_score, treatment)

    assert abs(ours - ref) < 1e-6


def test_bootstrap_ci_negative_control(synthetic_data):
    y_true, treatment, _ = synthetic_data
    rng = np.random.default_rng(123)
    noise_score = rng.normal(size=len(y_true))

    lb, ub = bootstrap_ci(y_true, treatment, noise_score, n_boot=300, seed=42)
    assert lb <= 0 <= ub


def test_fast_weighted_bootstrap_matches_expanded_resample(synthetic_data):
    from src.evaluation import _weighted_qini_score

    y_true, treatment, uplift_score = synthetic_data
    rng = np.random.default_rng(99)
    idx = rng.integers(0, len(y_true), size=len(y_true))
    weight = np.bincount(idx, minlength=len(y_true)).astype(float)
    order = np.argsort(uplift_score, kind="mergesort")[::-1]
    perfect = y_true * treatment - y_true * (1 - treatment)
    perfect_order = np.argsort(perfect, kind="mergesort")[::-1]

    fast = _weighted_qini_score(
        y_true,
        treatment,
        uplift_score,
        weight,
        order,
        perfect_order,
    )
    expanded = qini_score(y_true[idx], treatment[idx], uplift_score[idx])
    assert fast == pytest.approx(expanded, abs=1e-12)


def test_paired_bootstrap_compare_identical_scores(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data

    p_value = paired_bootstrap_compare(uplift_score, uplift_score, y_true, treatment, n_boot=200, seed=42)
    assert p_value == pytest.approx(1.0)


def test_paired_bootstrap_difference_ci_identical_scores(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data
    result = paired_bootstrap_difference_ci(
        uplift_score,
        uplift_score,
        y_true,
        treatment,
        n_boot=100,
        seed=42,
    )
    assert result["observed_difference"] == pytest.approx(0.0)
    assert result["ci_low"] == pytest.approx(0.0)
    assert result["ci_high"] == pytest.approx(0.0)


def test_paired_qini_bootstrap_matrix_preserves_identical_pair(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data
    result = paired_qini_bootstrap_matrix(
        {"a": uplift_score, "b": uplift_score},
        y_true,
        treatment,
        n_boot=50,
        seed=42,
    )
    np.testing.assert_allclose(result["draws"][:, 0], result["draws"][:, 1])
    np.testing.assert_allclose(result["observed"][0], result["observed"][1])


def test_uplift_curve_matches_sklift(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data

    ours = uplift_curve(y_true, treatment, uplift_score)
    ref_n, ref_uplift = sklift_uplift_curve(y_true, uplift_score, treatment)

    np.testing.assert_allclose(ours["n_targeted"].to_numpy(), ref_n)
    np.testing.assert_allclose(ours["uplift"].to_numpy(), ref_uplift, atol=1e-9)


def test_auuc_score_matches_sklift(synthetic_data):
    y_true, treatment, uplift_score = synthetic_data

    ours = auuc_score(y_true, treatment, uplift_score)
    ref = uplift_auc_score(y_true, uplift_score, treatment)

    assert abs(ours - ref) < 1e-6


def test_qini_score_no_conversion_returns_nan_not_crash():
    n = 50
    rng = np.random.default_rng(1)
    treatment = rng.integers(0, 2, size=n).astype(float)
    uplift_score = rng.normal(size=n)
    y_true = np.zeros(n)  # không có conversion nào -> auc_perfect == 0

    with pytest.warns(RuntimeWarning):
        result = qini_score(y_true, treatment, uplift_score)
    assert np.isnan(result)


def test_bootstrap_ci_no_conversion_raises_clear_error():
    n = 50
    rng = np.random.default_rng(1)
    treatment = rng.integers(0, 2, size=n).astype(float)
    uplift_score = rng.normal(size=n)
    y_true = np.zeros(n)  # mọi resample đều NaN -> phải raise ValueError rõ ràng, không crash mù mờ

    with pytest.raises(ValueError, match="NaN"):
        bootstrap_ci(y_true, treatment, uplift_score, n_boot=20, seed=42)


def test_transformed_outcome_has_correct_conditional_mean():
    rng = np.random.default_rng(11)
    n = 200_000
    x = rng.integers(0, 2, size=n)
    treatment = rng.binomial(1, 0.8, size=n)
    true_effect = 0.1 + 0.2 * x
    probability = 0.2 + treatment * true_effect
    y_true = (rng.random(n) < probability).astype(float)
    pseudo = transformed_outcome(y_true, treatment, propensity=0.8)

    np.testing.assert_allclose(
        [pseudo[x == 0].mean(), pseudo[x == 1].mean()],
        [0.1, 0.3],
        atol=0.015,
    )


def test_transformed_outcome_mse_prefers_true_effect():
    y_true, treatment, uplift_score = _synthetic_uplift_data(n=20_000, seed=17)
    correct = 0.3 * (uplift_score > 0)
    wrong = -correct

    assert transformed_outcome_mse(y_true, treatment, correct) < transformed_outcome_mse(
        y_true, treatment, wrong
    )


def test_transformed_outcome_validates_shapes_and_binary_treatment():
    with pytest.raises(ValueError, match="cùng shape"):
        transformed_outcome([0, 1], [1])
    with pytest.raises(ValueError, match="chỉ gồm 0/1"):
        transformed_outcome([0, 1], [0, 2])


def test_uplift_calibration_error_small_for_large_calibrated_sample():
    rng = np.random.default_rng(19)
    n = 200_000
    score = rng.uniform(0.02, 0.18, size=n)
    treatment = rng.binomial(1, 0.5, size=n)
    probability = 0.2 + treatment * score
    y_true = (rng.random(n) < probability).astype(float)

    assert uplift_calibration_error(y_true, treatment, score, n_bins=10) < 0.015
