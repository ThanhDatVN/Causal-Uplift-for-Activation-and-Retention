"""Export the audited Sprint 2 artifacts to one dashboard data contract."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import OUTPUT_DIR


REQUIRED_SPRINT2_FILES = [
    "protocol_manifest.json",
    "calibration_comparison.csv",
    "paired_qini_bootstrap.csv",
    "policy_value_comparison.csv",
    "policy_sensitivity.csv",
    "policy_budget_curve.csv",
]


def _records(frame: pd.DataFrame) -> list[dict]:
    result = []
    for record in frame.to_dict(orient="records"):
        clean = {}
        for key, value in record.items():
            if isinstance(value, float) and not math.isfinite(value):
                clean[key] = None
            else:
                clean[key] = value
        result.append(clean)
    return result


def build_payload(sprint2_dir: Path) -> dict:
    missing = [
        name for name in REQUIRED_SPRINT2_FILES
        if not (sprint2_dir / name).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"Thiếu Sprint 2 release artifacts: {', '.join(missing)}"
        )
    manifest = json.loads(
        (sprint2_dir / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    calibration = pd.read_csv(sprint2_dir / "calibration_comparison.csv")
    confirmation = calibration.loc[
        calibration["split"] == "confirmation"
    ].copy()
    validation = calibration.loc[calibration["split"] == "validation"].copy()
    paired = pd.read_csv(sprint2_dir / "paired_qini_bootstrap.csv")
    main_policy = pd.read_csv(sprint2_dir / "policy_value_comparison.csv")
    budget_curve = pd.read_csv(sprint2_dir / "policy_budget_curve.csv")

    # Selection is made on validation, before reading confirmation results.
    ranking_candidates = validation.loc[
        np.isfinite(validation["qini_score"])
        & np.isfinite(validation["auuc_score"])
    ]
    champion = ranking_candidates.sort_values(
        ["qini_score", "auuc_score"],
        ascending=False,
    ).iloc[0]["model"]
    if champion != "Response":
        raise ValueError(
            "Dashboard contract expects the validation-selected Response champion; "
            f"artifact currently selects {champion!r}. Review before changing UI."
        )

    champion_confirmation = confirmation.loc[
        confirmation["model"] == champion
    ].iloc[0]
    x_vs_response = paired.loc[
        (paired["model_a"] == "X-Renormalized")
        & (paired["model_b"] == "Response")
    ].iloc[0]

    return {
        "schema_version": "sprint2-dashboard-v1",
        "meta": {
            "run_id": manifest["run_id"],
            "status": manifest["status"],
            "champion": champion,
            "confirmation_rows": manifest["split"]["rows"]["confirmation"],
            "data_sha256": manifest["data"]["sha256"],
            "split_protocol": manifest["split"]["protocol"],
            "confirmation_index_sha256": manifest["split"][
                "source_index_sha256"
            ]["confirmation"],
            "n_boot": manifest["evaluation"]["n_boot"],
            "qini_confirmation": champion_confirmation["qini_score"],
            "auuc_confirmation": champion_confirmation["auuc_score"],
        },
        "decision": {
            "rule": "Target top-k% by Response score.",
            "selection_split": "validation",
            "reason": (
                "Response had the highest validation Qini among deployable "
                "ranking candidates. On untouched confirmation, "
                "X-Renormalized minus Response was not separated from zero."
            ),
            "x_minus_response_qini": x_vs_response["observed_difference"],
            "x_minus_response_ci_low": x_vs_response["ci_low"],
            "x_minus_response_ci_high": x_vs_response["ci_high"],
            "individual_principal_strata_available": False,
        },
        "model_comparison": _records(
            confirmation[
                [
                    "model",
                    "model_label",
                    "qini_score",
                    "auuc_score",
                    "uplift_calibration_error",
                    "score_mean",
                    "unique_score_count",
                ]
            ].sort_values("qini_score", ascending=False)
        ),
        "pairwise_qini": _records(paired),
        "policy_budget_curve": _records(
            budget_curve.sort_values("budget_fraction")
        ),
        "main_policy_comparison": _records(
            main_policy.sort_values(
                "dr_net_scenario_value_per_customer",
                ascending=False,
            )
        ),
        "assumption_contract": {
            "monetary_outcome_available": False,
            "default_audience": 1_000_000,
            "default_value_per_conversion": 1.0,
            "default_contact_cost": 0.0005,
            "tested_contact_cost_per_value_ratios": [0, 0.00025, 0.0005, 0.001],
            "interpretation": (
                "Conversion-equivalent scenario. If a user enters currency, "
                "conversion value and contact cost must use the same currency. "
                "The result is a scenario estimate, not observed revenue/profit."
            ),
        },
        "causal_forest": {
            "status": "pending_external_kaggle_session",
            "local_code_path_smoke": "passed_at_0.1_percent_only",
            "required_stages": [0.20, 0.30, 0.50],
            "release_result_available": False,
        },
        "limitations": [
            "Offline RCT policy estimate; no production A/B deployment was run.",
            "Criteo contains conversion but no revenue, margin, or treatment cost.",
            "No individual is observed as Persuadable, Sure Thing, Lost Cause, or Sleeping Dog.",
            "Response is a ranking policy score, not a calibrated individual CATE.",
            "Causal Forest is not in the release until Kaggle gates produce real artifacts.",
        ],
    }


def main():
    sprint2_dir = OUTPUT_DIR / "sprint2"
    payload = build_payload(sprint2_dir)
    output = OUTPUT_DIR / "dashboard_data.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"[write] {output} schema={payload['schema_version']} "
        f"run={payload['meta']['run_id']}"
    )


if __name__ == "__main__":
    main()
