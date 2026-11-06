"""Reward specification, cost ledger and break-even stress (E22, backlog V4-05).

The module keeps three things apart that reports routinely blur:

* **Actual postings** versus **assumed costs.**  A public dataset has no cost
  ledger.  Anything derived from an assumed price keeps ``source="assumed"`` and
  cannot be reported as realised money.
* **Incremental cost** versus **allocated overhead.**  Overhead is reported, but
  it never enters the incremental reward of a decision.
* **One posting, one charge.**  The ledger rejects a repeated posting id and
  flags a repeated ``(account, action, kind)`` triple, which is what
  double-counting an offer cost actually looks like (mutation Q08).

Sign convention, consistently with :mod:`telco_churn.uplift`: the outcome
``y=1`` is the undesirable event (churn).  Reward is net contribution, so higher
is better, and a prevented event is a positive contribution.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from .problem_contract import ContractViolation, ProblemContract

__all__ = [
    "CostPosting",
    "RewardLedger",
    "RewardSpec",
    "break_even_unit_cost",
    "cost_stress",
    "proxy_reward",
]

PostingKind = Literal[
    "retained_margin",
    "offer_cost",
    "contact_cost",
    "delivery_cost",
    "refund",
    "write_off",
    "allocated_overhead",
]

#: Kinds that add to net contribution.  Everything else subtracts.
_INFLOW_KINDS: frozenset[str] = frozenset({"retained_margin"})

#: Kinds excluded from the incremental reward of a single decision.
_NON_INCREMENTAL_KINDS: frozenset[str] = frozenset({"allocated_overhead"})

_ALL_KINDS: frozenset[str] = frozenset(
    {
        "retained_margin",
        "offer_cost",
        "contact_cost",
        "delivery_cost",
        "refund",
        "write_off",
        "allocated_overhead",
    }
)

Source = Literal["actual", "assumed"]


@dataclass(frozen=True)
class RewardSpec:
    """How a binary outcome becomes money, and how honest that mapping is.

    ``value_per_retained`` is the contribution kept when the endpoint event does
    not happen inside the horizon.  With a public dataset it is an assumption,
    and ``source`` records that so no downstream report can call it revenue.
    """

    value_per_retained: float
    unit_costs: Mapping[str, float]
    source: Source = "assumed"
    currency: str = "unit"
    note: str = ""

    def validate(self) -> None:
        if self.value_per_retained < 0:
            raise ContractViolation("value_per_retained must be non-negative")
        if self.source not in ("actual", "assumed"):
            raise ContractViolation(f"unknown reward source {self.source!r}")
        for name, cost in self.unit_costs.items():
            if cost < 0:
                raise ContractViolation(f"action {name!r} has a negative unit cost")

    @classmethod
    def from_contract(
        cls,
        contract: ProblemContract,
        *,
        value_per_retained: float,
        source: Source = "assumed",
        note: str = "",
    ) -> RewardSpec:
        spec = cls(
            value_per_retained=value_per_retained,
            unit_costs=dict(contract.unit_costs()),
            source=source,
            currency=contract.reward_unit,
            note=note,
        )
        spec.validate()
        return spec

    @property
    def is_evidence(self) -> bool:
        """``True`` only when every money figure came from actual postings."""

        return self.source == "actual"


def proxy_reward(
    outcome: Iterable[int],
    action: Iterable[str],
    spec: RewardSpec,
) -> np.ndarray:
    """Net contribution per account under the churn x margin proxy.

    ``reward = (1 - churn) * value_per_retained - unit_cost(action)``.  The cost
    is subtracted for every assigned account, successful or not: an offer that
    was paid for and did not work still cost money.
    """

    spec.validate()
    # `binary_outcome` hands back a nullable Int8 series, so pd.NA has to survive
    # the conversion as a NaN rather than raising an opaque TypeError.
    y = pd.to_numeric(pd.Series(list(outcome)), errors="coerce").to_numpy(dtype=float)
    actions = np.asarray(list(action), dtype=object)
    if y.shape != actions.shape:
        raise ContractViolation("outcome and action must have the same length")
    if np.isnan(y).any():
        raise ContractViolation(
            "proxy_reward received a missing outcome; adjudicate labels first and "
            "keep unknown rows out of the reward, not at zero"
        )
    if ((y != 0) & (y != 1)).any():
        raise ContractViolation("outcome must be binary 0/1")
    unknown = sorted({str(a) for a in actions} - set(spec.unit_costs))
    if unknown:
        raise ContractViolation(f"no unit cost declared for actions {unknown}")
    costs = np.array([spec.unit_costs[str(a)] for a in actions], dtype=float)
    return (1.0 - y) * spec.value_per_retained - costs


@dataclass(frozen=True)
class CostPosting:
    """One line in the ledger.  ``amount`` is always non-negative."""

    posting_id: str
    account_id: Any
    action: str
    kind: PostingKind
    amount: float
    source: Source = "assumed"
    note: str = ""

    def validate(self) -> None:
        if not self.posting_id:
            raise ContractViolation("every posting needs an id")
        if self.kind not in _ALL_KINDS:
            raise ContractViolation(f"unknown posting kind {self.kind!r}")
        if self.source not in ("actual", "assumed"):
            raise ContractViolation(f"unknown posting source {self.source!r}")
        if self.amount < 0:
            raise ContractViolation(
                f"posting {self.posting_id!r} has a negative amount; use the kind to "
                "carry the sign so inflows and outflows stay distinguishable"
            )

    @property
    def signed_amount(self) -> float:
        return self.amount if self.kind in _INFLOW_KINDS else -self.amount

    @property
    def is_incremental(self) -> bool:
        return self.kind not in _NON_INCREMENTAL_KINDS


@dataclass
class RewardLedger:
    """Append-only postings with single-count guarantees.

    Repeated posting ids are rejected outright.  A repeated
    ``(account, action, kind)`` triple is allowed only when the caller says so,
    because a retry can legitimately produce two delivery costs -- but by
    default it is the double-count bug, so it fails loudly.
    """

    currency: str = "unit"
    _postings: dict[str, CostPosting] = field(default_factory=dict, init=False, repr=False)
    _triples: dict[tuple[Any, str, str], str] = field(default_factory=dict, init=False, repr=False)

    def add(self, posting: CostPosting, *, allow_repeat: bool = False) -> None:
        posting.validate()
        if posting.posting_id in self._postings:
            raise ContractViolation(
                f"posting {posting.posting_id!r} was already recorded; an export retry "
                "must be idempotent, not a second charge"
            )
        triple = (posting.account_id, posting.action, posting.kind)
        if triple in self._triples and not allow_repeat:
            raise ContractViolation(
                f"{posting.kind} for account {posting.account_id!r} and action "
                f"{posting.action!r} was already posted as {self._triples[triple]!r}; "
                "pass allow_repeat=True only when a genuine second charge occurred"
            )
        self._postings[posting.posting_id] = posting
        self._triples.setdefault(triple, posting.posting_id)

    def extend(self, postings: Iterable[CostPosting], *, allow_repeat: bool = False) -> None:
        for posting in postings:
            self.add(posting, allow_repeat=allow_repeat)

    def __len__(self) -> int:
        return len(self._postings)

    @property
    def postings(self) -> tuple[CostPosting, ...]:
        return tuple(self._postings.values())

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "posting_id": posting.posting_id,
                    "account_id": posting.account_id,
                    "action": posting.action,
                    "kind": posting.kind,
                    "amount": posting.amount,
                    "signed_amount": posting.signed_amount,
                    "source": posting.source,
                    "is_incremental": posting.is_incremental,
                    "note": posting.note,
                }
                for posting in self._postings.values()
            ]
        )

    @property
    def source(self) -> Source:
        """``"actual"`` only when every posting came from a real posting."""

        sources = {posting.source for posting in self._postings.values()}
        return "actual" if sources == {"actual"} else "assumed"

    def net_reward_by_account(self, *, include_overhead: bool = False) -> pd.Series:
        """Net contribution per account.  Overhead is excluded by default."""

        frame = self.frame()
        if frame.empty:
            return pd.Series(dtype=float, name="net_reward")
        if not include_overhead:
            frame = frame.loc[frame["is_incremental"]]
        series = frame.groupby("account_id")["signed_amount"].sum()
        series.name = "net_reward"
        return series

    def reconcile(self, *, expected_total: float | None = None) -> dict[str, Any]:
        """Totals by kind, plus a check that the parts add up to the whole."""

        frame = self.frame()
        by_kind = frame.groupby("kind")["signed_amount"].sum().to_dict() if not frame.empty else {}
        incremental = float(frame.loc[frame["is_incremental"], "signed_amount"].sum())
        overhead = float(frame.loc[~frame["is_incremental"], "signed_amount"].sum())
        account_total = float(self.net_reward_by_account().sum())
        report: dict[str, Any] = {
            "n_postings": len(self._postings),
            "currency": self.currency,
            "source": self.source,
            "by_kind": {str(k): float(v) for k, v in by_kind.items()},
            "incremental_total": incremental,
            "allocated_overhead_total": overhead,
            "account_rollup_total": account_total,
            "rollup_matches_incremental": bool(np.isclose(account_total, incremental, atol=1e-9)),
        }
        if expected_total is not None:
            report["expected_total"] = float(expected_total)
            report["matches_expected"] = bool(np.isclose(incremental, expected_total, atol=1e-6))
        return report

    def assert_reconciled(self, *, expected_total: float | None = None) -> dict[str, Any]:
        report = self.reconcile(expected_total=expected_total)
        if not report["rollup_matches_incremental"]:
            raise ContractViolation(
                "per-account rollup does not equal the incremental ledger total"
            )
        if expected_total is not None and not report["matches_expected"]:
            raise ContractViolation(
                f"ledger total {report['incremental_total']} does not match the "
                f"independently computed {expected_total}"
            )
        return report


def break_even_unit_cost(delta_prevented_per_account: float, value_per_retained: float) -> float:
    """Largest per-account action cost a given prevented-event rate can carry.

    Returns ``0.0`` when the action does not prevent anything: there is no cost
    at which a null or harmful action pays for itself.
    """

    if value_per_retained < 0:
        raise ContractViolation("value_per_retained must be non-negative")
    if delta_prevented_per_account <= 0:
        return 0.0
    return float(delta_prevented_per_account * value_per_retained)


def cost_stress(
    delta_prevented_per_account: float,
    spec: RewardSpec,
    action: str,
    *,
    multipliers: Sequence[float] = (0.7, 0.9, 1.0, 1.1, 1.3, 2.0),
) -> pd.DataFrame:
    """How the recommendation moves when the cost assumption moves.

    The output carries ``evidence_source`` so a flip found under assumed costs
    is never read as a finding about realised money.
    """

    spec.validate()
    if action not in spec.unit_costs:
        raise ContractViolation(f"no unit cost declared for action {action!r}")
    base_cost = float(spec.unit_costs[action])
    gross = float(delta_prevented_per_account) * spec.value_per_retained
    rows = []
    for multiplier in multipliers:
        if multiplier < 0:
            raise ContractViolation("cost multipliers must be non-negative")
        cost = base_cost * multiplier
        net = gross - cost
        rows.append(
            {
                "action": action,
                "cost_multiplier": float(multiplier),
                "unit_cost": cost,
                "gross_value_per_account": gross,
                "net_value_per_account": net,
                "net_value_per_1000_eligible": net * 1000.0,
                "recommendation": "act" if net > 0 else "hold_bau",
                "evidence_source": spec.source,
            }
        )
    table = pd.DataFrame(rows)
    table.attrs["break_even_unit_cost"] = break_even_unit_cost(
        delta_prevented_per_account, spec.value_per_retained
    )
    table.attrs["recommendation_flips"] = bool(table["recommendation"].nunique() > 1)
    return table
