"""Does the asymmetry index transfer, or did it only fit the grid it came from?

The boundary sweep varied two things -- the propensity and the event rate --
and found that ``A = |1-2e| / sqrt(n h r e(1-e))`` ordered its cells while
imbalance did not.  That is one grid, one frame size, one acted fraction and
one mechanism, so it is a fit, not yet a law.  A formula that ranks the cells
it was derived on is the cheapest thing in statistics.

This study tries to break it, in the one way that matters: by holding ``A``
*fixed* and changing everything else.  For each target value of ``A`` it
solves for the propensity that realises that target under several different
``(n, h, rate)`` combinations, then scores them all.  If ``A`` is the right
summary, designs that differ four-fold in frame size and four-fold in acted
fraction must land on the same coverage; if it is a curve-fit, they will not.

It also includes an arm the formula is expected to **fail** on, declared as
such before the run, because a boundary that is never shown to have an
outside is not a boundary.

Pre-registered predictions (written before the first run, and scored in the
artifact whether they hold or not):

``P1 transfer``
    Within a target ``A``, the constant-propensity designs agree on coverage
    to within 2 Monte Carlo standard errors of their difference.
``P2 threshold``
    Designs at ``A = 0.10`` and ``A = 0.20`` cover; designs at ``A = 0.30``
    and ``A = 0.55`` do not, under the plain Wald interval.  This carries the
    0.202 threshold from the sweep to frames it never saw.
``P3 out of scope``
    The varying-propensity arm, whose ``A`` is computed from its *mean*
    propensity, under-covers relative to the constant arm at the same nominal
    ``A``.  ``1/(1-e)`` is convex, so averaging the propensity before taking
    the index understates the spike -- meaning the shipped gate, which
    believes what a caller declares, can be fooled by a design like this.
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

from .policy_comparison import (
    _gather,
    design_asymmetry_index,
    dr_action_scores,
    paired_contrast,
)
from .validity_suite import COVERAGE_LOWER_BOUND, NOMINAL_COVERAGE, _sigmoid, _wilson

__all__ = [
    "DESIGN_FAMILIES",
    "TARGET_ASYMMETRY",
    "TransferReport",
    "TransferResult",
    "main",
    "run_transfer",
    "solve_propensity",
]

HOLD = "hold"
CONTACT = "contact"

#: The values of ``A`` to hit.  Two below the sweep's 0.202 threshold for the
#: plain Wald interval, two above it.
TARGET_ASYMMETRY: tuple[float, ...] = (0.10, 0.20, 0.30, 0.55)

#: ``(label, n_units, acted_fraction, event_rate)``.  Two things are being
#: tested at once, so the list is built deliberately rather than swept.
#:
#: The middle four share a product ``n * h * r = 25`` while differing 16x in
#: frame size, 4x in acted fraction and 8x in event rate.  The formula says
#: those three enter *only* through their product, so if that is right these
#: four must be indistinguishable -- a sharp test, because nothing else about
#: them is alike.
#:
#: The rest carry products of 10, 100 and 160, so the study also spans a 16x
#: range in the product itself rather than only permuting within one value.
DESIGN_FAMILIES: tuple[tuple[str, int, float, float], ...] = (
    ("baseline", 10_000, 0.5, 0.005),
    ("narrow_policy", 10_000, 0.25, 0.010),
    ("whole_frame", 10_000, 1.00, 0.0025),
    ("small_frame", 2_500, 0.5, 0.020),
    ("sparse_frame", 5_000, 0.5, 0.004),
    ("large_frame", 40_000, 0.5, 0.005),
    ("dense_frame", 20_000, 0.8, 0.010),
)

METHOD = "normal"
MAX_PROPENSITY = 0.995


def solve_propensity(
    target: float, *, n_units: int, acted_fraction: float, event_rate: float
) -> float | None:
    """The propensity above 0.5 that gives this design the target ``A``.

    ``A`` rises monotonically from 0 at ``e = 0.5``, so a bisection is exact
    enough and cannot land on the wrong branch.  Returns ``None`` when the
    design cannot reach the target at all -- a large frame with plenty of
    events simply cannot be made that asymmetric without a degenerate
    propensity, and pretending otherwise would put a fake row in the table.
    """

    def index_at(propensity: float) -> float:
        return abs(
            design_asymmetry_index(
                n_units=n_units,
                propensity=propensity,
                event_rate=event_rate,
                acted_fraction=acted_fraction,
            )
        )

    if index_at(MAX_PROPENSITY) < target:
        return None
    low, high = 0.5 + 1e-9, MAX_PROPENSITY
    for _ in range(200):
        middle = 0.5 * (low + high)
        if index_at(middle) < target:
            low = middle
        else:
            high = middle
    return round(0.5 * (low + high), 6)


def _namespace(label: str) -> int:
    """A seed namespace keyed on the cell, so a cell is reproducible alone."""

    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _draw(
    *,
    n_units: int,
    acted_fraction: float,
    event_rate: float,
    propensity: float | np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """One world.  ``propensity`` may be a scalar or a per-unit vector."""

    acted = (rng.random(n_units) < acted_fraction).astype(int)
    z = rng.standard_normal(n_units)
    shape = 0.2 + 1.6 * _sigmoid(0.8 * (2 * acted - 1) + 0.5 * z)
    p0 = event_rate * shape
    tau = np.where(acted == 1, 0.1 * event_rate, 0.0)

    e = np.full(n_units, propensity) if np.isscalar(propensity) else np.asarray(propensity)
    treatment = (rng.random(n_units) < e).astype(int)
    reward = 1.0 - (rng.random(n_units) < p0 - tau * treatment).astype(float)

    return {
        "reward": reward,
        "action": np.where(treatment == 1, CONTACT, HOLD),
        "design": pd.DataFrame({HOLD: 1.0 - e, CONTACT: e}),
        "mean": pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)}),
        "policy_1": np.where(acted == 1, CONTACT, HOLD),
        "policy_0": np.full(n_units, HOLD),
        "finite_truth": float(np.mean((acted == 1) * tau)),
    }


@dataclass
class TransferResult:
    arm: str
    family: str
    target_asymmetry: float
    realised_asymmetry: float
    n_units: int
    acted_fraction: float
    event_rate: float
    propensity: float
    worlds: int
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    mean_skewness: float
    bias: float
    mc_se: float

    @property
    def passes(self) -> bool:
        return self.coverage_ci_low >= COVERAGE_LOWER_BOUND

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "passes": self.passes}


@dataclass
class TransferReport:
    worlds: int
    seed: int
    started_at: str
    results: list[TransferResult] = field(default_factory=list)
    infeasible: list[dict[str, Any]] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def _constant(self) -> list[TransferResult]:
        return [r for r in self.results if r.arm == "constant_propensity"]

    def score_p1_transfer(self) -> dict[str, Any]:
        """Do designs matched on ``A`` agree, across frames that differ 16x?"""

        levels: dict[str, Any] = {}
        held = True
        for target in sorted({r.target_asymmetry for r in self._constant()}):
            group = [r for r in self._constant() if r.target_asymmetry == target]
            if len(group) < 2:
                continue
            coverages = [r.coverage for r in group]
            spread = max(coverages) - min(coverages)
            # Two independent binomial proportions at the nominal rate.
            tolerance = 2 * math.sqrt(2 * NOMINAL_COVERAGE * (1 - NOMINAL_COVERAGE) / self.worlds)
            agrees = spread <= tolerance
            held = held and agrees
            levels[f"A={target}"] = {
                "target_asymmetry": target,
                "n_designs": len(group),
                "families": [r.family for r in group],
                "coverage_min": min(coverages),
                "coverage_max": max(coverages),
                "spread": round(spread, 4),
                "tolerance_2mcse": round(tolerance, 4),
                "agrees": agrees,
            }
        return {"prediction": "matched A agrees within 2 MCSE", "held": held, "levels": levels}

    def score_p2_threshold(self) -> dict[str, Any]:
        """Does the sweep's 0.202 threshold carry to frames it never saw?"""

        levels: dict[str, Any] = {}
        held = True
        for target in sorted({r.target_asymmetry for r in self._constant()}):
            group = [r for r in self._constant() if r.target_asymmetry == target]
            expected = target <= 0.202
            observed = [r.passes for r in group]
            agrees = all(value == expected for value in observed)
            held = held and agrees
            levels[f"A={target}"] = {
                "target_asymmetry": target,
                "expected_to_cover": expected,
                "n_covering": sum(observed),
                "n_designs": len(group),
                "agrees": agrees,
            }
        return {
            "prediction": "designs at A <= 0.202 cover, designs above it do not",
            "held": held,
            "levels": levels,
        }

    def score_p3_out_of_scope(self) -> dict[str, Any]:
        """Does a varying propensity defeat an index computed from its mean?"""

        varying = [r for r in self.results if r.arm == "varying_propensity"]
        comparisons = []
        held = bool(varying)
        for result in varying:
            matched = [
                r
                for r in self._constant()
                if r.target_asymmetry == result.target_asymmetry and r.family == result.family
            ]
            if not matched:
                continue
            reference = matched[0]
            gap = reference.coverage - result.coverage
            tolerance = 2 * math.sqrt(2 * NOMINAL_COVERAGE * (1 - NOMINAL_COVERAGE) / self.worlds)
            undercovers = gap > tolerance
            held = held and undercovers
            comparisons.append(
                {
                    "family": result.family,
                    "target_asymmetry": result.target_asymmetry,
                    "constant_coverage": reference.coverage,
                    "varying_coverage": result.coverage,
                    "gap": round(gap, 4),
                    "tolerance_2mcse": round(tolerance, 4),
                    "undercovers": undercovers,
                }
            )
        return {
            "prediction": (
                "a varying propensity under-covers relative to a constant one at the "
                "same nominal A, so the declared index understates the risk"
            ),
            "held": held,
            "comparisons": comparisons,
        }

    def to_dict(self) -> dict[str, Any]:
        predictions = {
            "P1_transfer": self.score_p1_transfer(),
            "P2_threshold": self.score_p2_threshold(),
            "P3_out_of_scope": self.score_p3_out_of_scope(),
        }
        return {
            "study": "asymmetry_index_transfer",
            "worlds_per_design": self.worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "interval_method": METHOD,
            "nominal_coverage": NOMINAL_COVERAGE,
            "coverage_tolerance": COVERAGE_LOWER_BOUND,
            "target_asymmetry": list(TARGET_ASYMMETRY),
            "design_families": [
                {"label": label, "n_units": n, "acted_fraction": h, "event_rate": r}
                for label, n, h, r in DESIGN_FAMILIES
            ],
            "predictions": predictions,
            "all_predictions_held": all(item["held"] for item in predictions.values()),
            "results": [result.to_dict() for result in self.results],
            "infeasible": self.infeasible,
            "scope_note": (
                "Designs are matched on A and differ in frame size, acted fraction and "
                "event rate. The varying-propensity arm is a declared out-of-scope "
                "control: the index assumes a constant propensity, and this arm exists "
                "to show where that assumption fails rather than to be rescued by it."
            ),
        }


def _paired_skewness(scores: pd.DataFrame, world: dict[str, Any]) -> float:
    """Skewness of the per-unit paired score, the quantity ``A`` predicts."""

    paired = _gather(scores, world["policy_1"]) - _gather(scores, world["policy_0"])
    centred = paired - paired.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return 0.0
    return float(np.mean(centred**3) / variance**1.5)


def _score_design(
    *,
    label: str,
    arm: str,
    target: float,
    n_units: int,
    acted_fraction: float,
    event_rate: float,
    propensity: float,
    realised: float,
    worlds: int,
    seed: int,
    vary: bool,
) -> TransferResult:
    covered = 0
    errors: list[float] = []
    skews: list[float] = []
    namespace = _namespace(f"{arm}:{label}:{target}")

    for index in range(worlds):
        rng = np.random.default_rng([seed, namespace, index])
        if vary:
            # Same mean propensity, two levels.  1/(1-e) is convex, so this is
            # strictly more asymmetric than the constant design it mimics.
            half = rng.random(n_units) < 0.5
            spread = min(0.5 * (1 - propensity), 0.5 * propensity) * 0.9
            e = np.where(half, propensity - spread, propensity + spread)
        else:
            e = propensity
        world = _draw(
            n_units=n_units,
            acted_fraction=acted_fraction,
            event_rate=event_rate,
            propensity=e,
            rng=rng,
        )
        scores = dr_action_scores(world["reward"], world["action"], world["design"], world["mean"])
        contrast = paired_contrast(
            scores, world["policy_1"], world["policy_0"], interval_method=METHOD
        )
        truth = world["finite_truth"]
        if contrast.ci_low <= truth <= contrast.ci_high:
            covered += 1
        errors.append(contrast.delta - truth)
        skews.append(_paired_skewness(scores, world))

    low, high = _wilson(covered, worlds)
    return TransferResult(
        arm=arm,
        family=label,
        target_asymmetry=target,
        realised_asymmetry=round(realised, 6),
        n_units=n_units,
        acted_fraction=acted_fraction,
        event_rate=event_rate,
        propensity=propensity,
        worlds=worlds,
        coverage=round(covered / worlds, 4),
        coverage_ci_low=round(low, 4),
        coverage_ci_high=round(high, 4),
        mean_skewness=round(float(np.mean(skews)), 4),
        bias=float(np.mean(errors)),
        mc_se=float(np.std(errors, ddof=1) / math.sqrt(worlds)),
    )


def run_transfer(
    *,
    worlds: int = 1_000,
    seed: int = 20260926,
    targets: Sequence[float] = TARGET_ASYMMETRY,
    families: Sequence[tuple[str, int, float, float]] = DESIGN_FAMILIES,
) -> TransferReport:
    """Hold ``A`` fixed, change everything else, and see whether it holds."""

    started = time.perf_counter()
    report = TransferReport(
        worlds=worlds, seed=seed, started_at=datetime.now(UTC).isoformat(timespec="seconds")
    )

    for target in targets:
        for label, n_units, acted, rate in families:
            propensity = solve_propensity(
                target, n_units=n_units, acted_fraction=acted, event_rate=rate
            )
            if propensity is None:
                report.infeasible.append(
                    {
                        "family": label,
                        "target_asymmetry": target,
                        "reason": (
                            f"a {n_units:,}-row frame with {rate:.1%} events and an acted "
                            f"share of {acted:g} cannot reach A = {target} below a "
                            f"propensity of {MAX_PROPENSITY}"
                        ),
                    }
                )
                continue
            realised = abs(
                design_asymmetry_index(
                    n_units=n_units,
                    propensity=propensity,
                    event_rate=rate,
                    acted_fraction=acted,
                )
            )
            report.results.append(
                _score_design(
                    label=label,
                    arm="constant_propensity",
                    target=target,
                    n_units=n_units,
                    acted_fraction=acted,
                    event_rate=rate,
                    propensity=propensity,
                    realised=realised,
                    worlds=worlds,
                    seed=seed,
                    vary=False,
                )
            )
            if label == "baseline":
                report.results.append(
                    _score_design(
                        label=label,
                        arm="varying_propensity",
                        target=target,
                        n_units=n_units,
                        acted_fraction=acted,
                        event_rate=rate,
                        propensity=propensity,
                        realised=realised,
                        worlds=worlds,
                        seed=seed,
                        vary=True,
                    )
                )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: TransferReport) -> str:
    payload = report.to_dict()
    lines = [
        "# Does the asymmetry index transfer?",
        "",
        f"{report.worlds:,} worlds per design · seed {report.seed} · "
        f"{report.runtime_seconds:.0f} s · {METHOD} interval",
        "",
        payload["scope_note"],
        "",
        "## Designs matched on A",
        "",
        "| target A | family | n | acted | rate | e | coverage | |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in report.results:
        if result.arm != "constant_propensity":
            continue
        lines.append(
            f"| {result.target_asymmetry:.2f} | {result.family} | {result.n_units:,} "
            f"| {result.acted_fraction:g} | {result.event_rate:.2%} "
            f"| {result.propensity:.4f} | {result.coverage:.3f} "
            f"| {'' if result.passes else '✗'} |"
        )
    lines.append("")

    lines.extend(["## Pre-registered predictions", "", "| prediction | held? |", "|---|---|"])
    for name, entry in payload["predictions"].items():
        lines.append(
            f"| **{name}** — {entry['prediction']} | {'**yes**' if entry['held'] else '**NO**'} |"
        )
    lines.append("")

    varying = [r for r in report.results if r.arm == "varying_propensity"]
    if varying:
        lines.extend(
            [
                "## The declared out-of-scope arm",
                "",
                "Same mean propensity, same nominal A, but the propensity varies by unit. "
                "The index is computed from the mean, which is what a caller would declare.",
                "",
                "| target A | constant e | varying e | gap |",
                "|---|---|---|---|",
            ]
        )
        for entry in payload["predictions"]["P3_out_of_scope"]["comparisons"]:
            lines.append(
                f"| {entry['target_asymmetry']:.2f} | {entry['constant_coverage']:.3f} "
                f"| {entry['varying_coverage']:.3f} | {entry['gap']:+.3f} |"
            )
        lines.append("")

    if report.infeasible:
        lines.extend(["## Designs that could not reach their target", ""])
        lines.extend(
            f"- **{entry['family']}** at A = {entry['target_asymmetry']}: {entry['reason']}"
            for entry in report.infeasible
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260926)
    parser.add_argument("--output-dir", default="reports/v4/asymmetry_transfer")
    args = parser.parse_args(argv)

    report = run_transfer(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    (destination / "asymmetry_transfer.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (destination / "ASYMMETRY_TRANSFER.md").write_text(render_markdown(report), encoding="utf-8")

    for result in report.results:
        flag = "ok  " if result.passes else "FAIL"
        print(
            f"[{flag}] {result.arm:<20} {result.family:<14} A={result.target_asymmetry:.2f} "
            f"e={result.propensity:.4f} coverage {result.coverage:.3f} "
            f"[{result.coverage_ci_low:.3f}]"
        )
    for name, entry in payload["predictions"].items():
        print(f"[{'HELD' if entry['held'] else 'FALSIFIED'}] {name}: {entry['prediction']}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
