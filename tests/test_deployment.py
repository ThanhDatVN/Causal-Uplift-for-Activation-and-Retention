"""Deployment surface: health, provenance and the smoke checks themselves.

The live stack is exercised by ``python -m telco_churn.deployment_smoke``
against running containers.  These tests cover the parts that must hold
without Docker: the endpoints an orchestrator probes, the content address of
the served evidence, and the smoke report's own pass/fail semantics -- a smoke
runner that cannot fail is not a check.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from telco_churn.dashboard import _snapshot_id, create_dashboard
from telco_churn.deployment_smoke import Check, SmokeReport, main, run_smoke
from telco_churn.evidence import build_index

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_dashboard("."))


# -- probes an orchestrator uses -------------------------------------------
def test_liveness_says_nothing_about_the_artifacts(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}


def test_readiness_reports_the_tier_it_can_serve(client: TestClient) -> None:
    payload = client.get("/health/ready").json()
    assert payload["status"] == "ready"
    assert payload["release_tier"]


def test_readiness_fails_when_the_evidence_is_missing(tmp_path) -> None:
    empty = TestClient(create_dashboard(tmp_path), raise_server_exceptions=False)
    response = empty.get("/health/ready")
    assert response.status_code == 503
    assert "missing evidence artifacts" in response.json()["detail"]


def test_deployment_endpoint_declares_its_bounds(client: TestClient) -> None:
    payload = client.get("/api/deployment").json()
    assert payload["read_only"] is True
    assert payload["artifacts_present"] <= payload["artifacts_declared"]
    assert "no authentication" in payload["security_note"]
    assert any("never refits" in line for line in payload["operational_bounds"])


def test_the_snapshot_id_is_a_content_address_of_the_artifacts() -> None:
    index = build_index(".").to_dict()
    first = _snapshot_id(index)
    assert first == _snapshot_id(index), "the same artifacts must give the same id"

    changed = json.loads(json.dumps(index))
    changed["artifacts"][0]["sha256"] = "0" * 64
    assert _snapshot_id(changed) != first, "a changed artifact must change the id"


def test_the_console_is_not_indexed(client: TestClient) -> None:
    body = client.get("/robots.txt").text
    assert "Disallow: /" in body


def test_the_console_routes_no_write_method(client: TestClient) -> None:
    assert client.post("/api/evidence", json={}).status_code in (404, 405)


# -- the smoke runner's own semantics --------------------------------------
def test_a_required_failure_fails_the_run_and_a_skip_does_not() -> None:
    report = SmokeReport()
    report.add(Check("ok", True, "fine"))
    report.add(Check("optional", False, "not available", required=False))
    assert report.passed is True
    assert [check.name for check in report.skipped] == ["optional"]

    report.add(Check("broken", False, "went wrong"))
    assert report.passed is False
    assert [check.name for check in report.failures] == ["broken"]
    assert "FAIL" in report.render()


def test_the_report_renders_every_check() -> None:
    report = SmokeReport()
    report.add(Check("alpha", True, "detail one"))
    report.add(Check("beta", False, "detail two", required=False))
    rendered = report.render()
    assert "| alpha | pass | detail one |" in rendered
    assert "| beta | skipped | detail two |" in rendered


def _stub_transport(*, api_ready: bool = True) -> httpx.MockTransport:
    """Canned responses for a deployment that is up (or an API that is not)."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/health/live":
            return httpx.Response(200, json={"status": "alive"})
        if path == "/health/ready":
            if not api_ready and request.url.port == 8000:
                return httpx.Response(503, json={"detail": "model not loaded"})
            return httpx.Response(200, json={"status": "ready", "release_tier": "TIER"})
        if path == "/v1/model-info":
            return httpx.Response(200, json={"artifact_version": "1.0.0"})
        if path == "/v1/predict":
            return httpx.Response(422, json={"detail": "inconsistent"})
        if path == "/api/deployment":
            return httpx.Response(
                200,
                json={
                    "read_only": True,
                    "evidence_snapshot": "deadbeefdeadbeef",
                    "artifacts_present": 3,
                    "artifacts_declared": 4,
                    "release_tier": "TIER",
                },
            )
        if path == "/api/evidence":
            return httpx.Response(405, json={"detail": "method not allowed"})
        if path == "/api/policy/allocation":
            return httpx.Response(
                200,
                json={
                    "readout": {
                        "dr_uplift": 0.5,
                        "decision": "no_launch",
                        "control_churn_events": 1,
                    }
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_run_smoke_collects_every_check_against_a_stub(tmp_path) -> None:
    with httpx.Client(transport=_stub_transport()) as stub:
        report = run_smoke(root=tmp_path, client=stub)
    names = [check.name for check in report.checks]
    assert names[:4] == ["api_live", "api_ready", "api_model_info", "api_rejects_invalid_input"]
    assert "console_exposes_no_write_path" in names
    # No host model or data under tmp_path, so parity reports as skipped rather
    # than silently passing.
    parity = next(check for check in report.checks if check.name == "host_container_parity")
    assert parity.required is False and parity.passed is False


def test_an_unready_api_fails_the_run() -> None:
    with httpx.Client(transport=_stub_transport(api_ready=False)) as stub:
        report = run_smoke(root=".", client=stub, api="http://127.0.0.1:8000")
    assert report.passed is False
    assert "api_ready" in [check.name for check in report.failures]


def test_a_snapshot_mismatch_is_reported_but_not_fatal() -> None:
    with httpx.Client(transport=_stub_transport()) as stub:
        report = run_smoke(root=".", client=stub)
    mismatch = next(
        check for check in report.checks if check.name == "evidence_snapshot_matches_host"
    )
    assert mismatch.passed is False
    assert mismatch.required is False
    assert "different snapshot" in mismatch.detail


def test_the_cli_writes_both_artifacts_and_returns_the_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "telco_churn.deployment_smoke.run_smoke",
        lambda **_: SmokeReport(checks=[Check("stub", True, "ok")]),
    )
    code = main(["--root", str(tmp_path), "--output-dir", "reports/deployment"])
    assert code == 0
    payload = json.loads(
        (tmp_path / "reports/deployment/deployment_smoke.json").read_text(encoding="utf-8")
    )
    assert payload["status"] == "PASS"
    assert "Deployment smoke" in (tmp_path / "reports/deployment/DEPLOYMENT_SMOKE.md").read_text(
        encoding="utf-8"
    )


def test_the_database_check_is_skipped_without_a_dsn() -> None:
    with httpx.Client(transport=_stub_transport()) as stub:
        report = run_smoke(root=".", client=stub, dsn=None)
    database = next(check for check in report.checks if check.name == "database_schema")
    assert database.required is False
    assert "no --dsn" in database.detail
