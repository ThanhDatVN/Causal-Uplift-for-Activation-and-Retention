from __future__ import annotations

from pathlib import Path

from telco_churn.assistant import (
    SENSITIVE_ATTRIBUTES,
    GroundedEvidenceAssistant,
    answer_question,
    evaluate_assistant,
    explain_cohort,
    explain_customer,
)
from telco_churn.inference import load_bundle
from telco_churn.policy import Scenario


def _sample_records() -> list[dict]:
    return [
        {
            "customerID": "CUST-HIGH-01",
            "gender": "Female",
            "SeniorCitizen": 1,
            "Partner": "No",
            "Dependents": "No",
            "PhoneService": "Yes",
            "MultipleLines": "No",
            "InternetService": "Fiber optic",
            "OnlineSecurity": "No",
            "OnlineBackup": "No",
            "DeviceProtection": "No",
            "TechSupport": "No",
            "StreamingTV": "Yes",
            "StreamingMovies": "Yes",
            "Contract": "Month-to-month",
            "PaperlessBilling": "Yes",
            "PaymentMethod": "Electronic check",
            "tenure": 2,
            "MonthlyCharges": 105.5,
            "TotalCharges": 211.0,
            "contact_eligible": True,
            "days_since_last_contact": 60,
        },
        {
            "customerID": "CUST-LOW-02",
            "gender": "Male",
            "SeniorCitizen": 0,
            "Partner": "Yes",
            "Dependents": "Yes",
            "PhoneService": "Yes",
            "MultipleLines": "Yes",
            "InternetService": "DSL",
            "OnlineSecurity": "Yes",
            "OnlineBackup": "Yes",
            "DeviceProtection": "Yes",
            "TechSupport": "Yes",
            "StreamingTV": "No",
            "StreamingMovies": "No",
            "Contract": "Two year",
            "PaperlessBilling": "No",
            "PaymentMethod": "Bank transfer (automatic)",
            "tenure": 58,
            "MonthlyCharges": 64.0,
            "TotalCharges": 3712.0,
            "contact_eligible": True,
            "days_since_last_contact": 120,
        },
    ]


def test_explain_customer_excludes_sensitive_attributes_and_computes_levers() -> None:
    bundle = load_bundle("artifacts/models/champion.joblib")
    records = _sample_records()
    scenario = Scenario(
        name="unit_test",
        save_rate=0.15,
        gross_margin_rate=0.60,
        contact_offer_cost=15.0,
        horizon_months=6,
    )
    explanation = explain_customer(records[0], bundle, scenario=scenario, lang="en")
    assert explanation["customer_id"] == "CUST-HIGH-01"
    assert explanation["sensitive_excluded_from_reasons"] is True
    assert 0.0 < explanation["churn_risk_probability"] < 1.0

    driver_features = {item["feature"] for item in explanation["top_risk_drivers"]}
    assert not (driver_features & SENSITIVE_ATTRIBUTES)
    assert "Contract" in driver_features or "InternetService" in driver_features

    assert len(explanation["counterfactual_levers"]) >= 1
    best_lever = explanation["counterfactual_levers"][0]
    assert best_lever["risk_delta"] < 0
    assert best_lever["new_risk_probability"] < explanation["churn_risk_probability"]

    vi_explanation = explain_customer(records[0], bundle, scenario=scenario, lang="vi")
    assert "xác suất rủi ro rời bỏ" in vi_explanation["narrative"]


def test_explain_cohort_summarizes_archetypes() -> None:
    bundle = load_bundle("artifacts/models/champion.joblib")
    records = _sample_records()
    result = explain_cohort(
        records,
        bundle,
        budget_fraction=0.5,
        max_total_cost=100.0,
        cooldown_days=7,
        lang="en",
    )
    assert result["cohort_summary"]["total_customers"] == 2
    assert len(result["customers"]) == 2
    assert sum(result["cohort_summary"]["archetype_counts"].values()) == 2


def test_grounded_assistant_answers_and_enforces_guardrails() -> None:
    root = Path(".")
    assistant = GroundedEvidenceAssistant(root)

    factual = assistant.ask(
        "How do causal uplift learners M03-M08 compare to M01 on Hillstrom vs Lenta?",
        lang="en",
    )
    assert factual["epistemic_state"] == "OBSERVED"
    assert factual["guardrail_triggered"] is False
    assert factual["topic_id"] == "KB_HILLSTROM_LENTA"
    assert any("external_replication" in c["path"] for c in factual["citations"])
    assert all(c["sha256_prefix"] is not None for c in factual["citations"] if c["exists"])

    overclaim = assistant.ask(
        "Prove that our IBM Telco model delivers measured ROI and causal uplift for offers.",
        lang="en",
    )
    assert overclaim["epistemic_state"] == "REFUSED_OVERCLAIM"
    assert overclaim["guardrail_triggered"] is True

    missing = assistant.ask(
        "What is the measured SMS uplift on our live production CRM database?",
        lang="en",
    )
    assert missing["epistemic_state"] == "MISSING_EVIDENCE"
    assert missing["guardrail_triggered"] is True

    live_draft = answer_question(
        "Summarize the current campaign draft and selected customers.",
        root=root,
        campaign_context={
            "summary": {
                "input_customers": 8,
                "selected_customers": 1,
                "contact_capacity": 1,
                "simulated_total_expected_value": 24.5,
                "assumed_contact_spend": 15.0,
            },
            "selected": [{"customer_id": "DEMO-01"}],
        },
        lang="vi",
    )
    assert live_draft["epistemic_state"] == "SIMULATED"
    assert live_draft["topic_id"] == "LIVE_CAMPAIGN_DRAFT"
    assert "DEMO-01" in live_draft["answer"]


def test_x09_evaluation_benchmark_passes_all_cases() -> None:
    report = evaluate_assistant(Path("."))
    assert report["study"] == "X09_GROUNDED_EVIDENCE_ASSISTANT"
    assert report["total_questions"] == 12
    assert report["passed_questions"] == 12
    assert report["overclaim_rate"] == 0.0
    assert report["gate_passed"] is True


def test_api_and_dashboard_routes_direct_invocation() -> None:
    from telco_churn.api import (
        AssistantAskRequest,
        CustomerFeatures,
        ExplainRequest,
        WhatIfRequest,
        create_app,
    )
    from telco_churn.dashboard import ConsoleAskRequest, create_dashboard

    api_app = create_app()
    api_routes = {getattr(r, "path", None): getattr(r, "endpoint", None) for r in api_app.routes}
    records = [CustomerFeatures(**r) for r in _sample_records()]

    explain_out = api_routes["/v2/customers/explain"](
        ExplainRequest(records=records, budget_fraction=0.5, language="vi")
    )
    assert explain_out["cohort_summary"]["total_customers"] == 2
    assert len(explain_out["customers"]) == 2

    whatif_out = api_routes["/v2/customers/what-if"](
        WhatIfRequest(
            record=records[0],
            overrides={"Contract": "One year", "TechSupport": "Yes"},
            language="en",
        )
    )
    assert whatif_out["delta"]["risk_reduced"] is True

    ask_out = api_routes["/v2/ai/ask"](
        AssistantAskRequest(
            question="Why was Logistic Regression retained over CatBoost?",
            language="en",
        )
    )
    assert ask_out["epistemic_state"] == "OBSERVED"

    dash_app = create_dashboard(".")
    dash_routes = {getattr(r, "path", None): getattr(r, "endpoint", None) for r in dash_app.routes}
    cd_out = dash_routes["/api/research/cross-domain"]()
    assert len(cd_out["hillstrom_r02"]["candidates"]) == 8
    assert len(cd_out["lenta_r10"]["candidates"]) == 8
    assert len(cd_out["r1_repair"]["cells"]) == 6

    dash_ai_out = dash_routes["/api/ai/ask"](
        ConsoleAskRequest(question="What happened in the R1 prospective repair study?", lang="en")
    )
    assert dash_ai_out["epistemic_state"] == "SYNTHETIC"
