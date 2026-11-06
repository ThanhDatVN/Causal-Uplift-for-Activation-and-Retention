"""Reward specification, single-count ledger and cost stress (E22, V4-05)."""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.economics import (
    CostPosting,
    RewardLedger,
    RewardSpec,
    break_even_unit_cost,
    cost_stress,
    proxy_reward,
)
from telco_churn.problem_contract import ContractViolation, load_contracts

CONTRACT = load_contracts("configs/problem_contracts.toml")["payment_support@1"]


def _spec(**overrides) -> RewardSpec:
    payload = {
        "value_per_retained": 100.0,
        "unit_costs": {"dunning_only": 0.0, "payment_support_call": 10.0},
    }
    payload.update(overrides)
    return RewardSpec(**payload)


def test_proxy_reward_matches_a_hand_calculation() -> None:
    reward = proxy_reward(
        [1, 0, 0, 0],
        ["dunning_only", "dunning_only", "payment_support_call", "payment_support_call"],
        _spec(),
    )
    # control: churn -> 0, retained -> 100; treated: retained 100 minus the 10 cost
    assert reward.tolist() == [0.0, 100.0, 90.0, 90.0]


def test_cost_is_charged_even_when_the_action_fails() -> None:
    reward = proxy_reward([1], ["payment_support_call"], _spec())
    assert reward.tolist() == [-10.0]


def test_missing_outcomes_may_not_enter_the_reward() -> None:
    with pytest.raises(ContractViolation, match="missing outcome"):
        proxy_reward([1, np.nan], ["dunning_only", "dunning_only"], _spec())


def test_assumed_costs_are_never_labelled_as_evidence() -> None:
    assert _spec().is_evidence is False
    assert _spec(source="actual").is_evidence is True
    from_contract = RewardSpec.from_contract(CONTRACT, value_per_retained=250.0)
    assert from_contract.source == "assumed"
    assert from_contract.unit_costs["payment_support_call"] == 6.5


def _posting(index: int, account: str, kind: str, amount: float) -> CostPosting:
    return CostPosting(f"p{index}", account, "payment_support_call", kind, amount, "actual")


def test_repeated_posting_id_is_rejected() -> None:
    ledger = RewardLedger()
    ledger.add(_posting(1, "a", "offer_cost", 10.0))
    with pytest.raises(ContractViolation, match="already recorded"):
        ledger.add(_posting(1, "a", "offer_cost", 10.0))


def test_repeated_account_action_kind_needs_an_explicit_opt_in() -> None:
    ledger = RewardLedger()
    ledger.add(_posting(1, "a", "offer_cost", 10.0))
    with pytest.raises(ContractViolation, match="already posted"):
        ledger.add(_posting(2, "a", "offer_cost", 10.0))
    ledger.add(_posting(3, "a", "offer_cost", 10.0), allow_repeat=True)
    assert len(ledger) == 2


def test_overhead_is_reported_but_not_incremental() -> None:
    ledger = RewardLedger()
    ledger.add(_posting(1, "a", "retained_margin", 100.0))
    ledger.add(_posting(2, "a", "offer_cost", 10.0))
    ledger.add(_posting(3, "a", "allocated_overhead", 25.0))
    report = ledger.reconcile()
    assert report["incremental_total"] == 90.0
    assert report["allocated_overhead_total"] == -25.0
    assert ledger.net_reward_by_account().loc["a"] == 90.0
    assert ledger.net_reward_by_account(include_overhead=True).loc["a"] == 65.0


def test_double_charged_offer_fails_the_hand_computed_total() -> None:
    ledger = RewardLedger()
    ledger.add(_posting(1, "a", "retained_margin", 100.0))
    ledger.add(_posting(2, "a", "offer_cost", 10.0))
    ledger.add(_posting(3, "b", "offer_cost", 10.0))
    assert ledger.assert_reconciled(expected_total=80.0)["matches_expected"] is True
    ledger.add(_posting(4, "a", "offer_cost", 10.0), allow_repeat=True)
    with pytest.raises(ContractViolation, match="does not match"):
        ledger.assert_reconciled(expected_total=80.0)


def test_a_single_assumed_posting_downgrades_the_whole_ledger() -> None:
    ledger = RewardLedger()
    ledger.add(_posting(1, "a", "retained_margin", 100.0))
    ledger.add(CostPosting("p2", "a", "payment_support_call", "offer_cost", 10.0, "assumed"))
    assert ledger.source == "assumed"


def test_negative_amounts_are_rejected_so_signs_stay_readable() -> None:
    with pytest.raises(ContractViolation, match="negative amount"):
        RewardLedger().add(_posting(1, "a", "refund", -5.0))


def test_break_even_is_zero_for_a_null_or_harmful_action() -> None:
    assert break_even_unit_cost(0.02, 100.0) == 2.0
    assert break_even_unit_cost(0.0, 100.0) == 0.0
    assert break_even_unit_cost(-0.01, 100.0) == 0.0


def test_cost_stress_flips_the_recommendation_and_keeps_its_provenance() -> None:
    table = cost_stress(0.12, _spec(), "payment_support_call", multipliers=(0.5, 1.0, 2.0))
    assert table.attrs["break_even_unit_cost"] == pytest.approx(12.0)
    assert table.attrs["recommendation_flips"] is True
    assert list(table["recommendation"]) == ["act", "act", "hold_bau"]
    assert set(table["evidence_source"]) == {"assumed"}


def test_cost_stress_holds_business_as_usual_when_nothing_is_prevented() -> None:
    table = cost_stress(0.0, _spec(), "payment_support_call")
    assert set(table["recommendation"]) == {"hold_bau"}
    assert table.attrs["recommendation_flips"] is False


def test_adjudicated_missing_labels_are_rejected_not_silently_zeroed() -> None:
    """A nullable Int8 column straight from `binary_outcome` must not sneak through."""

    import pandas as pd

    outcome = pd.Series([1, pd.NA, 0], dtype="Int8")
    with pytest.raises(ContractViolation, match="missing outcome"):
        proxy_reward(outcome, ["dunning_only"] * 3, _spec())
