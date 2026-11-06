"""Shared model loading and scoring used by both batch and online inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from telco_churn.schema import FEATURE_COLUMNS


def load_bundle(path: Path) -> dict[str, Any]:
    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or not {"model", "metadata"}.issubset(bundle):
        raise ValueError("Model artifact must contain model and metadata")
    artifact_features = bundle["metadata"].get("feature_columns")
    if artifact_features != FEATURE_COLUMNS:
        raise ValueError("Model artifact schema does not match application schema")
    return bundle


def prepare_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce CSV-like values and enforce the prediction-time feature contract."""
    missing = sorted(set(FEATURE_COLUMNS) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(FEATURE_COLUMNS))
    if missing or extra:
        raise ValueError(f"Feature mismatch; missing={missing}, extra={extra}")
    prepared = frame[FEATURE_COLUMNS].copy()
    object_columns = prepared.select_dtypes(include=["object", "string"]).columns
    for column in object_columns:
        prepared[column] = prepared[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    for column in ("SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"):
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    required_numeric = ["SeniorCitizen", "tenure", "MonthlyCharges"]
    if prepared[required_numeric].isna().any().any():
        raise ValueError("Required numeric fields contain blank or non-numeric values")
    if prepared[required_numeric + ["TotalCharges"]].lt(0).any().any():
        raise ValueError("Numeric features must be non-negative")
    invalid_total = prepared["TotalCharges"].isna() & prepared["tenure"].ne(0)
    if invalid_total.any():
        raise ValueError("TotalCharges may be missing only when tenure=0")
    invalid_phone = (
        prepared["PhoneService"].eq("No") & ~prepared["MultipleLines"].eq("No phone service")
    ) | (prepared["PhoneService"].eq("Yes") & prepared["MultipleLines"].eq("No phone service"))
    if invalid_phone.any():
        raise ValueError("PhoneService and MultipleLines are structurally inconsistent")
    add_ons = [
        "OnlineSecurity",
        "OnlineBackup",
        "DeviceProtection",
        "TechSupport",
        "StreamingTV",
        "StreamingMovies",
    ]
    no_internet = prepared["InternetService"].eq("No")
    invalid_internet = pd.Series(False, index=prepared.index)
    for column in add_ons:
        invalid_internet |= no_internet & ~prepared[column].eq("No internet service")
        invalid_internet |= ~no_internet & prepared[column].eq("No internet service")
    if invalid_internet.any():
        raise ValueError("InternetService and add-on fields are structurally inconsistent")
    return prepared


def score_frame(bundle: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    prepared = prepare_feature_frame(frame)
    probability = np.asarray(bundle["model"].predict_proba(prepared)[:, 1], dtype=float)
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("Model returned invalid probabilities")
    return probability
