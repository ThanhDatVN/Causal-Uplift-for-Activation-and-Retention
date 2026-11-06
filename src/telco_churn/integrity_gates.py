"""Gates that reject invalid inputs before anything is estimated.

Each gate here exists because a specific mutation in the E28 suite would
otherwise pass silently:

* :func:`point_in_time_violations` -- a fact whose *event* predates the snapshot
  but whose *availability* does not (Q03).  Filtering on ``event_at`` alone is
  the usual way this leak survives review.
* :class:`FeatureLineage` -- a forbidden column that reaches the model through a
  join or a rename (Q14).  A denylist of column names does not survive
  ``rename``; a lineage does.
* :func:`capacity_violations` -- an allocation that breaches slots or cooldown at
  a period boundary (Q16), checked independently of whichever allocator
  produced it.
* :func:`assert_bundle_compatible` -- a stored bundle loaded against a contract
  whose endpoint, revision or action versions have moved on (Q18).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .problem_contract import ContractViolation, ProblemContract

__all__ = [
    "FeatureLineage",
    "assert_bundle_compatible",
    "assert_point_in_time",
    "capacity_violations",
    "point_in_time_violations",
]


# -- point-in-time ----------------------------------------------------------
_PIT_COLUMNS = ("account_id", "feature_name", "event_at", "available_at")


def point_in_time_violations(
    feature_ledger: pd.DataFrame, decisions: pd.DataFrame, contract: ProblemContract
) -> pd.DataFrame:
    """Feature rows that were not readable at the decision instant.

    ``feature_ledger`` is long format with one row per observed fact:
    ``account_id``, ``feature_name``, ``event_at``, ``available_at``.
    ``decisions`` carries ``account_id`` and ``t0``.  A row is a violation when
    the fact only became available after the contract's feature cutoff, however
    early the underlying event happened.
    """

    missing = [column for column in _PIT_COLUMNS if column not in feature_ledger.columns]
    if missing:
        raise ContractViolation(f"feature ledger is missing columns: {missing}")
    if "t0" not in decisions.columns or "account_id" not in decisions.columns:
        raise ContractViolation("decisions must carry account_id and t0")

    merged = feature_ledger.merge(
        decisions.loc[:, ["account_id", "t0"]], on="account_id", how="left", validate="m:1"
    )
    if merged["t0"].isna().any():
        orphans = merged.loc[merged["t0"].isna(), "account_id"].unique()[:5]
        raise ContractViolation(f"feature rows without a decision, e.g. {list(orphans)}")
    cutoff = pd.to_datetime(merged["t0"]) + pd.Timedelta(
        days=contract.timing.feature_cutoff_offset_days
    )
    available_at = pd.to_datetime(merged["available_at"], errors="coerce")
    late = available_at.isna() | (available_at > cutoff)
    violations = merged.loc[late].copy()
    violations["cutoff"] = cutoff.loc[late]
    violations["reason"] = [
        "missing_available_at" if pd.isna(value) else "available_after_cutoff"
        for value in available_at.loc[late]
    ]
    return violations


def assert_point_in_time(
    feature_ledger: pd.DataFrame, decisions: pd.DataFrame, contract: ProblemContract
) -> pd.DataFrame:
    """Return the readable subset, or raise if anything was readable too late."""

    violations = point_in_time_violations(feature_ledger, decisions, contract)
    if len(violations):
        sample = violations.loc[:, ["account_id", "feature_name", "reason"]].head(3)
        raise ContractViolation(
            f"{len(violations)} feature rows were not available at the decision instant; "
            f"first offenders:\n{sample.to_string(index=False)}"
        )
    return feature_ledger


# -- column lineage ---------------------------------------------------------
@dataclass
class FeatureLineage:
    """Track where each column's information came from.

    A rename changes a column's name and nothing about its provenance, so the
    forbidden-source check keeps working after ``rename`` and after a derived
    column absorbs a forbidden input through :meth:`derive`.
    """

    _sources: dict[str, frozenset[str]] = field(default_factory=dict, init=False, repr=False)

    def declare(self, column: str, source: str) -> None:
        if not column or not source:
            raise ContractViolation("declare() needs a column and a source")
        self._sources[column] = frozenset({source})

    def declare_many(self, mapping: Mapping[str, str]) -> None:
        for column, source in mapping.items():
            self.declare(column, source)

    def derive(self, column: str, from_columns: Iterable[str]) -> None:
        parents = list(from_columns)
        unknown = [parent for parent in parents if parent not in self._sources]
        if unknown:
            raise ContractViolation(f"cannot derive from undeclared columns {unknown}")
        merged: frozenset[str] = frozenset()
        for parent in parents:
            merged |= self._sources[parent]
        self._sources[column] = merged

    def rename(self, old: str, new: str) -> None:
        if old not in self._sources:
            raise ContractViolation(f"column {old!r} was never declared")
        self._sources[new] = self._sources.pop(old)

    def sources_of(self, column: str) -> frozenset[str]:
        if column not in self._sources:
            raise ContractViolation(
                f"column {column!r} has no declared lineage; an undeclared column may "
                "not enter a model"
            )
        return self._sources[column]

    def violations(
        self, columns: Iterable[str], *, forbidden_sources: Iterable[str]
    ) -> dict[str, list[str]]:
        forbidden = set(forbidden_sources)
        found: dict[str, list[str]] = {}
        for column in columns:
            overlap = sorted(self.sources_of(column) & forbidden)
            if overlap:
                found[column] = overlap
        return found

    def assert_allowed(self, columns: Iterable[str], *, forbidden_sources: Iterable[str]) -> None:
        found = self.violations(columns, forbidden_sources=forbidden_sources)
        if found:
            rendered = ", ".join(
                f"{column} <- {sorted(sources)}" for column, sources in found.items()
            )
            raise ContractViolation(f"forbidden lineage reached the model: {rendered}")


# -- capacity feasibility ---------------------------------------------------
#: Contract capacity period -> pandas period alias.  ``campaign`` has no calendar
#: period: the whole assignment list shares one bucket.
_PERIOD_ALIAS: dict[str, str | None] = {
    "day": "D",
    "week": "W",
    "month": "M",
    "campaign": None,
}


def capacity_violations(
    assignments: pd.DataFrame, contract: ProblemContract
) -> list[dict[str, Any]]:
    """Independent feasibility check on a produced assignment list.

    Deliberately written without reference to any allocator, so that an
    allocator bug at a period boundary cannot be validated by the same code that
    caused it.  ``assignments`` needs ``account_id``, ``assigned_at``, ``action``.
    """

    required = ("account_id", "assigned_at", "action")
    missing = [column for column in required if column not in assignments.columns]
    if missing:
        raise ContractViolation(f"assignments frame is missing columns: {missing}")

    frame = assignments.copy()
    frame["assigned_at"] = pd.to_datetime(frame["assigned_at"], errors="coerce")
    if frame["assigned_at"].isna().any():
        raise ContractViolation("every assignment needs a valid assigned_at")
    unknown = sorted(set(frame["action"].astype(str)) - set(contract.action_names))
    if unknown:
        raise ContractViolation(f"assignments use actions outside the contract: {unknown}")

    problems: list[dict[str, Any]] = []
    treated = frame.loc[frame["action"].astype(str) != contract.bau_action].copy()

    alias = _PERIOD_ALIAS[contract.capacity.period]
    if alias is None:
        buckets = pd.Series(["campaign"] * len(treated), index=treated.index)
    else:
        buckets = treated["assigned_at"].dt.to_period(alias).astype(str)
    for bucket, count in buckets.value_counts().items():
        if count > contract.capacity.slots_per_period:
            problems.append(
                {
                    "kind": "capacity_exceeded",
                    "period": str(bucket),
                    "assigned": int(count),
                    "slots": contract.capacity.slots_per_period,
                }
            )

    cooldown = pd.Timedelta(days=contract.capacity.cooldown_days)
    if cooldown > pd.Timedelta(0):
        ordered = treated.sort_values(["account_id", "assigned_at"])
        gaps = ordered.groupby("account_id")["assigned_at"].diff()
        breached = ordered.loc[gaps.notna() & (gaps < cooldown)]
        for row in breached.itertuples(index=False):
            problems.append(
                {
                    "kind": "cooldown_breached",
                    "account_id": row.account_id,
                    "assigned_at": str(row.assigned_at),
                    "cooldown_days": contract.capacity.cooldown_days,
                }
            )

    duplicated = frame.duplicated(subset=["account_id", "assigned_at", "action"], keep=False)
    if duplicated.any():
        for row in frame.loc[duplicated].itertuples(index=False):
            problems.append(
                {
                    "kind": "duplicate_assignment",
                    "account_id": row.account_id,
                    "assigned_at": str(row.assigned_at),
                    "action": str(row.action),
                }
            )
    return problems


def assert_feasible(assignments: pd.DataFrame, contract: ProblemContract) -> None:
    problems = capacity_violations(assignments, contract)
    if problems:
        raise ContractViolation(f"{len(problems)} constraint violations: {problems[:3]}")


# -- bundle compatibility ---------------------------------------------------
def assert_bundle_compatible(contract: ProblemContract, bundle: Mapping[str, Any]) -> None:
    """Refuse to serve a stored bundle against a contract it was not built for.

    Version drift is a migration decision, not something to absorb silently: an
    endpoint or action version that moved invalidates the stored scores even
    when the feature schema still loads.
    """

    for key in ("contract_id", "contract_revision", "endpoint", "action_versions"):
        if key not in bundle:
            raise ContractViolation(f"bundle is missing required key {key!r}")
    if bundle["contract_id"] != contract.contract_id:
        raise ContractViolation(
            f"bundle was built for contract {bundle['contract_id']!r}, not {contract.contract_id!r}"
        )
    if int(bundle["contract_revision"]) != contract.revision:
        raise ContractViolation(
            f"bundle targets revision {bundle['contract_revision']}, contract is at "
            f"revision {contract.revision}; explicit migration and re-evaluation required"
        )
    if str(bundle["endpoint"]) != contract.endpoint:
        raise ContractViolation("bundle endpoint differs from the contract endpoint")
    expected = {action.name: action.version for action in contract.actions}
    got = dict(bundle["action_versions"])
    drifted = {
        name: (got.get(name), version)
        for name, version in expected.items()
        if got.get(name) != version
    }
    if drifted:
        raise ContractViolation(f"action version drift (bundle, contract): {drifted}")


def declared_schema_fingerprint(columns: Sequence[str]) -> str:
    """Order-insensitive fingerprint of a feature schema."""

    import hashlib

    joined = "|".join(sorted(str(column) for column in columns))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
