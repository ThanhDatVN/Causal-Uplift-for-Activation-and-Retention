"""Danh mục candidate model cho vòng cải tiến Sprint 3.

Mỗi candidate là một hàm ``builder(context) -> predict(X)``. Toàn bộ candidate
dùng chung:

- feature contract ``f0..f11``; không dùng ``visit``/``exposure``;
- outcome ``conversion``;
- propensity hằng của thiết kế randomized, không fit ``e(X)`` từ ``X``.

Score trả về của một số candidate có scale CATE (S/T/X/DR/R), số khác chỉ là
điểm ưu tiên (Response, Rank-Learner). Trường ``is_cate_scale`` quyết định
metric nào được tính; EUCE và DR risk chỉ áp dụng cho nhóm đầu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from econml.dml import NonParamDML
from econml.dr import DRLearner
from econml.metalearners import SLearner, TLearner, XLearner
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.dummy import DummyClassifier

from src.baselines import BinaryProbabilityRegressor
from src.rank_learner import RankLearner


BASE_LGBM_PARAMS = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 1000,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "colsample_bytree": 0.9,
    "verbose": -1,
}

CATE_LGBM_PARAMS = {
    **BASE_LGBM_PARAMS,
    "min_child_samples": 2500,
    "reg_lambda": 10.0,
}


def lgbm_params(seed: int, overrides: dict | None = None) -> dict:
    return {**BASE_LGBM_PARAMS, "random_state": seed, **(overrides or {})}


def rare_outcome_undersample_indices(
    treatment: np.ndarray,
    outcome: np.ndarray,
    factor: float,
    seed: int = 42,
) -> np.ndarray:
    """Phiên bản mảng của :func:`src.data.rare_outcome_undersample`.

    Giữ toàn bộ positive và giữ negative của **mỗi arm** với xác suất
    ``s_t = (1/k − p_t) / (1 − p_t)``, trong đó ``p_t`` là conversion rate của
    arm đó. Công thức theo Nyberg et al. (2021); dùng chung một tỷ lệ negative
    cho hai arm sẽ đổi uplift nên không được phép.
    """
    if factor < 1:
        raise ValueError("factor phải >= 1")
    if factor == 1:
        return np.arange(len(outcome))
    rng = np.random.default_rng(seed)
    keep: list[np.ndarray] = []
    for arm in (0, 1):
        arm_rows = np.flatnonzero(treatment == arm)
        arm_outcome = outcome[arm_rows]
        positive_rate = float(arm_outcome.mean())
        if positive_rate <= 0:
            raise ValueError(f"Arm treatment={arm} không có positive outcome")
        if factor >= 1.0 / positive_rate:
            raise ValueError(
                f"factor={factor} quá lớn cho arm treatment={arm}; "
                f"cần factor < {1.0 / positive_rate:.3f}"
            )
        keep_rate = (1.0 / factor - positive_rate) / (1.0 - positive_rate)
        positives = arm_rows[arm_outcome == 1]
        negatives = arm_rows[arm_outcome == 0]
        n_keep = int(round(len(negatives) * keep_rate))
        keep.append(positives)
        keep.append(rng.choice(negatives, size=n_keep, replace=False))
    return np.sort(np.concatenate(keep))


@dataclass
class FitContext:
    """Dữ liệu và tham số truyền cho mọi builder."""

    X: np.ndarray
    treatment: np.ndarray
    outcome: np.ndarray
    propensity: float
    seed: int
    params: dict = field(default_factory=dict)

    def undersampled(self) -> tuple["FitContext", float]:
        """Áp dụng undersampling nếu ``params['under'] > 1``."""
        factor = float(self.params.get("under", 1.0))
        if factor <= 1.0:
            return self, 1.0
        selected = rare_outcome_undersample_indices(
            self.treatment,
            self.outcome,
            factor=factor,
            seed=self.seed,
        )
        return (
            FitContext(
                X=self.X[selected],
                treatment=self.treatment[selected],
                outcome=self.outcome[selected],
                propensity=self.propensity,
                seed=self.seed,
                params=self.params,
            ),
            factor,
        )


def _outcome_model(kind: str, seed: int, params: dict | None):
    merged = lgbm_params(seed, params)
    if kind == "regressor":
        return LGBMRegressor(**merged)
    if kind == "classifier":
        return BinaryProbabilityRegressor(model_params=merged)
    raise ValueError(f"outcome model phải là 'regressor' hoặc 'classifier', nhận {kind!r}")


def build_response(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    model = LGBMClassifier(**lgbm_params(context.seed, context.params.get("params")))
    model.fit(context.X, context.outcome)
    return lambda X: model.predict_proba(X)[:, 1]


def build_s_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    fit_context, factor = context.undersampled()
    model = SLearner(
        overall_model=_outcome_model(
            context.params.get("outcome", "regressor"),
            context.seed,
            context.params.get("params"),
        )
    )
    model.fit(
        Y=fit_context.outcome.astype("float64"),
        T=fit_context.treatment.astype("float64"),
        X=fit_context.X,
    )
    return lambda X: model.effect(X).ravel() / factor


def build_t_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    fit_context, factor = context.undersampled()
    model = TLearner(
        models=_outcome_model(
            context.params.get("outcome", "regressor"),
            context.seed,
            context.params.get("params"),
        )
    )
    model.fit(
        Y=fit_context.outcome.astype("float64"),
        T=fit_context.treatment.astype("float64"),
        X=fit_context.X,
    )
    return lambda X: model.effect(X).ravel() / factor


def build_x_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    fit_context, factor = context.undersampled()
    propensity_setting = context.params.get("propensity", "fixed")
    if propensity_setting == "fixed":
        propensity_model = DummyClassifier(strategy="prior")
    elif propensity_setting == "estimated":
        propensity_model = LGBMClassifier(
            **lgbm_params(context.seed, context.params.get("params"))
        )
    else:
        raise ValueError(
            f"propensity phải là 'fixed' hoặc 'estimated', nhận {propensity_setting!r}"
        )
    model = XLearner(
        models=_outcome_model(
            context.params.get("outcome", "classifier"),
            context.seed,
            context.params.get("params"),
        ),
        cate_models=LGBMRegressor(
            **lgbm_params(
                context.seed,
                context.params.get("cate_params", CATE_LGBM_PARAMS),
            )
        ),
        propensity_model=propensity_model,
    )
    model.fit(
        Y=fit_context.outcome.astype("float64"),
        T=fit_context.treatment.astype("float64"),
        X=fit_context.X,
    )
    return lambda X: model.effect(X).ravel() / factor


def build_dr_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    params = context.params
    discrete_outcome = bool(params.get("discrete_outcome", False))
    nuisance_params = lgbm_params(context.seed, params.get("params"))
    model = DRLearner(
        model_propensity=DummyClassifier(strategy="prior"),
        model_regression=(
            LGBMClassifier(**nuisance_params)
            if discrete_outcome
            else LGBMRegressor(**nuisance_params)
        ),
        model_final=LGBMRegressor(
            **lgbm_params(context.seed, params.get("final_params", CATE_LGBM_PARAMS))
        ),
        discrete_outcome=discrete_outcome,
        cv=int(params.get("cv", 3)),
        mc_iters=params.get("mc_iters"),
        mc_agg=params.get("mc_agg", "mean"),
        random_state=context.seed,
    )
    model.fit(
        Y=context.outcome.astype("float64"),
        T=context.treatment.astype("float64"),
        X=context.X,
    )
    return lambda X: model.effect(X).ravel()


def build_r_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    """R-Learner qua ``NonParamDML``.

    ``model_t`` là ``DummyClassifier(strategy='prior')`` nên residual treatment
    dùng đúng tỷ lệ gán của thiết kế, không học propensity giả từ ``X``. Đây là
    hiện thực Robinson residualization của Nie & Wager (2021) trong EconML.
    """
    params = context.params
    discrete_outcome = bool(params.get("discrete_outcome", False))
    outcome_params = lgbm_params(context.seed, params.get("params"))
    model = NonParamDML(
        model_y=(
            LGBMClassifier(**outcome_params)
            if discrete_outcome
            else LGBMRegressor(**outcome_params)
        ),
        model_t=DummyClassifier(strategy="prior"),
        model_final=LGBMRegressor(
            **lgbm_params(context.seed, params.get("final_params", CATE_LGBM_PARAMS))
        ),
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
    return lambda X: model.effect(X).ravel()


def build_rank_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    params = context.params
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
    return model.predict


BUILDERS: dict[str, Callable[[FitContext], Callable[[np.ndarray], np.ndarray]]] = {
    "response": build_response,
    "s_learner": build_s_learner,
    "t_learner": build_t_learner,
    "x_learner": build_x_learner,
    "dr_learner": build_dr_learner,
    "r_learner": build_r_learner,
    "rank_learner": build_rank_learner,
}


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    family: str
    builder: str
    params: dict
    is_cate_scale: bool
    hypothesis: str

    def build(self, context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
        if self.builder not in BUILDERS:
            raise KeyError(
                f"builder {self.builder!r} chưa đăng ký; có {sorted(BUILDERS)}"
            )
        return BUILDERS[self.builder](context)

    def as_config(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "builder": self.builder,
            "params": self.params,
            "is_cate_scale": self.is_cate_scale,
        }


def candidate_from_dict(payload: dict) -> CandidateSpec:
    return CandidateSpec(
        name=payload["name"],
        family=payload.get("family", payload["builder"]),
        builder=payload["builder"],
        params=payload.get("params", {}),
        is_cate_scale=bool(payload.get("is_cate_scale", True)),
        hypothesis=payload.get("hypothesis", ""),
    )
