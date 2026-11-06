import numpy as np
from fastapi.testclient import TestClient

from telco_churn.api import create_app
from telco_churn.schema import FEATURE_COLUMNS


class FixedModel:
    def predict_proba(self, frame):
        probability = np.full(len(frame), 0.7)
        return np.column_stack([1 - probability, probability])


def valid_record() -> dict:
    return {
        "customerID": "7590-VHVEG",
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "No",
        "PhoneService": "No",
        "MultipleLines": "No phone service",
        "InternetService": "DSL",
        "OnlineSecurity": "No",
        "OnlineBackup": "Yes",
        "DeviceProtection": "No",
        "TechSupport": "No",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "tenure": 1,
        "MonthlyCharges": 29.85,
        "TotalCharges": 29.85,
    }


def client() -> TestClient:
    return TestClient(
        create_app(
            bundle={
                "model": FixedModel(),
                "metadata": {
                    "artifact_version": "test",
                    "feature_columns": FEATURE_COLUMNS,
                    "model_sha256": "a" * 64,
                    "benchmark_protocol": "test_protocol",
                },
            }
        )
    )


def test_health_and_prediction_contract() -> None:
    test_client = client()
    assert test_client.get("/health/ready").status_code == 200
    response = test_client.post("/v1/predict", json={"records": [valid_record()]})
    assert response.status_code == 200
    assert response.json()["predictions"][0]["risk_30d"] == 0.7


def test_v2_predict_preserves_score_and_exposes_unvalidated_horizon() -> None:
    test_client = client()
    request = {"records": [valid_record()]}
    legacy = test_client.post("/v1/predict", json=request)
    current = test_client.post("/v2/predict", json=request)
    assert legacy.status_code == current.status_code == 200
    payload = current.json()
    assert payload["predictions"] == [
        {"customer_id": valid_record()["customerID"], "churn_risk_probability": 0.7}
    ]
    assert (
        payload["predictions"][0]["churn_risk_probability"]
        == legacy.json()["predictions"][0]["risk_30d"]
    )
    assert payload["score_scope"]["horizon_status"] == "unvalidated"
    assert payload["score_scope"]["model_sha256"] == "a" * 64
    assert "risk_30d" not in str(payload)
    invalid = valid_record()
    invalid["unexpected"] = "field"
    assert test_client.post("/v2/predict", json={"records": [invalid]}).status_code == 422


def test_v2_preview_matches_v1_decisions_without_legacy_risk_field() -> None:
    test_client = client()
    request = {"records": [valid_record()], "budget_fraction": 1}
    legacy = test_client.post("/v1/campaigns/preview", json=request)
    current = test_client.post("/v2/campaigns/preview", json=request)
    assert legacy.status_code == current.status_code == 200
    old = legacy.json()
    new = current.json()
    assert old["summary"] == new["summary"]
    assert (
        old["ranked_candidates"][0]["risk_30d"]
        == new["ranked_candidates"][0]["churn_risk_probability"]
    )
    assert "risk_30d" not in str(new)
    assert new["score_scope"]["model_sha256"] == new["model_sha256"]


def test_unknown_field_and_structural_conflict_return_422() -> None:
    record = valid_record()
    record["unexpected"] = "field"
    assert client().post("/v1/predict", json={"records": [record]}).status_code == 422
    record = valid_record()
    record["MultipleLines"] = "Yes"
    assert client().post("/v1/predict", json={"records": [record]}).status_code == 422


def test_campaign_preview_never_claims_measured_impact() -> None:
    response = client().post(
        "/v1/campaigns/preview",
        json={"records": [valid_record()], "budget_fraction": 0.1},
    )
    assert response.status_code == 200
    assert "simulated" in response.json()["assumption_warning"].lower()
    assert response.json()["evidence_type"] == "risk_model_with_assumed_offer_response"
    assert len(response.json()["ranked_candidates"]) == 1


def test_duplicate_customer_ids_are_rejected() -> None:
    response = client().post(
        "/v1/campaigns/preview", json={"records": [valid_record(), valid_record()]}
    )
    assert response.status_code == 422
    assert "unique" in str(response.json()).lower()


def test_zero_margin_preview_serializes_unreachable_break_even_rate() -> None:
    response = client().post(
        "/v1/campaigns/preview",
        json={"records": [valid_record()], "scenario": {"gross_margin_rate": 0}},
    )
    assert response.status_code == 200
    assert response.json()["ranked_candidates"][0]["break_even_save_rate"] is None


def test_preview_reports_budget_and_sensitivity_without_claiming_impact() -> None:
    records = []
    for index in range(8):
        record = valid_record()
        record["customerID"] = f"customer-{index}"
        record["MonthlyCharges"] = 100
        records.append(record)
    response = client().post(
        "/v1/campaigns/preview",
        json={
            "records": records,
            "budget_fraction": 0.25,
            "max_total_cost": 15,
            "scenario": {"save_rate": 0.2, "contact_offer_cost": 15},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["contact_capacity"] == 2
    assert payload["summary"]["selected_customers"] == 1
    assert payload["summary"]["assumed_contact_spend"] == 15
    assert payload["summary"]["reason_counts"]["cost_cap_reached"] >= 1
    assert [item["label"] for item in payload["sensitivity"]] == ["lower", "current", "higher"]
    assert (
        payload["sensitivity"][0]["simulated_total_expected_value"]
        <= payload["sensitivity"][-1]["simulated_total_expected_value"]
    )


def test_cooldown_and_eligibility_exclude_before_ranking() -> None:
    records = []
    for index, fields in enumerate(
        (
            {"contact_eligible": False, "days_since_last_contact": 90},
            {"contact_eligible": True, "days_since_last_contact": 4},
            {"contact_eligible": True},
            {"contact_eligible": True, "days_since_last_contact": 60},
        )
    ):
        record = valid_record()
        record.update(fields)
        record["customerID"] = f"customer-{index}"
        records.append(record)
    response = client().post(
        "/v1/campaigns/preview",
        json={
            "records": records,
            "budget_fraction": 1,
            "cooldown_days": 30,
            "scenario": {"save_rate": 1, "contact_offer_cost": 0},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["customer_id"] for item in payload["selected"]] == ["customer-3"]
    assert payload["summary"]["reason_counts"] == {
        "not_eligible": 1,
        "cooldown_active": 1,
        "missing_contact_history": 1,
        "selected": 1,
    }
    assert all(item["selected_customers"] == 1 for item in payload["sensitivity"])


def test_planner_is_served_from_the_api() -> None:
    test_client = client()
    assert test_client.get("/").status_code == 200
    response = test_client.get("/planner/")
    assert response.status_code == 200
    assert "Campaign Planner" in response.text


def test_ai_explain_what_if_and_copilot_endpoints() -> None:
    test_client = client()
    explain_resp = test_client.post(
        "/v2/customers/explain",
        json={"records": [valid_record()], "budget_fraction": 0.5, "language": "en"},
    )
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert explain_data["cohort_summary"]["total_customers"] == 1
    assert explain_data["customers"][0]["customer_id"] == "7590-VHVEG"

    whatif_resp = test_client.post(
        "/v2/customers/what-if",
        json={
            "record": valid_record(),
            "overrides": {"Contract": "One year", "TechSupport": "Yes"},
            "language": "en",
        },
    )
    assert whatif_resp.status_code == 200
    assert "delta" in whatif_resp.json()

    ask_resp = test_client.post(
        "/v2/ai/ask",
        json={"question": "Why was Logistic Regression retained over CatBoost?", "language": "en"},
    )
    assert ask_resp.status_code == 200
    assert ask_resp.json()["epistemic_state"] == "OBSERVED"
    assert ask_resp.json()["guardrail_triggered"] is False

    eval_resp = test_client.get("/v2/ai/evaluation")
    assert eval_resp.status_code == 200
    assert eval_resp.json()["gate_passed"] is True
