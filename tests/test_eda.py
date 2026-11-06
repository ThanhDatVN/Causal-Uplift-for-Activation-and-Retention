from pathlib import Path

import pandas as pd
import pytest

from telco_churn.eda import EXPECTED_COLUMNS, load_and_clean, run_eda, wilson_interval

DATA_PATH = Path("data/raw/Telco-Customer-Churn.csv")


@pytest.mark.skipif(not DATA_PATH.exists(), reason="Run scripts/fetch_data.ps1 first")
def test_official_sample_contract() -> None:
    data, quality = load_and_clean(DATA_PATH)

    assert len(data) == 7043
    assert quality["sha256"] == "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91"
    assert quality["duplicate_customer_ids"] == 0
    assert quality["blank_total_charges"] == 11
    assert quality["blank_total_charges_with_tenure_zero"] == 11
    assert set(data["Churn"]) == {"No", "Yes"}


def test_schema_mismatch_fails_before_analysis(tmp_path: Path) -> None:
    frame = pd.DataFrame({column: [] for column in EXPECTED_COLUMNS if column != "Churn"})
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="Schema mismatch"):
        load_and_clean(path)


def test_wilson_interval_contains_observed_rate() -> None:
    low, high = wilson_interval(25, 100)
    assert low < 0.25 < high


@pytest.mark.skipif(not DATA_PATH.exists(), reason="Run scripts/fetch_data.ps1 first")
def test_eda_writes_expected_artifacts(tmp_path: Path) -> None:
    summary = run_eda(DATA_PATH, tmp_path)

    assert summary["rows"] == 7043
    assert (tmp_path / "EDA_REPORT.md").exists()
    assert (tmp_path / "categorical_churn_rates.csv").exists()
    assert (tmp_path / "schema_profile.csv").exists()
    assert (tmp_path / "figures" / "tenure_contract_heatmap.png").exists()
