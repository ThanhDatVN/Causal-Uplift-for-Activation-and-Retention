"""Dựng policy top-k và các tín hiệu hiệu ứng.

Bắt ba lỗi:

- **Policy vượt ngân sách** hoặc không tôn trọng thứ hạng điểm số.
- **IPW và DR không khôi phục được ATE.** Kiểm trên dữ liệu sinh có ATE biết trước; đây là
  cách duy nhất kiểm được tính đúng đắn, vì trên dữ liệu thật không có đáp án.
- **Bootstrap làm mất tính ghép cặp.** Nếu mỗi model được rút một bộ dòng khác nhau thì
  khoảng tin cậy của chênh lệch rộng ra vô cớ và mọi so sánh mất độ nhạy.
"""

import numpy as np
import pytest

from src.policy import (
    bootstrap_policy_values,
    cost_aware_policy,
    doubly_robust_effect_signal,
    ipw_effect_signal,
    policy_value_from_signal,
    top_budget_policy,
)


def test_top_budget_policy_respects_cap_and_ranking():
    score = np.array([0.2, 0.9, 0.4, -0.1, 0.7])
    policy = top_budget_policy(score, budget_fraction=0.4)
    np.testing.assert_array_equal(policy, [0, 1, 0, 0, 1])


def test_cost_aware_policy_can_target_fewer_than_budget():
    effect = np.array([0.01, 0.03, 0.06, 0.08])
    policy = cost_aware_policy(
        effect,
        budget_fraction=0.75,
        value_per_conversion=1.0,
        contact_cost=0.05,
    )
    np.testing.assert_array_equal(policy, [0, 0, 1, 1])


def test_ipw_and_dr_recover_synthetic_ate():
    rng = np.random.default_rng(23)
    n = 300_000
    x = rng.binomial(1, 0.5, size=n)
    treatment = rng.binomial(1, 0.8, size=n)
    mu0 = 0.1 + 0.1 * x
    tau = 0.04 + 0.08 * x
    mu1 = mu0 + tau
    y = rng.binomial(1, np.where(treatment == 1, mu1, mu0))

    ipw = ipw_effect_signal(y, treatment, propensity=0.8)
    dr = doubly_robust_effect_signal(
        y,
        treatment,
        mu0,
        mu1,
        propensity=0.8,
    )
    assert ipw.mean() == pytest.approx(tau.mean(), abs=0.005)
    assert dr.mean() == pytest.approx(tau.mean(), abs=0.005)


def test_policy_value_subtracts_cost_only_for_targeted_rows():
    policy = np.array([1, 0, 1, 0])
    signal = np.array([0.2, 99.0, 0.4, 99.0])
    value = policy_value_from_signal(
        policy,
        signal,
        value_per_conversion=2.0,
        contact_cost=0.1,
    )
    assert value == pytest.approx(((0.4 - 0.1) + (0.8 - 0.1)) / 4)


def test_bootstrap_policy_values_preserves_pairing():
    contribution = np.arange(20, dtype=float)
    matrix = np.column_stack([contribution, contribution])
    result = bootstrap_policy_values(matrix, n_boot=50, seed=42)
    np.testing.assert_allclose(result["draws"][:, 0], result["draws"][:, 1])
