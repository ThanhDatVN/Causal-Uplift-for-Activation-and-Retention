"""Hybrid prognostic–causal stacking, phương trình 2 và 3.

Nguồn: Athey, Keleher & Spiess, Journal of Econometrics 2025. Module đã hiện thực nhưng
**chưa có dòng nào trong registry** — nó là mục M1 của kế hoạch, chưa chạy.

Bốn điều được khóa:

- **Phương trình 3 chứa CATE thô đúng nguyên dạng**, không bị biến đổi ngầm;
- **Phương trình 2 khôi phục được submodel log-odds hằng số** khi dữ liệu đúng dạng đó;
- **Stacker tất định trên outcome nhị phân hiếm** — chế độ dễ mất tính tất định nhất;
- **Đầu vào của tầng trong chỉ được dự đoán bởi model không chứa dòng đó.** Vi phạm điều
  này là leakage bên trong chính stacker, và nó không hiện ra ở bất kỳ metric nào.
"""

import numpy as np
import pytest
from scipy.special import expit, logit

from src.candidates import (
    FitContext,
    _cross_fitted_hybrid_inputs,
    build_hybrid_logit_dina,
    build_logit_from_baseline,
)
from src.hybrid import (
    HybridLogitStacker,
    hybrid_logit_effect_from_coefficients,
    hybrid_logit_transforms,
)
from src.policy import doubly_robust_effect_signal


SMALL_NUISANCE = {
    "n_estimators": 10,
    "learning_rate": 0.12,
    "num_leaves": 7,
    "min_child_samples": 20,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
}
SMALL_FINAL = {
    "n_estimators": 14,
    "learning_rate": 0.10,
    "num_leaves": 7,
    "min_child_samples": 30,
    "reg_alpha": 0.0,
    "reg_lambda": 2.0,
}


def test_equation_three_contains_raw_cate_exactly():
    baseline = np.array([0.02, 0.10, 0.35, 0.70])
    cate = np.array([0.01, -0.03, 0.08, -0.15])
    # a_f=b_g=1 and all other coefficients zero gives
    # eta0=logit(f), eta1=logit(f)+g=logit(f+tau).
    coefficients = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 1.0])

    effect = hybrid_logit_effect_from_coefficients(
        baseline,
        cate,
        coefficients,
    )

    np.testing.assert_allclose(effect, cate, rtol=1e-12, atol=1e-12)


def test_equation_two_recovers_constant_log_odds_submodel():
    baseline = np.array([0.002, 0.02, 0.20, 0.60])
    beta = 0.7
    expected = expit(logit(baseline) + beta) - baseline

    effect = hybrid_logit_effect_from_coefficients(
        baseline,
        np.zeros_like(baseline),
        np.array([0.0, 1.0, beta]),
        include_cate=False,
    )

    np.testing.assert_allclose(effect, expected, rtol=1e-12, atol=1e-12)


def test_hybrid_stacker_is_deterministic_on_rare_binary_outcome():
    rng = np.random.default_rng(71)
    n = 6_000
    baseline = expit(-4.2 + 0.7 * rng.normal(size=n))
    cate = 0.006 * np.tanh(rng.normal(size=n))
    treatment = rng.binomial(1, 0.85, size=n)
    probability = np.clip(baseline + treatment * cate, 1e-6, 1.0 - 1e-6)
    outcome = rng.binomial(1, probability)

    first = HybridLogitStacker().fit(
        baseline,
        cate,
        treatment,
        outcome,
    )
    second = HybridLogitStacker().fit(
        baseline,
        cate,
        treatment,
        outcome,
    )

    np.testing.assert_allclose(first.coefficients_, second.coefficients_)
    np.testing.assert_allclose(
        first.effect(baseline, cate),
        second.effect(baseline, cate),
    )


def test_inner_hybrid_inputs_are_predicted_only_by_models_excluding_each_row():
    rows_per_stratum = 8
    treatment = np.repeat([0, 0, 1, 1], rows_per_stratum).astype("int8")
    outcome = np.repeat([0, 1, 0, 1], rows_per_stratum).astype("int8")
    row_id = np.arange(len(treatment), dtype="float32")
    X = np.column_stack([row_id, np.sin(row_id)]).astype("float32")
    context = FitContext(
        X=X,
        treatment=treatment,
        outcome=outcome,
        propensity=0.5,
        seed=13,
    )
    baseline_scored: set[int] = set()
    effect_scored: set[int] = set()

    def spy_baseline(fit_context, *, params, seed_offset):
        del params, seed_offset
        fitted_ids = set(fit_context.X[:, 0].astype(int))

        def predict(matrix):
            scored_ids = set(np.asarray(matrix)[:, 0].astype(int))
            assert fitted_ids.isdisjoint(scored_ids)
            baseline_scored.update(scored_ids)
            return np.full(len(scored_ids), 0.2)

        return predict

    def spy_effect(fit_context):
        fitted_ids = set(fit_context.X[:, 0].astype(int))

        def predict(matrix):
            scored_ids = set(np.asarray(matrix)[:, 0].astype(int))
            assert fitted_ids.isdisjoint(scored_ids)
            effect_scored.update(scored_ids)
            return np.full(len(scored_ids), 0.01)

        return predict

    baseline_oof, cate_oof = _cross_fitted_hybrid_inputs(
        context,
        n_splits=2,
        baseline_params={},
        effect_params={},
        include_cate=True,
        baseline_builder=spy_baseline,
        effect_builder=spy_effect,
    )

    assert baseline_scored == set(range(len(context.outcome)))
    assert effect_scored == set(range(len(context.outcome)))
    np.testing.assert_allclose(baseline_oof, 0.2)
    np.testing.assert_allclose(cate_oof, 0.01)


def test_registered_builders_return_finite_cate_on_rare_imbalanced_rct():
    rng = np.random.default_rng(91)
    n_train = 12_000
    n_test = 4_000
    X = rng.normal(size=(n_train + n_test, 3)).astype("float32")
    treatment = rng.binomial(1, 0.85, size=len(X)).astype("int8")
    p0 = expit(-4.1 + 0.7 * X[:, 0])
    log_odds_effect = 0.35 + 0.55 * np.tanh(X[:, 1])
    p1 = expit(logit(p0) + log_odds_effect)
    outcome = rng.binomial(
        1,
        np.where(treatment == 1, p1, p0),
    ).astype("int8")
    params = {
        "stacker_inner_cv": 2,
        "probability_clip": 1e-5,
        "baseline_params": SMALL_NUISANCE,
        "effect_params": {
            "inner_cv": 2,
            "probability_clip": 1e-5,
            "effect_clip": 3.0,
            "nuisance_params": SMALL_NUISANCE,
            "final_params": SMALL_FINAL,
        },
    }
    context = FitContext(
        X=X[:n_train],
        treatment=treatment[:n_train],
        outcome=outcome[:n_train],
        propensity=0.85,
        seed=17,
        params=params,
    )

    baseline_predict = build_logit_from_baseline(context)
    hybrid_predict = build_hybrid_logit_dina(context)
    baseline_score = baseline_predict(X[n_train:])
    hybrid_score = hybrid_predict(X[n_train:])

    for score in (baseline_score, hybrid_score):
        assert np.isfinite(score).all()
        assert np.all((-1.0 <= score) & (score <= 1.0))
        assert np.std(score) > 1e-5
    assert len(baseline_predict.stacker.coefficients_) == 3
    assert len(hybrid_predict.stacker.coefficients_) == 6


@pytest.mark.parametrize("propensity", [0.15, 0.5, 0.85])
def test_dr_signal_is_exact_racer_cmo_pseudo_outcome(propensity):
    treatment = np.array([0, 1, 1, 0, 1, 0], dtype="float64")
    outcome = np.array([0, 1, 0, 1, 1, 0], dtype="float64")
    mu0 = np.array([0.01, 0.02, 0.05, 0.30, 0.40, 0.70])
    mu1 = np.array([0.02, 0.08, 0.03, 0.50, 0.35, 0.80])
    dr_signal = doubly_robust_effect_signal(
        outcome,
        treatment,
        mu0,
        mu1,
        propensity=propensity,
    )
    signed_treatment = 2.0 * treatment - 1.0
    arm_probability = np.where(treatment == 1, propensity, 1.0 - propensity)
    cmo = (1.0 - propensity) * mu1 + propensity * mu0
    racer_signal = signed_treatment * (outcome - cmo) / arm_probability

    np.testing.assert_allclose(dr_signal, racer_signal, rtol=1e-14, atol=1e-14)


def test_hybrid_transform_reports_boundary_clipping_and_validates_inputs():
    _, _, diagnostics = hybrid_logit_transforms(
        np.array([0.0, 0.2, 1.0]),
        np.array([0.0, -0.4, 0.2]),
        probability_clip=1e-4,
    )
    assert diagnostics["baseline_clip_fraction"] == pytest.approx(2 / 3)
    assert diagnostics["treated_probability_clip_fraction"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="probability_clip"):
        HybridLogitStacker(probability_clip=0.5)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        hybrid_logit_transforms([1.1], [0.0])
