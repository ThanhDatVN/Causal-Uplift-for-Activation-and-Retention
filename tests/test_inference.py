import numpy as np
import pandas as pd
import pytest

from telco_churn.inference import prepare_feature_frame, score_frame
from telco_churn.schema import FEATURE_COLUMNS


class FixedModel:
    def predict_proba(self, frame):
        probability = np.full(len(frame), 0.4)
        return np.column_stack([1 - probability, probability])


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gender": "Female",
                "SeniorCitizen": 0,
                "Partner": "No",
                "Dependents": "No",
                "PhoneService": "No",
                "MultipleLines": "No phone service",
                "InternetService": "No",
                "OnlineSecurity": "No internet service",
                "OnlineBackup": "No internet service",
                "DeviceProtection": "No internet service",
                "TechSupport": "No internet service",
                "StreamingTV": "No internet service",
                "StreamingMovies": "No internet service",
                "Contract": "Month-to-month",
                "PaperlessBilling": "No",
                "PaymentMethod": "Mailed check",
                "tenure": 0,
                "MonthlyCharges": "20.0",
                "TotalCharges": " ",
            }
        ]
    )[FEATURE_COLUMNS]


def test_csv_whitespace_total_charges_is_coerced_at_tenure_zero() -> None:
    prepared = prepare_feature_frame(valid_frame())
    assert pd.isna(prepared.loc[0, "TotalCharges"])
    probability = score_frame(
        {"model": FixedModel(), "metadata": {"feature_columns": FEATURE_COLUMNS}},
        valid_frame(),
    )
    assert probability.tolist() == [0.4]


def test_structural_conflict_is_rejected() -> None:
    frame = valid_frame()
    frame.loc[0, "MultipleLines"] = "Yes"
    with pytest.raises(ValueError, match="structurally inconsistent"):
        prepare_feature_frame(frame)
