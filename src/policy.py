"""Offline policy construction and evaluation for a randomized experiment.

Monetary inputs are scenario assumptions because Criteo does not contain
customer-level revenue, margin, or contact cost.
"""

from __future__ import annotations

import numpy as np


def top_budget_policy(
    score,
    budget_fraction: float,
    eligible=None,
) -> np.ndarray:
    """Target at most top ``budget_fraction`` observations by score."""
    score = np.asarray(score, dtype="float64").ravel()
    if not 0 <= budget_fraction <= 1:
        raise ValueError("budget_fraction phải nằm trong [0, 1]")
    if not np.isfinite(score).all():
        raise ValueError("score phải hữu hạn")
    n = len(score)
    policy = np.zeros(n, dtype="int8")
    if n == 0 or budget_fraction == 0:
        return policy
    eligible_mask = (
        np.ones(n, dtype=bool)
        if eligible is None
        else np.asarray(eligible, dtype=bool).ravel()
    )
    if len(eligible_mask) != n:
        raise ValueError("eligible phải có cùng độ dài với score")
    eligible_idx = np.flatnonzero(eligible_mask)
    n_target = min(
        len(eligible_idx),
        int(np.floor(n * float(budget_fraction))),
    )
    if n_target == 0:
        return policy
    order = np.argsort(-score[eligible_idx], kind="mergesort")
    policy[eligible_idx[order[:n_target]]] = 1
    return policy


def cost_aware_policy(
    calibrated_effect,
    budget_fraction: float,
    value_per_conversion: float,
    contact_cost: float,
) -> np.ndarray:
    """Target positive expected scenario value, subject to a population budget cap."""
    effect = np.asarray(calibrated_effect, dtype="float64").ravel()
    value = float(value_per_conversion)
    cost = float(contact_cost)
    if value <= 0:
        raise ValueError("value_per_conversion phải > 0")
    if cost < 0:
        raise ValueError("contact_cost phải >= 0")
    expected_net = effect * value - cost
    return top_budget_policy(
        expected_net,
        budget_fraction=budget_fraction,
        eligible=expected_net > 0,
    )


def ipw_effect_signal(
    y_true,
    treatment,
    propensity: float | None = None,
) -> np.ndarray:
    """Per-row inverse-propensity signal whose mean estimates the ATE."""
    y = np.asarray(y_true, dtype="float64").ravel()
    t = np.asarray(treatment, dtype="float64").ravel()
    if len(y) != len(t):
        raise ValueError("y_true và treatment phải có cùng độ dài")
    p = float(np.mean(t) if propensity is None else propensity)
    if not 0 < p < 1:
        raise ValueError("propensity phải nằm trong (0, 1)")
    return t * y / p - (1.0 - t) * y / (1.0 - p)


def doubly_robust_effect_signal(
    y_true,
    treatment,
    mu0,
    mu1,
    propensity: float | None = None,
) -> np.ndarray:
    """AIPW/DR signal for the conditional treatment effect."""
    y = np.asarray(y_true, dtype="float64").ravel()
    t = np.asarray(treatment, dtype="float64").ravel()
    m0 = np.asarray(mu0, dtype="float64").ravel()
    m1 = np.asarray(mu1, dtype="float64").ravel()
    if not (len(y) == len(t) == len(m0) == len(m1)):
        raise ValueError("y_true, treatment, mu0 và mu1 phải có cùng độ dài")
    p = float(np.mean(t) if propensity is None else propensity)
    if not 0 < p < 1:
        raise ValueError("propensity phải nằm trong (0, 1)")
    return (
        m1
        - m0
        + t * (y - m1) / p
        - (1.0 - t) * (y - m0) / (1.0 - p)
    )


def policy_value_from_signal(
    policy,
    effect_signal,
    value_per_conversion: float = 1.0,
    contact_cost: float = 0.0,
) -> float:
    """Mean incremental net value per eligible customer in scenario units."""
    action = np.asarray(policy, dtype="float64").ravel()
    signal = np.asarray(effect_signal, dtype="float64").ravel()
    if len(action) != len(signal):
        raise ValueError("policy và effect_signal phải có cùng độ dài")
    if np.any((action != 0) & (action != 1)):
        raise ValueError("policy phải là vector binary")
    return float(
        np.mean(
            action
            * (float(value_per_conversion) * signal - float(contact_cost))
        )
    )


def bootstrap_policy_values(
    contribution_matrix,
    n_boot: int = 300,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, np.ndarray]:
    """Paired nonparametric bootstrap for precomputed per-row policy contributions."""
    contributions = np.asarray(contribution_matrix, dtype="float64")
    if contributions.ndim == 1:
        contributions = contributions[:, None]
    n = contributions.shape[0]
    if n == 0:
        raise ValueError("contribution_matrix không được rỗng")
    if n_boot < 1:
        raise ValueError("n_boot phải >= 1")
    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, contributions.shape[1]), dtype="float64")
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        weights = np.bincount(idx, minlength=n)
        draws[i] = weights @ contributions / n
    return {
        "draws": draws,
        "mean": contributions.mean(axis=0),
        "ci_low": np.quantile(draws, alpha / 2, axis=0),
        "ci_high": np.quantile(draws, 1 - alpha / 2, axis=0),
    }
