"""The decision console serves the artifacts, and says what they license."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from telco_churn.dashboard import WEBUI_DIR, create_dashboard

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_dashboard("."))


def test_the_page_and_its_assets_are_served(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "Retention decision console" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_the_evidence_endpoint_returns_the_scored_gates(client: TestClient) -> None:
    payload = client.get("/api/evidence").json()
    assert payload["release_tier"]
    assert {gate["gate_id"] for gate in payload["gates"]} >= {"contracts", "mutation_suite"}
    assert payload["tier_blockers"]


def test_an_unknown_report_is_a_404_not_an_empty_object(client: TestClient) -> None:
    assert client.get("/api/report/not_a_report").status_code == 404


def test_reports_are_served_with_the_path_they_came_from(client: TestClient) -> None:
    payload = client.get("/api/report/challenge_suite").json()
    assert payload["artifact"] == "reports/v4/challenge_suite.json"
    assert payload["payload"]["n_declared"] >= 24


def test_the_cohort_declares_its_evidence_state(client: TestClient) -> None:
    response = client.get("/api/policy/cohort")
    if response.status_code == 404:
        pytest.skip("the Orange holdout predictions are not in this working copy")
    payload = response.json()
    assert payload["evidence_state"] == "CONDITIONAL"
    assert payload["n_units"] == payload["n_control"] + payload["n_treated"]
    assert "risk_logistic" in payload["models"]


def test_the_capacity_curve_reproduces_the_locked_decision(client: TestClient) -> None:
    """The published locked number must come back out of the live allocator."""

    cohort = client.get("/api/policy/cohort")
    if cohort.status_code == 404:
        pytest.skip("the Orange holdout predictions are not in this working copy")
    locked = cohort.json()["locked_decision"]
    response = client.get(
        "/api/policy/allocation",
        params={
            "model": locked["model"],
            "fraction": locked["budget_fraction"],
            # The published budget curves used the ceiling convention.
            "cap_rule": "ceil",
        },
    )
    readout = response.json()["readout"]
    assert readout["dr_uplift"] == pytest.approx(locked["test_dr_uplift"], rel=1e-9)
    assert readout["control_churn_events"] == locked["selected_control_churn_events"]
    assert readout["treated_churn_events"] == locked["selected_treated_churn_events"]
    assert readout["decision"] == locked["test_decision"]
    agreement = response.json()["versus_locked_policy"]
    assert agreement["only_locked"] == 0 and agreement["only_current"] == 0


def test_the_deployment_cap_never_exceeds_the_declared_budget(client: TestClient) -> None:
    response = client.get("/api/policy/curve", params={"repeats": 200})
    if response.status_code == 404:
        pytest.skip("the Orange holdout predictions are not in this working copy")
    payload = response.json()
    for point in payload["points"]:
        assert point["n_selected"] <= point["capacity"]
    assert payload["evidence_state"] == "EXPLORATORY"
    assert "selection on the evaluation set" in payload["scope_note"]


def test_every_curve_point_carries_its_event_counts(client: TestClient) -> None:
    response = client.get("/api/policy/curve", params={"repeats": 200})
    if response.status_code == 404:
        pytest.skip("the Orange holdout predictions are not in this working copy")
    for point in response.json()["points"]:
        if point["dr_uplift"] is None:
            continue
        assert "control_churn_events" in point
        # A decision is never reported without the counts it depends on.
        assert set(point["gates"]) == {
            "positive_dr_ci_lower",
            "at_least_20_control_churn_events",
            "at_least_20_treated_churn_events",
        }


def test_the_temporal_view_is_labelled_synthetic(client: TestClient) -> None:
    response = client.get("/api/temporal/policy-truth", params={"budget_fraction": 0.2})
    if response.status_code == 404:
        pytest.skip("the temporal lab has not been run in this working copy")
    payload = response.json()
    assert payload["evidence_state"] == "SYNTHETIC"
    assert "not evidence about any market" in payload["scope_note"]
    assert any(row["policy"] == "oracle_value" for row in payload["rows"])


def test_a_budget_with_no_rows_is_refused(client: TestClient) -> None:
    response = client.get("/api/temporal/policy-truth", params={"budget_fraction": 0.77})
    assert response.status_code == 404


def test_the_page_keeps_the_forbidden_claims_visible(client: TestClient) -> None:
    text = client.get("/").text
    assert "Statements this evidence does not support" in text
    assert "Production ready" in text


def test_the_static_page_declares_both_themes() -> None:
    styles = (WEBUI_DIR / "styles.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in styles
    assert ':root[data-theme="dark"]' in styles


def test_evidence_payload_is_json_serialisable(client: TestClient) -> None:
    json.dumps(client.get("/api/evidence").json())


def test_cross_domain_and_console_ai_endpoints(client: TestClient) -> None:
    cd_resp = client.get("/api/research/cross-domain")
    assert cd_resp.status_code == 200
    cd_payload = cd_resp.json()
    assert "hillstrom_r02" in cd_payload
    assert "lenta_r10" in cd_payload
    assert "r1_repair" in cd_payload
    json.dumps(cd_payload)

    ai_resp = client.post(
        "/api/ai/ask",
        json={"question": "What happened in the R1 prospective repair study?", "lang": "en"},
    )
    assert ai_resp.status_code == 200
    assert ai_resp.json()["epistemic_state"] == "SYNTHETIC"

    eval_resp = client.get("/api/ai/evaluation")
    assert eval_resp.status_code == 200
    assert eval_resp.json()["overclaim_rate"] == 0.0
