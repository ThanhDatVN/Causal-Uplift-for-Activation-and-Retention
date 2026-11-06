"""R06: does choosing the best of four recipes manufacture a winner?

R01 validates the evaluator for a *fixed* policy.  That is not the same
guarantee as the one the workflow actually needs, because the workflow does
not evaluate a fixed policy -- it screens several, picks the best on a
selection sample, and then reports an interval for the winner.  Selecting on
a noisy criterion and reporting the selected value is the oldest way to
produce a result that does not replicate, and no amount of fixed-policy
coverage rules it out.

So this stage runs the whole procedure, end to end, in worlds where the truth
is known by construction:

* **Four frozen recipes**, never retuned on world outcomes.  Retuning inside
  a world would measure a different, more optimistic procedure.
* **Three independent samples per world** -- train, selection, evaluation.
  The recipe is fitted on train, chosen on selection, and reported on
  evaluation, so the reported number never comes from the sample that chose
  it.
* **One-versus-four**, on the *same* fitted predictions.  The only difference
  between the two arms is how many candidates the selector was allowed to
  look at, which isolates the cost of selection from the cost of modelling.
* **Two mechanisms**: a true null where no recipe has any effect, and a weak
  heterogeneous effect where one does.

What this can and cannot certify.  The runbook is explicit and it is worth
repeating in the code that implements it: **a few dozen null worlds cannot
score a 5% false-promotion gate.**  The binomial interval at that scale is
wider than the thing being measured.  This stage reports sensitivity -- how
much selection moves false promotion and regret -- and the artifact refuses
to describe itself as a gate.  Claiming the gate would need far more null
replications, or a cheaper pipeline designed for that purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .allocation import allocate_batch
from .policy_comparison import dr_action_scores, paired_contrast
from .validity_suite import _sigmoid, _wilson

__all__ = [
    "MECHANISMS",
    "RECIPES",
    "SelectionStressReport",
    "WorldOutcome",
    "main",
    "run_selection_stress",
]

HOLD = "hold"
CONTACT = "contact"

#: Sample size and effect scale are set so the study can actually *fail*.
#:
#: A first draft used 4,000 rows and a 2% effect scale.  Every arm covered at
#: 1.000 and promoted at 0.000, which is not a reassuring result -- it is a
#: scenario with no resolution, where the interval half-width was thirty
#: times the truth and no selector could have been caught doing anything.
#: These values put the alternative near the promotion boundary, which is the
#: only place where "did selecting inflate promotion" has an answer.
N_PER_SAMPLE = 20_000
PROPENSITY = 0.5
CAPACITY_FRACTION = 0.2
BASE_RATE = 0.06

#: Four frozen scoring recipes.  They differ in which covariates they look at
#: and how much they smooth, which is enough for the selector to have a real
#: choice, and none of them is refitted on world outcomes.
RECIPES: tuple[str, ...] = ("x1_only", "x2_only", "both", "smoothed")

#: ``(label, effect_scale)``.  Under ``null_effect`` no recipe can be better
#: than another, so every promotion is a false one and the regret of a
#: perfect selector is zero.
MECHANISMS: tuple[tuple[str, float], ...] = (
    ("null_effect", 0.0),
    ("weak_heterogeneous", 0.35),
)


def _namespace(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def _sample(n: int, effect_scale: float, rng: np.random.Generator) -> dict[str, Any]:
    x1 = rng.random(n)
    x2 = rng.random(n)
    noise = rng.standard_normal(n)
    p0 = BASE_RATE * (0.4 + 1.2 * _sigmoid(1.2 * (2 * x1 - 1) + 0.4 * noise))
    # Only x1 carries the effect, so a recipe that reads x2 is looking at
    # nothing: under the null every recipe is equally blind, and under the
    # alternative the difference between them is real but small.
    tau = effect_scale * (2 * x1 - 1) * BASE_RATE
    treatment = (rng.random(n) < PROPENSITY).astype(int)
    reward = 1.0 - (rng.random(n) < np.clip(p0 - tau * treatment, 0.0, 1.0)).astype(float)
    return {
        "x1": x1,
        "x2": x2,
        "reward": reward,
        "treatment": treatment,
        "tau": tau,
        "p0": p0,
        "unit_id": [f"u{index}" for index in range(n)],
    }


def _recipe_score(recipe: str, sample: dict[str, Any], fit: dict[str, float]) -> np.ndarray:
    """A frozen scoring function, parameterised only by train-side constants."""

    x1, x2 = sample["x1"], sample["x2"]
    if recipe == "x1_only":
        return fit["b1"] * (2 * x1 - 1)
    if recipe == "x2_only":
        return fit["b2"] * (2 * x2 - 1)
    if recipe == "both":
        return fit["b1"] * (2 * x1 - 1) + fit["b2"] * (2 * x2 - 1)
    if recipe == "smoothed":
        # Same information as "both", shrunk halfway toward the mean effect.
        return 0.5 * (fit["b1"] * (2 * x1 - 1) + fit["b2"] * (2 * x2 - 1)) + 0.5 * fit["ate"]
    raise ValueError(f"unknown recipe {recipe!r}")  # pragma: no cover


def _fit_recipes(train: dict[str, Any]) -> dict[str, float]:
    """Train-side constants, by a difference of arm means within halves.

    Deliberately crude and identical in form for every recipe: this stage is
    about the *selector*, and a sophisticated learner would confound the two.
    """

    reward, treatment = train["reward"], train["treatment"]
    constants: dict[str, float] = {}
    for name, covariate in (("b1", train["x1"]), ("b2", train["x2"])):
        high = covariate >= 0.5
        effects = []
        for mask in (high, ~high):
            treated = reward[mask & (treatment == 1)]
            control = reward[mask & (treatment == 0)]
            effects.append(
                float(treated.mean() - control.mean()) if len(treated) and len(control) else 0.0
            )
        constants[name] = 0.5 * (effects[0] - effects[1])
    treated_all = reward[treatment == 1]
    control_all = reward[treatment == 0]
    constants["ate"] = (
        float(treated_all.mean() - control_all.mean())
        if len(treated_all) and len(control_all)
        else 0.0
    )
    return constants


def _policy_readout(
    sample: dict[str, Any], scores: np.ndarray
) -> tuple[float, float, tuple[float, float]]:
    """Estimated contrast, true contrast, and the interval, for one allocation."""

    allocation = allocate_batch(
        [str(value) for value in sample["unit_id"]],
        scores,
        fraction=CAPACITY_FRACTION,
        require_positive=False,
    )
    chosen = allocation.frame["selected"].to_numpy()
    n = len(chosen)
    design = pd.DataFrame({HOLD: np.full(n, 1 - PROPENSITY), CONTACT: np.full(n, PROPENSITY)})
    p0, tau = sample["p0"], sample["tau"]
    means = pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)})
    action = np.where(sample["treatment"] == 1, CONTACT, HOLD)
    action_scores = dr_action_scores(sample["reward"], action, design, means)
    policy = np.where(chosen, CONTACT, HOLD)
    baseline = np.full(n, HOLD)
    contrast = paired_contrast(action_scores, policy, baseline)
    truth = float(np.mean(np.where(chosen, tau, 0.0)))
    return contrast.delta, truth, (contrast.ci_low, contrast.ci_high)


@dataclass
class WorldOutcome:
    mechanism: str
    world: int
    chosen_of_four: str
    #: The single fixed recipe the one-candidate arm was committed to in
    #: advance, so its promotion rate carries no selection at all.
    fixed_recipe: str
    selected_estimate: float
    selected_truth: float
    selected_promoted: bool
    selected_covered: bool
    fixed_estimate: float
    fixed_truth: float
    fixed_promoted: bool
    fixed_covered: bool
    best_possible_truth: float

    @property
    def selection_regret(self) -> float:
        """Truth of the best available recipe minus the truth of the chosen one."""

        return self.best_possible_truth - self.selected_truth

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "selection_regret": self.selection_regret}


@dataclass
class ArmSummary:
    mechanism: str
    arm: str
    worlds: int
    promotion_rate: float
    promotion_ci_low: float
    promotion_ci_high: float
    coverage: float
    mean_regret: float
    mean_bias: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SelectionStressReport:
    worlds_per_mechanism: int
    seed: int
    started_at: str
    outcomes: list[WorldOutcome] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def summaries(self) -> list[ArmSummary]:
        rows: list[ArmSummary] = []
        for mechanism, _scale in MECHANISMS:
            worlds = [item for item in self.outcomes if item.mechanism == mechanism]
            if not worlds:
                continue
            for arm in ("one_candidate", "four_candidates"):
                promoted = [
                    item.fixed_promoted if arm == "one_candidate" else item.selected_promoted
                    for item in worlds
                ]
                covered = [
                    item.fixed_covered if arm == "one_candidate" else item.selected_covered
                    for item in worlds
                ]
                errors = [
                    (item.fixed_estimate - item.fixed_truth)
                    if arm == "one_candidate"
                    else (item.selected_estimate - item.selected_truth)
                    for item in worlds
                ]
                regret = [
                    0.0 if arm == "one_candidate" else item.selection_regret for item in worlds
                ]
                low, high = _wilson(int(sum(promoted)), len(worlds))
                rows.append(
                    ArmSummary(
                        mechanism=mechanism,
                        arm=arm,
                        worlds=len(worlds),
                        promotion_rate=round(float(np.mean(promoted)), 4),
                        promotion_ci_low=round(low, 4),
                        promotion_ci_high=round(high, 4),
                        coverage=round(float(np.mean(covered)), 4),
                        mean_regret=float(np.mean(regret)),
                        mean_bias=float(np.mean(errors)),
                    )
                )
        return rows

    def selection_cost(self) -> dict[str, Any]:
        """How much the extra three candidates moved the answer, per mechanism."""

        out: dict[str, Any] = {}
        for mechanism, _scale in MECHANISMS:
            rows = {item.arm: item for item in self.summaries() if item.mechanism == mechanism}
            if len(rows) < 2:
                continue
            one, four = rows["one_candidate"], rows["four_candidates"]
            out[mechanism] = {
                "promotion_one": one.promotion_rate,
                "promotion_four": four.promotion_rate,
                "promotion_inflation": round(four.promotion_rate - one.promotion_rate, 4),
                "coverage_one": one.coverage,
                "coverage_four": four.coverage,
                "coverage_loss": round(one.coverage - four.coverage, 4),
                "mean_regret_four": four.mean_regret,
                "bias_inflation": four.mean_bias - one.mean_bias,
            }
        return out

    def to_dict(self) -> dict[str, Any]:
        worlds = self.worlds_per_mechanism
        # Width of a 95% binomial interval at the 5% gate, at this many worlds.
        resolution = 2 * math.sqrt(0.05 * 0.95 / worlds) if worlds else float("nan")
        return {
            "study": "R06_selection_stress",
            "worlds_per_mechanism": worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "recipes": list(RECIPES),
            "mechanisms": [name for name, _ in MECHANISMS],
            "n_per_sample": N_PER_SAMPLE,
            "capacity_fraction": CAPACITY_FRACTION,
            "is_a_gate": False,
            "gate_refusal_reason": (
                f"a 5% false-promotion gate cannot be scored on {worlds} null worlds: "
                f"the 95% binomial interval there is about +-{resolution:.3f}, wider "
                "than the quantity being gated. This stage reports sensitivity to "
                "selection, not a certified rate."
            ),
            "summaries": [row.to_dict() for row in self.summaries()],
            "selection_cost": self.selection_cost(),
            "worlds": [item.to_dict() for item in self.outcomes],
            "scope_note": (
                "One generator family, four frozen recipes, one capacity. The "
                "comparison is one-versus-four candidates on identical predictions, "
                "so it isolates the cost of selecting rather than of modelling."
            ),
        }


def run_selection_stress(*, worlds: int = 200, seed: int = 20260928) -> SelectionStressReport:
    """Run the whole screen-then-report procedure in worlds with known truth."""

    started = time.perf_counter()
    report = SelectionStressReport(
        worlds_per_mechanism=worlds,
        seed=seed,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    fixed_recipe = RECIPES[0]

    for mechanism, scale in MECHANISMS:
        namespace = _namespace(f"R06:{mechanism}")
        for index in range(worlds):
            rng = np.random.default_rng([seed, namespace, index])
            train = _sample(N_PER_SAMPLE, scale, rng)
            selection = _sample(N_PER_SAMPLE, scale, rng)
            evaluation = _sample(N_PER_SAMPLE, scale, rng)
            fit = _fit_recipes(train)

            # Choose on the selection sample only.
            selection_values = {
                recipe: _policy_readout(selection, _recipe_score(recipe, selection, fit))[0]
                for recipe in RECIPES
            }
            chosen = max(selection_values, key=lambda name: selection_values[name])

            readouts = {
                recipe: _policy_readout(evaluation, _recipe_score(recipe, evaluation, fit))
                for recipe in RECIPES
            }
            chosen_estimate, chosen_truth, (chosen_low, chosen_high) = readouts[chosen]
            fixed_estimate, fixed_truth, (fixed_low, fixed_high) = readouts[fixed_recipe]

            report.outcomes.append(
                WorldOutcome(
                    mechanism=mechanism,
                    world=index,
                    chosen_of_four=chosen,
                    fixed_recipe=fixed_recipe,
                    selected_estimate=chosen_estimate,
                    selected_truth=chosen_truth,
                    selected_promoted=bool(chosen_low > 0),
                    selected_covered=bool(chosen_low <= chosen_truth <= chosen_high),
                    fixed_estimate=fixed_estimate,
                    fixed_truth=fixed_truth,
                    fixed_promoted=bool(fixed_low > 0),
                    fixed_covered=bool(fixed_low <= fixed_truth <= fixed_high),
                    best_possible_truth=max(truth for _e, truth, _ci in readouts.values()),
                )
            )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: SelectionStressReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R06 — selection stress",
        "",
        f"{report.worlds_per_mechanism} worlds per mechanism · "
        f"{len(RECIPES)} frozen recipes · N = {N_PER_SAMPLE:,} per sample · "
        f"{report.runtime_seconds:.0f} s",
        "",
        "**This is not a gate.** " + payload["gate_refusal_reason"],
        "",
        payload["scope_note"],
        "",
        "| mechanism | arm | promotion | 95% CI | coverage | mean regret | bias |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report.summaries():
        lines.append(
            f"| {row.mechanism} | {row.arm} | {row.promotion_rate:.3f} "
            f"| [{row.promotion_ci_low:.3f}, {row.promotion_ci_high:.3f}] "
            f"| {row.coverage:.3f} | {row.mean_regret:+.6f} | {row.mean_bias:+.6f} |"
        )
    lines.extend(
        [
            "",
            "## What selection cost",
            "",
            "| mechanism | promotion inflation | coverage loss | mean regret |",
            "|---|---|---|---|",
        ]
    )
    for mechanism, entry in payload["selection_cost"].items():
        lines.append(
            f"| {mechanism} | {entry['promotion_inflation']:+.3f} "
            f"| {entry['coverage_loss']:+.3f} | {entry['mean_regret_four']:+.6f} |"
        )
    lines.extend(
        [
            "",
            "Under `null_effect` no recipe is better than any other, so every promotion "
            "is a false one and any regret above zero is the selector paying for noise. "
            "The one-candidate arm is committed to `" + RECIPES[0] + "` in advance, so "
            "its promotion rate carries no selection at all and the difference between "
            "the arms is the price of looking at four.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--output-dir", default="reports/v4/selection_stress")
    args = parser.parse_args(argv)

    report = run_selection_stress(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "selection_stress.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "SELECTION_STRESS.md").write_text(render_markdown(report), encoding="utf-8")
    for row in report.summaries():
        print(
            f"{row.mechanism:<20} {row.arm:<16} promotion {row.promotion_rate:.3f} "
            f"[{row.promotion_ci_low:.3f}, {row.promotion_ci_high:.3f}] "
            f"coverage {row.coverage:.3f} regret {row.mean_regret:+.6f}"
        )
    print("NOT A GATE: " + report.to_dict()["gate_refusal_reason"])
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
