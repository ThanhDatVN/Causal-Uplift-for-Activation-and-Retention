import numpy as np
import pytest

from src.evaluation import transformed_outcome
from src.policy import doubly_robust_effect_signal
from src.ranking_metrics import (
    adjusted_transformed_outcome,
    autoc_score,
    paired_difference_summary,
    paired_rate_bootstrap,
    rate_score,
    toc_curve,
)
from tests.synthetic_rct import make_synthetic_rct


def _oracle_signal(data):
    return doubly_robust_effect_signal(
        data.outcome,
        data.treatment,
        data.mu0,
        data.mu1,
        propensity=data.propensity,
    )


def test_adjusted_outcome_with_zero_prediction_equals_transformed_outcome():
    data = make_synthetic_rct(n=5_000, seed=1)
    raw = transformed_outcome(
        data.outcome,
        data.treatment,
        propensity=data.propensity,
    )
    adjusted = adjusted_transformed_outcome(
        data.outcome,
        data.treatment,
        np.zeros(len(raw)),
        propensity=data.propensity,
    )
    np.testing.assert_allclose(adjusted, raw)


def test_adjusted_outcome_preserves_ate_and_reduces_variance():
    """Adjustment không đổi estimand nhưng phải giảm variance của signal."""
    data = make_synthetic_rct(n=400_000, base_rate=0.05, seed=2)
    raw = transformed_outcome(
        data.outcome,
        data.treatment,
        propensity=data.propensity,
    )
    adjusted = adjusted_transformed_outcome(
        data.outcome,
        data.treatment,
        data.pooled_outcome_mean,
        propensity=data.propensity,
    )
    # Cả hai đều ước lượng cùng một ATE; sai số Monte Carlo được kiểm bằng
    # standard error của chính raw signal.
    standard_error = float(np.std(raw, ddof=1) / np.sqrt(len(raw)))
    assert abs(float(np.mean(raw)) - data.ate) < 4 * standard_error
    assert abs(float(np.mean(adjusted)) - data.ate) < 4 * standard_error
    assert np.var(adjusted) < np.var(raw)


def test_adjusted_outcome_lowers_autoc_sampling_variance():
    """Variance của AUTOC qua nhiều lần mô phỏng phải giảm khi adjust outcome.

    Mức giảm ở đây yếu hơn nhiều so với mức giảm variance của signal từng dòng:
    trong generator, ``mu0`` phụ thuộc ``X[:, 1]`` còn ranking dùng ``X[:, 0]``,
    nên phần variance bị adjustment loại bỏ phần lớn đã tự triệt tiêu giữa
    ``mean(top-q)`` và ``mean(toàn bộ)``. Đo trên 5 khối seed độc lập, tỷ lệ
    variance nằm trong khoảng 0,84–0,91; 120 lần lặp là đủ để kết luận ổn định,
    24 lần thì chưa.

    Kiểm định dùng dạng paired của Pitman–Morgan: với hai biến có cùng cỡ mẫu,
    ``Cov(a + b, a − b) = Var(a) − Var(b)``, nên hệ số tương quan giữa tổng và
    hiệu dương tương đương ``Var(raw) > Var(adjusted)``. Dạng paired có lực
    kiểm định cao hơn vì hai chuỗi tương quan khoảng 0,92.
    """
    raw_values = []
    adjusted_values = []
    for seed in range(120):
        data = make_synthetic_rct(n=20_000, base_rate=0.08, seed=100 + seed)
        score = data.X[:, 0]
        raw_values.append(
            autoc_score(
                transformed_outcome(
                    data.outcome,
                    data.treatment,
                    propensity=data.propensity,
                ),
                score,
            )
        )
        adjusted_values.append(
            autoc_score(
                adjusted_transformed_outcome(
                    data.outcome,
                    data.treatment,
                    data.pooled_outcome_mean,
                    propensity=data.propensity,
                ),
                score,
            )
        )
    raw = np.asarray(raw_values)
    adjusted = np.asarray(adjusted_values)
    assert np.var(adjusted, ddof=1) < np.var(raw, ddof=1)
    assert np.corrcoef(raw + adjusted, raw - adjusted)[0, 1] > 0


def test_oracle_ranking_beats_random_and_reversed_ranking():
    data = make_synthetic_rct(n=200_000, seed=3)
    signal = _oracle_signal(data)
    rng = np.random.default_rng(0)
    oracle = autoc_score(signal, data.tau)
    random_ranking = autoc_score(signal, rng.random(len(signal)))
    reversed_ranking = autoc_score(signal, -data.tau)
    assert oracle > random_ranking
    assert oracle > reversed_ranking
    assert reversed_ranking < random_ranking
    assert oracle > 0 > reversed_ranking


def test_qini_weighted_rate_is_antisymmetric_under_rank_reversal():
    """Chỉ biến thể α(q)=q mới đổi dấu chính xác khi đảo ngược ranking.

    Với TOC(q) = mean(Γ | top-q) − ḡ, đồng nhất thức
    ``TOC_rev(1−q) = −q·TOC(q)/(1−q)`` cho
    ``∫ q·TOC_rev(q) dq = −∫ q·TOC(q) dq``. Hệ thức tương tự không đúng cho
    α(q)=1, nên AUTOC của score đảo ngược không bằng −AUTOC.
    """
    data = make_synthetic_rct(n=100_000, seed=33)
    signal = _oracle_signal(data)
    forward = rate_score(signal, data.tau, weighting="qini")
    backward = rate_score(signal, -data.tau, weighting="qini")
    assert forward == pytest.approx(-backward, rel=1e-6)

    forward_autoc = rate_score(signal, data.tau, weighting="autoc")
    backward_autoc = rate_score(signal, -data.tau, weighting="autoc")
    assert forward_autoc != pytest.approx(-backward_autoc, rel=1e-3)


def test_rate_is_invariant_to_increasing_monotone_transform():
    data = make_synthetic_rct(n=50_000, seed=4)
    signal = _oracle_signal(data)
    score = data.X[:, 0]
    base = rate_score(signal, score)
    for transform in (
        lambda s: 3.5 * s + 1.25,
        lambda s: np.exp(s / 4.0),
        lambda s: np.arctan(s),
    ):
        assert rate_score(signal, transform(score)) == pytest.approx(base, rel=1e-9)


def test_constant_score_gives_zero_rate():
    data = make_synthetic_rct(n=20_000, seed=5)
    signal = _oracle_signal(data)
    constant = np.full(len(signal), 0.7)
    assert rate_score(signal, constant) == pytest.approx(0.0, abs=1e-12)
    assert rate_score(signal, constant, weighting="qini") == pytest.approx(
        0.0,
        abs=1e-12,
    )


def test_toc_curve_endpoints_and_shape():
    data = make_synthetic_rct(n=30_000, seed=6)
    signal = _oracle_signal(data)
    curve = toc_curve(signal, data.tau)
    assert curve["q"][-1] == pytest.approx(1.0)
    # Ở q = 1 toàn bộ population được chọn nên TOC phải bằng 0.
    assert curve["toc"][-1] == pytest.approx(0.0, abs=1e-10)
    grid = np.array([0.05, 0.1, 0.2, 0.5, 1.0])
    interpolated = toc_curve(signal, data.tau, q_grid=grid)
    assert interpolated["toc"].shape == grid.shape
    assert np.isfinite(interpolated["toc"]).all()


def test_metrics_are_finite_on_rare_outcome_sample():
    data = make_synthetic_rct(n=120_000, base_rate=0.003, effect_scale=0.002, seed=7)
    assert 0 < data.outcome.mean() < 0.01
    signal = _oracle_signal(data)
    assert np.isfinite(autoc_score(signal, data.X[:, 0]))
    assert np.isfinite(rate_score(signal, data.X[:, 0], weighting="qini"))
    curve = toc_curve(signal, data.X[:, 0])
    assert np.isfinite(curve["toc"]).all()


def test_qini_weighting_differs_from_autoc_but_agrees_on_sign():
    data = make_synthetic_rct(n=80_000, seed=8)
    signal = _oracle_signal(data)
    autoc = rate_score(signal, data.tau, weighting="autoc")
    qini_weighted = rate_score(signal, data.tau, weighting="qini")
    assert autoc > 0 and qini_weighted > 0
    assert autoc != pytest.approx(qini_weighted)


def test_paired_bootstrap_keeps_pairing_for_identical_scores():
    data = make_synthetic_rct(n=20_000, seed=9)
    signal = _oracle_signal(data)
    score = data.X[:, 0]
    result = paired_rate_bootstrap(
        {"a": score, "b": score.copy()},
        signal,
        n_boot=25,
        seed=11,
    )
    difference = result["draws"][:, 0] - result["draws"][:, 1]
    np.testing.assert_allclose(difference, 0.0, atol=1e-12)
    summary = paired_difference_summary(result, "a", "b")
    assert summary["ci_low"] == pytest.approx(0.0, abs=1e-12)
    assert summary["ci_high"] == pytest.approx(0.0, abs=1e-12)


def test_paired_bootstrap_separates_oracle_from_reversed_score():
    data = make_synthetic_rct(n=120_000, seed=10)
    signal = _oracle_signal(data)
    result = paired_rate_bootstrap(
        {"oracle": data.tau, "reversed": -data.tau},
        signal,
        n_boot=60,
        seed=12,
    )
    summary = paired_difference_summary(result, "oracle", "reversed")
    assert summary["observed_difference"] > 0
    assert summary["ci_low"] > 0
    assert summary["probability_difference_positive"] == 1.0


def test_bootstrap_ci_brackets_observed_value():
    data = make_synthetic_rct(n=60_000, seed=13)
    signal = _oracle_signal(data)
    result = paired_rate_bootstrap({"oracle": data.tau}, signal, n_boot=50, seed=14)
    assert result["ci_low"][0] < result["observed"][0] < result["ci_high"][0]


def test_input_validation():
    signal = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        rate_score(signal, np.array([1.0, 2.0]))
    with pytest.raises(ValueError):
        rate_score(signal, np.array([1.0, 2.0, np.nan]))
    with pytest.raises(ValueError):
        rate_score(signal, signal, weighting="unknown")
    with pytest.raises(ValueError):
        adjusted_transformed_outcome([1.0], [1.0], [0.0], propensity=1.0)
    with pytest.raises(ValueError):
        paired_rate_bootstrap({}, signal)
