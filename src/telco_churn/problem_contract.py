"""Problem, action, timing and data-role contracts.

Backlog V4-01 (sessions 2 and 4 of the V4 development plan).  The contract is
frozen *before* any model is fitted: it fixes population, eligibility, decision
unit, action catalogue, business-as-usual comparator, time zero, horizon,
endpoint, censoring, costs, capacity, estimand and the deployment boundary.

Two rules drive most of the validation logic:

* Target-trial alignment.  Eligibility, assignment and the start of follow-up
  must refer to the same instant ``t0``.  A design that keeps only the people
  who survived until a later delivery attempt is a *negative control*, never a
  promotable candidate.
* Unknown is not "no event".  A contract may not declare that a missing outcome
  record collapses into the non-event class.

Nothing here estimates anything.  The contract is the object the other V4
modules validate their inputs against.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "AccessRecord",
    "ActionSpec",
    "CapacitySpec",
    "ContractViolation",
    "DataRole",
    "DataRoleRegistry",
    "EndpointSpec",
    "ProblemContract",
    "TimingSpec",
    "load_contracts",
    "summarise_contracts",
]


class ContractViolation(ValueError):
    """Raised when a declared contract is internally inconsistent or unsafe."""


EvidenceState = Literal["PLANNED", "EXPLORATORY", "CONFIRMATORY", "SYNTHETIC"]
_EVIDENCE_STATES: frozenset[str] = frozenset(
    {"PLANNED", "EXPLORATORY", "CONFIRMATORY", "SYNTHETIC"}
)

CohortDefinition = Literal["as_assigned", "delivered_only", "survived_to_delivery"]
_REFERENCE_COHORT = "as_assigned"
_NEGATIVE_CONTROL_COHORTS: frozenset[str] = frozenset({"delivered_only", "survived_to_delivery"})

UnknownOutcomePolicy = Literal["keep_unknown", "right_censor", "treat_as_no_event"]


TargetKind = Literal["binary_event", "count", "currency", "duration"]
_TARGET_KINDS: frozenset[str] = frozenset({"binary_event", "count", "currency", "duration"})

Orientation = Literal["adverse", "beneficial"]
_ORIENTATIONS: frozenset[str] = frozenset({"adverse", "beneficial"})

EndpointRole = Literal["outcome", "effect", "reward"]
_ENDPOINT_ROLES: frozenset[str] = frozenset({"outcome", "effect", "reward"})


@dataclass(frozen=True)
class EndpointSpec:
    """One measured quantity, with its kind, sign, unit and observation window.

    A contract that says "the endpoint is a cancellation" and then reports a
    reward in currency is describing two different measurements under one name
    (G07).  Cancellation is a binary adverse event counted in events; retained
    margin is money.  They have different variances, different horizons and
    different maturity rules, so each one is declared separately and the
    contract's ``reward_unit`` has to come from one of them.

    Offsets are days relative to ``t0``.  ``window_start_offset_days`` is zero
    for any endpoint that follows the target trial: follow-up starts when the
    decision is made, not when a delivery attempt happens.
    """

    target_id: str
    target_kind: TargetKind
    orientation: Orientation
    unit: str
    maturity_rule: str
    role: EndpointRole = "outcome"
    window_start_offset_days: float = 0.0
    window_end_offset_days: float = 90.0
    description: str = ""

    def validate(self) -> None:
        if not self.target_id:
            raise ContractViolation("every endpoint needs a target_id")
        if self.target_kind not in _TARGET_KINDS:
            raise ContractViolation(
                f"endpoint {self.target_id!r} has unknown target_kind {self.target_kind!r}"
            )
        if self.orientation not in _ORIENTATIONS:
            raise ContractViolation(
                f"endpoint {self.target_id!r} must say whether a higher value is "
                "'adverse' or 'beneficial'"
            )
        if self.role not in _ENDPOINT_ROLES:
            raise ContractViolation(f"endpoint {self.target_id!r} has unknown role {self.role!r}")
        if not self.unit:
            raise ContractViolation(f"endpoint {self.target_id!r} must declare a unit")
        if not self.maturity_rule:
            raise ContractViolation(
                f"endpoint {self.target_id!r} must say when it may be read as final"
            )
        if self.window_start_offset_days != 0.0:
            raise ContractViolation(
                f"endpoint {self.target_id!r} starts its window after t0; events between t0 "
                "and the window start would be discarded by design"
            )
        if self.window_end_offset_days <= self.window_start_offset_days:
            raise ContractViolation(f"endpoint {self.target_id!r} has an empty observation window")

    @property
    def horizon_days(self) -> float:
        return self.window_end_offset_days - self.window_start_offset_days


@dataclass(frozen=True)
class ActionSpec:
    """One executable action, versioned separately from any model."""

    name: str
    version: str
    unit_cost: float
    channel: str
    is_bau: bool = False
    requires_delivery: bool = True
    reversible: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ContractViolation("action name must be non-empty")
        if not self.version:
            raise ContractViolation(f"action {self.name!r} must declare a version")
        if self.unit_cost < 0:
            raise ContractViolation(f"action {self.name!r} has a negative unit_cost")
        if not self.channel:
            raise ContractViolation(f"action {self.name!r} must declare a channel")


@dataclass(frozen=True)
class CapacitySpec:
    """Resource envelope.  Every compared policy must live inside the same one."""

    period: str
    slots_per_period: int
    cooldown_days: int = 0
    shared_resource: str | None = None

    def validate(self) -> None:
        if self.period not in {"day", "week", "month", "campaign"}:
            raise ContractViolation(f"unsupported capacity period {self.period!r}")
        if self.slots_per_period < 0:
            raise ContractViolation("slots_per_period must be non-negative")
        if self.cooldown_days < 0:
            raise ContractViolation("cooldown_days must be non-negative")


@dataclass(frozen=True)
class TimingSpec:
    """Offsets in days relative to the decision instant ``t0``.

    ``feature_cutoff_offset_days`` may not be positive: a feature that only
    becomes readable after the decision cannot inform the decision.  Assignment
    and the start of follow-up are pinned to ``t0`` so the analysis cohort
    cannot be conditioned on anything that happens afterwards.
    """

    time_zero_rule: str
    feature_cutoff_offset_days: float = 0.0
    assignment_offset_days: float = 0.0
    follow_up_start_offset_days: float = 0.0
    delivery_window_days: float = 0.0
    horizon_days: int = 90
    maturity_lag_days: int = 0
    correction_window_days: int = 0

    def validate(self) -> None:
        if not self.time_zero_rule:
            raise ContractViolation("time_zero_rule must be non-empty")
        if self.feature_cutoff_offset_days > 0:
            raise ContractViolation(
                "feature cutoff is after t0: features would carry post-decision information"
            )
        if self.assignment_offset_days != 0:
            raise ContractViolation(
                "assignment must happen at t0; a later assignment re-opens post-t0 selection"
            )
        if self.follow_up_start_offset_days != 0:
            raise ContractViolation(
                "follow-up must start at t0; starting later discards early events by design"
            )
        if self.delivery_window_days < 0:
            raise ContractViolation("delivery_window_days must be non-negative")
        if self.horizon_days <= 0:
            raise ContractViolation("horizon_days must be positive")
        if self.maturity_lag_days < 0:
            raise ContractViolation("maturity_lag_days must be non-negative")
        if self.correction_window_days < 0:
            raise ContractViolation("correction_window_days must be non-negative")

    @property
    def mature_after_days(self) -> float:
        """Days after ``t0`` at which a label may be read as final."""

        return self.horizon_days + self.maturity_lag_days


@dataclass(frozen=True)
class ProblemContract:
    """A frozen decision problem.  Versioned separately from model bundles."""

    contract_id: str
    revision: int
    population: str
    eligibility_rules: tuple[str, ...]
    decision_unit: str
    randomization_unit: str
    actions: tuple[ActionSpec, ...]
    bau_action: str
    timing: TimingSpec
    endpoint: str
    unknown_outcome_policy: UnknownOutcomePolicy
    competing_events: tuple[str, ...]
    capacity: CapacitySpec
    estimand: str
    inference_method: str
    cohort_definition: CohortDefinition = _REFERENCE_COHORT
    is_negative_control: bool = False
    evidence_state: EvidenceState = "PLANNED"
    reward_unit: str = "prevented_churn_events"
    endpoints: tuple[EndpointSpec, ...] = ()
    deployment_bounds: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.validate()

    # -- validation ---------------------------------------------------------
    def validate(self) -> None:
        if not self.contract_id:
            raise ContractViolation("contract_id must be non-empty")
        if self.revision < 1:
            raise ContractViolation("revision starts at 1 and increases on every change")
        if not self.population:
            raise ContractViolation("population must be described")
        if not self.eligibility_rules:
            raise ContractViolation("at least one eligibility rule must be declared")
        if not self.decision_unit or not self.randomization_unit:
            raise ContractViolation("decision_unit and randomization_unit must be declared")
        if self.evidence_state not in _EVIDENCE_STATES:
            raise ContractViolation(f"unknown evidence_state {self.evidence_state!r}")
        if self.unknown_outcome_policy == "treat_as_no_event":
            raise ContractViolation(
                "unknown outcomes may not be recoded as non-events; "
                "use keep_unknown or right_censor"
            )
        if not self.estimand:
            raise ContractViolation("estimand must be declared before any model is fitted")
        if not self.inference_method:
            raise ContractViolation("inference_method must be declared before evaluation")

        self.timing.validate()
        self.capacity.validate()
        self._validate_actions()
        self._validate_cohort()
        self._validate_endpoints()

    def _validate_actions(self) -> None:
        if not self.actions:
            raise ContractViolation("action catalogue must not be empty")
        names = [action.name for action in self.actions]
        if len(set(names)) != len(names):
            raise ContractViolation("action names must be unique inside one contract")
        for action in self.actions:
            action.validate()
        flagged = [action.name for action in self.actions if action.is_bau]
        if len(flagged) != 1:
            raise ContractViolation("exactly one action must carry is_bau=True")
        if flagged[0] != self.bau_action:
            raise ContractViolation(
                f"bau_action {self.bau_action!r} disagrees with the flagged action {flagged[0]!r}"
            )
        if len(self.actions) < 2:
            raise ContractViolation(
                "a decision problem needs at least one alternative to business as usual"
            )

    def _validate_endpoints(self) -> None:
        """Units and targets must be declared, distinct and consistent (G07)."""

        if not self.endpoints:
            return
        seen: set[str] = set()
        for endpoint in self.endpoints:
            endpoint.validate()
            if endpoint.target_id in seen:
                raise ContractViolation(f"duplicate endpoint target_id {endpoint.target_id!r}")
            seen.add(endpoint.target_id)
        outcomes = [item for item in self.endpoints if item.role == "outcome"]
        if len(outcomes) != 1:
            raise ContractViolation(
                "exactly one endpoint carries role='outcome'; "
                f"found {len(outcomes)} in {self.contract_id!r}"
            )
        outcome = outcomes[0]
        if outcome.window_end_offset_days != float(self.timing.horizon_days):
            raise ContractViolation(
                f"outcome endpoint {outcome.target_id!r} ends at "
                f"{outcome.window_end_offset_days:g} days but the contract horizon is "
                f"{self.timing.horizon_days} days; a different horizon is a different endpoint"
            )
        units = {endpoint.unit for endpoint in self.endpoints}
        if self.reward_unit not in units:
            raise ContractViolation(
                f"reward_unit {self.reward_unit!r} is not produced by any declared endpoint "
                f"({sorted(units)}); a currency reward on an event endpoint mixes two "
                "different measurements under one contract"
            )
        reward_endpoints = [
            endpoint for endpoint in self.endpoints if endpoint.unit == self.reward_unit
        ]
        # A reward measured on a different scale from the outcome needs its own
        # declared endpoint rather than borrowing the outcome's.
        rescaled = any(endpoint.target_kind != outcome.target_kind for endpoint in reward_endpoints)
        if rescaled and not any(endpoint.role == "reward" for endpoint in reward_endpoints):
            raise ContractViolation(
                f"reward_unit {self.reward_unit!r} is measured on a different scale from "
                f"the {outcome.target_kind} outcome {outcome.target_id!r}; declare an "
                "endpoint with role='reward' for it"
            )
        for endpoint in self.endpoints:
            if endpoint.role == "reward" and endpoint.orientation != "beneficial":
                raise ContractViolation(
                    f"reward endpoint {endpoint.target_id!r} is declared adverse; a reward is "
                    "the quantity a policy maximises"
                )

    def _validate_cohort(self) -> None:
        if self.cohort_definition in _NEGATIVE_CONTROL_COHORTS and not self.is_negative_control:
            raise ContractViolation(
                f"cohort_definition {self.cohort_definition!r} conditions on post-assignment "
                "survival or delivery; it is only admissible as a declared negative control"
            )
        if self.cohort_definition == _REFERENCE_COHORT and self.is_negative_control:
            raise ContractViolation(
                "an as-assigned cohort is the reference protocol, not a negative control"
            )
        if self.is_negative_control and self.evidence_state == "CONFIRMATORY":
            raise ContractViolation("a negative control may never hold confirmatory evidence")

    # -- helpers ------------------------------------------------------------
    @property
    def action_names(self) -> tuple[str, ...]:
        return tuple(action.name for action in self.actions)

    def action(self, name: str) -> ActionSpec:
        for candidate in self.actions:
            if candidate.name == name:
                return candidate
        raise ContractViolation(f"action {name!r} is not in contract {self.contract_id!r}")

    def unit_costs(self) -> dict[str, float]:
        return {action.name: action.unit_cost for action in self.actions}

    @property
    def units_declared(self) -> bool:
        """Whether this contract separates its outcome, effect and reward units."""

        return bool(self.endpoints)

    def endpoint_spec(self, role: str = "outcome") -> EndpointSpec:
        for endpoint in self.endpoints:
            if endpoint.role == role:
                return endpoint
        raise ContractViolation(
            f"contract {self.contract_id!r} declares no endpoint with role {role!r}"
        )

    @property
    def reward_endpoint_id(self) -> str | None:
        for endpoint in self.endpoints:
            if endpoint.unit == self.reward_unit:
                return endpoint.target_id
        return None

    @property
    def promotable(self) -> bool:
        """Whether results under this contract may ever be promoted to a launch."""

        return not self.is_negative_control and self.cohort_definition == _REFERENCE_COHORT

    def require_promotable(self) -> None:
        if not self.promotable:
            raise ContractViolation(
                f"contract {self.contract_id!r} is a negative control "
                f"({self.cohort_definition}); its results are diagnostics, not candidates"
            )

    def revise(self, **changes: Any) -> ProblemContract:
        """Return a new contract with an incremented revision.

        Changing an endpoint creates a *new* revision instead of overwriting the
        old one, so earlier results keep pointing at the contract they were
        produced under.
        """

        if "revision" in changes:
            raise ContractViolation("revision is managed by revise(); do not set it directly")
        payload = {**self._shallow_fields(), **changes, "revision": self.revision + 1}
        return ProblemContract(**payload)

    def _shallow_fields(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "revision": self.revision,
            "population": self.population,
            "eligibility_rules": self.eligibility_rules,
            "decision_unit": self.decision_unit,
            "randomization_unit": self.randomization_unit,
            "actions": self.actions,
            "bau_action": self.bau_action,
            "timing": self.timing,
            "endpoint": self.endpoint,
            "unknown_outcome_policy": self.unknown_outcome_policy,
            "competing_events": self.competing_events,
            "capacity": self.capacity,
            "estimand": self.estimand,
            "inference_method": self.inference_method,
            "cohort_definition": self.cohort_definition,
            "is_negative_control": self.is_negative_control,
            "evidence_state": self.evidence_state,
            "reward_unit": self.reward_unit,
            "endpoints": self.endpoints,
            "deployment_bounds": self.deployment_bounds,
            "assumptions": self.assumptions,
            "open_questions": self.open_questions,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mature_after_days"] = self.timing.mature_after_days
        payload["promotable"] = self.promotable
        return payload


# -- configuration loading --------------------------------------------------
_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "contract_id",
        "revision",
        "population",
        "eligibility_rules",
        "decision_unit",
        "randomization_unit",
        "actions",
        "bau_action",
        "timing",
        "endpoint",
        "unknown_outcome_policy",
        "competing_events",
        "capacity",
        "estimand",
        "inference_method",
        "cohort_definition",
        "is_negative_control",
        "evidence_state",
        "reward_unit",
        "endpoints",
        "deployment_bounds",
        "assumptions",
        "open_questions",
    }
)


def _as_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ContractViolation(f"{field_name} must be a list, not a single string")
    return tuple(str(item) for item in value)


def _contract_from_mapping(payload: Mapping[str, Any]) -> ProblemContract:
    unknown = set(payload) - _CONTRACT_KEYS
    if unknown:
        raise ContractViolation(
            f"unknown contract keys {sorted(unknown)}; unused parameters must fail loudly"
        )
    actions = tuple(ActionSpec(**action) for action in payload.get("actions", ()))
    endpoints = tuple(EndpointSpec(**endpoint) for endpoint in payload.get("endpoints", ()))
    timing = TimingSpec(**payload["timing"])
    capacity = CapacitySpec(**payload["capacity"])
    return ProblemContract(
        contract_id=str(payload["contract_id"]),
        revision=int(payload.get("revision", 1)),
        population=str(payload["population"]),
        eligibility_rules=_as_tuple(
            payload.get("eligibility_rules"), field_name="eligibility_rules"
        ),
        decision_unit=str(payload["decision_unit"]),
        randomization_unit=str(payload["randomization_unit"]),
        actions=actions,
        bau_action=str(payload["bau_action"]),
        timing=timing,
        endpoint=str(payload["endpoint"]),
        unknown_outcome_policy=payload.get("unknown_outcome_policy", "keep_unknown"),
        competing_events=_as_tuple(payload.get("competing_events"), field_name="competing_events"),
        capacity=capacity,
        estimand=str(payload["estimand"]),
        inference_method=str(payload["inference_method"]),
        cohort_definition=payload.get("cohort_definition", _REFERENCE_COHORT),
        is_negative_control=bool(payload.get("is_negative_control", False)),
        evidence_state=payload.get("evidence_state", "PLANNED"),
        reward_unit=str(payload.get("reward_unit", "prevented_churn_events")),
        endpoints=endpoints,
        deployment_bounds=_as_tuple(
            payload.get("deployment_bounds"), field_name="deployment_bounds"
        ),
        assumptions=_as_tuple(payload.get("assumptions"), field_name="assumptions"),
        open_questions=_as_tuple(payload.get("open_questions"), field_name="open_questions"),
    )


def load_contracts(path: str | Path) -> dict[str, ProblemContract]:
    """Load every ``[[contract]]`` entry from a TOML registry.

    Keys are ``"<contract_id>@<revision>"`` so that a revision never silently
    replaces the contract an older result was produced under.
    """

    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    entries = raw.get("contract", ())
    if not entries:
        raise ContractViolation(f"no [[contract]] entries found in {path}")
    contracts: dict[str, ProblemContract] = {}
    for entry in entries:
        contract = _contract_from_mapping(entry)
        key = f"{contract.contract_id}@{contract.revision}"
        if key in contracts:
            raise ContractViolation(f"duplicate contract revision {key}")
        contracts[key] = contract
    return contracts


# -- data-role registry -----------------------------------------------------
class DataRole(str, Enum):
    """Roles a frozen split may hold.  A split holds exactly one."""

    TRAINING = "training"
    NUISANCE = "nuisance"
    INNER_EVALUATION = "inner_evaluation"
    CONFIRMATION = "confirmation"


#: Purposes that read outcomes in order to *choose* something.  None of them may
#: ever touch the confirmation split.
SELECTION_PURPOSES: frozenset[str] = frozenset(
    {
        "feature_selection",
        "model_selection",
        "threshold_selection",
        "cost_selection",
        "hyperparameter_tuning",
        "policy_search",
        "stopping_rule",
    }
)

#: The only purpose under which confirmation outcomes may be opened.
CONFIRMATION_PURPOSE = "confirmation_evaluation"


@dataclass(frozen=True)
class SplitRecord:
    split_id: str
    role: DataRole
    row_count: int
    data_hash: str


@dataclass(frozen=True)
class AccessRecord:
    split_id: str
    role: DataRole
    purpose: str
    reads_outcomes: bool
    note: str = ""


@dataclass
class DataRoleRegistry:
    """Freeze split roles and log every access against them.

    The registry never reads data.  It records what a run *claims* to be doing,
    so that a role violation (tuning on confirmation, opening confirmation
    twice, two roles sharing one hash) becomes a hard failure instead of a
    footnote in a report.
    """

    contract_id: str
    _splits: dict[str, SplitRecord] = field(default_factory=dict, init=False, repr=False)
    _accesses: list[AccessRecord] = field(default_factory=list, init=False, repr=False)

    def register(
        self, split_id: str, role: DataRole | str, *, row_count: int, data_hash: str
    ) -> None:
        if split_id in self._splits:
            raise ContractViolation(
                f"split {split_id!r} is already frozen; create a new split id instead"
            )
        if row_count <= 0:
            raise ContractViolation(f"split {split_id!r} must contain rows")
        if not data_hash:
            raise ContractViolation(f"split {split_id!r} must declare a data hash")
        self._splits[split_id] = SplitRecord(split_id, DataRole(role), row_count, data_hash)

    @property
    def splits(self) -> dict[str, SplitRecord]:
        return dict(self._splits)

    @property
    def accesses(self) -> tuple[AccessRecord, ...]:
        return tuple(self._accesses)

    def role_of(self, split_id: str) -> DataRole:
        if split_id not in self._splits:
            raise ContractViolation(f"split {split_id!r} was never registered")
        return self._splits[split_id].role

    def record_access(
        self, split_id: str, *, purpose: str, reads_outcomes: bool, note: str = ""
    ) -> AccessRecord:
        role = self.role_of(split_id)
        if not purpose:
            raise ContractViolation("every access must declare a purpose")
        if role is DataRole.CONFIRMATION:
            if purpose in SELECTION_PURPOSES:
                raise ContractViolation(
                    f"purpose {purpose!r} selects on outcomes and may not touch the "
                    f"confirmation split {split_id!r}"
                )
            if reads_outcomes and purpose != CONFIRMATION_PURPOSE:
                raise ContractViolation(
                    f"confirmation outcomes may only be read under "
                    f"{CONFIRMATION_PURPOSE!r}, not {purpose!r}"
                )
            if reads_outcomes and self.confirmation_reads(split_id):
                raise ContractViolation(
                    f"confirmation split {split_id!r} was already opened; a second read "
                    "needs a new protocol revision and new data"
                )
        record = AccessRecord(split_id, role, purpose, reads_outcomes, note)
        self._accesses.append(record)
        return record

    def confirmation_reads(self, split_id: str | None = None) -> int:
        return sum(
            1
            for access in self._accesses
            if access.role is DataRole.CONFIRMATION
            and access.reads_outcomes
            and (split_id is None or access.split_id == split_id)
        )

    def violations(self) -> list[str]:
        """Post-hoc audit of the recorded ledger."""

        problems: list[str] = []
        roles = {record.role for record in self._splits.values()}
        for required in (DataRole.TRAINING, DataRole.CONFIRMATION):
            if required not in roles:
                problems.append(f"no split holds the {required.value} role")
        seen: dict[str, str] = {}
        for record in self._splits.values():
            if record.data_hash in seen:
                problems.append(
                    f"splits {seen[record.data_hash]!r} and {record.split_id!r} share a "
                    "data hash; they are not disjoint roles"
                )
            seen[record.data_hash] = record.split_id
        if self.confirmation_reads() > 1:
            problems.append("confirmation outcomes were read more than once")
        return problems

    def assert_clean(self) -> None:
        problems = self.violations()
        if problems:
            raise ContractViolation("; ".join(problems))

    def manifest(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "splits": [
                {**asdict(record), "role": record.role.value} for record in self._splits.values()
            ],
            "accesses": [
                {**asdict(record), "role": record.role.value} for record in self._accesses
            ],
            "confirmation_reads": self.confirmation_reads(),
            "violations": self.violations(),
        }


def summarise_contracts(contracts: Iterable[ProblemContract]) -> list[dict[str, Any]]:
    """Compact table for reports: one row per contract revision."""

    return [
        {
            "contract_id": contract.contract_id,
            "revision": contract.revision,
            "decision_unit": contract.decision_unit,
            "bau_action": contract.bau_action,
            "n_actions": len(contract.actions),
            "horizon_days": contract.timing.horizon_days,
            "mature_after_days": contract.timing.mature_after_days,
            "cohort_definition": contract.cohort_definition,
            "evidence_state": contract.evidence_state,
            "reward_unit": contract.reward_unit,
            "n_endpoints": len(contract.endpoints),
            "units_declared": contract.units_declared,
            "promotable": contract.promotable,
        }
        for contract in contracts
    ]
