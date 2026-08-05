"""Chọn và tổ hợp CATE model bằng doubly robust loss.

Nguồn: Lan & Syrgkanis, *Causal Q-Aggregation for CATE Model Selection*,
AISTATS 2024 (PMLR v238), bản arXiv 2310.16945.

Đồng nhất thức cho squared loss với pseudo-outcome ``Γ``::

    Σ_m w_m ‖Γ − f_m‖² = ‖Γ − f_w‖² + Σ_m w_m ‖f_m − f_w‖²,  f_w = Σ_m w_m f_m

nên mục tiêu Q-aggregation, vốn là tổ hợp lồi giữa model-selection loss và
model-averaging loss với tham số ``nu``, rút gọn thành::

    Q(w) = ‖Γ − f_w‖² + nu · Σ_m w_m ‖f_m − f_w‖²
         = const − 2·wᵀb + (1 − nu)·wᵀAw + nu·wᵀd

với ``b_m = mean(Γ·f_m)``, ``A_jk = mean(f_j·f_k)``, ``d_m = mean(f_m²)``. Với
``nu ∈ [0, 1)`` hàm này lồi trên simplex nên nghiệm là duy nhất theo giá trị
mục tiêu. ``nu = 0`` cho stacking thuần; paper dùng ``nu = 1/2`` làm mặc định.

Hai ràng buộc protocol:

1. Weights chỉ được học trên prediction out-of-fold, tức trên dữ liệu mà từng
   candidate không được fit. Hàm :func:`cross_fitted_ensemble_score` còn tách
   thêm một lớp nữa để bản thân điểm ensemble cũng là out-of-sample so với
   bước học weights.
2. DR loss chỉ có nghĩa cho score có scale CATE. Score chỉ dùng để xếp hạng
   (Response, Rank-Learner) không được đưa vào Q-aggregation; với chúng chỉ có
   :func:`rank_average_score`, một heuristic không có bảo đảm lý thuyết nào ở
   đây.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.stats import rankdata


@dataclass(frozen=True)
class EnsembleWeights:
    model_names: list[str]
    weights: np.ndarray
    method: str
    objective_value: float
    nu: float | None = None

    def as_dict(self) -> dict[str, float]:
        return {
            name: float(weight)
            for name, weight in zip(self.model_names, self.weights)
        }

    def predict(self, predictions_by_model: dict[str, np.ndarray]) -> np.ndarray:
        missing = [name for name in self.model_names if name not in predictions_by_model]
        if missing:
            raise KeyError(f"Thiếu prediction cho model: {missing}")
        matrix = np.column_stack(
            [
                np.asarray(predictions_by_model[name], dtype="float64").ravel()
                for name in self.model_names
            ]
        )
        return matrix @ self.weights


def _prediction_matrix(
    predictions_by_model: dict[str, np.ndarray],
    rows: np.ndarray | None = None,
) -> tuple[list[str], np.ndarray]:
    names = list(predictions_by_model)
    if not names:
        raise ValueError("predictions_by_model không được rỗng")
    columns = []
    for name in names:
        values = np.asarray(predictions_by_model[name], dtype="float64").ravel()
        if not np.isfinite(values).all():
            raise ValueError(f"prediction của {name!r} phải hữu hạn")
        columns.append(values if rows is None else values[rows])
    matrix = np.column_stack(columns)
    if len({column.shape for column in columns}) != 1:
        raise ValueError("Mọi prediction phải có cùng độ dài")
    return names, matrix


def doubly_robust_losses(
    predictions_by_model: dict[str, np.ndarray],
    effect_signal,
) -> dict[str, float]:
    """DR loss ``mean((Γ − f_m)²)`` cho từng model; nhỏ hơn là tốt hơn."""
    signal = np.asarray(effect_signal, dtype="float64").ravel()
    names, matrix = _prediction_matrix(predictions_by_model)
    if matrix.shape[0] != len(signal):
        raise ValueError("prediction và effect_signal phải có cùng độ dài")
    losses = np.mean((signal[:, None] - matrix) ** 2, axis=0)
    return dict(zip(names, (float(value) for value in losses)))


def best_single_by_dr_risk(
    predictions_by_model: dict[str, np.ndarray],
    effect_signal,
) -> EnsembleWeights:
    """Chọn đúng một model theo DR loss; baseline đơn giản nhất của selection."""
    losses = doubly_robust_losses(predictions_by_model, effect_signal)
    names = list(losses)
    best = min(names, key=lambda name: losses[name])
    weights = np.zeros(len(names), dtype="float64")
    weights[names.index(best)] = 1.0
    return EnsembleWeights(
        model_names=names,
        weights=weights,
        method="best_single_dr_risk",
        objective_value=float(losses[best]),
    )


def softmax_dr_risk_ensemble(
    predictions_by_model: dict[str, np.ndarray],
    effect_signal,
    temperature: float | None = None,
) -> EnsembleWeights:
    """Weights ``∝ exp(−loss / temperature)``.

    Đây là baseline heuristic, không phải Q-aggregation. Nhiệt độ mặc định là
    độ lệch chuẩn của các loss, để thang nhiệt tự thích ứng với khoảng cách
    thực tế giữa các model thay vì một hằng số tùy ý.
    """
    losses = doubly_robust_losses(predictions_by_model, effect_signal)
    names = list(losses)
    values = np.array([losses[name] for name in names], dtype="float64")
    scale = (
        float(np.std(values))
        if temperature is None
        else float(temperature)
    )
    if not np.isfinite(scale) or scale <= 0:
        weights = np.full(len(names), 1.0 / len(names))
    else:
        shifted = -(values - values.min()) / scale
        exponential = np.exp(shifted)
        weights = exponential / exponential.sum()
    return EnsembleWeights(
        model_names=names,
        weights=weights,
        method="softmax_dr_risk",
        objective_value=float(values @ weights),
    )


def causal_q_aggregation(
    predictions_by_model: dict[str, np.ndarray],
    effect_signal,
    nu: float = 0.5,
) -> EnsembleWeights:
    """Q-aggregation weights trên simplex, tối ưu bằng SLSQP.

    Số model trong repo này nhỏ (dưới 10) nên SLSQP với ràng buộc
    ``Σ w = 1, w ≥ 0`` là đủ; mục tiêu lồi nên nghiệm không phụ thuộc điểm khởi
    tạo theo giá trị mục tiêu.
    """
    if not 0 <= nu < 1:
        raise ValueError("nu phải nằm trong [0, 1)")
    signal = np.asarray(effect_signal, dtype="float64").ravel()
    names, matrix = _prediction_matrix(predictions_by_model)
    if matrix.shape[0] != len(signal):
        raise ValueError("prediction và effect_signal phải có cùng độ dài")

    n_models = matrix.shape[1]
    gram = matrix.T @ matrix / len(signal)
    cross = matrix.T @ signal / len(signal)
    diagonal = np.diag(gram).copy()

    def objective(weights: np.ndarray) -> float:
        return float(
            -2.0 * weights @ cross
            + (1.0 - nu) * weights @ gram @ weights
            + nu * weights @ diagonal
        )

    def gradient(weights: np.ndarray) -> np.ndarray:
        return (
            -2.0 * cross
            + 2.0 * (1.0 - nu) * gram @ weights
            + nu * diagonal
        )

    start = np.full(n_models, 1.0 / n_models)
    result = minimize(
        objective,
        start,
        jac=gradient,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_models,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}],
        options={"maxiter": 500, "ftol": 1e-12},
    )
    weights = np.clip(result.x, 0.0, None)
    total = weights.sum()
    weights = (
        weights / total if total > 0 else np.full(n_models, 1.0 / n_models)
    )
    constant = float(np.mean(signal**2))
    return EnsembleWeights(
        model_names=names,
        weights=weights,
        method="causal_q_aggregation",
        objective_value=objective(weights) + constant,
        nu=nu,
    )


def rank_average_score(
    predictions_by_model: dict[str, np.ndarray],
    weights: dict[str, float] | None = None,
) -> np.ndarray:
    """Trung bình thứ hạng chuẩn hóa; heuristic cho score không cùng scale.

    Không có bảo đảm lý thuyết nào của Q-aggregation áp dụng ở đây. Hàm chỉ tồn
    tại để so sánh một tổ hợp có thể gộp cả ranking score như Response.
    """
    names, matrix = _prediction_matrix(predictions_by_model)
    n_rows = matrix.shape[0]
    ranks = np.column_stack(
        [rankdata(matrix[:, index], method="average") / n_rows for index in range(len(names))]
    )
    if weights is None:
        weight_vector = np.full(len(names), 1.0 / len(names))
    else:
        weight_vector = np.array(
            [float(weights.get(name, 0.0)) for name in names],
            dtype="float64",
        )
        total = weight_vector.sum()
        if total <= 0:
            raise ValueError("Tổng weights phải > 0")
        weight_vector = weight_vector / total
    return ranks @ weight_vector


ENSEMBLE_METHODS = {
    "best_single_dr_risk": best_single_by_dr_risk,
    "softmax_dr_risk": softmax_dr_risk_ensemble,
    "causal_q_aggregation": causal_q_aggregation,
}


def cross_fitted_ensemble_score(
    predictions_by_model: dict[str, np.ndarray],
    effect_signal,
    method: str = "causal_q_aggregation",
    n_splits: int = 2,
    seed: int = 42,
    **method_kwargs,
) -> dict:
    """Điểm ensemble out-of-sample so với chính bước học weights.

    Dữ liệu OOF được chia thành ``n_splits`` phần. Weights học trên phần bù rồi
    chấm phần còn lại. Nếu học weights trên toàn bộ rồi chấm lại trên chính nó,
    ước lượng sẽ lạc quan vì weights đã thấy đúng những dòng đó.
    """
    if method not in ENSEMBLE_METHODS:
        raise KeyError(
            f"method {method!r} chưa đăng ký; có {sorted(ENSEMBLE_METHODS)}"
        )
    if n_splits < 2:
        raise ValueError("n_splits phải >= 2")
    signal = np.asarray(effect_signal, dtype="float64").ravel()
    names, matrix = _prediction_matrix(predictions_by_model)
    n = len(signal)
    if matrix.shape[0] != n:
        raise ValueError("prediction và effect_signal phải có cùng độ dài")

    rng = np.random.default_rng(seed)
    assignment = rng.permutation(n) % n_splits
    score = np.full(n, np.nan, dtype="float64")
    fold_weights = []
    for fold in range(n_splits):
        holdout = assignment == fold
        train = ~holdout
        fold_predictions = {
            name: matrix[train, index] for index, name in enumerate(names)
        }
        weights = ENSEMBLE_METHODS[method](
            fold_predictions,
            signal[train],
            **method_kwargs,
        )
        fold_weights.append(weights.as_dict())
        score[holdout] = matrix[holdout] @ weights.weights
    if not np.isfinite(score).all():
        raise RuntimeError("Ensemble score còn giá trị chưa gán")

    full_weights = ENSEMBLE_METHODS[method](
        predictions_by_model,
        signal,
        **method_kwargs,
    )
    return {
        "score": score,
        "method": method,
        "fold_weights": fold_weights,
        "full_sample_weights": full_weights.as_dict(),
        "full_sample_objective": full_weights.objective_value,
        "n_splits": int(n_splits),
    }
