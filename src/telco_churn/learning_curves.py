"""R05: how much of the result is the data budget, and how much is the seed?

R02 through R04 all say the same thing -- nothing in the causal pipeline
beats a simple outcome ranking on this cohort -- and all three were run at
one data budget with one seed.  Two questions follow, and they are different
questions:

**Is it the amount of data?**  Training fractions of 25%, 50% and 100% are
taken *inside* each outer training side, stratified, while the outer
evaluation rows are left alone.  Every finalist sees the same rows at each
fraction, so the curve compares recipes rather than the luck of their
subsamples.  The nuisance models are held to the same budget: letting the
evaluator train on everything while the candidate trains on a quarter would
hand the small-data regime an evaluator it would never have in practice.

**Is it the seed?**  At the full fraction only, each finalist is refitted
under two extra learner seeds.  What that can support is narrow and the
runbook says so: **three seeds are not three worlds.**  A confidence
interval built from them would describe the optimiser's jitter and be read
as sampling uncertainty.  So the seeds are reported as spread -- mean, IQR,
and how often the *selected accounts* change -- and never as an interval.

Selected-action agreement is the readout that matters operationally.  Two
seeds that score the same value while contacting different people have not
reproduced anything a business could act on.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

from .allocation import allocate_batch
from .candidates import build_candidate
from .screening import (
    CAPACITY_FRACTION,
    OUTER_FOLDS,
    CohortDesign,
    _evaluate_fold,
    _fold_nuisance,
    assert_gate_open,
    gate_status,
)

__all__ = [
    "EXTRA_SEEDS",
    "TRAINING_FRACTIONS",
    "CurvePoint",
    "LearningCurveReport",
    "SeedSpread",
    "main",
    "run_learning_curves",
]

TRAINING_FRACTIONS: tuple[float, ...] = (0.25, 0.50, 1.00)

#: Two *extra* seeds at the full fraction, so three in total per finalist.
#: Deliberately few: this is a stability probe, not a variance estimate, and
#: running twenty would invite exactly the misreading the module refuses.
EXTRA_SEEDS: tuple[int, ...] = (101, 202)


@dataclass
class CurvePoint:
    candidate_id: str
    training_fraction: float
    seed_offset: int
    fold_values: list[float] = field(default_factory=list)
    n_train_rows: list[int] = field(default_factory=list)
    n_train_events_treated: list[int] = field(default_factory=list)
    n_train_events_control: list[int] = field(default_factory=list)
    fit_seconds: float = 0.0
    #: Which accounts this fit would contact, per fold, so two seeds can be
    #: compared on decisions rather than only on value.
    fold_selections: list[frozenset[str]] = field(default_factory=list, repr=False)

    @property
    def mean_value(self) -> float:
        return float(np.mean(self.fold_values)) if self.fold_values else float("nan")

    def to_dict(self) -> dict[str, Any]:
        payload = {key: value for key, value in asdict(self).items() if key != "fold_selections"}
        return {
            **payload,
            "mean_value": self.mean_value,
            "mean_train_rows": float(np.mean(self.n_train_rows)) if self.n_train_rows else 0.0,
            "mean_train_events_treated": (
                float(np.mean(self.n_train_events_treated)) if self.n_train_events_treated else 0.0
            ),
            "mean_train_events_control": (
                float(np.mean(self.n_train_events_control)) if self.n_train_events_control else 0.0
            ),
        }


@dataclass
class SeedSpread:
    candidate_id: str
    seeds: int
    mean_value: float
    iqr_value: float
    min_value: float
    max_value: float
    #: Mean Jaccard overlap of the contacted sets between seed pairs.  1.0
    #: means the seeds contact identical accounts.
    selected_action_agreement: float
    mean_fit_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearningCurveReport:
    dataset: str
    started_at: str
    gate_detail: str
    finalists: list[str]
    n_units: int
    n_events: int
    propensity: float
    points: list[CurvePoint] = field(default_factory=list)
    runtime_seconds: float = 0.0
    fits: int = 0

    def curve(self, candidate_id: str) -> list[CurvePoint]:
        return sorted(
            (
                point
                for point in self.points
                if point.candidate_id == candidate_id and point.seed_offset == 0
            ),
            key=lambda point: point.training_fraction,
        )

    def seed_spreads(self) -> list[SeedSpread]:
        rows: list[SeedSpread] = []
        for candidate_id in self.finalists:
            variants = [
                point
                for point in self.points
                if point.candidate_id == candidate_id and point.training_fraction == 1.0
            ]
            if len(variants) < 2:
                continue
            values = [point.mean_value for point in variants]
            overlaps: list[float] = []
            for fold_index in range(OUTER_FOLDS):
                sets = [
                    point.fold_selections[fold_index]
                    for point in variants
                    if fold_index < len(point.fold_selections)
                ]
                for left in range(len(sets)):
                    for right in range(left + 1, len(sets)):
                        union = sets[left] | sets[right]
                        overlaps.append(
                            len(sets[left] & sets[right]) / len(union) if union else 1.0
                        )
            rows.append(
                SeedSpread(
                    candidate_id=candidate_id,
                    seeds=len(variants),
                    mean_value=float(np.mean(values)),
                    iqr_value=float(np.percentile(values, 75) - np.percentile(values, 25)),
                    min_value=float(np.min(values)),
                    max_value=float(np.max(values)),
                    selected_action_agreement=(
                        float(np.mean(overlaps)) if overlaps else float("nan")
                    ),
                    mean_fit_seconds=float(np.mean([p.fit_seconds for p in variants])),
                )
            )
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": "R05_learning_curves",
            "dataset": self.dataset,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "gate": self.gate_detail,
            "protocol": {
                "training_fractions": list(TRAINING_FRACTIONS),
                "extra_seeds_at_full_fraction": list(EXTRA_SEEDS),
                "outer_folds": OUTER_FOLDS,
                "capacity_fraction": CAPACITY_FRACTION,
                "nuisance_budget": "nuisances follow the same training fraction",
                "evaluation_rows": "outer evaluation rows are never subsampled",
                "split": "development only; the confirmation split is not opened",
            },
            "seeds_are_not_worlds": (
                "Three learner seeds describe optimiser jitter at one data budget. "
                "No confidence interval is formed from them, because it would be "
                "read as sampling uncertainty and it is not."
            ),
            "finalists": self.finalists,
            "cohort": {
                "n_units": self.n_units,
                "n_events": self.n_events,
                "propensity": self.propensity,
            },
            "candidate_fits": self.fits,
            "curves": {
                candidate_id: [point.to_dict() for point in self.curve(candidate_id)]
                for candidate_id in self.finalists
            },
            "seed_spread": [row.to_dict() for row in self.seed_spreads()],
            "points": [point.to_dict() for point in self.points],
            "scope_note": (
                "Development only. The curve is over training rows inside three outer "
                "folds of one dataset, so it describes this cohort's budget, not a "
                "general sample-size law."
            ),
        }


def _subsample(
    train_index: np.ndarray, strata: np.ndarray, fraction: float, seed: int
) -> np.ndarray:
    """A stratified subsample of the training side, shared by every finalist."""

    if fraction >= 1.0:
        return train_index
    keep, _drop = train_test_split(
        train_index,
        train_size=fraction,
        random_state=seed,
        stratify=strata[train_index],
    )
    return np.sort(keep)


def run_learning_curves(
    features: pd.DataFrame,
    treatment: Sequence[int] | np.ndarray,
    reward: Sequence[float] | np.ndarray,
    unit_id: Sequence[Any],
    *,
    dataset: str,
    propensity: float,
    finalists: Sequence[str],
    seed: int = 20260921,
    root: Path | str = ".",
    require_gate: bool = True,
) -> LearningCurveReport:
    """Score each finalist at each training fraction, plus seeds at the full one."""

    arm = np.asarray(treatment, dtype=int)
    value = np.asarray(reward, dtype=float)
    share = float(np.mean(value > 0)) if len(value) else 0.0
    design = CohortDesign(
        n_units=len(features),
        propensity=float(propensity),
        event_rate=min(share, 1.0 - share),
        acted_fraction=CAPACITY_FRACTION,
    )
    if require_gate:
        assert_gate_open(root, cohort_design=design)
    passed, detail = gate_status(root, cohort_design=design)
    if not passed:
        detail = f"GATE NOT PASSED, run forced: {detail}"

    started = time.perf_counter()
    report = LearningCurveReport(
        dataset=dataset,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        gate_detail=detail,
        finalists=list(finalists),
        n_units=len(features),
        n_events=int(value.sum()),
        propensity=float(propensity),
    )

    strata = arm * 2 + (value > 0).astype(int)
    splitter = StratifiedKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=seed)
    folds = list(splitter.split(features, strata))

    plan: list[tuple[float, int]] = [(fraction, 0) for fraction in TRAINING_FRACTIONS]
    plan.extend((1.0, offset) for offset in EXTRA_SEEDS)

    for candidate_id in finalists:
        for fraction, offset in plan:
            point = CurvePoint(
                candidate_id=candidate_id,
                training_fraction=fraction,
                seed_offset=offset,
            )
            clock = time.perf_counter()
            for fold_index, (train_index, score_index) in enumerate(folds):
                # The same subsample for every finalist at this fraction: the
                # seed depends on the fold and the fraction, not the model.
                budget = _subsample(train_index, strata, fraction, seed + fold_index)
                ids = [unit_id[position] for position in score_index]

                # The nuisance is held to the same budget as the candidate.
                mu0, mu1 = _fold_nuisance(
                    features.iloc[budget],
                    arm[budget],
                    value[budget],
                    features.iloc[score_index],
                    seed,
                )
                model = build_candidate(candidate_id, seed=seed + offset).fit(
                    features.iloc[budget],
                    arm[budget],
                    value[budget],
                    propensity=propensity,
                )
                report.fits += 1
                scores = model.score(features.iloc[score_index], unit_id=ids)
                fold_value, _n = _evaluate_fold(
                    scores,
                    ids,
                    value[score_index],
                    arm[score_index],
                    mu0,
                    mu1,
                    propensity=propensity,
                )
                allocation = allocate_batch(
                    [str(item) for item in ids],
                    scores,
                    fraction=CAPACITY_FRACTION,
                    require_positive=False,
                )
                chosen = allocation.frame["selected"].to_numpy()
                point.fold_values.append(fold_value)
                point.fold_selections.append(frozenset(str(ids[i]) for i in np.flatnonzero(chosen)))
                point.n_train_rows.append(len(budget))
                point.n_train_events_treated.append(
                    int(((value[budget] > 0) & (arm[budget] == 1)).sum())
                )
                point.n_train_events_control.append(
                    int(((value[budget] > 0) & (arm[budget] == 0)).sum())
                )
            point.fit_seconds = time.perf_counter() - clock
            report.points.append(point)

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: LearningCurveReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R05 — learning curves and seed stability",
        "",
        f"{report.dataset} · {report.n_units:,} units · {report.n_events:,} events · "
        f"{OUTER_FOLDS} outer folds · {report.fits} fits · "
        f"{report.runtime_seconds:.0f} s",
        "",
        f"Gate: {report.gate_detail}",
        "",
        payload["scope_note"],
        "",
        "## Learning curves",
        "",
        "| candidate | fraction | train rows | events treated | events control | value |",
        "|---|---|---|---|---|---|",
    ]
    for candidate_id in report.finalists:
        for point in report.curve(candidate_id):
            row = point.to_dict()
            lines.append(
                f"| {candidate_id} | {point.training_fraction:.0%} "
                f"| {row['mean_train_rows']:,.0f} "
                f"| {row['mean_train_events_treated']:,.0f} "
                f"| {row['mean_train_events_control']:,.0f} "
                f"| {point.mean_value:+.6f} |"
            )
    lines.extend(
        [
            "",
            "Nuisances follow the same budget as the candidate, so the 25% row is not "
            "scored by an evaluator that saw four times as much data as the model it is "
            "scoring.",
            "",
            "## Seed spread at the full fraction",
            "",
            "**" + payload["seeds_are_not_worlds"] + "**",
            "",
            "| candidate | seeds | mean | IQR | min | max | selected-action agreement |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in report.seed_spreads():
        lines.append(
            f"| {row.candidate_id} | {row.seeds} | {row.mean_value:+.6f} "
            f"| {row.iqr_value:.6f} | {row.min_value:+.6f} | {row.max_value:+.6f} "
            f"| {row.selected_action_agreement:.3f} |"
        )
    lines.extend(
        [
            "",
            "Selected-action agreement is the Jaccard overlap of the contacted sets "
            "between seed pairs. Two seeds that score the same value while contacting "
            "different accounts have not reproduced anything anyone could act on, so it "
            "is reported beside the value rather than instead of it.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="reports/v4/learning_curves")
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--treatment-arm", default="Mens E-Mail")
    parser.add_argument("--finalists", nargs="*", default=None)
    args = parser.parse_args(argv)

    from .hillstrom_data import (
        CONTROL_ARM,
        DEFAULT_PATH,
        TREATMENT_COLUMN,
        feature_frame,
        load_hillstrom,
        make_split,
    )

    raw = Path(args.root) / DEFAULT_PATH
    if not raw.exists():
        print(f"{raw} is missing; run `python -m telco_churn.hillstrom_data fetch` first")
        return 1

    frame = load_hillstrom(raw)
    split = make_split(frame)
    development = frame.loc[split.to_numpy() == "development"]
    pair = development.loc[
        development[TREATMENT_COLUMN].isin([args.treatment_arm, CONTROL_ARM])
    ].reset_index(drop=True)
    features = feature_frame(pair)
    treatment = (pair[TREATMENT_COLUMN] == args.treatment_arm).astype(int).to_numpy()
    reward = pair["conversion"].astype(float).to_numpy()

    finalists = args.finalists
    if finalists is None:
        screening_path = Path(args.root) / "reports/screening/screening.json"
        if not screening_path.exists():
            print(f"{screening_path} is missing; R05 takes its finalists from R02")
            return 1
        finalists = json.loads(screening_path.read_text(encoding="utf-8"))["shortlist"]

    try:
        report = run_learning_curves(
            features,
            treatment,
            reward,
            pair["row_id"].tolist(),
            dataset=f"hillstrom {args.treatment_arm} vs {CONTROL_ARM} (development)",
            propensity=float(treatment.mean()),
            finalists=finalists,
            seed=args.seed,
            root=args.root,
        )
    except RuntimeError as error:
        print(f"R05 refused to run: {error}")
        return 1

    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "learning_curves.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "LEARNING_CURVES.md").write_text(render_markdown(report), encoding="utf-8")

    for candidate_id in report.finalists:
        for point in report.curve(candidate_id):
            print(
                f"{candidate_id:<5} {point.training_fraction:>5.0%} value {point.mean_value:+.6f}"
            )
    for row in report.seed_spreads():
        print(
            f"{row.candidate_id:<5} seeds {row.seeds} IQR {row.iqr_value:.6f} "
            f"selected-action agreement {row.selected_action_agreement:.3f}"
        )
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
