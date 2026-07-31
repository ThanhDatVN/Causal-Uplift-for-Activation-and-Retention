"""Audit Criteo từ raw file và xuất data manifest cho Sprint 1.

Chạy:
    .venv/Scripts/python.exe scripts/audit_criteo.py --balance-frac 0.05

Balance diagnostics chạy trên sample stratified để vừa RAM/thời gian. Các số
schema/rate/ATE được tính trên toàn bộ file local.
"""
import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import (
    FEATURES,
    load_criteo_full,
    propensity_auc,
    standardized_mean_difference_by_treatment,
    stratified_sample,
    validate_criteo_schema,
)
from src.paths import CRITEO_PATH, OUTPUT_DIR, REPO_ROOT


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _difference_in_means(df: pd.DataFrame, outcome: str) -> dict:
    treated = df.loc[df["treatment"] == 1, outcome].to_numpy(dtype="float64")
    control = df.loc[df["treatment"] == 0, outcome].to_numpy(dtype="float64")
    estimate = float(treated.mean() - control.mean())
    standard_error = math.sqrt(
        float(treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control))
    )
    return {
        "outcome": outcome,
        "treated_mean": float(treated.mean()),
        "control_mean": float(control.mean()),
        "difference_in_means": estimate,
        "standard_error": standard_error,
        "ci_95_low": estimate - 1.96 * standard_error,
        "ci_95_high": estimate + 1.96 * standard_error,
        "n_treated": int(len(treated)),
        "n_control": int(len(control)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = load_criteo_full(dtype_f32=True)
    contract = validate_criteo_schema(df)
    if not contract["valid"]:
        raise ValueError(f"Data contract failed: {contract}")

    balance_df = stratified_sample(df, frac=args.balance_frac, seed=args.seed)
    smd = standardized_mean_difference_by_treatment(balance_df, FEATURES)
    auc = propensity_auc(balance_df, FEATURES, seed=args.seed)
    arm_summary = (
        df.groupby("treatment")
        .agg(
            row_count=("conversion", "size"),
            conversion_rate=("conversion", "mean"),
            conversion_count=("conversion", "sum"),
            visit_rate=("visit", "mean"),
            visit_count=("visit", "sum"),
            exposure_rate=("exposure", "mean"),
            exposure_count=("exposure", "sum"),
        )
        .reset_index()
    )

    sprint_dir = OUTPUT_DIR / "sprint1"
    sprint_dir.mkdir(parents=True, exist_ok=True)
    smd.to_csv(sprint_dir / "balance_smd.csv", index=False)
    arm_summary.to_csv(sprint_dir / "arm_outcome_summary.csv", index=False)

    manifest = {
        "dataset": "Criteo Uplift v2.1 local file",
        "path": CRITEO_PATH.relative_to(REPO_ROOT).as_posix(),
        "file_size_bytes": int(CRITEO_PATH.stat().st_size),
        "sha256": _sha256(CRITEO_PATH),
        "python": platform.python_version(),
        "schema_contract": contract,
        "feature_policy": {
            "allowed_pre_treatment_features": FEATURES,
            "treatment": "treatment",
            "primary_outcome": "conversion",
            "excluded_from_features": ["visit", "exposure"],
        },
        "rates": {
            "treatment": float(df["treatment"].mean()),
            "conversion": float(df["conversion"].mean()),
            "visit": float(df["visit"].mean()),
            "exposure": float(df["exposure"].mean()),
        },
        "difference_in_means": {
            outcome: _difference_in_means(df, outcome)
            for outcome in ["conversion", "visit", "exposure"]
        },
        "balance_diagnostics": {
            "sample_fraction": args.balance_frac,
            "sample_rows": int(len(balance_df)),
            "holdout_propensity_auc": float(auc),
            "max_abs_smd": float(smd["abs_smd"].max()),
            "median_abs_smd": float(smd["abs_smd"].median()),
            "interpretation": (
                "Diagnostics describe observed covariate balance; provenance of random "
                "assignment comes from the dataset documentation, not from AUC/SMD alone."
            ),
        },
    }
    manifest_path = sprint_dir / "data_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    print(f"[write] {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
