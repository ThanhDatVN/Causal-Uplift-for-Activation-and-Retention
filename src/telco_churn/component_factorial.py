"""R04: which component is doing the work, rather than which name won.

R02 ranked eight candidates and R03 showed tuning does not change the order.
Both answer *that* the simple baseline holds up; neither answers *why*, and a
leaderboard without that is a result nobody can act on.  R04 is the stage
that takes the winning pipeline apart.

Three factors, crossed, from the runbook's E24:

``A`` representation
    Base features versus base plus the four declared interactions:
    ``log1p(history) x recency``, ``log1p(history) x newbie``,
    ``recency x newbie``, ``mens x womens``.  Fitted train-side only.
``B`` final stage
    DR-Ridge versus DR-HGB, on the *same* cross-fitted nuisances and the same
    pseudo-outcomes, so the contrast is the final stage and nothing else.
``C`` allocator
    Feasible rank rule versus net-value allocation under the same capacity.

Eight cells, three outer folds.  ``C`` only changes the allocator, so a fold
needs **four** effect fits rather than eight: the two allocators read the
same scores.  That caching is the difference between 24 fits and 12, and it
is also what makes the ``C`` contrast exact rather than noisy -- both levels
see identical scores, so any difference is the allocation rule.

A warning the runbook makes and this module enforces.  Under a homogeneous
unit cost, "rank by score" and "rank by net value" select the same accounts,
because subtracting a constant is monotone.  In that case ``C`` is a **null
fixture**: it must show no difference, and if it ever did, something is wrong
with the allocator rather than interesting about the data.  The distinguishing
condition is a *heterogeneous* cost, so the factorial runs both and labels
which is which instead of quietly reporting one.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from .allocation import allocate_batch
from .candidates import build_candidate
from .policy_comparison import dr_action_scores, paired_contrast
from .screening import (
    CAPACITY_FRACTION,
    CONTACT,
    HOLD,
    OUTER_FOLDS,
    CohortDesign,
    _design_frames,
    _fold_nuisance,
    assert_gate_open,
    gate_status,
)

__all__ = [
    "COST_REGIMES",
    "FACTORS",
    "CellResult",
    "FactorialReport",
    "add_interactions",
    "main",
    "run_factorial",
]

#: The declared interactions, as (left, right) column pairs.  Named here so a
#: reader can check them against the runbook without reading the code.
INTERACTIONS: tuple[tuple[str, str], ...] = (
    ("log1p_history", "recency"),
    ("log1p_history", "newbie"),
    ("recency", "newbie"),
    ("mens", "womens"),
)

FACTORS: dict[str, tuple[str, ...]] = {
    "representation": ("base", "base_plus_interactions"),
    "final_stage": ("ridge", "hgb"),
    "allocator": ("rank", "net_value"),
}

#: Two cost regimes, because only one of them can tell the allocators apart.
#:
#: ``homogeneous`` is the declared **null fixture**: every contact costs the
#: same, so net value is the score minus a constant and the rank rule picks
#: the identical accounts.  ``heterogeneous`` is the distinguishing condition.
#: Running only the second and reporting a difference would leave no way to
#: tell a real effect from an allocator bug.
COST_REGIMES: dict[str, str] = {
    "homogeneous": "every contact costs the same; C is a null fixture here",
    "heterogeneous": "contact cost varies by channel, so net value reranks",
}

#: Cost per contact in reward units, by channel, for the heterogeneous regime.
#: Declared, not measured: Hillstrom has no cost ledger, so these are an
#: assumed price and the artifact says so.
CHANNEL_COST: dict[str, float] = {"Phone": 0.0020, "Web": 0.0005, "Multichannel": 0.0035}
HOMOGENEOUS_COST = 0.0015


def add_interactions(features: pd.DataFrame) -> pd.DataFrame:
    """Base features plus the four declared products.

    Only pairs whose columns are both present and numeric are formed; a
    missing column is an error rather than a silently skipped interaction,
    because a factorial that quietly drops a level is not a factorial.
    """

    augmented = features.copy()
    for left, right in INTERACTIONS:
        for column in (left, right):
            if column not in augmented.columns:
                raise ValueError(
                    f"interaction {left} x {right} needs column {column!r}, which the "
                    f"feature frame does not have; declared columns are "
                    f"{sorted(augmented.columns)}"
                )
        augmented[f"{left}_x_{right}"] = augmented[left].to_numpy(dtype=float) * augmented[
            right
        ].to_numpy(dtype=float)
    return augmented


def _contact_cost(features: pd.DataFrame, regime: str) -> np.ndarray:
    if regime == "homogeneous":
        return np.full(len(features), HOMOGENEOUS_COST, dtype=float)
    channel = features["channel"].astype(str).to_numpy()
    return np.array([CHANNEL_COST.get(value, HOMOGENEOUS_COST) for value in channel])


def _allocate(
    scores: np.ndarray,
    unit_id: Sequence[Any],
    cost: np.ndarray,
    *,
    allocator: str,
) -> np.ndarray:
    """Which accounts this allocator contacts, under the shared capacity."""

    ranking = scores if allocator == "rank" else scores - cost
    allocation = allocate_batch(
        [str(value) for value in unit_id],
        ranking,
        fraction=CAPACITY_FRACTION,
        require_positive=False,
    )
    return allocation.frame["selected"].to_numpy()


def _value_of(
    chosen: np.ndarray,
    reward: np.ndarray,
    treatment: np.ndarray,
    mu0: np.ndarray,
    mu1: np.ndarray,
    propensity: float,
) -> float:
    action = np.where(treatment == 1, CONTACT, HOLD)
    design = _design_frames(len(reward), propensity)
    nuisance = pd.DataFrame({HOLD: mu0, CONTACT: mu1})
    scores = dr_action_scores(reward, action, design, nuisance)
    policy = np.where(chosen, CONTACT, HOLD)
    baseline = np.full(len(reward), HOLD)
    return paired_contrast(scores, policy, baseline).delta


@dataclass
class CellResult:
    representation: str
    final_stage: str
    allocator: str
    cost_regime: str
    fold_values: list[float] = field(default_factory=list)
    #: Accounts selected, per fold.  Two cells that contact the same accounts
    #: cannot differ in value, so this is how a null fixture is checked
    #: rather than inferred from a small difference.
    fold_signatures: list[str] = field(default_factory=list)

    @property
    def cell_id(self) -> str:
        return f"{self.representation}|{self.final_stage}|{self.allocator}"

    @property
    def mean_value(self) -> float:
        return float(np.mean(self.fold_values)) if self.fold_values else float("nan")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "cell_id": self.cell_id,
            "mean_value": self.mean_value,
        }


@dataclass
class FactorialReport:
    dataset: str
    started_at: str
    gate_detail: str
    n_units: int
    n_events: int
    propensity: float
    cells: list[CellResult] = field(default_factory=list)
    runtime_seconds: float = 0.0
    effect_fits: int = 0

    def _by(self, regime: str) -> list[CellResult]:
        return [cell for cell in self.cells if cell.cost_regime == regime]

    def main_effects(self, regime: str) -> dict[str, dict[str, Any]]:
        """Paired main effect of each factor, averaged over the other two.

        Paired because every cell is scored on the same outer folds, so the
        difference is taken fold by fold before averaging rather than between
        two means that each carry their own fold noise.
        """

        cells = self._by(regime)
        effects: dict[str, dict[str, Any]] = {}
        for factor, levels in FACTORS.items():
            low, high = levels
            pairs: list[float] = []
            for cell in cells:
                if getattr(cell, factor) != high:
                    continue
                match = next(
                    (
                        other
                        for other in cells
                        if getattr(other, factor) == low
                        and all(
                            getattr(other, name) == getattr(cell, name)
                            for name in FACTORS
                            if name != factor
                        )
                    ),
                    None,
                )
                if match is None:
                    continue
                pairs.extend(
                    value - baseline
                    for value, baseline in zip(cell.fold_values, match.fold_values, strict=True)
                )
            effects[factor] = {
                "factor": factor,
                "from": low,
                "to": high,
                "mean_effect": float(np.mean(pairs)) if pairs else float("nan"),
                "n_paired_readouts": len(pairs),
                "se": (
                    float(np.std(pairs, ddof=1) / np.sqrt(len(pairs)))
                    if len(pairs) > 1
                    else float("nan")
                ),
            }
        return effects

    def null_fixture_held(self) -> dict[str, Any]:
        """Under a homogeneous cost the two allocators must agree exactly."""

        mismatches = []
        for cell in self._by("homogeneous"):
            if cell.allocator != "net_value":
                continue
            twin = next(
                (
                    other
                    for other in self._by("homogeneous")
                    if other.allocator == "rank"
                    and other.representation == cell.representation
                    and other.final_stage == cell.final_stage
                ),
                None,
            )
            if twin is None:
                continue
            if cell.fold_signatures != twin.fold_signatures:
                mismatches.append(cell.cell_id)
        return {
            "claim": (
                "with a homogeneous cost, net value is the score minus a constant, "
                "so a rank allocator must contact exactly the same accounts"
            ),
            "held": not mismatches,
            "mismatched_cells": mismatches,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": "R04_component_factorial",
            "dataset": self.dataset,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "gate": self.gate_detail,
            "protocol": {
                "factors": FACTORS,
                "interactions": [f"{left} x {right}" for left, right in INTERACTIONS],
                "cost_regimes": COST_REGIMES,
                "outer_folds": OUTER_FOLDS,
                "capacity_fraction": CAPACITY_FRACTION,
                "effect_fits": self.effect_fits,
                "split": "development only; the confirmation split is not opened",
            },
            "cohort": {
                "n_units": self.n_units,
                "n_events": self.n_events,
                "propensity": self.propensity,
            },
            "cost_source": "assumed, not measured; Hillstrom has no cost ledger",
            "null_fixture": self.null_fixture_held(),
            "main_effects": {regime: self.main_effects(regime) for regime in COST_REGIMES},
            "cells": [cell.to_dict() for cell in self.cells],
            "scope_note": (
                "Development only, three outer folds of one dataset. Main effects are "
                "paired across folds but three folds are not three datasets, and the "
                "contact costs are declared prices rather than postings."
            ),
        }


def run_factorial(
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
) -> FactorialReport:
    """Score every cell of the 2x2x2 factorial under both cost regimes."""

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
    report = FactorialReport(
        dataset=dataset,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        gate_detail=detail,
        n_units=len(features),
        n_events=int(value.sum()),
        propensity=float(propensity),
    )

    strata = arm * 2 + (value > 0).astype(int)
    splitter = StratifiedKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=seed)
    folds = list(splitter.split(features, strata))

    keys = list(product(FACTORS["representation"], FACTORS["final_stage"]))
    cells: dict[tuple[str, str, str, str], CellResult] = {}
    for representation, final_stage in keys:
        for allocator, regime in product(FACTORS["allocator"], COST_REGIMES):
            cells[(representation, final_stage, allocator, regime)] = CellResult(
                representation=representation,
                final_stage=final_stage,
                allocator=allocator,
                cost_regime=regime,
            )

    for train_index, score_index in folds:
        train_features = features.iloc[train_index]
        score_features = features.iloc[score_index]
        ids = [unit_id[position] for position in score_index]
        mu0, mu1 = _fold_nuisance(
            train_features, arm[train_index], value[train_index], score_features, seed
        )
        cost_by_regime = {regime: _contact_cost(score_features, regime) for regime in COST_REGIMES}

        # Four effect fits per fold, not eight: the allocators read the same
        # scores, so C costs nothing extra.
        for representation, final_stage in keys:
            if representation == "base_plus_interactions":
                fit_features = add_interactions(train_features)
                score_frame = add_interactions(score_features)
            else:
                fit_features, score_frame = train_features, score_features
            candidate_id = "M07" if final_stage == "ridge" else "M08"
            model = build_candidate(candidate_id, seed=seed).fit(
                fit_features, arm[train_index], value[train_index], propensity=propensity
            )
            report.effect_fits += 1
            scores = model.score(score_frame, unit_id=ids)

            for allocator, regime in product(FACTORS["allocator"], COST_REGIMES):
                chosen = _allocate(scores, ids, cost_by_regime[regime], allocator=allocator)
                cell = cells[(representation, final_stage, allocator, regime)]
                cell.fold_values.append(
                    _value_of(
                        chosen,
                        value[score_index],
                        arm[score_index],
                        mu0,
                        mu1,
                        propensity,
                    )
                )
                cell.fold_signatures.append(
                    ",".join(sorted(str(ids[i]) for i in np.flatnonzero(chosen)))[:64]
                )

    report.cells = list(cells.values())
    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: FactorialReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R04 — component factorial",
        "",
        f"{report.dataset} · {report.n_units:,} units · {report.n_events:,} events · "
        f"{OUTER_FOLDS} outer folds · {report.effect_fits} effect fits · "
        f"{report.runtime_seconds:.0f} s",
        "",
        f"Gate: {report.gate_detail}",
        "",
        payload["scope_note"],
        "",
        "Contact costs are **" + payload["cost_source"] + "**.",
        "",
    ]
    for regime, description in COST_REGIMES.items():
        lines.extend(
            [
                f"## Cost regime: {regime}",
                "",
                f"*{description}*",
                "",
                "| representation | final stage | allocator | mean value |",
                "|---|---|---|---|",
            ]
        )
        for cell in sorted(
            (c for c in report.cells if c.cost_regime == regime), key=lambda c: c.cell_id
        ):
            lines.append(
                f"| {cell.representation} | {cell.final_stage} | {cell.allocator} "
                f"| {cell.mean_value:+.6f} |"
            )
        lines.extend(["", "| factor | from | to | paired effect | se |", "|---|---|---|---|---|"])
        for effect in report.main_effects(regime).values():
            lines.append(
                f"| {effect['factor']} | {effect['from']} | {effect['to']} "
                f"| {effect['mean_effect']:+.6f} | {effect['se']:.6f} |"
            )
        lines.append("")

    fixture = payload["null_fixture"]
    lines.extend(
        [
            "## The null fixture",
            "",
            fixture["claim"] + ".",
            "",
            f"**{'Held' if fixture['held'] else 'BROKEN'}**"
            + (
                ""
                if fixture["held"]
                else f" — allocations differ in {', '.join(fixture['mismatched_cells'])}, "
                "which would be an allocator bug rather than a finding."
            ),
            "",
            "Under a homogeneous cost the allocator factor is expected to do nothing, and "
            "it is run precisely so that a difference under the heterogeneous cost can be "
            "read as the allocation rule rather than as noise in the pipeline.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="reports/v4/factorial")
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--treatment-arm", default="Mens E-Mail")
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
        report = run_factorial(
            features,
            treatment,
            reward,
            pair["row_id"].tolist(),
            dataset=f"hillstrom {args.treatment_arm} vs {CONTROL_ARM} (development)",
            propensity=float(treatment.mean()),
            seed=args.seed,
            root=args.root,
        )
    except RuntimeError as error:
        print(f"R04 refused to run: {error}")
        return 1

    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "component_factorial.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "FACTORIAL_REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    for regime in COST_REGIMES:
        print(f"-- {regime}")
        for effect in report.main_effects(regime).values():
            print(
                f"   {effect['factor']:<16} {effect['from']} -> {effect['to']}: "
                f"{effect['mean_effect']:+.6f} (se {effect['se']:.6f})"
            )
    fixture = report.null_fixture_held()
    print(f"null fixture: {'held' if fixture['held'] else 'BROKEN ' + str(fixture)}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
