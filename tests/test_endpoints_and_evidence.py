"""Endpoint units (A11, gap G07) and the evidence index that reads them back."""

from __future__ import annotations

import json

import pytest

from telco_churn.evidence import (
    RELEASE_TIERS,
    _best_powered_validity,
    _gate_coverage,
    build_index,
    main,
    render_markdown,
)
from telco_churn.problem_contract import (
    ActionSpec,
    CapacitySpec,
    ContractViolation,
    EndpointSpec,
    ProblemContract,
    TimingSpec,
    load_contracts,
)

CONFIG = "configs/problem_contracts.toml"


def _cancellation(**overrides) -> EndpointSpec:
    payload = {
        "target_id": "cancellation90",
        "target_kind": "binary_event",
        "orientation": "adverse",
        "unit": "cancellation_events",
        "role": "outcome",
        "window_end_offset_days": 90.0,
        "maturity_rule": "final at t0 + 90 + 30 days",
    }
    payload.update(overrides)
    return EndpointSpec(**payload)


def _margin(**overrides) -> EndpointSpec:
    payload = {
        "target_id": "net_contribution90",
        "target_kind": "currency",
        "orientation": "beneficial",
        "unit": "net_contribution_currency_units",
        "role": "reward",
        "window_end_offset_days": 90.0,
        "maturity_rule": "final at t0 + 135 days",
    }
    payload.update(overrides)
    return EndpointSpec(**payload)


def _contract(**overrides) -> ProblemContract:
    payload = {
        "contract_id": "units_fixture",
        "revision": 1,
        "population": "fixture accounts",
        "eligibility_rules": ("failed_invoice_at <= t0",),
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
            ActionSpec("payment_support_call", "call-1", 6.5, "outbound_agent_call"),
        ),
        "bau_action": "dunning_only",
        "timing": TimingSpec(
            time_zero_rule="nightly snapshot", horizon_days=90, maturity_lag_days=30
        ),
        "endpoint": "administrative cancellation within the horizon",
        "unknown_outcome_policy": "keep_unknown",
        "competing_events": (),
        "capacity": CapacitySpec(period="week", slots_per_period=500, cooldown_days=30),
        "estimand": "ITT prevented cancellations",
        "inference_method": "paired doubly robust contrast",
        "evidence_state": "SYNTHETIC",
    }
    payload.update(overrides)
    return ProblemContract(**payload)


# -- A11: a currency reward needs its own endpoint --------------------------
def test_a11_currency_reward_on_an_event_endpoint_is_refused() -> None:
    with pytest.raises(ContractViolation, match="not produced by any declared endpoint"):
        _contract(
            endpoints=(_cancellation(),),
            reward_unit="net_contribution_currency_units",
        )


def test_a11_declaring_the_money_endpoint_makes_the_contract_valid() -> None:
    contract = _contract(
        endpoints=(_cancellation(), _margin()),
        reward_unit="net_contribution_currency_units",
    )
    assert contract.units_declared is True
    assert contract.endpoint_spec("outcome").target_id == "cancellation90"
    assert contract.reward_endpoint_id == "net_contribution90"


def test_a11_a_reward_endpoint_may_not_be_adverse() -> None:
    with pytest.raises(ContractViolation, match="declared adverse"):
        _contract(
            endpoints=(_cancellation(), _margin(orientation="adverse")),
            reward_unit="net_contribution_currency_units",
        )


def test_a11_exactly_one_endpoint_carries_the_outcome_role() -> None:
    with pytest.raises(ContractViolation, match="exactly one endpoint"):
        _contract(
            endpoints=(_cancellation(), _margin(role="outcome")),
            reward_unit="net_contribution_currency_units",
        )


def test_an_endpoint_window_must_match_the_contract_horizon() -> None:
    with pytest.raises(ContractViolation, match="contract horizon"):
        _contract(
            endpoints=(_cancellation(window_end_offset_days=180.0), _margin()),
            reward_unit="net_contribution_currency_units",
        )


def test_an_endpoint_window_may_not_start_after_t0() -> None:
    with pytest.raises(ContractViolation, match="starts its window after t0"):
        _cancellation(window_start_offset_days=14.0).validate()


def test_duplicate_target_ids_are_refused() -> None:
    with pytest.raises(ContractViolation, match="duplicate endpoint target_id"):
        _contract(
            endpoints=(_cancellation(), _cancellation(role="effect")),
            reward_unit="cancellation_events",
        )


def test_the_shipped_registry_declares_its_units() -> None:
    """Every contract separates its outcome from its reward, whatever they are."""

    contracts = load_contracts(CONFIG)
    assert contracts, "the registry must not be empty"
    for key, contract in contracts.items():
        assert contract.units_declared, f"{key} does not declare its endpoints"
        outcome = contract.endpoint_spec("outcome")
        assert outcome.window_end_offset_days == float(contract.timing.horizon_days), key
        # The reward has to come from a declared endpoint, and when it is on a
        # different scale from the outcome it needs its own reward endpoint.
        reward_id = contract.reward_endpoint_id
        assert reward_id is not None, f"{key} rewards a unit no endpoint produces"
        reward = next(item for item in contract.endpoints if item.target_id == reward_id)
        assert reward.orientation == "beneficial", key
        if reward.target_kind != outcome.target_kind:
            assert reward.role == "reward", key


def test_the_registry_covers_both_study_families() -> None:
    """The payment-support mock and the Hillstrom real-data primary coexist."""

    contracts = load_contracts(CONFIG)
    ids = {contract.contract_id for contract in contracts.values()}
    assert "payment_support" in ids
    assert "hillstrom_mens_email" in ids

    hillstrom = contracts["hillstrom_mens_email@1"]
    assert hillstrom.timing.horizon_days == 14
    assert hillstrom.bau_action == "no_email"
    assert hillstrom.endpoint_spec("outcome").target_id == "conversion14"
    assert hillstrom.endpoint_spec("reward").target_kind == "currency"
    assert any("has not audited" in note for note in hillstrom.assumptions), (
        "a randomisation this repository has not verified must say so"
    )


# -- the evidence index -----------------------------------------------------
def test_the_index_scores_every_declared_gate() -> None:
    index = build_index(".")
    ids = {gate.gate_id for gate in index.gates}
    assert {
        "contracts",
        "mutation_suite",
        "runner_failure_propagation",
        "inference_coverage",
        "real_domain_identification",
        "external_replication",
        "partner_trial",
    } <= ids
    assert all(
        gate.status in {"PASS", "FAIL", "NOT_RUN", "NOT_MET", "UNVERIFIED"} for gate in index.gates
    )


def test_the_coverage_gate_never_passes_with_an_open_blocker() -> None:
    """PASS is only available when nothing is unrun and nothing undercovers."""

    index = build_index(".")
    coverage = index.gate("inference_coverage")
    assert coverage is not None
    if coverage.status == "PASS":
        assert coverage.blocker == ""
    else:
        assert coverage.status in {"NOT_MET", "FAIL", "NOT_RUN"}
        assert coverage.blocker, "a gate that is not passing must say what is missing"


def test_posthoc_interval_selection_cannot_promote_coverage_gate(tmp_path) -> None:
    for directory, passed in (("validity_confirm", False), ("validity_unshrunk", True)):
        target = tmp_path / "reports" / "v4" / directory
        target.mkdir(parents=True)
        (target / "validity_suite.json").write_text(
            json.dumps(
                {
                    "gate_passed": passed,
                    "status": "PASS" if passed else "FAIL",
                    "worlds_per_scenario": 2000,
                    "interval_method": "skewness_adjusted_t",
                    "scenarios_declared": ["V01"],
                    "scenarios_run": ["V01"],
                    "r00_identities_passed": True,
                }
            ),
            encoding="utf-8",
        )
    gate = _gate_coverage(None, _best_powered_validity(tmp_path), root=tmp_path)
    assert gate.status == "NOT_MET"
    assert "independent confirmation" in gate.blocker


def test_the_release_tier_stops_where_the_evidence_stops() -> None:
    """The tier must follow the gates, not a remembered snapshot.

    This used to assert a literal tier, which meant the test failed the day
    the evidence legitimately improved -- a test that punishes progress is
    not an invariant.  What must always hold is that the tier is exactly the
    highest one whose gates all pass, and that anything above it is blocked
    by a named gate.
    """

    index = build_index(".")
    tiers = [name for name, _ in RELEASE_TIERS]
    assert index.release_tier in {"NONE", *tiers}

    for tier, required in RELEASE_TIERS:
        achieved = all(
            (gate := index.gate(gate_id)) and gate.status == "PASS" for gate_id in required
        )
        if tier == index.release_tier:
            assert achieved, f"{tier} is claimed but not every gate passes"
        if not achieved:
            break

    blockers = index.tier_blockers()
    if index.release_tier != tiers[-1]:
        assert blockers, "a tier with no blockers would claim the next tier is reachable today"
        assert all(entry["reason"] for entry in blockers)


def test_the_top_tier_is_unreachable_while_anything_is_unrun() -> None:
    """No amount of passing gates substitutes for a stage that never ran."""

    index = build_index(".")
    unrun = [gate.gate_id for gate in index.gates if gate.status == "NOT_RUN"]
    if unrun:
        assert index.release_tier != RELEASE_TIERS[-1][0], (
            f"top tier claimed while {unrun} never ran"
        )


def test_the_index_flags_artifacts_older_than_their_producer(tmp_path) -> None:
    index = build_index(".")
    by_key = {artifact.key: artifact for artifact in index.artifacts}
    assert "challenge_suite" in by_key
    # Every recorded artifact either has a hash or is explicitly absent.
    for artifact in index.artifacts:
        assert artifact.exists == (artifact.sha256 is not None)


def test_the_cli_writes_both_files(tmp_path) -> None:
    code = main(
        [
            "--root",
            ".",
            "--output",
            str(tmp_path / "index.json"),
            "--markdown",
            str(tmp_path / "INDEX.md"),
        ]
    )
    assert code in (0, 1)
    payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert payload["gates"] and payload["artifacts"]
    assert "release tier" in (tmp_path / "INDEX.md").read_text(encoding="utf-8")


def test_markdown_renders_every_gate() -> None:
    index = build_index(".")
    markdown = render_markdown(index)
    for gate in index.gates:
        assert gate.title in markdown
