"""Where does the doubly robust interval stop working? A measured boundary.

R01 found that the DR interval under-covers at V05 (propensity 0.9, 0.5% event
rate) but not at V05B (propensity 0.5, same rate), which isolates *imbalance*
rather than rarity as the cause.  Two points do not draw a line, though, and a
claim about a regime needs the regime mapped.

This sweeps the two axes independently:

* **propensity** from balanced to severely imbalanced, and
* **event rate** from the rare regime to the comfortable one,

holding the mechanism, the policy and the estimator fixed, and scores the same
evaluator code path the benchmark uses.  Each cell reports coverage for the
published interval and for the Edgeworth-corrected one, so the output is not
"it breaks" but "it breaks here, and the correction buys you this much".

The generator is the R01 family with the baseline rate parameterised.  With
``p0 = rate * (0.2 + 1.6 * sigmoid(0.8(2X1-1) + 0.5Z))`` the marginal event
rate is ``rate`` exactly, because the sigmoid term averages to 0.5 by
symmetry.  The effect is ``tau = 0.1 * rate`` on the units the policy acts on,
so cells stay comparable in effect-to-noise terms rather than in absolute
effect, and every probability stays feasible without clipping.
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
    design_asymmetry_index,
    dr_action_scores,
    paired_contrast,
)
from .validity_suite import COVERAGE_LOWER_BOUND, NOMINAL_COVERAGE, _sigmoid, _wilson

__all__ = [
    "EVENT_RATES",
    "PROPENSITIES",
    "BoundaryReport",
    "CellResult",
    "main",
    "run_sweep",
]

HOLD = "hold"
CONTACT = "contact"
N_UNITS = 10_000

#: The policy acts on ``x1 == 1``, i.e. half the frame.  Only rows where the
#: two policies disagree enter a paired contrast, so this scales the design's
#: effective information the same way ``n`` and the event rate do.
ACTED_FRACTION = 0.5

#: Treated-arm probability.  0.5 is balanced; 0.95 is the edge of what a
#: logged campaign might plausibly look like.
PROPENSITIES: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

#: Marginal event rates: V05's rare regime, Hillstrom's, and V03's.
EVENT_RATES: tuple[float, ...] = (0.005, 0.01, 0.035)

METHODS: tuple[str, ...] = ("normal", "skewness_adjusted_t")


def _draw(rate: float, propensity: float, rng: np.random.Generator) -> dict[str, Any]:
    x1 = rng.integers(0, 2, size=N_UNITS)
    z = rng.standard_normal(N_UNITS)
    shape = 0.2 + 1.6 * _sigmoid(0.8 * (2 * x1 - 1) + 0.5 * z)
    p0 = rate * shape
    tau = np.where(x1 == 1, 0.1 * rate, 0.0)

    treatment = (rng.random(N_UNITS) < propensity).astype(int)
    probability = p0 - tau * treatment
    reward = 1.0 - (rng.random(N_UNITS) < probability).astype(float)

    design = pd.DataFrame(
        {HOLD: np.full(N_UNITS, 1.0 - propensity), CONTACT: np.full(N_UNITS, propensity)}
    )
    means = pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)})
    action = np.where(treatment == 1, CONTACT, HOLD)
    policy_1 = np.where(x1 == 1, CONTACT, HOLD)
    policy_0 = np.full(N_UNITS, HOLD)
    return {
        "reward": reward,
        "action": action,
        "design": design,
        "means": means,
        "policy_1": policy_1,
        "policy_0": policy_0,
        "finite_truth": float(np.mean((policy_1 != policy_0) * tau)),
        "events": float((reward == 0).sum()),
        "control_events": float(((reward == 0) & (treatment == 0)).sum()),
    }


@dataclass
class CellResult:
    propensity: float
    imbalance: float
    event_rate: float
    method: str
    worlds: int
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    width_ratio: float
    mean_score_skewness: float
    mean_control_events: float
    bias: float
    mc_se: float

    @property
    def asymmetry_index(self) -> float:
        """``|A|``: the design's predicted contrast skewness.

        Imbalance alone does not order these cells -- the same imbalance
        passes at one event rate and fails at another -- because ``n``, the
        event rate and the acted fraction are amplifiers of it.  ``A``
        combines all four, and on this grid it separates the passing cells
        from the failing ones without overlap.
        """

        return abs(
            design_asymmetry_index(
                n_units=N_UNITS,
                propensity=self.propensity,
                event_rate=self.event_rate,
                acted_fraction=ACTED_FRACTION,
            )
        )

    @property
    def passes(self) -> bool:
        return self.coverage_ci_low >= COVERAGE_LOWER_BOUND

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "passes": self.passes,
            "asymmetry_index": round(self.asymmetry_index, 6),
        }


@dataclass
class BoundaryReport:
    worlds: int
    seed: int
    started_at: str
    cells: list[CellResult] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def boundary_by_rate(self) -> dict[str, dict[str, Any]]:
        """For each method and event rate, the largest imbalance that still works."""

        summary: dict[str, dict[str, Any]] = {}
        for method in METHODS:
            for rate in EVENT_RATES:
                cells = sorted(
                    (c for c in self.cells if c.method == method and c.event_rate == rate),
                    key=lambda c: c.imbalance,
                )
                passing = [c.imbalance for c in cells if c.passes]
                failing = [c.imbalance for c in cells if not c.passes]
                summary[f"{method}@{rate}"] = {
                    "method": method,
                    "event_rate": rate,
                    "largest_passing_imbalance": max(passing) if passing else None,
                    "smallest_failing_imbalance": min(failing) if failing else None,
                    "all_pass": not failing,
                }
        return summary

    def boundary_by_asymmetry(self) -> dict[str, dict[str, Any]]:
        """Per method, where the coverage verdict flips as ``A`` grows.

        The imbalance boundary moves with the event rate, so it is not a rule
        a gate can apply.  This asks the same question of ``A``, and -- this
        is the part that has to be reported rather than assumed -- says
        explicitly whether ``A`` orders the cells cleanly.  ``separates`` is
        False when a passing cell sits above a failing one, which would mean
        ``A`` is no better a rule than imbalance was.
        """

        summary: dict[str, dict[str, Any]] = {}
        for method in sorted({cell.method for cell in self.cells}):
            cells = sorted(
                (c for c in self.cells if c.method == method),
                key=lambda c: c.asymmetry_index,
            )
            if not cells:
                continue
            passing = [c.asymmetry_index for c in cells if c.passes]
            failing = [c.asymmetry_index for c in cells if not c.passes]
            largest_passing = max(passing) if passing else None
            smallest_failing = min(failing) if failing else None
            separates = (
                largest_passing is None
                or smallest_failing is None
                or largest_passing < smallest_failing
            )
            straddling = [
                {
                    "event_rate": c.event_rate,
                    "propensity": c.propensity,
                    "asymmetry_index": round(c.asymmetry_index, 6),
                    "passes": c.passes,
                }
                for c in cells
                if not separates
                and smallest_failing is not None
                and largest_passing is not None
                and smallest_failing <= c.asymmetry_index <= largest_passing
            ]
            summary[method] = {
                "method": method,
                "n_cells": len(cells),
                "n_failing": len(failing),
                "largest_passing_asymmetry": largest_passing,
                "smallest_failing_asymmetry": smallest_failing,
                "separates": separates,
                "straddling_cells": straddling,
                "licensed_threshold": largest_passing if separates else None,
            }
        return summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "study": "overlap_boundary_sweep",
            "worlds_per_cell": self.worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "n_units": N_UNITS,
            "propensities": list(PROPENSITIES),
            "event_rates": list(EVENT_RATES),
            "methods": list(METHODS),
            "nominal_coverage": NOMINAL_COVERAGE,
            "coverage_tolerance": COVERAGE_LOWER_BOUND,
            "acted_fraction": ACTED_FRACTION,
            "boundary": self.boundary_by_rate(),
            "boundary_by_asymmetry": self.boundary_by_asymmetry(),
            "cells": [cell.to_dict() for cell in self.cells],
            "scope_note": (
                "One mechanism, one policy, one estimator family. The boundary is where "
                "this evaluator stops covering on this generator; it is not a general "
                "theorem about doubly robust inference, and the effect is held at a "
                "constant fraction of the event rate so cells compare like with like. "
                "The asymmetry threshold is measured on this grid only: A has not been "
                "checked outside this generator family, and a design whose propensity "
                "varies with X is not covered by it at all."
            ),
        }


def _score_shape(paired: np.ndarray) -> float:
    centred = paired - paired.mean()
    variance = float(np.mean(centred**2))
    if variance <= 0:
        return 0.0
    return float(np.mean(centred**3) / variance**1.5)


def run_sweep(
    *,
    worlds: int = 1_000,
    seed: int = 20260924,
    propensities: Sequence[float] = PROPENSITIES,
    event_rates: Sequence[float] = EVENT_RATES,
    methods: Sequence[str] = METHODS,
) -> BoundaryReport:
    """Score every (propensity, event rate, method) cell on common worlds."""

    started = time.perf_counter()
    report = BoundaryReport(
        worlds=worlds, seed=seed, started_at=datetime.now(UTC).isoformat(timespec="seconds")
    )

    for rate in event_rates:
        for propensity in propensities:
            # One seed namespace per design cell, keyed on its identity so the
            # cell is reproducible on its own.
            key = f"{rate}:{propensity}"
            namespace = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
            collected: dict[str, dict[str, list[float]]] = {
                method: {"estimate": [], "low": [], "high": [], "truth": [], "skew": []}
                for method in methods
            }
            control_events: list[float] = []

            for world_index in range(worlds):
                rng = np.random.default_rng([seed, namespace, world_index])
                world = _draw(rate, propensity, rng)
                control_events.append(world["control_events"])
                scores = dr_action_scores(
                    world["reward"], world["action"], world["design"], world["means"]
                )
                paired = (
                    scores.to_numpy()[
                        np.arange(N_UNITS), (world["policy_1"] == CONTACT).astype(int)
                    ]
                    - scores[HOLD].to_numpy()
                )
                for method in methods:
                    contrast = paired_contrast(
                        scores,
                        world["policy_1"],
                        world["policy_0"],
                        interval_method=method,
                        effective_df_floor=1.0,
                    )
                    bucket = collected[method]
                    bucket["estimate"].append(contrast.delta)
                    bucket["low"].append(contrast.ci_low)
                    bucket["high"].append(contrast.ci_high)
                    bucket["truth"].append(world["finite_truth"])
                    bucket["skew"].append(_score_shape(paired))

            for method, bucket in collected.items():
                estimate = np.asarray(bucket["estimate"])
                low = np.asarray(bucket["low"])
                high = np.asarray(bucket["high"])
                truth = np.asarray(bucket["truth"])
                covered = int(np.sum((low <= truth) & (truth <= high)))
                spread = float(estimate.std(ddof=1))
                required = 2 * 1.959963984540054 * spread
                coverage_low, coverage_high = _wilson(covered, worlds)
                report.cells.append(
                    CellResult(
                        propensity=propensity,
                        # Rounded: abs(0.8 - 0.5) is 0.30000000000000004 in
                        # binary floating point, which would land in the
                        # artifact and break any lookup keyed on the value.
                        imbalance=round(abs(propensity - 0.5), 4),
                        event_rate=rate,
                        method=method,
                        worlds=worlds,
                        coverage=covered / worlds,
                        coverage_ci_low=coverage_low,
                        coverage_ci_high=coverage_high,
                        width_ratio=float(np.mean(high - low) / required)
                        if required > 0
                        else float("nan"),
                        mean_score_skewness=float(np.mean(bucket["skew"])),
                        mean_control_events=float(np.mean(control_events)),
                        bias=float(np.mean(estimate - truth)),
                        mc_se=float(spread / math.sqrt(worlds)),
                    )
                )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: BoundaryReport) -> str:
    payload = report.to_dict()
    lines = [
        "# Overlap boundary: where the DR interval stops covering",
        "",
        f"{report.worlds:,} worlds per cell · N = {N_UNITS:,} · seed {report.seed} · "
        f"{report.runtime_seconds:.0f} s",
        "",
        payload["scope_note"],
        "",
    ]
    for method in report.to_dict()["methods"]:
        lines.extend(
            [
                f"## {method}",
                "",
                "| event rate | " + " | ".join(f"e={p:g}" for p in PROPENSITIES) + " |",
                "|---|" + "---|" * len(PROPENSITIES),
            ]
        )
        for rate in EVENT_RATES:
            row = [f"{rate:.1%}"]
            for propensity in PROPENSITIES:
                cell = next(
                    (
                        c
                        for c in report.cells
                        if c.method == method
                        and c.event_rate == rate
                        and c.propensity == propensity
                    ),
                    None,
                )
                row.append(
                    "—" if cell is None else f"{cell.coverage:.3f}{'' if cell.passes else ' ✗'}"
                )
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines.extend(
        [
            "## Boundary",
            "",
            "| method | event rate | largest passing imbalance | smallest failing |",
            "|---|---|---|---|",
        ]
    )
    for entry in report.boundary_by_rate().values():
        passing = entry["largest_passing_imbalance"]
        failing = entry["smallest_failing_imbalance"]
        lines.append(
            f"| {entry['method']} | {entry['event_rate']:.1%} "
            f"| {'none' if passing is None else f'{passing:.2f}'} "
            f"| {'none' if failing is None else f'{failing:.2f}'} |"
        )
    lines.append("")
    lines.extend(
        [
            "The imbalance boundary **moves with the event rate**, so imbalance is not a rule "
            "a gate can apply. The asymmetry index",
            "",
            "> `A = |1 - 2e| / sqrt(n * h * rate * e * (1 - e))`",
            "",
            "combines all four factors. Whether it orders these cells cleanly is measured, "
            "not assumed:",
            "",
            "| method | cells failing | largest passing A | smallest failing A | separates? |",
            "|---|---|---|---|---|",
        ]
    )
    for entry in report.boundary_by_asymmetry().values():
        passing = entry["largest_passing_asymmetry"]
        failing = entry["smallest_failing_asymmetry"]
        lines.append(
            f"| {entry['method']} | {entry['n_failing']}/{entry['n_cells']} "
            f"| {'none' if passing is None else f'{passing:.3f}'} "
            f"| {'none' if failing is None else f'{failing:.3f}'} "
            f"| {'yes' if entry['separates'] else '**no**'} |"
        )
    lines.append("")
    for entry in report.boundary_by_asymmetry().values():
        if entry["separates"] and entry["licensed_threshold"] is not None:
            lines.append(
                f"- `{entry['method']}`: licensed up to **A = "
                f"{entry['licensed_threshold']:.3f}** -- the largest value actually "
                "measured as covering; the crossing is bracketed, not interpolated."
            )
        elif not entry["separates"]:
            lines.append(
                f"- `{entry['method']}`: **A does not separate** these cells -- "
                f"{len(entry['straddling_cells'])} straddle the crossing, so A is no "
                "better a rule here than imbalance was."
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--output-dir", default="reports/v4/overlap_boundary")
    args = parser.parse_args(argv)

    report = run_sweep(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "overlap_boundary.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "OVERLAP_BOUNDARY.md").write_text(render_markdown(report), encoding="utf-8")

    for cell in report.cells:
        flag = "ok  " if cell.passes else "FAIL"
        print(
            f"[{flag}] rate {cell.event_rate:.1%} e={cell.propensity:<5g} {cell.method:<20} "
            f"coverage {cell.coverage:.3f} [{cell.coverage_ci_low:.3f}] "
            f"width_ratio {cell.width_ratio:.3f} skew {cell.mean_score_skewness:>7.1f} "
            f"control events {cell.mean_control_events:.0f}"
        )
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
