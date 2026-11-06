"""Score a CSV with the immutable model artifact and optionally create a campaign plan."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from telco_churn.inference import load_bundle, score_frame
from telco_churn.policy import DEFAULT_SCENARIOS, plan_campaign
from telco_churn.schema import FEATURE_COLUMNS, ID_COLUMN


def run_batch(
    input_path: Path,
    output_path: Path,
    model_path: Path,
    *,
    budget_fraction: float | None = None,
) -> pd.DataFrame:
    data = pd.read_csv(input_path)
    required = {ID_COLUMN, *FEATURE_COLUMNS}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")
    bundle = load_bundle(model_path)
    scores = score_frame(bundle, data[FEATURE_COLUMNS])
    if budget_fraction is None:
        result = pd.DataFrame(
            {
                ID_COLUMN: data[ID_COLUMN],
                "risk_30d": scores,
                "model_version": bundle["metadata"]["artifact_version"],
            }
        ).sort_values(["risk_30d", ID_COLUMN], ascending=[False, True])
    else:
        result = plan_campaign(
            data[ID_COLUMN],
            scores,
            data["MonthlyCharges"],
            DEFAULT_SCENARIOS[1],
            budget_fraction=budget_fraction,
        )
        result["model_version"] = bundle["metadata"]["artifact_version"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("artifacts/models/champion.joblib"))
    parser.add_argument("--budget-fraction", type=float)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    result = run_batch(
        arguments.input,
        arguments.output,
        arguments.model,
        budget_fraction=arguments.budget_fraction,
    )
    print(f"Wrote {len(result)} rows to {arguments.output}")


if __name__ == "__main__":
    main()
