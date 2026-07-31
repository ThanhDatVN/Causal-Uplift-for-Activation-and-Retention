"""Synchronize the human-readable Sprint 2 JSON summary with release CSVs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import OUTPUT_DIR


def main():
    sprint2_dir = OUTPUT_DIR / "sprint2"
    manifest = json.loads(
        (sprint2_dir / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(sprint2_dir / "calibration_comparison.csv")
    policy = pd.read_csv(sprint2_dir / "policy_value_comparison.csv")
    summary = {
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "elapsed_seconds": manifest["elapsed_seconds"],
        "confirmation_rows": manifest["split"]["rows"]["confirmation"],
        "confirmation_metrics": metrics.loc[
            metrics["split"] == "confirmation"
        ].astype(object).where(pd.notna(metrics), None).to_dict(orient="records"),
        "main_policy_scenario": policy.astype(object).where(
            pd.notna(policy),
            None,
        ).to_dict(orient="records"),
        "limitations": [
            "Criteo has no revenue, margin, or treatment cost; scenario value is not actual profit.",
            "Causal Forest cloud learning curve remains pending until a Kaggle session is provided.",
            "No individual principal stratum is observed; policies are score-based offline rules.",
        ],
    }
    output = sprint2_dir / "sprint2_local_summary.json"
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {output}")


if __name__ == "__main__":
    main()
