import numpy as np
import pytest

from tests.synthetic_rct import make_synthetic_rct


@pytest.mark.parametrize(
    ("base_rate", "effect_scale", "alignment"),
    [
        (0.003, 0.002, "orthogonal"),
        (0.05, 0.04, "risk_aligned"),
        (0.05, 0.04, "risk_anti_aligned"),
        (0.90, 0.30, "homogeneous"),
    ],
)
def test_synthetic_truth_equals_clipped_potential_outcome_difference(
    base_rate,
    effect_scale,
    alignment,
):
    data = make_synthetic_rct(
        n=20_000,
        base_rate=base_rate,
        effect_scale=effect_scale,
        effect_alignment=alignment,
        seed=701,
    )

    np.testing.assert_allclose(data.tau, data.mu1 - data.mu0, atol=0.0, rtol=0.0)
    assert np.all((0 <= data.mu0) & (data.mu0 <= 1))
    assert np.all((0 <= data.mu1) & (data.mu1 <= 1))


def test_synthetic_rct_reproduces_rare_outcome_and_imbalanced_assignment():
    data = make_synthetic_rct(
        n=200_000,
        propensity=0.85,
        base_rate=0.003,
        effect_scale=0.002,
        seed=702,
    )

    assert np.mean(data.treatment) == pytest.approx(0.85, abs=0.003)
    assert np.mean(data.outcome) < 0.01
    assert np.sum((data.treatment == 0) & (data.outcome == 1)) > 50


def test_effect_alignment_modes_have_the_registered_risk_relationship():
    aligned = make_synthetic_rct(
        n=80_000,
        base_rate=0.05,
        effect_scale=0.01,
        effect_alignment="risk_aligned",
        seed=703,
    )
    anti = make_synthetic_rct(
        n=80_000,
        base_rate=0.05,
        effect_scale=0.01,
        effect_alignment="risk_anti_aligned",
        seed=703,
    )

    assert np.corrcoef(aligned.mu0, aligned.tau)[0, 1] > 0.9
    assert np.corrcoef(anti.mu0, anti.tau)[0, 1] < -0.9


def test_invalid_effect_alignment_is_rejected():
    with pytest.raises(ValueError, match="effect_alignment"):
        make_synthetic_rct(effect_alignment="post_hoc_best")
