"""V09: two-stage recruitment and treatment, scored against known truth.

Runbook §9.1 declares this scenario and, unusually, declares its own negative
control in the same line: *"current recruitment-only variance là negative-
control mode, không được dùng làm main CI"*.  So there are two things to check
and they pull in opposite directions:

* the **superpopulation** interval, which carries recruitment, assignment and
  outcome noise together, has to cover; and
* the **recruitment-only** interval, which treats the realised scores as
  fixed, has to *fail* to cover -- if it did not, the distinction G03 was
  raised about would not matter.

Two studies, because they answer different questions and mixing their errors
into one coverage number is the mistake the runbook names:

``fixed_frame``
    One X frame is drawn once and held; recruitment, assignment and outcomes
    are redrawn each world.  The target is the contrast on *that* frame.
``redrawn_frame``
    X is redrawn every world too.  The target is the population contrast, so
    the interval has to carry the extra variation in who is in the frame.

The generator is V03's reward mechanism -- heterogeneous effect, marginal ATE
zero, positive policy value -- with recruitment ``q = 0.6`` where ``X1 = 1``
and ``q = 0.1`` where ``X1 = 0``, and a ``q = 1`` boundary cell where
recruitment stops being random at all.
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

from .policy_comparison import enriched_sampling_contrast
from .validity_suite import COVERAGE_LOWER_BOUND, _sigmoid, _wilson

__all__ = [
    "STUDIES",
    "RecruitmentReport",
    "main",
    "run_v09",
    "simulate_frame",
]

HOLD = "hold"
CONTACT = "contact"
FRAME_SIZE = 10_000
TREATMENT_PROPENSITY = 0.5
Q_HIGH = 0.6
Q_LOW = 0.1
STUDIES: tuple[str, ...] = ("fixed_frame", "redrawn_frame")


def simulate_frame(rng: np.random.Generator, n: int = FRAME_SIZE) -> dict[str, Any]:
    """V03's mechanism: heterogeneous effect, zero ATE, positive policy value."""

    x1 = rng.integers(0, 2, size=n)
    z = rng.standard_normal(n)
    p0 = 0.01 + 0.05 * _sigmoid(0.8 * (2 * x1 - 1) + 0.5 * z)
    tau = 0.01 * (2 * x1 - 1)
    return {"x1": x1, "p0": p0, "tau": tau}


def _draw_world(
    frame: dict[str, Any], rng: np.random.Generator, *, q_boundary: bool
) -> dict[str, Any]:
    """Redraw recruitment, assignment and outcomes on a given X frame."""

    x1, p0, tau = frame["x1"], frame["p0"], frame["tau"]
    n = len(x1)
    q = np.ones(n) if q_boundary else np.where(x1 == 1, Q_HIGH, Q_LOW)
    sampled = rng.random(n) < q

    treatment = (rng.random(n) < TREATMENT_PROPENSITY).astype(int)
    probability = p0 - tau * treatment
    reward = 1.0 - (rng.random(n) < probability).astype(float)

    # Scores are the analytic conditional means plus the IPW residual: the
    # evaluator's own doubly robust construction, not an oracle shortcut.
    means = pd.DataFrame({HOLD: 1.0 - p0, CONTACT: 1.0 - (p0 - tau)})
    residual = reward - np.where(treatment == 1, means[CONTACT], means[HOLD])
    scores = means.copy()
    scores[CONTACT] = means[CONTACT] + np.where(
        treatment == 1, residual / TREATMENT_PROPENSITY, 0.0
    )
    scores[HOLD] = means[HOLD] + np.where(
        treatment == 0, residual / (1.0 - TREATMENT_PROPENSITY), 0.0
    )
    policy_1 = np.where(x1 == 1, CONTACT, HOLD)
    policy_0 = np.full(n, HOLD)
    frame_truth = float(np.mean((policy_1 != policy_0) * tau))
    return {
        "scores": scores,
        "policy_1": policy_1,
        "policy_0": policy_0,
        "sampled": sampled,
        "q": q,
        "frame_truth": frame_truth,
    }


@dataclass
class Readout:
    study: str
    variance_target: str
    q_design: str
    worlds: int
    coverage: float
    coverage_ci_low: float
    coverage_ci_high: float
    mean_ci_width: float
    bias: float
    mc_se: float
    is_negative_control: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecruitmentReport:
    worlds: int
    seed: int
    started_at: str
    readouts: list[Readout] = field(default_factory=list)
    runtime_seconds: float = 0.0

    @property
    def failures(self) -> list[Readout]:
        return [
            item
            for item in self.readouts
            if not item.is_negative_control and item.coverage_ci_low < COVERAGE_LOWER_BOUND
        ]

    @property
    def controls_that_did_not_break(self) -> list[Readout]:
        """A negative control that covers correctly has proved nothing."""

        return [
            item
            for item in self.readouts
            if item.is_negative_control and item.coverage_ci_low >= COVERAGE_LOWER_BOUND
        ]

    @property
    def gate_passed(self) -> bool:
        return not self.failures and not self.controls_that_did_not_break and self.worlds >= 1_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": "V09_two_stage_recruitment",
            "status": "PASS"
            if self.gate_passed
            else ("FAIL" if self.worlds >= 1_000 else "SMOKE_ONLY"),
            "gate_passed": self.gate_passed,
            "worlds": self.worlds,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "design": {
                "frame_size": FRAME_SIZE,
                "q_high_when_x1": Q_HIGH,
                "q_low_when_x0": Q_LOW,
                "treatment_propensity": TREATMENT_PROPENSITY,
                "studies": list(STUDIES),
            },
            "failures": [f"{item.study}:{item.q_design}" for item in self.failures],
            "controls_that_did_not_break": [
                f"{item.study}:{item.q_design}" for item in self.controls_that_did_not_break
            ],
            "readouts": [item.to_dict() for item in self.readouts],
            "scope_note": (
                "Recruitment-only intervals are scored as declared negative controls: they "
                "condition on the realised scores and must under-cover a target that also "
                "carries outcome and assignment noise. A pass means the superpopulation "
                "interval covered and the recruitment-only one did not."
            ),
        }


def run_v09(*, worlds: int = 1_000, seed: int = 20260921) -> RecruitmentReport:
    started = time.perf_counter()
    report = RecruitmentReport(
        worlds=worlds, seed=seed, started_at=datetime.now(UTC).isoformat(timespec="seconds")
    )

    for study in STUDIES:
        for q_boundary in (False, True):
            label = "q=1 boundary" if q_boundary else "q=0.6/0.1"
            collected: dict[str, dict[str, list[float]]] = {}
            unestimable: dict[str, list[str]] = {}
            fixed_frame = (
                simulate_frame(np.random.default_rng([seed, 999]))
                if study == "fixed_frame"
                else None
            )

            for world_index in range(worlds):
                # sha256, not hash(): Python randomises string hashing per
                # process, so hash() would give a different world sequence on
                # every run -- the same class of bug the R01 suite just fixed.
                namespace = int(hashlib.sha256(study.encode("utf-8")).hexdigest()[:8], 16)
                rng = np.random.default_rng([seed, namespace, int(q_boundary), world_index])
                frame = fixed_frame if fixed_frame is not None else simulate_frame(rng)
                world = _draw_world(frame, rng, q_boundary=q_boundary)
                for target in ("superpopulation", "finite_frame"):
                    try:
                        result = enriched_sampling_contrast(
                            world["scores"],
                            world["policy_1"],
                            world["policy_0"],
                            sampled=world["sampled"],
                            inclusion_probability=world["q"],
                            variance_target=target,
                        )
                    except Exception as error:  # noqa: BLE001 - unestimable draws are counted
                        unestimable.setdefault(target, []).append(str(error)[:80])
                        continue
                    bucket = collected.setdefault(
                        target, {"estimate": [], "low": [], "high": [], "truth": []}
                    )
                    bucket["estimate"].append(result.delta)
                    bucket["low"].append(result.ci_low)
                    bucket["high"].append(result.ci_high)
                    bucket["truth"].append(world["frame_truth"])

            for target, reasons in unestimable.items():
                print(
                    f"  note: {study}/{label}/{target} had {len(reasons)} unestimable draw(s); "
                    f"first reason: {reasons[0]}"
                )
            for target, bucket in collected.items():
                estimate = np.asarray(bucket["estimate"])
                low = np.asarray(bucket["low"])
                high = np.asarray(bucket["high"])
                truth = np.asarray(bucket["truth"])
                covered = int(np.sum((low <= truth) & (truth <= high)))
                n = len(estimate)
                coverage_low, coverage_high = _wilson(covered, n)
                finite = np.isfinite(high - low)
                report.readouts.append(
                    Readout(
                        study=study,
                        variance_target=target,
                        q_design=label,
                        worlds=n,
                        coverage=covered / n if n else float("nan"),
                        coverage_ci_low=coverage_low,
                        coverage_ci_high=coverage_high,
                        mean_ci_width=float(np.mean((high - low)[finite])) if finite.any() else 0.0,
                        bias=float(np.mean(estimate - truth)),
                        mc_se=float(np.std(estimate, ddof=1) / math.sqrt(n))
                        if n > 1
                        else float("nan"),
                        is_negative_control=target == "finite_frame",
                    )
                )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: RecruitmentReport) -> str:
    payload = report.to_dict()
    lines = [
        "# V09 — two-stage recruitment and treatment",
        "",
        f"{report.worlds:,} worlds per cell · seed {report.seed} · "
        f"{report.runtime_seconds:.0f} s · status **{payload['status']}**",
        "",
        payload["scope_note"],
        "",
        "| Study | Recruitment | Variance target | Coverage | Wilson 95% | CI width | Role |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for item in report.readouts:
        role = "negative control" if item.is_negative_control else "primary"
        lines.append(
            f"| {item.study} | {item.q_design} | {item.variance_target} "
            f"| {item.coverage:.3f} | [{item.coverage_ci_low:.3f}, {item.coverage_ci_high:.3f}] "
            f"| {item.mean_ci_width:.5f} | {role} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--output-dir", default="reports/v4/validity_v09")
    args = parser.parse_args(argv)

    report = run_v09(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "v09_recruitment.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "V09_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for item in report.readouts:
        role = (
            "ctrl"
            if item.is_negative_control
            else ("ok  " if item.coverage_ci_low >= COVERAGE_LOWER_BOUND else "FAIL")
        )
        print(
            f"[{role}] {item.study:<14} {item.q_design:<14} {item.variance_target:<16} "
            f"coverage {item.coverage:.3f} [{item.coverage_ci_low:.3f}, {item.coverage_ci_high:.3f}] "
            f"width {item.mean_ci_width:.5f}"
        )
    print(f"status={report.to_dict()['status']} failures={len(report.failures)}")
    print(f"Report: {destination}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
