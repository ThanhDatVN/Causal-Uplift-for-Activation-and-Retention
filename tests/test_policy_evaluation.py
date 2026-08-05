import numpy as np
import pytest

from src.policy import (
    doubly_robust_effect_signal,
    ipw_effect_signal,
    policy_value_from_signal,
    top_budget_policy,
)
from src.policy_evaluation import (
    DEFAULT_BUDGET_GRID,
    doubly_robust_risk,
    dr_policy_value_curve,
    expected_random_policy_value,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
    policy_area_from_scores,
    random_topk_sensitivity,
)
from tests.synthetic_rct import make_synthetic_rct


def _oracle_signal(data):
    return doubly_robust_effect_signal(
        data.outcome,
        data.treatment,
        data.mu0,
        data.mu1,
        propensity=data.propensity,
    )


def test_curve_matches_explicit_top_k_policy_value():
    """Nội suy trên curve phải khớp phép cắt top-k trực tiếp trong sai số 1/n."""
    data = make_synthetic_rct(n=100_000, seed=20)
    signal = _oracle_signal(data)
    score = data.X[:, 0]
    budgets = np.array([0.01, 0.05, 0.10, 0.20, 0.30])
    curve = dr_policy_value_curve(signal, score, budgets=budgets)
    for index, budget in enumerate(budgets):
        policy = top_budget_policy(score, budget)
        direct = policy_value_from_signal(policy, signal)
        assert curve["gross_value_per_customer"][index] == pytest.approx(
            direct,
            abs=1e-6,
        )


def test_full_budget_curve_equals_mean_effect_signal():
    data = make_synthetic_rct(n=40_000, seed=21)
    signal = _oracle_signal(data)
    curve = dr_policy_value_curve(signal, data.X[:, 0], budgets=[0.5, 1.0])
    assert curve["gross_value_per_customer"][-1] == pytest.approx(
        float(np.mean(signal))
    )


def test_oracle_policy_area_beats_random_and_reversed():
    data = make_synthetic_rct(n=200_000, seed=22)
    signal = _oracle_signal(data)
    rng = np.random.default_rng(0)
    oracle = policy_area_from_scores(signal, data.tau)
    random_area = policy_area_from_scores(signal, rng.random(len(signal)))
    reversed_area = policy_area_from_scores(signal, -data.tau)
    assert oracle > random_area > reversed_area


def test_policy_area_is_invariant_to_increasing_transform():
    data = make_synthetic_rct(n=50_000, seed=23)
    signal = _oracle_signal(data)
    base = policy_area_from_scores(signal, data.X[:, 0])
    transformed = policy_area_from_scores(signal, np.exp(data.X[:, 0] / 3.0))
    assert transformed == pytest.approx(base, rel=1e-9)


def test_policy_area_single_budget_returns_point_value():
    data = make_synthetic_rct(n=10_000, seed=24)
    signal = _oracle_signal(data)
    curve = dr_policy_value_curve(signal, data.X[:, 0], budgets=[0.1])
    assert policy_area([0.1], curve["gross_value_per_customer"]) == pytest.approx(
        curve["gross_value_per_customer"][0]
    )


def test_policy_area_of_linear_curve_equals_midpoint():
    """Trapezoid trên một curve tuyến tính phải bằng giá trị tại điểm giữa dải."""
    budgets = np.array([0.0, 0.5, 1.0])
    values = np.array([0.0, 0.5, 1.0])
    assert policy_area(budgets, values) == pytest.approx(0.5)


def test_expected_random_policy_matches_random_topk_average():
    data = make_synthetic_rct(n=80_000, seed=25)
    signal = _oracle_signal(data)
    expected = expected_random_policy_value(signal, budgets=DEFAULT_BUDGET_GRID)
    sensitivity = random_topk_sensitivity(
        signal,
        budgets=DEFAULT_BUDGET_GRID,
        n_seeds=30,
        seed=7,
    )
    spread = sensitivity["value_draws"].std(axis=0, ddof=1)
    difference = np.abs(
        sensitivity["value_mean"] - expected["gross_value_per_customer"]
    )
    # Trung bình của 30 random ranking phải nằm trong 4 standard error của
    # stochastic policy pi(x)=b.
    assert np.all(difference <= 4 * spread / np.sqrt(sensitivity["n_seeds"]))
    assert sensitivity["policy_area_std"] > 0


def test_random_topk_sensitivity_is_reproducible():
    data = make_synthetic_rct(n=20_000, seed=26)
    signal = _oracle_signal(data)
    first = random_topk_sensitivity(signal, n_seeds=5, seed=3)
    second = random_topk_sensitivity(signal, n_seeds=5, seed=3)
    np.testing.assert_allclose(first["value_draws"], second["value_draws"])


def test_treat_none_and_full_treat_endpoints():
    data = make_synthetic_rct(n=20_000, seed=27)
    signal = ipw_effect_signal(
        data.outcome,
        data.treatment,
        propensity=data.propensity,
    )
    curve = dr_policy_value_curve(signal, data.X[:, 0], budgets=[0.0001, 1.0])
    assert curve["gross_value_per_customer"][0] < curve["gross_value_per_customer"][-1]
    zero_policy = np.zeros(len(signal), dtype="int8")
    assert policy_value_from_signal(zero_policy, signal) == pytest.approx(0.0)


def test_paired_bootstrap_identical_scores_have_zero_difference():
    data = make_synthetic_rct(n=20_000, seed=28)
    signal = _oracle_signal(data)
    score = data.X[:, 0]
    result = paired_policy_area_bootstrap(
        {"a": score, "b": score.copy()},
        signal,
        n_boot=20,
        seed=5,
    )
    summary = policy_area_difference_summary(result, "a", "b")
    assert summary["observed_difference"] == pytest.approx(0.0, abs=1e-12)
    assert summary["ci_low"] == pytest.approx(0.0, abs=1e-12)
    assert summary["ci_high"] == pytest.approx(0.0, abs=1e-12)


def test_paired_bootstrap_separates_oracle_from_random():
    data = make_synthetic_rct(n=150_000, seed=29)
    signal = _oracle_signal(data)
    rng = np.random.default_rng(1)
    result = paired_policy_area_bootstrap(
        {"oracle": data.tau, "random": rng.random(len(signal))},
        signal,
        n_boot=60,
        seed=6,
    )
    summary = policy_area_difference_summary(result, "oracle", "random")
    assert summary["observed_difference"] > 0
    assert summary["ci_low"] > 0
    assert result["curve_ci_low"].shape == result["observed_curve"].shape


def test_doubly_robust_risk_prefers_true_cate_over_constant():
    data = make_synthetic_rct(n=200_000, seed=30)
    signal = _oracle_signal(data)
    truth_risk = doubly_robust_risk(signal, data.tau)
    constant_risk = doubly_robust_risk(
        signal,
        np.full(len(signal), float(np.mean(data.tau))),
    )
    assert truth_risk < constant_risk


def test_metrics_finite_on_rare_outcome():
    data = make_synthetic_rct(n=150_000, base_rate=0.003, effect_scale=0.002, seed=31)
    signal = _oracle_signal(data)
    area = policy_area_from_scores(signal, data.X[:, 0])
    assert np.isfinite(area)
    curve = dr_policy_value_curve(signal, data.X[:, 0])
    assert np.isfinite(curve["gross_value_per_customer"]).all()


def test_input_validation():
    signal = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        dr_policy_value_curve(signal, np.array([1.0, 2.0]))
    with pytest.raises(ValueError):
        dr_policy_value_curve(signal, signal, budgets=[0.2, 0.1])
    with pytest.raises(ValueError):
        dr_policy_value_curve(signal, signal, budgets=[1.5])
    with pytest.raises(ValueError):
        policy_area([0.1, 0.2], [1.0])
    with pytest.raises(ValueError):
        paired_policy_area_bootstrap({"a": signal}, signal, n_boot=1)
