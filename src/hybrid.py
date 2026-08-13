"""Low-dimensional prognostic--causal logistic stacking.

This module implements equations (2) and (3) of Athey, Keleher & Spiess
(``Machine Learning Who to Nudge``, Journal of Econometrics, 2025).  It is
deliberately independent of any nuisance learner: callers must supply an
out-of-sample estimate ``f(x) = P(Y(0)=1 | X=x)`` and, for equation (3), an
out-of-sample absolute CATE estimate ``tau(x)``.

For the hybrid model, define::

    f_tilde(x) = logit(f(x))
    g_tilde(x) = logit(f(x) + tau(x)) - logit(f(x))

and fit the six-parameter logistic model::

    logit P(Y=1 | X=x, T=t)
      = a + a_f f_tilde + a_g g_tilde
          + (b + b_f f_tilde + b_g g_tilde) t.

The small parametric layer can shrink a noisy causal input through ``b_g``.
Leakage prevention is intentionally not hidden here: :class:`HybridLogitStacker`
expects its training inputs to already be out of sample.  The candidate builder
in :mod:`src.candidates` constructs those inputs by inner cross-fitting inside
each outer training fold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression


def _float_vector(values, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype="float64").ravel()
    if vector.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(vector).all():
        raise ValueError(f"{name} must be finite")
    return vector


def _validate_probability_clip(probability_clip: float) -> float:
    value = float(probability_clip)
    if not 0 < value < 0.5:
        raise ValueError("probability_clip must lie in (0, 0.5)")
    return value


def hybrid_logit_transforms(
    baseline_probability,
    cate_prediction,
    *,
    probability_clip: float = 1e-5,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Return ``f_tilde`` and ``g_tilde`` with explicit boundary diagnostics.

    The source model assumes both ``f`` and ``f + tau`` lie in the open unit
    interval.  A learned CATE need not respect that constraint, so the numerical
    implementation clips both probabilities and reports how often clipping was
    required.  These fractions are diagnostics, not tuning targets.
    """

    baseline = _float_vector(baseline_probability, "baseline_probability")
    cate = _float_vector(cate_prediction, "cate_prediction")
    if len(baseline) != len(cate):
        raise ValueError("baseline_probability and cate_prediction must align")
    if np.any((baseline < 0.0) | (baseline > 1.0)):
        raise ValueError("baseline_probability must lie in [0, 1]")
    clip = _validate_probability_clip(probability_clip)

    treated_probability = baseline + cate
    baseline_was_clipped = (baseline <= clip) | (baseline >= 1.0 - clip)
    treated_was_clipped = (
        (treated_probability <= clip)
        | (treated_probability >= 1.0 - clip)
    )
    baseline_clipped = np.clip(baseline, clip, 1.0 - clip)
    treated_clipped = np.clip(treated_probability, clip, 1.0 - clip)
    baseline_logit = logit(baseline_clipped)
    effect_log_odds = logit(treated_clipped) - baseline_logit
    diagnostics = {
        "baseline_clip_fraction": float(np.mean(baseline_was_clipped)),
        "treated_probability_clip_fraction": float(
            np.mean(treated_was_clipped)
        ),
    }
    return baseline_logit, effect_log_odds, diagnostics


def _effect_from_transforms(
    baseline_logit: np.ndarray,
    effect_log_odds: np.ndarray,
    coefficients: np.ndarray,
    *,
    include_cate: bool,
) -> np.ndarray:
    if include_cate:
        if len(coefficients) != 6:
            raise ValueError("equation (3) requires six coefficients")
        intercept, alpha_f, alpha_g, beta, beta_f, beta_g = coefficients
        eta0 = intercept + alpha_f * baseline_logit + alpha_g * effect_log_odds
        eta1 = eta0 + beta + beta_f * baseline_logit + beta_g * effect_log_odds
    else:
        if len(coefficients) != 3:
            raise ValueError("equation (2) requires three coefficients")
        intercept, alpha_f, beta = coefficients
        eta0 = intercept + alpha_f * baseline_logit
        eta1 = eta0 + beta
    return expit(np.clip(eta1, -30.0, 30.0)) - expit(
        np.clip(eta0, -30.0, 30.0)
    )


def hybrid_logit_effect_from_coefficients(
    baseline_probability,
    cate_prediction,
    coefficients,
    *,
    include_cate: bool = True,
    probability_clip: float = 1e-5,
) -> np.ndarray:
    """Evaluate equation (2) or (3) from coefficients in paper order.

    Equation (3) uses ``[a, a_f, a_g, b, b_f, b_g]``.  Equation (2) uses
    ``[a, a_f, b]``.  The pure function makes the nesting/reconstruction
    properties of the model directly testable without fitting an estimator.
    """

    baseline_logit, effect_log_odds, _ = hybrid_logit_transforms(
        baseline_probability,
        cate_prediction,
        probability_clip=probability_clip,
    )
    coefficient_vector = _float_vector(coefficients, "coefficients")
    return _effect_from_transforms(
        baseline_logit,
        effect_log_odds,
        coefficient_vector,
        include_cate=include_cate,
    )


@dataclass
class HybridLogitStacker:
    """Fit equation (2) or (3) on precomputed out-of-sample inputs."""

    include_cate: bool = True
    probability_clip: float = 1e-5
    max_iter: int = 1000

    def __post_init__(self) -> None:
        self.probability_clip = _validate_probability_clip(self.probability_clip)
        self.max_iter = int(self.max_iter)
        if self.max_iter < 1:
            raise ValueError("max_iter must be >= 1")

    def _design(
        self,
        baseline_probability,
        cate_prediction,
        treatment,
    ) -> tuple[np.ndarray, dict[str, float]]:
        baseline_logit, effect_log_odds, diagnostics = hybrid_logit_transforms(
            baseline_probability,
            cate_prediction,
            probability_clip=self.probability_clip,
        )
        treated = _float_vector(treatment, "treatment")
        if len(treated) != len(baseline_logit):
            raise ValueError("treatment must align with model inputs")
        if not set(np.unique(treated)).issubset({0.0, 1.0}):
            raise ValueError("treatment must contain only 0/1")
        if self.include_cate:
            design = np.column_stack(
                [
                    baseline_logit,
                    effect_log_odds,
                    treated,
                    treated * baseline_logit,
                    treated * effect_log_odds,
                ]
            )
        else:
            design = np.column_stack([baseline_logit, treated])
        return design, diagnostics

    def fit(
        self,
        baseline_probability,
        cate_prediction,
        treatment,
        outcome,
    ) -> "HybridLogitStacker":
        design, diagnostics = self._design(
            baseline_probability,
            cate_prediction,
            treatment,
        )
        target = _float_vector(outcome, "outcome")
        if len(target) != len(design):
            raise ValueError("outcome must align with model inputs")
        if not set(np.unique(target)).issubset({0.0, 1.0}):
            raise ValueError("outcome must contain only 0/1")
        if np.unique(target).size < 2:
            raise ValueError("outcome must contain both classes")
        if np.unique(np.asarray(treatment).ravel()).size < 2:
            raise ValueError("treatment must contain both arms")

        # Unpenalized logistic regression is the exact low-dimensional model in
        # equations (2)/(3).  Any regularization search would require another
        # nested validation layer and is intentionally outside this primitive.
        model = LogisticRegression(
            penalty=None,
            solver="lbfgs",
            max_iter=self.max_iter,
            tol=1e-8,
        )
        model.fit(design, target.astype("int8"))
        if int(model.n_iter_[0]) >= self.max_iter:
            raise RuntimeError("hybrid logistic stacker did not converge")
        self.model_ = model
        self.training_diagnostics_ = diagnostics
        self.coefficients_ = np.r_[model.intercept_[0], model.coef_[0]].astype(
            "float64"
        )
        return self

    def effect(self, baseline_probability, cate_prediction) -> np.ndarray:
        if not hasattr(self, "coefficients_"):
            raise RuntimeError("HybridLogitStacker has not been fitted")
        return hybrid_logit_effect_from_coefficients(
            baseline_probability,
            cate_prediction,
            self.coefficients_,
            include_cate=self.include_cate,
            probability_clip=self.probability_clip,
        )
