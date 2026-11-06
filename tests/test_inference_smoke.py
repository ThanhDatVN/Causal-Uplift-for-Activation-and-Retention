"""Known-truth inference smoke for the paired contrast (session 10)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from telco_churn.inference_smoke import TRUE_CONTRAST, main, run_smoke, simulate_world
from telco_churn.policy_comparison import paired_contrast, unpaired_contrast


def test_the_analytic_contrast_matches_the_simulated_potential_outcomes() -> None:
    rng = np.random.default_rng(1)
    world = simulate_world(400_000, rng)
    # Average the oracle scores over a large world; the DR score is unbiased for
    # the potential-outcome mean, so the paired contrast converges on the truth.
    contrast = paired_contrast(world["scores"], world["policy_1"], world["policy_0"])
    assert contrast.delta == pytest.approx(TRUE_CONTRAST, abs=0.01)


def test_both_estimators_share_a_point_estimate_but_not_a_standard_error() -> None:
    rng = np.random.default_rng(2)
    world = simulate_world(5_000, rng)
    paired = paired_contrast(world["scores"], world["policy_1"], world["policy_0"])
    unpaired = unpaired_contrast(world["scores"], world["policy_1"], world["policy_0"])
    assert paired.delta == pytest.approx(unpaired.delta)
    assert paired.se < unpaired.se


def test_smoke_is_unbiased_and_reports_its_monte_carlo_error() -> None:
    report = run_smoke(worlds=40, n_per_world=1500, seed=11)
    paired = report["paired"]
    assert paired["bias_within_2_mc_se"] is True
    assert paired["coverage_ci_low"] <= 0.95 <= paired["coverage_ci_high"]
    assert report["se_variance_ratio_unpaired_over_paired"] > 1.0


def test_doubly_robust_property_survives_a_constant_outcome_model() -> None:
    report = run_smoke(worlds=40, n_per_world=1500, seed=11, misspecify_outcome=True)
    assert report["config"]["misspecified_outcome_model"] is True
    assert report["paired"]["bias_within_2_mc_se"] is True


def test_the_report_refuses_to_pose_as_a_coverage_gate() -> None:
    report = run_smoke(worlds=10, n_per_world=500)
    assert report["status"] == "SMOKE_ONLY"
    assert len(report["scenarios_covered"]) == 1
    assert len(report["scenarios_required_for_gate"]) > 1
    assert "no false-promotion rate" in report["note"]


def test_cli_writes_a_report(tmp_path) -> None:
    output = tmp_path / "inference_smoke.json"
    assert main(["--worlds", "10", "--n-per-world", "500", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["true_contrast"] == TRUE_CONTRAST
    assert payload["budget"]["seconds_per_world"] > 0
