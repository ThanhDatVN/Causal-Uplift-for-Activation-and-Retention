"""Dataset acquisition, validation, modeling frame, and frozen split utilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from telco_churn.eda import EXPECTED_COLUMNS, SOURCE_URL, load_and_clean, sha256_file
from telco_churn.schema import (
    DATA_SHA256,
    FEATURE_COLUMNS,
    ID_COLUMN,
    SPLIT_SEED,
)


def fetch_dataset(output_path: Path, source_url: str = SOURCE_URL) -> Path:
    """Fetch the IBM sample and fail if its content is not the reviewed version."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(source_url, timeout=60) as response:
        content = response.read()
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != DATA_SHA256:
        raise ValueError(f"Dataset checksum mismatch: expected {DATA_SHA256}, got {actual_hash}")
    output_path.write_bytes(content)
    return output_path


def validate_modeling_data(data: pd.DataFrame) -> None:
    """Enforce assumptions that must hold before preprocessing/model fitting."""
    if list(data.columns[: len(EXPECTED_COLUMNS)]) != EXPECTED_COLUMNS:
        raise ValueError("Raw columns are not in the reviewed order")
    if data[ID_COLUMN].isna().any() or data[ID_COLUMN].duplicated().any():
        raise ValueError("customerID must be complete and unique")
    unexpected_total_missing = data["TotalCharges"].isna() & data["tenure"].ne(0)
    if unexpected_total_missing.any():
        raise ValueError("TotalCharges is missing outside the reviewed tenure=0 condition")
    if data["tenure"].lt(0).any() or data["MonthlyCharges"].lt(0).any():
        raise ValueError("Numeric features must be non-negative")


def load_modeling_data(path: Path) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    data, quality = load_and_clean(path)
    validate_modeling_data(data)
    features = data[FEATURE_COLUMNS].copy()
    target = data["churn_flag"].astype("int8")
    customer_ids = data[ID_COLUMN].astype("string")
    return features, target, customer_ids, quality


def create_or_load_split_manifest(
    customer_ids: pd.Series,
    target: pd.Series,
    output_path: Path,
    *,
    seed: int = SPLIT_SEED,
    test_size: float = 0.2,
) -> pd.DataFrame:
    """Create the frozen holdout exactly once, or validate and reuse it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        manifest = pd.read_csv(output_path, dtype={ID_COLUMN: "string"})
        required = {ID_COLUMN, "split", "target_at_split", "seed"}
        if set(manifest.columns) != required:
            raise ValueError("Existing split manifest has an unexpected schema")
        if set(manifest[ID_COLUMN]) != set(customer_ids):
            raise ValueError("Existing split manifest does not match current customer IDs")
        if manifest[ID_COLUMN].duplicated().any():
            raise ValueError("Existing split manifest contains duplicate IDs")
        target_lookup = dict(zip(customer_ids, target, strict=True))
        expected_target = manifest[ID_COLUMN].map(target_lookup).astype(int)
        if not expected_target.equals(manifest["target_at_split"].astype(int)):
            raise ValueError("Targets changed after the split manifest was frozen")
        if manifest["seed"].nunique() != 1 or int(manifest["seed"].iloc[0]) != seed:
            raise ValueError("Existing split manifest seed does not match protocol")
        return manifest

    indices = pd.RangeIndex(len(customer_ids))
    _development_index, test_index = train_test_split(
        indices,
        test_size=test_size,
        random_state=seed,
        stratify=target,
    )
    split = pd.Series("development", index=indices)
    split.loc[test_index] = "test"
    manifest = pd.DataFrame(
        {
            ID_COLUMN: pd.Series(customer_ids.to_numpy(), dtype="string"),
            "split": split.to_numpy(),
            "target_at_split": target.astype("int64").to_numpy(),
            "seed": seed,
        }
    )
    manifest.to_csv(output_path, index=False)
    return manifest


def split_by_manifest(
    features: pd.DataFrame,
    target: pd.Series,
    customer_ids: pd.Series,
    manifest: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
    split_lookup = dict(zip(manifest[ID_COLUMN], manifest["split"], strict=True))
    assigned_split = customer_ids.map(split_lookup)
    if assigned_split.isna().any():
        raise ValueError("Some customer IDs are absent from the split manifest")
    development_mask = assigned_split.eq("development")
    test_mask = assigned_split.eq("test")
    if not (development_mask | test_mask).all():
        raise ValueError("Unknown split label in manifest")
    return (
        features.loc[development_mask].reset_index(drop=True),
        features.loc[test_mask].reset_index(drop=True),
        target.loc[development_mask].reset_index(drop=True),
        target.loc[test_mask].reset_index(drop=True),
        customer_ids.loc[development_mask].reset_index(drop=True),
        customer_ids.loc[test_mask].reset_index(drop=True),
    )


def anonymize_customer_id(customer_id: str) -> str:
    return hashlib.sha256(f"telcochurn-portfolio:{customer_id}".encode()).hexdigest()[:12]


def split_manifest_metadata(path: Path) -> dict[str, str | int]:
    manifest = pd.read_csv(path)
    return {
        "path": path.as_posix(),
        "sha256": sha256_file(path),
        "rows": len(manifest),
        "development_rows": int(manifest["split"].eq("development").sum()),
        "test_rows": int(manifest["split"].eq("test").sum()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch_parser = subparsers.add_parser("fetch", help="Download and verify the IBM sample")
    fetch_parser.add_argument(
        "--output", type=Path, default=Path("data/raw/Telco-Customer-Churn.csv")
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    if arguments.command == "fetch":
        path = fetch_dataset(arguments.output)
        print(json.dumps({"path": str(path), "sha256": sha256_file(path)}, indent=2))


if __name__ == "__main__":
    main()
