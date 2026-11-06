"""R02 model screening: eight candidates, three outer folds, one gate (WP09).

The runbook opens this stage on one condition -- *"R02 — Model screening ...
Điều kiện mở đợt: R01 validity gates đạt"* -- and this module enforces it.
Screening eight models with an evaluator that has not passed its coverage gate
produces a leaderboard measured with an uncalibrated ruler, so
:func:`assert_gate_open` refuses to run and says which readouts failed.

The protocol, taken from the runbook rather than chosen here:

* **M01-M08 with declared defaults**, three outer folds, the same folds and the
  same preprocessing for every candidate.
* **Primary readout is policy value at the 20% cap**, paired against the M01
  baseline, evaluated with cross-fitted doubly robust scores under the known
  design propensity.
* **The evaluator never sees evaluation outcomes during fitting.**  Nuisances
  are fitted on the training side of each outer fold and applied to the held
  out side; otherwise the score would be partly fitted to what it is scoring.
* **Every attempt is recorded**, including the ones that fail.  A candidate
  that cannot be fitted is ``FIT_FAILED``, not a zero -- dropping it would
  quietly improve the average of the survivors.
* **At most three representatives** are shortlisted: one outcome-ranking, one
  S/T learner, one DR learner.  An empty family is left empty rather than
  filled from another family to make the number three.

Nothing here touches the confirmation split.  Development scores are a
shortlist, not a result.
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
from sklearn.model_selection import StratifiedKFold

from .allocation import allocate_batch
from .candidates import BASELINES, CANDIDATES, build_candidate
from .policy_comparison import (
    design_asymmetry_index,
    dr_action_scores,
    paired_contrast,
)
from .problem_contract import ContractViolation

__all__ = [
    "CandidateResult",
    "CohortDesign",
    "ScreeningReport",
    "assert_gate_open",
    "gate_status",
    "main",
    "run_screening",
]

HOLD = "hold"
CONTACT = "contact"
CAPACITY_FRACTION = 0.2
OUTER_FOLDS = 3
BASELINE_ID = "M01"

#: Every place an R01 verdict may live.  The gate reads them all and uses the
#: best-powered one rather than a fixed order: a later run at fewer worlds
#: should not override an earlier, larger one.
GATE_ARTIFACTS: tuple[str, ...] = (
    "reports/v4/validity_unshrunk/validity_suite.json",
    "reports/v4/validity_confirm/validity_suite.json",
    "reports/v4/validity/validity_suite.json",
    "reports/v4/validity_skewness/validity_suite.json",
    "reports/v4/validity_skew_t/validity_suite.json",
)


#: The measured coverage boundary.  The imbalance rule the gate used first is
#: not a rule at all -- the same imbalance passes at one event rate and fails
#: at another -- so when this artifact exists the gate prefers it.
BOUNDARY_ARTIFACT = "reports/v4/overlap_boundary/overlap_boundary.json"

#: The out-of-sample check on that boundary.  The sweep separated its own
#: cells perfectly, but the sweep is the grid the index was derived on, and
#: on fresh frames the separation did not hold: designs at A = 0.20 covered
#: anywhere from 0.926 to 0.948.  Where this artifact disagrees with the
#: sweep it wins, because it is the evidence that was not fitted.
TRANSFER_ARTIFACT = "reports/v4/asymmetry_transfer/asymmetry_transfer.json"


@dataclass(frozen=True)
class CohortDesign:
    """What a caller must declare before the gate can license its cohort.

    Declaring only a propensity is not enough.  The event rate, the frame size
    and the share of rows the policy actually moves are amplifiers of the same
    asymmetry, so a balanced-looking cohort with a very rare outcome and a
    small acted share can sit further outside the validated region than an
    imbalanced one with plenty of events.
    """

    n_units: int
    propensity: float
    event_rate: float
    acted_fraction: float = 1.0

    @property
    def asymmetry_index(self) -> float:
        """``|A|``, or ``inf`` for a design the formula cannot describe.

        The primitive refuses a degenerate propensity, because a formula
        should not silently return a number for an input outside its domain.
        A *cohort* with such a design is a different matter: it is not a
        crash, it is a cohort with an arm that is never observed, and the
        honest index for it is infinite -- which is exactly what makes the
        gate refuse it below.
        """

        try:
            return abs(
                design_asymmetry_index(
                    n_units=self.n_units,
                    propensity=self.propensity,
                    event_rate=self.event_rate,
                    acted_fraction=self.acted_fraction,
                )
            )
        except ContractViolation:
            return float("inf")

    def to_dict(self) -> dict[str, Any]:
        index = self.asymmetry_index
        return {
            **asdict(self),
            "asymmetry_index": None if index == float("inf") else round(index, 6),
        }


def _out_of_sample_ceiling(root: Path | str) -> tuple[float | None, str]:
    """The strictest ceiling the transfer study allows, if it has run.

    The transfer study holds ``A`` fixed and varies frame size, acted
    fraction and event rate -- frames the index was never fitted on.  Its
    verdict is the honest one, and it was harsher than the sweep's: the
    sweep separated 18/18 of its own cells, the transfer study separated
    none of its 28.

    The ceiling is the largest tested level at which *every* design covered.
    If even the lowest tested level had a failure there is no such level, and
    the ceiling becomes "strictly below the smallest level where anything
    failed" -- conservative, and still grounded in what was observed rather
    than extrapolated past it.
    """

    path = Path(root) / TRANSFER_ARTIFACT
    if not path.exists():
        return None, ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, ""

    rows = [row for row in payload.get("results", []) if row.get("arm") == "constant_propensity"]
    if not rows:
        return None, ""

    levels = sorted({float(row["target_asymmetry"]) for row in rows})
    failing = {float(row["target_asymmetry"]) for row in rows if not row.get("passes", True)}
    clean = [level for level in levels if level not in failing]
    worlds = payload.get("worlds_per_design")
    if clean and (not failing or max(clean) < min(failing)):
        ceiling = max(clean)
        return ceiling, (
            f"the transfer study covered every design up to A = {ceiling:.3f} "
            f"across {len(rows)} out-of-sample designs at {worlds} worlds each"
        )
    smallest_failing = min(failing)
    # The first failed level is excluded. Returning it directly would make
    # gate_status's <= check license exactly the level that failed.
    return float(np.nextafter(smallest_failing, -np.inf)), (
        f"the transfer study saw a design fail at A = {smallest_failing:.3f}, its "
        f"lowest clean level, so the licence stops strictly below that "
        f"({len(rows)} out-of-sample designs at {worlds} worlds each)"
    )


def _licensed_asymmetry(root: Path | str, method: str) -> tuple[float | None, str]:
    """The largest asymmetry this interval method may be licensed for.

    Two artifacts can speak.  The sweep measured where coverage fails as ``A``
    grows; the transfer study then checked whether that threshold survives on
    frames the index was not derived from, and it did not survive intact.
    Where they disagree the stricter one governs, because a threshold fitted
    on its own grid is not evidence about a new cohort.

    Returns ``None`` when there is no sweep, when the sweep never scored this
    method, or when the sweep found that the index does not order its cells --
    in which case there is no threshold to apply and the gate must not invent
    one.
    """

    path = Path(root) / BOUNDARY_ARTIFACT
    if not path.exists():
        return None, "no boundary sweep on disk"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "boundary sweep unreadable"
    entry = payload.get("boundary_by_asymmetry", {}).get(method)
    if entry is None:
        return None, f"the boundary sweep did not score the {method} interval"
    if not entry.get("separates"):
        return None, (
            f"the boundary sweep found the asymmetry index does not order its "
            f"{method} cells, so it yields no threshold"
        )
    threshold = entry.get("licensed_threshold")
    if threshold is None:
        return None, f"the boundary sweep licensed no threshold for {method}"

    threshold = float(threshold)
    provenance = (
        f"measured over {entry.get('n_cells')} cells at "
        f"{payload.get('worlds_per_cell')} worlds each"
    )
    ceiling, ceiling_note = _out_of_sample_ceiling(root)
    if ceiling is not None and ceiling < threshold:
        return ceiling, (f"{provenance}, but tightened from {threshold:.3f} because {ceiling_note}")
    if ceiling is not None:
        provenance = f"{provenance}; {ceiling_note}"
    return threshold, provenance


def _read_gate(root: Path | str) -> tuple[dict[str, Any] | None, str]:
    """The best-powered R01 verdict available, and what else was considered."""

    base = Path(root)
    found: list[dict[str, Any]] = []
    seen: list[str] = []
    for relative in GATE_ARTIFACTS:
        candidate = base / relative
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            seen.append(f"{relative}: unreadable")
            continue
        payload["_artifact"] = relative
        found.append(payload)
    if not found:
        return None, "; ".join(seen) or "no R01 artifact on disk"
    # Most worlds first, then a passing run ahead of a failing one of equal size.
    found.sort(
        key=lambda item: (item.get("worlds_per_scenario", 0), bool(item.get("gate_passed"))),
        reverse=True,
    )
    chosen = found[0]

    # Preferring a passing run over a failing one of the same size is method
    # selection: if two interval methods were scored at equal power and only
    # one cleared the gate, taking that one is choosing after looking.  The
    # rule stays -- an equally powered pass is still the better evidence about
    # *that* method -- but it must not happen quietly, so the caller is told.
    power = chosen.get("worlds_per_scenario", 0)
    rivals = [
        item
        for item in found[1:]
        if item.get("worlds_per_scenario", 0) == power
        and bool(item.get("gate_passed")) != bool(chosen.get("gate_passed"))
    ]
    if rivals:
        chosen = {
            **chosen,
            "_selected_among": [
                f"{item['_artifact']} ({item.get('interval_method', 'normal')}: "
                f"{item.get('status')})"
                for item in rivals
            ],
        }
    return chosen, chosen["_artifact"]


def gate_status(
    root: Path | str = ".",
    *,
    cohort_propensity: float | None = None,
    cohort_design: CohortDesign | None = None,
) -> tuple[bool, str]:
    """Is R01 satisfied for a cohort like this one?

    A whole-gate PASS is the clean case.  A gate that fails on some scenarios
    can still license a study whose design sits inside the region the run did
    validate -- but only if the caller says what its design is, and only if the
    region actually covers it.  Silence is not consent: with no declared
    design the answer is the whole-gate verdict.

    There are two regional rules, and they are not equally good.

    ``cohort_design``
        The measured one.  The boundary sweep scored coverage across event
        rates *and* propensities and found that the asymmetry index orders the
        cells cleanly while imbalance does not -- the same imbalance passes at
        one event rate and fails at another.  When a caller declares a full
        design and a sweep exists, this rule governs, and it governs even when
        it is the *stricter* of the two.
    ``cohort_propensity``
        The older, weaker one, kept for callers that know only their
        propensity.  It ignores the event rate, the frame size and the acted
        share, so it can license a cohort the measured rule would refuse; the
        detail string says so whenever it is what granted the licence.
    """

    payload, detail = _read_gate(root)
    if payload is None:
        return False, f"{detail}; run python -m telco_churn.validity_suite"

    artifact = payload["_artifact"]
    worlds = payload.get("worlds_per_scenario")
    method = payload.get("interval_method", "normal")
    selected_among = payload.get("_selected_among")
    caveat = (
        ""
        if not selected_among
        else (
            f" -- SELECTED AFTER LOOKING: {len(selected_among)} other run(s) at the same "
            f"{worlds} worlds disagree ({'; '.join(selected_among)}), so this verdict is "
            "a post-hoc choice of interval method and needs independent confirmation"
        )
    )
    failures = payload.get("coverage_failures", [])
    summary = f"{artifact}: {payload.get('status')} at {worlds} worlds with the {method} interval"
    if not payload.get("gate_passed"):
        summary += f" ({len(failures)} undercovering)"
    summary += caveat

    if cohort_design is not None:
        index = cohort_design.asymmetry_index
        threshold, provenance = _licensed_asymmetry(root, method)
        if threshold is None:
            return False, (
                f"{summary}; this cohort declares an asymmetry index of {index:.4f} but "
                f"{provenance}, so there is no measured region to license it"
            )
        if index <= threshold:
            return True, (
                f"{summary}, but this cohort's asymmetry index is {index:.4f}, at or below "
                f"the {threshold:.3f} that the {method} interval was measured to cover "
                f"({provenance})"
            )
        return False, (
            f"{summary}; this cohort's asymmetry index {index:.4f} exceeds the {threshold:.3f} "
            f"that the {method} interval was measured to cover ({provenance})"
        )

    if payload.get("gate_passed") and cohort_propensity is None:
        return True, summary

    region = payload.get("validated_design_region")
    if cohort_propensity is None or not region:
        return False, summary

    imbalance = abs(float(cohort_propensity) - 0.5)
    validated = float(region.get("max_propensity_imbalance_validated", 0.0))
    smallest_failing = float(region.get("smallest_failing_imbalance", 0.0))
    if imbalance <= validated < smallest_failing:
        return True, (
            f"{summary}, but this cohort's design imbalance is {imbalance:.4f}, inside the "
            f"region validated by {', '.join(region.get('validated_scenarios', []))} "
            f"(up to {validated:.2f}); the failing scenarios sit at {smallest_failing:.2f} "
            "and above. This is the imbalance rule, which ignores the event rate and the "
            "frame size; declare a full CohortDesign to be judged on the measured boundary"
        )
    return False, (
        f"{summary}; this cohort's imbalance {imbalance:.4f} is not inside the validated "
        f"region (up to {validated:.2f})"
    )


def assert_gate_open(
    root: Path | str = ".",
    *,
    cohort_propensity: float | None = None,
    cohort_design: CohortDesign | None = None,
) -> None:
    """Refuse to screen models behind a failed evaluator gate."""

    passed, detail = gate_status(
        root, cohort_propensity=cohort_propensity, cohort_design=cohort_design
    )
    if not passed:
        raise RuntimeError(
            "R02 is gated on R01 and R01 does not license this cohort. "
            f"{detail}. Screening now would rank eight models with an evaluator whose "
            "intervals are known to be wrong for this design."
        )


@dataclass
class CandidateResult:
    candidate_id: str
    name: str
    family: str
    score_kind: str
    status: str
    fold_values: list[float] = field(default_factory=list)
    fold_deltas_vs_baseline: list[float] = field(default_factory=list)
    n_selected: list[int] = field(default_factory=list)
    mean_value: float = float("nan")
    mean_delta_vs_baseline: float = float("nan")
    delta_ci_low: float = float("nan")
    delta_ci_high: float = float("nan")
    seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreeningReport:
    dataset: str
    started_at: str
    gate_detail: str
    capacity_fraction: float
    outer_folds: int
    n_units: int
    n_treated: int
    n_events: int
    propensity: float
    design: CohortDesign | None = None
    results: list[CandidateResult] = field(default_factory=list)
    shortlist: list[str] = field(default_factory=list)
    runtime_seconds: float = 0.0

    @property
    def completed(self) -> list[CandidateResult]:
        return [result for result in self.results if result.status == "COMPLETED"]

    @property
    def failed(self) -> list[CandidateResult]:
        return [result for result in self.results if result.status != "COMPLETED"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": "R02_model_screening",
            "dataset": self.dataset,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "gate": self.gate_detail,
            "protocol": {
                "capacity_fraction": self.capacity_fraction,
                "outer_folds": self.outer_folds,
                "baseline": BASELINE_ID,
                "evaluator": "cross-fitted paired DR under the known design propensity",
                "nuisance_fitted_on": "training side of each outer fold only",
                "split": "development only; the confirmation split is not opened",
            },
            "cohort": {
                "n_units": self.n_units,
                "n_treated": self.n_treated,
                "n_events": self.n_events,
                "propensity": self.propensity,
                "declared_design": None if self.design is None else self.design.to_dict(),
            },
            "n_completed": len(self.completed),
            "n_failed": len(self.failed),
            "shortlist": self.shortlist,
            "results": [result.to_dict() for result in self.results],
            "scope_note": (
                "Development shortlist only. These are not confirmatory results and the "
                "ranking may not be read as evidence that one method beats another; the "
                "intervals are over three outer folds of one dataset."
            ),
        }


def _design_frames(n: int, propensity: float) -> pd.DataFrame:
    return pd.DataFrame({HOLD: np.full(n, 1.0 - propensity), CONTACT: np.full(n, propensity)})


def _evaluate_fold(
    scores: np.ndarray,
    unit_id: Sequence[Any],
    reward: np.ndarray,
    treatment: np.ndarray,
    mu0: np.ndarray,
    mu1: np.ndarray,
    propensity: float,
) -> tuple[float, int]:
    """Policy value at the declared cap, against a no-contact baseline."""

    allocation = allocate_batch(
        [str(value) for value in unit_id],
        scores,
        fraction=CAPACITY_FRACTION,
        require_positive=False,
    )
    chosen = allocation.frame["selected"].to_numpy()
    action = np.where(treatment == 1, CONTACT, HOLD)
    design = _design_frames(len(reward), propensity)
    nuisance = pd.DataFrame({HOLD: mu0, CONTACT: mu1})
    action_scores = dr_action_scores(reward, action, design, nuisance)
    policy = np.where(chosen, CONTACT, HOLD)
    baseline = np.full(len(reward), HOLD)
    contrast = paired_contrast(action_scores, policy, baseline)
    return contrast.delta, int(chosen.sum())


def _fold_nuisance(
    train_features: pd.DataFrame,
    train_treatment: np.ndarray,
    train_reward: np.ndarray,
    score_features: pd.DataFrame,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Arm means fitted on the training side, applied to the held-out side."""

    from .candidates import _logistic, _positive_probability

    means = []
    for label in (0, 1):
        rows = train_treatment == label
        target = train_reward[rows].astype(int)
        if rows.sum() < 2 or len(np.unique(target)) < 2:
            means.append(np.full(len(score_features), float(train_reward[rows].mean())))
            continue
        model = _logistic(train_features, seed=seed + label)
        model.fit(train_features.loc[rows], target)
        means.append(_positive_probability(model, score_features))
    return means[0], means[1]


def run_screening(
    features: pd.DataFrame,
    treatment: Sequence[int] | np.ndarray,
    reward: Sequence[float] | np.ndarray,
    unit_id: Sequence[Any],
    *,
    dataset: str,
    propensity: float,
    seed: int = 20260921,
    root: Path | str = ".",
    require_gate: bool = True,
    candidates: Sequence[str] | None = None,
) -> ScreeningReport:
    """Screen the declared candidates over common outer folds."""

    arm = np.asarray(treatment, dtype=int)
    value = np.asarray(reward, dtype=float)

    # The gate is asked about this cohort's whole design, not just its
    # propensity.  The rate that matters is the rarer tail of the reward: that
    # is the side whose residual produces the heavy weighted spikes, and for a
    # mostly-one reward it is 1 - mean, not the mean.
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
    report = ScreeningReport(
        dataset=dataset,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        gate_detail=detail,
        capacity_fraction=CAPACITY_FRACTION,
        outer_folds=OUTER_FOLDS,
        n_units=len(features),
        n_treated=int(arm.sum()),
        n_events=int(value.sum()),
        propensity=float(propensity),
        design=design,
    )

    # One fold assignment, shared by every candidate: the comparison is between
    # recipes, not between the splits they happened to get.
    strata = arm * 2 + (value > 0).astype(int)
    splitter = StratifiedKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=seed)
    folds = list(splitter.split(features, strata))

    wanted = list(candidates) if candidates else [spec.candidate_id for spec in CANDIDATES]
    catalogue = {spec.candidate_id: spec for spec in (*CANDIDATES, *BASELINES)}

    # Cache the per-fold evaluator nuisances: they depend on the fold, not on
    # the candidate, and refitting them per candidate would be waste and drift.
    nuisances: list[tuple[np.ndarray, np.ndarray]] = []
    for train_index, score_index in folds:
        nuisances.append(
            _fold_nuisance(
                features.iloc[train_index],
                arm[train_index],
                value[train_index],
                features.iloc[score_index],
                seed,
            )
        )

    baseline_folds: list[float] = []
    for candidate_id in [BASELINE_ID, *[item for item in wanted if item != BASELINE_ID]]:
        spec = catalogue.get(candidate_id)
        if spec is None:
            report.results.append(
                CandidateResult(candidate_id, candidate_id, "?", "?", "UNKNOWN_CANDIDATE")
            )
            continue
        result = CandidateResult(
            candidate_id=spec.candidate_id,
            name=spec.name,
            family=spec.family,
            score_kind=spec.score_kind,
            status="COMPLETED",
        )
        candidate_started = time.perf_counter()
        try:
            for fold_index, (train_index, score_index) in enumerate(folds):
                candidate = build_candidate(candidate_id, seed=seed + fold_index)
                if spec.trainable:
                    candidate.fit(
                        features.iloc[train_index],
                        arm[train_index],
                        value[train_index],
                        propensity=propensity,
                    )
                held_out = features.iloc[score_index]
                ids = [unit_id[index] for index in score_index]
                scores = candidate.score(held_out, unit_id=ids)
                mu0, mu1 = nuisances[fold_index]
                fold_value, selected = _evaluate_fold(
                    scores,
                    ids,
                    value[score_index],
                    arm[score_index],
                    mu0,
                    mu1,
                    propensity,
                )
                result.fold_values.append(fold_value)
                result.n_selected.append(selected)
        except Exception as error:  # noqa: BLE001 - a failed fit is recorded, never dropped
            result.status = "FIT_FAILED"
            result.error = f"{type(error).__name__}: {error}"
        result.seconds = time.perf_counter() - candidate_started

        if result.status == "COMPLETED":
            result.mean_value = float(np.mean(result.fold_values))
            if candidate_id == BASELINE_ID:
                baseline_folds = list(result.fold_values)
                result.fold_deltas_vs_baseline = [0.0] * len(baseline_folds)
                result.mean_delta_vs_baseline = 0.0
            elif baseline_folds:
                # Paired across the same folds: two independent error bars
                # would not answer whether this candidate beats the baseline.
                deltas = [
                    candidate_value - baseline_value
                    for candidate_value, baseline_value in zip(
                        result.fold_values, baseline_folds, strict=True
                    )
                ]
                result.fold_deltas_vs_baseline = deltas
                result.mean_delta_vs_baseline = float(np.mean(deltas))
                spread = float(np.std(deltas, ddof=1)) if len(deltas) > 1 else float("nan")
                half = (
                    1.959963984540054 * spread / np.sqrt(len(deltas))
                    if np.isfinite(spread)
                    else 0.0
                )
                result.delta_ci_low = result.mean_delta_vs_baseline - half
                result.delta_ci_high = result.mean_delta_vs_baseline + half
        report.results.append(result)

    report.shortlist = _shortlist(report)
    report.runtime_seconds = time.perf_counter() - started
    return report


def _shortlist(report: ScreeningReport) -> list[str]:
    """One representative per family, at most three, best mean value first."""

    groups = {"outcome_ranking": [], "s_learner": [], "t_learner": [], "dr_learner": []}
    for result in report.completed:
        if result.family in groups:
            groups[result.family].append(result)
    chosen: list[str] = []
    # S and T learners compete for one slot: the runbook asks for one S/T
    # representative, not one of each.
    merged = {
        "outcome_ranking": groups["outcome_ranking"],
        "s_or_t_learner": groups["s_learner"] + groups["t_learner"],
        "dr_learner": groups["dr_learner"],
    }
    for members in merged.values():
        if not members:
            continue  # an empty family stays empty
        best = max(members, key=lambda item: item.mean_value)
        chosen.append(best.candidate_id)
    return chosen


def render_markdown(report: ScreeningReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R02 — model screening",
        "",
        f"{report.dataset} · {report.n_units:,} units · {report.n_events:,} events · "
        f"e = {report.propensity:.4f} · {report.outer_folds} outer folds · "
        f"cap {report.capacity_fraction:.0%} · {report.runtime_seconds:.0f} s",
        "",
        f"Gate: {report.gate_detail}",
        "",
        payload["scope_note"],
        "",
        "| ID | Candidate | Family | Score kind | Mean value | Δ vs M01 | 95% over folds | Status |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for result in report.results:
        if result.status != "COMPLETED":
            lines.append(
                f"| {result.candidate_id} | {result.name} | {result.family} "
                f"| {result.score_kind} | — | — | — | **{result.status}**: {result.error} |"
            )
            continue
        interval = (
            f"[{result.delta_ci_low:+.5f}, {result.delta_ci_high:+.5f}]"
            if np.isfinite(result.delta_ci_low)
            else "—"
        )
        lines.append(
            f"| {result.candidate_id} | {result.name} | {result.family} | {result.score_kind} "
            f"| {result.mean_value:+.5f} | {result.mean_delta_vs_baseline:+.5f} | {interval} "
            f"| {result.status} |"
        )
    lines.extend(
        [
            "",
            f"**Shortlist:** {', '.join(report.shortlist) or 'none'} "
            "(one representative per family, best mean value).",
            "",
            "The interval is over three outer folds of one dataset. It describes fold "
            "variation, not population uncertainty, and it is not a confirmation result.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="reports/screening")
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument(
        "--treatment-arm",
        default="Mens E-Mail",
        help="the arm compared against the control arm",
    )
    parser.add_argument(
        "--force-without-gate",
        action="store_true",
        help="run even though R01 has not passed; the report is stamped as ungated",
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

    try:
        report = run_screening(
            features,
            treatment,
            reward,
            pair["row_id"].tolist(),
            dataset=f"hillstrom {args.treatment_arm} vs {CONTROL_ARM} (development)",
            propensity=float(treatment.mean()),
            seed=args.seed,
            root=args.root,
            require_gate=not args.force_without_gate,
        )
    except RuntimeError as error:
        print(f"R02 refused to run: {error}")
        return 1

    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "screening.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "SCREENING_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for result in report.results:
        if result.status == "COMPLETED":
            print(
                f"[ok  ] {result.candidate_id} {result.name:<34} "
                f"value {result.mean_value:+.5f} delta {result.mean_delta_vs_baseline:+.5f} "
                f"({result.seconds:.1f}s)"
            )
        else:
            print(f"[FAIL] {result.candidate_id} {result.name:<34} {result.status}: {result.error}")
    print(f"shortlist: {', '.join(report.shortlist) or 'none'}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
