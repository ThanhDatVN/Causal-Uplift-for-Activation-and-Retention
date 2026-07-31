import json
from pathlib import Path

import pandas as pd

from scripts.export_dashboard_data import build_payload
from src.paths import OUTPUT_DIR


SPRINT2_DIR = OUTPUT_DIR / "sprint2"


def test_sprint2_release_artifacts_exist():
    required = [
        "protocol_manifest.json",
        "calibration_comparison.csv",
        "paired_qini_bootstrap.csv",
        "policy_value_comparison.csv",
        "policy_sensitivity.csv",
        "policy_budget_curve.csv",
        "confirmation_predictions.npz",
    ]
    assert all((SPRINT2_DIR / name).exists() for name in required)


def test_sprint2_confirmation_is_distinct_and_bootstrap_is_release_size():
    manifest = json.loads(
        (SPRINT2_DIR / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    hashes = manifest["split"]["source_index_sha256"]
    assert len(set(hashes.values())) == 3
    assert manifest["split"]["rows"]["confirmation"] == 1_397_959
    assert manifest["evaluation"]["n_boot"] == 500
    assert manifest["evaluation"]["monetary_outcome_available"] is False


def test_dashboard_contract_selects_response_on_validation():
    payload = build_payload(SPRINT2_DIR)
    assert payload["schema_version"] == "sprint2-dashboard-v1"
    assert payload["meta"]["champion"] == "Response"
    assert payload["decision"]["selection_split"] == "validation"
    assert payload["decision"]["individual_principal_strata_available"] is False
    assert payload["causal_forest"]["release_result_available"] is False


def test_policy_curve_has_treat_none_and_finite_release_points():
    curve = pd.read_csv(SPRINT2_DIR / "policy_budget_curve.csv")
    zero = curve.loc[curve["budget_fraction"] == 0].iloc[0]
    assert zero["target_fraction"] == 0
    assert zero["gross_incremental_conversions_per_customer_dr"] == 0
    positive = curve.loc[curve["budget_fraction"] > 0]
    assert (positive["gross_dr_ci_low"] > 0).all()
    assert (positive["n_boot"] == 500).all()


def test_main_response_policy_beats_random_by_paired_ci():
    comparison = pd.read_csv(SPRINT2_DIR / "policy_value_comparison.csv")
    response = comparison.loc[comparison["policy"] == "Response top-k"].iloc[0]
    assert response["dr_delta_vs_random_ci_low"] > 0
    assert response["n_boot"] == 500


def test_dashboard_html_is_self_contained_and_guarded():
    html = (OUTPUT_DIR / "dashboard.html").read_text(encoding="utf-8")
    assert "sprint2-dashboard-v1" in html
    assert "CAUSAL FOREST PENDING" in html
    assert "actual revenue/profit" in html
    assert 'class="seg ' not in html
    assert "https://cdn" not in html
