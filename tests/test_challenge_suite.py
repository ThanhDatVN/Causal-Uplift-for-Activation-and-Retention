"""The falsification suite, and proof that the suite itself can fail (E28, V4-03)."""

from __future__ import annotations

import json

import pytest

from telco_churn.challenge_suite import MUTATIONS, SuiteReport, main, run_suite


def test_every_declared_mutation_has_an_executable_check() -> None:
    assert len(MUTATIONS) == 24
    ids = [mutation.mutation_id for mutation in MUTATIONS]
    assert ids == [f"Q{index:02d}" for index in range(1, 25)]
    assert all(mutation.is_covered for mutation in MUTATIONS)


def test_suite_detects_every_critical_mutation_without_blocking_clean_fixtures() -> None:
    report = run_suite()
    assert report.uncovered == []
    assert report.false_blocks == [], "a clean fixture was rejected by its own detector"
    assert report.undetected == [], "a planted fault went unnoticed"
    assert report.critical_detection_rate == 1.0
    assert report.gate_passed is True


@pytest.mark.parametrize(
    ("mutation_id", "expected_detector"),
    [
        ("Q06", "maturity_and_adjudication_gate"),
        ("Q07", "itt_cohort_reconciliation"),
        ("Q09", "paired_contrast_identity"),
        ("Q11", "sampling_contract_known_truth"),
        ("Q17", "stage_failure_propagation"),
        ("Q19", "propensity_support_contract"),
        ("Q20", "row_key_join_contract"),
        ("Q21", "recruitment_variance_decomposition"),
        ("Q22", "artifact_freshness_gate"),
        ("Q24", "endpoint_unit_contract"),
    ],
)
def test_named_detectors_are_the_ones_that_fire(mutation_id: str, expected_detector: str) -> None:
    row = run_suite([mutation_id]).rows[0]
    assert row["detector"] == expected_detector
    assert row["ok"] is True


def _row(**overrides) -> dict:
    payload = {
        "mutation_id": "Q01",
        "title": "t",
        "node": "N05",
        "severity": "critical",
        "expected_detector": "d",
        "detector": "d",
        "clean_passes": True,
        "mutant_detected": True,
        "ok": True,
        "clean_note": "",
        "mutant_note": "",
    }
    payload.update(overrides)
    return payload


def test_the_gate_fails_when_a_critical_fault_slips_through() -> None:
    passing = run_suite()
    slipped = {**passing.rows[-1], "mutant_detected": False, "ok": False}
    weakened = SuiteReport([*passing.rows[:-1], slipped])
    assert weakened.undetected == [slipped["mutation_id"]]
    assert weakened.gate_passed is False


def test_the_gate_fails_when_a_detector_blocks_a_clean_fixture() -> None:
    report = SuiteReport([_row(clean_passes=False, ok=False)])
    assert report.false_blocks == ["Q01"]
    assert report.gate_passed is False


def test_the_gate_fails_when_a_declared_mutation_is_never_executed() -> None:
    report = run_suite(["Q01"])
    assert len(report.uncovered) == 23
    assert report.gate_passed is False


def test_cli_writes_both_artifacts_and_returns_zero_on_a_pass(tmp_path) -> None:
    code = main(["--output-dir", str(tmp_path)])
    assert code == 0
    payload = json.loads((tmp_path / "challenge_suite.json").read_text(encoding="utf-8"))
    assert payload["gate_passed"] is True
    assert payload["n_executed"] == 24
    assert payload["false_block_rate"] == 0.0
    markdown = (tmp_path / "CHALLENGE_SUITE_REPORT.md").read_text(encoding="utf-8")
    assert "| Q01 |" in markdown
    assert "gate: PASS" in markdown
