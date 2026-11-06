"""V08: does the capped batch-policy interval cover what it claims to cover?

The runbook declared V08 blocked -- *"blocked on G06: the batch-policy
interval has no validated domain yet, so there is nothing to score it
against"*.  G06 now exists as :func:`batch_policy_contrast`, so the blocker
is stale and this is the scenario that scores it.

A capped policy is not a fixed policy.  Under ``floor(fraction * N)`` the set
of units acted on depends on the realised batch: change who turns up and the
cap re-allocates, so the contrast has a source of variation that a fixed
policy does not have.  That is the whole reason the estimator resamples and
re-allocates rather than treating the chosen set as given.

Two targets, and they are not interchangeable:

``future_batch``
    Resamples accounts, so it carries the variation in *who turns up* as well
    as in what they do.  It is scored against the superpopulation truth.
``finite_batch``
    Conditions on this batch.  Narrower by construction.  Scored against the
    finite-frame truth, which is what it actually targets.

The third readout is the point of the scenario.  ``finite_batch`` scored
against the *superpopulation* truth is a **declared negative control**: it is
what happens when someone reports the narrow interval as a forward-looking
guarantee.  It is expected to under-cover, it is never gated on, and if it
ever stopped under-covering that would mean the two targets had collapsed
into one and the warning in :func:`batch_policy_contrast` was empty.

The superpopulation truth is itself estimated, on one large reference frame
drawn once and reused, so its Monte Carlo error is reported alongside it
rather than presented as exact.
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

from .policy_comparison import batch_policy_contrast, dr_action_scores
from .validity_suite import COVERAGE_LOWER_BOUND, NOMINAL_COVERAGE, _wilson

__all__ = [
    "BatchValidationReport",
    "ReadoutSummary",
    "main",
    "run_v08",
    "superpopulation_truth",
]

HOLD = "hold"
CONTACT = "contact"

N_UNITS = 3_000
CAPACITY_FRACTION = 0.2
PROPENSITY = 0.5

#: A continuous reward with strong effect heterogeneity, and why it has to be.
#:
#: The first draft of this scenario used the repo's usual rare binary outcome
#: and every readout covered at 1.000, including the negative control.  That
#: is not a pass, it is a scenario that cannot fail.  The reason is structural
#: rather than a matter of tuning: the batch-to-batch variation of the truth
#: scales as ``sd(tau)/sqrt(n)`` and the outcome noise as
#: ``sd(score)/sqrt(n)``, so **n cancels** and the ratio is fixed by the
#: generator.  For a binary reward at a few percent, ``sd(score)`` is about
#: ``2*sqrt(p(1-p)) ~ 0.9`` against ``sd(tau) ~ 0.07``: composition variation
#: is an order of magnitude below outcome noise, the two targets coincide,
#: and no sample size recovers the distinction.
#:
#: A capped policy only matters when *who gets picked* moves the answer, so
#: the scenario is set where that is true: a continuous reward whose noise is
#: small next to the spread of the effect.
EFFECT_SPREAD = 1.0

#: Two regimes, because whether the distinction *matters* is itself the
#: question.  Outcome noise sets the width of both intervals; the spread
#: of the effect sets how much the truth moves when the cap re-allocates.
#: Only when the second is comparable to the first can reporting the
#: batch-conditional interval as a forward-looking one actually mislead
#: anyone -- so the scenario runs one regime either side of that line and
#: reports which is which instead of tuning until the control fires.
REGIMES: tuple[tuple[str, float], ...] = (
    ("noisy_outcome", 0.25),
    ("predictable_outcome", 0.04),
)

#: Rows in the frame used to pin the superpopulation truth.  Large enough that
#: its own Monte Carlo error is an order of magnitude under the coverage
#: tolerance, and reported either way.
REFERENCE_UNITS = 400_000
REFERENCE_SEED = 20260927

#: Bootstrap resamples inside each world.  The runbook's 2,000 is right for a
#: reported interval; inside a coverage loop it is the dominant cost, and 600
#: leaves the quantile noise well under the coverage tolerance.
RESAMPLES = 600


def _namespace(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def _frame(n_units: int, rng: np.random.Generator, noise: float) -> dict[str, Any]:
    """One batch, with the analytic conditional means the truth needs.

    The effect is continuous and *signed*: acting on a low-``x1`` account
    makes things worse.  A capped policy that ranks well must therefore both
    find the accounts worth acting on and stay off the ones that are not,
    which is the behaviour a cap is supposed to reward and the reason which
    accounts get picked moves the answer at all.
    """

    x1 = rng.random(n_units)
    x2 = rng.random(n_units)
    mu0 = 1.0 + 0.5 * x1 - 0.3 * x2
    tau = EFFECT_SPREAD * (2.0 * x1 - 1.0)

    treatment = (rng.random(n_units) < PROPENSITY).astype(int)
    reward = mu0 + tau * treatment + noise * rng.standard_normal(n_units)

    # Policy 1 ranks on a noisy view of the effect; policy 0 ranks on a
    # covariate unrelated to it.  Both are frozen scoring functions: neither
    # is refitted inside a resample, so the interval measures allocation
    # variability rather than learning variability.
    score_1 = tau + 0.05 * rng.standard_normal(n_units)
    score_0 = x2 + 0.01 * rng.standard_normal(n_units)

    return {
        "reward": reward,
        "action": np.where(treatment == 1, CONTACT, HOLD),
        "design": pd.DataFrame(
            {HOLD: np.full(n_units, 1 - PROPENSITY), CONTACT: np.full(n_units, PROPENSITY)}
        ),
        "mean": pd.DataFrame({HOLD: mu0, CONTACT: mu0 + tau}),
        "score_1": score_1,
        "score_0": score_0,
        "unit_id": [f"u{index}" for index in range(n_units)],
        "n_units": n_units,
    }


def _analytic_contrast(frame: dict[str, Any]) -> float:
    """The capped contrast this batch would show if the means were known."""

    n_units = frame["n_units"]
    capacity = math.floor(n_units * CAPACITY_FRACTION)
    means = frame["mean"]
    treated = means[CONTACT].to_numpy()
    idle = means[HOLD].to_numpy()

    def value_of(score: np.ndarray) -> float:
        # Same rule the estimator uses: highest score first, cap at capacity.
        chosen = np.zeros(n_units, dtype=bool)
        chosen[np.argsort(-score, kind="stable")[:capacity]] = True
        return float(np.mean(np.where(chosen, treated, idle)))

    return value_of(frame["score_1"]) - value_of(frame["score_0"])


def superpopulation_truth(
    *,
    noise: float = 0.25,
    reference_units: int = REFERENCE_UNITS,
    seed: int = REFERENCE_SEED,
) -> tuple[float, float]:
    """The contrast a fresh batch would show on average, and its MC error.

    Estimated on one large reference frame rather than derived in closed
    form, because the cap makes the selected set depend on the realised score
    distribution.  The error is returned so the caller can see it is small
    rather than be told so.
    """

    rng = np.random.default_rng(seed)
    frame = _frame(reference_units, rng, noise)
    value = _analytic_contrast(frame)

    # Split the reference frame into blocks and take the spread of their
    # block-level contrasts as the error of the whole.
    blocks = 20
    size = reference_units // blocks
    block_values = []
    for index in range(blocks):
        start = index * size
        piece = {
            "mean": frame["mean"].iloc[start : start + size].reset_index(drop=True),
            "score_1": frame["score_1"][start : start + size],
            "score_0": frame["score_0"][start : start + size],
            "n_units": size,
        }
        block_values.append(_analytic_contrast(piece))
    error = float(np.std(block_values, ddof=1) / math.sqrt(blocks))
    return float(value), error


@dataclass
class ReadoutSummary:
    readout: str
    regime: str
    reward_noise: float
    target: str
    truth: str
    is_negative_control: bool
    worlds: int
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    mean_width: float
    bias: float
    mc_se: float
    #: sd of the finite truth across batches, over the mean interval half
    #: width.  Below ~1 the two targets are indistinguishable at this width
    #: and the control has nothing to detect.
    materiality: float = 0.0

    @property
    def passes(self) -> bool:
        """Negative controls are scored but never gated."""

        if self.is_negative_control:
            return True
        return self.coverage_ci_low >= COVERAGE_LOWER_BOUND

    @property
    def material(self) -> bool:
        """Could this control detect anything at this interval width?"""

        return self.materiality >= 1.0

    @property
    def fired(self) -> bool:
        """A negative control has done its job when it under-covers."""

        return self.is_negative_control and self.coverage_ci_high < COVERAGE_LOWER_BOUND

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "passes": self.passes,
            "fired": self.fired,
            "material": self.material,
        }


@dataclass
class BatchValidationReport:
    worlds: int
    seed: int
    started_at: str
    truths: dict[str, dict[str, float]] = field(default_factory=dict)
    summaries: list[ReadoutSummary] = field(default_factory=list)
    runtime_seconds: float = 0.0

    @property
    def gated(self) -> list[ReadoutSummary]:
        return [item for item in self.summaries if not item.is_negative_control]

    @property
    def controls(self) -> list[ReadoutSummary]:
        return [item for item in self.summaries if item.is_negative_control]

    @property
    def gate_passed(self) -> bool:
        """Every gated readout covers, and every control that *could* fire did.

        A control is only evidence where the distinction it probes is
        material.  When the batch-to-batch movement of the truth is small
        next to the interval width, reporting the conditional interval as a
        forward-looking one is undetectable *and harmless at that width*, so
        an unfired control there says nothing.  Requiring it to fire anyway
        would just be an instruction to tune the generator until it did.

        Where the movement is comparable to the width the control must fire,
        because there the distinction is real and an estimator that blurred
        it would be misleading someone.
        """

        material_controls = [item for item in self.controls if item.material]
        return (
            all(item.passes for item in self.gated)
            and bool(material_controls)
            and all(item.fired for item in material_controls)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "study": "V08_batch_cap_inference",
            "scenario": "V08",
            "worlds": self.worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "n_units": N_UNITS,
            "capacity_fraction": CAPACITY_FRACTION,
            "capacity": math.floor(N_UNITS * CAPACITY_FRACTION),
            "propensity": PROPENSITY,
            "effect_spread": EFFECT_SPREAD,
            "regimes": [{"regime": name, "reward_noise": noise} for name, noise in REGIMES],
            "bootstrap_resamples": RESAMPLES,
            "nominal_coverage": NOMINAL_COVERAGE,
            "coverage_tolerance": COVERAGE_LOWER_BOUND,
            "truths": self.truths,
            "reference_units": REFERENCE_UNITS,
            "gate_passed": self.gate_passed,
            "status": "PASS" if self.gate_passed else "FAIL",
            "failures": [f"{item.regime}:{item.readout}" for item in self.gated if not item.passes],
            "controls_that_did_not_fire": [
                f"{item.regime}:{item.readout}"
                for item in self.controls
                if item.material and not item.fired
            ],
            "controls_with_nothing_to_detect": [
                f"{item.regime}:{item.readout} (materiality {item.materiality:.2f}, below 1)"
                for item in self.controls
                if not item.material
            ],
            "summaries": [item.to_dict() for item in self.summaries],
            "scope_note": (
                "One mechanism, one cap, one balanced design. This scores the capped "
                "batch interval's coverage; it says nothing about capped inference "
                "under an imbalanced design, which the asymmetry index governs "
                "separately."
            ),
        }


def run_v08(*, worlds: int = 400, seed: int = 20260927) -> BatchValidationReport:
    """Score the capped batch interval against both truths it might mean."""

    started = time.perf_counter()
    report = BatchValidationReport(
        worlds=worlds, seed=seed, started_at=datetime.now(UTC).isoformat(timespec="seconds")
    )

    for regime, noise in REGIMES:
        truth_super, truth_error = superpopulation_truth(noise=noise)
        report.truths[regime] = {
            "reward_noise": noise,
            "superpopulation": round(truth_super, 8),
            "superpopulation_mc_se": round(truth_error, 8),
        }

        buckets: dict[str, dict[str, list[float]]] = {
            name: {"covered": [], "width": [], "error": []}
            for name in ("future_vs_super", "finite_vs_finite", "finite_vs_super")
        }
        finite_truths: list[float] = []
        namespace = _namespace(f"V08:{regime}")

        for index in range(worlds):
            rng = np.random.default_rng([seed, namespace, index])
            frame = _frame(N_UNITS, rng, noise)
            truth_finite = _analytic_contrast(frame)
            finite_truths.append(truth_finite)
            scores = dr_action_scores(
                frame["reward"], frame["action"], frame["design"], frame["mean"]
            )

            for target in ("future_batch", "finite_batch"):
                contrast = batch_policy_contrast(
                    scores,
                    score_1=frame["score_1"],
                    score_0=frame["score_0"],
                    unit_id=frame["unit_id"],
                    action_if_selected=CONTACT,
                    action_if_not=HOLD,
                    capacity_fraction=CAPACITY_FRACTION,
                    predicted_reward=frame["mean"],
                    resamples=RESAMPLES,
                    seed=seed + index,
                    target=target,
                )
                width = contrast.ci_high - contrast.ci_low
                pairs = (
                    [("future_vs_super", truth_super)]
                    if target == "future_batch"
                    else [
                        ("finite_vs_finite", truth_finite),
                        ("finite_vs_super", truth_super),
                    ]
                )
                for name, truth in pairs:
                    bucket = buckets[name]
                    bucket["covered"].append(float(contrast.ci_low <= truth <= contrast.ci_high))
                    bucket["width"].append(width)
                    bucket["error"].append(contrast.delta - truth)

        # How far the truth itself moves between batches, against the width
        # the interval offers.  Below 1 there is nothing for the control to
        # detect at this width, and saying so is more useful than tuning.
        truth_spread = float(np.std(finite_truths, ddof=1))
        report.truths[regime]["finite_truth_sd"] = round(truth_spread, 8)

        declared = (
            ("future_vs_super", "future_batch", "superpopulation", False),
            ("finite_vs_finite", "finite_batch", "finite_frame", False),
            ("finite_vs_super", "finite_batch", "superpopulation", True),
        )
        for name, target, truth_name, is_control in declared:
            bucket = buckets[name]
            covered = int(sum(bucket["covered"]))
            low, high = _wilson(covered, worlds)
            errors = np.asarray(bucket["error"], dtype=float)
            mean_width = float(np.mean(bucket["width"]))
            half = mean_width / 2
            report.summaries.append(
                ReadoutSummary(
                    readout=name,
                    regime=regime,
                    reward_noise=noise,
                    target=target,
                    truth=truth_name,
                    is_negative_control=is_control,
                    worlds=worlds,
                    coverage=round(covered / worlds, 4),
                    coverage_ci_low=round(low, 4),
                    coverage_ci_high=round(high, 4),
                    mean_width=round(mean_width, 8),
                    bias=float(np.mean(errors)),
                    mc_se=float(np.std(errors, ddof=1) / math.sqrt(worlds)),
                    materiality=(round(truth_spread / half, 4) if half > 0 else 0.0),
                )
            )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: BatchValidationReport) -> str:
    payload = report.to_dict()
    lines = [
        "# V08 — inference for a capped batch policy",
        "",
        f"{report.worlds:,} worlds per regime · N = {N_UNITS:,} · cap "
        f"{payload['capacity']:,} ({CAPACITY_FRACTION:.0%}) · "
        f"{RESAMPLES:,} resamples · {report.runtime_seconds:.0f} s",
        "",
        f"**{payload['status']}**",
        "",
        payload["scope_note"],
        "",
        "A capped policy re-allocates when the batch changes, so the contrast carries "
        "variation a fixed policy does not. Whether that variation is *material* "
        "depends on the regime, and the scenario runs one either side of the line "
        "rather than assuming it.",
        "",
    ]
    for regime, noise in REGIMES:
        truth = report.truths.get(regime, {})
        lines.extend(
            [
                f"## {regime} (reward noise {noise:g})",
                "",
                f"Superpopulation truth {truth.get('superpopulation', float('nan')):.5f} "
                f"(± {truth.get('superpopulation_mc_se', float('nan')):.5f} Monte Carlo on a "
                f"{REFERENCE_UNITS:,}-row reference frame). The finite truth moves "
                f"{truth.get('finite_truth_sd', float('nan')):.5f} between batches.",
                "",
                "| readout | target | scored against | coverage | width | materiality | |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for item in report.summaries:
            if item.regime != regime:
                continue
            if item.is_negative_control:
                if not item.material:
                    verdict = "nothing to detect"
                else:
                    verdict = "**fired**" if item.fired else "**DID NOT FIRE**"
            else:
                verdict = "" if item.passes else "✗"
            lines.append(
                f"| `{item.readout}` | {item.target} | {item.truth} "
                f"| {item.coverage:.3f} [{item.coverage_ci_low:.3f}, "
                f"{item.coverage_ci_high:.3f}] | {item.mean_width:.5f} "
                f"| {item.materiality:.2f} | {verdict} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Reading the control",
            "",
            "`finite_vs_super` is a **declared negative control**: the narrow, "
            "batch-conditional interval reported as though it were a forward-looking "
            "guarantee. It is never gated on directly.",
            "",
            "**Materiality** is how far the truth moves between batches, over the mean "
            "interval half-width. Below 1 the two targets are indistinguishable *at this "
            "width*, so misreporting one as the other could not mislead anyone and an "
            "unfired control is evidence of nothing. The gate therefore requires a "
            "control to fire only where materiality reaches 1 — anything else would be "
            "an instruction to tune the generator until the control cooperated.",
            "",
        ]
    )
    if payload["controls_with_nothing_to_detect"]:
        lines.extend(f"- {entry}" for entry in payload["controls_with_nothing_to_detect"])
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--output-dir", default="reports/v4/validity_v08")
    args = parser.parse_args(argv)

    report = run_v08(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "v08_batch_cap.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "V08_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for item in report.summaries:
        if item.is_negative_control:
            flag = "no signal" if not item.material else ("fired" if item.fired else "DID NOT FIRE")
        else:
            flag = "ok" if item.passes else "FAIL"
        print(
            f"[{flag:<12}] {item.regime:<20} {item.readout:<18} "
            f"coverage {item.coverage:.3f} [{item.coverage_ci_low:.3f}] "
            f"materiality {item.materiality:.2f}"
        )
    print(f"{report.to_dict()['status']}: {destination}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
