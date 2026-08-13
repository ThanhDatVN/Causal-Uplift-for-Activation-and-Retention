"""Generator RCT tổng hợp có ground-truth CATE, dùng cho test metric.

Criteo không cho phép quan sát ``tau(x)`` cá nhân, nên mọi metric mới phải được
kiểm tra trên dữ liệu mô phỏng mà công thức sinh dữ liệu đã biết trước. Generator
này cố ý tái tạo hai đặc điểm của Criteo: propensity hằng và lệch mạnh (0,85), và
outcome nhị phân hiếm.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SyntheticRCT:
    X: np.ndarray
    treatment: np.ndarray
    outcome: np.ndarray
    tau: np.ndarray
    mu0: np.ndarray
    mu1: np.ndarray
    propensity: float

    @property
    def pooled_outcome_mean(self) -> np.ndarray:
        """``E[Y | X]`` gộp hai arm; dùng làm ``m(X)`` oracle cho outcome adjustment."""
        return self.propensity * self.mu1 + (1.0 - self.propensity) * self.mu0

    @property
    def ate(self) -> float:
        return float(np.mean(self.tau))


def make_synthetic_rct(
    n: int = 60_000,
    propensity: float = 0.85,
    base_rate: float = 0.05,
    effect_scale: float = 0.02,
    effect_alignment: str = "orthogonal",
    seed: int = 0,
) -> SyntheticRCT:
    """Sinh một RCT nhị phân với CATE phụ thuộc feature đầu tiên.

    ``mu0`` biến thiên theo feature thứ hai để phần ``E[Y | X]`` có tín hiệu
    thật, nhờ đó test giảm variance của outcome adjustment mới có ý nghĩa.
    Mặc định ``tau`` đơn điệu tăng theo ``X[:, 0]`` nên score oracle chính là
    ``X[:, 0]`` và độc lập với prognostic direction ``X[:, 1]``. Các chế độ
    ``risk_aligned``, ``risk_anti_aligned`` và ``homogeneous`` tạo những stress
    test có cùng covariate/outcome surface nhưng quan hệ risk-effect khác nhau.
    """
    if not 0 < propensity < 1:
        raise ValueError("propensity phải nằm trong (0, 1)")
    if not 0 < base_rate < 1:
        raise ValueError("base_rate phải nằm trong (0, 1)")
    valid_alignments = {
        "orthogonal",
        "risk_aligned",
        "risk_anti_aligned",
        "homogeneous",
    }
    if effect_alignment not in valid_alignments:
        raise ValueError(
            f"effect_alignment phải nằm trong {sorted(valid_alignments)}"
        )

    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    mu0 = base_rate * np.exp(0.9 * np.tanh(X[:, 1]))
    mu0 = np.clip(mu0, 1e-6, 0.9)
    effect_direction = {
        "orthogonal": np.tanh(X[:, 0]),
        "risk_aligned": np.tanh(X[:, 1]),
        "risk_anti_aligned": -np.tanh(X[:, 1]),
        "homogeneous": np.ones(n, dtype="float64"),
    }[effect_alignment]
    requested_tau = effect_scale * effect_direction
    mu1 = np.clip(mu0 + requested_tau, 0.0, 1.0)
    # Ground truth must describe the *actual* clipped potential-outcome surface.
    # Keeping requested_tau here would silently make PEHE/ranking tests compare
    # against an impossible counterfactual whenever clipping is active.
    tau = mu1 - mu0
    treatment = (rng.random(n) < propensity).astype("float64")
    probability = np.where(treatment == 1, mu1, mu0)
    outcome = (rng.random(n) < probability).astype("float64")
    return SyntheticRCT(
        X=X,
        treatment=treatment,
        outcome=outcome,
        tau=tau,
        mu0=mu0,
        mu1=mu1,
        propensity=propensity,
    )
