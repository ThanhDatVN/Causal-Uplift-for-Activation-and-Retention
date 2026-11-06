"""A planner export must reconstruct the same decisions from its own inputs."""

import hashlib
import json
from pathlib import Path

import pytest

from telco_churn.replay import replay_packet
from telco_churn.schema import FEATURE_COLUMNS
from tests.test_api import FixedModel, client, valid_record


def _packet(version: int = 1) -> tuple[dict, dict]:
    records = []
    for index in range(8):
        record = valid_record()
        record["customerID"] = f"customer-{index}"
        record["contact_eligible"] = index != 2
        record["days_since_last_contact"] = 40 if index % 2 else 3
        records.append(record)
    assumptions = {
        "budget_fraction": 0.5,
        "max_total_cost": 30,
        "cooldown_days": 30,
        "scenario": {"save_rate": 0.5, "contact_offer_cost": 15},
    }
    response = client().post(
        f"/v{version}/campaigns/preview", json={"records": records, **assumptions}
    )
    assert response.status_code == 200
    contents = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode()
    packet = {
        **response.json(),
        "packet_version": version,
        "input_records": records,
        "input_customers": len(records),
        "input_sha256": hashlib.sha256(contents).hexdigest(),
        "assumptions": assumptions,
    }
    bundle = {
        "model": FixedModel(),
        "metadata": {
            "artifact_version": "test",
            "feature_columns": FEATURE_COLUMNS,
            "model_sha256": "a" * 64,
            "benchmark_protocol": "test_protocol",
        },
    }
    return packet, bundle


def test_packet_replay_matches_and_detects_changed_decisions() -> None:
    packet, bundle = _packet()
    assert replay_packet(packet, bundle=bundle)["status"] == "MATCH"
    packet["selected"][0]["simulated_expected_value"] += 1
    result = replay_packet(packet, bundle=bundle)
    assert result["status"] == "MISMATCH"
    assert any("selected" in path for path in result["differences"])


def test_packet_replay_rejects_changed_input_before_scoring() -> None:
    packet, bundle = _packet()
    packet["input_records"][0]["MonthlyCharges"] += 1
    assert replay_packet(packet, bundle=bundle)["differences"] == ["input_sha256"]


def test_packet_replay_rejects_incomplete_decision_fields() -> None:
    packet, bundle = _packet()
    packet["summary"].pop("contact_capacity")
    result = replay_packet(packet, bundle=bundle)
    assert result["status"] == "MISMATCH"
    assert "summary.contact_capacity:missing_from_packet" in result["differences"]


def test_packet_replay_checks_model_digest_even_when_version_matches() -> None:
    packet, bundle = _packet()
    packet["model_sha256"] = "different-bundle-with-the-same-version"
    result = replay_packet(packet, bundle=bundle)
    assert result["status"] == "MISMATCH"
    assert "model_sha256" in result["differences"]


def test_v2_packet_replay_matches_and_rejects_changed_scope_or_model() -> None:
    packet, bundle = _packet(version=2)
    assert replay_packet(packet, bundle=bundle)["status"] == "MATCH"
    packet["score_scope"]["horizon_status"] = "validated"
    assert "score_scope.horizon_status" in replay_packet(packet, bundle=bundle)["differences"]
    packet, bundle = _packet(version=2)
    bundle["metadata"]["model_sha256"] = "b" * 64
    assert "model_sha256" in replay_packet(packet, bundle=bundle)["differences"]


def test_frozen_v1_and_v2_packets_match_current_contract() -> None:
    for version in (1, 2):
        packet, bundle = _packet(version)
        fixture = Path(f"tests/fixtures/replay_packet_v{version}.json")
        frozen = json.loads(fixture.read_text(encoding="utf-8"))
        assert packet == frozen
        assert replay_packet(frozen, bundle=bundle)["status"] == "MATCH"
    invalid, bundle = _packet(2)
    invalid["packet_version"] = 3
    with pytest.raises(ValueError, match="Unsupported packet version"):
        replay_packet(invalid, bundle=bundle)
