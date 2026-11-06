"""R10: does the recipe hold in a domain it was not built on?

Hillstrom is an e-mail campaign on a US retailer's list, with 302 conversions
in 34,092 accounts -- a rare-event regime.  Lenta is an SMS campaign by a
Russian grocery chain, with roughly a 10.8% response rate.  Different
company, country, channel, outcome and population, and crucially a
**different event regime**, which is what makes it a test rather than
another slice.

The Womens arm (S35) is reported separately and is not this: it shares the
customers, the campaign and the period, so it measures stability, not
transfer.

## The prediction, registered before the run

R02 through R05 concluded that a control-outcome ranking beats every causal
learner on Hillstrom, and the explanation offered was **event scarcity**:
at 302 events nothing in the pipeline has enough signal to separate.  If
that explanation is right it makes a falsifiable prediction, because Lenta's
development split carries two orders of magnitude more events:

> **P1.** On Lenta, at least one causal learner beats the M01 baseline.

If instead the baseline still wins with tens of thousands of events, the
scarcity explanation is wrong and something else is going on -- the recipe,
the evaluator, or the class of learners.  Either answer is worth having, and
the prediction is written here before the artifact exists so it cannot be
adjusted afterwards.

> **P2.** The hyperparameter instability R03 found on Hillstrom -- no family
> agreeing across folds -- goes away with more events.

> **P3.** A learning curve appears: the finalists improve from 25% to 100%
> of the training rows, which they did not do on Hillstrom's Mens arm.

## What is held fixed

The same ``run_screening``, ``run_bounded_tuning`` and ``run_learning_curves``
functions the Hillstrom stages called, at the same capacity, the same fold
count and the same candidate registry.  That is what "same method recipe"
has to mean; re-implementing the protocol for a new dataset would test a
different protocol.

**R04 does not transfer** and is not run.  Its representation factor is
defined by Hillstrom's own columns (``log1p_history x recency`` and the
rest) and its cost model keys on a ``channel`` column Lenta does not have.
Running a *different* factorial and calling it the same stage would be the
kind of quiet substitution this stage exists to detect.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .bounded_tuning import run_bounded_tuning
from .learning_curves import run_learning_curves
from .screening import BASELINE_ID, CohortDesign, run_screening

__all__ = [
    "PREDICTIONS",
    "ReplicationReport",
    "load_cohort",
    "main",
    "run_external_replication",
]

#: Development rows to score.  The full split is 550k rows and 191 features;
#: a DR-HGB fit alone takes 12 s at 30k, so the tuning stage over all of it
#: is hours.  The point of this stage is the *regime change*, not the row
#: count: 60k rows carry roughly 6,500 events, twenty-one times Hillstrom's
#: 302, which is the contrast P1 turns on.  The subsample is declared here
#: and in the artifact rather than hidden, and the asymmetry index is
#: recomputed for it rather than inherited.
SUBSAMPLE_ROWS = 60_000
SUBSAMPLE_SEED = 20260921

PREDICTIONS: tuple[tuple[str, str], ...] = (
    ("P1_a_causal_learner_wins", "at least one causal learner beats the M01 baseline"),
    (
        "P2_configurations_stabilise",
        "with more events, at least one family agrees on a configuration across folds",
    ),
    (
        "P3_a_learning_curve_appears",
        "at least one finalist improves from 25% to 100% of the training rows",
    ),
)


def load_cohort(
    root: Path | str = ".", *, rows: int = SUBSAMPLE_ROWS, seed: int = SUBSAMPLE_SEED
) -> dict[str, Any]:
    """The Lenta development cohort, numeric features only, post-treatment gated."""

    from .lenta_data import (
        DEFAULT_PATH,
        OUTCOME_COLUMN,
        TREATMENT_COLUMN,
        TREATMENT_GROUP,
        feature_frame,
        load_lenta,
        make_split,
    )

    frame = load_lenta(Path(root) / DEFAULT_PATH)
    split = make_split(frame)
    development = frame.loc[split.to_numpy() == "development"].reset_index(drop=True)
    if rows and rows < len(development):
        rng = np.random.default_rng(seed)
        take = np.sort(rng.choice(len(development), size=rows, replace=False))
        development = development.iloc[take].reset_index(drop=True)

    features = feature_frame(development)
    # The candidate pipelines one-hot encode object columns; Lenta's two are
    # low cardinality and survive, but NaNs in the numeric block would fail
    # a logistic fit, so they are filled here and the choice is recorded.
    numeric = features.select_dtypes(include=["number"]).columns
    features[numeric] = features[numeric].fillna(features[numeric].median())
    # A missing category is information, not an error: filling it with a
    # named level keeps those rows in the study and makes the choice visible
    # in the encoded design, rather than dropping them or letting the
    # encoder decide silently.
    for column in features.select_dtypes(include=["object"]).columns:
        features[column] = features[column].fillna("missing").astype(str)

    treatment = (
        (development[TREATMENT_COLUMN].astype(str) == TREATMENT_GROUP).astype(int).to_numpy()
    )
    reward = development[OUTCOME_COLUMN].astype(float).to_numpy()
    return {
        "features": features,
        "treatment": treatment,
        "reward": reward,
        "unit_id": development["row_id"].tolist(),
        "dataset": "lenta SMS campaign (development)",
        "propensity": float(treatment.mean()),
        "n_development_total": int((split == "development").sum()),
        "missing_filled_with": (
            "numeric: median of the development subsample; categorical: an explicit 'missing' level"
        ),
    }


@dataclass
class ReplicationReport:
    dataset: str
    started_at: str
    n_units: int
    n_events: int
    propensity: float
    asymmetry_index: float
    n_development_total: int
    screening: dict[str, Any] = field(default_factory=dict)
    tuning: dict[str, Any] = field(default_factory=dict)
    curves: dict[str, Any] = field(default_factory=dict)
    runtime_seconds: float = 0.0

    def score_predictions(self) -> dict[str, Any]:
        """Each registered prediction, scored mechanically against the run."""

        results: dict[str, Any] = {}

        completed = [
            item
            for item in self.screening.get("results", [])
            if item.get("status") == "COMPLETED" and item.get("candidate_id") != BASELINE_ID
        ]
        winners = [
            item["candidate_id"]
            for item in completed
            if (item.get("mean_delta_vs_baseline") or 0.0) > 0
        ]
        results["P1_a_causal_learner_wins"] = {
            "prediction": PREDICTIONS[0][1],
            "held": bool(winners),
            "candidates_beating_the_baseline": winners,
            "best_delta": max(
                (item.get("mean_delta_vs_baseline") or 0.0 for item in completed),
                default=float("nan"),
            ),
        }

        stable = [
            item["candidate_id"]
            for item in self.tuning.get("results", [])
            if item.get("status") == "COMPLETED" and item.get("configuration_stable")
        ]
        results["P2_configurations_stabilise"] = {
            "prediction": PREDICTIONS[1][1],
            "held": bool(stable),
            "families_with_a_stable_configuration": stable,
        }

        improving = []
        for candidate_id, points in self.curves.get("curves", {}).items():
            ordered = sorted(points, key=lambda point: point["training_fraction"])
            if len(ordered) >= 2 and ordered[-1]["mean_value"] > ordered[0]["mean_value"]:
                improving.append(candidate_id)
        results["P3_a_learning_curve_appears"] = {
            "prediction": PREDICTIONS[2][1],
            "held": bool(improving),
            "finalists_improving_with_data": improving,
        }
        return results

    def to_dict(self) -> dict[str, Any]:
        predictions = self.score_predictions()
        return {
            "stage": "R10_external_replication",
            "dataset": self.dataset,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "is_independent_domain": True,
            "why_independent": (
                "different company, country, channel (SMS not e-mail), outcome and "
                "population, and a response rate two orders of magnitude above "
                "Hillstrom's. The Womens arm is reported separately and is not this."
            ),
            "cohort": {
                "n_units": self.n_units,
                "n_events": self.n_events,
                "propensity": self.propensity,
                "asymmetry_index": self.asymmetry_index,
                "n_development_total": self.n_development_total,
                "subsample_rows": SUBSAMPLE_ROWS,
            },
            "stages_replicated": ["R02", "R03", "R05"],
            "stages_not_transferable": {
                "R04": (
                    "its representation factor is defined by Hillstrom's own columns "
                    "and its cost model keys on a channel column Lenta lacks; running "
                    "a different factorial under the same name would be a quiet "
                    "substitution"
                )
            },
            "predictions": predictions,
            "all_predictions_held": all(item["held"] for item in predictions.values()),
            "screening": self.screening,
            "tuning": self.tuning,
            "curves": self.curves,
            "scope_note": (
                "One replication domain, a declared subsample of its development "
                "split, three outer folds. Two datasets under one protocol is the "
                "minimum that can be called replication, not a settled answer."
            ),
        }


def run_external_replication(
    root: Path | str = ".",
    *,
    rows: int = SUBSAMPLE_ROWS,
    seed: int = 20260921,
    require_gate: bool = True,
) -> ReplicationReport:
    """Run the Hillstrom protocol, unchanged, on the Lenta cohort."""

    started = time.perf_counter()
    cohort = load_cohort(root, rows=rows)
    features: pd.DataFrame = cohort["features"]
    treatment = cohort["treatment"]
    reward = cohort["reward"]
    share = float(np.mean(reward > 0))
    design = CohortDesign(
        n_units=len(features),
        propensity=cohort["propensity"],
        event_rate=min(share, 1.0 - share),
        acted_fraction=0.2,
    )

    screening = run_screening(
        features,
        treatment,
        reward,
        cohort["unit_id"],
        dataset=cohort["dataset"],
        propensity=cohort["propensity"],
        seed=seed,
        root=root,
        require_gate=require_gate,
    )
    shortlist = screening.shortlist or [BASELINE_ID]

    tuning = run_bounded_tuning(
        features,
        treatment,
        reward,
        cohort["unit_id"],
        dataset=cohort["dataset"],
        propensity=cohort["propensity"],
        shortlist=shortlist,
        seed=seed,
        root=root,
        require_gate=require_gate,
    )
    curves = run_learning_curves(
        features,
        treatment,
        reward,
        cohort["unit_id"],
        dataset=cohort["dataset"],
        propensity=cohort["propensity"],
        finalists=shortlist,
        seed=seed,
        root=root,
        require_gate=require_gate,
    )

    report = ReplicationReport(
        dataset=cohort["dataset"],
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        n_units=len(features),
        n_events=int(reward.sum()),
        propensity=cohort["propensity"],
        asymmetry_index=design.asymmetry_index,
        n_development_total=cohort["n_development_total"],
        screening=screening.to_dict(),
        tuning=tuning.to_dict(),
        curves=curves.to_dict(),
    )
    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: ReplicationReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R10 — external replication on Lenta",
        "",
        f"{report.dataset} · {report.n_units:,} units · {report.n_events:,} events · "
        f"e = {report.propensity:.4f} · A = {report.asymmetry_index:.4f} · "
        f"{report.runtime_seconds:.0f} s",
        "",
        "**" + payload["why_independent"] + "**",
        "",
        payload["scope_note"],
        "",
        "## Registered predictions",
        "",
        "These were written into the module docstring before the run.",
        "",
        "| prediction | held? | evidence |",
        "|---|---|---|",
    ]
    for name, entry in payload["predictions"].items():
        detail = next(
            (
                f"{key}: {value}"
                for key, value in entry.items()
                if key not in {"prediction", "held"}
            ),
            "",
        )
        lines.append(
            f"| **{name}** — {entry['prediction']} | "
            f"{'**yes**' if entry['held'] else '**NO**'} | {detail} |"
        )

    lines.extend(
        ["", "## R02 on Lenta", "", "| candidate | value | vs baseline |", "|---|---|---|"]
    )
    for item in sorted(
        (r for r in report.screening.get("results", []) if r.get("status") == "COMPLETED"),
        key=lambda r: -(r.get("mean_delta_vs_baseline") or 0.0),
    ):
        lines.append(
            f"| {item['candidate_id']} | {item['mean_value']:+.6f} "
            f"| {item['mean_delta_vs_baseline']:+.6f} |"
        )

    lines.extend(
        [
            "",
            "## R03 on Lenta",
            "",
            "| candidate | gain from tuning | config stable |",
            "|---|---|---|",
        ]
    )
    for item in report.tuning.get("results", []):
        if item.get("status") != "COMPLETED":
            lines.append(f"| {item['candidate_id']} | — | {item.get('status')} |")
            continue
        lines.append(
            f"| {item['candidate_id']} | {item['mean_gain_from_tuning']:+.6f} "
            f"| {'yes' if item['configuration_stable'] else '**no**'} |"
        )

    lines.extend(
        ["", "## R05 on Lenta", "", "| candidate | 25% | 50% | 100% |", "|---|---|---|---|"]
    )
    for candidate_id, points in report.curves.get("curves", {}).items():
        ordered = sorted(points, key=lambda point: point["training_fraction"])
        cells = " | ".join(f"{point['mean_value']:+.6f}" for point in ordered)
        lines.append(f"| {candidate_id} | {cells} |")

    lines.extend(
        [
            "",
            "**R04 is not run here.** " + payload["stages_not_transferable"]["R04"] + ".",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--rows", type=int, default=SUBSAMPLE_ROWS)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--output-dir", default="reports/v4/replication_lenta")
    args = parser.parse_args(argv)

    from .lenta_data import DEFAULT_PATH

    raw = Path(args.root) / DEFAULT_PATH
    if not raw.exists():
        print(f"{raw} is missing; download it first")
        return 1

    try:
        report = run_external_replication(args.root, rows=args.rows, seed=args.seed)
    except RuntimeError as error:
        print(f"R10 refused to run: {error}")
        return 1

    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "external_replication.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "EXTERNAL_REPLICATION.md").write_text(render_markdown(report), encoding="utf-8")
    for name, entry in report.score_predictions().items():
        print(f"[{'HELD' if entry['held'] else 'FALSIFIED'}] {name}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
