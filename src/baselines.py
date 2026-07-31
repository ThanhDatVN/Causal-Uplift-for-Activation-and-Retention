import numpy as np
from econml.dr import DRLearner
from econml.metalearners import SLearner, TLearner, XLearner
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.dummy import DummyClassifier

from src.calibration import restore_undersampled_probability


DEFAULT_LGBM_PARAMS = {
    "n_estimators": 200,
    "max_depth": 5,
    "verbose": -1,
}


class BinaryProbabilityRegressor(RegressorMixin, BaseEstimator):
    """Adapter để dùng xác suất lớp 1 của classifier ở API cần ``predict`` dạng regression.

    EconML S/T/X-Learner gọi ``predict`` của outcome model. Nếu truyền thẳng
    ``LGBMClassifier``, ``predict`` trả nhãn cứng 0/1 thay vì xác suất và làm hỏng phép
    trừ hai response surface. Adapter này giữ API scikit-learn có thể clone, nhưng trả
    ``predict_proba[:, 1]``.
    """

    def __init__(self, model_params: dict | None = None):
        self.model_params = model_params

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight=None):
        params = dict(self.model_params or {})
        self.model_ = LGBMClassifier(**params)
        self.model_.fit(X, y, sample_weight=sample_weight)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model_.predict_proba(X)[:, 1]


class UndersamplingCorrectedProbabilityRegressor(RegressorMixin, BaseEstimator):
    """Probability outcome model with exact post-undersampling restoration.

    ``negative_keep_prob`` is arm-specific. XLearner receives one instance for
    control and one for treatment, so it subtracts restored original-scale
    outcome probabilities rather than sampled probabilities.
    """

    def __init__(
        self,
        negative_keep_prob: float,
        model_params: dict | None = None,
    ):
        self.negative_keep_prob = negative_keep_prob
        self.model_params = model_params

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight=None):
        params = dict(self.model_params or {})
        self.model_ = LGBMClassifier(**params)
        self.model_.fit(X, y, sample_weight=sample_weight)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        sampled = self.model_.predict_proba(X)[:, 1]
        return restore_undersampled_probability(
            sampled,
            negative_keep_prob=self.negative_keep_prob,
        )


def _lgbm_params(seed: int, params: dict | None = None) -> dict:
    merged = {**DEFAULT_LGBM_PARAMS, "random_state": seed}
    if params:
        merged.update(params)
    return merged


def _outcome_model(kind: str, seed: int, params: dict | None = None):
    model_params = _lgbm_params(seed, params)
    if kind == "regressor":
        return LGBMRegressor(**model_params)
    if kind == "classifier":
        return BinaryProbabilityRegressor(model_params=model_params)
    raise ValueError(f"outcome_model phải là 'regressor' hoặc 'classifier', nhận được {kind!r}")


class ResponseBaseline:
    """Baseline marketing dự đoán P(conversion) và bỏ qua treatment.

    ``effect()`` trả propensity score để chấm khả năng ranking bằng Qini/AUUC trên cùng
    holdout. Score này không phải CATE và không xác định được principal stratum cá nhân.
    Release 29/07/2026: Qini 0.1879; paired CI tách được Response với T/DR, nhưng chưa
    tách được Response với S/X. Không nhúng kết luận nhân quả vào baseline này.
    """

    def __init__(self, seed: int = 42, model_params: dict | None = None):
        self.model = LGBMClassifier(**_lgbm_params(seed, model_params))

    def fit(self, X: np.ndarray, Y: np.ndarray):
        self.model.fit(X, Y)
        return self

    def effect(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]


def fit_response_baseline(
    X: np.ndarray,
    Y: np.ndarray,
    seed: int = 42,
    model_params: dict | None = None,
) -> ResponseBaseline:
    return ResponseBaseline(seed=seed, model_params=model_params).fit(X, Y)


def fit_s_learner(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    seed: int = 42,
    outcome_model: str = "regressor",
    model_params: dict | None = None,
) -> SLearner:
    """S-Learner học ``Y ~ f(X, T)`` rồi lấy hiệu hai potential-outcome predictions.

    Khi tín hiệu treatment nhỏ, regularization có thể làm model ít sử dụng treatment.
    Release 29/07/2026 đạt Qini 0.1772. Tỷ lệ score âm là đặc tính dự đoán
    model-dependent, không phải tỷ lệ ``Sleeping Dogs`` quan sát được.
    """
    model = SLearner(overall_model=_outcome_model(outcome_model, seed, model_params))
    model.fit(Y=Y, T=T, X=X)
    return model


def fit_t_learner(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    seed: int = 42,
    outcome_model: str = "regressor",
    model_params: dict | None = None,
) -> TLearner:
    model = TLearner(models=_outcome_model(outcome_model, seed, model_params))
    model.fit(Y=Y, T=T, X=X)
    return model


def fit_t_learner_exact_undersampling(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    negative_keep_prob_control: float,
    negative_keep_prob_treatment: float,
    seed: int = 42,
    model_params: dict | None = None,
) -> TLearner:
    """Double-classifier/T-Learner with exact arm-wise probability restoration.

    This is the direct implementation scope of Eq. 12 in Nyberg & Klami
    (2023): restore each sampled response probability, then take their
    difference. It does not add X-Learner imputation stages.
    """
    params = _lgbm_params(seed, model_params)
    outcome_models = [
        UndersamplingCorrectedProbabilityRegressor(
            negative_keep_prob=negative_keep_prob_control,
            model_params=params,
        ),
        UndersamplingCorrectedProbabilityRegressor(
            negative_keep_prob=negative_keep_prob_treatment,
            model_params=params,
        ),
    ]
    model = TLearner(models=outcome_models)
    model.fit(Y=Y, T=T, X=X)
    return model


def fit_x_learner(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    seed: int = 42,
    outcome_model: str = "regressor",
    model_params: dict | None = None,
    cate_model_params: dict | None = None,
    propensity: str = "estimated",
) -> XLearner:
    """Fit X-Learner với outcome model và CATE model được cấu hình riêng.

    ``propensity='fixed'`` dùng ``DummyClassifier(strategy='prior')``. Trên RCT này nó
    học đúng hằng số tỉ lệ gán treatment trong fold (xấp xỉ 0.85), thay vì học nhiễu từ X.
    Giữ ``estimated`` làm cấu hình cũ để A/B trên validation thay vì giả định trước bên nào tốt.
    """
    if propensity == "estimated":
        propensity_model = LGBMClassifier(**_lgbm_params(seed, model_params))
    elif propensity == "fixed":
        propensity_model = DummyClassifier(strategy="prior")
    else:
        raise ValueError(f"propensity phải là 'estimated' hoặc 'fixed', nhận được {propensity!r}")

    model = XLearner(
        models=_outcome_model(outcome_model, seed, model_params),
        cate_models=LGBMRegressor(**_lgbm_params(seed, cate_model_params or model_params)),
        propensity_model=propensity_model,
    )
    model.fit(Y=Y, T=T, X=X)
    return model


def fit_x_learner_exact_undersampling(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    negative_keep_prob_control: float,
    negative_keep_prob_treatment: float,
    seed: int = 42,
    model_params: dict | None = None,
    cate_model_params: dict | None = None,
) -> XLearner:
    """Research ablation: exact outcome restoration inside X-Learner imputation.

    Nyberg & Klami (2023) state that S/X learners may be compatible with some
    undersampling methods but leave their empirical evaluation to future work.
    This adapter is therefore not treated as a paper-validated release method.
    """
    params = _lgbm_params(seed, model_params)
    outcome_models = [
        UndersamplingCorrectedProbabilityRegressor(
            negative_keep_prob=negative_keep_prob_control,
            model_params=params,
        ),
        UndersamplingCorrectedProbabilityRegressor(
            negative_keep_prob=negative_keep_prob_treatment,
            model_params=params,
        ),
    ]
    model = XLearner(
        models=outcome_models,
        cate_models=LGBMRegressor(
            **_lgbm_params(seed, cate_model_params or model_params)
        ),
        propensity_model=DummyClassifier(strategy="prior"),
    )
    model.fit(Y=Y, T=T, X=X)
    return model


def fit_dr_learner(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    cv: int = 3,
    seed: int = 42,
    discrete_outcome: bool = False,
    regression_params: dict | None = None,
    final_params: dict | None = None,
    propensity: str = "fixed",
    mc_iters: int | None = None,
    mc_agg: str = "mean",
) -> DRLearner:
    """DR-Learner kết hợp outcome nuisance models và propensity qua pseudo-outcome.

    Propensity dùng `DummyClassifier(strategy="prior")` — trả về hằng số = tỉ lệ treatment thực
    nghiệm (≈0.85) cho mọi khách hàng. Dataset provenance mô tả randomized incrementality
    test; propensity AUC chỉ là balance diagnostic. Tính chất doubly robust cần các giả
    định identification/regularity và nói về nuisance consistency, không bảo đảm CATE
    finite-sample luôn không thiên lệch hoặc luôn thắng model khác.
    """
    if propensity == "fixed":
        propensity_model = DummyClassifier(strategy="prior")
    elif propensity == "estimated":
        propensity_model = LGBMClassifier(**_lgbm_params(seed, regression_params))
    else:
        raise ValueError(f"propensity phải là 'estimated' hoặc 'fixed', nhận được {propensity!r}")

    nuisance_params = _lgbm_params(seed, regression_params)
    nuisance_model = (
        LGBMClassifier(**nuisance_params)
        if discrete_outcome
        else LGBMRegressor(**nuisance_params)
    )
    model = DRLearner(
        model_propensity=propensity_model,
        model_regression=nuisance_model,
        model_final=LGBMRegressor(**_lgbm_params(seed, final_params or regression_params)),
        discrete_outcome=discrete_outcome,
        cv=cv,
        mc_iters=mc_iters,
        mc_agg=mc_agg,
        random_state=seed,
    )
    model.fit(Y=Y, T=T, X=X)
    return model
