"""R00 exact identities and R01 evaluator validation (runbook V4.1 §4, §9.1-9.2).

The runbook gates model screening on this: *"R02 — Model screening ... Điều kiện
mở đợt: R01 validity gates đạt"*.  Until the evaluator is shown to be unbiased
and correctly covered on scenarios whose truth is known by construction, a
leaderboard of eight models is a leaderboard of an unvalidated ruler.

Two stages live here.

**R00** is six exact identities that hold by algebra, not by approximation, and
are checked to floating-point tolerance.  They are cheap and they catch the
class of error where a sign, a denominator or a cost is wired wrong.

**R01** runs the declared scenarios, each with its generator frozen before the
run, through the *real* evaluator code path -- the same ``dr_action_scores``
and ``paired_contrast`` the benchmark uses, not a reimplementation.  Three
estimator modes are scored per scenario:

``ipw``
    Inverse-probability scores with the known design propensity.
``dr_correct``
    Doubly robust with the generator's analytic conditional means.  This oracle
    is available to the *evaluator test* only; no learner ever sees it.
``dr_misspecified``
    Doubly robust with intercept-only arm means fitted on an independent
    sample.  With a correct propensity this must still be unbiased and
    correctly covered -- that is the double-robustness property being tested,
    not an accident.

Truth is computed two ways per world, because they answer different questions:
the **finite-frame** truth conditions on the realised X and is what a
conditional interval targets, while the **population** truth is the analytic
value the design was built around.  Coverage is scored against the finite-frame
truth; bias is reported against both.

Gate thresholds follow MASTER_PLAN §4.4: the lower Wilson bound on coverage
must reach 0.92, and at a true null the upper Wilson bound on the promotion
rate must stay at or below 0.05 (promotion = lower bound of a two-sided 95%
interval above zero, so the nominal one-sided rate is 2.5%).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats

from .allocation import capacity_limit
from .policy_comparison import (
    _gather,
    dr_action_scores,
    ipw_action_scores,
    paired_contrast,
)

__all__ = [
    "SCENARIOS",
    "IdentityResult",
    "ScenarioSpec",
    "ValidityReport",
    "main",
    "run_r00",
    "run_r01",
    "simulate_world",
]

HOLD = "hold"
CONTACT = "contact"
ACTIONS = (HOLD, CONTACT)

EstimatorMode = Literal["ipw", "dr_correct", "dr_misspecified"]
MODES: tuple[EstimatorMode, ...] = ("ipw", "dr_correct", "dr_misspecified")

#: MASTER_PLAN §4.4 engineering tolerances.
COVERAGE_LOWER_BOUND = 0.92
FALSE_PROMOTION_UPPER_BOUND = 0.05
NOMINAL_COVERAGE = 0.95

#: Benchmark practical margin: one extra conversion per 1,000 eligible.
DELTA_MIN = 0.001


def _scenario_namespace(scenario_id: str) -> int:
    """A stable per-scenario seed namespace, independent of run composition."""

    digest = hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-value))


def _wilson(successes: int, trials: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials == 0:
        return float("nan"), float("nan")
    phat = successes / trials
    denominator = 1 + z**2 / trials
    centre = (phat + z**2 / (2 * trials)) / denominator
    spread = z * math.sqrt(phat * (1 - phat) / trials + z**2 / (4 * trials**2)) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


# -- scenario definitions ---------------------------------------------------
@dataclass(frozen=True)
class ScenarioSpec:
    """One frozen generator.  Every field is declared before the run."""

    scenario_id: str
    title: str
    detects: str
    n_units: int
    true_contrast: float
    is_null: bool
    propensity: str
    cluster_size: int | None = None
    baseline_rate: str = "0.01 + 0.05 * sigmoid(0.8(2X1-1) + 0.5Z)"
    effect: str = ""
    note: str = ""
    #: Largest distance of any design probability from 0.5 in this scenario.
    #: The validated region is read off these, so it is measured, not claimed.
    max_propensity_imbalance: float = 0.0
    min_event_rate: float = 0.035

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        "V01",
        "Sharp null, balanced randomised assignment",
        "false promotion; sign and interval plumbing",
        n_units=10_000,
        true_contrast=0.0,
        is_null=True,
        propensity="e = 0.5",
        effect="tau = 0",
        max_propensity_imbalance=0.0,
    ),
    ScenarioSpec(
        "V02",
        "Constant positive effect, balanced assignment",
        "bias, coverage and power -- not only the null",
        n_units=10_000,
        true_contrast=0.0025,
        is_null=False,
        propensity="e = 0.5",
        effect="tau = 0.005",
    ),
    ScenarioSpec(
        "V03",
        "Heterogeneous effects with marginal ATE = 0",
        "treating a weak null as a sharp null; the policy value is not zero",
        n_units=10_000,
        true_contrast=0.005,
        is_null=False,
        propensity="e = 0.5",
        effect="tau = 0.01 (2X1 - 1)",
        note="ATE is zero while the policy contrast is positive; a promotion here is correct.",
    ),
    ScenarioSpec(
        "V04",
        "Known stratum-varying propensity",
        "an evaluator that assumes a constant propensity",
        n_units=10_000,
        true_contrast=0.005,
        is_null=False,
        propensity="e = 0.2 if X1 = 0 else 0.8",
        max_propensity_imbalance=0.3,
        effect="tau = 0.01 (2X1 - 1)",
        note="Carries an extra negative control: the same data scored with the observed "
        "treatment share in place of the design probability.",
    ),
    ScenarioSpec(
        "V05",
        "Rare binary outcome, imbalanced assignment",
        "interval reliability under event scarcity; no false certainty",
        n_units=10_000,
        true_contrast=0.00025,
        is_null=False,
        propensity="e = 0.9",
        max_propensity_imbalance=0.4,
        min_event_rate=0.005,
        baseline_rate="0.001 + 0.008 * sigmoid(0.8(2X1-1) + 0.5Z)",
        effect="tau = 0.0005",
    ),
    ScenarioSpec(
        "V05B",
        "Rare outcome under a balanced design",
        "whether rarity alone breaks the interval, or only rarity plus imbalance",
        n_units=10_000,
        true_contrast=0.00025,
        is_null=False,
        propensity="e = 0.5",
        baseline_rate="0.001 + 0.008 * sigmoid(0.8(2X1-1) + 0.5Z)",
        effect="tau = 0.0005",
        max_propensity_imbalance=0.0,
        min_event_rate=0.005,
        note="Added 21/09/2026 after the confirmation run: V03 and V05 differ in both "
        "event rate and propensity balance, so neither one isolates the cause. This "
        "cell holds the rate at V05's level and the design at V01's, which is the "
        "regime the Hillstrom primary actually sits in.",
    ),
    ScenarioSpec(
        "V06",
        "Repeated accounts with cluster dependence",
        "IID standard errors under clustering",
        n_units=10_000,
        true_contrast=0.0,
        is_null=True,
        propensity="e = 0.5, drawn once per cluster",
        cluster_size=4,
        effect="tau = 0",
        note="Four accounts per cluster share the treatment draw and one outcome shock. "
        "Scored twice: cluster-robust (the correct design) and IID (the negative control).",
    ),
    ScenarioSpec(
        "B01",
        "Practical-boundary null at the benchmark margin",
        "a promotion rule stated against a margin rather than against zero",
        n_units=10_000,
        true_contrast=DELTA_MIN,
        is_null=False,
        propensity="e = 0.5",
        effect=f"tau = {2 * DELTA_MIN}",
        note="Runbook §9.2. The promotion rule here is lower95 > delta_min, so this is the "
        "null for that rule even though the contrast is positive.",
    ),
    ScenarioSpec(
        "V07",
        "Heavy-tailed continuous reward",
        "tail contributions; finite variance does not give small-sample normality",
        n_units=10_000,
        true_contrast=0.025,
        is_null=False,
        propensity="e = 0.5",
        baseline_rate="R(a) = 1 + 0.2 a (X - 0.5) + t(3)/sqrt(3), X ~ Uniform(0,1)",
        effect="policy contacts X > 0.5",
        note="Runbook §9.1. Rewards are not winsorised: a cap would be a different estimand.",
    ),
)

_BY_ID = {spec.scenario_id: spec for spec in SCENARIOS}


# -- world generation -------------------------------------------------------
def simulate_world(spec: ScenarioSpec, rng: np.random.Generator) -> dict[str, Any]:
    """Draw one world from a frozen generator.

    Returns the observed data an evaluator is allowed to see plus the oracle
    quantities the *evaluator test* uses: per-unit effect, analytic conditional
    means and the design propensity.  A learner never receives these.
    """

    n = spec.n_units
    if spec.scenario_id == "V07":
        return _simulate_heavy_tail(spec, rng, n)

    x1 = rng.integers(0, 2, size=n)
    rng.integers(0, 2, size=n)  # X2 is declared and unused by the effect; drawn to keep
    # the generator's stream identical to the specification.
    z = rng.standard_normal(n)
    linear = 0.8 * (2 * x1 - 1) + 0.5 * z

    if spec.scenario_id in ("V05", "V05B"):
        p0 = 0.001 + 0.008 * _sigmoid(linear)
        tau = np.full(n, 0.0005)
    elif spec.scenario_id in ("V03", "V04"):
        p0 = 0.01 + 0.05 * _sigmoid(linear)
        tau = 0.01 * (2 * x1 - 1)
    elif spec.scenario_id == "V02":
        p0 = 0.01 + 0.05 * _sigmoid(linear)
        tau = np.full(n, 0.005)
    elif spec.scenario_id == "B01":
        p0 = 0.01 + 0.05 * _sigmoid(linear)
        tau = np.full(n, 2 * DELTA_MIN)
    else:  # V01, V06
        p0 = 0.01 + 0.05 * _sigmoid(linear)
        tau = np.zeros(n)

    if spec.scenario_id == "V04":
        propensity = np.where(x1 == 1, 0.8, 0.2)
    elif spec.scenario_id == "V05":
        propensity = np.full(n, 0.9)
    elif spec.scenario_id == "V05B":
        propensity = np.full(n, 0.5)
    else:
        propensity = np.full(n, 0.5)

    cluster = None
    if spec.cluster_size:
        n_clusters = n // spec.cluster_size
        cluster = np.repeat(np.arange(n_clusters), spec.cluster_size)
        # One treatment draw and one outcome shock per cluster: the dependence
        # the IID standard error is supposed to miss.
        cluster_treatment = (rng.random(n_clusters) < 0.5).astype(int)
        treatment = cluster_treatment[cluster]
        shock = rng.random(n_clusters)[cluster]
    else:
        treatment = (rng.random(n) < propensity).astype(int)
        shock = rng.random(n)

    probability = p0 - tau * treatment
    outcome = (shock < probability).astype(float)
    reward = 1.0 - outcome

    action = np.where(treatment == 1, CONTACT, HOLD)
    design = pd.DataFrame({HOLD: 1.0 - propensity, CONTACT: propensity})
    # Analytic conditional means of the reward, per action.
    correct_mean = pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)})

    policy_1 = np.where(x1 == 1, CONTACT, HOLD)
    policy_0 = np.full(n, HOLD)
    finite_truth = float(np.mean((policy_1 != policy_0) * tau))

    return {
        "reward": reward,
        "action": action,
        "design": design,
        "correct_mean": correct_mean,
        "policy_1": policy_1,
        "policy_0": policy_0,
        "cluster": cluster,
        "finite_truth": finite_truth,
        "treatment": treatment,
        "events": float(outcome.sum()),
    }


def _simulate_heavy_tail(spec: ScenarioSpec, rng: np.random.Generator, n: int) -> dict[str, Any]:
    """V07: continuous reward with a t(3) error, scaled to unit variance."""

    x = rng.random(n)
    propensity = np.full(n, 0.5)
    treatment = (rng.random(n) < propensity).astype(int)
    noise = rng.standard_t(3, size=n) / math.sqrt(3.0)
    reward = 1.0 + 0.2 * treatment * (x - 0.5) + noise

    action = np.where(treatment == 1, CONTACT, HOLD)
    design = pd.DataFrame({HOLD: 1.0 - propensity, CONTACT: propensity})
    correct_mean = pd.DataFrame({HOLD: np.ones(n), CONTACT: 1.0 + 0.2 * (x - 0.5)})

    policy_1 = np.where(x > 0.5, CONTACT, HOLD)
    policy_0 = np.full(n, HOLD)
    effect = 0.2 * (x - 0.5)
    finite_truth = float(np.mean((policy_1 != policy_0) * effect))
    return {
        "reward": reward,
        "action": action,
        "design": design,
        "correct_mean": correct_mean,
        "policy_1": policy_1,
        "policy_0": policy_0,
        "cluster": None,
        "finite_truth": finite_truth,
        "treatment": treatment,
        "events": float("nan"),
    }


def _misspecified_mean(
    world: dict[str, Any], spec: ScenarioSpec, rng: np.random.Generator
) -> pd.DataFrame:
    """Intercept-only arm means fitted on an *independent* draw of the design.

    Deliberately wrong -- it ignores X entirely -- but fitted honestly: the
    values come from a separate sample, never from the evaluation data.  With
    a correct propensity the contrast must still be unbiased; that is the
    double-robustness property this mode exists to test.
    """

    training = simulate_world(spec, rng)
    treatment = training["treatment"]
    reward = training["reward"]
    hold_mean = float(reward[treatment == 0].mean()) if (treatment == 0).any() else 0.0
    contact_mean = float(reward[treatment == 1].mean()) if (treatment == 1).any() else 0.0
    n = len(world["reward"])
    return pd.DataFrame({HOLD: np.full(n, hold_mean), CONTACT: np.full(n, contact_mean)})


def _score_shape(scores: pd.DataFrame, world: dict[str, Any]) -> tuple[float, float]:
    """Skewness and excess kurtosis of the per-unit paired score.

    A symmetric interval around a strongly skewed sampling distribution misses
    asymmetrically, so this is the diagnostic that tells an interval failure
    apart from an estimator failure.
    """

    paired = _gather(scores, world["policy_1"]) - _gather(scores, world["policy_0"])
    centred = paired - paired.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return 0.0, 0.0
    skew = float(np.mean(centred**3) / variance**1.5)
    kurtosis = float(np.mean(centred**4) / variance**2 - 3.0)
    return skew, kurtosis


def _score(
    world: dict[str, Any],
    spec: ScenarioSpec,
    mode: EstimatorMode,
    rng: np.random.Generator,
) -> pd.DataFrame:
    if mode == "ipw":
        return ipw_action_scores(world["reward"], world["action"], world["design"])
    nuisance = (
        world["correct_mean"] if mode == "dr_correct" else _misspecified_mean(world, spec, rng)
    )
    return dr_action_scores(world["reward"], world["action"], world["design"], nuisance)


# -- R00: exact identities --------------------------------------------------
@dataclass(frozen=True)
class IdentityResult:
    identity_id: str
    title: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_r00() -> list[IdentityResult]:
    """Six identities that hold exactly, checked to floating-point tolerance."""

    results: list[IdentityResult] = []
    rng = np.random.default_rng(20260921)

    # I1: two identical policies contrast to exactly zero with exactly zero SE.
    n = 400
    scores = pd.DataFrame({HOLD: rng.normal(0, 1, n), CONTACT: rng.normal(0.2, 1, n)})
    policy = np.where(rng.random(n) < 0.5, CONTACT, HOLD)
    same = paired_contrast(scores, policy, policy)
    results.append(
        IdentityResult(
            "I1",
            "Identical policies give a zero contrast and a zero standard error",
            same.delta == 0.0 and same.se == 0.0,
            f"delta={same.delta}, se={same.se}, disagreement units={same.n_disagreement}",
        )
    )

    # I2: no-action against itself is zero, and no imagined cost is subtracted.
    hold_only = np.full(n, HOLD)
    idle = paired_contrast(scores, hold_only, hold_only)
    results.append(
        IdentityResult(
            "I2",
            "A no-action policy against itself is exactly zero, with no phantom cost",
            idle.delta == 0.0 and idle.delta_net == 0.0,
            f"delta={idle.delta}, delta_net={idle.delta_net}",
        )
    )

    # I3: a tiny enumerable multi-arm problem -- DR expectation equals the truth
    # under the actual assignment design, computed by enumerating every
    # assignment rather than sampling.
    truth, estimate = _enumerate_two_arm_expectation()
    results.append(
        IdentityResult(
            "I3",
            "Enumerated tiny design: the DR expectation equals the design truth",
            math.isclose(truth, estimate, rel_tol=0, abs_tol=1e-12),
            f"truth={truth:.15f}, enumerated DR expectation={estimate:.15f}",
        )
    )

    # I4: a constant reward makes the true contrast zero.  DR with a correct
    # constant nuisance is exactly zero in every realisation; IPW is only zero
    # in expectation, so it is checked by enumeration, not by an exact-zero
    # assertion that would be false.
    dr_max, ipw_expectation, ipw_any_nonzero = _constant_reward_identity()
    results.append(
        IdentityResult(
            "I4",
            "Constant reward: DR is exactly zero per realisation, IPW only in expectation",
            dr_max == 0.0 and math.isclose(ipw_expectation, 0.0, abs_tol=1e-12) and ipw_any_nonzero,
            f"max |DR contrast| = {dr_max}; enumerated IPW expectation = "
            f"{ipw_expectation:.2e}; at least one IPW realisation non-zero = {ipw_any_nonzero}",
        )
    )

    # I5: exhaustive tiny allocation -- the cap is feasible and raising cost
    # never raises optimal net value under the same constraints.
    feasible, monotone, detail = _allocation_identity()
    results.append(
        IdentityResult(
            "I5",
            "Exhaustive tiny allocation is feasible and cost-monotone",
            feasible and monotone,
            detail,
        )
    )

    # I6: mapping a binary adverse outcome to reward 1 - Y preserves the sign.
    prevented, reward_uplift = _sign_identity()
    results.append(
        IdentityResult(
            "I6",
            "Prevented-churn and reward (1 - Y) agree in sign and magnitude",
            math.isclose(prevented, reward_uplift, rel_tol=0, abs_tol=1e-12),
            f"prevented churn = {prevented:.15f}, reward uplift = {reward_uplift:.15f}",
        )
    )
    return results


def _enumerate_two_arm_expectation() -> tuple[float, float]:
    """Expectation over every assignment of a four-unit, two-arm design."""

    reward_hold = np.array([1.0, 0.0, 1.0, 1.0])
    reward_contact = np.array([1.0, 1.0, 0.0, 1.0])
    propensity = np.array([0.25, 0.5, 0.75, 0.5])
    mean_hold = np.array([0.9, 0.1, 0.8, 0.7])
    mean_contact = np.array([0.8, 0.9, 0.2, 0.6])
    n = len(reward_hold)

    policy_1 = np.full(n, CONTACT)
    policy_0 = np.full(n, HOLD)
    truth = float(np.mean(reward_contact - reward_hold))

    total = 0.0
    for mask in range(2**n):
        treatment = np.array([(mask >> index) & 1 for index in range(n)])
        probability = float(np.prod(np.where(treatment == 1, propensity, 1.0 - propensity)))
        reward = np.where(treatment == 1, reward_contact, reward_hold)
        design = pd.DataFrame({HOLD: 1.0 - propensity, CONTACT: propensity})
        nuisance = pd.DataFrame({HOLD: mean_hold, CONTACT: mean_contact})
        action = np.where(treatment == 1, CONTACT, HOLD)
        scores = dr_action_scores(reward, action, design, nuisance)
        total += probability * paired_contrast(scores, policy_1, policy_0).delta
    return truth, total


def _constant_reward_identity() -> tuple[float, float, bool]:
    constant = 3.5
    n = 6
    propensity = np.full(n, 0.4)
    design = pd.DataFrame({HOLD: 1.0 - propensity, CONTACT: propensity})
    nuisance = pd.DataFrame({HOLD: np.full(n, constant), CONTACT: np.full(n, constant)})
    policy_1 = np.full(n, CONTACT)
    policy_0 = np.full(n, HOLD)

    dr_max = 0.0
    ipw_expectation = 0.0
    ipw_nonzero = False
    for mask in range(2**n):
        treatment = np.array([(mask >> index) & 1 for index in range(n)])
        probability = float(np.prod(np.where(treatment == 1, propensity, 1.0 - propensity)))
        action = np.where(treatment == 1, CONTACT, HOLD)
        reward = np.full(n, constant)
        dr = paired_contrast(
            dr_action_scores(reward, action, design, nuisance), policy_1, policy_0
        ).delta
        dr_max = max(dr_max, abs(dr))
        ipw = paired_contrast(ipw_action_scores(reward, action, design), policy_1, policy_0).delta
        ipw_expectation += probability * ipw
        ipw_nonzero = ipw_nonzero or abs(ipw) > 1e-9
    return dr_max, ipw_expectation, ipw_nonzero


def _allocation_identity() -> tuple[bool, bool, str]:
    """Enumerate every subset of a tiny cohort under a hard cap."""

    value = np.array([0.9, 0.4, 0.25, 0.1, 0.05])
    n = len(value)
    cap = capacity_limit(n, 0.4)  # floor(0.4 * 5) = 2
    best_by_cost = {}
    for cost in (0.0, 0.2, 0.5):
        best = -math.inf
        for mask in range(2**n):
            chosen = [index for index in range(n) if (mask >> index) & 1]
            if len(chosen) > cap:
                continue
            best = max(best, float(sum(value[index] - cost for index in chosen)))
        best_by_cost[cost] = best
    feasible = cap == 2 and best_by_cost[0.0] == value[0] + value[1]
    costs = sorted(best_by_cost)
    monotone = all(
        best_by_cost[low] >= best_by_cost[high] - 1e-12 for low, high in itertools.pairwise(costs)
    )
    detail = f"cap={cap}, optimal net value by unit cost: " + ", ".join(
        f"{cost:g}->{best_by_cost[cost]:.4f}" for cost in costs
    )
    return feasible, monotone, detail


def _sign_identity() -> tuple[float, float]:
    outcome = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    treatment = np.array([0, 0, 0, 1, 1, 1])
    prevented = float(outcome[treatment == 0].mean() - outcome[treatment == 1].mean())
    reward = 1.0 - outcome
    reward_uplift = float(reward[treatment == 1].mean() - reward[treatment == 0].mean())
    return prevented, reward_uplift


# -- R01: scenario validation ----------------------------------------------
@dataclass
class ModeSummary:
    scenario_id: str
    mode: str
    variant: str
    worlds: int
    true_contrast: float
    mean_finite_truth: float
    bias_vs_population: float
    bias_vs_finite_frame: float
    mc_se: float
    rmse: float
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    miss_below: float
    miss_above: float
    mean_ci_width: float
    promotion_rate: float
    promotion_ci_high: float
    mean_events: float
    mean_score_skewness: float = float("nan")
    mean_score_excess_kurtosis: float = float("nan")
    width_ratio: float = float("nan")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidityReport:
    worlds: int
    seed: int
    started_at: str
    interval_method: str = "normal"
    identities: list[IdentityResult] = field(default_factory=list)
    summaries: list[ModeSummary] = field(default_factory=list)
    scenarios_run: list[str] = field(default_factory=list)
    scenarios_declared: list[str] = field(default_factory=list)
    runtime_seconds: float = 0.0

    # -- gates -------------------------------------------------------------
    def coverage_failures(self) -> list[ModeSummary]:
        """Modes whose coverage lower bound misses the engineering tolerance.

        The IID variant of the clustered scenario is a declared negative
        control: it is *supposed* to under-cover, so it is scored but never
        counted as a gate failure.
        """

        return [
            summary
            for summary in self.summaries
            if not summary.variant.endswith("negative_control")
            and summary.coverage_ci_low < COVERAGE_LOWER_BOUND
        ]

    def promotion_failures(self) -> list[ModeSummary]:
        return [
            summary
            for summary in self.summaries
            if _BY_ID[summary.scenario_id].is_null
            and not summary.variant.endswith("negative_control")
            and summary.promotion_ci_high > FALSE_PROMOTION_UPPER_BOUND
        ]

    @property
    def identities_passed(self) -> bool:
        return all(result.passed for result in self.identities)

    @property
    def negative_controls_detected(self) -> list[str]:
        """Negative controls must actually misbehave, or they prove nothing."""

        detected = []
        for summary in self.summaries:
            if summary.variant == "iid_negative_control" and (
                summary.coverage_ci_high < NOMINAL_COVERAGE
            ):
                detected.append(f"{summary.scenario_id}:{summary.variant}:undercovers")
            if (
                summary.variant == "ipw_constant_propensity_negative_control"
                and abs(summary.bias_vs_finite_frame) > 3 * summary.mc_se
            ):
                detected.append(f"{summary.scenario_id}:{summary.variant}:biased")
        return detected

    @property
    def family_false_failure_rate(self) -> float:
        """How often a *perfect* estimator would fail this gate by chance.

        The rule is pointwise -- every readout must show a Wilson lower bound
        at or above the tolerance -- and it is applied to every readout in the
        run.  With enough readouts and few enough worlds, that is close to a
        coin flip even when nothing is wrong.  MASTER_PLAN §4.4 anticipated
        this ("pointwise bounds không hỗ trợ câu đó"); reporting the number
        turns the warning into something a reader can act on.
        """

        readouts = [
            item for item in self.summaries if not item.variant.endswith("negative_control")
        ]
        if not readouts or self.worlds < 2:
            return float("nan")
        # Largest success count whose Wilson lower bound still misses the bar.
        boundary = -1
        for successes in range(self.worlds + 1):
            if _wilson(successes, self.worlds)[0] >= COVERAGE_LOWER_BOUND:
                boundary = successes - 1
                break
        if boundary < 0:
            return 0.0
        per_readout = float(stats.binom.cdf(boundary, self.worlds, NOMINAL_COVERAGE))
        return float(1.0 - (1.0 - per_readout) ** len(readouts))

    def validated_design_region(self) -> dict[str, Any]:
        """Where the evaluator demonstrably works, read off this run.

        A gate that only says FAIL tells a caller nothing about whether their
        own design is affected.  This reports the widest propensity imbalance
        and the lowest event rate among scenarios whose every primary readout
        cleared the bar, plus the ones that did not, so a study can check
        itself against measured ground rather than against a promise.
        """

        failing = {item.scenario_id for item in self.coverage_failures()}
        passed = [
            spec
            for spec in SCENARIOS
            if spec.scenario_id in self.scenarios_run and spec.scenario_id not in failing
        ]
        failed = [
            spec
            for spec in SCENARIOS
            if spec.scenario_id in self.scenarios_run and spec.scenario_id in failing
        ]
        return {
            "validated_scenarios": [spec.scenario_id for spec in passed],
            "failing_scenarios": [spec.scenario_id for spec in failed],
            "max_propensity_imbalance_validated": (
                max((spec.max_propensity_imbalance for spec in passed), default=0.0)
            ),
            "min_event_rate_validated": (
                min((spec.min_event_rate for spec in passed), default=float("nan"))
            ),
            "smallest_failing_imbalance": (
                min((spec.max_propensity_imbalance for spec in failed), default=float("inf"))
            ),
            "note": (
                "A study whose design sits inside the validated region may use this "
                "evaluator; one outside it may not, and saying so is the point of "
                "reporting the region rather than only the verdict."
            ),
        }

    def marginal_failures(self) -> list[ModeSummary]:
        """Failures close enough to the bar to be indistinguishable from noise."""

        return [
            item
            for item in self.coverage_failures()
            if item.coverage
            >= NOMINAL_COVERAGE
            - 3.0 * math.sqrt(NOMINAL_COVERAGE * (1 - NOMINAL_COVERAGE) / max(self.worlds, 1))
        ]

    def decisive_failures(self) -> list[ModeSummary]:
        marginal = {id(item) for item in self.marginal_failures()}
        return [item for item in self.coverage_failures() if id(item) not in marginal]

    @property
    def gate_passed(self) -> bool:
        return (
            self.identities_passed
            and not self.coverage_failures()
            and not self.promotion_failures()
            and self.worlds >= 1_000
        )

    @property
    def status(self) -> str:
        if not self.gate_passed:
            return "FAIL" if self.worlds >= 1_000 else "SMOKE_ONLY"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "gate_passed": self.gate_passed,
            "worlds_per_scenario": self.worlds,
            "seed": self.seed,
            "interval_method": self.interval_method,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "thresholds": {
                "coverage_lower_wilson_at_least": COVERAGE_LOWER_BOUND,
                "false_promotion_upper_wilson_at_most": FALSE_PROMOTION_UPPER_BOUND,
                "nominal_coverage": NOMINAL_COVERAGE,
                "worlds_required_per_scenario": 1_000,
            },
            "r00_identities_passed": self.identities_passed,
            "r00_identities": [result.to_dict() for result in self.identities],
            "scenarios_declared": self.scenarios_declared,
            "scenarios_run": self.scenarios_run,
            "scenario_specs": [
                spec.to_dict() for spec in SCENARIOS if spec.scenario_id in self.scenarios_run
            ],
            "coverage_failures": [
                f"{item.scenario_id}:{item.mode}:{item.variant}"
                for item in self.coverage_failures()
            ],
            "decisive_failures": [
                f"{item.scenario_id}:{item.mode}:{item.variant}"
                for item in self.decisive_failures()
            ],
            "marginal_failures": [
                f"{item.scenario_id}:{item.mode}:{item.variant}"
                for item in self.marginal_failures()
            ],
            "family_false_failure_rate": self.family_false_failure_rate,
            "promotion_failures": [
                f"{item.scenario_id}:{item.mode}" for item in self.promotion_failures()
            ],
            "negative_controls_detected": self.negative_controls_detected,
            "validated_design_region": self.validated_design_region(),
            "not_run": {
                "V08_batch_cap": "blocked on G06: the batch-policy interval has no validated "
                "domain yet, so there is nothing to score it against",
                "V09_two_stage_recruitment": "runs separately once the recruitment estimator "
                "has a declared target; the variance decomposition exists but its gate does not",
            },
            "summaries": [summary.to_dict() for summary in self.summaries],
        }


def _empty_bucket() -> dict[str, list[float]]:
    return {
        "estimate": [],
        "low": [],
        "high": [],
        "truth": [],
        "events": [],
        "skewness": [],
        "kurtosis": [],
    }


def _summarise(
    spec: ScenarioSpec,
    mode: str,
    variant: str,
    estimates: list[float],
    lows: list[float],
    highs: list[float],
    truths: list[float],
    events: list[float],
    skewness: list[float],
    kurtosis: list[float],
) -> ModeSummary:
    estimate = np.asarray(estimates, dtype=float)
    low = np.asarray(lows, dtype=float)
    high = np.asarray(highs, dtype=float)
    truth = np.asarray(truths, dtype=float)
    worlds = len(estimate)
    # The width the observed spread of estimates would need for nominal
    # coverage.  A ratio below one means the interval is too narrow, which is
    # what separates "the estimator is biased" from "the interval is wrong".
    spread = float(estimate.std(ddof=1))
    required_width = 2 * 1.959963984540054 * spread
    covered = int(np.sum((low <= truth) & (truth <= high)))
    # Which side the interval misses on separates "too narrow" from "shifted":
    # a symmetric miss asks for width, a one-sided miss asks for skew.
    below = int(np.sum(truth < low))
    above = int(np.sum(truth > high))
    promoted = int(np.sum(low > 0.0))
    coverage_low, coverage_high = _wilson(covered, worlds)
    _, promotion_high = _wilson(promoted, worlds)
    finite = np.isfinite(high - low)
    return ModeSummary(
        scenario_id=spec.scenario_id,
        mode=mode,
        variant=variant,
        worlds=worlds,
        true_contrast=spec.true_contrast,
        mean_finite_truth=float(truth.mean()),
        bias_vs_population=float(estimate.mean() - spec.true_contrast),
        bias_vs_finite_frame=float((estimate - truth).mean()),
        mc_se=float(estimate.std(ddof=1) / math.sqrt(worlds)),
        rmse=float(np.sqrt(np.mean((estimate - truth) ** 2))),
        coverage=covered / worlds,
        coverage_ci_low=coverage_low,
        coverage_ci_high=coverage_high,
        miss_below=below / worlds,
        miss_above=above / worlds,
        mean_ci_width=float(np.mean((high - low)[finite])) if finite.any() else float("nan"),
        promotion_rate=promoted / worlds,
        promotion_ci_high=promotion_high,
        mean_events=float(np.nanmean(events)) if events else float("nan"),
        mean_score_skewness=float(np.mean(skewness)) if skewness else float("nan"),
        mean_score_excess_kurtosis=float(np.mean(kurtosis)) if kurtosis else float("nan"),
        width_ratio=(
            float(np.mean((high - low)[finite]) / required_width)
            if finite.any() and required_width > 0
            else float("nan")
        ),
    )


def run_r01(
    *,
    worlds: int = 1_000,
    seed: int = 20260921,
    scenarios: Sequence[str] | None = None,
    include_identities: bool = True,
    interval_method: str = "normal",
    bootstrap_resamples: int = 999,
    n_units: int | None = None,
    effective_df_floor: float = 30.0,
) -> ValidityReport:
    """Score every declared scenario through the real evaluator code path."""

    wanted = list(scenarios) if scenarios else [spec.scenario_id for spec in SCENARIOS]
    unknown = [name for name in wanted if name not in _BY_ID]
    if unknown:
        raise ValueError(f"unknown scenario(s) {unknown}; declared: {sorted(_BY_ID)}")

    started = time.perf_counter()
    report = ValidityReport(
        worlds=worlds,
        seed=seed,
        interval_method=interval_method,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        scenarios_declared=[spec.scenario_id for spec in SCENARIOS],
        scenarios_run=wanted,
    )
    if include_identities:
        report.identities = run_r00()

    for scenario_id in wanted:
        spec = _BY_ID[scenario_id]
        if n_units is not None:
            # A declared sample-size sweep: the mechanism is unchanged, only
            # the cohort size, so the boundary it finds is about size alone.
            spec = replace(spec, n_units=n_units)
        # The seed namespace is keyed on the scenario *identity*, not on its
        # position in the requested list.  Keying on position meant that
        # `--scenarios V03` and a full run drew different worlds for V03, so
        # two runs of the same scenario were not comparable -- which defeats
        # the point of a frozen generator.
        namespace = _scenario_namespace(spec.scenario_id)
        collected: dict[tuple[str, str], dict[str, list[float]]] = {}
        for world_index in range(worlds):
            rng = np.random.default_rng([seed, namespace, world_index])
            world = simulate_world(spec, rng)
            for mode in MODES:
                scores = _score(world, spec, mode, rng)
                variants: list[tuple[str, Any]] = [("primary", world["cluster"])]
                if spec.cluster_size:
                    variants = [
                        ("cluster_robust", world["cluster"]),
                        ("iid_negative_control", None),
                    ]
                for variant, cluster in variants:
                    # The skewness expansion is derived for independent units,
                    # so a clustered readout falls back to the studentized
                    # bootstrap rather than silently using the wrong formula.
                    method = interval_method
                    if cluster is not None and interval_method.startswith("skewness_adjusted"):
                        method = "bootstrap_t"
                    contrast = paired_contrast(
                        scores,
                        world["policy_1"],
                        world["policy_0"],
                        cluster=cluster,
                        interval_method=method,
                        bootstrap_resamples=bootstrap_resamples,
                        bootstrap_seed=seed + world_index,
                        effective_df_floor=effective_df_floor,
                    )
                    bucket = collected.setdefault((mode, variant), _empty_bucket())
                    bucket["estimate"].append(contrast.delta)
                    bucket["low"].append(contrast.ci_low)
                    bucket["high"].append(contrast.ci_high)
                    bucket["truth"].append(world["finite_truth"])
                    bucket["events"].append(world["events"])
                    skew, kurtosis = _score_shape(scores, world)
                    bucket["skewness"].append(skew)
                    bucket["kurtosis"].append(kurtosis)

            if spec.scenario_id == "V04":
                # Negative control: replace the known stratum-varying design
                # probability with the observed treatment share.  Two readouts,
                # because they answer different questions.  IPW has nothing to
                # fall back on and must break; DR with a correct outcome model
                # should survive, which is double robustness doing its job and
                # is worth measuring rather than assuming.
                share = float(world["treatment"].mean())
                constant = pd.DataFrame(
                    {
                        HOLD: np.full(spec.n_units, 1.0 - share),
                        CONTACT: np.full(spec.n_units, share),
                    }
                )
                broken = {
                    "ipw_constant_propensity_negative_control": ipw_action_scores(
                        world["reward"], world["action"], constant
                    ),
                    "dr_constant_propensity_negative_control": dr_action_scores(
                        world["reward"], world["action"], constant, world["correct_mean"]
                    ),
                }
                for variant, scores in broken.items():
                    contrast = paired_contrast(scores, world["policy_1"], world["policy_0"])
                    bucket = collected.setdefault(("wrong_propensity", variant), _empty_bucket())
                    bucket["estimate"].append(contrast.delta)
                    bucket["low"].append(contrast.ci_low)
                    bucket["high"].append(contrast.ci_high)
                    bucket["truth"].append(world["finite_truth"])
                    bucket["events"].append(world["events"])
                    skew, kurtosis = _score_shape(scores, world)
                    bucket["skewness"].append(skew)
                    bucket["kurtosis"].append(kurtosis)

        for (mode, variant), bucket in collected.items():
            report.summaries.append(
                _summarise(
                    spec,
                    mode,
                    variant,
                    bucket["estimate"],
                    bucket["low"],
                    bucket["high"],
                    bucket["truth"],
                    bucket["events"],
                    bucket["skewness"],
                    bucket["kurtosis"],
                )
            )

    report.runtime_seconds = time.perf_counter() - started
    return report


# -- reporting --------------------------------------------------------------
def render_markdown(report: ValidityReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R00 / R01 — exact identities and evaluator validation",
        "",
        f"Run {report.started_at} · {report.worlds:,} worlds per scenario · seed {report.seed} · "
        f"{report.runtime_seconds:.0f} s.",
        "",
        f"- status: **{report.status}**",
        f"- R00 identities: {'all pass' if report.identities_passed else 'FAILED'}",
        f"- coverage failures: {len(report.coverage_failures())}",
        f"- false-promotion failures: {len(report.promotion_failures())}",
        f"- negative controls that misbehaved as intended: "
        f"{', '.join(report.negative_controls_detected) or 'none'}",
        "",
        "Coverage is scored against the finite-frame truth (the conditional value on the "
        "realised X); bias is reported against both that and the analytic population value. "
        "A gate pass means the evaluator is sound on these declared mechanisms, not on every "
        "mechanism.",
        "",
        "## R00 — exact identities",
        "",
        "| ID | Identity | Result | Evidence |",
        "|---|---|---|---|",
    ]
    for identity in report.identities:
        lines.append(
            f"| {identity.identity_id} | {identity.title} | "
            f"{'pass' if identity.passed else 'FAIL'} | {identity.detail} |"
        )

    lines.extend(
        [
            "",
            "## R01 — scenarios",
            "",
            "| Scenario | Mechanism | Detects |",
            "|---|---|---|",
        ]
    )
    for spec in SCENARIOS:
        if spec.scenario_id in report.scenarios_run:
            lines.append(
                f"| {spec.scenario_id} | {spec.title}; {spec.propensity}; {spec.effect} "
                f"| {spec.detects} |"
            )

    lines.extend(
        [
            "",
            "### Readouts",
            "",
            "| Scenario | Estimator | Variant | Truth | Bias | MCSE | Coverage | Wilson 95% "
            "| CI width | Width ratio | Score skew | Promotion |",
            "|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|",
        ]
    )
    for summary in report.summaries:
        lines.append(
            f"| {summary.scenario_id} | {summary.mode} | {summary.variant} "
            f"| {summary.true_contrast:.5f} | {summary.bias_vs_finite_frame:+.6f} "
            f"| {summary.mc_se:.6f} | {summary.coverage:.3f} "
            f"| [{summary.coverage_ci_low:.3f}, {summary.coverage_ci_high:.3f}] "
            f"| {summary.mean_ci_width:.5f} | {summary.width_ratio:.3f} "
            f"| {summary.mean_score_skewness:.2f} | {summary.promotion_rate:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Not run",
            "",
        ]
    )
    for key, reason in payload["not_run"].items():
        lines.append(f"- **{key}** — {reason}")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=1_000)
    parser.add_argument(
        "--interval-method",
        default="normal",
        choices=("normal", "skewness_adjusted", "skewness_adjusted_t", "bootstrap_t"),
        help="interval construction to score; the default is the published one",
    )
    parser.add_argument("--bootstrap-resamples", type=int, default=999)
    parser.add_argument(
        "--effective-df-floor",
        type=float,
        default=30.0,
        help="floor on the kurtosis-based effective df; 1 disables the floor",
    )
    parser.add_argument(
        "--n-units",
        type=int,
        default=None,
        help="override the cohort size for a declared sample-size sweep",
    )
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--scenarios", nargs="*", default=None)
    parser.add_argument("--output-dir", default="reports/v4/validity")
    parser.add_argument(
        "--skip-identities", action="store_true", help="run R01 only (R00 is cheap; rarely useful)"
    )
    args = parser.parse_args(argv)

    report = run_r01(
        worlds=args.worlds,
        seed=args.seed,
        scenarios=args.scenarios,
        include_identities=not args.skip_identities,
        interval_method=args.interval_method,
        bootstrap_resamples=args.bootstrap_resamples,
        n_units=args.n_units,
        effective_df_floor=args.effective_df_floor,
    )
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "validity_suite.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "VALIDITY_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for identity in report.identities:
        print(f"[{'ok  ' if identity.passed else 'FAIL'}] {identity.identity_id} {identity.title}")
    undersized = report.worlds < 1_000
    for summary in report.summaries:
        if summary.variant.endswith("negative_control"):
            flag = "ctrl"
        elif summary.coverage_ci_low >= COVERAGE_LOWER_BOUND:
            flag = "ok  "
        else:
            # Below the declared size the Wilson bound is wide by construction,
            # so a miss is a sample-size artefact, not a gate failure.
            flag = "thin" if undersized else "FAIL"
        print(
            f"[{flag}] {summary.scenario_id} {summary.mode:<16} {summary.variant:<34} "
            f"bias {summary.bias_vs_finite_frame:+.6f} (MCSE {summary.mc_se:.6f}) "
            f"coverage {summary.coverage:.3f} "
            f"[{summary.coverage_ci_low:.3f}, {summary.coverage_ci_high:.3f}] "
            f"miss {summary.miss_below:.3f}/{summary.miss_above:.3f} "
            f"promotion {summary.promotion_rate:.3f}"
        )
    rate = report.family_false_failure_rate
    print(
        f"gate self-noise: a perfect estimator fails this run {rate:.1%} of the time "
        f"({len([s for s in report.summaries if not s.variant.endswith('negative_control')])} "
        f"readouts x {report.worlds} worlds)"
    )
    if report.decisive_failures():
        print(
            "decisive failures:", [f"{i.scenario_id}:{i.mode}" for i in report.decisive_failures()]
        )
    if report.marginal_failures():
        print(
            "marginal (within 3 MCSE of nominal):",
            [f"{i.scenario_id}:{i.mode}" for i in report.marginal_failures()],
        )
    print(
        f"status={report.status} worlds={report.worlds} "
        f"runtime={report.runtime_seconds:.0f}s coverage_failures="
        f"{len(report.coverage_failures())} promotion_failures={len(report.promotion_failures())}"
    )
    print(f"Report: {destination}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
