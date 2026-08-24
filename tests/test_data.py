"""Hợp đồng dữ liệu Criteo, và các phép chia không được chồng lấn.

Bốn loại lỗi bị bắt ở đây:

1. **File dữ liệu đổi mà không ai biết** — kiểm hình dạng, tỷ lệ treatment và tỷ lệ
   conversion so với hằng số đã đăng ký.
2. **Split chồng lấn.** `stratified_complement` phải cho ra phần bù *rời nhau và phủ kín*.
   Nếu nó chồng lấn, confirmation Sprint 2 sẽ chứa dòng đã dùng ở Sprint 1 mà không metric
   nào phát hiện được.
3. **Schema hỏng lọt qua** — cột thiếu, nhãn nhị phân nhận giá trị phân số.
4. **Chẩn đoán cân bằng mất độ nhạy.** `test_standardized_mean_difference_detects_injected_imbalance`
   cố ý bơm lệch vào dữ liệu để chắc rằng SMD **phát hiện được**; một phép chẩn đoán không
   bao giờ báo động thì vô dụng.
"""

import numpy as np

from src.paths import CRITEO_PATH
from src.data import (
    FEATURES,
    ks_test_by_treatment,
    propensity_auc,
    rare_outcome_undersample,
    standardized_mean_difference_by_treatment,
    stratified_complement,
    stratified_sample,
    validate_criteo_schema,
)

import pytest

# Ca file can data/criteo-research-uplift-v2.1.csv.gz: nap toan bo Criteo va kiem hop dong du lieu.
# Khong co du lieu thi chay: pytest -m "not requires_criteo"
pytestmark = pytest.mark.requires_criteo


def test_criteo_path_exists():
    assert CRITEO_PATH.exists()


def test_load_criteo_full_shape(full_df):
    assert full_df.shape == (13_979_592, 16)


def test_load_criteo_full_treatment_rate(full_df):
    assert 0.83 <= full_df["treatment"].mean() <= 0.87


def test_load_criteo_full_conversion_rate(full_df):
    assert 0.0025 <= full_df["conversion"].mean() <= 0.0035


def test_stratified_sample_preserves_rates(full_df, sample_5pct):
    full_treatment = full_df["treatment"].mean()
    full_conversion = full_df["conversion"].mean()
    assert abs(sample_5pct["treatment"].mean() - full_treatment) < 0.005
    assert abs(sample_5pct["conversion"].mean() - full_conversion) < 0.005


def test_stratified_complement_is_disjoint_and_exhaustive():
    import pandas as pd

    df = pd.DataFrame(
        {
            "row_id": np.arange(400),
            "treatment": np.repeat([0, 1], 200),
            "conversion": np.tile(np.repeat([0, 1], 100), 2),
        }
    ).set_index("row_id", drop=False)
    selected = stratified_sample(df, frac=0.5, seed=42)
    complement = stratified_complement(df, selected_frac=0.5, seed=42)

    assert set(selected["row_id"]).isdisjoint(set(complement["row_id"]))
    assert set(selected["row_id"]) | set(complement["row_id"]) == set(df["row_id"])
    assert len(selected) == len(complement) == 200
    assert selected.groupby(["treatment", "conversion"]).size().nunique() == 1
    assert complement.groupby(["treatment", "conversion"]).size().nunique() == 1


def test_propensity_auc_near_chance_for_current_diagnostic(sample_5pct):
    auc = propensity_auc(sample_5pct, FEATURES, seed=42)
    assert 0.48 <= auc <= 0.52


def test_ks_test_negative_control(sample_5pct):
    df = sample_5pct.copy()
    df["fake_biased"] = df["treatment"] * 10 + 1
    result = ks_test_by_treatment(df, FEATURES + ["fake_biased"])
    fake_row = result.loc[result["feature"] == "fake_biased"].iloc[0]
    assert fake_row["p_value"] < 0.01


def test_rare_outcome_undersample_scales_each_arm_equally(sample_1pct):
    factor = 10
    sampled = rare_outcome_undersample(sample_1pct, factor=factor, seed=42)
    before = sample_1pct.groupby("treatment")["conversion"].mean()
    after = sampled.groupby("treatment")["conversion"].mean()

    np.testing.assert_allclose(after.to_numpy(), factor * before.to_numpy(), rtol=0.01)
    before_positive = sample_1pct["conversion"].sum()
    after_positive = sampled["conversion"].sum()
    assert after_positive == before_positive


def test_criteo_schema_contract(sample_1pct):
    result = validate_criteo_schema(sample_1pct)
    assert result["valid"]
    assert result["missing_columns"] == []
    assert result["all_features_finite"]


def test_criteo_schema_contract_rejects_missing_outcome(sample_1pct):
    df = sample_1pct.head(100).copy()
    df.loc[df.index[0], "conversion"] = np.nan
    result = validate_criteo_schema(df)
    assert not result["valid"]
    assert result["missing_cells"] == 1


def test_criteo_schema_contract_reports_missing_feature_without_crashing(sample_1pct):
    df = sample_1pct.head(100).drop(columns=["f3"])
    result = validate_criteo_schema(df)
    assert not result["valid"]
    assert result["missing_columns"] == ["f3"]
    assert not result["all_features_finite"]


def test_criteo_schema_contract_rejects_fractional_binary_value(sample_1pct):
    df = sample_1pct.head(100).copy()
    df["treatment"] = df["treatment"].astype("float64")
    df.loc[df.index[0], "treatment"] = 0.5
    result = validate_criteo_schema(df)
    assert not result["valid"]
    assert 0.5 in result["invalid_binary_columns"]["treatment"]


def test_standardized_mean_difference_detects_injected_imbalance(sample_1pct):
    df = sample_1pct.copy()
    df["fake_biased"] = df["treatment"] * 5.0
    result = standardized_mean_difference_by_treatment(df, FEATURES + ["fake_biased"])
    assert result.loc[result["feature"] == "fake_biased", "abs_smd"].iloc[0] > 1
