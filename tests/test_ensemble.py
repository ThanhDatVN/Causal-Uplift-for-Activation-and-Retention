"""Chọn và tổ hợp model bằng doubly robust loss.

Q-aggregation phải cho ra trọng số nằm trên **simplex** — không âm và tổng bằng 1. Trọng số
âm nghĩa là ensemble đang bán khống một model, điều không có nghĩa ở đây.

Ba kiểm tra hành vi, mỗi cái ứng với một cách ensemble có thể hỏng:

- tổ hợp phải **tốt hơn candidate tệ nhất** — nếu không thì tổ hợp làm hại;
- khi chỉ một model có tín hiệu còn lại là nhiễu, tổ hợp phải **khôi phục về model đó**;
- rank average phải **không phụ thuộc thang đo**, vì các model cho điểm ở thang rất khác nhau.

`test_cross_fitted_ensemble_returns_complete_out_of_fold_score` chặn lỗi âm thầm nhất: ensemble
để sót dòng không có điểm OOF, khiến metric tính trên tập con mà không ai biết.
"""

import numpy as np
import pytest

from src.ensemble import (
    best_single_by_dr_risk,
    causal_q_aggregation,
    cross_fitted_weight_ensemble_score,
    doubly_robust_losses,
    rank_average_score,
    softmax_dr_risk_ensemble,
)
from src.policy import doubly_robust_effect_signal
from src.policy_evaluation import doubly_robust_risk
from tests.synthetic_rct import make_synthetic_rct


def _fixture(n=80_000, seed=50):
    data = make_synthetic_rct(n=n, base_rate=0.08, effect_scale=0.04, seed=seed)
    signal = doubly_robust_effect_signal(
        data.outcome,
        data.treatment,
        data.mu0,
        data.mu1,
        propensity=data.propensity,
    )
    rng = np.random.default_rng(seed)
    predictions = {
        # Gần đúng: tau thật cộng nhiễu nhỏ.
        "good": data.tau + rng.normal(scale=0.002, size=n),
        # Sai lệch hệ thống: co về 0.
        "shrunk": 0.3 * data.tau,
        # Vô dụng: hằng số bằng ATE.
        "constant": np.full(n, data.ate),
    }
    return data, signal, predictions


def test_dr_losses_rank_models_by_quality():
    _, signal, predictions = _fixture()
    losses = doubly_robust_losses(predictions, signal)
    assert losses["good"] < losses["shrunk"]
    assert losses["good"] < losses["constant"]


def test_best_single_selects_lowest_loss_model():
    _, signal, predictions = _fixture()
    result = best_single_by_dr_risk(predictions, signal)
    assert result.as_dict()["good"] == 1.0
    assert sum(result.as_dict().values()) == pytest.approx(1.0)


def test_q_aggregation_weights_are_a_valid_simplex_point():
    _, signal, predictions = _fixture()
    result = causal_q_aggregation(predictions, signal)
    weights = result.weights
    assert np.all(weights >= -1e-9)
    assert weights.sum() == pytest.approx(1.0)
    assert result.as_dict()["good"] > result.as_dict()["constant"]


def test_q_aggregation_beats_worst_candidate_on_dr_risk():
    _, signal, predictions = _fixture()
    result = causal_q_aggregation(predictions, signal)
    ensemble = result.predict(predictions)
    losses = doubly_robust_losses(predictions, signal)
    assert doubly_robust_risk(signal, ensemble) < max(losses.values())
    # Với nu=0 (stacking thuần) nghiệm phải ít nhất bằng model đơn tốt nhất.
    stacking = causal_q_aggregation(predictions, signal, nu=0.0)
    assert doubly_robust_risk(signal, stacking.predict(predictions)) <= min(
        losses.values()
    ) + 1e-9


def test_q_aggregation_recovers_single_model_when_others_are_noise():
    data = make_synthetic_rct(n=60_000, base_rate=0.08, effect_scale=0.04, seed=51)
    signal = doubly_robust_effect_signal(
        data.outcome,
        data.treatment,
        data.mu0,
        data.mu1,
        propensity=data.propensity,
    )
    rng = np.random.default_rng(2)
    predictions = {
        "truth": data.tau,
        "noise_a": rng.normal(scale=0.04, size=len(data.tau)),
        "noise_b": rng.normal(scale=0.04, size=len(data.tau)),
    }
    weights = causal_q_aggregation(predictions, signal).as_dict()
    assert weights["truth"] > 0.8


def test_nu_zero_and_nu_half_both_stay_on_simplex():
    _, signal, predictions = _fixture(n=20_000, seed=52)
    for nu in (0.0, 0.25, 0.5, 0.9):
        weights = causal_q_aggregation(predictions, signal, nu=nu).weights
        assert weights.sum() == pytest.approx(1.0)
        assert np.all(weights >= -1e-9)
    with pytest.raises(ValueError):
        causal_q_aggregation(predictions, signal, nu=1.0)


def test_softmax_ensemble_gives_more_weight_to_lower_loss():
    _, signal, predictions = _fixture()
    weights = softmax_dr_risk_ensemble(predictions, signal).as_dict()
    assert weights["good"] > weights["shrunk"]
    assert weights["good"] > weights["constant"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_cross_fitted_ensemble_returns_complete_out_of_fold_score():
    _, signal, predictions = _fixture(n=40_000, seed=53)
    result = cross_fitted_weight_ensemble_score(
        predictions, signal, n_splits=2, seed=9
    )
    assert np.isfinite(result["score"]).all()
    assert len(result["fold_weights"]) == 2
    assert set(result["full_sample_weights"]) == set(predictions)
    assert result["nested_base_models"] is False
    # Điểm cross-fitted phải kém hơn hoặc bằng điểm học-và-chấm trên cùng dữ liệu.
    in_sample = causal_q_aggregation(predictions, signal).predict(predictions)
    assert doubly_robust_risk(signal, result["score"]) >= doubly_robust_risk(
        signal,
        in_sample,
    ) - 1e-9


def test_rank_average_is_scale_free():
    _, _, predictions = _fixture(n=10_000, seed=54)
    baseline = rank_average_score(predictions)
    rescaled = {
        name: 1000.0 * values + 5.0 for name, values in predictions.items()
    }
    np.testing.assert_allclose(rank_average_score(rescaled), baseline)


def test_input_validation():
    signal = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        doubly_robust_losses({}, signal)
    with pytest.raises(ValueError):
        doubly_robust_losses({"a": np.array([1.0, 2.0])}, signal)
    with pytest.raises(ValueError):
        doubly_robust_losses({"a": np.array([1.0, np.inf, 3.0])}, signal)
    with pytest.raises(KeyError):
        cross_fitted_weight_ensemble_score({"a": signal}, signal, method="unknown")
    with pytest.raises(KeyError):
        causal_q_aggregation({"a": signal}, signal).predict({"b": signal})
