"""Frozen, independent-family stress tests for the selected policy interval.

This uses the production paired contrast and DR score implementation, but a
generator distinct from validity_suite. A smoke run cannot promote evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom

from .policy_comparison import dr_action_scores, paired_contrast
from .validity_suite import _wilson

METHOD = "skewness_adjusted_t"
EFFECTIVE_DF_FLOOR = 1.0
SEED = 40637
NOMINAL_COVERAGE = 0.95
COVERAGE_WILSON_FLOOR = 0.92
FALSE_PROMOTION_WILSON_CEILING = 0.05


@dataclass(frozen=True)
class FreshScenario:
    name: str
    family: str
    assignment: str
    effect: str


SCENARIOS = (
    FreshScenario("F01_null_imbalanced", "smooth", "constant_085", "zero"),
    FreshScenario("F02_effect_imbalanced", "smooth", "constant_085", "heterogeneous"),
    FreshScenario("F03_effect_variable", "smooth", "variable", "heterogeneous"),
    FreshScenario("F04_piecewise_null", "piecewise", "stratified", "zero"),
    FreshScenario("F05_piecewise_harm_constant", "piecewise", "constant_085", "piecewise_harm"),
    FreshScenario("F06_piecewise_harm_stratified", "piecewise", "stratified", "piecewise_harm"),
)


def draw_world(
    scenario: FreshScenario, *, n_units: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame, np.ndarray, float]:
    """Generate smooth or piecewise risks with known policy-value truth."""

    if scenario.family == "smooth":
        x = rng.normal(size=n_units)
        baseline_churn = 1 / (1 + np.exp(-(-4.7 + 0.8 * x + 0.2 * x**2)))
        effect = np.zeros(n_units) if scenario.effect == "zero" else 0.006 / (1 + np.exp(-x))
        propensity = (
            np.full(n_units, 0.85)
            if scenario.assignment == "constant_085"
            else 0.1 + 0.8 / (1 + np.exp(-1.2 * x))
        )
    elif scenario.family == "piecewise":
        x = rng.uniform(-1, 1, size=n_units)
        baseline_churn = np.select(
            [x < -0.3, x < 0.3, x < 0.75],
            [0.003, 0.008, 0.025],
            default=0.060,
        )
        effect = (
            np.zeros(n_units)
            if scenario.effect == "zero"
            else np.select([x <= 0, x < 0.5], [0.0, -0.003], default=0.008)
        )
        propensity = (
            np.full(n_units, 0.85)
            if scenario.assignment == "constant_085"
            else np.where(x < 0, 0.12, 0.88)
        )
    else:
        raise ValueError(f"unknown generator family {scenario.family}")
    treated = rng.random(n_units) < propensity
    churn = rng.random(n_units) < baseline_churn - treated * effect
    reward = 1.0 - churn.astype(float)
    action = np.where(treated, "contact", "hold")
    design = pd.DataFrame({"hold": 1 - propensity, "contact": propensity})
    means = pd.DataFrame({"hold": 1 - baseline_churn, "contact": 1 - baseline_churn + effect})
    policy = np.where(x > 0, "contact", "hold")
    truth = float(np.mean(effect * (x > 0)))
    return reward, action, design, means, policy, truth


def family_false_failure_bound(*, worlds: int, n_coverage: int, n_null: int) -> float:
    """Union bound for this Monte Carlo gate under ideal nominal behavior."""

    coverage_boundary = max(
        count for count in range(worlds + 1) if _wilson(count, worlds)[0] < COVERAGE_WILSON_FLOOR
    )
    promotion_boundary = min(
        count
        for count in range(worlds + 1)
        if _wilson(count, worlds)[1] > FALSE_PROMOTION_WILSON_CEILING
    )
    coverage_failure_probability = float(binom.cdf(coverage_boundary, worlds, NOMINAL_COVERAGE))
    promotion_failure_probability = float(binom.sf(promotion_boundary - 1, worlds, 0.025))
    return min(
        1.0,
        n_coverage * coverage_failure_probability + n_null * promotion_failure_probability,
    )


def run(*, worlds: int, n_units: int = 4_000, seed: int = SEED) -> dict:
    if worlds < 1 or n_units < 100:
        raise ValueError("worlds must be positive and n_units at least 100")
    readouts = []
    for scenario in SCENARIOS:
        namespace = int(hashlib.sha256(scenario.name.encode()).hexdigest()[:8], 16)
        observations: dict[str, list[tuple[float, float, float, float]]] = {
            "selected_dr": [],
            "normal_dr_reference": [],
        }
        for index in range(worlds):
            rng = np.random.default_rng([seed, namespace, index])
            reward, action, design, means, policy, truth = draw_world(
                scenario, n_units=n_units, rng=rng
            )
            scores = dr_action_scores(reward, action, design, means)
            baseline = np.full(n_units, "hold")
            for label, method in (
                ("selected_dr", METHOD),
                ("normal_dr_reference", "normal"),
            ):
                contrast = paired_contrast(
                    scores,
                    policy,
                    baseline,
                    interval_method=method,
                    effective_df_floor=EFFECTIVE_DF_FLOOR,
                )
                observations[label].append(
                    (contrast.delta, contrast.ci_low, contrast.ci_high, truth)
                )
        for label, values in observations.items():
            result = np.asarray(values)
            covered = int(((result[:, 1] <= result[:, 3]) & (result[:, 3] <= result[:, 2])).sum())
            promoted = int((result[:, 1] > 0).sum())
            coverage_low, coverage_high = _wilson(covered, worlds)
            promotion_low, promotion_high = _wilson(promoted, worlds)
            readouts.append(
                {
                    "scenario": scenario.name,
                    "method": label,
                    "worlds": worlds,
                    "bias_vs_finite_truth": float(np.mean(result[:, 0] - result[:, 3])),
                    "coverage": covered / worlds,
                    "coverage_wilson": [coverage_low, coverage_high],
                    "promotion_rate": promoted / worlds,
                    "promotion_wilson": [promotion_low, promotion_high],
                    "mean_interval_width": float(np.mean(result[:, 2] - result[:, 1])),
                    "cell_coverage_pass": coverage_low >= COVERAGE_WILSON_FLOOR,
                    "null_promotion_pass": (
                        promotion_high <= FALSE_PROMOTION_WILSON_CEILING
                        if scenario.effect == "zero"
                        else None
                    ),
                }
            )
    selected = [item for item in readouts if item["method"] == "selected_dr"]
    cellwise_pass = all(
        item["cell_coverage_pass"] and item["null_promotion_pass"] is not False for item in selected
    )
    family_bound = family_false_failure_bound(
        worlds=worlds,
        n_coverage=len(selected),
        n_null=sum(scenario.effect == "zero" for scenario in SCENARIOS),
    )
    return {
        "status": "DIAGNOSTIC" if worlds >= 2_000 else "SMOKE_ONLY",
        "release_gate": "NOT_EVALUATED",
        "cellwise_diagnostic_pass": cellwise_pass if worlds >= 2_000 else None,
        "family_false_failure_upper_bound": family_bound,
        "family_gate_calibrated": family_bound <= 0.05 if worlds >= 2_000 else None,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "worlds_per_scenario": worlds,
        "n_units": n_units,
        "seed": seed,
        "selected_interval_method": METHOD,
        "effective_df_floor": EFFECTIVE_DF_FLOOR,
        "note": "This interval was selected after earlier results. Two fresh generator families test transfer, but this study alone does not resolve every prior selection and release-gate issue.",
        "scenarios": [asdict(item) for item in SCENARIOS],
        "readouts": readouts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=2_000)
    parser.add_argument("--n-units", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/v4/fresh_evaluator"))
    args = parser.parse_args()
    result = run(worlds=args.worlds, n_units=args.n_units, seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "FRESH_EVALUATOR.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"{path}: {result['status']} cellwise={result['cellwise_diagnostic_pass']}")
    for item in result["readouts"]:
        if item["method"] == "selected_dr":
            print(
                f"{item['scenario']}: coverage={item['coverage']:.3f}, "
                f"Wilson low={item['coverage_wilson'][0]:.3f}, "
                f"null promotion={item['null_promotion_pass']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
