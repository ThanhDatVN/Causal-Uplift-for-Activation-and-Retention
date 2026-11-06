"""Time-zero, maturity and cohort reconciliation (E19, V4-01)."""

from __future__ import annotations

import pandas as pd
import pytest

from telco_churn.outcome_adjudication import (
    LabelState,
    adjudicate,
    analysis_cohort,
    apply_cohort_definition,
    arm_completeness,
    binary_outcome,
    maturity_imbalance,
    reconcile_cohort,
)
from telco_churn.problem_contract import ContractViolation, load_contracts

T0 = pd.Timestamp("2026-01-01")
MATURE_AS_OF = "2026-06-01"  # horizon 90d + maturity lag 30d
CONTRACTS = load_contracts("configs/problem_contracts.toml")
REFERENCE = CONTRACTS["payment_support@1"]
DELIVERED_ONLY = CONTRACTS["payment_support_delivered_only@1"]
SURVIVOR_COHORT = CONTRACTS["payment_support_survivor_cohort@1"]


def _history(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "t0": T0,
        "assigned_action": "payment_support_call",
        "delivery_at": T0 + pd.Timedelta(days=3),
        "delivered": True,
        "event_at": pd.NaT,
        "event_type": pd.NA,
        "last_observed_at": pd.Timestamp("2026-06-01"),
        "record_status": "ok",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def _states(frame: pd.DataFrame) -> list[str]:
    return list(frame["label_state"].astype(str))


def test_six_states_are_separated() -> None:
    history = _history(
        [
            {
                "account_id": "event",
                "event_at": T0 + pd.Timedelta(days=30),
                "event_type": "cancellation",
            },
            {
                "account_id": "competing",
                "event_at": T0 + pd.Timedelta(days=30),
                "event_type": "involuntary_termination_for_fraud",
            },
            {"account_id": "survivor"},
            {"account_id": "censored", "last_observed_at": T0 + pd.Timedelta(days=40)},
            {"account_id": "missing", "record_status": "missing"},
            {"account_id": "conflict", "record_status": "disputed"},
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    assert _states(labels) == [
        LabelState.OBSERVED_EVENT.value,
        LabelState.OBSERVED_COMPETING_EVENT.value,
        LabelState.OBSERVED_NO_EVENT.value,
        LabelState.RIGHT_CENSORED.value,
        LabelState.RIGHT_CENSORED.value,
        LabelState.UNRESOLVED_CONFLICT.value,
    ]
    assert list(labels["reason_code"])[4] == "missing_outcome_record"


def test_immature_and_censored_rows_never_become_zero() -> None:
    history = _history(
        [
            {"account_id": "survivor"},
            {"account_id": "immature"},
            {"account_id": "censored", "last_observed_at": T0 + pd.Timedelta(days=10)},
        ]
    )
    early = adjudicate(history, REFERENCE, as_of="2026-02-15").labels
    outcome = binary_outcome(early, REFERENCE)
    assert outcome.isna().all()

    mature = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    mature_outcome = binary_outcome(mature, REFERENCE)
    assert mature_outcome.tolist()[:2] == [0, 0]
    assert pd.isna(mature_outcome.tolist()[2])


def test_event_inside_the_correction_window_is_not_yet_final() -> None:
    history = _history(
        [
            {
                "account_id": "recent",
                "event_at": T0 + pd.Timedelta(days=80),
                "event_type": "cancellation",
            }
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of="2026-04-05").labels
    assert _states(labels) == [LabelState.OBSERVED_EVENT.value]
    assert bool(labels["is_mature"].iloc[0]) is False
    assert pd.isna(binary_outcome(labels, REFERENCE).iloc[0])
    assert binary_outcome(labels, REFERENCE, require_mature=False).iloc[0] == 1


def test_event_before_time_zero_cannot_enter_the_baseline() -> None:
    history = _history(
        [
            {
                "account_id": "impossible",
                "event_at": T0 - pd.Timedelta(days=5),
                "event_type": "cancellation",
            }
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    assert _states(labels) == [LabelState.UNRESOLVED_CONFLICT.value]
    assert labels["reason_code"].iloc[0] == "event_before_time_zero"
    assert pd.isna(binary_outcome(labels, REFERENCE).iloc[0])


def test_competing_event_requires_an_explicit_choice() -> None:
    history = _history(
        [
            {
                "account_id": "fraud",
                "event_at": T0 + pd.Timedelta(days=10),
                "event_type": "involuntary_termination_for_fraud",
            }
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    assert pd.isna(binary_outcome(labels, REFERENCE).iloc[0])
    assert binary_outcome(labels, REFERENCE, competing_as="event").iloc[0] == 1


def test_analysis_cohort_keeps_the_itt_denominator() -> None:
    history = _history(
        [
            {
                "account_id": "a",
                "event_at": T0 + pd.Timedelta(days=5),
                "event_type": "cancellation",
            },
            {"account_id": "b"},
            {"account_id": "c", "record_status": "missing"},
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    cohort, reconciliation = analysis_cohort(labels, REFERENCE)
    assert reconciliation["itt_denominator"] == 3
    assert reconciliation["n_analysed"] == 2
    assert reconciliation["excluded_by_state"] == {LabelState.RIGHT_CENSORED.value: 1}
    assert set(cohort["outcome"]) == {0, 1}


def test_dropping_delivered_rows_breaks_reconciliation() -> None:
    history = _history(
        [
            {"account_id": "a", "delivered": True},
            {"account_id": "b", "delivered": True},
            {"account_id": "c", "delivered": False},
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    report = reconcile_cohort(labels, REFERENCE, analysed_ids=["a", "b", "c"])
    assert report["itt_denominator_preserved"] is True
    with pytest.raises(ContractViolation, match="ITT denominator"):
        reconcile_cohort(labels, REFERENCE, analysed_ids=["a", "b"])


def test_cohort_definition_is_gated_by_the_contract() -> None:
    history = _history(
        [
            {"account_id": "a", "delivered": True},
            {"account_id": "b", "delivered": False},
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    kept, report = apply_cohort_definition(labels, REFERENCE)
    assert report["n_removed_post_assignment"] == 0
    assert len(kept) == 2

    control_labels = adjudicate(history, DELIVERED_ONLY, as_of=MATURE_AS_OF).labels
    kept_control, control_report = apply_cohort_definition(control_labels, DELIVERED_ONLY)
    assert len(kept_control) == 1
    assert control_report["promotable"] is False


def test_arm_completeness_flags_treatment_dependent_maturity() -> None:
    history = _history(
        [
            {"account_id": "t1", "assigned_action": "payment_support_call"},
            {"account_id": "t2", "assigned_action": "payment_support_call"},
            {
                "account_id": "c1",
                "assigned_action": "dunning_only",
                "last_observed_at": T0 + pd.Timedelta(days=10),
            },
            {
                "account_id": "c2",
                "assigned_action": "dunning_only",
                "last_observed_at": T0 + pd.Timedelta(days=10),
            },
        ]
    )
    labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    table = arm_completeness(labels)
    shares = dict(zip(table["assigned_action"], table["informative_share"], strict=True))
    assert shares["payment_support_call"] == 1.0
    assert shares["dunning_only"] == 0.0
    assert maturity_imbalance(labels)["balanced"] is False


def test_unknown_action_and_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ContractViolation, match="not in contract"):
        adjudicate(
            _history([{"account_id": "a", "assigned_action": "free_iphone"}]),
            REFERENCE,
            as_of=MATURE_AS_OF,
        )
    with pytest.raises(ContractViolation, match="duplicate account_id"):
        adjudicate(
            _history([{"account_id": "a"}, {"account_id": "a"}]),
            REFERENCE,
            as_of=MATURE_AS_OF,
        )


def test_survivor_cohort_negative_control_drops_immortal_time() -> None:
    """Keeping only accounts still alive when the agent called is immortal time."""

    history = _history(
        [
            # churned before the contact landed on day 3
            {
                "account_id": "early",
                "event_at": T0 + pd.Timedelta(days=1),
                "event_type": "cancellation",
            },
            # churned after the contact
            {
                "account_id": "late",
                "event_at": T0 + pd.Timedelta(days=30),
                "event_type": "cancellation",
            },
            {"account_id": "survivor"},
        ]
    )
    labels = adjudicate(history, SURVIVOR_COHORT, as_of=MATURE_AS_OF).labels
    kept, report = apply_cohort_definition(labels, SURVIVOR_COHORT)
    assert set(kept["account_id"]) == {"late", "survivor"}
    assert report["n_removed_post_assignment"] == 1
    assert report["promotable"] is False

    # The same restriction is refused under the reference protocol.
    reference_labels = adjudicate(history, REFERENCE, as_of=MATURE_AS_OF).labels
    with pytest.raises(ContractViolation, match="ITT denominator"):
        reconcile_cohort(reference_labels, REFERENCE, analysed_ids=["late", "survivor"])
