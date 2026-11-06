"""R07: a refresh strategy has to be replayed, not re-scored.

The runbook marks R07 ``BLOCKED_BY_IMPLEMENTATION`` until a proper replay
exists, and is specific about why: *"actions phải thay future state, không
tái chấm fixed logged trajectory như rollout truth"*.  The existing
simulator assigns treatment at random and cannot be driven by a policy, so
scoring strategies on its fixed log would measure how well each strategy
agrees with a random policy, which is not the question.

This module is that replay.  Each strategy drives its **own** trajectory:

1. At the start of each decision month the strategy scores the accounts
   still active in *its* world and contacts the top ``capacity`` of them.
2. The simulator advances that world given those contacts.  A contacted
   account's churn risk changes, and so do ``prior_offer_count`` and
   ``months_since_offer``, which feed the next month.  Contact fatigue means
   a strategy that contacts the same people every month earns less for it.
3. Churned accounts leave.  Two strategies therefore face **different
   cohorts** by month three, which is the whole point and is also why a
   logged-trajectory re-score cannot answer this.

Four strategies, from the runbook:

``frozen``
    Fit once on the training months, never refit.
``calibration_only``
    Refit the *intercept* monthly on matured labels.  The name is load
    bearing: it recalibrates level, and it is not a fix for effect drift.
``full_expanding``
    Refit on every matured month so far.
``rolling_6``
    Refit on the trailing six months of matured labels.

Labels mature with a declared delay, and a refit may only read labels that
had matured **before** its cutoff.  Without that, every strategy silently
trains on the future and the comparison is meaningless.

What this does not do.  There is no money here: the reward is prevented
churn, and the ledger reconciles decisions against outcomes rather than
against cash.  A few dozen worlds per mechanism is a sensitivity study, not
a precise estimate of any strategy's advantage, and the artifact states the
count it actually ran.
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

__all__ = [
    "DECISION_MONTHS",
    "LABEL_DELAY_MONTHS",
    "MECHANISMS",
    "STRATEGIES",
    "TRAINING_MONTHS",
    "StrategyOutcome",
    "TemporalReplayReport",
    "main",
    "run_temporal_replay",
]

N_ACCOUNTS = 3_000
TRAINING_MONTHS = 12
DECISION_MONTHS = 12
#: Labels are observed one month after the decision, so a refit at the start
#: of month m may use decisions up to and including month m - 2.
LABEL_DELAY_MONTHS = 1
CAPACITY_FRACTION = 0.10
ROLLING_WINDOW = 6

STRATEGIES: tuple[str, ...] = (
    "frozen",
    "calibration_only",
    "full_expanding",
    "rolling_6",
)

#: ``(label, description)``.  Each bends the world in a different direction,
#: and a strategy that only handles one of them is not robust.
MECHANISMS: tuple[tuple[str, str], ...] = (
    ("covariate_shift", "the population drifts toward higher-risk accounts"),
    ("effect_reversal", "the offer's effect weakens and then turns negative"),
    ("ingestion_delay", "labels arrive one month later than the strategy expects"),
)


def _namespace(label: str) -> int:
    return int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


#: Deciles of the observable feature.  A strategy sees ``x`` and has to
#: *learn* the risk attached to it, which is what makes a stale model stale.
RISK_BINS = 10


@dataclass
class _World:
    """Mutable account state for one strategy's own trajectory.

    ``x`` is the one thing a strategy can see.  ``risk_slope`` and
    ``lift_scale`` are the truth, and no strategy ever reads them: a
    strategy that knew the true risk would have nothing to learn, refitting
    could only add noise, and ``frozen`` would win by construction.  That
    was the first draft of this module and it measured nothing.
    """

    x: np.ndarray
    risk_slope: float
    risk_base: float
    lift_scale: float
    responsiveness: np.ndarray
    active: np.ndarray
    prior_offers: np.ndarray
    months_since_offer: np.ndarray

    @property
    def risk(self) -> np.ndarray:
        return np.clip(self.risk_base + self.risk_slope * self.x, 0.005, 0.95)

    def copy(self) -> _World:
        return _World(
            x=self.x.copy(),
            risk_slope=self.risk_slope,
            risk_base=self.risk_base,
            lift_scale=self.lift_scale,
            responsiveness=self.responsiveness.copy(),
            active=self.active.copy(),
            prior_offers=self.prior_offers.copy(),
            months_since_offer=self.months_since_offer.copy(),
        )


def _initial_world(rng: np.random.Generator) -> _World:
    return _World(
        x=rng.random(N_ACCOUNTS),
        risk_slope=0.18,
        risk_base=0.02,
        lift_scale=1.0,
        responsiveness=rng.beta(2.5, 3.0, N_ACCOUNTS),
        active=np.ones(N_ACCOUNTS, dtype=bool),
        prior_offers=np.zeros(N_ACCOUNTS, dtype=int),
        months_since_offer=np.full(N_ACCOUNTS, 12, dtype=int),
    )


def _drift(world: _World, month: int, mechanism: str, rng: np.random.Generator) -> None:
    """Bend the world.  Applied identically to every strategy's own copy."""

    progress = (month + 1) / DECISION_MONTHS
    if mechanism == "covariate_shift":
        # The risk attached to x reverses sign, so a stale risk model ranks
        # the wrong accounts first and refitting the risk model helps.
        world.risk_slope = 0.18 - 0.36 * progress
        world.risk_base = 0.02 + 0.18 * progress
    elif mechanism == "effect_reversal":
        # The offer's effect weakens and then turns harmful, which only a
        # strategy that refits the *lift* can notice.
        world.lift_scale = 1.0 - 2.2 * progress
    elif mechanism == "ingestion_delay":
        world.risk_slope = 0.18 - 0.20 * progress
        world.risk_base = 0.02 + 0.06 * progress


def _churn_probability(world: _World, contacted: np.ndarray) -> np.ndarray:
    """Churn risk this month, after the contact decision.

    Contact fatigue is the part that makes replay necessary: the same
    account contacted repeatedly responds less, so a strategy's own history
    changes what its future contacts are worth.
    """

    fatigue = 1.0 - 0.30 * np.clip(world.prior_offers, 0, 3) / 3.0
    lift = world.responsiveness * fatigue * world.lift_scale
    return np.clip(world.risk * (1.0 - lift * contacted), 0.0, 1.0)


def _advance(
    world: _World, contacted: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Realise churn, update history, and return (churned, counterfactual)."""

    probability = _churn_probability(world, contacted)
    draw = rng.random(N_ACCOUNTS)
    churned = (draw < probability) & world.active
    # The same draw against the no-contact risk: what would have happened
    # had nobody been contacted. Known only to the scorer, never to a
    # strategy, and used to report prevented churn without an estimator.
    counterfactual = (draw < _churn_probability(world, np.zeros(N_ACCOUNTS, dtype=bool))) & (
        world.active
    )

    world.prior_offers = world.prior_offers + contacted.astype(int)
    world.months_since_offer = np.where(contacted, 0, world.months_since_offer + 1)
    world.active = world.active & ~churned
    return churned, counterfactual


def _fit_scorer(history: list[dict[str, np.ndarray]], x: np.ndarray) -> dict[str, Any]:
    """Estimate a per-decile risk curve and an average lift, from matured months.

    Deliberately crude -- decile churn rates among *uncontacted* accounts for
    risk, and a difference of churn rates for lift.  The stage compares
    *refresh policies*, so a sophisticated learner would confound the two.
    The risk curve is what goes stale under covariate shift; the lift is what
    goes stale under effect reversal, and separating them is the only way
    ``calibration_only`` can mean anything.
    """

    bins = np.clip((x * RISK_BINS).astype(int), 0, RISK_BINS - 1)
    if not history:
        return {"risk_by_bin": np.full(RISK_BINS, 0.1), "lift": 0.0}

    contacted_churn: list[float] = []
    idle_churn: list[float] = []
    numerator = np.zeros(RISK_BINS)
    denominator = np.zeros(RISK_BINS)
    for month in history:
        contacted, churned, active = month["contacted"], month["churned"], month["active"]
        idle = ~contacted & active
        if contacted.any():
            contacted_churn.append(float(churned[contacted].mean()))
        if idle.any():
            idle_churn.append(float(churned[idle].mean()))
            np.add.at(numerator, bins[idle], churned[idle].astype(float))
            np.add.at(denominator, bins[idle], 1.0)

    overall = float(numerator.sum() / denominator.sum()) if denominator.sum() else 0.1
    risk_by_bin = np.where(denominator > 0, numerator / np.maximum(denominator, 1), overall)
    lift = (
        float(np.mean(idle_churn) - np.mean(contacted_churn))
        if contacted_churn and idle_churn
        else 0.0
    )
    return {"risk_by_bin": risk_by_bin, "lift": lift}


def _score_accounts(scorer: dict[str, Any], x: np.ndarray) -> np.ndarray:
    """Expected prevented churn per account, as the strategy believes it."""

    bins = np.clip((x * RISK_BINS).astype(int), 0, RISK_BINS - 1)
    return np.asarray(scorer["risk_by_bin"])[bins] * float(scorer["lift"])


def _matured(history: list[dict[str, np.ndarray]], month: int, delay: int) -> list[dict]:
    """Only months whose labels had arrived before this decision."""

    return [entry for entry in history if entry["month"] + delay < month]


def _refit_for(
    strategy: str,
    initial: dict[str, Any],
    history: list[dict[str, np.ndarray]],
    x: np.ndarray,
    month: int,
    delay: int,
) -> tuple[dict[str, Any], bool]:
    """The scorer this strategy uses this month, and whether it refitted."""

    matured = _matured(history, month, delay)
    if strategy == "frozen" or not matured:
        return initial, False
    if strategy == "calibration_only":
        # Risk only: the lift estimate stays where training left it, which is
        # exactly what "calibration" means and exactly why it cannot notice an
        # effect that has reversed.
        fresh = _fit_scorer(matured, x)
        return {"risk_by_bin": fresh["risk_by_bin"], "lift": initial["lift"]}, True
    if strategy == "full_expanding":
        return _fit_scorer(matured, x), True
    if strategy == "rolling_6":
        window = [entry for entry in matured if entry["month"] >= month - ROLLING_WINDOW]
        return _fit_scorer(window or matured, x), True
    raise ValueError(f"unknown strategy {strategy!r}")  # pragma: no cover


@dataclass
class StrategyOutcome:
    mechanism: str
    strategy: str
    world: int
    prevented_churn: float
    contacts: int
    refits: int
    #: Decisions minus outcomes, which must reconcile exactly: every contact
    #: is either followed by a churn or not, and nothing may be double
    #: counted across months.
    ledger_balanced: bool
    monthly_prevented: list[float] = field(default_factory=list)

    @property
    def late_prevented_churn(self) -> float:
        """The second half only, where a stale model has had time to go stale.

        The whole-horizon total is dominated by the early months: the active
        pool is largest, fatigue has not accumulated, and every strategy is
        still using the same freshly fitted model.  Averaging over that
        hides the very degradation the stage exists to measure, so both are
        reported and neither replaces the other.
        """

        half = len(self.monthly_prevented) // 2
        return float(np.sum(self.monthly_prevented[half:]))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "late_prevented_churn": self.late_prevented_churn}


@dataclass
class TemporalReplayReport:
    worlds_per_mechanism: int
    seed: int
    started_at: str
    outcomes: list[StrategyOutcome] = field(default_factory=list)
    runtime_seconds: float = 0.0

    def summary(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for mechanism, _description in MECHANISMS:
            frozen = [
                item.prevented_churn
                for item in self.outcomes
                if item.mechanism == mechanism and item.strategy == "frozen"
            ]
            frozen_late = [
                item.late_prevented_churn
                for item in self.outcomes
                if item.mechanism == mechanism and item.strategy == "frozen"
            ]
            for strategy in STRATEGIES:
                values = [
                    item.prevented_churn
                    for item in self.outcomes
                    if item.mechanism == mechanism and item.strategy == strategy
                ]
                late = [
                    item.late_prevented_churn
                    for item in self.outcomes
                    if item.mechanism == mechanism and item.strategy == strategy
                ]
                if not values:
                    continue
                paired_late = [value - base for value, base in zip(late, frozen_late, strict=True)]
                # Paired against frozen in the same world, because the worlds
                # differ in difficulty and an unpaired mean would mix that in.
                paired = [value - base for value, base in zip(values, frozen, strict=True)]
                rows.append(
                    {
                        "mechanism": mechanism,
                        "strategy": strategy,
                        "worlds": len(values),
                        "mean_prevented_churn": float(np.mean(values)),
                        "mean_late_prevented_churn": float(np.mean(late)),
                        "vs_frozen": float(np.mean(paired)),
                        "late_vs_frozen": float(np.mean(paired_late)),
                        "late_vs_frozen_se": (
                            float(np.std(paired_late, ddof=1) / np.sqrt(len(paired_late)))
                            if len(paired_late) > 1
                            else float("nan")
                        ),
                        "vs_frozen_se": (
                            float(np.std(paired, ddof=1) / np.sqrt(len(paired)))
                            if len(paired) > 1
                            else float("nan")
                        ),
                        "mean_refits": float(
                            np.mean(
                                [
                                    item.refits
                                    for item in self.outcomes
                                    if item.mechanism == mechanism and item.strategy == strategy
                                ]
                            )
                        ),
                    }
                )
        return rows

    def to_dict(self) -> dict[str, Any]:
        unbalanced = [
            f"{item.mechanism}:{item.strategy}:{item.world}"
            for item in self.outcomes
            if not item.ledger_balanced
        ]
        return {
            "study": "R07_temporal_replay",
            "worlds_per_mechanism": self.worlds_per_mechanism,
            "seed": self.seed,
            "started_at": self.started_at,
            "runtime_seconds": round(self.runtime_seconds, 2),
            "n_accounts": N_ACCOUNTS,
            "training_months": TRAINING_MONTHS,
            "decision_months": DECISION_MONTHS,
            "label_delay_months": LABEL_DELAY_MONTHS,
            "capacity_fraction": CAPACITY_FRACTION,
            "rolling_window": ROLLING_WINDOW,
            "strategies": list(STRATEGIES),
            "mechanisms": [{"mechanism": name, "description": text} for name, text in MECHANISMS],
            "replay": (
                "each strategy drives its own trajectory: its contacts change churn, "
                "contact history and who is still active, so two strategies face "
                "different cohorts within a few months. No strategy is re-scored on "
                "another's log."
            ),
            "ledger_balanced": not unbalanced,
            "unbalanced_runs": unbalanced,
            "summary": self.summary(),
            "outcomes": [item.to_dict() for item in self.outcomes],
            "scope_note": (
                "A mock world, not evidence about any operator. "
                f"{self.worlds_per_mechanism} worlds per mechanism is a sensitivity "
                "study; the paired standard errors are reported so nobody reads a "
                "small difference as an established one. The reward is prevented "
                "churn, not money: there is no cost ledger."
            ),
        }


def run_temporal_replay(*, worlds: int = 10, seed: int = 20260930) -> TemporalReplayReport:
    """Replay every strategy in its own trajectory, in each mechanism."""

    started = time.perf_counter()
    report = TemporalReplayReport(
        worlds_per_mechanism=worlds,
        seed=seed,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )

    for mechanism, _description in MECHANISMS:
        namespace = _namespace(f"R07:{mechanism}")
        for index in range(worlds):
            base_rng = np.random.default_rng([seed, namespace, index])
            start = _initial_world(base_rng)

            # A shared training history, drawn under random assignment, so
            # every strategy starts from the same fitted scorer.
            training_world = start.copy()
            training_history: list[dict[str, np.ndarray]] = []
            for month in range(-TRAINING_MONTHS, 0):
                contacted = (base_rng.random(N_ACCOUNTS) < CAPACITY_FRACTION) & (
                    training_world.active
                )
                active_before = training_world.active.copy()
                churned, _counterfactual = _advance(training_world, contacted, base_rng)
                training_history.append(
                    {
                        "month": month,
                        "contacted": contacted,
                        "churned": churned,
                        "active": active_before,
                    }
                )
            initial_scorer = _fit_scorer(training_history, start.x)

            delay = LABEL_DELAY_MONTHS + (1 if mechanism == "ingestion_delay" else 0)

            for strategy in STRATEGIES:
                # Same starting world and same shock stream for every
                # strategy, so they differ only through their own actions.
                world = training_world.copy()
                rng = np.random.default_rng([seed, namespace, index, 7])
                history = list(training_history)
                prevented: list[float] = []
                contacts = 0
                refits = 0
                ledger_ok = True

                for month in range(DECISION_MONTHS):
                    _drift(world, month, mechanism, rng)
                    scorer, did_refit = _refit_for(
                        strategy, initial_scorer, history, world.x, month, delay
                    )
                    refits += int(did_refit)

                    believed = _score_accounts(scorer, world.x)
                    score = np.where(world.active, believed, -np.inf)
                    capacity = int(world.active.sum() * CAPACITY_FRACTION)
                    contacted = np.zeros(N_ACCOUNTS, dtype=bool)
                    if capacity > 0:
                        chosen = np.argsort(-score, kind="stable")[:capacity]
                        contacted[chosen] = True
                        contacted &= world.active

                    active_before = world.active.copy()
                    churned, counterfactual = _advance(world, contacted, rng)
                    # Prevented churn: would have churned, did not.
                    prevented.append(
                        float((counterfactual & ~churned).sum() - (churned & ~counterfactual).sum())
                    )
                    contacts += int(contacted.sum())
                    # Reconciliation: nothing may be counted for an account
                    # that was not active, and no account may churn twice.
                    if (churned & ~active_before).any() or (contacted & ~active_before).any():
                        ledger_ok = False
                    history.append(
                        {
                            "month": month,
                            "contacted": contacted,
                            "churned": churned,
                            "active": active_before,
                        }
                    )

                report.outcomes.append(
                    StrategyOutcome(
                        mechanism=mechanism,
                        strategy=strategy,
                        world=index,
                        prevented_churn=float(np.sum(prevented)),
                        contacts=contacts,
                        refits=refits,
                        ledger_balanced=ledger_ok,
                        monthly_prevented=prevented,
                    )
                )

    report.runtime_seconds = time.perf_counter() - started
    return report


def render_markdown(report: TemporalReplayReport) -> str:
    payload = report.to_dict()
    lines = [
        "# R07 — temporal replay of refresh strategies",
        "",
        f"{report.worlds_per_mechanism} worlds per mechanism · {N_ACCOUNTS:,} accounts · "
        f"{TRAINING_MONTHS} training + {DECISION_MONTHS} decision months · "
        f"{report.runtime_seconds:.0f} s",
        "",
        "**" + payload["replay"] + "**",
        "",
        payload["scope_note"],
        "",
        f"Ledger reconciliation: **{'balanced' if payload['ledger_balanced'] else 'BROKEN'}**"
        + ("" if payload["ledger_balanced"] else f" — {', '.join(payload['unbalanced_runs'][:5])}"),
        "",
        "| mechanism | strategy | prevented (all) | vs frozen | prevented (late) "
        "| late vs frozen | se | refits |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report.summary():
        lines.append(
            f"| {row['mechanism']} | {row['strategy']} | {row['mean_prevented_churn']:,.1f} "
            f"| {row['vs_frozen']:+,.1f} | {row['mean_late_prevented_churn']:,.1f} "
            f"| {row['late_vs_frozen']:+,.1f} | {row['late_vs_frozen_se']:,.1f} "
            f"| {row['mean_refits']:.0f} |"
        )
    lines.extend(
        [
            "",
            "The **late** columns cover the second half of the horizon only. The "
            "whole-horizon total is dominated by the early months, when every strategy "
            "is still using the same freshly fitted model and the active pool is "
            "largest, so it hides the degradation this stage exists to measure.",
            "",
            "`vs frozen` is paired within each world, because the worlds differ in "
            "difficulty and an unpaired mean would mix that in. Under "
            "`effect_reversal` the offer eventually becomes harmful, so a strategy that "
            "keeps contacting on a stale lift estimate should lose ground -- and "
            "`calibration_only` refits the level while leaving the lift where training "
            "put it, which is why recalibration is not a fix for effect drift.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--output-dir", default="reports/v4/temporal_replay")
    args = parser.parse_args(argv)

    report = run_temporal_replay(worlds=args.worlds, seed=args.seed)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "temporal_replay.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "TEMPORAL_REPLAY.md").write_text(render_markdown(report), encoding="utf-8")
    for row in report.summary():
        print(
            f"{row['mechanism']:<18} {row['strategy']:<18} "
            f"prevented {row['mean_prevented_churn']:8,.1f} "
            f"vs frozen {row['vs_frozen']:+8,.1f} (se {row['vs_frozen_se']:,.1f}) "
            f"refits {row['mean_refits']:.0f}"
        )
    payload = report.to_dict()
    print(f"ledger: {'balanced' if payload['ledger_balanced'] else 'BROKEN'}")
    print(f"Report: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
