"""Hiệu chỉnh uplift sau stratified undersampling.

Các công thức exact probability restoration theo Nyberg & Klami (2023),
DOI: 10.1007/s10618-023-00917-9. Ký hiệu ``q`` bên dưới là xác suất outcome
trong dữ liệu đã undersample; ``s`` là xác suất giữ một negative.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression

from src.evaluation import transformed_outcome


def negative_keep_probability(base_rate: float, factor: float) -> float:
    """Xác suất giữ negative để prevalence sau lấy mẫu bằng ``factor * base_rate``.

    Giữ toàn bộ positive và lấy mỗi negative với xác suất
    ``s = (1 / factor - p) / (1 - p)``.
    """
    p = float(base_rate)
    k = float(factor)
    if not 0 < p < 1:
        raise ValueError("base_rate phải nằm trong (0, 1)")
    if k < 1:
        raise ValueError("factor phải >= 1")
    if k >= 1.0 / p:
        raise ValueError("factor phải nhỏ hơn 1 / base_rate")
    return float((1.0 / k - p) / (1.0 - p))


def sampled_probability(original_probability, negative_keep_prob: float) -> np.ndarray:
    """Forward map dùng cho kiểm thử: ``q = p / (p + s(1-p))``."""
    p = np.asarray(original_probability, dtype="float64")
    s = float(negative_keep_prob)
    if not 0 < s <= 1:
        raise ValueError("negative_keep_prob phải nằm trong (0, 1]")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("original_probability phải nằm trong [0, 1]")
    return p / (p + s * (1.0 - p))


def restore_undersampled_probability(
    sampled_probability_value,
    negative_keep_prob: float,
) -> np.ndarray:
    """Khôi phục xác suất gốc: ``p = s*q / (1 - q*(1-s))``.

    Công thức được áp dụng riêng cho control và treatment trước khi lấy hiệu.
    """
    q = np.asarray(sampled_probability_value, dtype="float64")
    s = float(negative_keep_prob)
    if not 0 < s <= 1:
        raise ValueError("negative_keep_prob phải nằm trong (0, 1]")
    if np.any((q < 0) | (q > 1)):
        raise ValueError("sampled_probability phải nằm trong [0, 1]")
    denominator = 1.0 - q * (1.0 - s)
    restored = s * q / denominator
    return np.clip(restored, 0.0, 1.0)


class TauIsotonicCalibrator:
    """Hiệu chỉnh đơn điệu từ CATE score sang transformed outcome trên validation.

    Isotonic calibration thay đổi scale nhưng giữ thứ tự không giảm. Nó chỉ được
    fit trên validation độc lập; confirmation/final holdout không tham gia fit.
    """

    def __init__(self, out_of_bounds: str = "clip"):
        self.out_of_bounds = out_of_bounds

    def fit(
        self,
        score,
        y_true,
        treatment,
        propensity: float | None = None,
    ) -> "TauIsotonicCalibrator":
        score = np.asarray(score, dtype="float64").ravel()
        y_true = np.asarray(y_true, dtype="float64").ravel()
        treatment = np.asarray(treatment, dtype="float64").ravel()
        if not (len(score) == len(y_true) == len(treatment)):
            raise ValueError("score, y_true và treatment phải có cùng độ dài")
        if not np.isfinite(score).all():
            raise ValueError("score phải hữu hạn")
        self.propensity_ = float(
            np.mean(treatment) if propensity is None else propensity
        )
        target = transformed_outcome(
            y_true,
            treatment,
            propensity=self.propensity_,
        )
        self.model_ = IsotonicRegression(
            increasing=True,
            out_of_bounds=self.out_of_bounds,
        )
        self.model_.fit(score, target)
        return self

    def predict(self, score) -> np.ndarray:
        if not hasattr(self, "model_"):
            raise RuntimeError("Calibrator chưa được fit")
        score = np.asarray(score, dtype="float64").ravel()
        if not np.isfinite(score).all():
            raise ValueError("score phải hữu hạn")
        return np.asarray(self.model_.predict(score), dtype="float64")
