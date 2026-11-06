"""Causal retention models and decision metrics.

The undesirable outcome is churn (y=1).  Throughout this module, positive
uplift means churn prevented: E[Y(0) - Y(1) | X].
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

# Re-exported: the implementation lives in a module with no model dependencies so
# that serving code can use it without installing a training stack.
from .resampling import bootstrap_selected_effect  # noqa: F401

ModelKind = Literal["logistic", "rf", "hgb", "catboost"]


class CatBoostFrameClassifier(BaseEstimator):
    """Small sklearn-compatible wrapper that preserves native categorical inputs."""

    def __init__(
        self,
        *,
        seed: int,
        iterations: int = 250,
        depth: int = 5,
        learning_rate: float = 0.04,
        l2_leaf_reg: float = 10.0,
    ) -> None:
        self.seed = seed
        self.iterations = iterations
        self.depth = depth
        self.learning_rate = learning_rate
        self.l2_leaf_reg = l2_leaf_reg

    @staticmethod
    def _coerce(frame: pd.DataFrame) -> pd.DataFrame:
        prepared = frame.copy()
        for column in prepared:
            if not pd.api.types.is_numeric_dtype(prepared[column]):
                prepared[column] = prepared[column].fillna("__MISSING__").astype(str)
        return prepared

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply the fill values learned at fit time.

        Imputing from the incoming batch would make a prediction depend on the
        other rows scored alongside it, so a single row, a chunk and the full
        frame could disagree (mutation Q04).  The medians are therefore learned
        once, on training data, and reused unchanged at inference.
        """

        prepared = self._coerce(frame)
        for column, value in self.numeric_fill_.items():
            if column in prepared.columns and prepared[column].isna().any():
                prepared[column] = prepared[column].fillna(value)
        return prepared

    def fit(self, features: pd.DataFrame, outcome: np.ndarray) -> CatBoostFrameClassifier:
        coerced = self._coerce(features)
        self.numeric_fill_ = {
            column: (float(coerced[column].median()) if coerced[column].notna().any() else 0.0)
            for column in coerced.columns
            if pd.api.types.is_numeric_dtype(coerced[column])
        }
        prepared = self._prepare(features)
        self.feature_names_in_ = np.asarray(prepared.columns, dtype=object)
        self.categorical_features_ = [
            column for column in prepared if not pd.api.types.is_numeric_dtype(prepared[column])
        ]
        self.model_ = CatBoostClassifier(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            l2_leaf_reg=self.l2_leaf_reg,
            loss_function="Logloss",
            eval_metric="Logloss",
            random_seed=self.seed,
            allow_writing_files=False,
            verbose=False,
            thread_count=-1,
        )
        self.model_.fit(prepared, outcome, cat_features=self.categorical_features_)
        return self

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        prepared = self._prepare(features.loc[:, self.feature_names_in_])
        return np.asarray(self.model_.predict_proba(prepared), dtype=float)


def _feature_groups(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    categorical = [column for column in frame if not pd.api.types.is_numeric_dtype(frame[column])]
    numeric = [column for column in frame if column not in categorical]
    return numeric, categorical


def _preprocessor(frame: pd.DataFrame, *, dense: bool) -> ColumnTransformer:
    numeric, categorical = _feature_groups(frame)
    numeric_steps: list[tuple[str, BaseEstimator]] = [("imputer", SimpleImputer(strategy="median"))]
    if not dense:
        numeric_steps.append(("scaler", StandardScaler()))
    if dense:
        category_encoder: BaseEstimator = OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1
        )
    else:
        category_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    return ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), numeric),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", category_encoder),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
    )


def make_outcome_model(kind: ModelKind, frame: pd.DataFrame, *, seed: int) -> BaseEstimator:
    if kind == "logistic":
        model: BaseEstimator = LogisticRegression(
            C=0.3,
            max_iter=2_000,
            solver="liblinear",
            random_state=seed,
        )
        dense = False
    elif kind == "rf":
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=10,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        )
        dense = False
    elif kind == "hgb":
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=200,
            max_leaf_nodes=15,
            min_samples_leaf=30,
            l2_regularization=10.0,
            early_stopping=True,
            random_state=seed,
        )
        dense = True
    elif kind == "catboost":
        return CatBoostFrameClassifier(seed=seed)
    else:
        raise ValueError(f"Unknown outcome model kind: {kind}")
    return Pipeline([("preprocess", _preprocessor(frame, dense=dense)), ("model", model)])


def _fit_arm_models(
    kind: ModelKind,
    features: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    seed: int,
) -> tuple[BaseEstimator, BaseEstimator]:
    control = treatment == 0
    treated = treatment == 1
    if outcome[control].sum() < 2 or outcome[treated].sum() < 2:
        raise ValueError("Each treatment arm needs at least two positive outcomes")
    model_0 = make_outcome_model(kind, features, seed=seed).fit(
        features.loc[control], outcome[control]
    )
    model_1 = make_outcome_model(kind, features, seed=seed + 1).fit(
        features.loc[treated], outcome[treated]
    )
    return model_0, model_1


def _predict_positive(model: BaseEstimator, features: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(features)[:, 1], dtype=float)


@dataclass
class FittedPolicyModel:
    name: str
    model_0: BaseEstimator | None = None
    model_1: BaseEstimator | None = None
    single_model: BaseEstimator | None = None
    effect_model: BaseEstimator | None = None
    effect_model_1: BaseEstimator | None = None
    propensity: float | None = None

    def predict(self, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ranking score, predicted control risk, and predicted treated risk."""
        if self.name.startswith("risk_"):
            if self.model_0 is None:
                raise RuntimeError("Missing control outcome model")
            p0 = _predict_positive(self.model_0, features)
            return p0, p0, np.full(len(features), np.nan)
        if self.name.startswith("t_"):
            if self.model_0 is None or self.model_1 is None:
                raise RuntimeError("Missing T-learner arm model")
            p0 = _predict_positive(self.model_0, features)
            p1 = _predict_positive(self.model_1, features)
            return p0 - p1, p0, p1
        if self.name in {"s_hgb", "s_logistic"}:
            if self.single_model is None:
                raise RuntimeError("Missing S-learner model")
            control = _augment_s_features(
                features, treatment=0, interactions=self.name == "s_logistic"
            )
            treated = _augment_s_features(
                features, treatment=1, interactions=self.name == "s_logistic"
            )
            p0 = _predict_positive(self.single_model, control)
            p1 = _predict_positive(self.single_model, treated)
            return p0 - p1, p0, p1
        if self.name in {"dr_hgb", "dr_extratrees", "to_hgb", "r_hgb"}:
            if self.effect_model is None or self.model_0 is None or self.model_1 is None:
                raise RuntimeError("Incomplete DR-learner")
            score = np.clip(np.asarray(self.effect_model.predict(features), dtype=float), -1, 1)
            return (
                score,
                _predict_positive(self.model_0, features),
                _predict_positive(self.model_1, features),
            )
        if self.name == "x_hgb":
            if (
                self.effect_model is None
                or self.effect_model_1 is None
                or self.model_0 is None
                or self.model_1 is None
                or self.propensity is None
            ):
                raise RuntimeError("Incomplete X-learner")
            tau_0 = np.asarray(self.effect_model.predict(features), dtype=float)
            tau_1 = np.asarray(self.effect_model_1.predict(features), dtype=float)
            score = np.clip(self.propensity * tau_0 + (1 - self.propensity) * tau_1, -1, 1)
            return (
                score,
                _predict_positive(self.model_0, features),
                _predict_positive(self.model_1, features),
            )
        raise ValueError(f"Unknown fitted policy model: {self.name}")


def _augment_s_features(
    features: pd.DataFrame, *, treatment: int | np.ndarray, interactions: bool
) -> pd.DataFrame:
    treatment_values = np.asarray(treatment)
    if treatment_values.ndim == 0:
        treatment_values = np.full(len(features), treatment_values.item())
    treatment_frame = pd.DataFrame({"_treatment": treatment_values}, index=features.index)
    parts = [features, treatment_frame]
    if interactions:
        numeric, _ = _feature_groups(features)
        interactions_frame = features.loc[:, numeric].multiply(treatment_values, axis="index")
        interactions_frame.columns = [f"_tx_{column}" for column in numeric]
        parts.append(interactions_frame)
    return pd.concat(parts, axis="columns").copy()


def cross_fit_potential_outcomes(
    features: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    folds: int = 5,
    seed: int = 20260914,
    kind: ModelKind = "logistic",
) -> tuple[np.ndarray, np.ndarray]:
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=int)
    joint = treatment * 2 + outcome
    p0 = np.zeros(len(features), dtype=float)
    p1 = np.zeros(len(features), dtype=float)
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for fold, (train, valid) in enumerate(splitter.split(features, joint)):
        model_0, model_1 = _fit_arm_models(
            kind,
            features.iloc[train],
            treatment[train],
            outcome[train],
            seed=seed + 10 * fold,
        )
        p0[valid] = _predict_positive(model_0, features.iloc[valid])
        p1[valid] = _predict_positive(model_1, features.iloc[valid])
    return p0, p1


def doubly_robust_scores(
    outcome: np.ndarray,
    treatment: np.ndarray,
    p0: np.ndarray,
    p1: np.ndarray,
    propensity: float | np.ndarray,
) -> np.ndarray:
    """Orthogonal score for prevented churn, Y(0)-Y(1)."""
    y = np.asarray(outcome, dtype=float)
    t = np.asarray(treatment, dtype=float)
    m0 = np.clip(np.asarray(p0, dtype=float), 1e-6, 1 - 1e-6)
    m1 = np.clip(np.asarray(p1, dtype=float), 1e-6, 1 - 1e-6)
    e = np.clip(np.asarray(propensity, dtype=float), 1e-3, 1 - 1e-3)
    return m0 - m1 + (1 - t) * (y - m0) / (1 - e) - t * (y - m1) / e


def ipw_scores(
    outcome: np.ndarray, treatment: np.ndarray, propensity: float | np.ndarray
) -> np.ndarray:
    y = np.asarray(outcome, dtype=float)
    t = np.asarray(treatment, dtype=float)
    e = np.clip(np.asarray(propensity, dtype=float), 1e-3, 1 - 1e-3)
    return (1 - t) * y / (1 - e) - t * y / e


def fit_policy_model(
    name: str,
    features: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    propensity: float,
    seed: int = 20260914,
) -> FittedPolicyModel:
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=int)
    if name.startswith("risk_"):
        kind = name.removeprefix("risk_")
        if kind not in {"logistic", "rf", "hgb", "catboost"}:
            raise ValueError(f"Unknown risk model: {name}")
        control = treatment == 0
        model = make_outcome_model(kind, features, seed=seed).fit(
            features.loc[control], outcome[control]
        )
        return FittedPolicyModel(name=name, model_0=model)
    if name.startswith("t_"):
        kind = name.removeprefix("t_")
        if kind not in {"logistic", "rf", "hgb", "catboost"}:
            raise ValueError(f"Unknown T-learner: {name}")
        model_0, model_1 = _fit_arm_models(kind, features, treatment, outcome, seed=seed)
        return FittedPolicyModel(name=name, model_0=model_0, model_1=model_1)
    if name in {"s_hgb", "s_logistic"}:
        interactions = name == "s_logistic"
        augmented = _augment_s_features(features, treatment=treatment, interactions=interactions)
        kind: ModelKind = "logistic" if interactions else "hgb"
        model = make_outcome_model(kind, augmented, seed=seed).fit(augmented, outcome)
        return FittedPolicyModel(name=name, single_model=model)
    if name in {"dr_hgb", "dr_extratrees"}:
        p0_oof, p1_oof = cross_fit_potential_outcomes(
            features, treatment, outcome, folds=3, seed=seed, kind="logistic"
        )
        pseudo_outcome = doubly_robust_scores(outcome, treatment, p0_oof, p1_oof, propensity)
        if name == "dr_hgb":
            effect_estimator: BaseEstimator = HistGradientBoostingRegressor(
                learning_rate=0.04,
                max_iter=150,
                max_leaf_nodes=7,
                min_samples_leaf=80,
                l2_regularization=20.0,
                early_stopping=True,
                random_state=seed,
            )
        else:
            effect_estimator = ExtraTreesRegressor(
                n_estimators=300,
                max_depth=8,
                min_samples_leaf=40,
                max_features=0.5,
                n_jobs=-1,
                random_state=seed,
            )
        effect_model = Pipeline(
            [
                ("preprocess", _preprocessor(features, dense=True)),
                ("model", effect_estimator),
            ]
        ).fit(features, pseudo_outcome)
        model_0, model_1 = _fit_arm_models(
            "logistic", features, treatment, outcome, seed=seed + 100
        )
        return FittedPolicyModel(
            name=name,
            model_0=model_0,
            model_1=model_1,
            effect_model=effect_model,
        )
    if name in {"to_hgb", "r_hgb"}:
        if name == "to_hgb":
            pseudo_outcome = ipw_scores(outcome, treatment, propensity)
            sample_weight = None
        else:
            marginal_oof = np.zeros(len(features), dtype=float)
            joint = treatment * 2 + outcome
            splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
            for fold, (train, valid) in enumerate(splitter.split(features, joint)):
                marginal = make_outcome_model("logistic", features, seed=seed + 10 * fold).fit(
                    features.iloc[train], outcome[train]
                )
                marginal_oof[valid] = _predict_positive(marginal, features.iloc[valid])
            residual_treatment = treatment - propensity
            pseudo_outcome = -(outcome - marginal_oof) / residual_treatment
            sample_weight = residual_treatment**2
        effect_model = Pipeline(
            [
                ("preprocess", _preprocessor(features, dense=True)),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        learning_rate=0.04,
                        max_iter=150,
                        max_leaf_nodes=7,
                        min_samples_leaf=80,
                        l2_regularization=20.0,
                        early_stopping=True,
                        random_state=seed,
                    ),
                ),
            ]
        )
        fit_kwargs = {} if sample_weight is None else {"model__sample_weight": sample_weight}
        effect_model.fit(features, pseudo_outcome, **fit_kwargs)
        model_0, model_1 = _fit_arm_models(
            "logistic", features, treatment, outcome, seed=seed + 100
        )
        return FittedPolicyModel(
            name=name,
            model_0=model_0,
            model_1=model_1,
            effect_model=effect_model,
        )
    if name == "x_hgb":
        model_0, model_1 = _fit_arm_models("logistic", features, treatment, outcome, seed=seed)
        control = treatment == 0
        treated = treatment == 1
        # For positive prevented-churn effect tau=Y(0)-Y(1): controls use
        # observed Y(0)-m1(X); treated units use m0(X)-observed Y(1).
        effect_control = outcome[control] - _predict_positive(model_1, features.loc[control])
        effect_treated = _predict_positive(model_0, features.loc[treated]) - outcome[treated]

        def effect_regressor(regression_seed: int) -> Pipeline:
            return Pipeline(
                [
                    ("preprocess", _preprocessor(features, dense=True)),
                    (
                        "model",
                        HistGradientBoostingRegressor(
                            learning_rate=0.04,
                            max_iter=150,
                            max_leaf_nodes=7,
                            min_samples_leaf=80,
                            l2_regularization=20.0,
                            early_stopping=True,
                            random_state=regression_seed,
                        ),
                    ),
                ]
            )

        tau_0 = effect_regressor(seed + 10).fit(features.loc[control], effect_control)
        tau_1 = effect_regressor(seed + 20).fit(features.loc[treated], effect_treated)
        return FittedPolicyModel(
            name=name,
            model_0=model_0,
            model_1=model_1,
            effect_model=tau_0,
            effect_model_1=tau_1,
            propensity=propensity,
        )
    raise ValueError(f"Unknown policy model: {name}")


def top_fraction_mask(score: np.ndarray, ids: np.ndarray, fraction: float) -> np.ndarray:
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    score = np.asarray(score, dtype=float)
    ids = np.asarray(ids, dtype=str)
    if len(score) != len(ids):
        raise ValueError("score and ids must have the same length")
    k = max(1, math.ceil(len(score) * fraction))
    selected = np.lexsort((ids, -score))[:k]
    mask = np.zeros(len(score), dtype=bool)
    mask[selected] = True
    return mask


def curve_metrics(score: np.ndarray, effect_score: np.ndarray) -> dict[str, float]:
    """AUUC/Qini with an explicit, normalized pseudo-outcome convention."""
    score = np.asarray(score, dtype=float)
    effect = np.asarray(effect_score, dtype=float)
    order = np.argsort(-score, kind="stable")
    n = len(order)
    fraction = np.arange(1, n + 1, dtype=float) / n
    cumulative_gain = np.cumsum(effect[order]) / n
    auuc = float(np.trapezoid(cumulative_gain, fraction))
    ate = float(effect.mean())
    random_auuc = ate / 2
    return {
        "auuc": auuc,
        "qini": auuc - random_auuc,
        "ate_effect_score": ate,
        "random_auuc": random_auuc,
    }


def budget_table(
    score: np.ndarray,
    ids: np.ndarray,
    outcome: np.ndarray,
    treatment: np.ndarray,
    ipw_effect: np.ndarray,
    dr_effect: np.ndarray,
    *,
    budgets: tuple[float, ...] = (0.10, 0.20, 0.30),
) -> pd.DataFrame:
    y = np.asarray(outcome, dtype=int)
    t = np.asarray(treatment, dtype=int)
    rows = []
    for budget in budgets:
        selected = top_fraction_mask(score, ids, budget)
        selected_control = selected & (t == 0)
        selected_treated = selected & (t == 1)
        dr_uplift = float(np.mean(dr_effect[selected]))
        control_rate = float(y[selected_control].mean()) if selected_control.any() else math.nan
        treated_rate = float(y[selected_treated].mean()) if selected_treated.any() else math.nan
        rows.append(
            {
                "budget_fraction": budget,
                "selected_n": int(selected.sum()),
                "selected_control_n": int(selected_control.sum()),
                "selected_treated_n": int(selected_treated.sum()),
                "control_churn_rate": control_rate,
                "treated_churn_rate": treated_rate,
                "difference_in_means_uplift": control_rate - treated_rate,
                "ipw_uplift": float(np.mean(ipw_effect[selected])),
                "dr_uplift": dr_uplift,
                "dr_incremental_churns_prevented": float(selected.sum() * dr_uplift),
                "break_even_contact_cost_per_value_unit": dr_uplift,
            }
        )
    return pd.DataFrame(rows)


def ate_with_wald_interval(
    outcome: np.ndarray, treatment: np.ndarray, *, alpha_z: float = 1.959963984540054
) -> dict[str, float]:
    y = np.asarray(outcome, dtype=float)
    t = np.asarray(treatment, dtype=int)
    y0 = y[t == 0]
    y1 = y[t == 1]
    estimate = float(y0.mean() - y1.mean())
    standard_error = math.sqrt(y0.var(ddof=1) / len(y0) + y1.var(ddof=1) / len(y1))
    return {
        "control_churn_rate": float(y0.mean()),
        "treated_churn_rate": float(y1.mean()),
        "ate_prevented_churn": estimate,
        "standard_error": standard_error,
        "ci95_low": estimate - alpha_z * standard_error,
        "ci95_high": estimate + alpha_z * standard_error,
        "control_n": len(y0),
        "treated_n": len(y1),
    }


def required_sample_size(
    control_rate: float,
    treated_rate: float,
    treatment_fraction: float,
    effect: float,
    *,
    z_alpha: float = 1.959963984540054,
    z_power: float = 0.8416212335729143,
) -> int:
    """Approximate total RCT size for a two-sided two-proportion test."""
    if effect <= 0:
        raise ValueError("effect must be positive")
    if not 0 < treatment_fraction < 1:
        raise ValueError("treatment_fraction must be between zero and one")
    variance = control_rate * (1 - control_rate) / (1 - treatment_fraction)
    variance += treated_rate * (1 - treated_rate) / treatment_fraction
    return math.ceil((z_alpha + z_power) ** 2 * variance / effect**2)
