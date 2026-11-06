"""Contract validation and the data-role access ledger (V4-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from telco_churn.problem_contract import (
    ActionSpec,
    CapacitySpec,
    ContractViolation,
    DataRole,
    DataRoleRegistry,
    ProblemContract,
    TimingSpec,
    load_contracts,
    summarise_contracts,
)

CONFIG = "configs/problem_contracts.toml"


def _timing(**overrides) -> TimingSpec:
    payload = {
        "time_zero_rule": "nightly snapshot on grace-period entry",
        "horizon_days": 90,
        "maturity_lag_days": 30,
    }
    payload.update(overrides)
    return TimingSpec(**payload)


def _contract(**overrides) -> ProblemContract:
    payload = {
        "contract_id": "fixture",
        "revision": 1,
        "population": "accounts in a failed-payment grace period",
        "eligibility_rules": ("grace_period_end > t0",),
        "decision_unit": "account",
        "randomization_unit": "account",
        "actions": (
            ActionSpec("bau", "v1", 0.0, "email", is_bau=True, requires_delivery=False),
            ActionSpec("call", "v1", 6.5, "phone"),
        ),
        "bau_action": "bau",
        "timing": _timing(),
        "endpoint": "cancellation within the horizon",
        "unknown_outcome_policy": "keep_unknown",
        "competing_events": (),
        "capacity": CapacitySpec(period="week", slots_per_period=100),
        "estimand": "ITT prevented cancellations",
        "inference_method": "paired DR contrast",
    }
    payload.update(overrides)
    return ProblemContract(**payload)


def test_shipped_registry_loads_and_flags_negative_controls() -> None:
    contracts = load_contracts(CONFIG)
    summary = {row["contract_id"]: row for row in summarise_contracts(contracts.values())}
    assert summary["payment_support"]["promotable"] is True
    assert summary["payment_support_delivered_only"]["promotable"] is False
    assert summary["payment_support_survivor_cohort"]["promotable"] is False


def test_feature_cutoff_after_time_zero_is_rejected() -> None:
    with pytest.raises(ContractViolation, match="post-decision"):
        _contract(timing=_timing(feature_cutoff_offset_days=1.0))


def test_assignment_and_follow_up_are_pinned_to_time_zero() -> None:
    with pytest.raises(ContractViolation, match="assignment must happen at t0"):
        _contract(timing=_timing(assignment_offset_days=2.0))
    with pytest.raises(ContractViolation, match="follow-up must start at t0"):
        _contract(timing=_timing(follow_up_start_offset_days=2.0))


def test_unknown_outcomes_may_not_be_recoded_as_non_events() -> None:
    with pytest.raises(ContractViolation, match="may not be recoded"):
        _contract(unknown_outcome_policy="treat_as_no_event")


def test_post_assignment_cohort_requires_a_negative_control_declaration() -> None:
    with pytest.raises(ContractViolation, match="negative control"):
        _contract(cohort_definition="delivered_only")
    control = _contract(
        cohort_definition="delivered_only", is_negative_control=True, evidence_state="SYNTHETIC"
    )
    assert control.promotable is False
    with pytest.raises(ContractViolation, match="diagnostics"):
        control.require_promotable()


def test_negative_control_may_not_hold_confirmatory_evidence() -> None:
    with pytest.raises(ContractViolation, match="never hold confirmatory"):
        _contract(
            cohort_definition="delivered_only",
            is_negative_control=True,
            evidence_state="CONFIRMATORY",
        )


def test_exactly_one_business_as_usual_action() -> None:
    with pytest.raises(ContractViolation, match="exactly one action"):
        _contract(
            actions=(
                ActionSpec("bau", "v1", 0.0, "email", is_bau=True),
                ActionSpec("call", "v1", 6.5, "phone", is_bau=True),
            )
        )


def test_revision_increments_and_never_overwrites() -> None:
    original = _contract()
    revised = original.revise(endpoint="cancellation within 180 days")
    assert (original.revision, revised.revision) == (1, 2)
    assert original.endpoint != revised.endpoint
    with pytest.raises(ContractViolation, match="managed by revise"):
        original.revise(revision=5)


def test_unknown_config_keys_fail_loudly(tmp_path) -> None:
    source = Path(CONFIG).read_text(encoding="utf-8")
    broken = tmp_path / "broken.toml"
    broken.write_text(source + '\n[[contract]]\ncontract_id = "x"\nmystery = 1\n', encoding="utf-8")
    with pytest.raises(ContractViolation, match="unknown contract keys"):
        load_contracts(broken)


# -- data-role registry -----------------------------------------------------
def _registry() -> DataRoleRegistry:
    registry = DataRoleRegistry(contract_id="fixture")
    registry.register("dev", DataRole.TRAINING, row_count=100, data_hash="h1")
    registry.register("inner", DataRole.INNER_EVALUATION, row_count=50, data_hash="h2")
    registry.register("holdout", DataRole.CONFIRMATION, row_count=40, data_hash="h3")
    return registry


def test_selection_purposes_may_not_touch_confirmation() -> None:
    registry = _registry()
    registry.record_access("inner", purpose="model_selection", reads_outcomes=True)
    with pytest.raises(ContractViolation, match="may not touch the confirmation split"):
        registry.record_access("holdout", purpose="model_selection", reads_outcomes=True)


def test_confirmation_opens_exactly_once() -> None:
    registry = _registry()
    registry.record_access("holdout", purpose="confirmation_evaluation", reads_outcomes=True)
    with pytest.raises(ContractViolation, match="already opened"):
        registry.record_access("holdout", purpose="confirmation_evaluation", reads_outcomes=True)
    assert registry.confirmation_reads() == 1


def test_confirmation_features_may_be_read_without_outcomes() -> None:
    registry = _registry()
    registry.record_access("holdout", purpose="schema_check", reads_outcomes=False)
    registry.assert_clean()


def test_shared_hash_between_roles_is_a_violation() -> None:
    registry = DataRoleRegistry(contract_id="fixture")
    registry.register("dev", DataRole.TRAINING, row_count=100, data_hash="same")
    registry.register("holdout", DataRole.CONFIRMATION, row_count=40, data_hash="same")
    with pytest.raises(ContractViolation, match="share a\ndata hash|share a data hash"):
        registry.assert_clean()


def test_manifest_records_every_access() -> None:
    registry = _registry()
    registry.record_access("dev", purpose="model_fit", reads_outcomes=True)
    registry.record_access("holdout", purpose="confirmation_evaluation", reads_outcomes=True)
    manifest = registry.manifest()
    assert manifest["confirmation_reads"] == 1
    assert len(manifest["accesses"]) == 2
    assert manifest["violations"] == []
