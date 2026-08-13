"""Offline policy value theo ngân sách, dùng làm primary selection metric Sprint 3.

Khung giá trị/regret theo Athey & Wager, Econometrica 2021
(DOI 10.3982/ECTA15732) và doubly robust policy evaluation theo Dudík, Langford
& Li, ICML 2011. Effect signal đưa vào đây phải có ``E[Γ | X] = τ(X)``; trong
repo, tín hiệu đó là :func:`src.policy.doubly_robust_effect_signal` hoặc
:func:`src.policy.ipw_effect_signal`.

Định nghĩa dùng thống nhất trong Sprint 3::

    G(b) = E[ 1{S(X) nằm trong top-b} · Γ ]

tức conversion tăng thêm trung bình **trên toàn population**, không phải trên
riêng nhóm được target. Chọn dạng này để giá trị tại các budget khác nhau cộng
gộp và so sánh được trực tiếp, và để treat-none có giá trị đúng bằng 0.

``policy_area`` là trung bình của ``G(b)`` trên dải budget đã đăng ký, tính bằng
trapezoid rồi chia cho độ rộng dải. Đơn vị vẫn là incremental conversion trên mỗi
khách hàng, không phải tiền.
"""

from __future__ import annotations

import numpy as np


DEFAULT_BUDGET_GRID = (0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)

# ``np.trapezoid`` chỉ có từ NumPy 2.0; requirements cho phép 1.26 nên giữ fallback.
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


def _as_float_array(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype="float64").ravel()
    if array.size == 0:
        raise ValueError(f"{name} không được rỗng")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} phải hữu hạn")
    return array


def _validate_budgets(budgets) -> np.ndarray:
    grid = np.asarray(budgets, dtype="float64").ravel()
    if grid.size == 0:
        raise ValueError("budgets không được rỗng")
    if np.any((grid < 0) | (grid > 1)):
        raise ValueError("Mọi budget phải nằm trong [0, 1]")
    if np.any(np.diff(grid) <= 0):
        raise ValueError("budgets phải tăng nghiêm ngặt")
    return grid


def _cumulative_value_curve(
    effect_signal: np.ndarray,
    score: np.ndarray,
    order: np.ndarray,
    sample_weight: np.ndarray | None,
):
    """Trả về ``(q, G)`` với ``G(q)`` là giá trị gross trên mỗi khách hàng.

    Điểm cắt chỉ được đặt tại biên của các nhóm score bằng nhau. Bên trong một
    nhóm tie, nội suy tuyến tính tương đương kỳ vọng khi chọn ngẫu nhiên một
    phần của nhóm — cách xử lý duy nhất không phụ thuộc thứ tự tuỳ ý của tie.
    """
    signal = effect_signal[order]
    sorted_score = score[order]
    weight = (
        np.ones(len(signal), dtype="float64")
        if sample_weight is None
        else sample_weight[order]
    )
    distinct = np.flatnonzero(np.diff(sorted_score))
    boundaries = np.r_[distinct, sorted_score.size - 1]
    cumulative_count = np.cumsum(weight)[boundaries]
    total = cumulative_count[-1]
    if total <= 0:
        raise ValueError("Tổng sample_weight phải > 0")
    cumulative_value = np.cumsum(weight * signal)[boundaries] / total
    q = cumulative_count / total
    return np.r_[0.0, q], np.r_[0.0, cumulative_value]


def dr_policy_value_curve(
    effect_signal,
    score,
    budgets=DEFAULT_BUDGET_GRID,
    sample_weight=None,
) -> dict[str, np.ndarray]:
    """Gross policy value trên mỗi khách hàng tại từng budget.

    Điểm nằm giữa hai ngưỡng score được nội suy tuyến tính, tương đương coi
    nhóm ở biên ngân sách được target theo tỷ lệ. Với dữ liệu lớn và score liên
    tục, sai khác so với cắt cứng là bậc ``1/n``.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    ranking = _as_float_array(score, "score")
    if len(signal) != len(ranking):
        raise ValueError("effect_signal và score phải có cùng độ dài")
    weight = (
        None
        if sample_weight is None
        else _as_float_array(sample_weight, "sample_weight")
    )
    if weight is not None and len(weight) != len(signal):
        raise ValueError("sample_weight phải có cùng độ dài với effect_signal")
    if weight is not None and np.any(weight < 0):
        raise ValueError("sample_weight không được âm")
    grid = _validate_budgets(budgets)
    order = np.argsort(ranking, kind="mergesort")[::-1]
    q, cumulative_value = _cumulative_value_curve(signal, ranking, order, weight)
    return {
        "budget_fraction": grid,
        "gross_value_per_customer": np.interp(grid, q, cumulative_value),
    }


def policy_area(budgets, values) -> float:
    """Trung bình trapezoid của ``G(b)`` trên dải budget, chia cho độ rộng dải.

    Một điểm budget duy nhất trả về đúng giá trị tại điểm đó.
    """
    grid = _validate_budgets(budgets)
    curve = _as_float_array(values, "values")
    if len(curve) != len(grid):
        raise ValueError("budgets và values phải có cùng độ dài")
    if len(grid) == 1:
        return float(curve[0])
    span = float(grid[-1] - grid[0])
    if span <= 0:
        raise ValueError("Dải budget phải có độ rộng > 0")
    return float(_trapezoid(curve, grid) / span)


def policy_area_from_scores(
    effect_signal,
    score,
    budgets=DEFAULT_BUDGET_GRID,
    sample_weight=None,
) -> float:
    """Primary selection metric ``policy_area_dr`` cho một score."""
    curve = dr_policy_value_curve(
        effect_signal,
        score,
        budgets=budgets,
        sample_weight=sample_weight,
    )
    return policy_area(
        curve["budget_fraction"],
        curve["gross_value_per_customer"],
    )


def expected_random_policy_value(effect_signal, budgets=DEFAULT_BUDGET_GRID) -> dict:
    """Giá trị kỳ vọng của stochastic policy ``π(x) = b`` (target ngẫu nhiên độc lập X).

    Kỳ vọng bằng ``b · mean(Γ)`` với mọi b, nên comparator này không phụ thuộc
    một ranking ngẫu nhiên cụ thể. Đây là comparator "random" chính; random
    top-k một seed chỉ là một hiện thực hóa của nó.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    grid = _validate_budgets(budgets)
    mean_effect = float(np.mean(signal))
    return {
        "budget_fraction": grid,
        "gross_value_per_customer": grid * mean_effect,
        "mean_effect_signal": mean_effect,
    }


def random_topk_sensitivity(
    effect_signal,
    budgets=DEFAULT_BUDGET_GRID,
    n_seeds: int = 20,
    seed: int = 42,
) -> dict:
    """Phân bố giá trị policy qua nhiều random ranking khác nhau.

    Dùng để cho thấy biến thiên của comparator random, không dùng để chọn ra
    lần random tốt nhất.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    grid = _validate_budgets(budgets)
    if n_seeds < 1:
        raise ValueError("n_seeds phải >= 1")
    rng = np.random.default_rng(seed)
    values = np.empty((n_seeds, len(grid)), dtype="float64")
    areas = np.empty(n_seeds, dtype="float64")
    for index in range(n_seeds):
        random_score = rng.random(len(signal))
        curve = dr_policy_value_curve(signal, random_score, budgets=grid)
        values[index] = curve["gross_value_per_customer"]
        areas[index] = policy_area(grid, values[index])
    return {
        "budget_fraction": grid,
        "value_draws": values,
        "value_mean": values.mean(axis=0),
        "value_min": values.min(axis=0),
        "value_max": values.max(axis=0),
        "policy_area_draws": areas,
        "policy_area_mean": float(areas.mean()),
        "policy_area_std": float(areas.std(ddof=1)) if n_seeds > 1 else 0.0,
        "n_seeds": int(n_seeds),
    }


def paired_policy_area_bootstrap(
    scores_by_model: dict[str, np.ndarray],
    effect_signal,
    budgets=DEFAULT_BUDGET_GRID,
    n_boot: int = 500,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """Paired bootstrap cho ``policy_area`` và cho toàn bộ budget curve.

    Mỗi iteration dùng chung một bộ multiplicity weight cho mọi model. Thứ tự
    sort của từng model được tính một lần bên ngoài vòng lặp.
    """
    if not scores_by_model:
        raise ValueError("scores_by_model không được rỗng")
    if n_boot < 2:
        raise ValueError("n_boot phải >= 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")

    signal = _as_float_array(effect_signal, "effect_signal")
    grid = _validate_budgets(budgets)
    names = list(scores_by_model)
    n = len(signal)
    orders = {}
    ranked = {}
    for name, value in scores_by_model.items():
        array = _as_float_array(value, f"scores_by_model[{name!r}]")
        if len(array) != n:
            raise ValueError(
                f"scores_by_model[{name!r}] có độ dài {len(array)}, cần {n}"
            )
        ranked[name] = array
        orders[name] = np.argsort(array, kind="mergesort")[::-1]

    observed_curve = np.empty((len(names), len(grid)), dtype="float64")
    for model_index, name in enumerate(names):
        q, cumulative_value = _cumulative_value_curve(
            signal,
            ranked[name],
            orders[name],
            None,
        )
        observed_curve[model_index] = np.interp(grid, q, cumulative_value)
    observed_area = np.array(
        [policy_area(grid, curve) for curve in observed_curve],
        dtype="float64",
    )

    area_draws = np.empty((n_boot, len(names)), dtype="float64")
    curve_draws = np.empty((n_boot, len(names), len(grid)), dtype="float64")
    rng = np.random.default_rng(seed)
    for bootstrap_index in range(n_boot):
        idx = rng.integers(0, n, size=n)
        weight = np.bincount(idx, minlength=n).astype("float64", copy=False)
        for model_index, name in enumerate(names):
            q, cumulative_value = _cumulative_value_curve(
                signal,
                ranked[name],
                orders[name],
                weight,
            )
            curve = np.interp(grid, q, cumulative_value)
            curve_draws[bootstrap_index, model_index] = curve
            area_draws[bootstrap_index, model_index] = policy_area(grid, curve)

    return {
        "model_names": names,
        "budget_fraction": grid,
        "observed_policy_area": observed_area,
        "observed_curve": observed_curve,
        "policy_area_draws": area_draws,
        "curve_draws": curve_draws,
        "policy_area_ci_low": np.quantile(area_draws, alpha / 2, axis=0),
        "policy_area_ci_high": np.quantile(area_draws, 1 - alpha / 2, axis=0),
        "curve_ci_low": np.quantile(curve_draws, alpha / 2, axis=0),
        "curve_ci_high": np.quantile(curve_draws, 1 - alpha / 2, axis=0),
        "n_boot": int(n_boot),
    }


def policy_area_difference_summary(
    bootstrap_result: dict,
    model_a: str,
    model_b: str,
    alpha: float = 0.05,
) -> dict:
    """CI của chênh lệch paired ``policy_area(A) − policy_area(B)``."""
    names = bootstrap_result["model_names"]
    if model_a not in names or model_b not in names:
        raise ValueError(
            f"model_a/model_b phải nằm trong {names}, nhận được "
            f"{model_a!r} và {model_b!r}"
        )
    index_a = names.index(model_a)
    index_b = names.index(model_b)
    differences = (
        bootstrap_result["policy_area_draws"][:, index_a]
        - bootstrap_result["policy_area_draws"][:, index_b]
    )
    return {
        "model_a": model_a,
        "model_b": model_b,
        "metric": "policy_area_dr",
        "observed_difference": float(
            bootstrap_result["observed_policy_area"][index_a]
            - bootstrap_result["observed_policy_area"][index_b]
        ),
        "ci_low": float(np.quantile(differences, alpha / 2)),
        "ci_high": float(np.quantile(differences, 1 - alpha / 2)),
        "probability_difference_positive": float(np.mean(differences > 0)),
        "n_boot": int(bootstrap_result["n_boot"]),
    }


def paired_policy_difference_band(
    bootstrap_result: dict,
    reference: str,
    candidates: list[str] | tuple[str, ...] | None = None,
    alpha: float = 0.05,
) -> dict:
    """Simultaneous paired bootstrap band over candidate-by-budget differences.

    The input must come from :func:`paired_policy_area_bootstrap`, so every model
    and every budget shares the same resampled rows.  We first construct paired
    differences against ``reference`` and then use one maximum standardized
    bootstrap-deviation critical value for the full registered family.  This is
    deliberately stricter than reading separate percentile intervals after choosing
    an attractive model or budget.

    Scores are treated as fixed out-of-fold prioritization rules.  Consequently the
    band quantifies evaluation-sample uncertainty; it does not include uncertainty
    from refitting a learner on a new training sample.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")

    names = list(bootstrap_result.get("model_names", []))
    if reference not in names:
        raise ValueError(f"reference {reference!r} phải nằm trong model_names")
    selected = (
        [name for name in names if name != reference]
        if candidates is None
        else list(candidates)
    )
    if not selected:
        raise ValueError("candidates phải chứa ít nhất một model khác reference")
    if len(set(selected)) != len(selected):
        raise ValueError("candidates không được lặp")
    unknown = [name for name in selected if name not in names]
    if unknown:
        raise ValueError(f"Candidate không có trong model_names: {unknown}")
    if reference in selected:
        raise ValueError("reference không được xuất hiện trong candidates")

    observed_curve = np.asarray(
        bootstrap_result.get("observed_curve"),
        dtype="float64",
    )
    curve_draws = np.asarray(
        bootstrap_result.get("curve_draws"),
        dtype="float64",
    )
    budgets = _validate_budgets(bootstrap_result.get("budget_fraction"))
    expected_observed_shape = (len(names), len(budgets))
    if observed_curve.shape != expected_observed_shape:
        raise ValueError(
            "observed_curve phải có shape "
            f"{expected_observed_shape}, nhận được {observed_curve.shape}"
        )
    if (
        curve_draws.ndim != 3
        or curve_draws.shape[1:] != expected_observed_shape
        or curve_draws.shape[0] < 2
    ):
        raise ValueError(
            "curve_draws phải có shape (n_boot, n_models, n_budgets) với n_boot >= 2"
        )
    if not np.isfinite(observed_curve).all() or not np.isfinite(curve_draws).all():
        raise ValueError("observed_curve và curve_draws phải hữu hạn")

    reference_index = names.index(reference)
    candidate_indices = np.asarray(
        [names.index(name) for name in selected],
        dtype="int64",
    )
    observed_difference = (
        observed_curve[candidate_indices] - observed_curve[reference_index]
    )
    difference_draws = (
        curve_draws[:, candidate_indices, :]
        - curve_draws[:, reference_index : reference_index + 1, :]
    )
    standard_error = difference_draws.std(axis=0, ddof=1)
    centered = difference_draws - observed_difference[None, :, :]
    standardized = np.zeros_like(centered)
    positive_se = standard_error > 0
    standardized[:, positive_se] = (
        np.abs(centered[:, positive_se]) / standard_error[positive_se]
    )
    max_deviation = standardized.reshape(len(standardized), -1).max(axis=1)
    critical_value = float(np.quantile(max_deviation, 1 - alpha))
    margin = critical_value * standard_error

    return {
        "reference": reference,
        "candidate_names": selected,
        "budget_fraction": budgets,
        "observed_difference": observed_difference,
        "difference_draws": difference_draws,
        "standard_error": standard_error,
        "pointwise_ci_low": np.quantile(difference_draws, alpha / 2, axis=0),
        "pointwise_ci_high": np.quantile(
            difference_draws,
            1 - alpha / 2,
            axis=0,
        ),
        "simultaneous_ci_low": observed_difference - margin,
        "simultaneous_ci_high": observed_difference + margin,
        "critical_value": critical_value,
        "max_abs_studentized_deviation": max_deviation,
        "family_size": int(observed_difference.size),
        "simultaneous_coverage_fraction": float(
            np.mean(max_deviation <= critical_value)
        ),
        "alpha": float(alpha),
        "n_boot": int(curve_draws.shape[0]),
        "scope": "conditional_on_fixed_oof_scores",
        "method": "paired_max_standardized_bootstrap_deviation",
    }


def _hard_top_indices(score, budget: float) -> np.ndarray:
    ranking = _as_float_array(score, "score")
    n_target = int(np.floor(len(ranking) * float(budget)))
    if n_target == 0:
        return np.empty(0, dtype="int64")
    order = np.argsort(-ranking, kind="mergesort")
    return order[:n_target]


def top_tail_event_support(outcome, treatment, score, budgets) -> list[dict]:
    """Count arm-specific rows and positive events under exact hard top-k cuts.

    This diagnostic uses the same ``floor(n * budget)`` convention as
    :func:`src.policy.top_budget_policy`.  ``boundary_tie_size`` makes an otherwise
    hidden source of arbitrary membership instability visible.
    """
    y = np.asarray(outcome).ravel()
    t = np.asarray(treatment).ravel()
    ranking = _as_float_array(score, "score")
    if not (len(y) == len(t) == len(ranking)):
        raise ValueError("outcome, treatment và score phải có cùng độ dài")
    if not set(np.unique(y)).issubset({0, 1}):
        raise ValueError("outcome phải là nhị phân")
    if not set(np.unique(t)).issubset({0, 1}):
        raise ValueError("treatment phải là nhị phân")

    rows = []
    for budget in _validate_budgets(budgets):
        selected = _hard_top_indices(ranking, float(budget))
        selected_t = t[selected]
        selected_y = y[selected]
        treated = selected_t == 1
        control = ~treated
        boundary_tie_size = (
            int(np.sum(ranking == ranking[selected[-1]])) if len(selected) else 0
        )
        rows.append(
            {
                "budget_fraction": float(budget),
                "target_count": int(len(selected)),
                "treated_count": int(treated.sum()),
                "control_count": int(control.sum()),
                "treated_events": int(np.sum(selected_y[treated] == 1)),
                "control_events": int(np.sum(selected_y[control] == 1)),
                "total_events": int(np.sum(selected_y == 1)),
                "boundary_tie_size": boundary_tie_size,
            }
        )
    return rows


def top_tail_overlap(score_a, score_b, budgets) -> list[dict]:
    """Membership overlap between two rankings at registered hard budgets."""
    first = _as_float_array(score_a, "score_a")
    second = _as_float_array(score_b, "score_b")
    if len(first) != len(second):
        raise ValueError("score_a và score_b phải có cùng độ dài")

    rows = []
    for budget in _validate_budgets(budgets):
        index_a = _hard_top_indices(first, float(budget))
        index_b = _hard_top_indices(second, float(budget))
        membership_a = np.zeros(len(first), dtype=bool)
        membership_b = np.zeros(len(first), dtype=bool)
        membership_a[index_a] = True
        membership_b[index_b] = True
        intersection = int(np.sum(membership_a & membership_b))
        union = int(np.sum(membership_a | membership_b))
        target_count = int(len(index_a))
        rows.append(
            {
                "budget_fraction": float(budget),
                "target_count": target_count,
                "intersection_count": intersection,
                "union_count": union,
                "overlap_fraction": (
                    float(intersection / target_count) if target_count else 1.0
                ),
                "jaccard": float(intersection / union) if union else 1.0,
            }
        )
    return rows


def doubly_robust_risk(
    effect_signal,
    cate_prediction,
    sample_weight=None,
) -> float:
    """DR risk ``E[(Γ − τ̂(X))²]`` dùng cho selection/ensemble.

    Đây là loss được Lan & Syrgkanis (AISTATS 2024) dùng làm nền cho causal
    Q-aggregation. Giá trị nhỏ hơn là tốt hơn. Loss chỉ có ý nghĩa cho score có
    scale CATE; ranking score như Response không so được bằng metric này.
    """
    signal = _as_float_array(effect_signal, "effect_signal")
    prediction = _as_float_array(cate_prediction, "cate_prediction")
    if len(signal) != len(prediction):
        raise ValueError("effect_signal và cate_prediction phải có cùng độ dài")
    residual = (signal - prediction) ** 2
    if sample_weight is None:
        return float(np.mean(residual))
    weight = _as_float_array(sample_weight, "sample_weight")
    if len(weight) != len(signal):
        raise ValueError("sample_weight phải có cùng độ dài với effect_signal")
    if np.any(weight < 0) or weight.sum() <= 0:
        raise ValueError("sample_weight phải không âm và có tổng > 0")
    return float(np.average(residual, weights=weight))
