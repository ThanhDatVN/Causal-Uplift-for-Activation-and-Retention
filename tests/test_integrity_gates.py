"""Point-in-time, lineage, feasibility and bundle-compatibility gates."""

from __future__ import annotations

import pandas as pd
import pytest

from telco_churn.integrity_gates import (
    FeatureLineage,
    assert_bundle_compatible,
    assert_feasible,
    assert_point_in_time,
    capacity_violations,
    declared_schema_fingerprint,
    point_in_time_violations,
)
from telco_churn.problem_contract import ContractViolation, load_contracts

CONTRACT = load_contracts("configs/problem_contracts.toml")["payment_support@1"]
T0 = pd.Timestamp("2026-01-01")


def _decisions() -> pd.DataFrame:
    return pd.DataFrame({"account_id": ["a", "b"], "t0": [T0, T0]})


def _ledger(available_offsets: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account_id": ["a", "b"],
            "feature_name": ["arrears_balance", "arrears_balance"],
            "event_at": [T0 - pd.Timedelta(days=5)] * 2,
            "available_at": [T0 + pd.Timedelta(days=offset) for offset in available_offsets],
        }
    )


def test_a_late_published_fact_is_a_leak_even_with_an_early_event() -> None:
    assert_point_in_time(_ledger([-1, -1]), _decisions(), CONTRACT)
    with pytest.raises(ContractViolation, match="not available at the decision instant"):
        assert_point_in_time(_ledger([-1, 2]), _decisions(), CONTRACT)


def test_missing_availability_is_treated_as_unreadable() -> None:
    ledger = _ledger([-1, -1])
    ledger.loc[1, "available_at"] = pd.NaT
    violations = point_in_time_violations(ledger, _decisions(), CONTRACT)
    assert list(violations["reason"]) == ["missing_available_at"]


def test_feature_rows_without_a_decision_are_rejected() -> None:
    ledger = _ledger([-1, -1])
    ledger.loc[1, "account_id"] = "ghost"
    with pytest.raises(ContractViolation, match="without a decision"):
        point_in_time_violations(ledger, _decisions(), CONTRACT)


# -- lineage ----------------------------------------------------------------
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


def test_forbidden_lineage_survives_a_rename() -> None:
    lineage = _lineage()
    lineage.derive("risk_proxy", ["tenure_days", "cancelled_within_90d"])
    lineage.rename("risk_proxy", "cust_score")
    with pytest.raises(ContractViolation, match="forbidden lineage"):
        lineage.assert_allowed(["cust_score"], forbidden_sources={"outcome_ledger"})


def test_clean_derivations_pass_and_carry_both_parents() -> None:
    lineage = _lineage()
    lineage.derive("arrears_per_month", ["arrears_balance", "tenure_days"])
    lineage.assert_allowed(
        ["arrears_balance", "tenure_days", "arrears_per_month"],
        forbidden_sources={"outcome_ledger"},
    )
    assert lineage.sources_of("arrears_per_month") == frozenset({"billing_ledger", "crm"})


def test_an_undeclared_column_may_not_enter_a_model() -> None:
    with pytest.raises(ContractViolation, match="no declared lineage"):
        _lineage().assert_allowed(["mystery"], forbidden_sources=set())


# -- capacity ---------------------------------------------------------------
def _plan(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["account_id", "assigned_at", "action"])


def test_feasible_plan_raises_nothing() -> None:
    # 500 weekly slots, 30-day cooldown in the shipped contract.
    assert_feasible(
        _plan(
            [
                ("a", "2026-01-05", "payment_support_call"),
                ("b", "2026-01-06", "payment_support_call"),
                ("a", "2026-02-10", "payment_support_call"),
            ]
        ),
        CONTRACT,
    )


def test_cooldown_and_duplicates_are_detected() -> None:
    problems = capacity_violations(
        _plan(
            [
                ("a", "2026-01-05", "payment_support_call"),
                ("a", "2026-01-20", "payment_support_call"),
                ("b", "2026-01-06", "payment_support_call"),
                ("b", "2026-01-06", "payment_support_call"),
            ]
        ),
        CONTRACT,
    )
    kinds = {problem["kind"] for problem in problems}
    assert kinds == {"cooldown_breached", "duplicate_assignment"}


def test_business_as_usual_does_not_consume_contact_slots() -> None:
    plan = _plan([(f"a{index}", "2026-01-05", "dunning_only") for index in range(2000)])
    assert capacity_violations(plan, CONTRACT) == []


def test_actions_outside_the_contract_are_rejected() -> None:
    with pytest.raises(ContractViolation, match="outside the contract"):
        capacity_violations(_plan([("a", "2026-01-05", "free_iphone")]), CONTRACT)


# -- bundle compatibility ---------------------------------------------------
def _bundle(**overrides) -> dict:
    payload = {
        "contract_id": CONTRACT.contract_id,
        "contract_revision": CONTRACT.revision,
        "endpoint": CONTRACT.endpoint,
        "action_versions": {action.name: action.version for action in CONTRACT.actions},
    }
    payload.update(overrides)
    return payload


def test_matching_bundle_loads() -> None:
    assert_bundle_compatible(CONTRACT, _bundle())


def test_revision_endpoint_and_action_drift_all_block_the_load() -> None:
    with pytest.raises(ContractViolation, match="revision"):
        assert_bundle_compatible(CONTRACT, _bundle(contract_revision=99))
    with pytest.raises(ContractViolation, match="endpoint"):
        assert_bundle_compatible(CONTRACT, _bundle(endpoint="something else"))
    drifted = {action.name: "stale" for action in CONTRACT.actions}
    with pytest.raises(ContractViolation, match="action version drift"):
        assert_bundle_compatible(CONTRACT, _bundle(action_versions=drifted))
    with pytest.raises(ContractViolation, match="missing required key"):
        assert_bundle_compatible(CONTRACT, {"contract_id": CONTRACT.contract_id})


def test_schema_fingerprint_ignores_column_order() -> None:
    assert declared_schema_fingerprint(["b", "a"]) == declared_schema_fingerprint(["a", "b"])
    assert declared_schema_fingerprint(["a"]) != declared_schema_fingerprint(["a", "b"])


def test_every_capacity_period_buckets_correctly() -> None:
    """Month and campaign periods share the alias table with day and week."""

    from dataclasses import replace

    plan = _plan(
        [
            ("a", "2026-01-31", "payment_support_call"),
            ("b", "2026-02-01", "payment_support_call"),
            ("c", "2026-02-02", "payment_support_call"),
        ]
    )
    # Pandas weeks end on Sunday, so Sat 31 Jan and Sun 1 Feb share a week and
    # Mon 2 Feb opens the next one.
    for period, slots, expected_breaches in [
        ("day", 1, 0),  # three distinct days, one slot each
        ("week", 1, 1),  # the 26 Jan week holds two of the three
        ("month", 2, 0),  # one January, two February
        ("campaign", 2, 1),  # a single bucket of three
    ]:
        contract = replace(
            CONTRACT,
            capacity=replace(
                CONTRACT.capacity, period=period, slots_per_period=slots, cooldown_days=0
            ),
        )
        breaches = [
            problem
            for problem in capacity_violations(plan, contract)
            if problem["kind"] == "capacity_exceeded"
        ]
        assert len(breaches) == expected_breaches, (period, breaches)
