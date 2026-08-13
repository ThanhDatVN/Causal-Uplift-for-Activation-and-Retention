"""Danh mục candidate model cho vòng cải tiến Sprint 3.

Mỗi candidate là một hàm ``builder(context) -> predict(X)``. Toàn bộ candidate
dùng chung:

- feature contract lúc ra quyết định chỉ có ``f0..f11``; không đưa
  ``visit``/``exposure`` vào ``predict(X)``;
- outcome ``conversion``;
- propensity hằng của thiết kế randomized, không fit ``e(X)`` từ ``X``.

Protocol data-optimization-v1 được phép dùng ``visit`` làm auxiliary *training
outcome* cho phép phân rã funnel. Nó không phải feature, không có mặt lúc scoring
và không thay đổi estimand conversion.

Score trả về của một số candidate có scale CATE (S/T/X/DR/R), số khác chỉ là
điểm ưu tiên (Response, Rank-Learner). Trường ``is_cate_scale`` quyết định
metric nào được tính; EUCE và DR risk chỉ áp dụng cho nhóm đầu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from econml.dml import NonParamDML
from econml.dr import DRLearner
from econml.metalearners import SLearner, TLearner, XLearner
from lightgbm import LGBMClassifier, LGBMRegressor
from scipy.special import expit, logit
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import StratifiedKFold

from src.baselines import BinaryProbabilityRegressor
from src.hybrid import HybridLogitStacker
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


class SentinelFeatureAugmenter:
    """Thêm mask point-mass được học chỉ từ ``X`` của fold train.

    Criteo không xác nhận đây là missing value, nên tên và API cố ý dùng
    ``sentinel``. Việc fit không đọc treatment/outcome; sample giới hạn đủ để
    nhận diện các point mass 40–99% mà EDA đã phát hiện, đồng thời tránh sort
    toàn bộ hàng triệu giá trị cho mỗi candidate.
    """

    def __init__(
        self,
        min_mode_share: float = 0.05,
        sample_size: int = 200_000,
        seed: int = 42,
    ):
        if not 0 < min_mode_share <= 1:
            raise ValueError("min_mode_share phải nằm trong (0, 1]")
        if sample_size < 1:
            raise ValueError("sample_size phải >= 1")
        self.min_mode_share = float(min_mode_share)
        self.sample_size = int(sample_size)
        self.seed = int(seed)

    def fit(self, X: np.ndarray) -> "SentinelFeatureAugmenter":
        matrix = np.asarray(X)
        if matrix.ndim != 2:
            raise ValueError("X phải là ma trận 2 chiều")
        if len(matrix) == 0:
            raise ValueError("Không thể fit sentinel augmenter trên X rỗng")
        if len(matrix) > self.sample_size:
            rng = np.random.default_rng(self.seed)
            rows = rng.choice(len(matrix), size=self.sample_size, replace=False)
            sample = matrix[rows]
        else:
            sample = matrix
        modes = []
        shares = []
        for column in range(sample.shape[1]):
            values, counts = np.unique(sample[:, column], return_counts=True)
            winner = int(np.argmax(counts))
            modes.append(values[winner])
            shares.append(float(counts[winner] / len(sample)))
        self.mode_values_ = np.asarray(modes, dtype=matrix.dtype)
        self.mode_shares_ = np.asarray(shares, dtype="float64")
        self.active_columns_ = np.flatnonzero(
            self.mode_shares_ >= self.min_mode_share
        )
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not hasattr(self, "active_columns_"):
            raise RuntimeError("SentinelFeatureAugmenter chưa được fit")
        matrix = np.asarray(X, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != len(self.mode_values_):
            raise ValueError("X transform không cùng số cột với X fit")
        # Preallocate the final matrix and fill one flag at a time.  Building a
        # separate dense ``flags`` matrix and then column-stacking it temporarily
        # held two copies of every flag, which is material on the 5.6M-row stage.
        n_rows, n_features = matrix.shape
        n_flags = len(self.active_columns_)
        transformed = np.empty(
            (n_rows, n_features + n_flags + 1),
            dtype="float32",
        )
        transformed[:, :n_features] = matrix
        count = np.zeros(n_rows, dtype="float32")
        for flag_index, column in enumerate(self.active_columns_):
            flag = matrix[:, column] == self.mode_values_[column]
            transformed[:, n_features + flag_index] = flag
            count += flag
        transformed[:, -1] = count
        return transformed

    def pattern_id(self, X: np.ndarray) -> np.ndarray:
        """Encode fold-local sentinel flags as a stable integer pattern."""
        if not hasattr(self, "active_columns_"):
            raise RuntimeError("SentinelFeatureAugmenter chưa được fit")
        matrix = np.asarray(X, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != len(self.mode_values_):
            raise ValueError("X pattern không cùng số cột với X fit")
        if len(self.active_columns_) > 62:
            raise ValueError("pattern_id chỉ hỗ trợ tối đa 62 cờ")
        flags = (
            matrix[:, self.active_columns_]
            == self.mode_values_[self.active_columns_]
        ).astype("int64")
        powers = np.left_shift(
            np.int64(1),
            np.arange(flags.shape[1], dtype="int64"),
        )
        return flags @ powers

    def transform_compact(self, X: np.ndarray) -> pd.DataFrame:
        """Return the same ordered features with compact flag dtypes.

        Pandas keeps raw inputs as float32 blocks while boolean flags and the
        count use one byte each.  This avoids upcasting every sentinel flag to
        float32 on full-development folds without changing feature values.
        """
        if not hasattr(self, "active_columns_"):
            raise RuntimeError("SentinelFeatureAugmenter chua duoc fit")
        matrix = np.asarray(X, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != len(self.mode_values_):
            raise ValueError("X transform khong cung so cot voi X fit")
        columns: dict[str, np.ndarray] = {
            f"raw_{column}": matrix[:, column]
            for column in range(matrix.shape[1])
        }
        count = np.zeros(len(matrix), dtype="uint8")
        for flag_index, column in enumerate(self.active_columns_):
            flag = matrix[:, column] == self.mode_values_[column]
            columns[f"sentinel_{flag_index}_f{column}"] = flag
            count += flag
        columns["sentinel_count"] = count
        return pd.DataFrame(columns, copy=False)


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
    outcome_name: str = "conversion"
    auxiliary_outcomes: dict[str, np.ndarray] = field(default_factory=dict)

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
                outcome_name=self.outcome_name,
                auxiliary_outcomes={
                    name: values[selected]
                    for name, values in self.auxiliary_outcomes.items()
                },
            ),
            factor,
        )


def _feature_view(
    context: FitContext,
) -> tuple[FitContext, Callable[[np.ndarray], np.ndarray]]:
    augmentation = context.params.get("feature_augmentation", "none")
    if augmentation == "none":
        return context, lambda X: np.asarray(X)
    if augmentation != "sentinel_flags":
        raise ValueError(f"feature_augmentation không hỗ trợ: {augmentation!r}")
    augmenter = SentinelFeatureAugmenter(
        min_mode_share=float(context.params.get("sentinel_min_mode_share", 0.05)),
        sample_size=int(context.params.get("sentinel_sample_size", 200_000)),
        seed=context.seed,
    ).fit(context.X)
    compact_threshold = int(
        context.params.get("sentinel_compact_threshold_rows", 1_000_000)
    )
    transform = (
        augmenter.transform_compact
        if len(context.X) >= compact_threshold
        else augmenter.transform
    )
    transformed = FitContext(
        X=transform(context.X),
        treatment=context.treatment,
        outcome=context.outcome,
        propensity=context.propensity,
        seed=context.seed,
        params=context.params,
        outcome_name=context.outcome_name,
        auxiliary_outcomes=context.auxiliary_outcomes,
    )
    return transformed, transform


def _outcome_model(kind: str, seed: int, params: dict | None):
    merged = lgbm_params(seed, params)
    if kind == "regressor":
        return LGBMRegressor(**merged)
    if kind == "classifier":
        return BinaryProbabilityRegressor(model_params=merged)
    raise ValueError(f"outcome model phải là 'regressor' hoặc 'classifier', nhận {kind!r}")


def build_response(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    fit_context, transform = _feature_view(context)
    model = LGBMClassifier(**lgbm_params(context.seed, context.params.get("params")))
    model.fit(fit_context.X, fit_context.outcome)
    return lambda X: model.predict_proba(transform(X))[:, 1]


def build_s_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    feature_context, transform = _feature_view(context)
    fit_context, factor = feature_context.undersampled()
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
    return lambda X: model.effect(transform(X)).ravel() / factor


def build_t_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    feature_context, transform = _feature_view(context)
    fit_context, factor = feature_context.undersampled()
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
    return lambda X: model.effect(transform(X)).ravel() / factor


def build_x_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    feature_context, transform = _feature_view(context)
    fit_context, factor = feature_context.undersampled()
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
    return lambda X: model.effect(transform(X)).ravel() / factor


def build_funnel_s_learner(context: FitContext) -> Callable[[np.ndarray], np.ndarray]:
    """Factorize conversion qua visit mà không dùng visit lúc scoring.

    Trong Criteo, ``conversion=1`` kéo theo ``visit=1`` chính xác. Bởi quy tắc
    xác suất, với mỗi treatment arm:

    ``P(conversion=1|X,T) = P(visit=1|X,T) × P(conversion=1|visit=1,X,T)``.

    Hai classifier S-style chia sẻ dữ liệu giữa treatment/control: model thứ
    nhất học visit trên mọi dòng; model thứ hai học conversion chỉ trên các
    dòng đã visit. ``visit`` chỉ là auxiliary training outcome/sample mask,
    không bao giờ được đưa vào ma trận feature hay API predict. Vì thế score
    vẫn chỉ dùng pre-treatment ``X`` và bao gồm toàn bộ đường dẫn treatment →
    visit → conversion thay vì điều chỉnh chặn mediator.
    """
    if context.outcome_name != "conversion":
        raise ValueError("funnel_s_learner chỉ hợp lệ cho outcome conversion")
    if "visit" not in context.auxiliary_outcomes:
        raise ValueError("funnel_s_learner cần auxiliary outcome visit")
    visit = np.asarray(context.auxiliary_outcomes["visit"], dtype="int8")
    if len(visit) != len(context.outcome):
        raise ValueError("visit và conversion phải có cùng độ dài")
    if np.any(context.outcome > visit):
        raise ValueError("Dữ liệu vi phạm invariant conversion <= visit")

    feature_context, transform = _feature_view(context)
    treatment_column = feature_context.treatment.astype("float32")[:, None]
    design = np.column_stack([feature_context.X, treatment_column])
    params = lgbm_params(context.seed, context.params.get("params"))
    visit_model = LGBMClassifier(**params)
    visit_model.fit(design, visit)

    visited = visit == 1
    visited_conversions = context.outcome[visited].sum()
    if visited_conversions == 0 or visited_conversions == visited.sum():
        raise ValueError("conversion|visit phải chứa cả hai lớp")
    conversion_model = LGBMClassifier(**{**params, "random_state": context.seed + 1})
    conversion_model.fit(design[visited], context.outcome[visited])

    def potential_conversion_probability(X: np.ndarray, arm: int) -> np.ndarray:
        features = transform(X)
        arm_column = np.full((len(features), 1), arm, dtype="float32")
        counterfactual_design = np.column_stack([features, arm_column])
        visit_probability = visit_model.predict_proba(counterfactual_design)[:, 1]
        conditional_conversion = conversion_model.predict_proba(
            counterfactual_design
        )[:, 1]
        return visit_probability * conditional_conversion

    return lambda X: (
        potential_conversion_probability(X, 1)
        - potential_conversion_probability(X, 0)
    )


def _validate_binary_context(context: FitContext) -> None:
    if context.outcome_name != "conversion":
        raise ValueError("Estimator này chỉ hợp lệ cho outcome conversion")
    if not 0 < context.propensity < 1:
        raise ValueError("propensity phải nằm trong (0, 1)")
    if not set(np.unique(context.treatment)).issubset({0, 1}):
        raise ValueError("treatment phải là nhị phân")
    if not set(np.unique(context.outcome)).issubset({0, 1}):
        raise ValueError("outcome phải là nhị phân")
    for arm in (0, 1):
        arm_outcome = context.outcome[context.treatment == arm]
        if len(arm_outcome) == 0 or np.unique(arm_outcome).size < 2:
            raise ValueError(f"Arm treatment={arm} phải chứa cả hai lớp outcome")


def _inner_folds(context: FitContext, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    if n_splits < 2:
        raise ValueError("inner_cv phải >= 2")
    strata = (
        context.treatment.astype("int64") * 2
        + context.outcome.astype("int64")
    )
    counts = np.bincount(strata, minlength=4)
    occupied = counts[counts > 0]
    if len(occupied) < 4 or int(occupied.min()) < n_splits:
        raise ValueError("Không đủ treatment/outcome strata cho inner cross-fitting")
    splitter = StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=context.seed,
    )
    return list(splitter.split(context.X, strata))


def _cross_fitted_marginal_probability(
    context: FitContext,
    *,
    n_splits: int,
    params: dict | None,
) -> tuple[np.ndarray, LGBMClassifier]:
    """Cross-fit m(x)=E[Y|X] and fit its deployable full-training counterpart."""
    oof = np.full(len(context.outcome), np.nan, dtype="float64")
    for fold_index, (train_idx, test_idx) in enumerate(
        _inner_folds(context, n_splits)
    ):
        model = LGBMClassifier(
            **lgbm_params(context.seed + fold_index, params)
        )
        model.fit(context.X[train_idx], context.outcome[train_idx])
        oof[test_idx] = model.predict_proba(context.X[test_idx])[:, 1]
    full_model = LGBMClassifier(**lgbm_params(context.seed + 100, params))
    full_model.fit(context.X, context.outcome)
    if not np.isfinite(oof).all():
        raise RuntimeError("Marginal nuisance OOF không hữu hạn")
    return oof, full_model


def _cross_fitted_arm_probabilities(
    context: FitContext,
    *,
    n_splits: int,
    params: dict | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Cross-fit mu0/mu1 within an outer training fold for DINA."""
    mu0 = np.full(len(context.outcome), np.nan, dtype="float64")
    mu1 = np.full(len(context.outcome), np.nan, dtype="float64")
    for fold_index, (train_idx, test_idx) in enumerate(
        _inner_folds(context, n_splits)
    ):
        for arm, target in ((0, mu0), (1, mu1)):
            arm_rows = train_idx[context.treatment[train_idx] == arm]
            model = LGBMClassifier(
                **lgbm_params(context.seed + 10 * fold_index + arm, params)
            )
            model.fit(context.X[arm_rows], context.outcome[arm_rows])
            target[test_idx] = model.predict_proba(context.X[test_idx])[:, 1]
    if not np.isfinite(mu0).all() or not np.isfinite(mu1).all():
        raise RuntimeError("Arm nuisance OOF không hữu hạn")
    return mu0, mu1


def _r_anchor_components(
    context: FitContext,
    *,
    n_splits: int,
    nuisance_params: dict | None,
) -> tuple[np.ndarray, LGBMClassifier, float, np.ndarray, np.ndarray]:
    """Return cross-fitted risk anchor and the exact weighted R-loss target."""
    marginal_oof, marginal_model = _cross_fitted_marginal_probability(
        context,
        n_splits=n_splits,
        params=nuisance_params,
    )
    treatment_residual = context.treatment.astype("float64") - context.propensity
    outcome_residual = context.outcome.astype("float64") - marginal_oof
    anchor_design = treatment_residual * marginal_oof
    denominator = float(np.dot(anchor_design, anchor_design))
    if denominator <= 0:
        raise ValueError("Không thể fit risk anchor: R-loss denominator bằng 0")
    alpha = float(np.dot(anchor_design, outcome_residual) / denominator)
    target = (
        outcome_residual - treatment_residual * alpha * marginal_oof
    ) / treatment_residual
    weight = np.square(treatment_residual)
    if not np.isfinite(target).all() or not np.isfinite(alpha):
        raise RuntimeError("R-loss target không hữu hạn")
    return marginal_oof, marginal_model, alpha, target, weight


def build_anchored_r_learner(
    context: FitContext,
) -> Callable[[np.ndarray], np.ndarray]:
    """Risk-anchored R-Learner with preregistered residual shrinkage.

    The anchor is the fold-local marginal response model. Only the orthogonal
    treatment residual is learned by the flexible final model, and its contribution
    is multiplied by ``residual_shrinkage`` to limit mistargeting variance.
    """
    _validate_binary_context(context)
    params = context.params
    inner_cv = int(params.get("inner_cv", 2))
    shrinkage = float(params.get("residual_shrinkage", 0.25))
    if not 0 <= shrinkage <= 1:
        raise ValueError("residual_shrinkage phải nằm trong [0, 1]")
    _, marginal_model, alpha, residual_target, residual_weight = (
        _r_anchor_components(
            context,
            n_splits=inner_cv,
            nuisance_params=params.get("nuisance_params"),
        )
    )
    feature_context, transform = _feature_view(context)
    residual_model = LGBMRegressor(
        **lgbm_params(context.seed, params.get("final_params", CATE_LGBM_PARAMS))
    )
    residual_model.fit(
        feature_context.X,
        residual_target,
        sample_weight=residual_weight,
    )

    def predict(X: np.ndarray) -> np.ndarray:
        marginal = marginal_model.predict_proba(np.asarray(X))[:, 1]
        residual = residual_model.predict(transform(X))
        return np.clip(alpha * marginal + shrinkage * residual, -1.0, 1.0)

    return predict


def build_anchored_pattern_r_learner(
    context: FitContext,
) -> Callable[[np.ndarray], np.ndarray]:
    """Partial-pool the R-loss residual over fold-local sentinel patterns."""
    _validate_binary_context(context)
    params = context.params
    prior_weight = float(params.get("pattern_prior_weight", 1000.0))
    if prior_weight < 0:
        raise ValueError("pattern_prior_weight phải >= 0")
    _, marginal_model, alpha, residual_target, residual_weight = (
        _r_anchor_components(
            context,
            n_splits=int(params.get("inner_cv", 2)),
            nuisance_params=params.get("nuisance_params"),
        )
    )
    augmenter = SentinelFeatureAugmenter(
        min_mode_share=float(params.get("sentinel_min_mode_share", 0.05)),
        sample_size=int(params.get("sentinel_sample_size", 200_000)),
        seed=context.seed,
    ).fit(context.X)
    pattern = augmenter.pattern_id(context.X)
    residual_lookup: dict[int, float] = {}
    for value in np.unique(pattern):
        rows = pattern == value
        numerator = float(
            np.dot(residual_weight[rows], residual_target[rows])
        )
        denominator = float(residual_weight[rows].sum() + prior_weight)
        residual_lookup[int(value)] = numerator / denominator

    def predict(X: np.ndarray) -> np.ndarray:
        matrix = np.asarray(X)
        marginal = marginal_model.predict_proba(matrix)[:, 1]
        pattern_id = augmenter.pattern_id(matrix)
        residual = np.fromiter(
            (residual_lookup.get(int(value), 0.0) for value in pattern_id),
            dtype="float64",
            count=len(pattern_id),
        )
        return np.clip(alpha * marginal + residual, -1.0, 1.0)

    return predict


class BinaryDINALoss:
    """Bernoulli negative log-likelihood for non-parametric DINA equation (30)."""

    def __init__(self, treatment_residual: np.ndarray, offset: np.ndarray):
        self.treatment_residual = np.asarray(
            treatment_residual,
            dtype="float64",
        )
        self.offset = np.asarray(offset, dtype="float64")
        if self.treatment_residual.shape != self.offset.shape:
            raise ValueError("DINA treatment residual và offset phải cùng shape")
        if not (
            np.isfinite(self.treatment_residual).all()
            and np.isfinite(self.offset).all()
        ):
            raise ValueError("DINA treatment residual/offset phải hữu hạn")

    def __call__(
        self,
        y_true: np.ndarray,
        raw_effect: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        linear_predictor = np.clip(
            self.offset + self.treatment_residual * raw_effect,
            -30.0,
            30.0,
        )
        probability = expit(linear_predictor)
        gradient = self.treatment_residual * (probability - y_true)
        hessian = (
            np.square(self.treatment_residual)
            * probability
            * (1.0 - probability)
        )
        return gradient, np.maximum(hessian, 1e-8)


def build_binary_dina_learner(
    context: FitContext,
) -> Callable[[np.ndarray], np.ndarray]:
    """Cross-fitted Bernoulli DINA, converted back to absolute CATE.

    ``delta(X)`` is learned on the conditional log-odds-ratio scale using the
    orthogonal nuisance construction of Gao & Hastie.  Policy evaluation remains
    on the registered absolute conversion-difference scale by combining ``delta``
    with a control-risk model fit only inside this outer training fold.
    """
    _validate_binary_context(context)
    params = context.params
    probability_clip = float(params.get("probability_clip", 1e-5))
    effect_clip = float(params.get("effect_clip", 3.0))
    if not 0 < probability_clip < 0.5:
        raise ValueError("probability_clip phải nằm trong (0, 0.5)")
    if effect_clip <= 0:
        raise ValueError("effect_clip phải > 0")

    mu0, mu1 = _cross_fitted_arm_probabilities(
        context,
        n_splits=int(params.get("inner_cv", 2)),
        params=params.get("nuisance_params"),
    )
    mu0 = np.clip(mu0, probability_clip, 1.0 - probability_clip)
    mu1 = np.clip(mu1, probability_clip, 1.0 - probability_clip)
    variance0 = mu0 * (1.0 - mu0)
    variance1 = mu1 * (1.0 - mu1)
    denominator = (
        context.propensity * variance1
        + (1.0 - context.propensity) * variance0
    )
    modified_propensity = context.propensity * variance1 / denominator
    eta0 = logit(mu0)
    eta1 = logit(mu1)
    offset = modified_propensity * eta1 + (1.0 - modified_propensity) * eta0
    treatment_residual = (
        context.treatment.astype("float64") - modified_propensity
    )

    feature_context, transform = _feature_view(context)
    final_params = lgbm_params(context.seed, params.get("final_params", CATE_LGBM_PARAMS))
    final_params["objective"] = BinaryDINALoss(treatment_residual, offset)
    final_params["boost_from_average"] = False
    effect_model = LGBMRegressor(**final_params)
    effect_model.fit(feature_context.X, context.outcome.astype("float64"))

    control_rows = context.treatment == 0
    control_model = LGBMClassifier(
        **lgbm_params(context.seed + 100, params.get("nuisance_params"))
    )
    control_model.fit(
        context.X[control_rows],
        context.outcome[control_rows],
    )

    def predict(X: np.ndarray) -> np.ndarray:
        matrix = np.asarray(X)
        p0 = np.clip(
            control_model.predict_proba(matrix)[:, 1],
            probability_clip,
            1.0 - probability_clip,
        )
        log_odds_effect = np.clip(
            effect_model.predict(transform(matrix)),
            -effect_clip,
            effect_clip,
        )
        p1 = expit(logit(p0) + log_odds_effect)
        return np.clip(p1 - p0, -1.0, 1.0)

    return predict


def _context_subset(
    context: FitContext,
    rows: np.ndarray,
    *,
    params: dict,
    seed: int,
) -> FitContext:
    """Subset a fit context without dropping fold-local auxiliary outcomes."""

    return FitContext(
        X=context.X[rows],
        treatment=context.treatment[rows],
        outcome=context.outcome[rows],
        propensity=context.propensity,
        seed=seed,
        params=params,
        outcome_name=context.outcome_name,
        auxiliary_outcomes={
            name: values[rows]
            for name, values in context.auxiliary_outcomes.items()
        },
    )


def _fit_control_probability(
    context: FitContext,
    *,
    params: dict | None,
    seed_offset: int = 0,
) -> Callable[[np.ndarray], np.ndarray]:
    """Fit the paper's baseline ``f(x)=P(Y(0)=1|X=x)`` on controls only."""

    control_rows = context.treatment == 0
    control_outcome = context.outcome[control_rows]
    if len(control_outcome) == 0 or np.unique(control_outcome).size < 2:
        raise ValueError("Control arm must contain both outcome classes")
    model = LGBMClassifier(
        **lgbm_params(context.seed + seed_offset, params)
    )
    model.fit(context.X[control_rows], control_outcome)
    return lambda X: model.predict_proba(np.asarray(X))[:, 1]


def _cross_fitted_hybrid_inputs(
    context: FitContext,
    *,
    n_splits: int,
    baseline_params: dict | None,
    effect_params: dict,
    include_cate: bool,
    baseline_builder=None,
    effect_builder=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build row-honest prognostic/CATE inputs inside one outer train fold.

    Dependency injection is private and exists so structural tests can prove
    that no inner validation row reaches either fitted nuisance.  Production
    callers always use a control-only LightGBM baseline and the locked binary
    DINA effect learner.
    """

    if baseline_builder is None:
        baseline_builder = _fit_control_probability
    if effect_builder is None:
        effect_builder = build_binary_dina_learner
    baseline_oof = np.full(len(context.outcome), np.nan, dtype="float64")
    cate_oof = np.zeros(len(context.outcome), dtype="float64")
    for fold_index, (train_idx, test_idx) in enumerate(
        _inner_folds(context, n_splits)
    ):
        # One inner-training copy is shared by the baseline and DINA fits.  The
        # baseline receives its own model params explicitly, while FitContext
        # params belong to DINA.
        inner_context = _context_subset(
            context,
            train_idx,
            params=effect_params,
            seed=context.seed + 1000 + fold_index,
        )
        baseline_predict = baseline_builder(
            inner_context,
            params=baseline_params,
            seed_offset=0,
        )
        baseline_oof[test_idx] = baseline_predict(context.X[test_idx])
        if include_cate:
            effect_predict = effect_builder(inner_context)
            cate_oof[test_idx] = effect_predict(context.X[test_idx])
            del effect_predict
        del baseline_predict, inner_context
    if not np.isfinite(baseline_oof).all() or not np.isfinite(cate_oof).all():
        raise RuntimeError("Hybrid inner OOF inputs must be finite and complete")
    return baseline_oof, cate_oof


def _build_hybrid_logit_candidate(
    context: FitContext,
    *,
    include_cate: bool,
) -> Callable[[np.ndarray], np.ndarray]:
    """Fit equation (2)/(3) with all calibration confined to outer training."""

    _validate_binary_context(context)
    params = context.params
    effect_params = params.get("effect_params", {})
    if not isinstance(effect_params, dict):
        raise ValueError("effect_params must be a dictionary")
    baseline_params = params.get("baseline_params")
    if baseline_params is not None and not isinstance(baseline_params, dict):
        raise ValueError("baseline_params must be a dictionary")
    inner_cv = int(params.get("stacker_inner_cv", 2))
    probability_clip = float(params.get("probability_clip", 1e-5))
    max_iter = int(params.get("stacker_max_iter", 1000))

    baseline_oof, cate_oof = _cross_fitted_hybrid_inputs(
        context,
        n_splits=inner_cv,
        baseline_params=baseline_params,
        effect_params=effect_params,
        include_cate=include_cate,
    )
    stacker = HybridLogitStacker(
        include_cate=include_cate,
        probability_clip=probability_clip,
        max_iter=max_iter,
    ).fit(
        baseline_oof,
        cate_oof,
        context.treatment,
        context.outcome,
    )

    baseline_predict = _fit_control_probability(
        context,
        params=baseline_params,
        seed_offset=3000,
    )
    if include_cate:
        # Reuse the outer-training arrays by reference.  Integer-indexing with
        # ``arange`` would create a second full copy on the multi-million-row
        # stage solely to change params/seed.
        full_effect_context = FitContext(
            X=context.X,
            treatment=context.treatment,
            outcome=context.outcome,
            propensity=context.propensity,
            seed=context.seed + 4000,
            params=effect_params,
            outcome_name=context.outcome_name,
            auxiliary_outcomes=context.auxiliary_outcomes,
        )
        effect_predict = build_binary_dina_learner(full_effect_context)
    else:
        effect_predict = lambda X: np.zeros(len(np.asarray(X)), dtype="float64")

    def predict(X: np.ndarray) -> np.ndarray:
        matrix = np.asarray(X)
        return stacker.effect(
            baseline_predict(matrix),
            effect_predict(matrix),
        )

    # Expose fold-local diagnostics to focused tests and future manifests without
    # changing the candidate callable contract used by the OOF runner.
    predict.stacker = stacker  # type: ignore[attr-defined]
    return predict


def build_logit_from_baseline(
    context: FitContext,
) -> Callable[[np.ndarray], np.ndarray]:
    """Athey--Keleher--Spiess equation (2), using control risk only."""

    return _build_hybrid_logit_candidate(context, include_cate=False)


def build_hybrid_logit_dina(
    context: FitContext,
) -> Callable[[np.ndarray], np.ndarray]:
    """Equation (3) with binary DINA as the single locked causal input."""

    return _build_hybrid_logit_candidate(context, include_cate=True)


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
    "funnel_s_learner": build_funnel_s_learner,
    "anchored_r_learner": build_anchored_r_learner,
    "anchored_pattern_r_learner": build_anchored_pattern_r_learner,
    "binary_dina_learner": build_binary_dina_learner,
    "logit_from_baseline": build_logit_from_baseline,
    "hybrid_logit_dina": build_hybrid_logit_dina,
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
