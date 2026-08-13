"""Rank-Learner: pairwise Neyman-orthogonal ranking cho treatment effect.

Nguồn phương pháp: *Rank-Learner: Orthogonal Ranking of Treatment Effects*,
ICML 2026, arXiv 2602.03517. Các thành phần được lấy từ bản HTML v2 của paper:

- doubly robust score
  ``φ(W) = T/e·(Y − μ₁) − (1−T)/(1−e)·(Y − μ₀) + μ₁ − μ₀``;
- soft target ``t_τ(X, X′) = σ((τ(X) − τ(X′)) / κ)`` với κ > 0;
- trọng số ``ω_τ(X, X′) = (1/κ)·t_τ·(1 − t_τ)``;
- hiệu chỉnh ``Δ_η(W, W′) = [φ(W) − τ(X)] − [φ(W′) − τ(X′)]``;
- pseudo-label ``t̃ = t_τ + ω_τ·Δ_η``;
- mục tiêu ``L = E[ℓ(p_g(X, X′), t̃)]`` với ``p_g(X, X′) = σ(g(X) − g(X′))``.

Hai lựa chọn hiện thực khác paper được ghi rõ:

1. Paper dùng feed-forward neural network/Adam; repo dùng LightGBM custom
   objective. Objective vẫn là binary cross-entropy như Equation 17/58.
2. Paper dùng "một tập con ngẫu nhiên các cặp rút đều ở mỗi epoch". Ở đây tập
   con đó là một **ghép cặp hoàn hảo ngẫu nhiên**: mỗi vòng boosting xáo trộn
   toàn bộ chỉ số rồi ghép các vị trí liền kề. Cách này giữ đúng tính "rút đều"
   theo từng cặp, cho mỗi dòng đúng một gradient khác 0 mỗi vòng, và có chi phí
   ``O(n)``.

Model nền là LightGBM với custom objective; paper mô tả phương pháp là
model-agnostic. Nuisance được cross-fit bên trong ``fit`` nên caller chỉ cần
truyền ``(X, T, Y)``.
"""

from __future__ import annotations

import numpy as np
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.model_selection import StratifiedKFold


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * values))


DEFAULT_NUISANCE_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 1000,
    "reg_lambda": 5.0,
    "colsample_bytree": 0.9,
    "verbose": -1,
}

DEFAULT_RANK_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 1000,
    "reg_lambda": 5.0,
    "colsample_bytree": 0.9,
    "verbose": -1,
}


def cross_fitted_dr_score(
    X: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    propensity: float,
    n_folds: int = 3,
    seed: int = 42,
    nuisance_params: dict | None = None,
) -> dict[str, np.ndarray]:
    """Cross-fit ``μ₀``, ``μ₁`` rồi trả DR score và plug-in ``τ`` out-of-fold.

    Propensity là hằng số của thiết kế randomized; không fit ``e(X)`` từ ``X``.
    """
    if not 0 < propensity < 1:
        raise ValueError("propensity phải nằm trong (0, 1)")
    params = {**DEFAULT_NUISANCE_PARAMS, **(nuisance_params or {})}
    n = len(outcome)
    mu0 = np.zeros(n, dtype="float64")
    mu1 = np.zeros(n, dtype="float64")
    strata = treatment.astype("int64") * 2 + outcome.astype("int64")
    splitter = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for fold_index, (train_idx, test_idx) in enumerate(
        splitter.split(np.zeros(n, dtype="int8"), strata)
    ):
        for arm, target in ((0, mu0), (1, mu1)):
            arm_rows = train_idx[treatment[train_idx] == arm]
            model = LGBMClassifier(**params, random_state=seed + fold_index)
            model.fit(X[arm_rows], outcome[arm_rows])
            target[test_idx] = model.predict_proba(X[test_idx])[:, 1]
    t = treatment.astype("float64")
    y = outcome.astype("float64")
    dr_score = (
        mu1
        - mu0
        + t * (y - mu1) / propensity
        - (1.0 - t) * (y - mu0) / (1.0 - propensity)
    )
    return {"dr_score": dr_score, "plugin_tau": mu1 - mu0, "mu0": mu0, "mu1": mu1}


class RankLearner:
    """Ranking score được học bằng pairwise orthogonal loss.

    ``predict`` trả điểm ưu tiên, **không** phải CATE có scale. Vì vậy metric
    calibration như EUCE và DR risk không áp dụng cho model này, giống Response.
    """

    def __init__(
        self,
        kappa_scale: float = 1.0,
        n_folds: int = 3,
        seed: int = 42,
        rank_params: dict | None = None,
        nuisance_params: dict | None = None,
        hessian_floor: float = 1e-6,
        label_clip_epsilon: float = 1e-6,
    ):
        self.kappa_scale = float(kappa_scale)
        self.n_folds = int(n_folds)
        self.seed = int(seed)
        self.rank_params = rank_params
        self.nuisance_params = nuisance_params
        self.hessian_floor = float(hessian_floor)
        self.label_clip_epsilon = float(label_clip_epsilon)
        if self.kappa_scale <= 0:
            raise ValueError("kappa_scale phải > 0")
        if self.n_folds < 2:
            raise ValueError("n_folds phải >= 2")
        if self.hessian_floor <= 0:
            raise ValueError("hessian_floor phải > 0")
        if not 0 < self.label_clip_epsilon < 0.5:
            raise ValueError("label_clip_epsilon phải nằm trong (0, 0.5)")

    def _pairwise_objective(self, _y_true, y_pred):
        """Gradient/Hessian của binary cross-entropy pairwise trong paper."""
        n = len(y_pred)
        order = self._rng.permutation(n)
        n_pairs = n // 2
        left = order[:n_pairs]
        right = order[n_pairs : 2 * n_pairs]

        difference = y_pred[left] - y_pred[right]
        probability = _sigmoid(difference)
        derivative = probability * (1.0 - probability)

        soft_target = _sigmoid((self._tau[left] - self._tau[right]) / self._kappa)
        weight = soft_target * (1.0 - soft_target) / self._kappa
        correction = (self._residual[left]) - (self._residual[right])
        pseudo_label = soft_target + weight * correction
        pseudo_label = np.clip(
            pseudo_label,
            self.label_clip_epsilon,
            1.0 - self.label_clip_epsilon,
        )

        residual = probability - pseudo_label
        # LightGBM kỳ vọng gradient/hessian theo từng observation và tự cộng
        # chúng khi tính split gain. Chuẩn hóa theo số pair ở đây sẽ làm
        # ``reg_lambda`` lấn át toàn bộ tín hiệu trên sample lớn.
        pair_gradient = residual
        pair_hessian = derivative

        gradient = np.zeros(n, dtype="float64")
        hessian = np.full(n, self.hessian_floor, dtype="float64")
        np.add.at(gradient, left, pair_gradient)
        np.add.at(gradient, right, -pair_gradient)
        np.add.at(hessian, left, pair_hessian)
        np.add.at(hessian, right, pair_hessian)
        return gradient, hessian

    def fit(
        self,
        X: np.ndarray,
        treatment: np.ndarray,
        outcome: np.ndarray,
        propensity: float,
    ) -> "RankLearner":
        X = np.asarray(X)
        treatment = np.asarray(treatment).ravel()
        outcome = np.asarray(outcome).ravel()
        if not (len(X) == len(treatment) == len(outcome)):
            raise ValueError("X, treatment và outcome phải có cùng độ dài")

        nuisance = cross_fitted_dr_score(
            X,
            treatment,
            outcome,
            propensity=propensity,
            n_folds=self.n_folds,
            seed=self.seed,
            nuisance_params=self.nuisance_params,
        )
        self._tau = nuisance["plugin_tau"]
        self._residual = nuisance["dr_score"] - self._tau
        tau_scale = float(np.std(self._tau))
        if not np.isfinite(tau_scale) or tau_scale <= 0:
            raise ValueError(
                "plug-in tau gần hằng số nên không xác định được kappa; "
                "nuisance model không học được heterogeneity trên sample này"
            )
        self._kappa = self.kappa_scale * tau_scale
        self._rng = np.random.default_rng(self.seed)

        params = {**DEFAULT_RANK_PARAMS, **(self.rank_params or {})}
        self.model_ = LGBMRegressor(
            objective=self._pairwise_objective,
            random_state=self.seed,
            **params,
        )
        # ``y`` không tham gia loss; truyền plug-in tau để LightGBM có nhãn hợp lệ
        # và để init_score mặc định nằm gần thang của score.
        self.model_.fit(X, self._tau, init_score=np.zeros(len(X)))
        self.kappa_ = self._kappa
        self.tau_scale_ = tau_scale
        del self._tau, self._residual
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not hasattr(self, "model_"):
            raise RuntimeError("RankLearner chưa được fit")
        return np.asarray(self.model_.predict(X), dtype="float64").ravel()

    # Giữ cùng tên phương thức với các meta-learner của EconML để runner gọi chung.
    def effect(self, X: np.ndarray) -> np.ndarray:
        return self.predict(X)
