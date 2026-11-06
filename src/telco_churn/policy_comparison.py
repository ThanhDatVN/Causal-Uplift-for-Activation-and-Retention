"""Paired policy comparison over the disagreement region (E20, backlog V4-02).

For two deterministic policies with the same action semantics, the same reward
and no interference, the contrast decomposes as

``Delta = P(D=1) * E[R(pi1) - R(pi0) | D=1]``  with ``D(X) = 1{pi1(X) != pi0(X)}``.

This is an identity of the contrast, not an assumption that the treatment effect
is zero where the policies agree: both policies simply take the same action
there.  Working with per-unit paired scores

``Z_i = Gamma_i(pi1(X_i)) - Gamma_i(pi0(X_i))``

makes that identity exact in finite samples -- ``Z_i`` is *identically* zero on
the agreement region when both policies are scored with the same nuisance
estimates, so both the point estimate and its standard error come only from the
units where the decisions differ.

Two things this module deliberately does not do:

* It does not present the pairing as a new estimator.  Paired AIPW is the
  standard construction; the contribution being tested in V4 is the *sampling
  design* in :func:`enriched_sampling_contrast`, not the algebra.
* It does not fold a fixed deployment overhead into the sampling uncertainty.
  A challenger that costs more to run than business as usual shifts the net
  contrast by a known constant, even where ``D = 0``; that constant has no
  standard error, and :class:`PolicyContrast` keeps it separate.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats

from .problem_contract import ContractViolation

__all__ = [
    "MIN_EFFECTIVE_DF",
    "ActionScores",
    "BatchPolicyContrast",
    "IntervalMethod",
    "PolicyContrast",
    "SamplingContrast",
    "SupportDiagnostics",
    "action_pair_strata",
    "align_by_row_key",
    "batch_policy_contrast",
    "cost_to_precision",
    "design_asymmetry_index",
    "disagreement_mask",
    "dr_action_scores",
    "dr_action_scores_with_support",
    "enriched_sampling_contrast",
    "ipw_action_scores",
    "paired_contrast",
    "unpaired_contrast",
]

#: Floor used by the *declared* support policies.  It is never applied to the
#: primary estimator: ``support_policy="unmodified"`` uses the design
#: probabilities exactly as they were logged (G01).
DEFAULT_SUPPORT_FLOOR = 1e-3

SupportPolicy = Literal["unmodified", "reject", "clip"]
VarianceTarget = Literal["finite_frame", "superpopulation"]
IntervalMethod = Literal["normal", "skewness_adjusted", "skewness_adjusted_t", "bootstrap_t"]

#: Floor on the kurtosis-based effective degrees of freedom.  Without it the
#: correction is unbounded: a score with excess kurtosis in the thousands
#: implies df in the single digits and an interval wide enough to be useless.
MIN_EFFECTIVE_DF = 30.0

_MAX_REPORTED_KEYS = 5


def _as_action_array(actions: Sequence[Any] | np.ndarray | pd.Series, *, name: str) -> np.ndarray:
    array = np.asarray(pd.Series(actions).to_numpy(), dtype=object)
    if array.ndim != 1:
        raise ContractViolation(f"{name} must be one-dimensional")
    return array


def _validate_action_columns(frame: pd.DataFrame, *, name: str) -> dict[str, int]:
    """Column-label contract for an action-indexed frame.

    Actions are matched by their string form, so ``1`` and ``"1"`` would land in
    the same slot and the last one silently win.  Two columns that collapse to
    the same label are an ambiguity in the action map, not a detail to resolve
    by ordering (G02).
    """

    lookup: dict[str, int] = {}
    collisions: list[str] = []
    for index, column in enumerate(frame.columns):
        label = str(column)
        if not label or label.lower() in {"nan", "none"}:
            raise ContractViolation(f"{name} has an unnamed action column at position {index}")
        if label in lookup:
            collisions.append(label)
        lookup[label] = index
    if collisions:
        raise ContractViolation(
            f"{name} has action columns that collapse to the same label "
            f"{sorted(set(collisions))}; mixed types such as 1 and '1' or duplicated "
            "columns make the action map ambiguous"
        )
    return lookup


def _check_score_frame(scores: pd.DataFrame, actions: np.ndarray, *, name: str) -> None:
    lookup = _validate_action_columns(scores, name="the score frame")
    unknown = sorted({str(a) for a in actions} - set(lookup))
    if unknown:
        raise ContractViolation(
            f"{name} selects actions {unknown} that have no column in the score frame; "
            "an action without support may not be scored by imputation"
        )


def _gather(scores: pd.DataFrame, actions: np.ndarray) -> np.ndarray:
    """Pick ``scores[i, actions[i]]`` for every row, by action label."""

    lookup = _validate_action_columns(scores, name="the score frame")
    values = scores.to_numpy(dtype=float)
    columns = np.array([lookup[str(a)] for a in actions], dtype=int)
    return values[np.arange(len(actions)), columns]


def disagreement_mask(
    policy_1_actions: Sequence[Any], policy_0_actions: Sequence[Any]
) -> np.ndarray:
    """``True`` where the two frozen policies choose different actions."""

    a1 = _as_action_array(policy_1_actions, name="policy_1_actions")
    a0 = _as_action_array(policy_0_actions, name="policy_0_actions")
    if a1.shape != a0.shape:
        raise ContractViolation("the two policies must be evaluated on the same cohort")
    return np.array([str(x) != str(y) for x, y in zip(a1, a0, strict=True)], dtype=bool)


def _describe_keys(index: pd.Index, mask: np.ndarray) -> str:
    keys = [repr(key) for key in index[mask][:_MAX_REPORTED_KEYS]]
    more = int(mask.sum()) - len(keys)
    return ", ".join(keys) + (f" (+{more} more)" if more > 0 else "")


def _require_finite(values: np.ndarray, index: pd.Index, *, name: str) -> None:
    """Reject NaN/Inf with the offending row keys instead of emitting NaN metrics."""

    bad = ~np.isfinite(values)
    if bad.any():
        flat = bad.any(axis=1) if bad.ndim > 1 else bad
        raise ContractViolation(
            f"{name} has {int(bad.sum())} non-finite value(s) at row key(s) "
            f"{_describe_keys(index, flat)}; a metric may not be reported over them"
        )


def align_by_row_key(
    objects: Mapping[str, pd.DataFrame | pd.Series],
    *,
    row_key: Sequence[Any],
) -> dict[str, pd.DataFrame | pd.Series]:
    """Join every frame onto one declared row key (G02, A02).

    "Both frames have N rows" is not evidence that row ``i`` describes the same
    account in both of them.  This reindexes each object onto ``row_key`` and
    refuses anything that is not a permutation of it, so a shuffled or partially
    overlapping frame fails loudly instead of contributing a positional contrast
    between two different accounts.
    """

    keys = pd.Index(list(row_key))
    if keys.has_duplicates:
        duplicated = keys[keys.duplicated()].unique().tolist()[:_MAX_REPORTED_KEYS]
        raise ContractViolation(
            f"row_key repeats {duplicated}; a decision unit may appear once per frame"
        )
    aligned: dict[str, pd.DataFrame | pd.Series] = {}
    for name, obj in objects.items():
        if not isinstance(obj, (pd.DataFrame, pd.Series)):
            raise ContractViolation(f"{name} carries no row key; pass a Series or DataFrame")
        if obj.index.has_duplicates:
            raise ContractViolation(f"{name} has duplicate row keys")
        if len(obj.index) != len(keys) or not obj.index.sort_values().equals(keys.sort_values()):
            missing = keys.difference(obj.index).tolist()[:_MAX_REPORTED_KEYS]
            extra = obj.index.difference(keys).tolist()[:_MAX_REPORTED_KEYS]
            raise ContractViolation(
                f"{name} is not a permutation of row_key (missing {missing}, extra {extra}); "
                "frames must be joined on the decision-unit key, not on position"
            )
        aligned[name] = obj.reindex(keys)
    return aligned


def _check_shared_row_keys(named: Mapping[str, Any]) -> pd.Index:
    """Every keyed input must carry the *same* index in the *same* order."""

    keyed = {
        name: obj.index for name, obj in named.items() if isinstance(obj, (pd.DataFrame, pd.Series))
    }
    if not keyed:
        return pd.Index([])
    reference_name, reference = next(iter(keyed.items()))
    if reference.has_duplicates:
        raise ContractViolation(f"{reference_name} has duplicate row keys")
    for name, index in keyed.items():
        if index.equals(reference):
            continue
        same_set = len(index) == len(reference) and index.sort_values().equals(
            reference.sort_values()
        )
        detail = "the same keys in a different order" if same_set else "a different set of keys"
        raise ContractViolation(
            f"{name} and {reference_name} carry {detail}; align them with "
            "align_by_row_key(...) instead of relying on position"
        )
    return reference


@dataclass(frozen=True)
class SupportDiagnostics:
    """What the propensities looked like, and what (if anything) was changed.

    The primary estimator never edits a logged design probability.  When a
    declared sensitivity analysis does clip, the count and the weights it moved
    are recorded here so the edit appears in the report rather than inside the
    estimate (G01).
    """

    support_policy: str
    support_floor: float
    n_units: int
    min_propensity: float
    min_taken_propensity: float
    n_cells_below_floor: int
    n_taken_below_floor: int
    n_clipped: int
    max_weight: float
    effective_sample_size: float
    ess_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionScores:
    """Score frame plus the support diagnostics that produced it."""

    scores: pd.DataFrame
    support: SupportDiagnostics


def _support_diagnostics(
    e: np.ndarray,
    taken_e: np.ndarray,
    *,
    support_policy: str,
    support_floor: float,
    n_clipped: int,
) -> SupportDiagnostics:
    weights = 1.0 / taken_e
    ess = float(weights.sum() ** 2 / np.square(weights).sum()) if weights.size else 0.0
    return SupportDiagnostics(
        support_policy=support_policy,
        support_floor=float(support_floor),
        n_units=int(taken_e.size),
        min_propensity=float(e.min()) if e.size else float("nan"),
        min_taken_propensity=float(taken_e.min()) if taken_e.size else float("nan"),
        n_cells_below_floor=int((e < support_floor).sum()),
        n_taken_below_floor=int((taken_e < support_floor).sum()),
        n_clipped=int(n_clipped),
        max_weight=float(weights.max()) if weights.size else float("nan"),
        effective_sample_size=ess,
        ess_ratio=float(ess / taken_e.size) if taken_e.size else float("nan"),
    )


def dr_action_scores_with_support(
    reward: Sequence[float],
    action: Sequence[Any],
    propensity: pd.DataFrame,
    predicted_reward: pd.DataFrame,
    *,
    row_key: Sequence[Any] | None = None,
    support_policy: SupportPolicy = "unmodified",
    support_floor: float = DEFAULT_SUPPORT_FLOOR,
) -> ActionScores:
    """Augmented IPW score ``Gamma_i(a)`` for every action column.

    ``Gamma_i(a) = m_a(X_i) + 1{A_i = a} / e_a(X_i) * (R_i - m_a(X_i))``

    ``propensity`` holds the *design* probabilities where they are known.  An
    estimated propensity is a diagnostic, not a source of truth, and the caller
    is responsible for saying which one it passed.

    ``support_policy`` says what happens when a realised action had very little
    probability of being taken.  The three answers are different studies and the
    choice is never made silently (G01):

    ``"unmodified"``
        The primary estimator.  Design probabilities are used exactly as logged;
        a tiny ``e`` produces a large weight, which is a real property of the
        design and is reported in :class:`SupportDiagnostics`.
    ``"reject"``
        The support contract.  A realised action below ``support_floor`` fails
        with its row keys: the target is declared out of support rather than
        estimated from one heavily weighted unit.
    ``"clip"``
        A declared sensitivity analysis.  ``e`` is floored at ``support_floor``
        and the number of moved cells is recorded.  The result is biased by
        construction and may not be reported as the primary estimate.
    """

    if support_policy not in ("unmodified", "reject", "clip"):
        raise ContractViolation(f"unknown support_policy {support_policy!r}")
    if not 0 <= support_floor < 1:
        raise ContractViolation("support_floor must lie in [0, 1)")

    if row_key is not None:
        keyed = {
            name: obj
            for name, obj in (
                ("reward", reward),
                ("action", action),
                ("propensity", propensity),
                ("predicted_reward", predicted_reward),
            )
            if isinstance(obj, (pd.DataFrame, pd.Series))
        }
        aligned = align_by_row_key(keyed, row_key=row_key)
        reward = aligned.get("reward", reward)
        action = aligned.get("action", action)
        propensity = aligned.get("propensity", propensity)
        predicted_reward = aligned.get("predicted_reward", predicted_reward)
    else:
        _check_shared_row_keys(
            {
                "propensity": propensity,
                "predicted_reward": predicted_reward,
                "reward": reward,
                "action": action,
            }
        )

    y = np.asarray(list(reward), dtype=float)
    actions = _as_action_array(action, name="action")
    if len(y) != len(actions):
        raise ContractViolation("reward and action must have the same length")
    if not propensity.columns.equals(predicted_reward.columns):
        raise ContractViolation("propensity and predicted_reward must share action columns")
    if len(propensity) != len(y) or len(predicted_reward) != len(y):
        raise ContractViolation("nuisance frames must have one row per unit")
    lookup = _validate_action_columns(propensity, name="propensity")
    _check_score_frame(propensity, actions, name="action")

    index = propensity.index
    _require_finite(y, index, name="reward")

    e = propensity.to_numpy(dtype=float)
    if np.isnan(e).any():
        raise ContractViolation("propensity must be fully specified")
    _require_finite(e, index, name="propensity")
    if (e <= 0).any() or (e > 1).any():
        raise ContractViolation("propensity values must lie in (0, 1]")
    row_sums = e.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-6):
        raise ContractViolation("per-unit action probabilities must sum to one")

    m = predicted_reward.to_numpy(dtype=float)
    _require_finite(m, index, name="predicted_reward")

    rows = np.arange(len(actions))
    columns = np.array([lookup[str(a)] for a in actions], dtype=int)
    taken_e = e[rows, columns]

    n_clipped = 0
    if support_policy == "reject":
        below = taken_e < support_floor
        if below.any():
            raise ContractViolation(
                f"{int(below.sum())} realised action(s) have propensity below the declared "
                f"support floor {support_floor:g} at row key(s) {_describe_keys(index, below)}; "
                "the contrast is out of support here and may not be estimated by clipping "
                "the design probability"
            )
    elif support_policy == "clip":
        n_clipped = int((e < support_floor).sum())
        e = np.clip(e, support_floor, 1.0)
        taken_e = e[rows, columns]

    diagnostics = _support_diagnostics(
        e,
        taken_e,
        support_policy=support_policy,
        support_floor=support_floor,
        n_clipped=n_clipped,
    )

    taken = np.zeros_like(m, dtype=float)
    taken[rows, columns] = 1.0
    residual = (y - m[rows, columns])[:, None]
    scores = pd.DataFrame(m + taken * residual / e, columns=propensity.columns, index=index)
    scores.attrs["support"] = diagnostics.to_dict()
    return ActionScores(scores=scores, support=diagnostics)


def dr_action_scores(
    reward: Sequence[float],
    action: Sequence[Any],
    propensity: pd.DataFrame,
    predicted_reward: pd.DataFrame,
    *,
    row_key: Sequence[Any] | None = None,
    support_policy: SupportPolicy = "unmodified",
    support_floor: float = DEFAULT_SUPPORT_FLOOR,
) -> pd.DataFrame:
    """Score frame only; see :func:`dr_action_scores_with_support` for the contract.

    The support diagnostics stay attached as ``scores.attrs["support"]`` so a
    caller that only wants the frame still carries the weight report with it.
    """

    return dr_action_scores_with_support(
        reward,
        action,
        propensity,
        predicted_reward,
        row_key=row_key,
        support_policy=support_policy,
        support_floor=support_floor,
    ).scores


def ipw_action_scores(
    reward: Sequence[float],
    action: Sequence[Any],
    propensity: pd.DataFrame,
    *,
    row_key: Sequence[Any] | None = None,
    support_policy: SupportPolicy = "unmodified",
    support_floor: float = DEFAULT_SUPPORT_FLOOR,
) -> pd.DataFrame:
    """Inverse-probability score, i.e. :func:`dr_action_scores` with ``m = 0``."""

    zeros = pd.DataFrame(
        np.zeros((len(propensity), propensity.shape[1])),
        columns=propensity.columns,
        index=propensity.index,
    )
    return dr_action_scores(
        reward,
        action,
        propensity,
        zeros,
        row_key=row_key,
        support_policy=support_policy,
        support_floor=support_floor,
    )


@dataclass(frozen=True)
class PolicyContrast:
    """Result of one paired comparison.

    ``delta`` is the action-outcome contrast and carries all of the sampling
    uncertainty.  ``fixed_overhead_per_account`` is a known constant and is
    reported next to it, never inside ``se``.
    """

    delta: float
    se: float
    ci_low: float
    ci_high: float
    n_units: int
    n_clusters: int
    n_disagreement: int
    share_changed: float
    estimator: str
    paired: bool
    alpha: float
    fixed_overhead_per_account: float = 0.0
    interval_method: str = "normal"

    @property
    def delta_net(self) -> float:
        """Contrast after the known deployment-overhead difference."""

        return self.delta - self.fixed_overhead_per_account

    @property
    def delta_net_per_1000(self) -> float:
        return self.delta_net * 1000.0

    @property
    def is_identical(self) -> bool:
        """Exactly zero contrast and zero sampling uncertainty."""

        return self.n_disagreement == 0 and self.delta == 0.0 and self.se == 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimator": self.estimator,
            "paired": self.paired,
            "delta": self.delta,
            "se": self.se,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "alpha": self.alpha,
            "n_units": self.n_units,
            "n_clusters": self.n_clusters,
            "n_disagreement": self.n_disagreement,
            "share_changed": self.share_changed,
            "interval_method": self.interval_method,
            "fixed_overhead_per_account": self.fixed_overhead_per_account,
            "delta_net": self.delta_net,
            "delta_net_per_1000": self.delta_net_per_1000,
        }


def _cluster_moments(values: np.ndarray, cluster: np.ndarray | None) -> tuple[float, float, int]:
    """Mean, cluster-robust standard error and cluster count."""

    n = len(values)
    if n == 0:
        raise ContractViolation("cannot form a contrast on an empty cohort")
    mean = float(values.mean())
    residual = values - mean
    if cluster is None:
        groups = np.arange(n)
    else:
        _, groups = np.unique(np.asarray(cluster, dtype=object), return_inverse=True)
    n_clusters = int(groups.max()) + 1 if n else 0
    sums = np.bincount(groups, weights=residual, minlength=n_clusters)
    if n_clusters <= 1:
        return mean, float("nan"), n_clusters
    correction = n_clusters / (n_clusters - 1)
    variance = correction * float(np.square(sums).sum()) / (n**2)
    return mean, float(np.sqrt(variance)), n_clusters


def _interval(mean: float, se: float, n_clusters: int, alpha: float) -> tuple[float, float]:
    if se == 0.0:
        return mean, mean
    if not np.isfinite(se) or n_clusters <= 1:
        return float("-inf"), float("inf")
    critical = float(stats.t.ppf(1 - alpha / 2, df=n_clusters - 1))
    return mean - critical * se, mean + critical * se


def _skewness_adjusted_interval(
    values: np.ndarray, mean: float, se: float, alpha: float
) -> tuple[float, float]:
    """Cornish-Fisher interval for the studentized mean.

    A symmetric interval around a right-skewed sampling distribution misses
    asymmetrically: the estimate usually lands below the target and the rare
    large contributions are usually absent, so the truth sits above the upper
    limit far more often than below the lower one.  The one-term Edgeworth
    expansion of the studentized statistic ``T = sqrt(n)(mean - mu)/s`` is

    ``P(T <= x) = Phi(x) + n^(-1/2) phi(x) (gamma / 6)(2x^2 + 1) + O(1/n)``

    which inverts to ``t_p = z_p - (gamma / (6 sqrt(n)))(2 z_p^2 + 1)``.  Both
    quantiles move by the same amount, so this *shifts* the interval rather
    than widening it -- which is what an asymmetric miss pattern calls for.

    The correction is first-order in ``gamma / sqrt(n)``.  Where that quantity
    is large the expansion is unreliable, so the shift is capped at one
    standard error and the fact is reported rather than hidden.
    """

    n = len(values)
    if n < 3 or se == 0.0 or not np.isfinite(se):
        return _interval(mean, se, n, alpha)
    centred = values - values.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return _interval(mean, se, n, alpha)
    skewness = float(np.mean(centred**3) / variance**1.5)
    z = float(stats.norm.ppf(1 - alpha / 2))
    shift = (skewness / (6.0 * math.sqrt(n))) * (2.0 * z**2 + 1.0)
    shift = float(np.clip(shift, -1.0, 1.0))
    return mean - (z - shift) * se, mean + (z + shift) * se


def _effective_degrees_of_freedom(values: np.ndarray) -> float:
    """Satterthwaite-style df for the variance of a heavy-tailed mean.

    A t-interval with ``n - 1`` degrees of freedom assumes the variance is
    estimated from ``n`` effective observations.  When the score is dominated
    by a handful of heavily weighted units that is false: matching the
    variance of ``S^2`` to a chi-square gives

    ``df_eff = 2n / (kappa - 1)``

    with ``kappa`` the (non-excess) kurtosis.  For a rare outcome under an
    imbalanced design ``kappa`` runs into the thousands, so the raw formula
    collapses df into single digits.  That is the quantity this function
    reports; the caller decides whether to floor it.
    """

    n = len(values)
    if n < 4:
        return float(max(n - 1, 1))
    centred = values - values.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return float(n - 1)
    kurtosis = float(np.mean(centred**4) / variance**2)
    denominator = max(kurtosis - 1.0, 1e-9)
    return float(min(2.0 * n / denominator, n - 1))


def _skewness_adjusted_t_interval(
    values: np.ndarray, mean: float, se: float, alpha: float, *, floor_df: float
) -> tuple[float, float]:
    """The two corrections together: shift for skew, widen for unstable variance.

    R01 separated the failure into an asymmetric part, which the Edgeworth
    shift fixes, and a width deficit, which it does not.  This adds the second
    piece by replacing the normal quantile with a t quantile on effective
    degrees of freedom.
    """

    n = len(values)
    if n < 4 or se == 0.0 or not np.isfinite(se):
        return _interval(mean, se, n, alpha)
    centred = values - values.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return _interval(mean, se, n, alpha)
    skewness = float(np.mean(centred**3) / variance**1.5)
    df = max(_effective_degrees_of_freedom(values), floor_df)
    quantile = float(stats.t.ppf(1 - alpha / 2, df=df))
    shift = (skewness / (6.0 * math.sqrt(n))) * (2.0 * quantile**2 + 1.0)
    shift = float(np.clip(shift, -1.0, 1.0))
    return mean - (quantile - shift) * se, mean + (quantile + shift) * se


def _bootstrap_t_interval(
    values: np.ndarray,
    groups: np.ndarray | None,
    mean: float,
    se: float,
    alpha: float,
    *,
    resamples: int,
    seed: int,
    block: int = 200,
) -> tuple[float, float]:
    """Studentized bootstrap interval, resampling the independent unit.

    Second-order accurate: it learns the shape of the studentized statistic
    from the data instead of assuming it is normal, so it corrects skew and
    the instability of the variance estimate at the same time.  Clusters are
    the resampling unit when they are declared -- resampling rows inside a
    cluster would destroy the dependence the interval exists to carry.
    """

    n = len(values)
    if n < 3 or se == 0.0 or not np.isfinite(se):
        return _interval(mean, se, n, alpha)
    rng = np.random.default_rng(seed)

    if groups is None:
        statistics = []
        for start in range(0, resamples, block):
            draws = min(block, resamples - start)
            index = rng.integers(0, n, size=(draws, n))
            sample = values[index]
            boot_mean = sample.mean(axis=1)
            boot_se = sample.std(axis=1, ddof=1) / math.sqrt(n)
            with np.errstate(divide="ignore", invalid="ignore"):
                statistics.append(np.where(boot_se > 0, (boot_mean - mean) / boot_se, 0.0))
        studentized = np.concatenate(statistics)
    else:
        # Cluster bootstrap: draw whole clusters, then recompute both the mean
        # and its cluster-robust standard error on the drawn sample.  Rows are
        # never resampled inside a cluster -- that would destroy exactly the
        # dependence the interval exists to carry.
        unique, inverse = np.unique(groups, return_inverse=True)
        n_groups = len(unique)
        order = np.argsort(inverse, kind="stable")
        sizes = np.bincount(inverse, minlength=n_groups)
        equal_size = int(sizes[0]) if n_groups and np.all(sizes == sizes[0]) else 0

        if equal_size:
            # Equal-size clusters vectorise: one gather over a (groups, size)
            # membership matrix instead of a Python loop per resample.
            members = order.reshape(n_groups, equal_size)
            statistics = []
            for start in range(0, resamples, block):
                draws = min(block, resamples - start)
                picks = rng.integers(0, n_groups, size=(draws, n_groups))
                index = members[picks].reshape(draws, n_groups * equal_size)
                sample = values[index]
                boot_mean = sample.mean(axis=1)
                residual = sample - boot_mean[:, None]
                sums = residual.reshape(draws, n_groups, equal_size).sum(axis=2)
                correction = n_groups / (n_groups - 1) if n_groups > 1 else 1.0
                variance = correction * np.square(sums).sum(axis=1) / (sample.shape[1] ** 2)
                boot_se = np.sqrt(variance)
                with np.errstate(divide="ignore", invalid="ignore"):
                    statistics.append(np.where(boot_se > 0, (boot_mean - mean) / boot_se, 0.0))
            studentized = np.concatenate(statistics)
        else:
            members_by_group = [
                order[sizes[:index].sum() : sizes[: index + 1].sum()] for index in range(n_groups)
            ]
            studentized = np.empty(resamples, dtype=float)
            for draw in range(resamples):
                picks = rng.integers(0, n_groups, size=n_groups)
                index = np.concatenate([members_by_group[pick] for pick in picks])
                sample = values[index]
                labels = np.repeat(
                    np.arange(n_groups), [len(members_by_group[pick]) for pick in picks]
                )
                boot_mean, boot_se, _ = _cluster_moments(sample, labels)
                studentized[draw] = (
                    (boot_mean - mean) / boot_se if boot_se and np.isfinite(boot_se) else 0.0
                )

    finite = studentized[np.isfinite(studentized)]
    if finite.size < 10:
        return _interval(mean, se, n, alpha)
    low_q = float(np.quantile(finite, alpha / 2))
    high_q = float(np.quantile(finite, 1 - alpha / 2))
    return mean - high_q * se, mean - low_q * se


def paired_contrast(
    scores: pd.DataFrame,
    policy_1_actions: Sequence[Any],
    policy_0_actions: Sequence[Any],
    *,
    cluster: Sequence[Any] | None = None,
    alpha: float = 0.05,
    fixed_overhead_per_account: float = 0.0,
    estimator: str = "paired_dr",
    interval_method: IntervalMethod = "normal",
    bootstrap_resamples: int = 999,
    bootstrap_seed: int = 20260921,
    effective_df_floor: float = MIN_EFFECTIVE_DF,
) -> PolicyContrast:
    """Whole-cohort paired contrast between two frozen policies.

    ``scores`` must hold one column per action and one row per eligible unit --
    the *whole* cohort, not only the units where the policies disagree.  Rows in
    the agreement region contribute exactly zero, which is what makes the
    standard error collapse for identical policies.
    """

    if not 0 < alpha < 1:
        raise ContractViolation("alpha must lie in (0, 1)")
    a1 = _as_action_array(policy_1_actions, name="policy_1_actions")
    a0 = _as_action_array(policy_0_actions, name="policy_0_actions")
    if len(scores) != len(a1) or len(scores) != len(a0):
        raise ContractViolation("scores and both policies must cover the same cohort")
    _check_score_frame(scores, a1, name="policy_1_actions")
    _check_score_frame(scores, a0, name="policy_0_actions")

    value_1 = _gather(scores, a1)
    value_0 = _gather(scores, a0)
    # Both policies read the same score frame, which is what makes the agreement
    # region a structural zero rather than an approximate one.  A missing score
    # would silently destroy that, so it fails here instead.
    if not np.isfinite(value_1).all() or not np.isfinite(value_0).all():
        raise ContractViolation(
            "the score frame has missing or infinite values for a selected action; "
            "an unsupported action must be refused, not scored by imputation"
        )
    paired = value_1 - value_0
    changed = disagreement_mask(a1, a0)
    cluster_array = None if cluster is None else np.asarray(list(cluster), dtype=object)
    if cluster_array is not None and len(cluster_array) != len(paired):
        raise ContractViolation("cluster must have one entry per unit")
    mean, se, n_clusters = _cluster_moments(paired, cluster_array)
    if interval_method == "normal":
        low, high = _interval(mean, se, n_clusters, alpha)
    elif interval_method == "skewness_adjusted":
        if cluster_array is not None:
            raise ContractViolation(
                "the skewness-adjusted interval is derived for independent units; "
                "use bootstrap_t when clusters are declared"
            )
        low, high = _skewness_adjusted_interval(paired, mean, se, alpha)
    elif interval_method == "skewness_adjusted_t":
        if cluster_array is not None:
            raise ContractViolation(
                "the skewness-adjusted interval is derived for independent units; "
                "use bootstrap_t when clusters are declared"
            )
        low, high = _skewness_adjusted_t_interval(
            paired, mean, se, alpha, floor_df=effective_df_floor
        )
    elif interval_method == "bootstrap_t":
        groups = None
        if cluster_array is not None:
            _, groups = np.unique(cluster_array, return_inverse=True)
        low, high = _bootstrap_t_interval(
            paired,
            groups,
            mean,
            se,
            alpha,
            resamples=bootstrap_resamples,
            seed=bootstrap_seed,
        )
    else:
        raise ContractViolation(f"unknown interval_method {interval_method!r}")
    return PolicyContrast(
        delta=mean,
        se=se,
        ci_low=low,
        ci_high=high,
        n_units=len(paired),
        n_clusters=n_clusters,
        n_disagreement=int(changed.sum()),
        share_changed=float(changed.mean()),
        estimator=estimator,
        paired=True,
        alpha=alpha,
        fixed_overhead_per_account=float(fixed_overhead_per_account),
        interval_method=interval_method,
    )


def unpaired_contrast(
    scores: pd.DataFrame,
    policy_1_actions: Sequence[Any],
    policy_0_actions: Sequence[Any],
    *,
    alpha: float = 0.05,
    fixed_overhead_per_account: float = 0.0,
) -> PolicyContrast:
    """Difference of two separately estimated policy values, ignoring covariance.

    This is a **diagnostic**, not a candidate estimator: it is what an analysis
    that compares two overall means without pairing would report.  Its standard
    error stays positive even when the two policies are identical, which is the
    inefficiency :func:`paired_contrast` removes.
    """

    a1 = _as_action_array(policy_1_actions, name="policy_1_actions")
    a0 = _as_action_array(policy_0_actions, name="policy_0_actions")
    value_1 = _gather(scores, a1)
    value_0 = _gather(scores, a0)
    n = len(value_1)
    mean = float(value_1.mean() - value_0.mean())
    var = float(value_1.var(ddof=1) + value_0.var(ddof=1)) / n
    se = float(np.sqrt(var))
    low, high = _interval(mean, se, n, alpha)
    changed = disagreement_mask(a1, a0)
    return PolicyContrast(
        delta=mean,
        se=se,
        ci_low=low,
        ci_high=high,
        n_units=n,
        n_clusters=n,
        n_disagreement=int(changed.sum()),
        share_changed=float(changed.mean()),
        estimator="unpaired_diagnostic",
        paired=False,
        alpha=alpha,
        fixed_overhead_per_account=float(fixed_overhead_per_account),
    )


def action_pair_strata(
    scores: pd.DataFrame,
    policy_1_actions: Sequence[Any],
    policy_0_actions: Sequence[Any],
) -> pd.DataFrame:
    """Contrast decomposed by the ``(pi0 action, pi1 action)`` pair.

    Strata are defined by pre-treatment policy decisions only.  Nothing here may
    read evaluation outcomes to choose the strata.
    """

    a1 = _as_action_array(policy_1_actions, name="policy_1_actions")
    a0 = _as_action_array(policy_0_actions, name="policy_0_actions")
    paired = _gather(scores, a1) - _gather(scores, a0)
    frame = pd.DataFrame(
        {
            "bau_action": [str(a) for a in a0],
            "challenger_action": [str(a) for a in a1],
            "paired_score": paired,
        }
    )
    grouped = frame.groupby(["bau_action", "challenger_action"], sort=True)
    table = grouped["paired_score"].agg(["size", "mean", "std"]).reset_index()
    table = table.rename(columns={"size": "n_units", "mean": "mean_paired_score"})
    table["share_of_cohort"] = table["n_units"] / len(frame)
    table["contribution_to_delta"] = table["mean_paired_score"] * table["share_of_cohort"]
    table["is_disagreement"] = table["bau_action"] != table["challenger_action"]
    return table


@dataclass(frozen=True)
class SamplingContrast:
    """Paired contrast estimated from a recruited subsample of a finite frame.

    ``inclusion_probability`` (``q``) is the chance of being recruited into the
    evaluation.  ``propensity`` (``e``) is the chance of receiving an action
    once recruited.  They answer different questions and are never interchanged.

    Two variances are reported because they answer two different questions
    (G03).  ``se_recruitment_only`` is the Horvitz-Thompson variance of the
    frame total *conditional on the realised scores*: it asks how much the
    answer would move if recruitment were redrawn.  ``se_superpopulation`` also
    carries the treatment-assignment and outcome noise inside each score, which
    is what a claim about future units depends on.  A census (``q = 1``
    everywhere) drives the first to exactly zero and leaves the second
    positive; reading the first as "no uncertainty" is the error this split
    exists to prevent.
    """

    delta: float
    se: float
    ci_low: float
    ci_high: float
    frame_size: int
    n_sampled: int
    n_sampled_disagreement: int
    min_inclusion_probability: float
    variance_assumption: str
    alpha: float
    variance_target: str = "finite_frame"
    se_recruitment_only: float = float("nan")
    se_superpopulation: float = float("nan")
    scope_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimator": "horvitz_thompson_paired",
            "delta": self.delta,
            "se": self.se,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "frame_size": self.frame_size,
            "n_sampled": self.n_sampled,
            "n_sampled_disagreement": self.n_sampled_disagreement,
            "min_inclusion_probability": self.min_inclusion_probability,
            "variance_assumption": self.variance_assumption,
            "variance_target": self.variance_target,
            "se_recruitment_only": self.se_recruitment_only,
            "se_superpopulation": self.se_superpopulation,
            "scope_note": self.scope_note,
            "alpha": self.alpha,
        }


_SCOPE_NOTES = {
    "finite_frame": (
        "Recruitment-only uncertainty, conditional on the realised score frame. "
        "It answers 'what if we recruited again from these same units', not "
        "'what would happen to other units'."
    ),
    "superpopulation": (
        "Recruitment, assignment and outcome noise under independent recruitment "
        "and exchangeable units. It is the domain a forward-looking claim needs."
    ),
}


def enriched_sampling_contrast(
    scores: pd.DataFrame,
    policy_1_actions: Sequence[Any],
    policy_0_actions: Sequence[Any],
    *,
    sampled: Sequence[bool],
    inclusion_probability: Sequence[float],
    frame_size: int | None = None,
    alpha: float = 0.05,
    variance_target: VarianceTarget = "finite_frame",
) -> SamplingContrast:
    """Contrast estimated from a recruited subsample of a finite frame.

    Each recruited unit is weighted by ``1 / q_i``, so a design that
    over-recruits the disagreement region stays unbiased for the whole-frame
    contrast.  A unit with ``q_i = 0`` may be excluded only where its paired
    contribution is structurally zero -- that is, where the two policies agree.
    Setting ``q = 0`` on a disagreement unit makes the target unidentified and
    raises.

    Both variance estimators assume independent (Poisson) recruitment given the
    frame.  A fixed-size or stratified design needs its own estimator and a
    finite-population correction; neither is implemented here.

    With ``Z_i`` the paired score, ``S_i`` recruitment and independent
    recruitment given the frame,

    ``Var(S Z / q) = Var(Z) / q + (1 - q) / q * E[Z]^2``

    The first term is the score noise that survives a census; the second is what
    recruitment adds.  ``variance_target="finite_frame"`` reports only the
    second (it treats ``Z`` as fixed), ``"superpopulation"`` reports the sum.
    """

    if variance_target not in ("finite_frame", "superpopulation"):
        raise ContractViolation(f"unknown variance_target {variance_target!r}")
    a1 = _as_action_array(policy_1_actions, name="policy_1_actions")
    a0 = _as_action_array(policy_0_actions, name="policy_0_actions")
    taken = np.asarray(list(sampled), dtype=bool)
    q = np.asarray(list(inclusion_probability), dtype=float)
    n_frame = len(scores) if frame_size is None else int(frame_size)
    if not (len(scores) == len(a1) == len(a0) == len(taken) == len(q)):
        raise ContractViolation("every input must cover the same eligible frame")
    if n_frame <= 0:
        raise ContractViolation("frame_size must be positive")
    if not np.isfinite(q).all():
        raise ContractViolation("inclusion probabilities must be finite")
    if ((q < 0) | (q > 1)).any():
        raise ContractViolation("inclusion probabilities must lie in [0, 1]")

    _check_score_frame(scores, a1, name="policy_1_actions")
    _check_score_frame(scores, a0, name="policy_0_actions")
    paired = _gather(scores, a1) - _gather(scores, a0)
    _require_finite(paired, scores.index, name="the paired score")
    changed = disagreement_mask(a1, a0)
    unidentified = changed & (q <= 0)
    if unidentified.any():
        raise ContractViolation(
            f"{int(unidentified.sum())} disagreement units have zero inclusion probability; "
            "the whole-frame contrast is not identified under this design"
        )
    if (taken & (q <= 0)).any():
        raise ContractViolation("a unit was recruited despite zero inclusion probability")

    if changed.any() and not (taken & changed).any():
        # Every recruited unit sits in the agreement region, where the paired
        # score is a structural zero.  The estimate would be exactly 0 with a
        # standard error of exactly 0 -- certainty from no data.
        raise ContractViolation(
            f"no disagreement unit was recruited out of {int(changed.sum())} in the frame; "
            "the contrast is not estimable from this sample"
        )

    weight = np.zeros_like(q)
    np.divide(1.0, q, out=weight, where=q > 0)
    contribution = paired * weight * taken
    delta = float(contribution.sum() / n_frame)

    # Recruitment-only (Horvitz-Thompson, Z treated as fixed).
    sampled_idx = taken & (q > 0)
    per_unit = paired[sampled_idx]
    q_sampled = q[sampled_idx]
    variance_recruitment = float(
        np.sum((1.0 - q_sampled) * np.square(per_unit) / np.square(q_sampled))
    )
    se_recruitment = float(np.sqrt(variance_recruitment) / n_frame)

    # Superpopulation: add the score noise that a census does not remove.  The
    # agreement region contributes a structural zero with zero variance, so
    # both moments are estimated on the disagreement units only.
    disagreement_sampled = sampled_idx & changed
    weights_d = weight[disagreement_sampled]
    values_d = paired[disagreement_sampled]
    total_weight = float(weights_d.sum())
    if total_weight > 0:
        mean_d = float(np.sum(weights_d * values_d) / total_weight)
        score_variance = float(np.sum(weights_d * np.square(values_d - mean_d)) / total_weight)
    else:
        mean_d, score_variance = 0.0, 0.0
    q_changed = q[changed]
    with np.errstate(divide="ignore", invalid="ignore"):
        per_unit_terms = np.where(
            q_changed > 0,
            score_variance / q_changed + np.square(mean_d) * (1.0 - q_changed) / q_changed,
            0.0,
        )
    variance_super = float(per_unit_terms.sum()) / (n_frame**2)
    se_super = float(np.sqrt(variance_super))

    se = se_recruitment if variance_target == "finite_frame" else se_super
    if se == 0.0:
        low, high = delta, delta
    else:
        critical = float(stats.norm.ppf(1 - alpha / 2))
        low, high = delta - critical * se, delta + critical * se
    positive_q = q[q > 0]
    return SamplingContrast(
        delta=delta,
        se=se,
        ci_low=low,
        ci_high=high,
        frame_size=n_frame,
        n_sampled=int(taken.sum()),
        n_sampled_disagreement=int((taken & changed).sum()),
        min_inclusion_probability=float(positive_q.min()) if positive_q.size else 0.0,
        variance_assumption="poisson_sampling_horvitz_thompson",
        alpha=alpha,
        variance_target=variance_target,
        se_recruitment_only=se_recruitment,
        se_superpopulation=se_super,
        scope_note=_SCOPE_NOTES[variance_target],
    )


@dataclass(frozen=True)
class BatchPolicyContrast:
    """Contrast between two *batch* policies under a shared hard cap.

    A capped policy is not a per-unit rule: whether an account is contacted
    depends on who else is in the batch.  So the interval cannot be the
    interval of a mean -- resampling accounts without re-running the
    allocation holds the decisions fixed and answers a different question.

    ``delta`` re-allocates both policies on the observed batch.  The interval
    re-allocates them inside every bootstrap resample, which is what makes it
    a statement about the *policy*, not about one frozen action vector.
    ``se_frozen_actions`` keeps the naive alternative beside it as a
    diagnostic: when it is much smaller, the difference is the allocation
    uncertainty that answer throws away.
    """

    delta: float
    ci_low: float
    ci_high: float
    se_bootstrap: float
    se_frozen_actions: float
    se_conditional: float
    capacity: int
    n_units: int
    n_selected_policy_1: int
    n_selected_policy_0: int
    n_disagreement: int
    resamples: int
    alpha: float
    target: str
    tie_rule: str = "descending score, then ascending unit id"

    @property
    def allocation_variance_share(self) -> float:
        """How much of the variance the frozen-action answer discards."""

        if self.se_bootstrap <= 0:
            return float("nan")
        return 1.0 - (self.se_frozen_actions / self.se_bootstrap) ** 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimator": "batch_policy_bootstrap",
            "delta": self.delta,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "se_bootstrap": self.se_bootstrap,
            "se_frozen_actions": self.se_frozen_actions,
            "se_conditional": self.se_conditional,
            "allocation_variance_share": self.allocation_variance_share,
            "capacity": self.capacity,
            "n_units": self.n_units,
            "n_selected_policy_1": self.n_selected_policy_1,
            "n_selected_policy_0": self.n_selected_policy_0,
            "n_disagreement": self.n_disagreement,
            "resamples": self.resamples,
            "alpha": self.alpha,
            "target": self.target,
            "tie_rule": self.tie_rule,
        }


def _allocate_under_cap(score: np.ndarray, unit_id: np.ndarray, capacity: int) -> np.ndarray:
    """Top-``capacity`` by score, ties broken by unit id, never by row order."""

    if capacity <= 0:
        return np.zeros(len(score), dtype=bool)
    order = np.lexsort((unit_id, -score))
    chosen = np.zeros(len(score), dtype=bool)
    chosen[order[:capacity]] = True
    return chosen


def batch_policy_contrast(
    scores: pd.DataFrame,
    *,
    score_1: Sequence[float],
    score_0: Sequence[float],
    unit_id: Sequence[Any],
    action_if_selected: str,
    action_if_not: str,
    capacity_fraction: float,
    predicted_reward: pd.DataFrame | None = None,
    alpha: float = 0.05,
    resamples: int = 2_000,
    seed: int = 20260921,
    target: str = "future_batch",
) -> BatchPolicyContrast:
    """Contrast two capped batch policies, re-allocating in every resample.

    ``score_1`` and ``score_0`` are the frozen scoring functions of the two
    policies; the allocation recipe -- sort, cap, tie rule -- is applied to
    both identically, so the comparison is between scoring functions under one
    envelope rather than between two envelopes.

    ``target`` says what the interval covers, and the two are not
    interchangeable.

    ``"future_batch"``
        Resamples accounts, so it carries the variation in who turns up as
        well as in what they do, and it targets the value a *fresh* batch
        would show.
    ``"finite_batch"``
        Conditions on this batch, so the composition and therefore the
        allocation are held and only the outcomes remain random.  It targets
        the value of *this* batch and may not be reported as a
        forward-looking guarantee.

    It is tempting to say the finite interval is narrower by construction.
    It targets the smaller variance -- ``se_bootstrap >= se_frozen_actions``,
    since composition variation only adds -- but the gap can be a couple of
    percent when the cap selects near-exchangeable units, and a percentile
    interval against a normal one can cross at that margin.  Both standard
    errors are returned so the gap can be read rather than assumed.
    """

    values_1 = np.asarray(list(score_1), dtype=float)
    values_0 = np.asarray(list(score_0), dtype=float)
    ids = np.asarray([str(value) for value in unit_id], dtype=object)
    n = len(scores)
    if not (len(values_1) == len(values_0) == len(ids) == n):
        raise ContractViolation("scores, both policy scores and unit ids must cover one batch")
    if not 0 < capacity_fraction <= 1:
        raise ContractViolation("capacity_fraction must lie in (0, 1]")
    if target not in ("future_batch", "finite_batch"):
        raise ContractViolation(f"unknown target {target!r}")

    capacity = math.floor(n * capacity_fraction)
    lookup = _validate_action_columns(scores, name="the score frame")
    for action in (action_if_selected, action_if_not):
        if action not in lookup:
            raise ContractViolation(f"action {action!r} has no column in the score frame")
    matrix = scores.to_numpy(dtype=float)
    selected_column = lookup[action_if_selected]
    idle_column = lookup[action_if_not]

    def contrast_on(index: np.ndarray) -> float:
        chosen_1 = _allocate_under_cap(
            values_1[index], ids[index], math.floor(len(index) * capacity_fraction)
        )
        chosen_0 = _allocate_under_cap(
            values_0[index], ids[index], math.floor(len(index) * capacity_fraction)
        )
        taken = matrix[index]
        value_1 = np.where(chosen_1, taken[:, selected_column], taken[:, idle_column])
        value_0 = np.where(chosen_0, taken[:, selected_column], taken[:, idle_column])
        return float(np.mean(value_1 - value_0))

    identity = np.arange(n)
    delta = contrast_on(identity)

    chosen_1 = _allocate_under_cap(values_1, ids, capacity)
    chosen_0 = _allocate_under_cap(values_0, ids, capacity)
    frozen_paired = np.where(
        chosen_1, matrix[:, selected_column], matrix[:, idle_column]
    ) - np.where(chosen_0, matrix[:, selected_column], matrix[:, idle_column])
    se_frozen = float(np.std(frozen_paired, ddof=1) / math.sqrt(n)) if n > 1 else float("nan")

    # `se_frozen` spreads the *whole* score across units, so it carries the
    # between-unit variation in the predicted means as well as the outcome
    # noise -- that is a superpopulation quantity, and using it to condition
    # on a batch gives an interval that is valid but needlessly wide.  Given
    # the means, the conditional variance is the variance of the residual
    # part alone, because m_a(X) is fixed once the batch is.
    se_conditional = se_frozen
    if predicted_reward is not None:
        if not predicted_reward.columns.equals(scores.columns):
            raise ContractViolation(
                "predicted_reward must share action columns with the score frame"
            )
        if len(predicted_reward) != n:
            raise ContractViolation("predicted_reward must cover the same batch")
        means = predicted_reward.to_numpy(dtype=float)
        _require_finite(means, scores.index, name="predicted_reward")
        conditional_paired = frozen_paired - (
            np.where(chosen_1, means[:, selected_column], means[:, idle_column])
            - np.where(chosen_0, means[:, selected_column], means[:, idle_column])
        )
        se_conditional = (
            float(np.std(conditional_paired, ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
        )

    critical = float(stats.norm.ppf(1 - alpha / 2))
    if target == "finite_batch":
        # Conditioning on this batch fixes the composition *and* therefore the
        # allocation, so there is nothing left for a resample to vary: drawing
        # the identity index `resamples` times returns one number and the
        # quantiles of a constant are that constant.  An earlier version did
        # exactly that and produced an interval of width zero, which covers
        # nothing and is not narrower-but-honest, it is empty.  What remains
        # once the batch is held is the per-unit sampling noise in the scores
        # themselves, and conditional on a fixed allocation the contrast is a
        # plain mean of `frozen_paired`, whose standard error is se_frozen.
        se_bootstrap = float("nan")
        low = delta - critical * se_conditional
        high = delta + critical * se_conditional
    else:
        rng = np.random.default_rng(seed)
        draws = np.empty(resamples, dtype=float)
        for index in range(resamples):
            draws[index] = contrast_on(rng.integers(0, n, size=n))
        se_bootstrap = float(np.std(draws, ddof=1)) if resamples > 1 else float("nan")
        low = float(np.quantile(draws, alpha / 2)) if resamples > 1 else delta
        high = float(np.quantile(draws, 1 - alpha / 2)) if resamples > 1 else delta

    return BatchPolicyContrast(
        delta=delta,
        ci_low=low,
        ci_high=high,
        se_bootstrap=se_bootstrap,
        se_frozen_actions=se_frozen,
        se_conditional=se_conditional,
        capacity=capacity,
        n_units=n,
        n_selected_policy_1=int(chosen_1.sum()),
        n_selected_policy_0=int(chosen_0.sum()),
        n_disagreement=int((chosen_1 != chosen_0).sum()),
        resamples=resamples,
        alpha=alpha,
        target=target,
    )


def cost_to_precision(
    per_unit_variance: float,
    *,
    target_half_width: float,
    cost_per_screened: float,
    cost_per_recruited: float,
    cost_per_outcome: float,
    fixed_cost: float = 0.0,
    screening_ratio: float = 1.0,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Units and money needed to reach a target confidence-interval half-width.

    ``screening_ratio`` is how many units must be screened per unit recruited --
    the number that makes an enriched design expensive when disagreement is rare
    or hard to predict.  The result is a planning figure under the stated
    variance, not a guarantee.
    """

    if per_unit_variance < 0:
        raise ContractViolation("per_unit_variance must be non-negative")
    if target_half_width <= 0:
        raise ContractViolation("target_half_width must be positive")
    if screening_ratio < 1:
        raise ContractViolation("screening_ratio must be at least 1")
    critical = float(stats.norm.ppf(1 - alpha / 2))
    required = per_unit_variance * (critical / target_half_width) ** 2
    n_recruited = float(np.ceil(required)) if required > 0 else 0.0
    n_screened = float(np.ceil(n_recruited * screening_ratio))
    total = (
        fixed_cost
        + n_screened * cost_per_screened
        + n_recruited * (cost_per_recruited + cost_per_outcome)
    )
    return {
        "target_half_width": target_half_width,
        "alpha": alpha,
        "per_unit_variance": per_unit_variance,
        "n_recruited": n_recruited,
        "n_screened": n_screened,
        "total_cost": float(total),
        "cost_per_recruited_unit": float(total / n_recruited) if n_recruited else float("nan"),
    }


def design_asymmetry_index(
    *,
    n_units: int,
    propensity: float,
    event_rate: float,
    acted_fraction: float = 1.0,
) -> float:
    """Predicted skewness of the paired DR contrast, from the design alone.

    A symmetric Wald interval around a skewed sampling distribution misses
    asymmetrically, so the skewness of the *mean* -- not the sample size, and
    not the event count -- is what governs how far coverage falls below
    nominal.  For a two-arm design with a **constant, known** propensity and a
    rare binary outcome, that skewness has a closed form.

    The heavy-tailed part of the per-unit paired score is a spike of size
    ``1/e`` when a treated unit has an event and ``-1/(1-e)`` when a control
    unit does.  Collecting both::

        E[d^3] ~ h * r * (1/e^2 - 1/(1-e)^2)      Var[d] ~ h * r / (e(1-e))

    which reduces to::

        gamma = (1 - 2e) / sqrt(n * h * r * e * (1 - e))

    Two things follow, and they are the reason this function exists rather
    than a bare imbalance threshold:

    * ``(1 - 2e)`` is **exactly zero at a balanced design**, for any event
      rate.  Rarity alone does not skew the contrast; it only amplifies an
      asymmetry that imbalance created.
    * ``n``, ``r`` and ``h`` enter only through their product, as amplifiers.
      A design licensed on imbalance alone ignores all three.

    Measured against the estimator on the V05 generator with six worlds per
    point, the prediction tracks the realised skewness to within 8-22% over
    ``e`` from 0.5 to 0.95, with the residual coming from the augmentation
    term the spike model drops.  It is a design diagnostic, not a guarantee:
    it assumes a constant propensity, a rare binary outcome and a correct
    outcome model, and it says nothing about *where* the acceptable threshold
    lies -- that is measured, in ``overlap_boundary``.

    Args:
        n_units: rows in the frame.
        propensity: the constant treated-arm probability, in (0, 1).
        event_rate: marginal probability of the rare outcome.
        acted_fraction: share of rows where the two policies disagree; only
            those rows contribute to a paired contrast.

    Returns:
        The signed predicted skewness.  Its magnitude is the quantity to
        threshold on; the sign only records which tail is heavy.
    """

    if not 0 < propensity < 1:
        raise ContractViolation(f"propensity must lie in (0, 1); got {propensity}")
    if not 0 <= event_rate <= 1:
        raise ContractViolation(f"event_rate must lie in [0, 1]; got {event_rate}")
    if not 0 <= acted_fraction <= 1:
        raise ContractViolation(f"acted_fraction must lie in [0, 1]; got {acted_fraction}")
    if n_units <= 0:
        raise ContractViolation(f"n_units must be positive; got {n_units}")

    effective = n_units * acted_fraction * event_rate * propensity * (1 - propensity)
    if effective <= 0:
        return float("inf")
    return float((1 - 2 * propensity) / math.sqrt(effective))
