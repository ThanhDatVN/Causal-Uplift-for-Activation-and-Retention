"""Fixed-policy inference smoke over known-truth worlds (session 10).

This is the second tier of the E28 statistical challenge suite -- fixed
policies, a known design propensity and an analytically known contrast -- run at
*smoke* size.  It answers three questions before any expensive study is opened:

1. Is the paired contrast unbiased for the truth it claims to estimate?
2. Do its intervals cover at roughly the nominal rate?
3. How much does one world cost, and what would a real coverage run cost?

What it is **not**: a coverage gate.  The V3/V4 protocol asks for at least 1000
replications per canonical scenario before a false-promotion rate is scored, and
100 worlds cannot resolve 95% coverage -- the Monte Carlo error alone is about
2 points.  The report therefore prints the Wilson interval around the empirical
coverage and the projected budget for a gate-sized run, and says so.

The data-generating process is deliberately simple and fully specified:

* ``X ~ Uniform(0, 1)``;
* the design assigns ``contact`` with probability 0.3 when ``X <= 0.5`` and 0.7
  otherwise, so a constant propensity would be wrong;
* ``E[R(hold) | X] = 1``, ``E[R(contact) | X] = 1 + 0.6 (X - 0.5)``;
* ``pi0`` always holds, ``pi1`` contacts when ``X > 0.5``.

The contrast is then ``E[0.6 (X - 0.5) 1{X > 0.5}] = 0.075`` exactly.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .policy_comparison import dr_action_scores, paired_contrast, unpaired_contrast

__all__ = ["TRUE_CONTRAST", "SmokeResult", "main", "run_smoke", "simulate_world"]

HOLD = "hold"
CONTACT = "contact"
ACTIONS = (HOLD, CONTACT)

#: Analytic value of the contrast under the documented data-generating process.
TRUE_CONTRAST = 0.075

_EFFECT_SLOPE = 0.6
_BASE_REWARD = 1.0
_NOISE_SD = 1.0


def _mu(covariate: np.ndarray, action: str) -> np.ndarray:
    if action == HOLD:
        return np.full_like(covariate, _BASE_REWARD)
    return _BASE_REWARD + _EFFECT_SLOPE * (covariate - 0.5)


def _design_propensity(covariate: np.ndarray) -> np.ndarray:
    """Probability of ``contact``; deliberately not constant in ``X``."""

    return np.where(covariate <= 0.5, 0.3, 0.7)


def simulate_world(
    n: int, rng: np.random.Generator, *, misspecify_outcome: bool = False
) -> dict[str, Any]:
    """One randomized world plus the two frozen policies evaluated on it."""

    covariate = rng.uniform(0.0, 1.0, n)
    contact_probability = _design_propensity(covariate)
    contacted = rng.uniform(0.0, 1.0, n) < contact_probability
    action = np.where(contacted, CONTACT, HOLD)

    mean_reward = np.where(contacted, _mu(covariate, CONTACT), _mu(covariate, HOLD))
    reward = mean_reward + rng.normal(0.0, _NOISE_SD, n)

    propensity = pd.DataFrame({HOLD: 1.0 - contact_probability, CONTACT: contact_probability})
    if misspecify_outcome:
        # A constant outcome model: doubly robust estimation should still be
        # unbiased because the design propensity is known exactly.
        predicted = pd.DataFrame(
            {HOLD: np.full(n, _BASE_REWARD), CONTACT: np.full(n, _BASE_REWARD)}
        )
    else:
        predicted = pd.DataFrame({HOLD: _mu(covariate, HOLD), CONTACT: _mu(covariate, CONTACT)})

    scores = dr_action_scores(reward, action, propensity, predicted)
    policy_0 = [HOLD] * n
    policy_1 = [CONTACT if value > 0.5 else HOLD for value in covariate]
    return {"scores": scores, "policy_0": policy_0, "policy_1": policy_1}


@dataclass(frozen=True)
class SmokeResult:
    estimator: str
    worlds: int
    n_per_world: int
    alpha: float
    bias: float
    bias_mc_se: float
    rmse: float
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    mean_ci_width: float
    mean_se: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimator": self.estimator,
            "worlds": self.worlds,
            "n_per_world": self.n_per_world,
            "alpha": self.alpha,
            "true_contrast": TRUE_CONTRAST,
            "bias": self.bias,
            "bias_mc_se": self.bias_mc_se,
            "bias_within_2_mc_se": bool(abs(self.bias) <= 2 * self.bias_mc_se),
            "rmse": self.rmse,
            "coverage": self.coverage,
            "coverage_ci_low": self.coverage_ci_low,
            "coverage_ci_high": self.coverage_ci_high,
            "nominal_inside_coverage_ci": bool(
                self.coverage_ci_low <= 1 - self.alpha <= self.coverage_ci_high
            ),
            "mean_ci_width": self.mean_ci_width,
            "mean_se": self.mean_se,
        }


def _wilson(successes: int, trials: int, *, confidence: float = 0.95) -> tuple[float, float]:
    if trials == 0:
        return float("nan"), float("nan")
    z = float(stats.norm.ppf(0.5 + confidence / 2))
    phat = successes / trials
    denominator = 1 + z**2 / trials
    centre = (phat + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt(phat * (1 - phat) / trials + z**2 / (4 * trials**2)) / denominator
    return float(centre - margin), float(centre + margin)


def _summarise(
    estimator: str,
    deltas: list[float],
    lows: list[float],
    highs: list[float],
    ses: list[float],
    *,
    n_per_world: int,
    alpha: float,
) -> SmokeResult:
    delta_array = np.asarray(deltas, dtype=float)
    worlds = len(delta_array)
    errors = delta_array - TRUE_CONTRAST
    covered = sum(1 for low, high in zip(lows, highs, strict=True) if low <= TRUE_CONTRAST <= high)
    coverage_low, coverage_high = _wilson(covered, worlds)
    return SmokeResult(
        estimator=estimator,
        worlds=worlds,
        n_per_world=n_per_world,
        alpha=alpha,
        bias=float(errors.mean()),
        bias_mc_se=float(delta_array.std(ddof=1) / np.sqrt(worlds)) if worlds > 1 else float("nan"),
        rmse=float(np.sqrt(np.square(errors).mean())),
        coverage=covered / worlds if worlds else float("nan"),
        coverage_ci_low=coverage_low,
        coverage_ci_high=coverage_high,
        mean_ci_width=float(np.mean(np.asarray(highs) - np.asarray(lows))),
        mean_se=float(np.mean(ses)),
    )


def run_smoke(
    *,
    worlds: int = 100,
    n_per_world: int = 2000,
    seed: int = 20260920,
    alpha: float = 0.05,
    misspecify_outcome: bool = False,
) -> dict[str, Any]:
    """Run the smoke and return both estimators' summaries plus a cost projection."""

    rng = np.random.default_rng(seed)
    paired: dict[str, list[float]] = {"delta": [], "low": [], "high": [], "se": []}
    unpaired: dict[str, list[float]] = {"delta": [], "low": [], "high": [], "se": []}

    started = time.perf_counter()
    for _ in range(worlds):
        world = simulate_world(n_per_world, rng, misspecify_outcome=misspecify_outcome)
        for store, contrast in (
            (
                paired,
                paired_contrast(world["scores"], world["policy_1"], world["policy_0"], alpha=alpha),
            ),
            (
                unpaired,
                unpaired_contrast(
                    world["scores"], world["policy_1"], world["policy_0"], alpha=alpha
                ),
            ),
        ):
            store["delta"].append(contrast.delta)
            store["low"].append(contrast.ci_low)
            store["high"].append(contrast.ci_high)
            store["se"].append(contrast.se)
    elapsed = time.perf_counter() - started

    paired_result = _summarise(
        "paired_dr",
        paired["delta"],
        paired["low"],
        paired["high"],
        paired["se"],
        n_per_world=n_per_world,
        alpha=alpha,
    )
    unpaired_result = _summarise(
        "unpaired_diagnostic",
        unpaired["delta"],
        unpaired["low"],
        unpaired["high"],
        unpaired["se"],
        n_per_world=n_per_world,
        alpha=alpha,
    )
    per_world = elapsed / worlds if worlds else float("nan")
    variance_ratio = (
        (unpaired_result.mean_se / paired_result.mean_se) ** 2
        if paired_result.mean_se
        else float("inf")
    )
    return {
        "status": "SMOKE_ONLY",
        "note": (
            "One canonical scenario, fixed policies, correct design propensity. The "
            "V3/V4 coverage gate scores every canonical scenario (null, constant "
            "effect, heterogeneous, non-constant propensity, rare outcomes, clustered, "
            "heavy-tailed) and the full selection pipeline; neither is exercised here, "
            "so no false-promotion rate may be read off this run."
        ),
        "scenarios_covered": ["heterogeneous_effect_stratified_propensity"],
        "scenarios_required_for_gate": [
            "null",
            "constant_effect",
            "heterogeneous_effect",
            "non_constant_known_propensity",
            "rare_outcome",
            "clustered_outcome",
            "heavy_tailed_finite_variance",
            "full_selection_pipeline",
        ],
        "config": {
            "worlds": worlds,
            "n_per_world": n_per_world,
            "seed": seed,
            "alpha": alpha,
            "misspecified_outcome_model": misspecify_outcome,
            "known_design_propensity": True,
        },
        "true_contrast": TRUE_CONTRAST,
        "paired": paired_result.to_dict(),
        "unpaired": unpaired_result.to_dict(),
        "se_variance_ratio_unpaired_over_paired": variance_ratio,
        "budget": {
            "elapsed_s": round(elapsed, 3),
            "seconds_per_world": round(per_world, 4),
            "projected_seconds_for_1000_worlds": round(per_world * 1000, 1),
            "projection_caveat": (
                "Linear extrapolation from one setting; a gate run also refits "
                "nuisance models, which this smoke does not."
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=100)
    parser.add_argument("--n-per-world", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument(
        "--misspecify-outcome",
        action="store_true",
        help="use a constant outcome model to exercise the doubly robust property",
    )
    parser.add_argument("--output", default="reports/v4/inference_smoke.json")
    args = parser.parse_args(argv)

    report = run_smoke(
        worlds=args.worlds,
        n_per_world=args.n_per_world,
        seed=args.seed,
        alpha=args.alpha,
        misspecify_outcome=args.misspecify_outcome,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for key in ("paired", "unpaired"):
        row = report[key]
        print(
            f"{row['estimator']:<20} bias {row['bias']:+.5f} "
            f"(MCSE {row['bias_mc_se']:.5f})  coverage {row['coverage']:.2%} "
            f"[{row['coverage_ci_low']:.2%}, {row['coverage_ci_high']:.2%}]  "
            f"mean CI width {row['mean_ci_width']:.4f}"
        )
    print(
        f"pairing cuts the sampling variance by "
        f"{report['se_variance_ratio_unpaired_over_paired']:.1f}x"
    )
    print(
        f"{report['budget']['seconds_per_world']:.3f}s per world; a 1000-world run "
        f"projects to {report['budget']['projected_seconds_for_1000_worlds']:.0f}s"
    )
    print(f"status={report['status']}: {report['note']}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
