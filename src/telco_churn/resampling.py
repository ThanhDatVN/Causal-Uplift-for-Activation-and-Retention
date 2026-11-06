"""Resampling helpers with no model dependencies.

``bootstrap_selected_effect`` used to live in :mod:`telco_churn.uplift`, which
imports CatBoost and scikit-learn at module level.  Anything that only wanted
to put an interval around an already-computed score -- a report, the decision
console, a deployed read-only service -- therefore had to install and import a
full training stack to use fifteen lines of NumPy.

Moving it here keeps **one** implementation of the published interval (the
locked Orange decision was produced with it) while letting the serving side
depend on NumPy alone.  ``telco_churn.uplift`` re-exports the name, so existing
imports and notebooks are unaffected.
"""

from __future__ import annotations

import numpy as np

__all__ = ["bootstrap_selected_effect"]


def bootstrap_selected_effect(
    selected: np.ndarray,
    effect_score: np.ndarray,
    *,
    repeats: int = 2_000,
    seed: int = 20260914,
) -> dict[str, float]:
    """Percentile bootstrap of the mean score over the selected sub-cohort.

    The scoring functions are held fixed: this resamples units, not model fits,
    so the interval covers sampling variation in the selected cohort and not
    the uncertainty in the scores themselves.
    """

    values = np.asarray(effect_score, dtype=float)[np.asarray(selected, dtype=bool)]
    if len(values) < 2:
        raise ValueError("At least two selected observations are required")
    rng = np.random.default_rng(seed)
    estimates = np.empty(repeats, dtype=float)
    for repeat in range(repeats):
        estimates[repeat] = rng.choice(values, size=len(values), replace=True).mean()
    return {
        "estimate": float(values.mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
        "bootstrap_repeats": repeats,
    }
