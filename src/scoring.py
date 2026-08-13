"""Scorer có thể lưu xuống đĩa để batch scoring trong web app.

``src.candidates`` trả về closure nên không pickle được. Module này bọc đúng
những estimator đã fit vào một object picklable, kèm metadata đủ để truy nguồn:
tên candidate, config hash, split hash của dữ liệu fit, và thang điểm.

Scorer chỉ nhận 12 feature ``f0..f11`` theo đúng thứ tự của data contract. Nó
không nhận ``visit``/``exposure``; đó là post-treatment variable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from src.candidates import FitContext, lgbm_params
from src.data import FEATURES


@dataclass
class PersistedScorer:
    """Bọc một model đã fit và mô tả cách chuyển output thành điểm ưu tiên."""

    name: str
    family: str
    params: dict
    estimator: object
    scale_divisor: float = 1.0
    is_cate_scale: bool = True
    feature_names: list[str] = field(default_factory=lambda: list(FEATURES))
    metadata: dict = field(default_factory=dict)

    def score(self, X) -> np.ndarray:
        matrix = np.asarray(X, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != len(self.feature_names):
            raise ValueError(
                f"X phải có shape (n, {len(self.feature_names)}); nhận "
                f"{getattr(matrix, 'shape', None)}"
            )
        if not np.isfinite(matrix).all():
            raise ValueError("X phải hữu hạn; không có giá trị thiếu hoặc vô cực")
        if self.family == "response":
            raw = self.estimator.predict_proba(matrix)[:, 1]
        elif self.family == "rank_learner":
            raw = self.estimator.predict(matrix)
        else:
            raw = np.asarray(self.estimator.effect(matrix)).ravel()
        return np.asarray(raw, dtype="float64").ravel() / self.scale_divisor

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)
        return path

    @staticmethod
    def load(path: Path) -> "PersistedScorer":
        return joblib.load(path)


def _fit_estimator(family: str, context: FitContext):
    """Fit đúng estimator gốc và trả cả hệ số quy đổi thang điểm."""
    from econml.dr import DRLearner
    from econml.dml import NonParamDML
    from econml.metalearners import SLearner, TLearner, XLearner
    from lightgbm import LGBMClassifier, LGBMRegressor
    from sklearn.dummy import DummyClassifier

    from src.candidates import CATE_LGBM_PARAMS, _outcome_model
    from src.rank_learner import RankLearner

    params = context.params
    if family == "response":
        model = LGBMClassifier(**lgbm_params(context.seed, params.get("params")))
        model.fit(context.X, context.outcome)
        return model, 1.0

    if family in {"s_learner", "t_learner", "x_learner"}:
        fit_context, factor = context.undersampled()
        outcome_model = _outcome_model(
            params.get("outcome", "classifier" if family == "x_learner" else "regressor"),
            context.seed,
            params.get("params"),
        )
        if family == "s_learner":
            model = SLearner(overall_model=outcome_model)
        elif family == "t_learner":
            model = TLearner(models=outcome_model)
        else:
            propensity_setting = params.get("propensity", "fixed")
            if propensity_setting not in {"fixed", "estimated"}:
                raise ValueError(
                    "propensity phải là 'fixed' hoặc 'estimated', nhận "
                    f"{propensity_setting!r}"
                )
            propensity_model = (
                DummyClassifier(strategy="prior")
                if propensity_setting == "fixed"
                else LGBMClassifier(**lgbm_params(context.seed, params.get("params")))
            )
            model = XLearner(
                models=outcome_model,
                cate_models=LGBMRegressor(
                    **lgbm_params(
                        context.seed,
                        params.get("cate_params", CATE_LGBM_PARAMS),
                    )
                ),
                propensity_model=propensity_model,
            )
        model.fit(
            Y=fit_context.outcome.astype("float64"),
            T=fit_context.treatment.astype("float64"),
            X=fit_context.X,
        )
        return model, factor

    if family in {"dr_learner", "r_learner"}:
        discrete_outcome = bool(params.get("discrete_outcome", False))
        nuisance_params = lgbm_params(context.seed, params.get("params"))
        final_model = LGBMRegressor(
            **lgbm_params(context.seed, params.get("final_params", CATE_LGBM_PARAMS))
        )
        if family == "dr_learner":
            model = DRLearner(
                model_propensity=DummyClassifier(strategy="prior"),
                model_regression=(
                    LGBMClassifier(**nuisance_params)
                    if discrete_outcome
                    else LGBMRegressor(**nuisance_params)
                ),
                model_final=final_model,
                discrete_outcome=discrete_outcome,
                cv=int(params.get("cv", 3)),
                mc_iters=params.get("mc_iters"),
                random_state=context.seed,
            )
        else:
            model = NonParamDML(
                model_y=(
                    LGBMClassifier(**nuisance_params)
                    if discrete_outcome
                    else LGBMRegressor(**nuisance_params)
                ),
                model_t=DummyClassifier(strategy="prior"),
                model_final=final_model,
                discrete_treatment=True,
                discrete_outcome=discrete_outcome,
                cv=int(params.get("cv", 3)),
                mc_iters=params.get("mc_iters"),
                random_state=context.seed,
            )
        model.fit(
            Y=context.outcome.astype("float64"),
            T=context.treatment.astype("float64"),
            X=context.X,
        )
        return model, 1.0

    if family == "rank_learner":
        model = RankLearner(
            kappa_scale=float(params.get("kappa_scale", 1.0)),
            n_folds=int(params.get("cv", 3)),
            seed=context.seed,
            rank_params=params.get("rank_params"),
            nuisance_params=params.get("params"),
        )
        model.fit(
            context.X,
            context.treatment,
            context.outcome,
            propensity=context.propensity,
        )
        return model, 1.0

    raise ValueError(f"family {family!r} chưa được hỗ trợ cho persisted scorer")


def fit_persisted_scorer(
    spec,
    X: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    propensity: float,
    seed: int = 42,
    metadata: dict | None = None,
) -> PersistedScorer:
    """Fit một candidate và bọc thành scorer lưu được."""
    context = FitContext(
        X=X,
        treatment=treatment,
        outcome=outcome,
        propensity=propensity,
        seed=seed,
        params=spec.params,
    )
    estimator, factor = _fit_estimator(spec.family, context)
    payload = {
        "fitted_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows": int(len(outcome)),
        "propensity": float(propensity),
        "seed": int(seed),
    }
    payload.update(metadata or {})
    return PersistedScorer(
        name=spec.name,
        family=spec.family,
        params=dict(spec.params),
        estimator=estimator,
        scale_divisor=float(factor),
        is_cate_scale=bool(spec.is_cate_scale),
        metadata=payload,
    )
