from pathlib import Path

import pandas as pd

from telco_churn.data import (
    DATA_SHA256,
    create_or_load_split_manifest,
    load_modeling_data,
)
from telco_churn.eda import sha256_file

RAW_PATH = Path("data/raw/Telco-Customer-Churn.csv")


def test_reviewed_dataset_checksum_and_modeling_schema() -> None:
    assert sha256_file(RAW_PATH) == DATA_SHA256
    features, target, customer_ids, quality = load_modeling_data(RAW_PATH)
    assert features.shape == (7_043, 19)
    assert int(target.sum()) == 1_869
    assert customer_ids.is_unique
    assert quality["blank_total_charges"] == 11


def test_split_manifest_is_reproducible_and_frozen(tmp_path: Path) -> None:
    _, target, customer_ids, _ = load_modeling_data(RAW_PATH)
    path = tmp_path / "manifest.csv"
    first = create_or_load_split_manifest(customer_ids, target, path)
    second = create_or_load_split_manifest(customer_ids, target, path)
    pd.testing.assert_frame_equal(first, second)
    assert first["split"].value_counts().to_dict() == {"development": 5_634, "test": 1_409}
    assert first.groupby("split")["target_at_split"].mean().between(0.26, 0.27).all()


def test_split_manifest_rejects_target_drift(tmp_path: Path) -> None:
    _, target, customer_ids, _ = load_modeling_data(RAW_PATH)
    path = tmp_path / "manifest.csv"
    create_or_load_split_manifest(customer_ids, target, path)
    modified = target.copy()
    modified.iloc[0] = 1 - modified.iloc[0]
    try:
        create_or_load_split_manifest(customer_ids, modified, path)
    except ValueError as error:
        assert "Targets changed" in str(error)
    else:
        raise AssertionError("Target drift should be rejected")
