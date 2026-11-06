"""Time zero, outcome taxonomy and label adjudication (E19, backlog V4-01).

Two failure modes motivate this module, and both are silent when labels are a
single 0/1 column:

* **Immature or missing outcomes read as non-events.**  An account whose horizon
  has not elapsed, or whose status record never arrived, is not a survivor.
  :func:`binary_outcome` refuses to produce a 0 for it.
* **Post-assignment selection.**  Restricting the cohort to accounts that were
  actually reached, or that survived until the agent called, conditions on the
  future.  :func:`apply_cohort_definition` will only do it for a contract that
  declares itself a negative control.

The taxonomy separates six states.  ``observed_no_event`` is the *only* one that
may become a zero, and a competing event never silently becomes either class.

Required columns of an event-history frame:

===================  ========================================================
``account_id``       decision unit identifier
``t0``               decision instant; eligibility, assignment, follow-up start
``assigned_action``  action assigned at ``t0`` (as assigned, not as delivered)
``delivery_at``      when the action reached the account, ``NaT`` if never
``delivered``        whether delivery succeeded
``event_at``         endpoint event timestamp, ``NaT`` if none recorded
``event_type``       taxonomy of the recorded event, ``NA`` if none
``last_observed_at`` last instant the account status was observable
``record_status``    ``"ok"``, ``"missing"`` or ``"disputed"``
===================  ========================================================
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import numpy as np
import pandas as pd

from .problem_contract import ContractViolation, ProblemContract

__all__ = [
    "REQUIRED_COLUMNS",
    "AdjudicationResult",
    "LabelState",
    "adjudicate",
    "analysis_cohort",
    "apply_cohort_definition",
    "arm_completeness",
    "binary_outcome",
    "reconcile_cohort",
]


class LabelState(str, Enum):
    """Mutually exclusive outcome states.  Only one of them is a zero."""

    OBSERVED_EVENT = "observed_event"
    OBSERVED_COMPETING_EVENT = "observed_competing_event"
    OBSERVED_NO_EVENT = "observed_no_event"
    RIGHT_CENSORED = "right_censored"
    NOT_YET_MATURE = "not_yet_mature"
    UNRESOLVED_CONFLICT = "unresolved_conflict"


#: States that carry an informative binary label.
_INFORMATIVE: frozenset[LabelState] = frozenset(
    {LabelState.OBSERVED_EVENT, LabelState.OBSERVED_NO_EVENT}
)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "account_id",
    "t0",
    "assigned_action",
    "delivery_at",
    "delivered",
    "event_at",
    "event_type",
    "last_observed_at",
    "record_status",
)

CompetingAs = Literal["event", "censored", "unknown"]


@dataclass(frozen=True)
class AdjudicationResult:
    """Per-account labels plus the counts a reviewer needs to trust them."""

    labels: pd.DataFrame
    as_of: pd.Timestamp
    contract_id: str
    contract_revision: int

    @property
    def state_counts(self) -> dict[str, int]:
        counts = self.labels["label_state"].value_counts()
        return {str(state): int(counts.get(state, 0)) for state in LabelState}

    @property
    def informative_share(self) -> float:
        if not len(self.labels):
            return float("nan")
        informative = self.labels["label_state"].isin([s.value for s in _INFORMATIVE])
        return float(informative.mean())

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_revision": self.contract_revision,
            "as_of": self.as_of.isoformat(),
            "n_assigned": len(self.labels),
            "state_counts": self.state_counts,
            "informative_share": self.informative_share,
        }


def _require_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ContractViolation(f"event history is missing required columns: {missing}")


def _as_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def adjudicate(
    history: pd.DataFrame,
    contract: ProblemContract,
    *,
    as_of: str | pd.Timestamp,
) -> AdjudicationResult:
    """Assign one :class:`LabelState` and one reason code per assigned account.

    The function reads only the event history and the contract's timing rules.
    It never looks at a policy score, so adjudication cannot be steered by the
    candidate being evaluated.
    """

    _require_columns(history)
    as_of_ts = pd.Timestamp(as_of)
    if pd.isna(as_of_ts):
        raise ContractViolation("as_of must be a valid timestamp")

    frame = history.copy()
    if frame["account_id"].duplicated().any():
        duplicated = frame.loc[frame["account_id"].duplicated(), "account_id"].unique()[:5]
        raise ContractViolation(
            f"duplicate account_id rows in the assignment frame, e.g. {list(duplicated)}"
        )

    for column in ("t0", "delivery_at", "event_at", "last_observed_at"):
        frame[column] = _as_datetime(frame[column])

    unknown_actions = set(frame["assigned_action"].dropna().unique()) - set(contract.action_names)
    if unknown_actions:
        raise ContractViolation(
            f"assigned actions {sorted(unknown_actions)} are not in contract "
            f"{contract.contract_id!r}"
        )

    horizon = pd.Timedelta(days=contract.timing.horizon_days)
    maturity = pd.Timedelta(days=contract.timing.mature_after_days)
    correction = pd.Timedelta(days=contract.timing.correction_window_days)
    competing = set(contract.competing_events)

    states: list[str] = []
    reasons: list[str] = []
    matures: list[bool] = []
    resolved: list[pd.Timestamp] = []

    for row in frame.itertuples(index=False):
        state, reason, is_mature, resolved_at = _adjudicate_row(
            row,
            as_of=as_of_ts,
            horizon=horizon,
            maturity=maturity,
            correction=correction,
            competing=competing,
        )
        states.append(state.value)
        reasons.append(reason)
        matures.append(is_mature)
        resolved.append(resolved_at)

    frame["label_state"] = states
    frame["reason_code"] = reasons
    frame["is_mature"] = matures
    frame["resolved_at"] = resolved
    frame["horizon_end"] = frame["t0"] + horizon
    frame["mature_at"] = frame["t0"] + maturity
    frame["adjudicated_as_of"] = as_of_ts
    frame["contract_id"] = contract.contract_id
    frame["contract_revision"] = contract.revision
    return AdjudicationResult(
        labels=frame,
        as_of=as_of_ts,
        contract_id=contract.contract_id,
        contract_revision=contract.revision,
    )


def _adjudicate_row(
    row: Any,
    *,
    as_of: pd.Timestamp,
    horizon: pd.Timedelta,
    maturity: pd.Timedelta,
    correction: pd.Timedelta,
    competing: set[str],
) -> tuple[LabelState, str, bool, pd.Timestamp]:
    t0 = row.t0
    if pd.isna(t0):
        return LabelState.UNRESOLVED_CONFLICT, "missing_time_zero", False, pd.NaT
    if str(row.record_status) == "disputed":
        return LabelState.UNRESOLVED_CONFLICT, "disputed_record", False, pd.NaT
    if pd.notna(row.event_at) and row.event_at < t0:
        # An account cannot be eligible at t0 and already have had the endpoint
        # event before t0.  Never quietly fold this into the baseline.
        return LabelState.UNRESOLVED_CONFLICT, "event_before_time_zero", False, pd.NaT
    if pd.notna(row.delivery_at) and row.delivery_at < t0:
        return LabelState.UNRESOLVED_CONFLICT, "delivery_before_time_zero", False, pd.NaT
    if pd.isna(row.last_observed_at):
        return LabelState.UNRESOLVED_CONFLICT, "missing_observation_window", False, pd.NaT
    if row.last_observed_at < t0:
        return LabelState.UNRESOLVED_CONFLICT, "observation_ends_before_time_zero", False, pd.NaT

    horizon_end = t0 + horizon
    has_event = pd.notna(row.event_at) and t0 <= row.event_at <= horizon_end

    if str(row.record_status) == "missing":
        if has_event:
            return LabelState.UNRESOLVED_CONFLICT, "missing_status_with_event", False, pd.NaT
        # A record that never arrived is not evidence that nothing happened.
        return (
            LabelState.RIGHT_CENSORED,
            "missing_outcome_record",
            False,
            row.last_observed_at,
        )

    if has_event:
        event_type = "" if pd.isna(row.event_type) else str(row.event_type)
        resolved_at = row.event_at + correction
        is_mature = as_of >= resolved_at
        state = (
            LabelState.OBSERVED_COMPETING_EVENT
            if event_type in competing
            else LabelState.OBSERVED_EVENT
        )
        reason = "event_within_horizon" if is_mature else "event_inside_correction_window"
        return state, reason, bool(is_mature), resolved_at

    if as_of < horizon_end:
        return LabelState.NOT_YET_MATURE, "horizon_not_elapsed", False, t0 + maturity
    if row.last_observed_at < horizon_end:
        return (
            LabelState.RIGHT_CENSORED,
            "observation_ends_before_horizon",
            False,
            row.last_observed_at,
        )
    if as_of < t0 + maturity:
        return LabelState.NOT_YET_MATURE, "inside_maturity_lag", False, t0 + maturity
    return LabelState.OBSERVED_NO_EVENT, "no_event_through_horizon", True, horizon_end


def binary_outcome(
    labels: pd.DataFrame,
    contract: ProblemContract,
    *,
    competing_as: CompetingAs = "unknown",
    require_mature: bool = True,
) -> pd.Series:
    """Map label states to ``{0, 1, <NA>}`` under the contract's unknown policy.

    ``<NA>`` is a first-class answer.  A contract that asked for
    ``treat_as_no_event`` never gets built, so the only way to reach a zero here
    is an account observed through the whole horizon without the endpoint event.
    """

    if contract.unknown_outcome_policy == "treat_as_no_event":
        raise ContractViolation(
            "unknown outcomes may not be recoded as non-events"
        )  # pragma: no cover - blocked at contract construction
    if competing_as not in ("event", "censored", "unknown"):
        raise ContractViolation(f"unsupported competing_as {competing_as!r}")
    if "label_state" not in labels.columns:
        raise ContractViolation("labels frame must come from adjudicate()")

    state = labels["label_state"].astype(str)
    result = pd.Series(pd.NA, index=labels.index, dtype="Int8")
    result[state == LabelState.OBSERVED_EVENT.value] = 1
    result[state == LabelState.OBSERVED_NO_EVENT.value] = 0
    if competing_as == "event":
        result[state == LabelState.OBSERVED_COMPETING_EVENT.value] = 1
    if require_mature and "is_mature" in labels.columns:
        result[~labels["is_mature"].astype(bool)] = pd.NA
    return result


def analysis_cohort(
    labels: pd.DataFrame,
    contract: ProblemContract,
    *,
    competing_as: CompetingAs = "unknown",
    require_mature: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rows with an informative label, plus the reconciliation against ITT.

    The dropped rows are reported, never hidden: the denominator of any rate
    computed downstream is ``n_assigned``, not ``n_analysed``.
    """

    outcome = binary_outcome(
        labels, contract, competing_as=competing_as, require_mature=require_mature
    )
    keep = outcome.notna()
    cohort = labels.loc[keep].copy()
    cohort["outcome"] = outcome.loc[keep].astype(int)
    dropped = labels.loc[~keep, "label_state"].astype(str).value_counts()
    reconciliation = {
        "n_assigned": len(labels),
        "n_analysed": int(keep.sum()),
        "n_excluded": int((~keep).sum()),
        "excluded_by_state": {str(k): int(v) for k, v in dropped.items()},
        "itt_denominator": len(labels),
        "competing_as": competing_as,
        "require_mature": require_mature,
    }
    return cohort, reconciliation


def apply_cohort_definition(
    labels: pd.DataFrame, contract: ProblemContract
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply the contract's cohort rule and report exactly what it removed.

    An ``as_assigned`` contract may not drop a single assigned row.  The two
    post-assignment restrictions are available only to a contract that declared
    ``is_negative_control``; they exist so the bias can be measured, and
    :attr:`ProblemContract.promotable` stays ``False`` for their results.
    """

    definition = contract.cohort_definition
    if definition == "as_assigned":
        kept = labels
    elif definition == "delivered_only":
        kept = labels.loc[labels["delivered"].astype(bool)]
    elif definition == "survived_to_delivery":
        event_at = _as_datetime(labels["event_at"])
        delivery_at = _as_datetime(labels["delivery_at"])
        survived = event_at.isna() | (delivery_at.notna() & (event_at > delivery_at))
        kept = labels.loc[survived & delivery_at.notna()]
    else:  # pragma: no cover - blocked by the contract's Literal type
        raise ContractViolation(f"unsupported cohort_definition {definition!r}")

    removed = int(len(labels) - len(kept))
    if definition == "as_assigned" and removed:
        raise ContractViolation(
            "an as-assigned cohort must keep every assigned row; "
            f"{removed} rows would have been dropped"
        )
    if removed and contract.promotable:
        raise ContractViolation(
            f"cohort_definition {definition!r} dropped {removed} post-assignment rows "
            "from a promotable contract"
        )
    return kept.copy(), {
        "cohort_definition": definition,
        "n_assigned": len(labels),
        "n_kept": len(kept),
        "n_removed_post_assignment": removed,
        "promotable": contract.promotable,
    }


def reconcile_cohort(
    labels: pd.DataFrame,
    contract: ProblemContract,
    *,
    analysed_ids: Iterable[Any],
) -> dict[str, Any]:
    """Compare an analysis cohort against the assigned frame (mutation Q07).

    ``analysed_ids`` is whatever a downstream step actually scored.  If those
    ids are a strict subset of the assigned accounts under a promotable
    contract, the ITT denominator has been lost and the check fails.
    """

    assigned = set(labels["account_id"])
    analysed = set(analysed_ids)
    unknown = analysed - assigned
    if unknown:
        raise ContractViolation(
            f"{len(unknown)} analysed ids were never assigned, e.g. {sorted(unknown)[:5]}"
        )
    lost = assigned - analysed
    informative = set(
        labels.loc[
            labels["label_state"].astype(str).isin([s.value for s in _INFORMATIVE]),
            "account_id",
        ]
    )
    unexplained = lost & informative
    report = {
        "n_assigned": len(assigned),
        "n_analysed": len(analysed),
        "n_lost": len(lost),
        "n_lost_with_informative_label": len(unexplained),
        "itt_denominator_preserved": not unexplained,
    }
    if unexplained and contract.promotable:
        raise ContractViolation(
            f"{len(unexplained)} accounts with informative labels were dropped from a "
            "promotable analysis cohort; the ITT denominator no longer reconciles"
        )
    return report


def arm_completeness(labels: pd.DataFrame) -> pd.DataFrame:
    """Label-state completeness per assigned arm.

    Maturity that differs by arm is a bias, not an inconvenience: it is exactly
    what treatment-dependent logging looks like in the label table.
    """

    state = labels["label_state"].astype(str)
    table = (
        pd.crosstab(labels["assigned_action"], state)
        .reindex(columns=[s.value for s in LabelState], fill_value=0)
        .reset_index()
    )
    totals = table[[s.value for s in LabelState]].sum(axis=1)
    informative = table[[s.value for s in _INFORMATIVE]].sum(axis=1)
    table["n_assigned"] = totals.astype(int)
    table["informative_share"] = np.where(totals > 0, informative / totals, np.nan)
    return table


def maturity_imbalance(labels: pd.DataFrame, *, tolerance: float = 0.02) -> dict[str, Any]:
    """Flag arms whose informative share differs by more than ``tolerance``."""

    table = arm_completeness(labels)
    shares = table["informative_share"].to_numpy(dtype=float)
    spread = float(np.nanmax(shares) - np.nanmin(shares)) if len(shares) else float("nan")
    return {
        "tolerance": tolerance,
        "informative_share_by_arm": dict(
            zip(table["assigned_action"].astype(str), shares, strict=True)
        ),
        "max_minus_min": spread,
        "balanced": bool(np.isfinite(spread) and spread <= tolerance),
    }


def state_table(results: Sequence[AdjudicationResult]) -> pd.DataFrame:
    """One row per adjudication run, for the report registry."""

    rows = []
    for result in results:
        rows.append(
            {
                "contract_id": result.contract_id,
                "contract_revision": result.contract_revision,
                "as_of": result.as_of,
                "n_assigned": len(result.labels),
                "informative_share": result.informative_share,
                **result.state_counts,
            }
        )
    return pd.DataFrame(rows)
