"""Batch allocation under a declared hard cap (node N07, acceptance test A13).

A decision rule that scores one account at a time is not the policy that gets
deployed.  The deployed policy takes a batch, sorts it and stops at a capacity
limit, so one account's action depends on who else is in the batch.  That makes
three things contractual rather than incidental:

* **The cap is a floor, not a rounding.**  ``floor(fraction * n)`` never
  exceeds the declared envelope; ``ceil`` breaches it by one unit at most batch
  sizes, which is a real violation of a hard constraint even though it looks
  like a rounding detail.  ``top_fraction_mask`` in :mod:`telco_churn.uplift`
  keeps the older ceiling convention because published budget curves were
  produced with it; deployment allocation uses this module instead.
* **Ties are resolved by a stable key, never by row order.**  Two accounts with
  the same score must get the same decision whichever order the batch arrived
  in, or the policy is not reproducible and a replay can differ from the run.
* **A negative-value action is never forced.**  If the cap allows more contacts
  than there are accounts worth contacting, the remaining slots stay unused.
  Spending capacity to reach a break-even threshold is a business decision, not
  an allocator default.

Nothing here reads an outcome.  The allocator sees scores, identifiers and the
capacity contract, and nothing else.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .problem_contract import ContractViolation, ProblemContract

__all__ = [
    "Allocation",
    "allocate_batch",
    "capacity_limit",
    "contract_capacity_limit",
]


def capacity_limit(n_units: int, fraction: float) -> int:
    """Hard cap for a batch of ``n_units`` at ``fraction`` capacity.

    ``floor`` is the declared convention: a cap of "at most 20%" is breached by
    ``ceil`` for every batch size that is not a multiple of five.  Small batches
    can therefore have a capacity of zero, which is the honest answer -- there
    is no slot to spend -- rather than a free contact.
    """

    if n_units < 0:
        raise ContractViolation("n_units must be non-negative")
    if not 0 <= fraction <= 1:
        raise ContractViolation("fraction must lie in [0, 1]")
    return math.floor(n_units * fraction)


def contract_capacity_limit(contract: ProblemContract, n_units: int, *, fraction: float) -> int:
    """Cap for one batch: the smaller of the declared fraction and the slot count."""

    return min(capacity_limit(n_units, fraction), contract.capacity.slots_per_period)


@dataclass(frozen=True)
class Allocation:
    """One batch decision, with the reason each unit was or was not selected."""

    frame: pd.DataFrame
    capacity: int
    n_selected: int
    n_eligible: int
    n_positive_value: int
    fraction: float
    tie_rule: str = "descending score, then ascending unit_id"

    @property
    def utilisation(self) -> float:
        return self.n_selected / self.capacity if self.capacity else 0.0

    @property
    def unused_slots(self) -> int:
        return self.capacity - self.n_selected

    def selected_ids(self) -> list[str]:
        return self.frame.loc[self.frame["selected"], "unit_id"].tolist()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capacity": self.capacity,
            "n_selected": self.n_selected,
            "n_eligible": self.n_eligible,
            "n_positive_value": self.n_positive_value,
            "fraction": self.fraction,
            "utilisation": self.utilisation,
            "unused_slots": self.unused_slots,
            "tie_rule": self.tie_rule,
        }


def allocate_batch(
    unit_id: Sequence[Any],
    score: Sequence[float],
    *,
    fraction: float,
    eligible: Sequence[bool] | None = None,
    require_positive: bool = True,
    capacity: int | None = None,
) -> Allocation:
    """Select at most ``floor(fraction * n)`` units, deterministically.

    ``score`` is whatever the policy maximises -- an estimated effect, an
    expected value, a risk ranking.  The allocator does not interpret it beyond
    its sign: with ``require_positive`` a unit whose score is not strictly
    positive is never contacted, so a policy cannot be pushed into negative
    value just to fill the batch.

    The returned frame keeps the input order and carries a ``reason`` for every
    unit, because "why was this account not contacted" is a question the
    workflow has to answer without re-running the allocator.
    """

    ids = np.asarray([str(value) for value in unit_id], dtype=object)
    values = np.asarray(list(score), dtype=float)
    if len(ids) != len(values):
        raise ContractViolation("unit_id and score must have the same length")
    if len(set(ids.tolist())) != len(ids):
        raise ContractViolation("unit_id must be unique inside one batch")
    if not np.isfinite(values).all():
        raise ContractViolation("scores must be finite; a missing score is not a low score")
    if eligible is None:
        eligible_mask = np.ones(len(ids), dtype=bool)
    else:
        eligible_mask = np.asarray(list(eligible), dtype=bool)
        if len(eligible_mask) != len(ids):
            raise ContractViolation("eligible must have one entry per unit")

    limit = capacity_limit(len(ids), fraction) if capacity is None else int(capacity)
    if limit < 0:
        raise ContractViolation("capacity must be non-negative")

    candidate = eligible_mask & (values > 0 if require_positive else np.ones_like(values, bool))
    # Stable, order-independent ranking: score descending, then unit id ascending.
    order = np.lexsort((ids, -values))
    selected = np.zeros(len(ids), dtype=bool)
    taken = 0
    for index in order:
        if taken >= limit:
            break
        if candidate[index]:
            selected[index] = True
            taken += 1

    rank = np.empty(len(ids), dtype=int)
    rank[order] = np.arange(1, len(ids) + 1)
    reason = np.where(
        selected,
        "selected",
        np.where(
            ~eligible_mask,
            "not_eligible",
            np.where(~candidate, "non_positive_value", "capacity_exhausted"),
        ),
    )
    frame = pd.DataFrame(
        {
            "unit_id": ids,
            "score": values,
            "eligible": eligible_mask,
            "rank": rank,
            "selected": selected,
            "reason": reason,
        }
    )
    return Allocation(
        frame=frame,
        capacity=limit,
        n_selected=int(selected.sum()),
        n_eligible=int(eligible_mask.sum()),
        n_positive_value=int(candidate.sum()),
        fraction=float(fraction),
    )
