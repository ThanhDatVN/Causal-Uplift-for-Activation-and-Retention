"""FastAPI application for schema-validated churn scoring and campaign previews."""

from __future__ import annotations

import math
import os
from hashlib import sha256
from numbers import Real
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from telco_churn.allocation import capacity_limit
from telco_churn.assistant import (
    answer_question,
    evaluate_assistant,
    explain_cohort,
    explain_customer,
)
from telco_churn.inference import load_bundle, score_frame
from telco_churn.policy import Scenario, plan_campaign

YesNo = Literal["Yes", "No"]
InternetAddOn = Literal["Yes", "No", "No internet service"]


class CustomerFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    customerID: Annotated[str, Field(min_length=1, max_length=128)]
    gender: Literal["Female", "Male"]
    SeniorCitizen: Literal[0, 1]
    Partner: YesNo
    Dependents: YesNo
    PhoneService: YesNo
    MultipleLines: Literal["Yes", "No", "No phone service"]
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: InternetAddOn
    OnlineBackup: InternetAddOn
    DeviceProtection: InternetAddOn
    TechSupport: InternetAddOn
    StreamingTV: InternetAddOn
    StreamingMovies: InternetAddOn
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: YesNo
    PaymentMethod: Literal[
        "Bank transfer (automatic)",
        "Credit card (automatic)",
        "Electronic check",
        "Mailed check",
    ]
    tenure: Annotated[int, Field(ge=0, le=120)]
    MonthlyCharges: Annotated[float, Field(ge=0, le=10_000)]
    TotalCharges: Annotated[float | None, Field(ge=0, le=1_000_000)] = None
    contact_eligible: bool | None = None
    days_since_last_contact: Annotated[int | None, Field(ge=0)] = None

    @model_validator(mode="after")
    def check_structural_consistency(self) -> CustomerFeatures:
        if self.PhoneService == "No" and self.MultipleLines != "No phone service":
            raise ValueError("MultipleLines must be 'No phone service' when PhoneService is No")
        if self.PhoneService == "Yes" and self.MultipleLines == "No phone service":
            raise ValueError("MultipleLines is inconsistent with PhoneService=Yes")
        internet_fields = (
            self.OnlineSecurity,
            self.OnlineBackup,
            self.DeviceProtection,
            self.TechSupport,
            self.StreamingTV,
            self.StreamingMovies,
        )
        if self.InternetService == "No" and any(
            value != "No internet service" for value in internet_fields
        ):
            raise ValueError("Internet add-ons must be 'No internet service'")
        if self.InternetService != "No" and any(
            value == "No internet service" for value in internet_fields
        ):
            raise ValueError("Internet add-ons are inconsistent with active internet service")
        if self.TotalCharges is None and self.tenure != 0:
            raise ValueError("TotalCharges may be null only for tenure=0")
        return self


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    records: Annotated[list[CustomerFeatures], Field(min_length=1, max_length=1_000)]

    @model_validator(mode="after")
    def unique_customers(self) -> PredictionRequest:
        identifiers = [record.customerID for record in self.records]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("customerID must be unique within a request")
        return self


class ScoreScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: Literal["IBM Telco Customer Churn"]
    label_description: Literal["Churn status in a static public sample"]
    horizon_status: Literal["unvalidated"]
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    training_protocol: str


class PredictionV2Row(BaseModel):
    customer_id: str
    churn_risk_probability: float = Field(ge=0, le=1)


class PredictionV2Response(BaseModel):
    model_version: str
    score_scope: ScoreScope
    predictions: list[PredictionV2Row]


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = "custom"
    save_rate: Annotated[float, Field(ge=0, le=1)] = 0.10
    gross_margin_rate: Annotated[float, Field(ge=0, le=1)] = 0.60
    contact_offer_cost: Annotated[float, Field(ge=0)] = 15.0
    horizon_months: Annotated[int, Field(ge=1, le=60)] = 6


class CampaignPreviewRequest(PredictionRequest):
    budget_fraction: Annotated[float, Field(gt=0, le=1)] = 0.10
    max_total_cost: Annotated[float | None, Field(ge=0)] = None
    cooldown_days: Annotated[int, Field(ge=0, le=365)] = 0
    scenario: ScenarioInput = ScenarioInput()


class ExplainRequest(CampaignPreviewRequest):
    language: Literal["en", "vi"] = "en"


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    baseline: CustomerFeatures | None = None
    counterfactual: CustomerFeatures | None = None
    record: CustomerFeatures | None = None
    overrides: dict[str, object] | None = None
    scenario: ScenarioInput = ScenarioInput()
    language: Literal["en", "vi"] = "en"


class AssistantAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    question: Annotated[str, Field(min_length=1, max_length=1_000)]
    lang: Literal["en", "vi"] | None = None
    language: Literal["en", "vi"] | None = None
    campaign_context: dict | None = None


def _feature_frame(records: list[CustomerFeatures]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            record.model_dump(exclude={"customerID", "contact_eligible", "days_since_last_contact"})
            for record in records
        ]
    )


def _json_rows(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            key: None if isinstance(value, Real) and not math.isfinite(value) else value
            for key, value in row.items()
        }
        for row in frame.to_dict(orient="records")
    ]


def create_app(*, bundle: dict | None = None, model_path: Path | None = None) -> FastAPI:
    application = FastAPI(
        title="TelcoChurn Decision System",
        version="1.0.0",
        description="Portfolio inference API; business value is simulated, not causal.",
    )
    resolved_path = model_path or Path(
        os.getenv("TELCO_MODEL_PATH", "artifacts/models/champion.joblib")
    )
    application.state.bundle = bundle
    application.state.model_error = None
    application.state.model_sha256 = (
        application.state.bundle.get("metadata", {}).get("model_sha256")
        if application.state.bundle is not None
        else None
    )
    if application.state.bundle is None:
        try:
            application.state.bundle = load_bundle(resolved_path)
            application.state.model_sha256 = sha256(resolved_path.read_bytes()).hexdigest()
        except (FileNotFoundError, ValueError) as error:
            application.state.model_error = str(error)

    def require_bundle() -> dict:
        if application.state.bundle is None:
            raise HTTPException(
                status_code=503,
                detail=f"Model is not ready: {application.state.model_error}",
            )
        return application.state.bundle

    def score_scope() -> dict:
        active_bundle = require_bundle()
        digest = application.state.model_sha256
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise HTTPException(status_code=503, detail="Model bundle SHA-256 is unavailable")
        return ScoreScope(
            dataset="IBM Telco Customer Churn",
            label_description="Churn status in a static public sample",
            horizon_status="unvalidated",
            model_sha256=digest,
            training_protocol=str(
                active_bundle["metadata"].get("benchmark_protocol", "not_recorded")
            ),
        ).model_dump()

    @application.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @application.get("/health/ready")
    def ready() -> dict[str, str]:
        require_bundle()
        return {"status": "ready"}

    @application.get("/v1/model-info")
    def model_info() -> dict:
        return require_bundle()["metadata"]

    @application.post("/v1/predict")
    def predict(request: PredictionRequest) -> dict:
        active_bundle = require_bundle()
        scores = score_frame(active_bundle, _feature_frame(request.records))
        version = active_bundle["metadata"]["artifact_version"]
        return {
            "model_version": version,
            "predictions": [
                {"customer_id": record.customerID, "risk_30d": float(score)}
                for record, score in zip(request.records, scores, strict=True)
            ],
        }

    @application.post("/v2/predict", response_model=PredictionV2Response)
    def predict_v2(request: PredictionRequest) -> dict:
        scope = score_scope()
        legacy = predict(request)
        return {
            "model_version": legacy["model_version"],
            "score_scope": scope,
            "predictions": [
                {
                    "customer_id": row["customer_id"],
                    "churn_risk_probability": row["risk_30d"],
                }
                for row in legacy["predictions"]
            ],
        }

    @application.post("/v1/campaigns/preview")
    def campaign_preview(request: CampaignPreviewRequest) -> dict:
        active_bundle = require_bundle()
        scores = score_frame(active_bundle, _feature_frame(request.records))
        scenario = Scenario(**request.scenario.model_dump())
        eligibility = [
            record.contact_eligible is not False
            and (
                request.cooldown_days == 0
                or (
                    record.days_since_last_contact is not None
                    and record.days_since_last_contact >= request.cooldown_days
                )
            )
            for record in request.records
        ]
        plan = plan_campaign(
            [record.customerID for record in request.records],
            scores,
            [record.MonthlyCharges for record in request.records],
            scenario,
            budget_fraction=request.budget_fraction,
            max_total_cost=request.max_total_cost,
            eligible=eligibility,
        )
        exclusion_reasons = {}
        for record in request.records:
            if record.contact_eligible is False:
                exclusion_reasons[record.customerID] = "not_eligible"
            elif request.cooldown_days and record.days_since_last_contact is None:
                exclusion_reasons[record.customerID] = "missing_contact_history"
            elif (
                request.cooldown_days
                and record.days_since_last_contact is not None
                and record.days_since_last_contact < request.cooldown_days
            ):
                exclusion_reasons[record.customerID] = "cooldown_active"
        plan["reason"] = [
            exclusion_reasons.get(customer_id, reason)
            for customer_id, reason in zip(plan["customer_id"], plan["reason"], strict=True)
        ]
        sensitivity = []
        for label, save_rate in (
            ("lower", max(0.0, scenario.save_rate - 0.05)),
            ("current", scenario.save_rate),
            ("higher", min(1.0, scenario.save_rate + 0.05)),
        ):
            variant = Scenario(
                name=label,
                save_rate=save_rate,
                gross_margin_rate=scenario.gross_margin_rate,
                contact_offer_cost=scenario.contact_offer_cost,
                horizon_months=scenario.horizon_months,
            )
            alternate = plan_campaign(
                [record.customerID for record in request.records],
                scores,
                [record.MonthlyCharges for record in request.records],
                variant,
                budget_fraction=request.budget_fraction,
                max_total_cost=request.max_total_cost,
                eligible=eligibility,
            )
            sensitivity.append(
                {
                    "label": label,
                    "assumed_save_rate": save_rate,
                    "selected_customers": int(alternate["selected"].sum()),
                    "simulated_total_expected_value": float(
                        alternate.loc[alternate["selected"], "simulated_expected_value"].sum()
                    ),
                }
            )
        return {
            "model_version": active_bundle["metadata"]["artifact_version"],
            "model_sha256": application.state.model_sha256,
            "assumption_warning": "Expected value is simulated; it is not measured causal uplift.",
            "score_scope_note": "IBM Telco is a static snapshot; a 30-day horizon is not validated.",
            "evidence_type": "risk_model_with_assumed_offer_response",
            "policy_type": "positive_simulated_value_under_contact_capacity",
            "ranked_candidates": _json_rows(plan),
            "selected": _json_rows(plan[plan["selected"]]),
            "sensitivity": sensitivity,
            "summary": {
                "input_customers": len(plan),
                "selected_customers": int(plan["selected"].sum()),
                "contact_capacity": capacity_limit(len(plan), request.budget_fraction),
                "max_total_cost": request.max_total_cost,
                "cooldown_days": request.cooldown_days,
                "eligibility_flags_supplied": sum(
                    record.contact_eligible is not None for record in request.records
                ),
                "contact_history_supplied": sum(
                    record.days_since_last_contact is not None for record in request.records
                ),
                "assumed_contact_spend": float(plan["selected"].sum())
                * scenario.contact_offer_cost,
                "reason_counts": {
                    reason: int(count) for reason, count in plan["reason"].value_counts().items()
                },
                "simulated_total_expected_value": float(
                    plan.loc[plan["selected"], "simulated_expected_value"].sum()
                ),
            },
        }

    @application.post("/v2/campaigns/preview")
    def campaign_preview_v2(request: CampaignPreviewRequest) -> dict:
        scope = score_scope()
        result = campaign_preview(request)
        result.pop("score_scope_note")
        result["score_scope"] = scope
        for key in ("ranked_candidates", "selected"):
            for row in result[key]:
                row["churn_risk_probability"] = row.pop("risk_30d")
        return result

    @application.post("/v2/customers/explain")
    def explain_customers_v2(request: ExplainRequest) -> dict:
        active_bundle = require_bundle()
        scope = score_scope()
        preview_payload = campaign_preview_v2(request)
        scenario = Scenario(**request.scenario.model_dump())
        raw_records = [record.model_dump() for record in request.records]
        cohort_result = explain_cohort(
            active_bundle,
            raw_records,
            scenario=scenario,
            ranked_candidates=preview_payload["ranked_candidates"],
            budget_fraction=request.budget_fraction,
            max_total_cost=request.max_total_cost,
            cooldown_days=request.cooldown_days,
            lang=request.language,
        )
        return {
            "model_version": preview_payload["model_version"],
            "score_scope": scope,
            "cohort_summary": cohort_result["cohort_summary"],
            "archetype_counts": cohort_result["cohort_summary"]["archetype_counts"],
            "customers": cohort_result["customers"],
            "explanations": cohort_result["explanations"],
        }

    @application.post("/v2/customers/what-if")
    def customer_what_if_v2(request: WhatIfRequest) -> dict:
        active_bundle = require_bundle()
        scope = score_scope()
        scenario = Scenario(**request.scenario.model_dump())
        base_model = request.baseline or request.record
        if base_model is None:
            raise HTTPException(status_code=422, detail="Either baseline or record is required")
        base_dict = base_model.model_dump()
        if request.counterfactual is not None:
            cf_dict = request.counterfactual.model_dump()
        else:
            cf_dict = dict(base_dict)
            for key, val in (request.overrides or {}).items():
                if key in cf_dict and val is not None:
                    cf_dict[key] = val
        base_ex = explain_customer(
            active_bundle,
            base_dict,
            scenario=scenario,
            selected=True,
            rank=1,
            reason="selected",
            lang=request.language,
        )
        cf_ex = explain_customer(
            active_bundle,
            cf_dict,
            scenario=scenario,
            selected=True,
            rank=1,
            reason="selected",
            lang=request.language,
        )
        risk_delta = round(
            cf_ex["churn_risk_probability"] - base_ex["churn_risk_probability"],
            4,
        )
        risk_delta_pp = round(risk_delta * 100.0, 2)
        ev_delta = round(
            cf_ex["simulated_expected_value"] - base_ex["simulated_expected_value"],
            2,
        )
        return {
            "customer_id": base_ex["customer_id"],
            "model_version": active_bundle["metadata"]["artifact_version"],
            "score_scope": scope,
            "epistemic_label": "OBSERVATIONAL_MODEL_COUNTERFACTUAL",
            "baseline": base_ex,
            "counterfactual": cf_ex,
            "delta": {
                "risk_delta": risk_delta,
                "churn_risk_pp": risk_delta_pp,
                "expected_value_delta": ev_delta,
                "simulated_expected_value": ev_delta,
                "risk_reduced": risk_delta_pp < 0,
            },
        }

    @application.post("/v2/ai/ask")
    def ai_ask_v2(request: AssistantAskRequest) -> dict:
        return answer_question(
            request.question,
            lang=request.lang or request.language,
            campaign_context=request.campaign_context,
        )

    @application.get("/v2/ai/evaluation")
    def ai_evaluation_v2() -> dict:
        return evaluate_assistant(".")

    planner_dir = Path(__file__).parent / "planner"
    application.mount("/planner", StaticFiles(directory=planner_dir, html=True), name="planner")

    @application.get("/", include_in_schema=False)
    def planner_home() -> RedirectResponse:
        return RedirectResponse(url="/planner/")

    return application


app = create_app()
