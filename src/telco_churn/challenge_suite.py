"""Falsification suite: prove the evaluator can reject (E28, backlog V4-03).

A green test run says the code does what it did yesterday.  It does not say the
pipeline would notice a swapped treatment label, a double-charged offer or a
confirmation split opened for tuning.  This module carries the mutations
declared in the V4 experiment design -- Q01-Q18 from the first round and
Q19-Q24 for the G01-G07 gaps found in the V4.1 plan review -- each with a clean
fixture and a deliberately broken copy, and reports which ones are caught.

Every check answers two questions, because a detector that blocks everything is
not a detector:

* does the **clean** fixture pass?  (false-block rate)
* is the **mutant** detected?  (critical-mutation detection)

Mutations build their own fixtures and never touch raw data or stored
artifacts.  A pass means the declared fault was caught -- not that the pipeline
is safe against faults nobody wrote down.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from .economics import CostPosting, RewardLedger
from .integrity_gates import (
    FeatureLineage,
    assert_bundle_compatible,
    assert_point_in_time,
    capacity_violations,
)
from .outcome_adjudication import LabelState, adjudicate, binary_outcome, reconcile_cohort
from .policy_comparison import (
    dr_action_scores,
    dr_action_scores_with_support,
    enriched_sampling_contrast,
    paired_contrast,
    unpaired_contrast,
)
from .problem_contract import (
    ActionSpec,
    CapacitySpec,
    ContractViolation,
    DataRole,
    DataRoleRegistry,
    EndpointSpec,
    ProblemContract,
    TimingSpec,
)
from .research_runner import Stage, run_stages
from .uplift import CatBoostFrameClassifier, ipw_scores, top_fraction_mask

__all__ = [
    "MUTATIONS",
    "Mutation",
    "MutationOutcome",
    "SuiteReport",
    "main",
    "run_suite",
]

Severity = Literal["critical", "major", "minor"]

_T0 = pd.Timestamp("2026-01-01")


@dataclass(frozen=True)
class MutationOutcome:
    """What happened when one mutation was exercised."""

    clean_passes: bool
    mutant_detected: bool
    detector: str
    clean_note: str = ""
    mutant_note: str = ""

    @property
    def ok(self) -> bool:
        return self.clean_passes and self.mutant_detected


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    title: str
    expected_detector: str
    severity: Severity
    node: str
    check: Callable[[], MutationOutcome] | None = None

    @property
    def is_covered(self) -> bool:
        return self.check is not None


# -- shared fixtures --------------------------------------------------------
def _fixture_contract(**overrides: Any) -> ProblemContract:
    """A small three-action contract used by most fixtures."""

    payload: dict[str, Any] = {
        "contract_id": "fixture_payment_support",
        "revision": 1,
        "population": "fixture accounts in a failed-payment grace period",
        "eligibility_rules": ("failed_invoice_at <= t0", "grace_period_end > t0"),
        "decision_unit": "account",
        "randomization_unit": "account",
        "actions": (
            ActionSpec(
                "dunning_only",
                "bau-1",
                0.0,
                "automated_email",
                is_bau=True,
                requires_delivery=False,
            ),
            ActionSpec("payment_support_call", "call-1", 10.0, "outbound_agent_call"),
            ActionSpec(
                "grace_extension", "grace-1", 2.0, "automated_email", requires_delivery=False
            ),
        ),
        "bau_action": "dunning_only",
        "timing": TimingSpec(
            time_zero_rule="nightly snapshot on grace-period entry",
            horizon_days=90,
            maturity_lag_days=30,
            correction_window_days=30,
        ),
        "endpoint": "administrative cancellation within the horizon",
        "unknown_outcome_policy": "keep_unknown",
        "competing_events": ("involuntary_termination",),
        "capacity": CapacitySpec(period="week", slots_per_period=2, cooldown_days=30),
        "estimand": "ITT prevented cancellations versus dunning_only",
        "inference_method": "paired doubly robust contrast",
        "evidence_state": "SYNTHETIC",
    }
    payload.update(overrides)
    return ProblemContract(**payload)


def _history(
    n: int,
    *,
    event_days: dict[int, int] | None = None,
    delivered: Sequence[bool] | None = None,
    last_observed: pd.Timestamp | None = None,
    record_status: Sequence[str] | None = None,
) -> pd.DataFrame:
    events = event_days or {}
    observed_through = pd.Timestamp("2026-06-01") if last_observed is None else last_observed
    return pd.DataFrame(
        {
            "account_id": [f"a{index}" for index in range(n)],
            "t0": [_T0] * n,
            "assigned_action": [
                "dunning_only" if index % 2 else "payment_support_call" for index in range(n)
            ],
            "delivery_at": [_T0 + pd.Timedelta(days=3)] * n,
            "delivered": list(delivered) if delivered is not None else [True] * n,
            "event_at": [
                _T0 + pd.Timedelta(days=events[index]) if index in events else pd.NaT
                for index in range(n)
            ],
            "event_type": ["cancellation" if index in events else pd.NA for index in range(n)],
            "last_observed_at": [observed_through] * n,
            "record_status": list(record_status) if record_status is not None else ["ok"] * n,
        }
    )


def _score_frame(values: dict[str, Sequence[float]]) -> pd.DataFrame:
    return pd.DataFrame(values)


def _raises(
    call: Callable[[], Any], *, expected: type[Exception] = ContractViolation
) -> tuple[bool, str]:
    try:
        call()
    except expected as error:
        return True, str(error)[:200]
    except Exception as error:  # noqa: BLE001 - an unexpected failure mode is still a miss
        return False, f"unexpected {type(error).__name__}: {error}"[:200]
    return False, "no exception raised"


def _passes(call: Callable[[], Any]) -> tuple[bool, str]:
    try:
        call()
    except Exception as error:  # noqa: BLE001 - any failure is a false block
        return False, f"{type(error).__name__}: {error}"[:200]
    return True, "clean fixture accepted"


# -- Q01: sign convention ---------------------------------------------------
def _check_q01() -> MutationOutcome:
    treatment = np.array([0, 0, 1, 1])
    outcome = np.array([1, 0, 0, 0])
    expected = 0.5  # control churn 1/2, treated churn 0/2, prevented = 0.5
    clean = float(ipw_scores(outcome, treatment, 0.5).mean())
    mutated = float(ipw_scores(outcome, 1 - treatment, 0.5).mean())
    return MutationOutcome(
        clean_passes=bool(np.isclose(clean, expected)),
        mutant_detected=not bool(np.isclose(mutated, expected)),
        detector="hand_computed_ate_identity",
        clean_note=f"prevented-churn ATE {clean:+.4f} matches the hand calculation",
        mutant_note=f"swapped arms give {mutated:+.4f}, opposite sign",
    )


# -- Q02: constant propensity under a stratified design ---------------------
def _stratified_design() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Two strata, zero true effect, treatment probability 0.8 and 0.2."""

    treatment = np.concatenate([np.repeat([1, 0], [80, 20]), np.repeat([1, 0], [20, 80])])
    outcome = np.concatenate(
        [
            np.repeat([1, 0], [40, 40]),  # stratum A treated, churn 0.5
            np.repeat([1, 0], [10, 10]),  # stratum A control, churn 0.5
            np.repeat([1, 0], [2, 18]),  # stratum B treated, churn 0.1
            np.repeat([1, 0], [8, 72]),  # stratum B control, churn 0.1
        ]
    )
    propensity = np.concatenate([np.full(100, 0.8), np.full(100, 0.2)])
    return treatment, outcome, propensity


def _check_q02() -> MutationOutcome:
    treatment, outcome, propensity = _stratified_design()
    clean = float(ipw_scores(outcome, treatment, propensity).mean())
    mutated = float(ipw_scores(outcome, treatment, 0.5).mean())
    return MutationOutcome(
        clean_passes=bool(np.isclose(clean, 0.0, atol=1e-12)),
        mutant_detected=not bool(np.isclose(mutated, 0.0, atol=1e-3)),
        detector="design_probability_vs_known_truth",
        clean_note=f"design propensities recover the true zero effect ({clean:+.1e})",
        mutant_note=f"a constant 0.5 propensity reports {mutated:+.4f} where truth is 0",
    )


# -- Q03: point-in-time availability ----------------------------------------
def _check_q03() -> MutationOutcome:
    contract = _fixture_contract()
    decisions = pd.DataFrame({"account_id": ["a0", "a1"], "t0": [_T0, _T0]})
    ledger = pd.DataFrame(
        {
            "account_id": ["a0", "a1"],
            "feature_name": ["arrears_balance", "arrears_balance"],
            "event_at": [_T0 - pd.Timedelta(days=5), _T0 - pd.Timedelta(days=5)],
            "available_at": [_T0 - pd.Timedelta(days=1), _T0 - pd.Timedelta(days=1)],
        }
    )
    mutated = ledger.copy()
    # The event still predates t0; only the batch that published it runs late.
    mutated.loc[1, "available_at"] = _T0 + pd.Timedelta(days=2)
    clean_ok, clean_note = _passes(lambda: assert_point_in_time(ledger, decisions, contract))
    detected, note = _raises(lambda: assert_point_in_time(mutated, decisions, contract))
    return MutationOutcome(clean_ok, detected, "point_in_time_gate", clean_note, note)


# -- Q04: preprocessing fitted on the scoring batch -------------------------
class _BatchFittedCatBoost(CatBoostFrameClassifier):
    """The pre-fix behaviour: impute from whichever rows are being scored."""

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:  # type: ignore[override]
        prepared = self._coerce(frame)
        for column in prepared.columns:
            if pd.api.types.is_numeric_dtype(prepared[column]) and prepared[column].isna().any():
                prepared[column] = prepared[column].fillna(prepared[column].median())
        return prepared


def _q04_frame() -> tuple[pd.DataFrame, np.ndarray]:
    values = np.concatenate([np.full(15, 1.0), np.full(15, 100.0)])
    frame = pd.DataFrame(
        {
            "arrears": values,
            "segment": ["x"] * 15 + ["y"] * 15,
        }
    )
    frame.loc[0, "arrears"] = np.nan
    frame.loc[20, "arrears"] = np.nan
    outcome = (values > 50).astype(int)
    return frame, outcome


def _chunk_invariance(model: CatBoostFrameClassifier, frame: pd.DataFrame) -> float:
    """Largest gap between whole-frame and chunk-wise preprocessing."""

    # Reaching into the private transform is deliberate: the property under test
    # is the preprocessing step itself, not the model's predictions.
    whole = model._prepare(frame)
    chunks = pd.concat([model._prepare(frame.iloc[:15]), model._prepare(frame.iloc[15:])])
    gap = whole["arrears"].to_numpy(dtype=float) - chunks["arrears"].to_numpy(dtype=float)
    return float(np.nanmax(np.abs(gap)))


def _check_q04() -> MutationOutcome:
    frame, outcome = _q04_frame()
    fixed = CatBoostFrameClassifier(seed=7, iterations=10, depth=2).fit(frame, outcome)
    broken = _BatchFittedCatBoost(seed=7, iterations=10, depth=2).fit(frame, outcome)
    clean_gap = _chunk_invariance(fixed, frame)
    mutant_gap = _chunk_invariance(broken, frame)
    return MutationOutcome(
        clean_passes=bool(clean_gap == 0.0),
        mutant_detected=bool(mutant_gap > 1e-6),
        detector="batch_chunk_invariance",
        clean_note=f"fit-time fill values give an identical transform (gap {clean_gap:g})",
        mutant_note=f"batch-fitted medians move an imputed value by {mutant_gap:g}",
    )


# -- Q05: duplicate assignment after an export retry ------------------------
def _posting(index: int, account: str, kind: str, amount: float) -> CostPosting:
    return CostPosting(f"p{index}", account, "payment_support_call", kind, amount, source="actual")


def _check_q05() -> MutationOutcome:
    def clean() -> None:
        ledger = RewardLedger()
        ledger.add(_posting(1, "a0", "contact_cost", 10.0))
        ledger.add(_posting(2, "a1", "contact_cost", 10.0))

    def mutated() -> None:
        ledger = RewardLedger()
        ledger.add(_posting(1, "a0", "contact_cost", 10.0))
        ledger.add(_posting(1, "a0", "contact_cost", 10.0))

    clean_ok, clean_note = _passes(clean)
    detected, note = _raises(mutated)
    return MutationOutcome(clean_ok, detected, "posting_idempotency_gate", clean_note, note)


# -- Q06: immature outcome recorded as a non-event --------------------------
def _check_q06() -> MutationOutcome:
    contract = _fixture_contract()
    history = _history(6, event_days={0: 30}, last_observed=pd.Timestamp("2026-03-01"))
    result = adjudicate(history, contract, as_of="2026-03-01")
    labels = result.labels
    immature = labels["label_state"].astype(str) == LabelState.NOT_YET_MATURE.value
    clean_outcome = binary_outcome(labels, contract)
    naive = labels["event_at"].notna().astype(int)  # the mutation
    clean_zeros = int(((clean_outcome == 0) & immature).sum())
    naive_zeros = int(((naive == 0) & immature).sum())
    return MutationOutcome(
        clean_passes=bool(immature.any() and clean_zeros == 0),
        mutant_detected=bool(naive_zeros > 0),
        detector="maturity_and_adjudication_gate",
        clean_note=f"{int(immature.sum())} immature rows stay missing, none become zero",
        mutant_note=f"the naive label turns {naive_zeros} immature rows into survivors",
    )


# -- Q07: delivered-only filter applied after randomization -----------------
def _check_q07() -> MutationOutcome:
    contract = _fixture_contract()
    delivered = [True, True, True, False, False, False]
    history = _history(6, delivered=delivered)
    labels = adjudicate(history, contract, as_of="2026-06-01").labels
    all_ids = list(labels["account_id"])
    delivered_ids = list(labels.loc[labels["delivered"], "account_id"])
    clean_ok, clean_note = _passes(lambda: reconcile_cohort(labels, contract, analysed_ids=all_ids))
    detected, note = _raises(lambda: reconcile_cohort(labels, contract, analysed_ids=delivered_ids))
    return MutationOutcome(clean_ok, detected, "itt_cohort_reconciliation", clean_note, note)


# -- Q08: an offer cost charged twice ---------------------------------------
def _build_ledger(*, double_charge: bool) -> RewardLedger:
    ledger = RewardLedger(currency="unit")
    ledger.add(
        CostPosting("m-a0", "a0", "payment_support_call", "retained_margin", 100.0, "actual")
    )
    ledger.add(CostPosting("o-a0", "a0", "payment_support_call", "offer_cost", 10.0, "actual"))
    ledger.add(CostPosting("o-a1", "a1", "payment_support_call", "offer_cost", 10.0, "actual"))
    if double_charge:
        ledger.add(
            CostPosting("o-a0-retry", "a0", "payment_support_call", "offer_cost", 10.0, "actual"),
            allow_repeat=True,
        )
    return ledger


def _check_q08() -> MutationOutcome:
    expected = 80.0  # 100 retained margin, two offers of 10
    clean_ok, clean_note = _passes(
        lambda: _build_ledger(double_charge=False).assert_reconciled(expected_total=expected)
    )
    detected, note = _raises(
        lambda: _build_ledger(double_charge=True).assert_reconciled(expected_total=expected)
    )
    return MutationOutcome(clean_ok, detected, "ledger_identity_tiny_example", clean_note, note)


# -- Q09: identical policies compared without pairing -----------------------
def _identical_policy_scores(seed: int = 11) -> tuple[pd.DataFrame, list[str]]:
    rng = np.random.default_rng(seed)
    n = 200
    scores = _score_frame(
        {
            "dunning_only": rng.normal(0, 1, n),
            "payment_support_call": rng.normal(0, 1, n),
        }
    )
    actions = ["payment_support_call" if index % 3 else "dunning_only" for index in range(n)]
    return scores, actions


def _check_q09() -> MutationOutcome:
    scores, actions = _identical_policy_scores()
    paired = paired_contrast(scores, actions, actions)
    unpaired = unpaired_contrast(scores, actions, actions)
    return MutationOutcome(
        clean_passes=bool(paired.is_identical),
        mutant_detected=bool(unpaired.se > 0),
        detector="paired_contrast_identity",
        clean_note=f"paired delta {paired.delta:g} with SE {paired.se:g}",
        mutant_note=f"unpaired analysis reports SE {unpaired.se:.4f} for a zero contrast",
    )


# -- Q10: clustered rows pooled as independent accounts ---------------------
def _check_q10() -> MutationOutcome:
    n_clusters, per_cluster = 20, 10
    rng = np.random.default_rng(5)
    cluster_effect = rng.normal(0, 1, n_clusters)
    paired_values = np.repeat(cluster_effect, per_cluster)
    cluster = np.repeat([f"c{index}" for index in range(n_clusters)], per_cluster)
    scores = _score_frame(
        {
            "dunning_only": np.zeros(n_clusters * per_cluster),
            "payment_support_call": paired_values,
        }
    )
    challenger = ["payment_support_call"] * (n_clusters * per_cluster)
    bau = ["dunning_only"] * (n_clusters * per_cluster)
    clustered = paired_contrast(scores, challenger, bau, cluster=cluster)
    pooled = paired_contrast(scores, challenger, bau)
    ratio = clustered.se / pooled.se if pooled.se else float("inf")
    return MutationOutcome(
        clean_passes=bool(clustered.n_clusters == n_clusters and np.isfinite(clustered.se)),
        mutant_detected=bool(ratio > 2.0),
        detector="unit_manifest_and_cluster_variance",
        clean_note=f"cluster-robust SE {clustered.se:.4f} over {clustered.n_clusters} clusters",
        mutant_note=f"pooling customer-months shrinks the SE by {ratio:.1f}x",
    )


# -- Q11: enriched sampling without the inclusion weight --------------------
def _sampling_fixture() -> tuple[pd.DataFrame, list[str], list[str], np.ndarray, np.ndarray]:
    n = 200
    paired_values = np.zeros(n)
    paired_values[:20] = 4.0  # high-contribution disagreement units
    paired_values[20:40] = 1.0  # low-contribution disagreement units
    scores = _score_frame({"dunning_only": np.zeros(n), "payment_support_call": paired_values})
    challenger = ["payment_support_call"] * 40 + ["dunning_only"] * (n - 40)
    bau = ["dunning_only"] * n
    q = np.full(n, 1.0)
    q[20:40] = 0.25
    sampled = np.zeros(n, dtype=bool)
    sampled[:20] = True
    sampled[20:25] = True  # exactly the 25% recruited from the low stratum
    return scores, challenger, bau, q, sampled


def _check_q11() -> MutationOutcome:
    scores, challenger, bau, q, sampled = _sampling_fixture()
    truth = 100.0 / 200.0  # frame total 20*4 + 20*1, divided by the frame size
    weighted = enriched_sampling_contrast(
        scores, challenger, bau, sampled=sampled, inclusion_probability=q
    )
    paired_values = scores["payment_support_call"].to_numpy()
    unweighted = float(paired_values[sampled].sum() / len(paired_values))
    return MutationOutcome(
        clean_passes=bool(np.isclose(weighted.delta, truth)),
        mutant_detected=not bool(np.isclose(unweighted, truth, atol=1e-6)),
        detector="sampling_contract_known_truth",
        clean_note=f"Horvitz-Thompson delta {weighted.delta:.4f} equals the frame truth",
        mutant_note=f"dropping 1/q gives {unweighted:.4f} against a truth of {truth:.4f}",
    )


# -- Q12: an action with no logged support ----------------------------------
def _check_q12() -> MutationOutcome:
    n = 20
    scores = _score_frame({"dunning_only": np.zeros(n), "payment_support_call": np.ones(n)})
    bau = ["dunning_only"] * n
    supported = ["payment_support_call"] * n
    unsupported = ["grace_extension"] * n  # never logged, so it has no score column
    clean_ok, clean_note = _passes(lambda: paired_contrast(scores, supported, bau))
    detected, note = _raises(lambda: paired_contrast(scores, unsupported, bau))
    return MutationOutcome(clean_ok, detected, "support_gate", clean_note, note)


# -- Q13: tuning against the confirmation split -----------------------------
def _registry() -> DataRoleRegistry:
    registry = DataRoleRegistry(contract_id="fixture_payment_support")
    registry.register("dev", DataRole.TRAINING, row_count=1000, data_hash="h-train")
    registry.register("inner", DataRole.INNER_EVALUATION, row_count=300, data_hash="h-inner")
    registry.register("holdout", DataRole.CONFIRMATION, row_count=400, data_hash="h-conf")
    return registry


def _check_q13() -> MutationOutcome:
    def clean() -> None:
        registry = _registry()
        registry.record_access("inner", purpose="model_selection", reads_outcomes=True)
        registry.record_access("holdout", purpose="confirmation_evaluation", reads_outcomes=True)
        registry.assert_clean()

    def mutated() -> None:
        registry = _registry()
        registry.record_access("holdout", purpose="model_selection", reads_outcomes=True)

    clean_ok, clean_note = _passes(clean)
    detected, note = _raises(mutated)
    return MutationOutcome(clean_ok, detected, "data_role_access_ledger", clean_note, note)


# -- Q14: a forbidden column that survives a rename -------------------------
def _lineage() -> FeatureLineage:
    lineage = FeatureLineage()
    lineage.declare_many(
        {
            "arrears_balance": "billing_ledger",
            "tenure_days": "crm",
            "cancelled_within_90d": "outcome_ledger",
        }
    )
    return lineage


def _check_q14() -> MutationOutcome:
    forbidden = {"outcome_ledger"}

    def clean() -> None:
        lineage = _lineage()
        lineage.derive("arrears_per_month", ["arrears_balance", "tenure_days"])
        lineage.assert_allowed(
            ["arrears_balance", "tenure_days", "arrears_per_month"], forbidden_sources=forbidden
        )

    def mutated() -> None:
        lineage = _lineage()
        lineage.derive("risk_proxy", ["tenure_days", "cancelled_within_90d"])
        lineage.rename("risk_proxy", "cust_score")  # the name no longer looks like an outcome
        lineage.assert_allowed(["tenure_days", "cust_score"], forbidden_sources=forbidden)

    clean_ok, clean_note = _passes(clean)
    detected, note = _raises(mutated)
    return MutationOutcome(clean_ok, detected, "column_lineage_gate", clean_note, note)


# -- Q15: tie-breaking that depends on row order ----------------------------
def _check_q15() -> MutationOutcome:
    ids = np.array([f"a{index:02d}" for index in range(10)])
    score = np.array([0.5] * 10)  # a complete tie
    order = np.array([7, 2, 9, 0, 4, 1, 8, 3, 6, 5])

    selected = set(ids[top_fraction_mask(score, ids, 0.3)])
    permuted = set(ids[order][top_fraction_mask(score[order], ids[order], 0.3)])

    def naive(score_values: np.ndarray, id_values: np.ndarray) -> set[str]:
        limit = max(1, int(np.ceil(len(score_values) * 0.3)))
        return set(id_values[np.argsort(-score_values, kind="stable")[:limit]])

    naive_selected = naive(score, ids)
    naive_permuted = naive(score[order], ids[order])

    def render(values: set[Any]) -> list[str]:
        return sorted(str(value) for value in values)

    return MutationOutcome(
        clean_passes=bool(selected == permuted and len(selected) == 3),
        mutant_detected=bool(naive_selected != naive_permuted),
        detector="stable_tie_break_reproducibility",
        clean_note=f"id-stable tie break selects {render(selected)} under both orderings",
        mutant_note=f"score-only ordering selects {render(naive_selected)} then "
        f"{render(naive_permuted)}",
    )


# -- Q16: capacity and cooldown breached at a boundary ----------------------
def _plan(rows: Sequence[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["account_id", "assigned_at", "action"])


def _check_q16() -> MutationOutcome:
    contract = _fixture_contract()  # 2 slots per week, 30-day cooldown
    feasible = _plan(
        [
            ("a0", "2026-01-05", "payment_support_call"),
            ("a1", "2026-01-06", "payment_support_call"),
            ("a2", "2026-01-12", "payment_support_call"),
            ("a0", "2026-02-09", "payment_support_call"),
        ]
    )
    infeasible = _plan(
        [
            ("a0", "2026-01-05", "payment_support_call"),
            ("a1", "2026-01-06", "payment_support_call"),
            ("a2", "2026-01-07", "payment_support_call"),  # third slot in the same week
            ("a0", "2026-01-20", "payment_support_call"),  # inside the cooldown
        ]
    )
    clean_problems = capacity_violations(feasible, contract)
    mutant_problems = capacity_violations(infeasible, contract)
    kinds = sorted({problem["kind"] for problem in mutant_problems})
    return MutationOutcome(
        clean_passes=bool(not clean_problems),
        mutant_detected=bool({"capacity_exceeded", "cooldown_breached"} <= set(kinds)),
        detector="independent_feasibility_checker",
        clean_note="the feasible plan raises no constraint violation",
        mutant_note=f"detected {kinds}",
    )


# -- Q17: a failing subprocess reported as success --------------------------
def _check_q17() -> MutationOutcome:
    import sys

    python = sys.executable or "python"
    ok_stage = Stage("ok", [python, "-c", "print('fine')"])
    failing_stage = Stage("boom", [python, "-c", "raise SystemExit(3)"])
    clean_report = run_stages([ok_stage])
    mutant_report = run_stages([ok_stage, failing_stage, ok_stage])
    return MutationOutcome(
        clean_passes=bool(clean_report.status == "COMPLETE" and clean_report.exit_code == 0),
        mutant_detected=bool(mutant_report.status == "FAILED" and mutant_report.exit_code != 0),
        detector="stage_failure_propagation",
        clean_note="a clean stage list reports COMPLETE with exit code 0",
        mutant_note=f"exit code 3 propagates: status {mutant_report.status}, "
        f"{len(mutant_report.skipped)} stage(s) recorded as skipped",
    )


# -- Q18: a stale bundle loaded against a moved contract --------------------
def _bundle(contract: ProblemContract, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_id": contract.contract_id,
        "contract_revision": contract.revision,
        "endpoint": contract.endpoint,
        "action_versions": {action.name: action.version for action in contract.actions},
    }
    payload.update(overrides)
    return payload


def _check_q18() -> MutationOutcome:
    contract = _fixture_contract()
    moved = contract.revise(endpoint="administrative cancellation within 180 days")
    clean_ok, clean_note = _passes(lambda: assert_bundle_compatible(contract, _bundle(contract)))
    detected, note = _raises(lambda: assert_bundle_compatible(moved, _bundle(contract)))
    return MutationOutcome(clean_ok, detected, "bundle_compatibility_gate", clean_note, note)


# -- Q19: a design probability quietly replaced by a floor ------------------
def _support_fixture() -> tuple[list[float], list[str], pd.DataFrame, pd.DataFrame]:
    """One account was assigned an action it had almost no chance of getting."""

    rare = 0.0005
    propensity = pd.DataFrame(
        {
            "dunning_only": [0.5, 0.5, 1.0 - rare],
            "payment_support_call": [0.5, 0.5, rare],
        }
    )
    predicted = pd.DataFrame(
        {"dunning_only": [0.0, 0.0, 0.0], "payment_support_call": [0.0, 0.0, 0.0]}
    )
    action = ["dunning_only", "payment_support_call", "payment_support_call"]
    reward = [1.0, 1.0, 1.0]
    return reward, action, propensity, predicted


def _check_q19() -> MutationOutcome:
    reward, action, propensity, predicted = _support_fixture()
    exact = dr_action_scores_with_support(reward, action, propensity, predicted)
    # 1 / 0.0005 = 2000 exactly; the primary estimator may not round that away.
    unmodified_weight = float(exact.scores.loc[2, "payment_support_call"])
    clipped = dr_action_scores_with_support(
        reward, action, propensity, predicted, support_policy="clip", support_floor=1e-3
    )
    clipped_weight = float(clipped.scores.loc[2, "payment_support_call"])
    rejected, reject_note = _raises(
        lambda: dr_action_scores(
            reward, action, propensity, predicted, support_policy="reject", support_floor=1e-3
        )
    )
    clean_ok = bool(
        np.isclose(unmodified_weight, 2000.0, rtol=0, atol=1e-9)
        and exact.support.n_clipped == 0
        and exact.support.support_policy == "unmodified"
    )
    detected = bool(
        rejected
        and clipped.support.n_clipped > 0
        and not np.isclose(clipped_weight, unmodified_weight)
    )
    return MutationOutcome(
        clean_passes=clean_ok,
        mutant_detected=detected,
        detector="propensity_support_contract",
        clean_note=f"unmodified design probability gives weight {unmodified_weight:.1f} "
        f"and reports ESS {exact.support.effective_sample_size:.2f}",
        mutant_note=f"clipping moves the score to {clipped_weight:.1f} on "
        f"{clipped.support.n_clipped} cell(s); the support contract refuses it: {reject_note}",
    )


# -- Q20: two nuisance frames joined by position after a shuffle ------------
def _check_q20() -> MutationOutcome:
    keys = [f"acct-{index:02d}" for index in range(6)]
    action = pd.Series(["dunning_only", "payment_support_call"] * 3, index=keys)
    reward = pd.Series([0.0, 1.0] * 3, index=keys)
    propensity = pd.DataFrame(
        {"dunning_only": [0.5] * 6, "payment_support_call": [0.5] * 6}, index=keys
    )
    predicted = pd.DataFrame(
        {"dunning_only": [0.1] * 6, "payment_support_call": [0.9] * 6}, index=keys
    )
    shuffled = predicted.iloc[[3, 1, 5, 0, 4, 2]]  # same rows, same length, wrong order

    clean_ok, clean_note = _passes(lambda: dr_action_scores(reward, action, propensity, predicted))
    detected, note = _raises(lambda: dr_action_scores(reward, action, propensity, shuffled))
    realigned = dr_action_scores(reward, action, propensity, shuffled, row_key=keys)
    honest = dr_action_scores(reward, action, propensity, predicted)
    repaired = bool(np.allclose(realigned.to_numpy(), honest.to_numpy()))
    return MutationOutcome(
        clean_passes=bool(clean_ok and repaired),
        mutant_detected=detected,
        detector="row_key_join_contract",
        clean_note=f"{clean_note}; an explicit row_key join restores the honest scores",
        mutant_note=note,
    )


# -- Q21: a census read as zero uncertainty ---------------------------------
def _check_q21() -> MutationOutcome:
    rng = np.random.default_rng(20260921)
    n = 400
    noisy = np.zeros(n)
    noisy[:200] = rng.normal(0.5, 2.0, 200)  # disagreement units carry outcome noise
    scores = _score_frame({"dunning_only": np.zeros(n), "payment_support_call": noisy})
    challenger = ["payment_support_call"] * 200 + ["dunning_only"] * 200
    bau = ["dunning_only"] * n

    partial_q = np.where(np.arange(n) < 200, 0.5, 1.0)
    partial_sampled = np.zeros(n, dtype=bool)
    partial_sampled[:100] = True
    partial_sampled[200:] = True
    partial = enriched_sampling_contrast(
        scores,
        challenger,
        bau,
        sampled=partial_sampled,
        inclusion_probability=partial_q,
        variance_target="superpopulation",
    )
    census = enriched_sampling_contrast(
        scores,
        challenger,
        bau,
        sampled=np.ones(n, dtype=bool),
        inclusion_probability=np.ones(n),
        variance_target="superpopulation",
    )
    return MutationOutcome(
        clean_passes=bool(partial.se_recruitment_only > 0 and partial.se_superpopulation > 0),
        mutant_detected=bool(census.se_recruitment_only == 0.0 and census.se_superpopulation > 0.0),
        detector="recruitment_variance_decomposition",
        clean_note=f"under q=0.5 recruitment SE {partial.se_recruitment_only:.4f} and total SE "
        f"{partial.se_superpopulation:.4f} are both positive",
        mutant_note=f"at q=1 the recruitment term is exactly 0 but the reported total SE stays "
        f"{census.se_superpopulation:.4f}; a census removes sampling noise, not outcome noise",
    )


# -- Q22: an artifact from an earlier run certifying this one ---------------
def _check_q22() -> MutationOutcome:
    import sys
    import tempfile

    python = sys.executable or "python"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "leftover.json").write_text('{"from": "an earlier run"}', encoding="utf-8")
        writer = Stage(
            "writes_it",
            [python, "-c", "open('fresh.json', 'w').write('{}')"],
            required_artifacts=("fresh.json",),
        )
        inheritor = Stage(
            "inherits_it",
            [python, "-c", "pass"],
            required_artifacts=("leftover.json",),
        )
        clean = run_stages([writer], cwd=root)
        mutant = run_stages([inheritor], cwd=root)
    clean_result = clean.results[0]
    mutant_result = mutant.results[0]
    return MutationOutcome(
        clean_passes=bool(clean_result.status == "SUCCESS"),
        mutant_detected=bool(mutant_result.status == "STALE_ARTIFACT" and mutant.exit_code != 0),
        detector="artifact_freshness_gate",
        clean_note="a stage that writes its declared artifact is SUCCESS",
        mutant_note=f"a stage that exits 0 without rewriting it is {mutant_result.status}: "
        f"{list(mutant_result.stale_artifacts)}",
    )


# -- Q23: a timeout that loses the run --------------------------------------
def _check_q23() -> MutationOutcome:
    import sys

    python = sys.executable or "python"
    quick = Stage("quick", [python, "-c", "pass"], timeout_s=30.0)
    hangs = Stage("hangs", [python, "-c", "import time; time.sleep(30)"], timeout_s=0.5)
    clean = run_stages([quick])
    mutant = run_stages([hangs])
    mutant_result = mutant.results[0]
    manifest = mutant.to_dict()
    return MutationOutcome(
        clean_passes=bool(clean.status == "COMPLETE"),
        mutant_detected=bool(
            mutant_result.status == "TIMED_OUT"
            and mutant.status == "FAILED"
            and manifest["stages"][0]["status"] == "TIMED_OUT"
        ),
        detector="timeout_manifest_contract",
        clean_note="a stage inside its timeout completes normally",
        mutant_note=f"the killed child is recorded as {mutant_result.status} and the run "
        f"manifest still lists it ({mutant_result.detail})",
    )


# -- Q24: a currency reward attached to an event endpoint -------------------
def _cancellation_endpoint() -> EndpointSpec:
    return EndpointSpec(
        target_id="cancellation90",
        target_kind="binary_event",
        orientation="adverse",
        unit="cancellation_events",
        role="outcome",
        window_end_offset_days=90.0,
        maturity_rule="final at t0 + 90 + 30 days",
    )


def _margin_endpoint() -> EndpointSpec:
    return EndpointSpec(
        target_id="net_contribution90",
        target_kind="currency",
        orientation="beneficial",
        unit="net_contribution_currency_units",
        role="reward",
        window_end_offset_days=90.0,
        maturity_rule="final at t0 + 135 days after refunds",
    )


def _check_q24() -> MutationOutcome:
    clean_ok, clean_note = _passes(
        lambda: _fixture_contract(
            endpoints=(_cancellation_endpoint(), _margin_endpoint()),
            reward_unit="net_contribution_currency_units",
        )
    )
    detected, note = _raises(
        lambda: _fixture_contract(
            endpoints=(_cancellation_endpoint(),),
            reward_unit="net_contribution_currency_units",
        )
    )
    return MutationOutcome(
        clean_passes=clean_ok,
        mutant_detected=detected,
        detector="endpoint_unit_contract",
        clean_note=f"{clean_note} with a declared currency reward endpoint",
        mutant_note=note,
    )


# -- registry ---------------------------------------------------------------
MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "Q01",
        "Churn-prevention sign inverted or arms swapped",
        "hand-computed reward fixture and sign identity",
        "critical",
        "N05",
        _check_q01,
    ),
    Mutation(
        "Q02",
        "Constant propensity under a stratified design",
        "design-log mismatch and known-truth bias alarm",
        "critical",
        "N01",
        _check_q02,
    ),
    Mutation(
        "Q03",
        "Feature event before the snapshot, available after it",
        "point-in-time gate rejects the record",
        "critical",
        "N03",
        _check_q03,
    ),
    Mutation(
        "Q04",
        "Imputer fitted on the evaluation batch",
        "batch, chunk and single-row invariance",
        "major",
        "N03",
        _check_q04,
    ),
    Mutation(
        "Q05",
        "Duplicate assignment after an export retry",
        "uniqueness and idempotency gate",
        "critical",
        "N08",
        _check_q05,
    ),
    Mutation(
        "Q06",
        "Immature or missing outcome recorded as zero",
        "maturity and adjudication gate",
        "critical",
        "N02",
        _check_q06,
    ),
    Mutation(
        "Q07",
        "Delivered-only filter applied after randomization",
        "cohort reconciliation finds the lost ITT denominator",
        "critical",
        "N02",
        _check_q07,
    ),
    Mutation(
        "Q08",
        "Offer cost subtracted twice",
        "ledger identities against an exact tiny example",
        "critical",
        "N07",
        _check_q08,
    ),
    Mutation(
        "Q09",
        "Identical policies given a positive contrast SE",
        "paired-contrast identity",
        "critical",
        "N06",
        _check_q09,
    ),
    Mutation(
        "Q10",
        "Customer-months pooled as independent accounts",
        "unit manifest mismatch and cluster variance",
        "major",
        "N06",
        _check_q10,
    ),
    Mutation(
        "Q11",
        "Enriched sampling without the inclusion weight",
        "sampling contract plus known-truth bias test",
        "critical",
        "N06",
        _check_q11,
    ),
    Mutation(
        "Q12",
        "Candidate selects an action with no logged support",
        "support gate; fallback rather than score imputation",
        "critical",
        "N05",
        _check_q12,
    ),
    Mutation(
        "Q13",
        "Candidates tuned against the confirmation split",
        "access and run ledger detect the role violation",
        "critical",
        "N06",
        _check_q13,
    ),
    Mutation(
        "Q14",
        "Future or oracle column propagated through a rename",
        "lineage and allowed-source checks",
        "critical",
        "N03",
        _check_q14,
    ),
    Mutation(
        "Q15",
        "Tie-break depends on row order",
        "stable-id tie policy and reproducibility fixture",
        "major",
        "N10",
        _check_q15,
    ),
    Mutation(
        "Q16",
        "Allocation breaches capacity or cooldown at a boundary",
        "feasibility checker independent of the allocator",
        "critical",
        "N07",
        _check_q16,
    ),
    Mutation(
        "Q17",
        "Subprocess exits non-zero but the runner reports success",
        "failure-propagation contract",
        "critical",
        "N08",
        _check_q17,
    ),
    Mutation(
        "Q18",
        "Stale bundle loaded against a moved contract",
        "compatibility gate demands explicit migration",
        "critical",
        "N10",
        _check_q18,
    ),
    Mutation(
        "Q19",
        "Known design probability silently replaced by a floor",
        "support contract: unmodified, reject or declared clip",
        "critical",
        "N01",
        _check_q19,
    ),
    Mutation(
        "Q20",
        "Nuisance frames joined by position after a row shuffle",
        "row-key join contract",
        "critical",
        "N06",
        _check_q20,
    ),
    Mutation(
        "Q21",
        "Census recruitment reported as zero uncertainty",
        "recruitment and outcome variance reported separately",
        "critical",
        "N06",
        _check_q21,
    ),
    Mutation(
        "Q22",
        "Artifact from an earlier run certifies this one",
        "artifact freshness and run identity",
        "critical",
        "N08",
        _check_q22,
    ),
    Mutation(
        "Q23",
        "Stage timeout loses the run manifest",
        "timeout status is recorded, not lost",
        "critical",
        "N08",
        _check_q23,
    ),
    Mutation(
        "Q24",
        "Currency reward attached to an event endpoint",
        "endpoint unit and target-kind contract",
        "critical",
        "N00",
        _check_q24,
    ),
)


@dataclass
class SuiteReport:
    rows: list[dict[str, Any]]

    @property
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    @property
    def declared_critical(self) -> int:
        return sum(1 for mutation in MUTATIONS if mutation.severity == "critical")

    @property
    def detected_critical(self) -> int:
        return sum(
            1 for row in self.rows if row["severity"] == "critical" and row["mutant_detected"]
        )

    @property
    def critical_detection_rate(self) -> float:
        declared = self.declared_critical
        return self.detected_critical / declared if declared else float("nan")

    @property
    def false_blocks(self) -> list[str]:
        return [row["mutation_id"] for row in self.rows if not row["clean_passes"]]

    @property
    def undetected(self) -> list[str]:
        return [row["mutation_id"] for row in self.rows if not row["mutant_detected"]]

    @property
    def uncovered(self) -> list[str]:
        covered = {row["mutation_id"] for row in self.rows}
        return [
            mutation.mutation_id for mutation in MUTATIONS if mutation.mutation_id not in covered
        ]

    @property
    def gate_passed(self) -> bool:
        """Every declared-critical mutation detected, and no clean fixture blocked."""

        return self.critical_detection_rate == 1.0 and not self.false_blocks and not self.uncovered

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_declared": len(MUTATIONS),
            "n_executed": len(self.rows),
            "declared_critical": self.declared_critical,
            "detected_critical": self.detected_critical,
            "critical_detection_rate": self.critical_detection_rate,
            "false_block_rate": len(self.false_blocks) / len(self.rows) if self.rows else 0.0,
            "false_blocks": self.false_blocks,
            "undetected": self.undetected,
            "uncovered": self.uncovered,
            "gate_passed": self.gate_passed,
            "results": self.rows,
        }


def run_suite(selected: Sequence[str] | None = None) -> SuiteReport:
    """Execute every covered mutation and record clean and mutant outcomes."""

    wanted = set(selected) if selected else None
    rows: list[dict[str, Any]] = []
    for mutation in MUTATIONS:
        if wanted is not None and mutation.mutation_id not in wanted:
            continue
        if mutation.check is None:  # pragma: no cover - every mutation is covered today
            continue
        outcome = mutation.check()
        rows.append(
            {
                "mutation_id": mutation.mutation_id,
                "title": mutation.title,
                "node": mutation.node,
                "severity": mutation.severity,
                "expected_detector": mutation.expected_detector,
                "detector": outcome.detector,
                "clean_passes": outcome.clean_passes,
                "mutant_detected": outcome.mutant_detected,
                "ok": outcome.ok,
                "clean_note": outcome.clean_note,
                "mutant_note": outcome.mutant_note,
            }
        )
    return SuiteReport(rows)


def _render_markdown(report: SuiteReport) -> str:
    lines = [
        "# E28 challenge suite",
        "",
        "Each row builds a clean fixture and a deliberately broken copy of it. "
        "`clean_passes` is the false-block check; `mutant_detected` is the falsification "
        "check. A pass means the declared fault was caught, not that the pipeline is "
        "safe against faults nobody wrote down.",
        "",
        f"- declared mutations: {len(MUTATIONS)}",
        f"- executed: {report.to_dict()['n_executed']}",
        f"- critical detection: {report.detected_critical}/{report.declared_critical} "
        f"({report.critical_detection_rate:.0%})",
        f"- false blocks: {len(report.false_blocks)}",
        f"- gate: {'PASS' if report.gate_passed else 'FAIL'}",
        "",
        "| ID | Node | Severity | Mutation | Detector | Clean | Detected |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        lines.append(
            f"| {row['mutation_id']} | {row['node']} | {row['severity']} | {row['title']} "
            f"| `{row['detector']}` | {'ok' if row['clean_passes'] else 'BLOCKED'} "
            f"| {'yes' if row['mutant_detected'] else 'NO'} |"
        )
    lines.extend(["", "## Evidence per mutation", ""])
    for row in report.rows:
        lines.extend(
            [
                f"### {row['mutation_id']} — {row['title']}",
                "",
                f"- clean: {row['clean_note']}",
                f"- mutant: {row['mutant_note']}",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the E28 falsification suite.")
    parser.add_argument("--only", nargs="*", default=None, help="mutation ids to run")
    parser.add_argument("--output-dir", default="reports/v4")
    args = parser.parse_args(argv)

    report = run_suite(args.only)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "challenge_suite.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "CHALLENGE_SUITE_REPORT.md").write_text(
        _render_markdown(report), encoding="utf-8"
    )

    for row in report.rows:
        flag = "ok " if row["ok"] else "FAIL"
        print(f"[{flag}] {row['mutation_id']} {row['severity']:<8} {row['title']}")
    print(
        f"critical detection {report.detected_critical}/{report.declared_critical}; "
        f"false blocks {len(report.false_blocks)}; gate "
        f"{'PASS' if report.gate_passed else 'FAIL'}"
    )
    print(f"Reports written to {destination}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
