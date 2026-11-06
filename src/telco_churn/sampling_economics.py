"""R08: is the enriched sampling design worth what it costs?

The V4 contribution is not the estimator -- paired AIPW is standard -- it is
the *sampling design*: recruit disproportionately from the region where two
policies disagree, since only that region carries information about their
contrast.  That claim has never been evaluated, and it is easy to make it
look good by accident.

Two ways it can be made to look good dishonestly, both avoided here:

* **Comparing at equal N.** Enriched sampling buys precision by spending
  screening effort, so at equal recruited N it wins by construction.  The
  runbook is explicit that designs are compared at **equal precision**, with
  screening, recruitment and label costs all counted.
* **Forcing the sample size.** Bernoulli inclusion makes the realised sample
  fluctuate.  Rounding it back to the target while keeping the old weights
  would quietly bias the estimator, so the realised size is whatever it is
  and the weights match it.

The designs, from the runbook, at frame ``N = 10,000`` and a target expected
recruitment of ``0.2N``:

``uniform``
    ``q = 0.2`` for everyone.
``enriched``
    ``q_D = min(0.8, [0.2 - 0.05(1-d)] / d)`` inside the disagreement region
    and ``q_agree = (0.2 - d * q_D) / (1 - d)`` outside it, where ``d`` is the
    frame's actual disagreement share.  Both designs therefore recruit the
    same number of accounts in expectation, and the agreement region keeps a
    positive inclusion probability rather than being dropped -- a design that
    drops it cannot estimate the frame-level contrast at all.

Three disagreement fractions are swept because the enrichment has no room to
work when almost everything disagrees: at ``d = 0.5`` the formula pushes
``q_D`` barely above ``0.2``, and the two designs should converge.  Reporting
only ``d = 0.05`` would overstate the method.

Each design is scored against **the truth its own variance targets**, which
is not optional bookkeeping.  The finite-frame variance treats the frame's
scores as fixed and reports only what redrawing the recruitment would move,
so it targets the *census* value -- what a full recruitment of this frame
would have produced.  The superpopulation variance adds the score noise that
survives a census, so it targets the underlying effect.  A first run of this
study scored the finite-frame interval against the underlying effect and
found coverage of 0.61; that was not a broken estimator, it was the wrong
truth.  The mismatch is kept as a **declared negative control**, because it
is the mistake a reader of the narrow interval would actually make.

The economics are kept separate and labelled.  Hillstrom has no cost ledger,
so unit costs here are **declared prices**, and the output is a cost ratio at
matched precision rather than a profit claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    cost_to_precision,
    dr_action_scores,
    enriched_sampling_contrast,
)
from .validity_suite import COVERAGE_LOWER_BOUND, _sigmoid, _wilson

__all__ = [
    "COST_MODEL",
    "DESIGNS",
    "DISAGREEMENT_FRACTIONS",
    "DesignSummary",
    "SamplingEconomicsReport",
    "inclusion_probabilities",
    "main",
    "run_sampling_economics",
]

HOLD = "hold"
CONTACT = "contact"

FRAME_SIZE = 10_000
TARGET_RECRUITMENT_SHARE = 0.2
#: Floor on the agreement region's inclusion probability.  The runbook's
#: formula reserves this much of the budget for coverage outside D, because a
#: design that never looks there cannot notice being wrong about it.
AGREEMENT_RESERVE = 0.05
MAX_DISAGREEMENT_INCLUSION = 0.8
PROPENSITY = 0.5
EVENT_RATE = 0.05

DISAGREEMENT_FRACTIONS: tuple[float, ...] = (0.05, 0.20, 0.50)
DESIGNS: tuple[str, ...] = ("uniform", "enriched")

#: Declared prices in reward units, not postings.  Screening is cheap and
#: recruiting plus observing an outcome is not, which is the asymmetry the
#: enriched design is trying to exploit; if screening cost as much as
#: recruiting there would be nothing to gain.
COST_MODEL: dict[str, float] = {
    "cost_per_screened": 0.01,
    "cost_per_recruited": 1.00,
    "cost_per_outcome": 0.50,
}


def _namespace(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def inclusion_probabilities(
    disagrees: np.ndarray, design: str
) -> tuple[np.ndarray, dict[str, float]]:
    """Per-unit inclusion probability, and the design constants behind it.

    ``d`` is the frame's *actual* disagreement share, not the nominal one:
    the frame is drawn at random, so forcing the nominal value into the
    formula would leave the realised weights inconsistent with the realised
    design.
    """

    share = float(np.mean(disagrees))
    if design == "uniform":
        return (
            np.full(len(disagrees), TARGET_RECRUITMENT_SHARE),
            {
                "disagreement_share": share,
                "q_disagreement": TARGET_RECRUITMENT_SHARE,
                "q_agreement": TARGET_RECRUITMENT_SHARE,
            },
        )
    if design != "enriched":
        raise ValueError(f"unknown design {design!r}; declared: {DESIGNS}")

    if share <= 0:
        # Nothing to enrich toward; fall back to uniform rather than divide
        # by zero and call the result a design.
        return (
            np.full(len(disagrees), TARGET_RECRUITMENT_SHARE),
            {
                "disagreement_share": 0.0,
                "q_disagreement": TARGET_RECRUITMENT_SHARE,
                "q_agreement": TARGET_RECRUITMENT_SHARE,
                "degenerate": True,
            },
        )

    numerator = TARGET_RECRUITMENT_SHARE - AGREEMENT_RESERVE * (1.0 - share)
    q_disagreement = min(MAX_DISAGREEMENT_INCLUSION, numerator / share)
    q_agreement = (
        (TARGET_RECRUITMENT_SHARE - share * q_disagreement) / (1.0 - share) if share < 1.0 else 0.0
    )
    q_agreement = float(np.clip(q_agreement, 1e-6, 1.0))
    probability = np.where(disagrees, q_disagreement, q_agreement)
    return probability.astype(float), {
        "disagreement_share": share,
        "q_disagreement": float(q_disagreement),
        "q_agreement": q_agreement,
    }


def _frame(disagreement_fraction: float, rng: np.random.Generator) -> dict[str, Any]:
    """One frame of accounts with two frozen policies and known truth."""

    x = rng.random(FRAME_SIZE)
    z = rng.standard_normal(FRAME_SIZE)
    p0 = EVENT_RATE * (0.4 + 1.2 * _sigmoid(1.0 * (2 * x - 1) + 0.4 * z))
    # The policies disagree on the top slice of x, and that is also where the
    # effect lives -- an enriched design that recruited from a region with no
    # effect would be enriching toward noise.
    disagrees = x >= (1.0 - disagreement_fraction)
    tau = np.where(disagrees, 0.3 * EVENT_RATE, 0.0)

    treatment = (rng.random(FRAME_SIZE) < PROPENSITY).astype(int)
    reward = 1.0 - (rng.random(FRAME_SIZE) < p0 - tau * treatment).astype(float)

    return {
        "reward": reward,
        "action": np.where(treatment == 1, CONTACT, HOLD),
        "design": pd.DataFrame(
            {HOLD: np.full(FRAME_SIZE, 1 - PROPENSITY), CONTACT: np.full(FRAME_SIZE, PROPENSITY)}
        ),
        "mean": pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)}),
        "policy_1": np.where(disagrees, CONTACT, HOLD),
        "policy_0": np.full(FRAME_SIZE, HOLD),
        "disagrees": disagrees,
        "finite_truth": float(np.mean(np.where(disagrees, tau, 0.0))),
    }


@dataclass
class DesignSummary:
    disagreement_fraction: float
    design: str
    readout: str
    variance_target: str
    truth: str
    is_negative_control: bool
    worlds: int
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    mean_half_width: float
    mean_recruited: float
    mean_recruited_in_disagreement: float
    q_disagreement: float
    q_agreement: float
    bias: float
    mc_se: float
    per_unit_variance: float

    @property
    def covers(self) -> bool:
        return self.coverage_ci_low >= COVERAGE_LOWER_BOUND

    @property
    def passes(self) -> bool:
        """A declared control is scored but never gated."""

        return True if self.is_negative_control else self.covers

    @property
    def fired(self) -> bool:
        return self.is_negative_control and self.coverage_ci_high < COVERAGE_LOWER_BOUND

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "covers": self.covers,
            "passes": self.passes,
            "fired": self.fired,
        }


@dataclass
class SamplingEconomicsReport:
    worlds: int
    seed: int
    started_at: str
    summaries: list[DesignSummary] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def cost_at_matched_precision(self) -> dict[str, Any]:
        """What each design costs to reach the *same* interval width.

        Comparing raw recruited N would reward the design that simply
        recruits more.  Instead each design is costed for the sample size it
        would need to hit a common target half-width, with screening counted:
        the enriched design screens the whole frame to find its region, and
        that is part of what it costs.
        """

        out: dict[str, Any] = {}
        for fraction in DISAGREEMENT_FRACTIONS:
            # Cost is priced from the interval a study would actually
            # report for a forward-looking claim, which is the
            # superpopulation one.  Pricing the narrow finite-frame interval
            # would buy precision the design does not have.
            rows = {
                row.design: row
                for row in self.summaries
                if row.disagreement_fraction == fraction and row.readout == "super_vs_effect"
            }
            if len(rows) < len(DESIGNS):
                continue
            # A common target: the wider of the two designs' achieved widths,
            # so neither is costed for precision it never demonstrated.
            target = max(row.mean_half_width for row in rows.values())
            costed: dict[str, Any] = {}
            for design, row in rows.items():
                # Screening ratio: how many accounts must be looked at per
                # account recruited. Uniform screens only who it recruits.
                ratio = 1.0 / TARGET_RECRUITMENT_SHARE if design == "enriched" else 1.0
                costed[design] = cost_to_precision(
                    row.per_unit_variance,
                    target_half_width=target,
                    screening_ratio=ratio,
                    **COST_MODEL,
                )
            uniform_cost = costed["uniform"]["total_cost"]
            enriched_cost = costed["enriched"]["total_cost"]
            out[f"d={fraction}"] = {
                "disagreement_fraction": fraction,
                "target_half_width": target,
                "uniform": costed["uniform"],
                "enriched": costed["enriched"],
                "cost_ratio_enriched_over_uniform": (
                    round(enriched_cost / uniform_cost, 4) if uniform_cost else float("nan")
                ),
                "enriched_is_cheaper": enriched_cost < uniform_cost,
            }
        return out

    def to_dict(self) -> dict[str, Any]:
        costs = self.cost_at_matched_precision()
        return {
            "study": "R08_sampling_economics",
            "worlds_per_cell": self.worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "frame_size": FRAME_SIZE,
            "target_recruitment_share": TARGET_RECRUITMENT_SHARE,
            "agreement_reserve": AGREEMENT_RESERVE,
            "propensity": PROPENSITY,
            "event_rate": EVENT_RATE,
            "disagreement_fractions": list(DISAGREEMENT_FRACTIONS),
            "designs": list(DESIGNS),
            "cost_model": COST_MODEL,
            "cost_source": "declared prices in reward units, not postings",
            "readouts": [
                {
                    "readout": name,
                    "variance_target": target,
                    "truth": truth,
                    "is_negative_control": control,
                }
                for name, target, truth, control in READOUTS
            ],
            "all_gated_readouts_cover": all(
                row.passes for row in self.summaries if not row.is_negative_control
            ),
            "designs_that_undercover": [
                f"d={row.disagreement_fraction}:{row.design}:{row.readout}"
                for row in self.summaries
                if not row.is_negative_control and not row.covers
            ],
            "controls_that_fired": [
                f"d={row.disagreement_fraction}:{row.design}"
                for row in self.summaries
                if row.is_negative_control and row.fired
            ],
            "cost_at_matched_precision": costs,
            "enriched_cheaper_at": [
                key for key, entry in costs.items() if entry["enriched_is_cheaper"]
            ],
            "summaries": [row.to_dict() for row in self.summaries],
            "scope_note": (
                "One generator, one frame size, one capacity-free contrast. Costs are "
                "declared prices, so the output is a cost ratio at matched precision "
                "and not a profit claim. Comparing designs at equal recruited N would "
                "flatter the enriched one; this compares them at equal precision."
            ),
        }


#: ``(readout, variance_target, truth, is_negative_control)``.
#:
#: The finite-frame interval targets the census value; the superpopulation
#: interval targets the underlying effect.  The third row pairs the narrow
#: interval with the wrong truth on purpose, because that is the mistake a
#: reader of a finite-frame interval would actually make.
READOUTS: tuple[tuple[str, str, str, bool], ...] = (
    ("finite_vs_census", "finite_frame", "census", False),
    ("super_vs_effect", "superpopulation", "effect", False),
    ("finite_vs_effect", "finite_frame", "effect", True),
)


def run_sampling_economics(*, worlds: int = 400, seed: int = 20260929) -> SamplingEconomicsReport:
    """Score both designs at each disagreement fraction on common frames."""

    started = time.perf_counter()
    report = SamplingEconomicsReport(
        worlds=worlds, seed=seed, started_at=datetime.now(UTC).isoformat(timespec="seconds")
    )

    for fraction in DISAGREEMENT_FRACTIONS:
        namespace = _namespace(f"R08:{fraction}")
        buckets: dict[tuple[str, str], dict[str, list[float]]] = {
            (design, readout): {
                "covered": [],
                "half_width": [],
                "recruited": [],
                "recruited_d": [],
                "error": [],
                "q_d": [],
                "q_a": [],
                "variance": [],
            }
            for design in DESIGNS
            for readout, _target, _truth, _control in READOUTS
        }

        for index in range(worlds):
            rng = np.random.default_rng([seed, namespace, index])
            frame = _frame(fraction, rng)
            scores = dr_action_scores(
                frame["reward"], frame["action"], frame["design"], frame["mean"]
            )
            # The census value: what recruiting the whole frame would give.
            # This is what a finite-frame variance treats as its target, and
            # it differs from the effect by the outcome noise in the frame.
            paired = _gather(scores, frame["policy_1"]) - _gather(scores, frame["policy_0"])
            truths = {
                "census": float(np.mean(paired)),
                "effect": frame["finite_truth"],
            }
            draw = rng.random(FRAME_SIZE)

            for design in DESIGNS:
                probability, constants = inclusion_probabilities(frame["disagrees"], design)
                # One uniform draw, reused across designs, so the two see the
                # same luck rather than differing by an extra random stream.
                sampled = draw < probability
                if not sampled[frame["disagrees"]].any():
                    continue
                for readout, target, truth_name, _control in READOUTS:
                    contrast = enriched_sampling_contrast(
                        scores,
                        frame["policy_1"],
                        frame["policy_0"],
                        sampled=sampled,
                        inclusion_probability=probability,
                        frame_size=FRAME_SIZE,
                        variance_target=target,
                    )
                    truth = truths[truth_name]
                    bucket = buckets[(design, readout)]
                    bucket["covered"].append(float(contrast.ci_low <= truth <= contrast.ci_high))
                    bucket["half_width"].append((contrast.ci_high - contrast.ci_low) / 2)
                    bucket["recruited"].append(float(sampled.sum()))
                    bucket["recruited_d"].append(float((sampled & frame["disagrees"]).sum()))
                    bucket["error"].append(contrast.delta - truth)
                    bucket["q_d"].append(constants["q_disagreement"])
                    bucket["q_a"].append(constants["q_agreement"])
                    # Variance per recruited unit, which is what a cost model
                    # needs in order to price a target precision.
                    bucket["variance"].append(contrast.se**2 * max(sampled.sum(), 1))

        for design in DESIGNS:
            for readout, target, truth_name, control in READOUTS:
                bucket = buckets[(design, readout)]
                if not bucket["covered"]:
                    continue
                covered = int(sum(bucket["covered"]))
                total = len(bucket["covered"])
                low, high = _wilson(covered, total)
                errors = np.asarray(bucket["error"], dtype=float)
                report.summaries.append(
                    DesignSummary(
                        disagreement_fraction=fraction,
                        design=design,
                        readout=readout,
                        variance_target=target,
                        truth=truth_name,
                        is_negative_control=control,
                        worlds=total,
                        coverage=round(covered / total, 4),
                        coverage_ci_low=round(low, 4),
                        coverage_ci_high=round(high, 4),
                        mean_half_width=float(np.mean(bucket["half_width"])),
                        mean_recruited=float(np.mean(bucket["recruited"])),
                        mean_recruited_in_disagreement=float(np.mean(bucket["recruited_d"])),
                        q_disagreement=float(np.mean(bucket["q_d"])),
                        q_agreement=float(np.mean(bucket["q_a"])),
                        bias=float(np.mean(errors)),
                        mc_se=float(np.std(errors, ddof=1) / np.sqrt(total)),
                        per_unit_variance=float(np.mean(bucket["variance"])),
                    )
                )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: SamplingEconomicsReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R08 — sampling design and its economics",
        "",
        f"{report.worlds:,} worlds per cell · frame {FRAME_SIZE:,} · "
        f"target recruitment {TARGET_RECRUITMENT_SHARE:.0%} · "
        f"{report.runtime_seconds:.0f} s",
        "",
        payload["scope_note"],
        "",
        "Each interval is scored against **the truth its own variance targets**. "
        "The finite-frame variance treats the frame's scores as fixed, so it targets "
        "the census value; the superpopulation variance adds the score noise that "
        "survives a census, so it targets the effect.",
        "",
        "| d | design | readout | q_D | q_agree | recruited | in D | coverage | half width | |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report.summaries:
        if row.is_negative_control:
            verdict = "**fired**" if row.fired else "control did not fire"
        else:
            verdict = "" if row.covers else "✗"
        lines.append(
            f"| {row.disagreement_fraction:.2f} | {row.design} | `{row.readout}` "
            f"| {row.q_disagreement:.3f} "
            f"| {row.q_agreement:.3f} | {row.mean_recruited:,.0f} "
            f"| {row.mean_recruited_in_disagreement:,.0f} "
            f"| {row.coverage:.3f} [{row.coverage_ci_low:.3f}] "
            f"| {row.mean_half_width:.5f} | {verdict} |"
        )
    lines.extend(
        [
            "",
            "`finite_vs_effect` is a **declared negative control**: the narrow interval "
            "read as though it said something about the underlying effect. It is expected "
            "to under-cover and is never gated on.",
            "",
            "## Cost at matched precision",
            "",
            "Each design is costed for the sample it would need to reach a **common** "
            "target half-width, with screening counted, using the superpopulation "
            "interval -- the one a forward-looking claim would actually report. "
            "Comparing raw recruited N would reward whichever design recruits more.",
            "",
            "| d | target half width | uniform cost | enriched cost | ratio | cheaper |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in payload["cost_at_matched_precision"].values():
        lines.append(
            f"| {entry['disagreement_fraction']:.2f} | {entry['target_half_width']:.5f} "
            f"| {entry['uniform']['total_cost']:,.0f} "
            f"| {entry['enriched']['total_cost']:,.0f} "
            f"| {entry['cost_ratio_enriched_over_uniform']:.3f} "
            f"| {'enriched' if entry['enriched_is_cheaper'] else '**uniform**'} |"
        )
    lines.extend(
        [
            "",
            f"Costs use **{payload['cost_source']}**: "
            + ", ".join(f"{key} = {value}" for key, value in COST_MODEL.items())
            + ".",
            "",
            "At `d = 0.50` the formula can barely enrich -- `q_D` is pushed only a little "
            "above the uniform 0.2 -- so the two designs are expected to converge there. "
            "Reporting only the smallest `d` would overstate what the design buys.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20260929)
    parser.add_argument("--output-dir", default="reports/v4/sampling_economics")
    args = parser.parse_args(argv)

    report = run_sampling_economics(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "sampling_economics.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "SAMPLING_ECONOMICS.md").write_text(render_markdown(report), encoding="utf-8")
    for row in report.summaries:
        print(
            f"[{'ok  ' if row.covers else 'FAIL'}] d={row.disagreement_fraction:.2f} "
            f"{row.design:<9} recruited {row.mean_recruited:,.0f} "
            f"coverage {row.coverage:.3f} half width {row.mean_half_width:.5f}"
        )
    for key, entry in report.to_dict()["cost_at_matched_precision"].items():
        print(
            f"  {key}: cost ratio {entry['cost_ratio_enriched_over_uniform']:.3f} "
            f"({'enriched' if entry['enriched_is_cheaper'] else 'uniform'} cheaper)"
        )
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
