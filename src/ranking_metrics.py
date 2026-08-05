"""Rank-weighted treatment effect metrics cho đánh giá prioritization rule.

Nội dung:

- ``toc_curve`` / ``rate_score`` / ``autoc_score`` theo khung TOC–RATE của
  Yadlowsky, Fleming, Shah, Brunskill & Wager, *Evaluating Treatment
  Prioritization Rules via Rank-Weighted Average Treatment Effects*,
  JASA 2025, DOI 10.1080/01621459.2024.2393466 (bản arXiv 2111.07966).
  Định nghĩa dùng ở đây: với prioritization score ``S`` và một effect signal
  ``Γ`` có ``E[Γ | X] = τ(X)``,

      TOC(q) = mean(Γ trên top-q theo S) − mean(Γ),
      RATE   = ∫₀¹ α(q) · TOC(q) dq.

  ``α(q) = 1`` cho AUTOC; ``α(q) = q`` cho biến thể có trọng số kiểu Qini.
  Paper yêu cầu score được fit trên dữ liệu tách biệt với dữ liệu chấm; module
  này không tự bảo đảm điều đó, caller phải cung cấp OOF prediction.

- Outcome adjustment để giảm variance của evaluation metric trên RCT, theo
  hướng của Bokelmann & Lessmann, EJOR 2024 (bản arXiv 2210.02152). Repo chỉ
  đọc được abstract/metadata của nguồn này, không đọc được phần công thức đầy
  đủ, nên :func:`adjusted_transformed_outcome` bên dưới là dạng
  regression-adjusted quen thuộc được **suy ra và kiểm chứng tại chỗ** bằng
  test bất biến kỳ vọng và test giảm variance, không phải bản sao công thức
  của paper. Xem ``tests/test_ranking_metrics.py``.

Mọi hàm ở đây chỉ phụ thuộc thứ hạng của score, nên bất biến với phép biến đổi
đơn điệu tăng. Tie được gộp theo thứ tự ``mergesort`` ổn định, cùng quy ước với
``src.evaluation``.
"""

from __future__ import annotations

import numpy as np


def _as_float_array(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype="float64").ravel()
    if array.size == 0:
        raise ValueError(f"{name} không được rỗng")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} phải hữu hạn")
    return array


def _check_same_length(**arrays: np.ndarray) -> int:
    lengths = {name: len(value) for name, value in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"Các mảng phải có cùng độ dài, nhận được {lengths}")
    return next(iter(lengths.values()))


def adjusted_transformed_outcome(
    y_true,
    treatment,
    outcome_prediction,
    propensity: float | None = None,
) -> np.ndarray:
    """Transformed outcome có regression adjustment: ``(Y − m(X))·(T − p)/(p(1−p))``.

    Với propensity hằng ``p`` của một RCT và bất kỳ hàm ``m(X)`` nào không phụ
    thuộc ``T`` hay ``Y``, kỳ vọng điều kiện vẫn là CATE::

        E[R_adj | X] = (μ₁(X) − m(X)) − (μ₀(X) − m(X)) = τ(X)

    tức adjustment không đổi estimand. Variance giảm khi ``m(X)`` xấp xỉ tốt
    ``E[Y | X]`` gộp hai arm, vì phần dư ``Y − m(X)`` nhỏ hơn ``Y``. Điều kiện
    bắt buộc: ``m`` phải được fit ngoài mẫu đang chấm, nếu không phần dư bị co
    lại một cách giả tạo và metric bị lệch lạc quan.

    Đặt ``outcome_prediction = 0`` sẽ thu về đúng
    :func:`src.evaluation.transformed_outcome`.
    """
    y = _as_float_array(y_true, "y_true")
    t = _as_float_array(treatment, "treatment")
    m = _as_float_array(outcome_prediction, "outcome_prediction")
    _check_same_length(y_true=y, treatment=t, outcome_prediction=m)
    p = float(np.mean(t) if propensity is None else propensity)
    if not 0 < p < 1:
        raise ValueError(f"propensity phải nằm trong (0, 1), nhận được {p}")
    return (y - m) * (t - p) / (p * (1.0 - p))


def _tie_group_boundaries(sorted_score: np.ndarray) -> np.ndarray:
    """Chỉ số cuối của mỗi nhóm score bằng nhau trong mảng đã sort."""
    distinct = np.flatnonzero(np.diff(sorted_score))
    return np.r_[distinct, sorted_score.size - 1]


def _sorted_weighted_cumulants(
    effect_signal: np.ndarray,
    score: np.ndarray,
    sample_weight: np.ndarray | None,
    order: np.ndarray | None = None,
):
    """Cumulative weighted count/sum tại biên của từng nhóm score bằng nhau.

    Các quan sát có cùng score phải được gộp thành một điểm cắt: một
    prioritization rule không phân biệt được chúng, nên không được phép hưởng
    lợi từ thứ tự ngẫu nhiên bên trong nhóm. Không gộp thì score hằng số sẽ cho
    RATE khác 0. Quy ước này khớp ``_qini_curve_raw`` trong ``src.evaluation``.
    """
    if order is None:
        order = np.argsort(score, kind="mergesort")[::-1]
    signal = effect_signal[order]
    sorted_score = score[order]
    weight = (
        np.ones(len(signal), dtype="float64")
        if sample_weight is None
        else sample_weight[order]
    )
    boundaries = _tie_group_boundaries(sorted_score)
    cumulative_count = np.cumsum(weight)[boundaries]
    cumulative_sum = np.cumsum(weight * signal)[boundaries]
    group_weight = np.diff(np.r_[0.0, cumulative_count])
    return group_weight, cumulative_count, cumulative_sum


def toc_curve(
    effect_signal,
    score,
    sample_weight=None,
    q_grid=None,
) -> dict[str, np.ndarray]:
    """Targeting Operator Characteristic: TOC(q) = mean(Γ | top-q) − mean(Γ).

    Trả về ``q`` (tỷ lệ population được ưu tiên) và ``toc``. Khi ``q_grid`` là
    ``None``, curve được tính tại mọi điểm cắt của dữ liệu; ngược lại giá trị
    được nội suy tuyến tính về lưới yêu cầu.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    ranking = _as_float_array(score, "score")
    _check_same_length(effect_signal=signal, score=ranking)
    weight = (
        None
        if sample_weight is None
        else _as_float_array(sample_weight, "sample_weight")
    )
    if weight is not None:
        _check_same_length(effect_signal=signal, sample_weight=weight)

    _, cumulative_count, cumulative_sum = _sorted_weighted_cumulants(
        signal,
        ranking,
        weight,
    )
    total_count = cumulative_count[-1]
    if total_count <= 0:
        raise ValueError("Tổng sample_weight phải > 0")
    overall_mean = cumulative_sum[-1] / total_count

    positive = cumulative_count > 0
    q = cumulative_count[positive] / total_count
    top_mean = cumulative_sum[positive] / cumulative_count[positive]
    toc = top_mean - overall_mean

    if q_grid is None:
        return {"q": q, "toc": toc}
    grid = _as_float_array(q_grid, "q_grid")
    if np.any((grid < 0) | (grid > 1)):
        raise ValueError("q_grid phải nằm trong [0, 1]")
    return {"q": grid, "toc": np.interp(grid, q, toc, left=toc[0], right=toc[-1])}


def _rate_from_cumulants(
    weight: np.ndarray,
    cumulative_count: np.ndarray,
    cumulative_sum: np.ndarray,
    weighting: str,
) -> float:
    total_count = cumulative_count[-1]
    overall_mean = cumulative_sum[-1] / total_count
    positive = cumulative_count > 0
    count = cumulative_count[positive]
    q = count / total_count
    toc = cumulative_sum[positive] / count - overall_mean
    dq = weight[positive] / total_count
    if weighting == "autoc":
        alpha = np.ones_like(q)
    elif weighting == "qini":
        alpha = q
    else:
        raise ValueError(
            f"weighting phải là 'autoc' hoặc 'qini', nhận được {weighting!r}"
        )
    return float(np.sum(alpha * toc * dq))


def rate_score(
    effect_signal,
    score,
    weighting: str = "autoc",
    sample_weight=None,
) -> float:
    """RATE = ∫ α(q)·TOC(q) dq, xấp xỉ bằng tổng Riemann trên các điểm cắt dữ liệu.

    ``weighting='autoc'`` cho α(q)=1 và ``weighting='qini'`` cho α(q)=q. Score
    hằng số cho RATE bằng 0 vì mọi TOC(q) đều bằng 0 khi chỉ có một nhóm.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    ranking = _as_float_array(score, "score")
    _check_same_length(effect_signal=signal, score=ranking)
    weight = (
        None
        if sample_weight is None
        else _as_float_array(sample_weight, "sample_weight")
    )
    if weight is not None:
        _check_same_length(effect_signal=signal, sample_weight=weight)
    sorted_weight, cumulative_count, cumulative_sum = _sorted_weighted_cumulants(
        signal,
        ranking,
        weight,
    )
    if cumulative_count[-1] <= 0:
        raise ValueError("Tổng sample_weight phải > 0")
    return _rate_from_cumulants(
        sorted_weight,
        cumulative_count,
        cumulative_sum,
        weighting,
    )


def autoc_score(effect_signal, score, sample_weight=None) -> float:
    """Area under the TOC curve; bằng ``rate_score(..., weighting='autoc')``."""
    return rate_score(
        effect_signal,
        score,
        weighting="autoc",
        sample_weight=sample_weight,
    )


def paired_rate_bootstrap(
    scores_by_model: dict[str, np.ndarray],
    effect_signal,
    n_boot: int = 500,
    seed: int = 42,
    alpha: float = 0.05,
    weighting: str = "autoc",
) -> dict:
    """Paired nonparametric bootstrap cho RATE của nhiều model trên cùng resample.

    Mọi model dùng chung một bộ multiplicity weight trong mỗi iteration nên
    chênh lệch giữ đúng pairing. Thứ tự sort của từng model được tính một lần
    và tái sử dụng, giống cách ``src.evaluation`` xử lý Qini bootstrap.
    """
    if not scores_by_model:
        raise ValueError("scores_by_model không được rỗng")
    if n_boot < 2:
        raise ValueError("n_boot phải >= 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")

    signal = _as_float_array(effect_signal, "effect_signal")
    names = list(scores_by_model)
    scores = {
        name: _as_float_array(value, f"scores_by_model[{name!r}]")
        for name, value in scores_by_model.items()
    }
    n = len(signal)
    for name, value in scores.items():
        if len(value) != n:
            raise ValueError(
                f"scores_by_model[{name!r}] có độ dài {len(value)}, cần {n}"
            )

    orders = {
        name: np.argsort(value, kind="mergesort")[::-1]
        for name, value in scores.items()
    }
    observed = np.array(
        [
            rate_score(signal, scores[name], weighting=weighting)
            for name in names
        ],
        dtype="float64",
    )
    draws = np.empty((n_boot, len(names)), dtype="float64")
    rng = np.random.default_rng(seed)
    for bootstrap_index in range(n_boot):
        idx = rng.integers(0, n, size=n)
        weight = np.bincount(idx, minlength=n).astype("float64", copy=False)
        for model_index, name in enumerate(names):
            group_weight, cumulative_count, cumulative_sum = (
                _sorted_weighted_cumulants(
                    signal,
                    scores[name],
                    weight,
                    order=orders[name],
                )
            )
            draws[bootstrap_index, model_index] = _rate_from_cumulants(
                group_weight,
                cumulative_count,
                cumulative_sum,
                weighting,
            )
    return {
        "model_names": names,
        "weighting": weighting,
        "observed": observed,
        "draws": draws,
        "ci_low": np.quantile(draws, alpha / 2, axis=0),
        "ci_high": np.quantile(draws, 1 - alpha / 2, axis=0),
        "n_boot": int(n_boot),
    }


def paired_difference_summary(
    bootstrap_result: dict,
    model_a: str,
    model_b: str,
    alpha: float = 0.05,
) -> dict:
    """Tóm tắt chênh lệch paired ``A − B`` từ output của bootstrap ở trên."""
    names = bootstrap_result["model_names"]
    if model_a not in names or model_b not in names:
        raise ValueError(
            f"model_a/model_b phải nằm trong {names}, nhận được "
            f"{model_a!r} và {model_b!r}"
        )
    index_a = names.index(model_a)
    index_b = names.index(model_b)
    differences = (
        bootstrap_result["draws"][:, index_a]
        - bootstrap_result["draws"][:, index_b]
    )
    return {
        "model_a": model_a,
        "model_b": model_b,
        "observed_difference": float(
            bootstrap_result["observed"][index_a]
            - bootstrap_result["observed"][index_b]
        ),
        "ci_low": float(np.quantile(differences, alpha / 2)),
        "ci_high": float(np.quantile(differences, 1 - alpha / 2)),
        "probability_difference_positive": float(np.mean(differences > 0)),
        "n_boot": int(bootstrap_result["n_boot"]),
    }
