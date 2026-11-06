"""R03: bounded tuning, so the screening result is not defaults-versus-defaults.

R02 ranked eight candidates on the runbook's declared hyperparameters and the
simple baseline won.  That result is not defensible on its own, and the
reason is the first question any reader asks: the causal learners have more
knobs, so comparing them at one arbitrary setting each measures the settings
as much as the methods.  R03 is the stage that answers it.

The protocol is the runbook's, not chosen here:

* **At most three families**, one representative each, taken from the R02
  shortlist.  Adding a fourth after seeing R02 would be selection.
* **Exactly eight configurations per family**, from the declared grids.  Not
  a joint sweep over C x features x calibrator relabelled as eight trials --
  calibration and representation are R04's experiments, not this one.
* **Nested folds**: the inner search picks a configuration using only the
  training side of each outer fold, and the outer fold scores that choice.
  Hyperparameter selection never reads outer labels, so the reported number
  is what this *procedure* would earn, not what its luckiest setting earns.
* **Paired against the same baseline on the same folds** as R02, so the two
  stages are comparable.

What R03 can and cannot settle.  It can say whether tuning closes the gap the
defaults showed.  It cannot turn three outer folds of one dataset into
independent evidence, and a tuned winner here is still a development result:
the confirmation split stays shut.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from .candidates import build_candidate
from .screening import (
    BASELINE_ID,
    CAPACITY_FRACTION,
    OUTER_FOLDS,
    CohortDesign,
    _evaluate_fold,
    _fold_nuisance,
    assert_gate_open,
    gate_status,
)

__all__ = [
    "GRIDS",
    "INNER_FOLDS",
    "TunedResult",
    "TuningReport",
    "main",
    "run_bounded_tuning",
]

INNER_FOLDS = 3

#: Runbook §"R02/R03 — Cách shortlist và tinh chỉnh", eight per family.
#:
#: The grids are one-dimensional on purpose where the runbook says so.  A
#: logistic family varies its penalty and nothing else; the interactions are
#: fixed by the model recipe, because varying them here would confound the
#: tuning question with the representation question that R04 owns.
LOGISTIC_GRID: tuple[dict[str, Any], ...] = tuple(
    {"C": value} for value in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
)
HGB_GRID: tuple[dict[str, Any], ...] = tuple(
    {
        "max_leaf_nodes": leaves,
        "min_samples_leaf": leaf,
        "l2_regularization": l2,
        "learning_rate": 0.05,
        "max_iter": 300,
    }
    for leaves in (15, 31)
    for leaf in (50, 200)
    for l2 in (1.0, 10.0)
)
RIDGE_GRID: tuple[dict[str, Any], ...] = tuple(
    {"alpha": alpha, "shrinkage": shrinkage}
    for alpha in (0.1, 1.0, 10.0, 100.0)
    for shrinkage in (0.5, 1.0)
)

#: Which grid each candidate searches.  A candidate absent from here has no
#: declared grid and may not be tuned in this stage.
GRIDS: dict[str, tuple[dict[str, Any], ...]] = {
    "M01": LOGISTIC_GRID,
    "M02": HGB_GRID,
    "M03": LOGISTIC_GRID,
    "M04": HGB_GRID,
    "M05": LOGISTIC_GRID,
    "M06": HGB_GRID,
    "M07": RIDGE_GRID,
    "M08": HGB_GRID,
}


@dataclass
class InnerTrial:
    configuration: dict[str, Any]
    inner_value: float
    folds_scored: int
    #: Hash of the units this configuration would actually contact, across
    #: the inner folds.  Two configurations with the same signature made the
    #: same decisions, so the grid searched one point, not two.
    allocation_signature: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TunedResult:
    candidate_id: str
    family: str
    status: str = "COMPLETED"
    error: str = ""
    #: The configuration the inner search chose, per outer fold.  Different
    #: folds may choose differently; that instability is a result, not a
    #: defect to be averaged away.
    chosen_per_fold: list[dict[str, Any]] = field(default_factory=list)
    fold_values: list[float] = field(default_factory=list)
    fold_deltas_vs_baseline: list[float] = field(default_factory=list)
    default_fold_values: list[float] = field(default_factory=list)
    inner_trials: list[list[InnerTrial]] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return float(np.mean(self.fold_values)) if self.fold_values else float("nan")

    @property
    def mean_delta_vs_baseline(self) -> float:
        values = self.fold_deltas_vs_baseline
        return float(np.mean(values)) if values else float("nan")

    @property
    def mean_gain_from_tuning(self) -> float:
        """Tuned minus default, on the same folds.  The stage's actual question."""

        if not self.fold_values or len(self.fold_values) != len(self.default_fold_values):
            return float("nan")
        return float(
            np.mean(
                [
                    tuned - default
                    for tuned, default in zip(
                        self.fold_values, self.default_fold_values, strict=True
                    )
                ]
            )
        )

    @property
    def distinct_configurations_searched(self) -> list[int]:
        """Per outer fold, how many grid points made *different* decisions.

        A grid dimension the allocator cannot see is not a search dimension.
        Shrinking a score toward a constant, for instance, is an affine
        transform, and a rank-based allocator is invariant to it -- so those
        configurations contact exactly the same accounts and the grid is
        narrower than it looks.  Reporting eight trials when four of them
        were duplicates would overstate the search.
        """

        return [
            len({trial.allocation_signature for trial in fold if trial.allocation_signature})
            for fold in self.inner_trials
        ]

    @property
    def grid_is_degenerate(self) -> bool:
        searched = self.distinct_configurations_searched
        if not searched or not self.inner_trials:
            return False
        return min(searched) < len(self.inner_trials[0])

    @property
    def configuration_stable(self) -> bool:
        """Did every outer fold's inner search land on the same setting?"""

        if len(self.chosen_per_fold) < 2:
            return True
        first = json.dumps(self.chosen_per_fold[0], sort_keys=True)
        return all(json.dumps(choice, sort_keys=True) == first for choice in self.chosen_per_fold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "family": self.family,
            "status": self.status,
            "error": self.error,
            "chosen_per_fold": self.chosen_per_fold,
            "configuration_stable": self.configuration_stable,
            "grid_size": len(self.inner_trials[0]) if self.inner_trials else 0,
            "distinct_configurations_searched": self.distinct_configurations_searched,
            "grid_is_degenerate": self.grid_is_degenerate,
            "fold_values": self.fold_values,
            "fold_deltas_vs_baseline": self.fold_deltas_vs_baseline,
            "default_fold_values": self.default_fold_values,
            "mean_value": self.mean_value,
            "mean_delta_vs_baseline": self.mean_delta_vs_baseline,
            "mean_gain_from_tuning": self.mean_gain_from_tuning,
            "inner_trials": [[trial.to_dict() for trial in fold] for fold in self.inner_trials],
        }


@dataclass
class TuningReport:
    dataset: str
    started_at: str
    gate_detail: str
    shortlist: list[str]
    n_units: int
    n_events: int
    propensity: float
    results: list[TunedResult] = field(default_factory=list)
    runtime_seconds: float = 0.0
    fits: int = 0

    @property
    def completed(self) -> list[TunedResult]:
        return [item for item in self.results if item.status == "COMPLETED"]

    def to_dict(self) -> dict[str, Any]:
        tuned_beat_default = [
            item.candidate_id for item in self.completed if item.mean_gain_from_tuning > 0
        ]
        return {
            "stage": "R03_bounded_tuning",
            "dataset": self.dataset,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "gate": self.gate_detail,
            "protocol": {
                "outer_folds": OUTER_FOLDS,
                "inner_folds": INNER_FOLDS,
                "configurations_per_family": 8,
                "capacity_fraction": CAPACITY_FRACTION,
                "baseline": BASELINE_ID,
                "selection": "inner search on the training side of each outer fold only",
                "split": "development only; the confirmation split is not opened",
            },
            "shortlist": self.shortlist,
            "cohort": {
                "n_units": self.n_units,
                "n_events": self.n_events,
                "propensity": self.propensity,
            },
            "candidate_fits": self.fits,
            "tuned_beat_their_default": tuned_beat_default,
            "degenerate_grids": [
                item.candidate_id for item in self.completed if item.grid_is_degenerate
            ],
            "any_tuned_candidate_beat_the_baseline": [
                item.candidate_id
                for item in self.completed
                if item.mean_delta_vs_baseline > 0 and item.candidate_id != BASELINE_ID
            ],
            "results": [item.to_dict() for item in self.results],
            "scope_note": (
                "Development only, three outer folds of one dataset. A tuned score "
                "here is not a confirmation, and the fold-to-fold instability of the "
                "chosen configuration is reported rather than averaged away."
            ),
        }


def _inner_search(
    features: pd.DataFrame,
    treatment: np.ndarray,
    reward: np.ndarray,
    unit_id: Sequence[Any],
    *,
    candidate_id: str,
    grid: Sequence[Mapping[str, Any]],
    propensity: float,
    seed: int,
) -> tuple[dict[str, Any], list[InnerTrial], int]:
    """Pick a configuration using only these rows, which are all training rows.

    Every configuration is scored on the same inner folds, so the comparison
    between them is paired.  A configuration that cannot be fitted is recorded
    with its error and scored as minus infinity rather than dropped -- dropping
    it would quietly improve the average of whatever survived.
    """

    strata = treatment * 2 + (reward > 0).astype(int)
    splitter = StratifiedKFold(n_splits=INNER_FOLDS, shuffle=True, random_state=seed)
    inner_folds = list(splitter.split(features, strata))

    trials: list[InnerTrial] = []
    fits = 0
    for configuration in grid:
        values: list[float] = []
        selected: list[str] = []
        error = ""
        for train_index, score_index in inner_folds:
            try:
                model = build_candidate(candidate_id, seed=seed, hyperparameters=configuration).fit(
                    features.iloc[train_index],
                    treatment[train_index],
                    reward[train_index],
                    propensity=propensity,
                )
                fits += 1
                scores = model.score(
                    features.iloc[score_index],
                    unit_id=[unit_id[position] for position in score_index],
                )
                mu0, mu1 = _fold_nuisance(
                    features.iloc[train_index],
                    treatment[train_index],
                    reward[train_index],
                    features.iloc[score_index],
                    seed,
                )
                value, _ = _evaluate_fold(
                    scores,
                    [unit_id[position] for position in score_index],
                    reward[score_index],
                    treatment[score_index],
                    mu0,
                    mu1,
                    propensity=propensity,
                )
                values.append(value)
                order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
                capacity = int(len(score_index) * CAPACITY_FRACTION)
                selected.extend(
                    sorted(str(unit_id[score_index[position]]) for position in order[:capacity])
                )
            except (ValueError, RuntimeError, FloatingPointError) as failure:
                error = f"{type(failure).__name__}: {failure}"
                break
        trials.append(
            InnerTrial(
                configuration=dict(configuration),
                inner_value=float(np.mean(values)) if len(values) == INNER_FOLDS else float("-inf"),
                folds_scored=len(values),
                allocation_signature=hashlib.sha256("|".join(selected).encode("utf-8")).hexdigest()[
                    :16
                ],
                error=error,
            )
        )

    best = max(trials, key=lambda trial: trial.inner_value)
    if best.inner_value == float("-inf"):
        raise RuntimeError(
            f"every configuration for {candidate_id} failed to fit; "
            f"first error: {trials[0].error or 'unknown'}"
        )
    return best.configuration, trials, fits


def run_bounded_tuning(
    features: pd.DataFrame,
    treatment: Sequence[int] | np.ndarray,
    reward: Sequence[float] | np.ndarray,
    unit_id: Sequence[Any],
    *,
    dataset: str,
    propensity: float,
    shortlist: Sequence[str],
    seed: int = 20260921,
    root: Path | str = ".",
    require_gate: bool = True,
) -> TuningReport:
    """Tune each shortlisted family inside the training side of each outer fold."""

    if len(shortlist) > 3:
        raise ValueError(
            f"the runbook allows at most three families in R03; got {list(shortlist)}. "
            "Widening the shortlist after seeing R02 is selection, not tuning."
        )
    unknown = [name for name in shortlist if name not in GRIDS]
    if unknown:
        raise ValueError(f"no declared tuning grid for {unknown}")

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
    report = TuningReport(
        dataset=dataset,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        gate_detail=detail,
        shortlist=list(shortlist),
        n_units=len(features),
        n_events=int(value.sum()),
        propensity=float(propensity),
    )

    # The same outer folds R02 used, so the two stages are comparable.
    strata = arm * 2 + (value > 0).astype(int)
    splitter = StratifiedKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=seed)
    folds = list(splitter.split(features, strata))

    baseline_values: list[float] = []
    for train_index, score_index in folds:
        model = build_candidate(BASELINE_ID, seed=seed).fit(
            features.iloc[train_index],
            arm[train_index],
            value[train_index],
            propensity=propensity,
        )
        report.fits += 1
        mu0, mu1 = _fold_nuisance(
            features.iloc[train_index],
            arm[train_index],
            value[train_index],
            features.iloc[score_index],
            seed,
        )
        scores = model.score(
            features.iloc[score_index],
            unit_id=[unit_id[position] for position in score_index],
        )
        value_here, _ = _evaluate_fold(
            scores,
            [unit_id[position] for position in score_index],
            value[score_index],
            arm[score_index],
            mu0,
            mu1,
            propensity=propensity,
        )
        baseline_values.append(value_here)

    for candidate_id in shortlist:
        spec_family = build_candidate(candidate_id, seed=seed).spec.family
        result = TunedResult(candidate_id=candidate_id, family=spec_family)
        try:
            for fold_index, (train_index, score_index) in enumerate(folds):
                chosen, trials, inner_fits = _inner_search(
                    features.iloc[train_index].reset_index(drop=True),
                    arm[train_index],
                    value[train_index],
                    [unit_id[position] for position in train_index],
                    candidate_id=candidate_id,
                    grid=GRIDS[candidate_id],
                    propensity=propensity,
                    seed=seed + fold_index,
                )
                report.fits += inner_fits
                result.chosen_per_fold.append(chosen)
                result.inner_trials.append(trials)

                mu0, mu1 = _fold_nuisance(
                    features.iloc[train_index],
                    arm[train_index],
                    value[train_index],
                    features.iloc[score_index],
                    seed,
                )
                ids = [unit_id[position] for position in score_index]
                for label, configuration in (("tuned", chosen), ("default", {})):
                    model = build_candidate(
                        candidate_id, seed=seed, hyperparameters=configuration
                    ).fit(
                        features.iloc[train_index],
                        arm[train_index],
                        value[train_index],
                        propensity=propensity,
                    )
                    report.fits += 1
                    scores = model.score(features.iloc[score_index], unit_id=ids)
                    outer_value, _ = _evaluate_fold(
                        scores,
                        ids,
                        value[score_index],
                        arm[score_index],
                        mu0,
                        mu1,
                        propensity=propensity,
                    )
                    if label == "tuned":
                        result.fold_values.append(outer_value)
                        result.fold_deltas_vs_baseline.append(
                            outer_value - baseline_values[fold_index]
                        )
                    else:
                        result.default_fold_values.append(outer_value)
        except (ValueError, RuntimeError, FloatingPointError) as failure:
            result.status = "TUNING_FAILED"
            result.error = f"{type(failure).__name__}: {failure}"
        report.results.append(result)

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: TuningReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R03 — bounded tuning",
        "",
        f"{report.dataset} · {report.n_units:,} units · {report.n_events:,} events · "
        f"{OUTER_FOLDS} outer x {INNER_FOLDS} inner · {report.fits:,} candidate fits · "
        f"{report.runtime_seconds:.0f} s",
        "",
        f"Gate: {report.gate_detail}",
        "",
        payload["scope_note"],
        "",
        "| candidate | family | tuned value | vs baseline | gain from tuning "
        "| config stable | distinct configs |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in report.results:
        if item.status != "COMPLETED":
            lines.append(f"| {item.candidate_id} | {item.family} | — | — | — | {item.status} | — |")
            continue
        searched = item.distinct_configurations_searched
        size = len(item.inner_trials[0]) if item.inner_trials else 0
        lines.append(
            f"| {item.candidate_id} | {item.family} | {item.mean_value:+.5f} "
            f"| {item.mean_delta_vs_baseline:+.5f} | {item.mean_gain_from_tuning:+.5f} "
            f"| {'yes' if item.configuration_stable else '**no**'} "
            f"| {min(searched) if searched else 0}/{size} |"
        )
    lines.extend(
        [
            "",
            "`gain from tuning` is the tuned configuration minus the runbook default on "
            "the *same* outer folds, which is the question this stage exists to answer. "
            "`vs baseline` is against " + BASELINE_ID + ", paired on the same folds as R02.",
            "",
            "`distinct configs` is how many of the grid points actually produced different "
            "allocations. Where it is below the grid size the search was narrower than it "
            "looks: a dimension the allocator cannot see is not a dimension.",
            "",
        ]
    )
    for item in report.completed:
        lines.append(f"### {item.candidate_id}")
        lines.append("")
        lines.append(
            "Chosen per outer fold: "
            + "; ".join(json.dumps(choice, sort_keys=True) for choice in item.chosen_per_fold)
        )
        if not item.configuration_stable:
            lines.append("")
            lines.append(
                "The inner search did not agree across folds. That instability is the "
                "finding: a configuration this dataset cannot pin down is not a "
                "setting to carry into confirmation."
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="reports/v4/tuning")
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--treatment-arm", default="Mens E-Mail")
    parser.add_argument(
        "--shortlist",
        nargs="*",
        default=None,
        help="override the R02 shortlist; at most three, each with a declared grid",
    )
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

    shortlist = args.shortlist
    if shortlist is None:
        screening_path = Path(args.root) / "reports/screening/screening.json"
        if not screening_path.exists():
            print(
                f"{screening_path} is missing; R03 takes its shortlist from R02, so run "
                "`python -m telco_churn.screening` first"
            )
            return 1
        shortlist = json.loads(screening_path.read_text(encoding="utf-8"))["shortlist"]

    try:
        report = run_bounded_tuning(
            features,
            treatment,
            reward,
            pair["row_id"].tolist(),
            dataset=f"hillstrom {args.treatment_arm} vs {CONTROL_ARM} (development)",
            propensity=float(treatment.mean()),
            shortlist=shortlist,
            seed=args.seed,
            root=args.root,
        )
    except RuntimeError as error:
        print(f"R03 refused to run: {error}")
        return 1

    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "bounded_tuning.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "TUNING_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for item in report.results:
        if item.status != "COMPLETED":
            print(f"[{item.status}] {item.candidate_id}: {item.error}")
            continue
        print(
            f"[ok] {item.candidate_id:<5} tuned {item.mean_value:+.6f} "
            f"vs baseline {item.mean_delta_vs_baseline:+.6f} "
            f"gain {item.mean_gain_from_tuning:+.6f} "
            f"{'stable' if item.configuration_stable else 'UNSTABLE'}"
        )
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
