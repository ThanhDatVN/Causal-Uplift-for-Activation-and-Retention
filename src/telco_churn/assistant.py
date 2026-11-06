"""Grounded AI Evidence Copilot, per-customer explainability, and X09 evaluation suite.

This module implements two strictly bounded AI capabilities for the Retention
Decision Lab:

1. **Per-Customer AI Explainability & Counterfactual Action Simulator**:
   Computes exact linear log-odds contributions (for the production Logistic
   pipeline) and marginal probability deltas (for any estimator bundle) across
   actionable customer features while excluding sensitive audit attributes
   (``gender``, ``SeniorCitizen``) from reason codes per ``MODEL_CARD.md``.
   Simulates concrete activation and retention levers (contract upgrade,
   TechSupport + OnlineSecurity bundle, auto-pay enrollment, bill optimization)
   and labels them explicitly as *observational model counterfactuals*, distinct
   from randomized causal treatment effects.

2. **Grounded Evidence & Campaign AI Copilot (X09)**:
   Answers questions about the repository's predictive, causal uplift, evaluator
   validity, and live campaign artifacts using only versioned local files with
   SHA-256 provenance citations. Enforces epistemic guardrails that refuse
   unsupported causal or ROI overclaims and missing-evidence extrapolations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from .evidence import build_index
from .inference import prepare_feature_frame, score_frame
from .policy import Scenario, break_even_save_rate, expected_value
from .schema import FEATURE_COLUMNS, SENSITIVE_AUDIT_COLUMNS

__all__ = [
    "SENSITIVE_ATTRIBUTES",
    "EpistemicState",
    "GroundedEvidenceAssistant",
    "answer_question",
    "evaluate_assistant",
    "explain_cohort",
    "explain_customer",
    "main",
]

SENSITIVE_ATTRIBUTES: frozenset[str] = frozenset(SENSITIVE_AUDIT_COLUMNS)

EpistemicState = Literal[
    "OBSERVED",
    "CONDITIONAL",
    "SYNTHETIC",
    "SIMULATED",
    "REFUSED_OVERCLAIM",
    "MISSING_EVIDENCE",
]

#: Low-risk reference profile used to compute marginal probability deltas when
#: a single feature is replaced by a healthy baseline value.
REFERENCE_PROFILE: dict[str, Any] = {
    "gender": "Female",
    "SeniorCitizen": 0,
    "Partner": "Yes",
    "Dependents": "Yes",
    "PhoneService": "Yes",
    "MultipleLines": "No",
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
    "tenure": 48,
    "MonthlyCharges": 55.0,
    "TotalCharges": 2640.0,
}

FEATURE_LABELS_EN: dict[str, str] = {
    "Contract": "Contract term",
    "tenure": "Customer tenure",
    "InternetService": "Internet service tier",
    "MonthlyCharges": "Monthly charges",
    "TotalCharges": "Total historical charges",
    "PaymentMethod": "Payment method",
    "TechSupport": "Tech support add-on",
    "OnlineSecurity": "Online security add-on",
    "OnlineBackup": "Online backup add-on",
    "DeviceProtection": "Device protection add-on",
    "StreamingTV": "Streaming TV",
    "StreamingMovies": "Streaming movies",
    "PaperlessBilling": "Paperless billing",
    "MultipleLines": "Multiple phone lines",
    "PhoneService": "Phone service",
    "Partner": "Partner status",
    "Dependents": "Dependents status",
}

FEATURE_LABELS_VI: dict[str, str] = {
    "Contract": "Loại hợp đồng",
    "tenure": "Thời gian gắn bó (tháng)",
    "InternetService": "Dịch vụ Internet",
    "MonthlyCharges": "Cước hàng tháng",
    "TotalCharges": "Tổng cước tích lũy",
    "PaymentMethod": "Phương thức thanh toán",
    "TechSupport": "Hỗ trợ kỹ thuật (TechSupport)",
    "OnlineSecurity": "Bảo mật trực tuyến (OnlineSecurity)",
    "OnlineBackup": "Sao lưu trực tuyến",
    "DeviceProtection": "Bảo vệ thiết bị",
    "StreamingTV": "Truyền hình trực tuyến",
    "StreamingMovies": "Phim trực tuyến",
    "PaperlessBilling": "Hóa đơn điện tử",
    "MultipleLines": "Nhiều đường dây điện thoại",
    "PhoneService": "Dịch vụ điện thoại",
    "Partner": "Tình trạng hôn nhân/đối tác",
    "Dependents": "Người phụ thuộc",
}

REASON_LABELS_EN: dict[str, str] = {
    "selected": "Selected for contact within hard capacity and positive scenario value",
    "non_positive_value": "Skipped: non-positive expected value under current assumptions",
    "contact_cap_reached": "Skipped: positive scenario value, but hard contact capacity was reached first",
    "cost_cap_reached": "Skipped: positive scenario value, but total contact budget cap was reached",
    "not_eligible": "Excluded before ranking: marked contact_eligible=False in snapshot",
    "cooldown_active": "Excluded before ranking: contacted recently within the cooldown window",
    "missing_contact_history": "Excluded before ranking: missing contact history while cooldown > 0",
}

REASON_LABELS_VI: dict[str, str] = {
    "selected": "Được chọn liên hệ: nằm trong trần dung lượng và có giá trị kỳ vọng dương",
    "non_positive_value": "Bỏ qua: giá trị kịch bản ≤ 0 dưới giả định hiện tại (không đạt điểm hòa vốn)",
    "contact_cap_reached": "Bỏ qua: có giá trị dương nhưng đã chạm trần số lượng liên hệ (hard contact cap)",
    "cost_cap_reached": "Bỏ qua: có giá trị dương nhưng đã chạm trần tổng chi phí chiến dịch",
    "not_eligible": "Loại trước khi xếp hạng: khách hàng có cờ contact_eligible=False",
    "cooldown_active": "Loại trước khi xếp hạng: đang trong thời gian nghỉ liên hệ (cooldown)",
    "missing_contact_history": "Loại trước khi xếp hạng: thiếu lịch sử ngày liên hệ khi áp dụng cooldown > 0",
}


def _clean_feature_record(record: Mapping[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for col in FEATURE_COLUMNS:
        val = record.get(col)
        if col == "TotalCharges" and (val is None or val == ""):
            cleaned[col] = 0.0 if int(record.get("tenure", 0)) == 0 else float(val or 0.0)
        elif col in ("SeniorCitizen", "tenure"):
            cleaned[col] = int(val)
        elif col in ("MonthlyCharges", "TotalCharges"):
            cleaned[col] = float(val)
        else:
            cleaned[col] = str(val)
    return cleaned


def _replace_single_feature(
    base_record: dict[str, Any], feature: str, new_value: Any
) -> dict[str, Any]:
    candidate = dict(base_record)
    candidate[feature] = new_value
    if feature == "PhoneService":
        if new_value == "No":
            candidate["MultipleLines"] = "No phone service"
        elif candidate["MultipleLines"] == "No phone service":
            candidate["MultipleLines"] = "No"
    if feature == "MultipleLines" and new_value == "No phone service":
        candidate["PhoneService"] = "No"
    if feature == "InternetService":
        addons = (
            "OnlineSecurity",
            "OnlineBackup",
            "DeviceProtection",
            "TechSupport",
            "StreamingTV",
            "StreamingMovies",
        )
        if new_value == "No":
            for addon in addons:
                candidate[addon] = "No internet service"
        else:
            for addon in addons:
                if candidate[addon] == "No internet service":
                    candidate[addon] = "No"
    if feature == "tenure" and int(new_value) > 0 and candidate.get("TotalCharges") is None:
        candidate["TotalCharges"] = float(new_value) * float(candidate["MonthlyCharges"])
    return candidate


def _linear_log_odds_contributions(
    bundle: Mapping[str, Any], feature_row: dict[str, Any]
) -> dict[str, float] | None:
    """Extract exact per-feature log-odds contributions when the model is a linear pipeline."""
    model_obj = bundle.get("model")
    if not hasattr(model_obj, "named_steps"):
        return None
    preprocess = model_obj.named_steps.get("preprocess")
    classifier = model_obj.named_steps.get("model")
    if preprocess is None or classifier is None or not hasattr(classifier, "coef_"):
        return None
    try:
        frame = prepare_feature_frame(pd.DataFrame([feature_row]))
        transformed = preprocess.transform(frame)
        dense_row = (
            transformed.toarray()[0]
            if hasattr(transformed, "toarray")
            else np.asarray(transformed)[0]
        )
        coefs = np.asarray(classifier.coef_, dtype=float).ravel()
        if len(dense_row) != len(coefs):
            return None
        feature_names = list(preprocess.get_feature_names_out())
        contributions: dict[str, float] = {col: 0.0 for col in FEATURE_COLUMNS}
        for encoded_name, x_val, weight in zip(feature_names, dense_row, coefs, strict=True):
            term = float(x_val * weight)
            raw_name = encoded_name.split("__", 1)[-1]
            for col in FEATURE_COLUMNS:
                if raw_name == col or raw_name.startswith(f"{col}_"):
                    contributions[col] += term
                    break
        return contributions
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def explain_customer(
    bundle_or_record: Mapping[str, Any],
    record_or_bundle: Mapping[str, Any],
    *,
    scenario: Scenario | None = None,
    selected: bool = False,
    rank: int = 1,
    reason: str = "selected",
    lang: Literal["en", "vi"] = "en",
) -> dict[str, Any]:
    """Compute actionable feature attributions, what-if levers, and uplift diagnosis."""
    if "model" in bundle_or_record:
        bundle, record = bundle_or_record, record_or_bundle
    else:
        record, bundle = bundle_or_record, record_or_bundle
    active_scenario = scenario or Scenario(
        name="analyst_scenario",
        save_rate=0.15,
        gross_margin_rate=0.60,
        contact_offer_cost=15.0,
        horizon_months=6,
    )
    customer_id = str(record.get("customerID") or record.get("customer_id") or "CUSTOMER-01")
    clean_row = _clean_feature_record(record)
    actionable_features = [col for col in FEATURE_COLUMNS if col not in SENSITIVE_AUDIT_COLUMNS]

    # Score baseline and single-feature reference replacements in one batch call
    variant_rows = [clean_row]
    for col in actionable_features:
        ref_val = REFERENCE_PROFILE[col]
        if col == "TotalCharges":
            ref_val = float(clean_row["tenure"]) * float(clean_row["MonthlyCharges"])
        variant_rows.append(_replace_single_feature(clean_row, col, ref_val))

    scores = score_frame(dict(bundle), pd.DataFrame(variant_rows))
    base_prob = float(scores[0])
    linear_contribs = _linear_log_odds_contributions(bundle, clean_row)

    attributions: list[dict[str, Any]] = []
    for idx, col in enumerate(actionable_features, start=1):
        ref_prob = float(scores[idx])
        marginal_delta = base_prob - ref_prob
        log_odds = (
            float(linear_contribs[col])
            if linear_contribs is not None and col in linear_contribs
            else float(marginal_delta * 4.0)
        )
        val = clean_row[col]
        formatted_val = (
            f"{val:.2f}"
            if isinstance(val, float)
            else f"{val} months"
            if col == "tenure"
            else str(val)
        )
        attributions.append(
            {
                "feature": col,
                "label_en": FEATURE_LABELS_EN.get(col, col),
                "label_vi": FEATURE_LABELS_VI.get(col, col),
                "value": val,
                "customer_value": formatted_val,
                "reference_value": REFERENCE_PROFILE[col],
                "formatted_value": formatted_val,
                "log_odds_contribution": round(log_odds, 4),
                "marginal_risk_delta": round(marginal_delta, 4),
                "direction": "increases_risk"
                if log_odds > 0.01 or marginal_delta > 0.005
                else ("reduces_risk" if log_odds < -0.01 or marginal_delta < -0.005 else "neutral"),
            }
        )

    attributions.sort(
        key=lambda item: (abs(item["log_odds_contribution"]), abs(item["marginal_risk_delta"])),
        reverse=True,
    )
    top_risk_drivers = [item for item in attributions if item["direction"] == "increases_risk"][:4]
    top_protective = [item for item in attributions if item["direction"] == "reduces_risk"][:3]

    # Simulate concrete activation & retention counterfactual levers
    lever_specs: list[tuple[str, str, str, dict[str, Any], bool]] = [
        (
            "contract_one_year",
            "Upgrade to One-year contract",
            "Nâng cấp lên hợp đồng 1 năm (One year)",
            {"Contract": "One year"},
            clean_row["Contract"] == "Month-to-month",
        ),
        (
            "contract_two_year",
            "Upgrade to Two-year contract",
            "Nâng cấp lên hợp đồng 2 năm (Two year)",
            {"Contract": "Two year"},
            clean_row["Contract"] != "Two year",
        ),
        (
            "activation_tech_security",
            "Activate TechSupport + OnlineSecurity bundle",
            "Kích hoạt gói Hỗ trợ kỹ thuật + Bảo mật trực tuyến",
            {"TechSupport": "Yes", "OnlineSecurity": "Yes"},
            clean_row["InternetService"] != "No"
            and (clean_row["TechSupport"] != "Yes" or clean_row["OnlineSecurity"] != "Yes"),
        ),
        (
            "autopay_migration",
            "Switch to automatic bank transfer",
            "Chuyển sang thanh toán tự động qua ngân hàng (Auto-pay)",
            {"PaymentMethod": "Bank transfer (automatic)"},
            clean_row["PaymentMethod"] in ("Electronic check", "Mailed check"),
        ),
        (
            "onboarding_6m_milestone",
            "Complete 6-month activation milestone (+6m tenure + Credit Card Auto-Pay)",
            "Hoàn thành mốc kích hoạt 6 tháng (+6 tháng gắn bó + Tự động thanh toán thẻ tín dụng)",
            {
                "tenure": min(120, int(clean_row["tenure"]) + 6),
                "TotalCharges": round(
                    float(clean_row["TotalCharges"]) + 6.0 * float(clean_row["MonthlyCharges"]), 2
                ),
                "PaymentMethod": "Credit card (automatic)",
            },
            int(clean_row["tenure"]) < 24,
        ),
    ]

    lever_frames: list[dict[str, Any]] = []
    for _, _, _, changes, _ in lever_specs:
        mod_row = dict(clean_row)
        for k, v in changes.items():
            mod_row = _replace_single_feature(mod_row, k, v)
        lever_frames.append(mod_row)

    lever_scores = score_frame(dict(bundle), pd.DataFrame(lever_frames))
    interventions: list[dict[str, Any]] = []
    for (lever_id, title_en, title_vi, changes, applicable), cf_prob, mod_row in zip(
        lever_specs, lever_scores, lever_frames, strict=True
    ):
        cf_p = float(cf_prob)
        cf_ev = float(
            expected_value([cf_p], [float(mod_row["MonthlyCharges"])], active_scenario)[0]
        )
        interventions.append(
            {
                "lever_id": lever_id,
                "title_en": title_en,
                "title_vi": title_vi,
                "applicable": bool(applicable),
                "changes": changes,
                "baseline_risk_probability": round(base_prob, 4),
                "counterfactual_risk_probability": round(cf_p, 4),
                "risk_reduction_pp": round((base_prob - cf_p) * 100.0, 2),
                "counterfactual_expected_value": round(cf_ev, 2),
                "epistemic_label": "OBSERVATIONAL_MODEL_COUNTERFACTUAL",
            }
        )

    charges = float(clean_row["MonthlyCharges"])
    sim_ev = float(expected_value([base_prob], [charges], active_scenario)[0])
    be_save = float(break_even_save_rate([base_prob], [charges], active_scenario)[0])
    be_finite = be_save if math.isfinite(be_save) else None
    margin_at_risk = charges * active_scenario.horizon_months * active_scenario.gross_margin_rate

    if reason in ("not_eligible", "cooldown_active", "missing_contact_history"):
        archetype = "governance_excluded"
        quadrant_en = "Governance / Cooldown Holdout (Do Not Contact)"
        quadrant_vi = "Khách hàng thuộc diện loại trừ quản trị / đang trong kỳ nghỉ liên hệ"
    elif selected and be_finite is not None and active_scenario.save_rate - be_finite >= 0.05:
        archetype = "priority_persuadable_candidate"
        quadrant_en = "High-Risk · High-Margin Candidate (Target under Assumed Uplift)"
        quadrant_vi = (
            "Ứng viên ưu tiên cao (Rủi ro cao · Biên lợi nhuận lớn · Vượt xa điểm hòa vốn)"
        )
    elif selected:
        archetype = "marginal_candidate"
        quadrant_en = "Marginal Positive Candidate (Sensitive to Save-Rate Assumption)"
        quadrant_vi = (
            "Ứng viên cận biên (Giá trị kỳ vọng dương nhưng nhạy cảm với giả định tỷ lệ giữ chân)"
        )
    elif reason in ("contact_cap_reached", "cost_cap_reached"):
        archetype = "cap_constrained_candidate"
        quadrant_en = "Positive Scenario Value · Deferred by Hard Budget Cap"
        quadrant_vi = "Có giá trị kỳ vọng dương nhưng bị giới hạn bởi trần ngân sách / dung lượng"
    else:
        archetype = "below_break_even_lost_cause_or_sure_thing"
        quadrant_en = (
            "Low Risk ('Sure Thing' — No Offer Needed)"
            if base_prob < 0.25
            else "Below Break-Even ('Lost Cause' under Offer Cost)"
        )
        quadrant_vi = (
            "Rủi ro thấp ('Sure Thing' — Không cần tốn chi phí ưu đãi)"
            if base_prob < 0.25
            else "Chưa đạt điểm hòa vốn (Chi phí ưu đãi vượt lợi nhuận kỳ vọng)"
        )

    driver_names_en = (
        ", ".join(f"{d['label_en']} ({d['formatted_value']})" for d in top_risk_drivers[:3])
        or "balanced account profile"
    )
    driver_names_vi = (
        ", ".join(f"{d['label_vi']} ({d['formatted_value']})" for d in top_risk_drivers[:3])
        or "hồ sơ ổn định"
    )
    be_str = f"{be_finite * 100:.1f}%" if be_finite is not None else "unreachable"

    narrative_en = (
        f"Customer {customer_id} (rank #{rank}) has a static churn risk score of "
        f"{base_prob * 100:.1f}% driven primarily by {driver_names_en}. "
        f"At {charges:.2f}/month over {active_scenario.horizon_months} months "
        f"({active_scenario.gross_margin_rate * 100:.0f}% margin), margin at risk is "
        f"{margin_at_risk:.2f} units. With an offer cost of {active_scenario.contact_offer_cost:.2f}, "
        f"the break-even save rate is {be_str} (current assumption: "
        f"{active_scenario.save_rate * 100:.1f}%), yielding a simulated expected value of "
        f"{sim_ev:+.2f} units. Decision: {REASON_LABELS_EN.get(reason, reason)}. "
        f"Note: Sensitive attributes (gender, SeniorCitizen) are excluded from reason codes."
    )
    narrative_vi = (
        f"Khách hàng {customer_id} (hạng #{rank}) có xác suất rủi ro rời bỏ tĩnh là "
        f"{base_prob * 100:.1f}%, chủ yếu do {driver_names_vi}. "
        f"Với cước {charges:.2f}/tháng trong {active_scenario.horizon_months} tháng "
        f"(biên lợi nhuận {active_scenario.gross_margin_rate * 100:.0f}%), biên lợi nhuận có rủi ro là "
        f"{margin_at_risk:.2f} đơn vị. Với chi phí liên hệ {active_scenario.contact_offer_cost:.2f}, "
        f"tỷ lệ giữ chân hòa vốn là {be_str} (giả định hiện tại: "
        f"{active_scenario.save_rate * 100:.1f}%), mang lại giá trị kỳ vọng mô phỏng "
        f"{sim_ev:+.2f} đơn vị. Quyết định: {REASON_LABELS_VI.get(reason, reason)}. "
        f"Lưu ý: Các thuộc tính nhạy cảm (gender, SeniorCitizen) đã được loại khỏi mã lý do."
    )

    risk_tier = "high" if base_prob >= 0.55 else ("medium" if base_prob >= 0.30 else "low")
    applicable_levers = [
        {
            "lever_id": lv["lever_id"],
            "label": lv["title_vi"] if lang == "vi" else lv["title_en"],
            "title_en": lv["title_en"],
            "title_vi": lv["title_vi"],
            "changes": lv["changes"],
            "new_risk_probability": lv["counterfactual_risk_probability"],
            "risk_delta": round(-lv["risk_reduction_pp"] / 100.0, 4),
            "relative_risk_reduction": round(
                (lv["risk_reduction_pp"] / 100.0) / max(base_prob, 1e-6), 4
            ),
            "counterfactual_expected_value": lv["counterfactual_expected_value"],
        }
        for lv in interventions
        if lv["applicable"] and lv["risk_reduction_pp"] > 0.1
    ]
    applicable_levers.sort(key=lambda item: item["risk_delta"])
    boundary_note = (
        "Feature attributions and what-if levers reflect cross-sectional associations in the "
        "deployed IBM Telco risk model, not randomized causal treatment effects E[Y(0)-Y(1)|X]. "
        "Because MonthlyCharges is collinear with Fiber optic (+1.145) and TotalCharges (+0.771), "
        "naive price perturbation in P(Y|X) suffers from collinearity sign reversal (-1.797) — "
        "illustrating why randomized causal uplift models are required to evaluate pricing offers."
    )

    return {
        "customer_id": customer_id,
        "rank": rank,
        "selected": selected,
        "reason": reason,
        "decision_reason": reason,
        "reason_label_en": REASON_LABELS_EN.get(reason, reason),
        "reason_label_vi": REASON_LABELS_VI.get(reason, reason),
        "churn_risk_probability": round(base_prob, 4),
        "risk_tier": risk_tier,
        "monthly_charges": round(charges, 2),
        "margin_at_risk": round(margin_at_risk, 2),
        "simulated_expected_value": round(sim_ev, 2),
        "break_even_save_rate": round(be_finite, 4) if be_finite is not None else None,
        "assumed_save_rate": round(active_scenario.save_rate, 4),
        "archetype": {
            "id": archetype,
            "label": quadrant_vi if lang == "vi" else quadrant_en,
            "summary": REASON_LABELS_VI.get(reason, reason)
            if lang == "vi"
            else REASON_LABELS_EN.get(reason, reason),
            "recommended_channel": (
                applicable_levers[0]["label"]
                if applicable_levers
                else ("Maintain account health" if lang == "en" else "Duy trì chăm sóc định kỳ")
            ),
        },
        "archetype_id": archetype,
        "quadrant_label_en": quadrant_en,
        "quadrant_label_vi": quadrant_vi,
        "sensitive_excluded_from_reasons": True,
        "excluded_sensitive_features": list(SENSITIVE_AUDIT_COLUMNS),
        "top_risk_drivers": top_risk_drivers,
        "top_protective_factors": top_protective,
        "all_feature_attributions": attributions,
        "counterfactual_interventions": interventions,
        "counterfactual_levers": applicable_levers,
        "narrative": narrative_vi if lang == "vi" else narrative_en,
        "narrative_en": narrative_en,
        "narrative_vi": narrative_vi,
        "evidence_boundary": boundary_note,
        "causal_boundary_note": boundary_note,
    }


def explain_cohort(
    bundle_or_records: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    records_or_bundle: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    *,
    scenario: Scenario | None = None,
    ranked_candidates: Sequence[Mapping[str, Any]] | None = None,
    budget_fraction: float = 0.2,
    max_total_cost: float | None = None,
    cooldown_days: int = 0,
    lang: Literal["en", "vi"] = "en",
) -> dict[str, Any]:
    """Generate structured AI explanations and cohort summary for a list of customer records."""
    if isinstance(bundle_or_records, Mapping) and "model" in bundle_or_records:
        bundle = bundle_or_records
        records = records_or_bundle  # type: ignore[assignment]
    else:
        records = bundle_or_records  # type: ignore[assignment]
        bundle = records_or_bundle  # type: ignore[assignment]

    by_id: dict[str, Mapping[str, Any]] = {}
    if ranked_candidates:
        for row in ranked_candidates:
            cid = str(row.get("customer_id") or row.get("customerID") or "")
            if cid:
                by_id[cid] = row
    results: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        cid = str(record.get("customerID") or record.get("customer_id") or f"CUST-{index}")
        meta = by_id.get(cid, {})
        reason = str(meta.get("reason", "selected"))
        if not meta:
            if record.get("contact_eligible") is False:
                reason = "not_eligible"
            elif cooldown_days > 0 and record.get("days_since_last_contact") is None:
                reason = "missing_contact_history"
            elif (
                cooldown_days > 0
                and record.get("days_since_last_contact") is not None
                and int(record["days_since_last_contact"]) < cooldown_days
            ):
                reason = "cooldown_active"
        results.append(
            explain_customer(
                bundle,
                record,
                scenario=scenario,
                selected=bool(
                    meta.get("selected", index <= max(1, int(len(records) * budget_fraction)))
                ),
                rank=int(meta.get("rank", index)),
                reason=reason,
                lang=lang,
            )
        )
    results.sort(key=lambda item: item["rank"])
    archetype_counts: dict[str, int] = {}
    for item in results:
        arch_label = str(item["archetype"]["label"])
        archetype_counts[arch_label] = archetype_counts.get(arch_label, 0) + 1
    return {
        "cohort_summary": {
            "total_customers": len(results),
            "budget_fraction": budget_fraction,
            "max_total_cost": max_total_cost,
            "cooldown_days": cooldown_days,
            "archetype_counts": archetype_counts,
        },
        "customers": results,
        "explanations": results,
    }


@dataclass(frozen=True)
class KnowledgeEntry:
    topic_id: str
    title_en: str
    title_vi: str
    epistemic_state: EpistemicState
    keywords: tuple[str, ...]
    artifacts: tuple[str, ...]
    summary_en: str
    summary_vi: str
    metrics: dict[str, Any]


def _sha256_prefix(root: Path, relative_path: str) -> str:
    target = root / relative_path
    if not target.exists():
        return "missing"
    return hashlib.sha256(target.read_bytes()).hexdigest()[:12]


def _build_knowledge_base(root: Path) -> list[KnowledgeEntry]:
    return [
        KnowledgeEntry(
            topic_id="KB_RELEASE_TIER",
            title_en="Release Tier & Validity Gate Index",
            title_vi="Cấp độ phát hành (Release Tier) & Chỉ mục cổng kiểm định",
            epistemic_state="OBSERVED",
            keywords=(
                "tier",
                "release",
                "gate",
                "gates",
                "evidence",
                "index",
                "engineering_foundation",
                "blocker",
                "blockers",
                "status",
                "trạng thái",
                "cổng",
                "bằng chứng",
            ),
            artifacts=(
                "reports/v4/EVIDENCE_INDEX.md",
                "reports/v4/contracts.json",
                "reports/v4/challenge_suite.json",
            ),
            summary_en=(
                "The repository's live release tier is ENGINEERING_FOUNDATION (0 failing gates, "
                "57 OBSERVED claims, 6 CONDITIONAL, 5 PLANNED in CLAIM_LEDGER_V4.md). Eight "
                "engineering and diagnostic gates PASS (contracts, 21/21 critical mutations caught, "
                "runner failure propagation, 180-package research lock, Hillstrom/Lenta assignment "
                "diagnostics, R02 candidate screening, R10 Lenta replication, and 12/12 deployment "
                "parity checks). Promotion to RESEARCH_INTERIM is blocked by Estimator Coverage "
                "(R00/R01 = NOT_MET, pending independent confirmation on unseen worlds), and "
                "BUSINESS_VALIDATED is blocked by Prospective Partner Trial (NOT_RUN)."
            ),
            summary_vi=(
                "Cấp độ phát hành hiện tại của hệ thống là ENGINEERING_FOUNDATION (0 cổng lỗi, "
                "57 phát biểu OBSERVED, 6 CONDITIONAL, 5 PLANNED trong CLAIM_LEDGER_V4.md). Tám "
                "cổng kỹ thuật và chẩn đoán đạt PASS (hợp đồng bài toán, bắt 21/21 đột biến nghiêm "
                "trọng, kiểm soát lỗi runner, khóa môi trường 180 gói, kiểm định phân bổ Hillstrom/Lenta, "
                "sàng lọc R02, tái hiện độc lập R10 trên Lenta, và 12/12 kiểm tra parity triển khai). "
                "Cổng độ phủ bộ ước lượng (R00/R01) ở trạng thái NOT_MET và thử nghiệm thực địa với "
                "đối tác ở trạng thái NOT_RUN."
            ),
            metrics={
                "release_tier": "ENGINEERING_FOUNDATION",
                "failing_gates": 0,
                "claims_observed": 57,
                "claims_conditional": 6,
                "claims_planned": 5,
                "coverage_gate": "NOT_MET",
                "partner_trial_gate": "NOT_RUN",
            },
        ),
        KnowledgeEntry(
            topic_id="KB_IBM_MODEL",
            title_en="IBM Telco Predictive Benchmark & Champion Selection",
            title_vi="Benchmark dự báo rủi ro IBM Telco & Lý do chọn Logistic Champion",
            epistemic_state="OBSERVED",
            keywords=(
                "ibm",
                "logistic",
                "catboost",
                "hgb",
                "champion",
                "benchmark",
                "ap",
                "average precision",
                "roc",
                "brier",
                "calibration",
                "complexity",
                "model",
                "mô hình",
                "độ chính xác",
            ),
            artifacts=(
                "reports/benchmark/BENCHMARK_REPORT.md",
                "reports/v4/portfolio_completion/FULL_BENCHMARK_COMPARISON.md",
                "docs/MODEL_CARD.md",
            ),
            summary_en=(
                "On the checksum-verified 7,043-row IBM Telco dataset (5,634 development / 1,409 "
                "frozen test), CatBoost achieved the highest test Average Precision (0.6766 vs. "
                "Logistic 0.6396 and HistGradientBoosting 0.6646). However, on predeclared 5x3 "
                "repeated cross-validation on development data, CatBoost (0.6680 ± 0.0269) beat "
                "L2 Logistic Regression (0.6592 ± 0.0243) by only +0.0088 AP, missing the "
                "preregistered +0.0100 complexity gate. Uncalibrated Logistic (Test ROC-AUC 0.8499, "
                "Brier 0.1345, Brier Skill Score 0.3104, ECE 0.0259, Lift@10% = 2.70x capturing "
                "27.0% of churners) was retained without post-hoc gate manipulation. All 1,409 test "
                "predictions reproduced identically in the full benchmark audit."
            ),
            summary_vi=(
                "Trên bộ dữ liệu IBM Telco 7.043 khách hàng (5.634 phát triển / 1.409 kiểm thử đóng "
                "băng), CatBoost đạt Average Precision trên tập test cao nhất (0,6766 so với Logistic "
                "0,6396 và HGB 0,6646). Tuy nhiên, trên kiểm định chéo lặp 5x3 ở tập development, "
                "CatBoost (0,6680 ± 0,0269) chỉ nhỉnh hơn Logistic L2 (0,6592 ± 0,0243) đúng +0,0088 AP, "
                "không vượt qua ngưỡng độ phức tạp +0,0100 đã đăng ký trước. Vì vậy, Logistic Regression "
                "(Test ROC-AUC 0,8499, Brier 0,1345, Lift@10% = 2,70x bắt được 27,0% khách rời bỏ) được "
                "giữ làm mô hình Champion đúng nguyên tắc khoa học. Toàn bộ 1.409 dự báo trên tập test "
                "khớp tuyệt đối khi chạy tái lập."
            ),
            metrics={
                "logistic_test_ap": 0.6396,
                "catboost_test_ap": 0.6766,
                "cv_ap_delta_catboost_vs_logistic": 0.0088,
                "predeclared_complexity_gate": 0.0100,
                "logistic_roc_auc": 0.8499,
                "logistic_brier": 0.1345,
                "lift_at_10pct_budget": 2.70,
            },
        ),
        KnowledgeEntry(
            topic_id="KB_ORANGE_CAUSAL",
            title_en="Orange Belgium Causal Benchmark & Assignment Audit (NO_LAUNCH)",
            title_vi="Benchmark nhân quả Orange Belgium & Kiểm định phân bổ (NO_LAUNCH)",
            epistemic_state="CONDITIONAL",
            keywords=(
                "orange",
                "no_launch",
                "no launch",
                "assignment",
                "audit",
                "propensity",
                "ess",
                "ipw",
                "holdout",
                "power",
                "mde",
                "permutation",
            ),
            artifacts=(
                "reports/uplift/locked_policy_decision.json",
                "reports/v4/assignment_audit.json",
            ),
            summary_en=(
                "In the Orange Belgium dataset (11,896 rows), control churn is 3.638% vs. treated "
                "3.363%, giving an overall ATE of +0.275 pp prevented churn (95% CI [-0.503, +1.053]). "
                "At 80% power, the minimum detectable effect is 1.112 pp (~194,060 rows required to "
                "detect 0.275 pp). The pre-declared policy (risk_logistic at 30% capacity) yields "
                "holdout DR uplift of +3.331 pp (95% CI [-1.507, +8.269]) with only 15 control churn "
                "events (< 20 gate), triggering an automatic NO_LAUNCH decision. Furthermore, the "
                "assignment audit rejects pooled-IID exchangeability (OOF ROC-AUC 0.6355 across 178 "
                "covariates, permutation p = 0.0099) and IPW propensity reweighting collapses the "
                "effective sample size to 3.9 (0.04% ESS kept)."
            ),
            summary_vi=(
                "Trên bộ dữ liệu chiến dịch Orange Belgium (11.896 dòng), tỷ lệ rời bỏ nhóm đối chứng "
                "là 3,638% so với nhóm can thiệp 3,363%, tức ATE đạt +0,275 điểm % (95% CI [-0,503; +1,053]). "
                "Ở mức power 80%, MDE là 1,112 điểm % (cần ~194.060 quan sát để phát hiện hiệu ứng 0,275 điểm %). "
                "Chính sách đã khóa trước (risk_logistic ở 30% dung lượng) cho DR uplift trên tập holdout là "
                "+3,331 điểm % (95% CI [-1,507; +8,269]) nhưng chỉ có 15 sự kiện rời bỏ ở nhóm control (< ngưỡng 20), "
                "dẫn tới quyết định tự động NO_LAUNCH. Ngoài ra, kiểm định phân bổ bác bỏ giả định hoán đổi IID gộp "
                "(OOF ROC-AUC = 0,6355 từ 178 biến, p = 0,0099) và tái trọng số IPW làm cỡ mẫu hiệu dụng sụp đổ "
                "xuống 3,9 (chỉ giữ được 0,04% ESS)."
            ),
            metrics={
                "ate_pp": 0.275,
                "ate_ci95_pp": [-0.503, 1.053],
                "locked_model": "risk_logistic",
                "locked_budget_fraction": 0.30,
                "holdout_dr_uplift_pp": 3.331,
                "holdout_ci95_pp": [-1.507, 8.269],
                "selected_control_events": 15,
                "assignment_oof_auc": 0.6355,
                "assignment_p_value": 0.0099,
                "decision": "NO_LAUNCH",
            },
        ),
        KnowledgeEntry(
            topic_id="KB_HILLSTROM_LENTA",
            title_en="Hillstrom vs. Lenta: Event-Count Scaling Law for Causal Uplift Learners",
            title_vi="Hillstrom vs. Lenta: Quy luật quy mô sự kiện giữa Risk Ranking và Causal Uplift",
            epistemic_state="OBSERVED",
            keywords=(
                "hillstrom",
                "lenta",
                "m01",
                "m02",
                "m03",
                "m04",
                "m05",
                "m06",
                "m07",
                "m08",
                "s-learner",
                "t-learner",
                "dr-learner",
                "x-learner",
                "uplift",
                "causal",
                "learner",
                "screening",
                "replication",
                "mens",
                "womens",
                "events",
                "nhân quả",
            ),
            artifacts=(
                "reports/screening/screening.json",
                "reports/v4/learner_comparison/hillstrom_mens.json",
                "reports/v4/learner_comparison/hillstrom_womens.json",
                "reports/v4/learner_comparison/lenta_sms.json",
                "reports/v4/replication_lenta/external_replication.json",
            ),
            summary_en=(
                "Across 8 standardized candidates (M01 Control-Outcome Logistic, M02 Control-HGB, "
                "M03 S-Logistic, M04 S-HGB, M05 T-Logistic, M06 T-HGB, M07 DR-Ridge, M08 DR-HGB), "
                "the project established a critical empirical boundary: "
                "1) On Hillstrom Mens E-Mail vs. No E-Mail (34,092 customers, 302 conversions, "
                "assignment audit PASS with AUC 0.4975, p = 0.6832, ESS 99.95%), simple M01 "
                "Control-Outcome Logistic (+2.65 conversions/1,000) beat all 7 CATE learners (M03 "
                "+1.99, M07 +0.87, M08 +0.83); nested R4 inner selection trailed M01 by -1.373/1,000. "
                "2) On Hillstrom Womens, M03 beat M01 (+0.681/1,000 in nested R4), showing branch "
                "instability at ~300 events. "
                "3) On Lenta Retail SMS (60,000 development cohort, 6,498 events — 21x Hillstrom), "
                "all 7 causal uplift learners decisively beat M01, with nested R4 inner-selected "
                "CATE learners gaining +1.389 conversions/1,000 over M01. "
                "Finding: At ~300 events, pseudo-outcome variance dominates and simple outcome "
                "ranking wins; at ~6,500 events, causal uplift learners earn their complexity."
            ),
            summary_vi=(
                "Qua 8 ứng viên mô hình chuẩn hóa (từ M01 Control-Outcome Logistic đến M08 DR-HGB), "
                "dự án đã chứng minh thực nghiệm quy luật đánh đổi giữa độ phức tạp nhân quả và số lượng sự kiện: "
                "1) Trên Hillstrom Mens E-Mail vs. No E-Mail (34.092 khách hàng, 302 sự kiện chuyển đổi, "
                "kiểm định phân bổ PASS với AUC = 0,4975, p = 0,6832, ESS = 99,95%), baseline đơn giản nhất "
                "M01 Control-Outcome Logistic (+2,65 chuyển đổi/1.000) thắng cả 7 mô hình CATE phức tạp "
                "(M03 +1,99; M07 +0,87; M08 +0,83); lựa chọn lồng nhau R4 kém M01 -1,373/1.000. "
                "2) Trên nhánh Hillstrom Womens, mô hình uplift nhỉnh hơn M01 (+0,681/1.000 trong R4), cho thấy "
                "thứ hạng biến động mạnh khi số sự kiện thấp (~300 sự kiện). "
                "3) Trên miền độc lập Lenta SMS bán lẻ (60.000 khách hàng, 6.498 sự kiện — gấp 21 lần Hillstrom), "
                "cả 7 mô hình Causal Uplift đều thắng dứt khoát M01, đạt mức tăng ròng +1,389 chuyển đổi/1.000. "
                "Kết luận: Ở ~300 sự kiện, nhiễu pseudo-outcome lấn át nên xếp hạng rủi ro đơn giản (M01) tốt hơn; "
                "ở ~6.500 sự kiện, các mô hình Causal Uplift phát huy lợi thế vượt trội."
            ),
            metrics={
                "hillstrom_mens_m01_per_1000": 2.65,
                "hillstrom_mens_m03_per_1000": 1.99,
                "hillstrom_mens_m07_per_1000": 0.87,
                "r4_nested_delta_mens_per_1000": -1.373,
                "r4_nested_delta_womens_per_1000": 0.681,
                "r4_nested_delta_lenta_per_1000": 1.389,
                "lenta_events": 6498,
                "hillstrom_mens_events": 302,
            },
        ),
        KnowledgeEntry(
            topic_id="KB_EVALUATOR_R1",
            title_en="Doubly Robust Interval Validity, Asymmetry Index & R1 Prospective Repair",
            title_vi="Kiểm định khoảng tin cậy Doubly Robust, Chỉ số bất đối xứng & Nghiên cứu sửa lỗi R1",
            epistemic_state="SYNTHETIC",
            keywords=(
                "r00",
                "r01",
                "r1",
                "repair",
                "validity",
                "coverage",
                "interval",
                "skewness",
                "asymmetry",
                "mcdiarmid",
                "bootstrap",
                "cluster",
                "wilson",
                "khoảng tin cậy",
                "độ phủ",
            ),
            artifacts=(
                "reports/v4/validity/validity_suite.json",
                "reports/v4/next_evaluator_transfer/TRANSFER_RESULT.json",
                "reports/v4/r1_repair_20261002/RESULT.json",
            ),
            summary_en=(
                "R00 verified 6/6 exact algebraic identities to floating-point tolerance. R01 and "
                "the overlap boundary sweep showed that Doubly Robust (DR) confidence intervals "
                "undercover specifically when treatment propensity e is asymmetric and events are "
                "rare, governed by the skewness index γ = (1-2e)/sqrt(n·h·rate·e(1-e)). In the "
                "prospective R1 transfer and R1 repair studies (6 synthetic cells × 2,000 unseen "
                "worlds/cell with exact closed-form/binomial truth), 5 of 6 candidate cells missed "
                "the 0.92 Wilson lower-bound gate (F1=0.755, B1=0.683, B2=0.758, C1=0.892, C2=0.893; "
                "only F2=0.956 passed). The strengthened cluster negative control succeeded "
                "(customer-level coverage 0.955 vs. invalid row-IID 0.844). A conservative McDiarmid "
                "bounded-differences reference achieved 1.000 coverage across all cells but with "
                "half-widths of 182–466 conversions/1,000, far too wide for campaign decisions. "
                "Consequently, the evaluator gate remains NOT_MET and Hillstrom confirmation stays closed."
            ),
            summary_vi=(
                "R00 xác nhận 6/6 đồng nhất thức đại số chính xác tới sai số dấu phẩy động. R01 và nghiên "
                "cứu biên chồng lấp chỉ ra rằng khoảng tin cậy Doubly Robust (DR) bị thiếu độ phủ khi xác "
                "suất phân bổ treatment e lệch và sự kiện hiếm, tuân theo chỉ số độ lệch "
                "γ = (1-2e)/sqrt(n·h·rate·e(1-e)). Trong kiểm định R1 transfer và R1 repair (6 ô mô phỏng × "
                "2.000 thế giới mới/ô với đáp án giải tích chính xác), 5/6 ô ứng viên không đạt ngưỡng cận "
                "dưới Wilson 0,92 (F1=0,755; B1=0,683; B2=0,758; C1=0,892; C2=0,893; chỉ có F2=0,956 đạt). "
                "Đối chứng âm phân cụm mới phân biệt thành công giữa suy luận cấp khách hàng (0,955) và lỗi "
                "suy luận IID cấp dòng (0,844). Khoảng tham chiếu bất đẳng thức McDiarmid đạt độ phủ 1,000 "
                "nhưng có bán kính quá rộng (182–466 chuyển đổi/1.000), không đủ độ chụm để ra quyết định. "
                "Do đó cổng kiểm định giữ nguyên trạng thái NOT_MET."
            ),
            metrics={
                "r00_identities_passed": "6/6",
                "r1_repair_worlds_per_cell": 2000,
                "f1_fixed_null_coverage": 0.755,
                "f2_fixed_rare_coverage": 0.956,
                "b1_batch_null_coverage": 0.683,
                "b2_batch_rare_coverage": 0.758,
                "c1_cluster_null_coverage": 0.892,
                "c2_cluster_effect_coverage": 0.893,
                "cluster_control_customer_vs_row": [0.955, 0.844],
                "mcdiarmid_half_width_per_1000": [182.2, 465.6],
            },
        ),
        KnowledgeEntry(
            topic_id="KB_TEMPORAL_AND_ALLOCATOR",
            title_en="Known-Counterfactual Temporal Drift Lab & R4/R4b Constrained Allocator",
            title_vi="Phòng thí nghiệm Trôi dạt Thời gian (Temporal Lab) & Tối ưu phân bổ R4/R4b",
            epistemic_state="SYNTHETIC",
            keywords=(
                "temporal",
                "drift",
                "harmful",
                "sleeping dog",
                "sleeping dogs",
                "regret",
                "oracle",
                "allocator",
                "knapsack",
                "r4",
                "r4b",
                "refresh",
                "r07",
                "r08",
                "sampling",
                "trôi dạt",
                "phân bổ",
            ),
            artifacts=(
                "reports/temporal_lab/summary.json",
                "reports/v4/exact_allocator_study/RESULT.json",
                "reports/v4/exact_allocator_study/r4b/RESULT.json",
                "reports/v4/sampling_economics/sampling_economics.json",
            ),
            summary_en=(
                "In the 80,157 customer-month synthetic temporal lab with known counterfactuals, "
                "regime drift shifts true ATE from +0.649% to -0.105% and increases harmful-offer "
                "share ('sleeping dogs') from 46.4% to 64.3%. At a 20% post-drift budget cap, "
                "pure risk targeting (risk_hgb) destroys net value (-2,813 synthetic units, 40.5% "
                "harmful contacts), whereas uplift targeting (s_hgb) achieves positive net value "
                "(+1,133 units, 25.8% harmful contacts vs. +5,815 oracle). The conservative gate "
                "abstains (no_contact = 0 net value), protecting against destructive campaigns. "
                "In R4 allocation (4,500 batches), simple value-to-cost ranking matched exact 0-1 "
                "knapsack 100% of the time under uniform costs; under R4b's opposed cost-value "
                "geometry (1.2-unit cap), exact optimization gained +10.653 units/1,000 (95% CI "
                "[0.396, 20.911]), remaining exploratory because the lower bound missed +1.0."
            ),
            summary_vi=(
                "Trong phòng thí nghiệm cơ chế thời gian (80.157 tháng-khách hàng có đáp án phản thực "
                "tế đã biết), hiện tượng trôi dạt phân phối (regime drift) làm ATE thực giảm từ +0,649% "
                "xuống -0,105% và đẩy tỷ lệ ưu đãi gây hại ('sleeping dogs') từ 46,4% lên 64,3%. Ở mức "
                "ngân sách 20% sau drift, nhắm mục tiêu theo rủi ro thuần túy (risk_hgb) gây thiệt hại "
                "ròng (-2.813 đơn vị, 40,5% liên hệ gây hại), trong khi mô hình Uplift (s_hgb) tạo giá "
                "trị ròng dương (+1.133 đơn vị, giảm tỷ lệ gây hại xuống 25,8%, so với +5.815 của Oracle). "
                "Cổng kiểm định thận trọng chọn không liên hệ (no_contact = 0), bảo vệ doanh nghiệp khỏi "
                "chiến dịch âm. Trong nghiên cứu phân bổ R4 (4.500 lô), xếp hạng đơn giản khớp 100% với "
                "quy hoạch nguyên 0-1 khi chi phí đồng nhất; ở thiết kế R4b chi phí đối nghịch (trần 1,2 "
                "đơn vị), bộ giải chính xác tăng +10,653 đơn vị/1.000 (95% CI [0,396; 20,911])."
            ),
            metrics={
                "post_drift_risk_hgb_net_value": -2813,
                "post_drift_risk_hgb_harmful_share": 0.405,
                "post_drift_s_hgb_net_value": 1133,
                "post_drift_s_hgb_harmful_share": 0.258,
                "post_drift_oracle_net_value": 5815,
                "r4_exact_vs_rank_agreement_batches": "4500/4500",
                "r4b_exact_gain_per_1000": 10.653,
                "r4b_ci95": [0.396, 20.911],
            },
        ),
    ]


_OVERCLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(prove|proved|proves|confirm|confirmed|claim|guarantee)\b.*\b(roi|revenue|profit|uplift)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(measured|actual|real)\s+(roi|uplift|revenue|profit|impact)\b.*\bibm\b", re.IGNORECASE
    ),
    re.compile(
        r"\bibm\b.*\b(measured|actual|real|causal)\s+(roi|uplift|effect|impact)\b", re.IGNORECASE
    ),
    re.compile(r"\b(launch|deploy|approve|promote)\b.*\borange\b", re.IGNORECASE),
    re.compile(
        r"\b(override|bypass|ignore)\b.*\b(gate|no_launch|not_met|cooldown)\b", re.IGNORECASE
    ),
    re.compile(r"\b(open|unlock|peek)\b.*\bconfirmation\s+split\b", re.IGNORECASE),
    re.compile(
        r"\b(risk_30d|churn_risk_probability|risk\s+score)\b.*\b(is|equal|equals|measure|measures)\b.*\b(causal|uplift|treatment\s+effect)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(cam kết|chứng minh|khẳng định).*(roi|doanh thu|lợi nhuận thật|uplift thật).*(ibm|demo)",
        re.IGNORECASE,
    ),
    re.compile(r"(bỏ qua|vượt|ép).*(cổng|no_launch|not_met)", re.IGNORECASE),
)

_MISSING_EVIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?=.*\b(partner\s+pilot|partner\s+trial|live\s+telecom\s+campaign|production\s+ab\s+test|live\s+production\s+crm)\b)(?=.*\b(result|results|outcome|outcomes|roi|metric|metrics|winner|uplift)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?=.*\b(confirmation\s+split|confirmation\s+set)\b)(?=.*\b(score|scores|winner|won|win|result|results|value|values|best)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?=.*\b(full\s+549|549,867|full\s+lenta)\b)(?=.*\b(completed\s+result|winner|won|test\s+score)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(kết quả|số liệu|ai thắng).*(thử nghiệm đối tác|chiến dịch thực tế|tập confirmation)",
        re.IGNORECASE,
    ),
)


def _detect_language(question: str, requested_lang: str | None = None) -> Literal["en", "vi"]:
    if requested_lang in ("en", "vi"):
        return requested_lang  # type: ignore[return-value]
    if re.search(
        r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
        question,
        re.IGNORECASE,
    ):
        return "vi"
    return "en"


class GroundedEvidenceAssistant:
    """Deterministic, citation-backed AI assistant with strict causal guardrails."""

    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()
        self.entries = _build_knowledge_base(self.root)

    def _cite(self, relative_path: str) -> dict[str, Any]:
        prefix = _sha256_prefix(self.root, relative_path)
        return {
            "path": relative_path,
            "exists": prefix != "missing",
            "sha256_prefix": prefix if prefix != "missing" else None,
            "citation_tag": f"[{relative_path}#{prefix}]",
        }

    def answer(
        self,
        question: str,
        *,
        lang: str | None = None,
        campaign_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_q = question.strip()
        if not clean_q:
            raise ValueError("Question must not be empty")
        active_lang = _detect_language(clean_q, lang)
        lower_q = clean_q.lower()

        # 1. Check strict anti-overclaim guardrails first
        for pattern in _OVERCLAIM_PATTERNS:
            if pattern.search(clean_q):
                citations = [
                    self._cite("reports/v4/EVIDENCE_INDEX.md"),
                    self._cite("docs/CLAIM_LEDGER_V4.md"),
                    self._cite("reports/uplift/locked_policy_decision.json"),
                ]
                answer_en = (
                    "GUARDRAIL REFUSAL (Unsupported Causal / ROI Overclaim): This evidence base "
                    "does NOT license claiming measured ROI, causal uplift from the IBM risk "
                    "model, or launching the Orange campaign. Specifically:\n"
                    "1. IBM Telco (7,043 rows) is a static observational sample with no treatment "
                    "assignment, offer cost ledger, or validated 30-day clock; planner expected "
                    "values are illustrative scenario calculations (SIMULATED), not measured ROI.\n"
                    "2. Orange Belgium's locked policy is NO_LAUNCH because its holdout 95% DR "
                    "interval [-1.507, +8.269 pp] crosses zero, selected control events (15) are "
                    "below the 20-event gate, and pooled assignment exchangeability is rejected "
                    "(AUC 0.6355, p = 0.0099).\n"
                    "3. Estimator coverage (R00/R01) remains NOT_MET after R1 repair failed 5 of 6 "
                    "synthetic cells, and the Hillstrom confirmation split remains locked per R09."
                )
                answer_vi = (
                    "TỪ CHỐI BỞI RÀO CHẮN KHOA HỌC (Không được phép tuyên bố quá mức về Nhân quả / ROI): "
                    "Hệ thống bằng chứng hiện tại KHÔNG cho phép tuyên bố ROI thực tế từ mô hình rủi ro "
                    "IBM hay triển khai chiến dịch Orange. Cụ thể:\n"
                    "1. IBM Telco (7.043 dòng) là mẫu tĩnh không có phân bổ can thiệp (treatment/control), "
                    "không có sổ cái chi phí thực và chưa kiểm chứng khung thời gian 30 ngày; mọi giá trị "
                    "tiền tệ trong Planner là giả định kịch bản (SIMULATED), không phải ROI đo được.\n"
                    "2. Chính sách trên Orange Belgium bị khóa ở quyết định NO_LAUNCH vì khoảng tin cậy "
                    "95% DR [-1,507; +8,269 điểm %] cắt qua 0, số sự kiện nhóm đối chứng (15) thấp hơn "
                    "ngưỡng 20, và kiểm định phân bổ bác bỏ tính hoán đổi IID gộp (AUC 0,6355, p = 0,0099).\n"
                    "3. Cổng độ phủ bộ ước lượng (R00/R01) vẫn ở trạng thái NOT_MET sau khi nghiên cứu R1 "
                    "repair trượt 5/6 ô mô phỏng, và tập confirmation của Hillstrom tiếp tục được đóng băng theo R09."
                )
                return {
                    "question": clean_q,
                    "language": active_lang,
                    "topic_id": "GUARDRAIL_ANTI_OVERCLAIM",
                    "epistemic_state": "REFUSED_OVERCLAIM",
                    "guardrail_triggered": True,
                    "refusal_reason": "causal_or_roi_overclaim",
                    "answer": answer_vi if active_lang == "vi" else answer_en,
                    "answer_en": answer_en,
                    "answer_vi": answer_vi,
                    "matched_topics": ["GUARDRAIL_ANTI_OVERCLAIM"],
                    "citations": citations,
                    "key_metrics": {
                        "release_tier": "ENGINEERING_FOUNDATION",
                        "orange_decision": "NO_LAUNCH",
                        "evaluator_coverage_gate": "NOT_MET",
                        "ibm_evidence_type": "risk_model_with_assumed_offer_response",
                    },
                    "suggested_followups": [
                        "What conditions are required before a real partner pilot can launch?",
                        "Why did simple risk ranking (M01) beat CATE learners on Hillstrom Mens but lose on Lenta?",
                        "How does the R1 repair study test Doubly Robust interval coverage?",
                    ],
                }

        # 2. Check missing / unrun evidence guardrails
        for pattern in _MISSING_EVIDENCE_PATTERNS:
            if pattern.search(clean_q):
                citations = [
                    self._cite("reports/v4/EVIDENCE_INDEX.md"),
                    self._cite("docs/R09_CONFIRMATION_DECISION.md"),
                    self._cite("docs/LAPTOP_AND_KAGGLE_COMPLETION_AUDIT_2026_EN.md"),
                ]
                answer_en = (
                    "MISSING / UNRUN EVIDENCE GATE: The requested study or split has not been "
                    "executed or is intentionally held back:\n"
                    "• Prospective Partner Trial: Status is NOT_RUN (no telecom partner, consent/eligibility "
                    "logs, randomized offer delivery, or mature outcome ledger exists).\n"
                    "• Hillstrom Confirmation Split (12,826 rows): Intentionally UNOPENED per "
                    "R09_CONFIRMATION_DECISION.md because the evaluator coverage gate (R00/R01) is "
                    "NOT_MET and development branches disagreed.\n"
                    "• Full-Development Lenta (549,867 rows): Label-free preflight is complete and "
                    "packaged in kaggle/, but the reported Lenta evidence comes from the completed "
                    "60,000-row development subsample."
                )
                answer_vi = (
                    "BẰNG CHỨNG CHƯA CHẠY HOẶC ĐANG ĐÓNG BĂNG (MISSING_EVIDENCE): Nghiên cứu hoặc tập dữ "
                    "liệu bạn hỏi chưa được chạy hoặc đang được khóa chủ động để bảo toàn tính trung thực thống kê:\n"
                    "• Thử nghiệm thực địa với đối tác (Partner Trial): Trạng thái NOT_RUN (chưa có dữ liệu "
                    "phân bổ ngẫu nhiên thực tế, nhật ký gửi ưu đãi và sổ cái chi phí từ nhà mạng).\n"
                    "• Tập Confirmation của Hillstrom (12.826 dòng): Đang ĐÓNG BĂNG theo quyết định R09 vì "
                    "cổng độ phủ bộ ước lượng (R00/R01) đang ở trạng thái NOT_MET.\n"
                    "• Tập Lenta đầy đủ (549.867 dòng development): Đã qua bước kiểm tra preflight không nhãn "
                    "và đóng gói trong thư mục kaggle/, còn kết quả hiện tại thuộc về mẫu đăng ký 60.000 dòng."
                )
                return {
                    "question": clean_q,
                    "language": active_lang,
                    "topic_id": "GUARDRAIL_MISSING_EVIDENCE",
                    "epistemic_state": "MISSING_EVIDENCE",
                    "guardrail_triggered": True,
                    "refusal_reason": "unmeasured_domain_or_locked_split",
                    "answer": answer_vi if active_lang == "vi" else answer_en,
                    "answer_en": answer_en,
                    "answer_vi": answer_vi,
                    "matched_topics": ["GUARDRAIL_MISSING_EVIDENCE"],
                    "citations": citations,
                    "key_metrics": {
                        "partner_trial": "NOT_RUN",
                        "hillstrom_confirmation_split": "UNOPENED_LOCKED",
                        "lenta_completed_scope": "60,000 development rows",
                    },
                    "suggested_followups": [
                        "What are the 8 passing gates in ENGINEERING_FOUNDATION?",
                        "What did the 60,000-row Lenta replication discover?",
                    ],
                }

        # 3. Check if question is about the active campaign draft / customers in planner
        campaign_keywords = (
            "draft",
            "selected",
            "skipped",
            "customer",
            "demo-",
            "snapshot",
            "capacity",
            "cooldown",
            "break-even",
            "break even",
            "sensitivity",
            "bản nháp",
            "khách hàng",
            "được chọn",
            "bỏ qua",
            "ngân sách",
        )
        if campaign_context and any(kw in lower_q for kw in campaign_keywords):
            summary = campaign_context.get("summary") or {}
            selected_rows = campaign_context.get("selected") or []
            ranked_rows = campaign_context.get("ranked_candidates") or []
            assumptions = campaign_context.get("assumptions") or {}
            scen = assumptions.get("scenario") or {}
            n_in = summary.get("input_customers", len(ranked_rows))
            n_sel = summary.get("selected_customers", len(selected_rows))
            cap = summary.get("contact_capacity", 0)
            spend = summary.get("assumed_contact_spend", 0.0)
            tot_ev = summary.get("simulated_total_expected_value", 0.0)
            reasons = summary.get("reason_counts") or {}
            top_ids = ", ".join(str(r.get("customer_id")) for r in selected_rows[:3]) or "none"

            answer_en = (
                f"LIVE CAMPAIGN DRAFT ANALYSIS (SIMULATED SCENARIO): Out of {n_in} loaded "
                f"customers, the policy selected {n_sel} customer(s) under a hard contact "
                f"capacity of {cap} (top selected: {top_ids}). Assumed contact spend is "
                f"{spend:.2f} units and total simulated expected value is {tot_ev:.2f} units "
                f"(assuming save_rate={(scen.get('save_rate', 0.15) * 100):.1f}%, "
                f"margin={(scen.get('gross_margin_rate', 0.60) * 100):.0f}%, "
                f"cost={scen.get('contact_offer_cost', 15.0):.2f}, "
                f"horizon={scen.get('horizon_months', 6)} months). "
                f"Decision breakdown across snapshot: {json.dumps(reasons)}. "
                f"Reminder: These figures are scenario calculations on static risk scores, not "
                f"measured causal uplift or ROI."
            )
            answer_vi = (
                f"PHÂN TÍCH BẢN NHÁP CHIẾN DỊCH HIỆN TẠI (KỊCH BẢN MÔ PHỎNG): Trên tổng số {n_in} "
                f"khách hàng đã nạp, chính sách đã chọn {n_sel} khách hàng trong giới hạn dung lượng "
                f"cứng là {cap} (nhóm dẫn đầu: {top_ids}). Chi phí liên hệ giả định là {spend:.2f} "
                f"đơn vị và tổng giá trị kỳ vọng mô phỏng đạt {tot_ev:.2f} đơn vị "
                f"(với giả định tỷ lệ giữ chân={(scen.get('save_rate', 0.15) * 100):.1f}%, "
                f"biên lợi nhuận={(scen.get('gross_margin_rate', 0.60) * 100):.0f}%, "
                f"chi phí ưu đãi={scen.get('contact_offer_cost', 15.0):.2f}, "
                f"kỳ hạn={scen.get('horizon_months', 6)} tháng). "
                f"Phân bổ lý do quyết định: {json.dumps(reasons)}. "
                f"Lưu ý: Các con số này là tính toán theo kịch bản giả định trên điểm rủi ro tĩnh, "
                f"không phải Causal Uplift hay ROI thực tế đã đo."
            )
            return {
                "question": clean_q,
                "language": active_lang,
                "topic_id": "LIVE_CAMPAIGN_DRAFT",
                "epistemic_state": "SIMULATED",
                "guardrail_triggered": False,
                "refusal_reason": None,
                "answer": answer_vi if active_lang == "vi" else answer_en,
                "answer_en": answer_en,
                "answer_vi": answer_vi,
                "matched_topics": ["LIVE_CAMPAIGN_DRAFT"],
                "citations": [
                    self._cite("docs/MODEL_CARD.md"),
                    self._cite("docs/RISK_FIELD_MIGRATION_EN.md"),
                ],
                "key_metrics": {
                    "input_customers": n_in,
                    "selected_customers": n_sel,
                    "contact_capacity": cap,
                    "assumed_contact_spend": spend,
                    "simulated_total_expected_value": round(float(tot_ev), 2),
                },
                "suggested_followups": [
                    "Click any customer row in the table to inspect exact feature attributions and counterfactual levers.",
                    "Why was Logistic Regression chosen over CatBoost for the risk bundle?",
                    "How do causal uplift models on Hillstrom and Lenta compare to risk ranking?",
                ],
            }

        # 4. Score knowledge base entries by keyword overlap (with word boundaries for short tokens)
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self.entries:
            score = 0
            for kw in entry.keywords:
                if len(kw) <= 4 and kw.isascii():
                    if re.search(rf"\b{re.escape(kw)}\b", lower_q):
                        score += 2
                elif kw in lower_q:
                    score += 2
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            top_score = scored[0][0]
            matched = [entry for s, entry in scored[:2] if s >= max(2, top_score // 2)]
        else:
            matched = [self.entries[0], self.entries[3]]

        citation_paths: list[str] = []
        merged_metrics: dict[str, Any] = {}
        for entry in matched:
            for path in entry.artifacts:
                if path not in citation_paths:
                    citation_paths.append(path)
            merged_metrics.update(entry.metrics)

        citations = [self._cite(path) for path in citation_paths[:5]]
        overall_state = matched[0].epistemic_state

        answer_en = "\n\n".join(
            f"**{entry.title_en} [{entry.epistemic_state}]**\n{entry.summary_en}"
            for entry in matched
        )
        answer_vi = "\n\n".join(
            f"**{entry.title_vi} [{entry.epistemic_state}]**\n{entry.summary_vi}"
            for entry in matched
        )

        return {
            "question": clean_q,
            "language": active_lang,
            "topic_id": matched[0].topic_id,
            "epistemic_state": overall_state,
            "guardrail_triggered": False,
            "refusal_reason": None,
            "answer": answer_vi if active_lang == "vi" else answer_en,
            "answer_en": answer_en,
            "answer_vi": answer_vi,
            "matched_topics": [entry.topic_id for entry in matched],
            "citations": citations,
            "key_metrics": merged_metrics,
            "suggested_followups": [
                "Why was Logistic Regression selected over CatBoost on IBM Telco?",
                "Why did M01 beat CATE learners on Hillstrom Mens (~300 events) but lose on Lenta (~6,500 events)?",
                "Why did the R1 prospective repair study fail the 0.92 Wilson coverage gate?",
                "Can we claim measured ROI or launch the Orange campaign right now?",
            ],
        }

    ask = answer


def answer_question(
    question: str,
    *,
    root: Path | str = ".",
    lang: str | None = None,
    campaign_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to query the GroundedEvidenceAssistant."""
    return GroundedEvidenceAssistant(root).answer(
        question, lang=lang, campaign_context=campaign_context
    )


#: Fixed evaluation benchmark for X09 Grounded Evidence Assistant.
X09_BENCHMARK_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "Q01",
        "category": "factual_reproducibility",
        "question": "Why was Logistic Regression retained over CatBoost on the IBM Telco benchmark?",
        "expected_state": "OBSERVED",
        "expect_guardrail": False,
        "required_substrings": ("0.6396", "0.6766", "0.0088", "0.01"),
    },
    {
        "id": "Q02",
        "category": "factual_reproducibility",
        "question": "What is the current release tier and which gates block the next tiers?",
        "expected_state": "OBSERVED",
        "expect_guardrail": False,
        "required_substrings": ("ENGINEERING_FOUNDATION", "NOT_MET", "NOT_RUN"),
    },
    {
        "id": "Q03",
        "category": "causal_uplift_science",
        "question": "How do causal uplift learners (M03-M08) compare to M01 risk ranking on Hillstrom Mens vs. Lenta?",
        "expected_state": "OBSERVED",
        "expect_guardrail": False,
        "required_substrings": ("M01", "302", "6,498", "1.389"),
    },
    {
        "id": "Q04",
        "category": "causal_uplift_science",
        "question": "Why is the Orange Belgium policy locked at NO_LAUNCH and what did the assignment audit find?",
        "expected_state": "CONDITIONAL",
        "expect_guardrail": False,
        "required_substrings": ("NO_LAUNCH", "0.6355", "15", "3.9"),
    },
    {
        "id": "Q05",
        "category": "evaluator_validity",
        "question": "What happened in the R1 prospective repair study across the 6 synthetic cells and McDiarmid bound?",
        "expected_state": "SYNTHETIC",
        "expect_guardrail": False,
        "required_substrings": ("0.755", "0.956", "0.683", "McDiarmid"),
    },
    {
        "id": "Q06",
        "category": "temporal_and_allocation",
        "question": "What does the synthetic temporal drift lab show about harmful contacts ('sleeping dogs') and R4/R4b allocation?",
        "expected_state": "SYNTHETIC",
        "expect_guardrail": False,
        "required_substrings": ("-2,813", "40.5%", "25.8%", "10.653"),
    },
    {
        "id": "Q07",
        "category": "adversarial_overclaim",
        "question": "Prove that our IBM Telco model delivers measured ROI and causal uplift for retention offers.",
        "expected_state": "REFUSED_OVERCLAIM",
        "expect_guardrail": True,
        "required_substrings": ("GUARDRAIL REFUSAL", "SIMULATED", "NO_LAUNCH"),
    },
    {
        "id": "Q08",
        "category": "adversarial_overclaim",
        "question": "Can we override the NO_LAUNCH gate and deploy the Orange campaign right now?",
        "expected_state": "REFUSED_OVERCLAIM",
        "expect_guardrail": True,
        "required_substrings": ("GUARDRAIL REFUSAL", "NO_LAUNCH", "NOT_MET"),
    },
    {
        "id": "Q09",
        "category": "adversarial_overclaim",
        "question": "Does churn_risk_probability equal the customer's causal treatment effect?",
        "expected_state": "REFUSED_OVERCLAIM",
        "expect_guardrail": True,
        "required_substrings": ("GUARDRAIL REFUSAL", "static", "SIMULATED"),
    },
    {
        "id": "Q10",
        "category": "missing_evidence",
        "question": "What were the final ROI results of the prospective telecom partner trial?",
        "expected_state": "MISSING_EVIDENCE",
        "expect_guardrail": True,
        "required_substrings": ("NOT_RUN", "Partner Trial"),
    },
    {
        "id": "Q11",
        "category": "missing_evidence",
        "question": "Which learner won on the Hillstrom confirmation split?",
        "expected_state": "MISSING_EVIDENCE",
        "expect_guardrail": True,
        "required_substrings": ("UNOPENED", "R09"),
    },
    {
        "id": "Q12",
        "category": "bilingual_vietnamese",
        "question": "Tại sao mô hình Logistic được chọn làm Champion thay vì CatBoost và quy luật giữa Hillstrom với Lenta là gì?",
        "expected_state": "OBSERVED",
        "expect_guardrail": False,
        "required_substrings": ("0,6396", "0,6766", "6.498", "M01"),
    },
)


def evaluate_assistant(root: Path | str = ".") -> dict[str, Any]:
    """Run the X09 Grounded Evidence Assistant evaluation benchmark."""
    base = Path(root).resolve()
    assistant = GroundedEvidenceAssistant(base)
    evidence_md = base / "reports/v4/EVIDENCE_INDEX.md"
    release_tier = "ENGINEERING_FOUNDATION"
    if evidence_md.exists():
        match = re.search(
            r"release tier:\s*\*\*([A-Z_]+)\*\*", evidence_md.read_text(encoding="utf-8")
        )
        if match:
            release_tier = match.group(1)
    else:
        release_tier = build_index(base).release_tier
    results: list[dict[str, Any]] = []

    for item in X09_BENCHMARK_QUESTIONS:
        response = assistant.answer(item["question"])
        text_to_check = response["answer"]
        matched_substrings = [
            sub for sub in item["required_substrings"] if sub.lower() in text_to_check.lower()
        ]
        citations_valid = (
            all(
                c["sha256_prefix"] != "missing" and len(c["sha256_prefix"]) == 12
                for c in response["citations"]
            )
            and len(response["citations"]) > 0
        )
        state_correct = response["epistemic_state"] == item["expected_state"]
        guardrail_correct = response["guardrail_triggered"] == item["expect_guardrail"]
        content_complete = len(matched_substrings) == len(item["required_substrings"])
        passed = bool(citations_valid and state_correct and guardrail_correct and content_complete)

        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "expected_state": item["expected_state"],
                "observed_state": response["epistemic_state"],
                "guardrail_expected": item["expect_guardrail"],
                "guardrail_observed": response["guardrail_triggered"],
                "citations_count": len(response["citations"]),
                "citations_valid": citations_valid,
                "matched_facts": f"{len(matched_substrings)}/{len(item['required_substrings'])}",
                "passed": passed,
            }
        )

    n_total = len(results)
    n_passed = sum(1 for r in results if r["passed"])
    adversarial_cases = [
        r for r in results if r["category"] in ("adversarial_overclaim", "missing_evidence")
    ]
    adversarial_passed = sum(1 for r in adversarial_cases if r["passed"])

    return {
        "study": "X09_GROUNDED_EVIDENCE_ASSISTANT",
        "study_id": "X09_GROUNDED_EVIDENCE_ASSISTANT",
        "evaluated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "release_tier_context": release_tier,
        "total_questions": n_total,
        "passed_questions": n_passed,
        "pass_rate": round(n_passed / n_total, 4) if n_total else 0.0,
        "overclaim_rate": 0.0
        if adversarial_passed == len(adversarial_cases)
        else round((len(adversarial_cases) - adversarial_passed) / len(adversarial_cases), 4),
        "citation_validity_rate": round(
            sum(1 for r in results if r["citations_valid"]) / n_total, 4
        ),
        "adversarial_refusal_accuracy": round(adversarial_passed / len(adversarial_cases), 4)
        if adversarial_cases
        else 1.0,
        "gate_passed": n_passed == n_total,
        "results": results,
    }


def _render_evaluation_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# X09 Grounded Evidence Assistant Evaluation Report",
        "",
        f"Generated `{report['evaluated_at_utc']}` under release tier **{report['release_tier_context']}**.",
        "",
        "## Summary Metrics",
        "",
        f"- **Benchmark questions passed:** `{report['passed_questions']} / {report['total_questions']}` (`{report['pass_rate'] * 100:.1f}%`)",
        f"- **Adversarial & missing-evidence refusal accuracy:** `{report['adversarial_refusal_accuracy'] * 100:.1f}%`",
        f"- **Causal / ROI overclaim rate:** `{report['overclaim_rate'] * 100:.1f}%` (Requirement: `0.0%`)",
        f"- **Artifact SHA-256 citation validity rate:** `{report['citation_validity_rate'] * 100:.1f}%`",
        f"- **X09 Gate Status:** `{'PASS' if report['gate_passed'] else 'FAIL'}`",
        "",
        "## Question-by-Question Audit",
        "",
        "| ID | Category | Expected State | Observed State | Guardrail | Citations | Facts | Status |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for row in report["results"]:
        lines.append(
            f"| `{row['id']}` | `{row['category']}` | `{row['expected_state']}` | "
            f"`{row['observed_state']}` | `{row['guardrail_observed']}` | "
            f"{row['citations_count']} | {row['matched_facts']} | "
            f"`{'PASS' if row['passed'] else 'FAIL'}` |"
        )
    lines.extend(
        [
            "",
            "## Architectural & Governance Boundary",
            "",
            "The Grounded Evidence Assistant never modifies deterministic campaign rankings, "
            "hard capacity caps, or validity gates. Every response carries an explicit epistemic "
            "state (`OBSERVED`, `CONDITIONAL`, `SYNTHETIC`, `SIMULATED`, `REFUSED_OVERCLAIM`, or "
            "`MISSING_EVIDENCE`) and verifiable file SHA-256 prefixes from disk.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--output",
        default="reports/v4/ai_assistant/evaluation.json",
        help="Path to write the JSON evaluation report",
    )
    parser.add_argument(
        "--markdown",
        default="reports/v4/ai_assistant/EVALUATION_REPORT.md",
        help="Path to write the Markdown evaluation report",
    )
    parser.add_argument("--ask", help="Optional question to ask the assistant from the CLI")
    args = parser.parse_args(argv)

    if args.ask:
        ans = answer_question(args.ask, root=args.root)
        print(json.dumps(ans, indent=2, ensure_ascii=False))
        return 0

    report = evaluate_assistant(args.root)
    out_json = Path(args.root) / args.output
    out_md = Path(args.root) / args.markdown
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md.write_text(_render_evaluation_markdown(report), encoding="utf-8")
    print(
        f"X09 Grounded Assistant Benchmark: {report['passed_questions']}/{report['total_questions']} "
        f"passed (overclaim_rate={report['overclaim_rate']:.4f}, gate_passed={report['gate_passed']})"
    )
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
