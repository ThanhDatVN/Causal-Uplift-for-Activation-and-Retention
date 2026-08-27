"""Khôi phục thang xác suất sau undersampling.

Undersampling phá thang xác suất — xem
`docs/methods/02_CALIBRATION_AND_POLICY_VALUE.md`. Hai điều phải đúng:

- **Phép khôi phục là nghịch đảo của phép lấy mẫu.** Áp sampling map rồi áp restoration
  phải quay về giá trị ban đầu.
- **Tỷ lệ đích đạt được thật.** `negative_keep_probability` phải cho ra đúng prevalence
  được yêu cầu, không xấp xỉ.

Isotonic calibrator phải **đơn điệu** và từ chối điểm không hữu hạn thay vì lan `nan` ra
toàn bộ pipeline.
"""

import numpy as np
import pytest

from src.calibration import (
    TauIsotonicCalibrator,
    negative_keep_probability,
    restore_undersampled_probability,
    sampled_probability,
)


def test_exact_probability_restoration_inverts_sampling_map():
    original = np.linspace(0, 1, 101)
    keep_probability = 0.12
    sampled = sampled_probability(original, keep_probability)
    restored = restore_undersampled_probability(sampled, keep_probability)
    np.testing.assert_allclose(restored, original, atol=1e-12)


def test_negative_keep_probability_reaches_requested_prevalence():
    p = 0.003
    factor = 7.0
    s = negative_keep_probability(p, factor)
    sampled_p = sampled_probability(np.array([p]), s)[0]
    assert sampled_p == pytest.approx(factor * p)


def test_isotonic_calibrator_is_finite_and_monotone():
    rng = np.random.default_rng(17)
    n = 50_000
    raw_score = rng.uniform(-0.15, 0.25, size=n)
    treatment = rng.binomial(1, 0.7, size=n)
    true_effect = np.clip(0.02 + 0.4 * raw_score, -0.03, 0.12)
    probability = np.clip(0.15 + treatment * true_effect, 0.001, 0.999)
    y_true = rng.binomial(1, probability)
    calibrator = TauIsotonicCalibrator().fit(
        raw_score,
        y_true,
        treatment,
        propensity=0.7,
    )
    grid = np.linspace(raw_score.min(), raw_score.max(), 1000)
    prediction = calibrator.predict(grid)

    assert np.isfinite(prediction).all()
    assert np.all(np.diff(prediction) >= -1e-12)


def test_isotonic_calibrator_rejects_non_finite_scores():
    with pytest.raises(ValueError, match="hữu hạn"):
        TauIsotonicCalibrator().fit(
            [0.1, np.nan],
            [0, 1],
            [0, 1],
            propensity=0.5,
        )
