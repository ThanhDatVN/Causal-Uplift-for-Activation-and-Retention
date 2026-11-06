"""Leak-resistant preprocessing and estimator factories."""

from __future__ import annotations

from typing import Any

from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from telco_churn.schema import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def make_preprocessor(*, dense: bool, drop_sensitive: bool = False) -> ColumnTransformer:
    categorical = list(CATEGORICAL_FEATURES)
    if drop_sensitive:
        categorical = [
            column for column in categorical if column not in {"gender", "SeniorCitizen"}
        ]
    numeric_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot",
                OneHotEncoder(handle_unknown="ignore", sparse_output=not dense),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, categorical),
        ],
        remainder="drop",
    )


def build_estimator(name: str, *, seed: int, drop_sensitive: bool = False) -> Any:
    if name == "dummy_prior":
        return Pipeline(
            [
                ("preprocess", make_preprocessor(dense=False, drop_sensitive=drop_sensitive)),
                ("model", DummyClassifier(strategy="prior", random_state=seed)),
            ]
        )
    if name == "dummy_most_frequent":
        return Pipeline(
            [
                ("preprocess", make_preprocessor(dense=False, drop_sensitive=drop_sensitive)),
                ("model", DummyClassifier(strategy="most_frequent", random_state=seed)),
            ]
        )
    if name in {"logistic", "logistic_no_sensitive"}:
        return Pipeline(
            [
                (
                    "preprocess",
                    make_preprocessor(
                        dense=False,
                        drop_sensitive=drop_sensitive or name == "logistic_no_sensitive",
                    ),
                ),
                (
                    "model",
                    LogisticRegression(max_iter=2_000, solver="liblinear", random_state=seed),
                ),
            ]
        )
    if name == "hist_gradient_boosting":
        return Pipeline(
            [
                ("preprocess", make_preprocessor(dense=True, drop_sensitive=drop_sensitive)),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        random_state=seed,
                        early_stopping=True,
                        validation_fraction=0.15,
                        n_iter_no_change=20,
                    ),
                ),
            ]
        )
    if name == "catboost":
        categorical = tuple(CATEGORICAL_FEATURES)
        if drop_sensitive:
            categorical = tuple(
                column for column in categorical if column not in {"gender", "SeniorCitizen"}
            )
        return CatBoostClassifier(
            cat_features=categorical,
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
            thread_count=1,
            loss_function="Logloss",
            eval_metric="PRAUC",
        )
    raise ValueError(f"Unknown estimator: {name}")


def parameter_space(name: str, *, quick: bool = False) -> tuple[dict[str, list], int]:
    if name in {"dummy_prior", "dummy_most_frequent"}:
        return {}, 1
    if name in {"logistic", "logistic_no_sensitive"}:
        values = {
            "model__C": [0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
            "model__class_weight": [None, "balanced"],
        }
        return values, 4 if quick else 12
    if name == "hist_gradient_boosting":
        values = {
            "model__learning_rate": [0.03, 0.05, 0.08, 0.12],
            "model__max_leaf_nodes": [7, 15, 31],
            "model__min_samples_leaf": [10, 20, 40, 80],
            "model__l2_regularization": [0.0, 1.0, 5.0, 10.0],
            "model__max_iter": [150, 250, 400],
        }
        return values, 4 if quick else 20
    if name == "catboost":
        values = {
            "depth": [4, 5, 6, 7],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "l2_leaf_reg": [3.0, 5.0, 10.0, 20.0],
            "iterations": [200, 350, 500],
            "auto_class_weights": ["None", "Balanced"],
        }
        return values, 4 if quick else 20
    raise ValueError(f"Unknown estimator: {name}")
