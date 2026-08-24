"""Artifact phát hành Sprint 2 và dashboard tự chứa.

Kiểm rằng sản phẩm và bằng chứng không trôi khỏi nhau:

- artifact release tồn tại đủ;
- confirmation là tập **riêng biệt**, và số lần bootstrap đúng bằng mức đã phát hành;
- hợp đồng dashboard chọn Response **trên validation**, đúng như selection contract — không
  chọn lại sau khi nhìn confirmation;
- policy curve có điểm `treat-none` và mọi điểm release đều hữu hạn;
- Response top-k thắng random theo **paired CI**, không chỉ theo point estimate.

`test_dashboard_html_is_self_contained_and_guarded` chặn việc dashboard lặng lẽ phụ thuộc
CDN: nó phải mở được khi không có mạng.
"""

import json
from pathlib import Path

import pandas as pd

from scripts.export_dashboard_data import build_payload
from src.paths import OUTPUT_DIR
from tests.repo_state import ignored_paths


SPRINT2_DIR = OUTPUT_DIR / "sprint2"


def test_sprint2_release_artifacts_exist():
    """Artifact release Sprint 2 phải có mặt.

    `confirmation_predictions.npz` bị `.gitignore` loại (`output/**/*.npz`) vì mảng dự
    đoán tái tạo lại được và làm repo nặng thêm. Trên máy dev nó tồn tại và được kiểm;
    trên bản checkout sạch nó vắng mặt đúng thiết kế nên bỏ qua thay vì fail.
    """
    required = [
        "protocol_manifest.json",
        "calibration_comparison.csv",
        "paired_qini_bootstrap.csv",
        "policy_value_comparison.csv",
        "policy_sensitivity.csv",
        "policy_budget_curve.csv",
        "confirmation_predictions.npz",
    ]
    absent = [
        f"output/sprint2/{name}"
        for name in required
        if not (SPRINT2_DIR / name).exists()
    ]
    by_design = ignored_paths(absent)
    missing = sorted(p for p in absent if p not in by_design)
    assert not missing, "Thieu artifact release:\n" + "\n".join(f"  {m}" for m in missing)


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
    html = (OUTPUT_DIR / "product" / "dashboard.html").read_text(encoding="utf-8")
    assert "sprint2-dashboard-v1" in html
    assert "CAUSAL FOREST PENDING" in html
    assert "actual revenue/profit" in html
    assert 'class="seg ' not in html
    assert "https://cdn" not in html
