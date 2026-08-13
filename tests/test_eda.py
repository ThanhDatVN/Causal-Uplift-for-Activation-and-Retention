"""Test cho các chẩn đoán dữ liệu ở :mod:`src.eda`.

Nguyên tắc giống phần còn lại của repo: mỗi hàm được kiểm trên dữ liệu mà đáp án
đã biết trước — hoặc tính tay được, hoặc do generator sinh ra — chứ không chỉ
kiểm rằng hàm chạy không lỗi. Riêng :func:`prognostic_dominance_summary` được
kiểm hai chiều: nó phải nhận ra cấu trúc nhân *và* phải từ chối khi cấu trúc là
cộng, nếu không thì chẩn đoán chỉ là một con số luôn luôn lớn.
"""

import numpy as np
import pandas as pd
import pytest

from src.eda import (
    arm_outcome_table,
    balance_table,
    binned_effect_table,
    cochran_q,
    difference_in_means,
    duplicate_profile,
    feature_cardinality_profile,
    minimum_detectable_effect,
    post_treatment_leakage_report,
    prognostic_dominance_summary,
    propensity_overlap,
    quantile_bins,
    required_sample_size,
    sample_representativity,
    sentinel_mask_agreement,
    sentinel_mask_matrix,
    sentinel_mask_profile,
)


# ---------------------------------------------------------------------------
# Fixtures cục bộ
# ---------------------------------------------------------------------------


def _binary_rct(
    n: int = 400_000,
    propensity: float = 0.85,
    baseline: np.ndarray | None = None,
    effect: np.ndarray | None = None,
    seed: int = 0,
):
    """RCT nhị phân với ``mu0`` và ``tau`` chỉ định sẵn theo từng dòng."""
    rng = np.random.default_rng(seed)
    mu0 = np.full(n, 0.01) if baseline is None else np.asarray(baseline, dtype="float64")
    tau = np.full(n, 0.005) if effect is None else np.asarray(effect, dtype="float64")
    treatment = (rng.random(n) < propensity).astype("float64")
    probability = np.clip(np.where(treatment == 1, mu0 + tau, mu0), 0.0, 1.0)
    outcome = (rng.random(n) < probability).astype("float64")
    return outcome, treatment, mu0, tau


# ---------------------------------------------------------------------------
# 1. Cấu trúc dữ liệu
# ---------------------------------------------------------------------------


def test_cardinality_profile_reports_point_mass_and_bin_collapse():
    df = pd.DataFrame(
        {
            "spread": np.linspace(0.0, 1.0, 1000),
            "point_mass": np.r_[np.full(990, 7.0), np.arange(100, 110, dtype="float64")],
        }
    )
    profile = feature_cardinality_profile(df, ["spread", "point_mass"]).set_index("feature")

    assert profile.loc["spread", "mode_share"] == pytest.approx(0.001)
    assert profile.loc["spread", "n_effective_quantile_bins"] == 10
    assert profile.loc["point_mass", "mode_value"] == 7.0
    assert profile.loc["point_mass", "mode_share"] == pytest.approx(0.99)
    # 99% khối lượng ở một giá trị: phần lớn biên decile trùng nhau và bị gộp.
    assert profile.loc["point_mass", "n_effective_quantile_bins"] < 10


def test_quantile_bins_merges_duplicate_edges_instead_of_raising():
    values = np.r_[np.zeros(95), np.arange(1, 6, dtype="float64")]
    bins = quantile_bins(values, n_bins=10)
    assert pd.Series(bins).nunique() < 10
    assert len(bins) == len(values)


def test_sentinel_mask_agreement_is_one_for_shared_encoding():
    n = 1000
    shared = np.r_[np.ones(700, dtype=bool), np.zeros(300, dtype=bool)]
    rng = np.random.default_rng(7)
    df = pd.DataFrame(
        {
            # a và b khác giá trị nhưng nằm ở sentinel trên đúng cùng một tập dòng.
            "a": np.where(shared, 1.0, rng.normal(5, 1, n)),
            "b": np.where(shared, -3.0, rng.normal(9, 1, n)),
            "c": np.where(rng.random(n) < 0.7, 0.0, rng.normal(2, 1, n)),
        }
    )
    mask, sentinels = sentinel_mask_matrix(df, ["a", "b", "c"])
    agreement = sentinel_mask_agreement(mask)

    assert sentinels["a"] == 1.0 and sentinels["b"] == -3.0
    assert agreement.loc["a", "b"] == 1.0
    assert agreement.loc["a", "c"] < 1.0


def test_sentinel_mask_profile_counts_patterns_and_observed_features():
    mask = pd.DataFrame(
        {
            "a": [True, True, False, False],
            "b": [True, False, False, False],
            "c": [True, True, True, False],
        }
    )
    profile = sentinel_mask_profile(mask)

    assert profile["n_distinct_patterns"] == 4
    assert profile["n_possible_patterns"] == 8
    assert profile["top_patterns"]["n_rows"].sum() == 4
    # Số feature quan sát được mỗi dòng: 0, 1, 2, 3.
    assert profile["median_observed_features"] == pytest.approx(1.5)
    assert profile["observed_per_row"]["n_rows"].sum() == 4


def test_duplicate_profile_counts_repeated_feature_vectors():
    df = pd.DataFrame({"x": [1, 1, 1, 2, 3], "y": [0, 0, 0, 1, 2]})
    profile = duplicate_profile(df, ["x", "y"])

    assert profile["n_distinct_feature_vectors"] == 3
    assert profile["n_duplicate_rows"] == 2
    assert profile["max_group_size"] == 3
    assert profile["n_rows_in_repeated_groups"] == 3
    assert profile["share_rows_in_repeated_groups"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# 2. Tính hợp lệ của thiết kế
# ---------------------------------------------------------------------------


def test_balance_table_ranks_injected_imbalance_first():
    rng = np.random.default_rng(3)
    n = 40_000
    treatment = (rng.random(n) < 0.85).astype("int8")
    df = pd.DataFrame(
        {
            "treatment": treatment,
            "balanced": rng.normal(size=n),
            "biased": rng.normal(size=n) + 0.8 * treatment,
        }
    )
    table = balance_table(df, ["balanced", "biased"])

    assert table.iloc[0]["feature"] == "biased"
    assert table.iloc[0]["abs_smd"] > 0.5
    assert table.loc[table["feature"] == "balanced", "abs_smd"].iloc[0] < 0.1


def test_propensity_overlap_flags_bins_with_a_single_arm():
    score = np.r_[np.full(500, 0.1), np.full(500, 0.9)]
    treatment = np.r_[np.zeros(500), np.ones(500)]
    result = propensity_overlap(score, treatment, n_bins=4)

    assert not result["positivity_holds_in_sample"]
    assert result["n_single_arm_bins"] == 2
    assert result["share_rows_in_single_arm_bins"] == pytest.approx(1.0)


def test_propensity_overlap_passes_for_constant_design_propensity():
    """Trường hợp Criteo: propensity là hằng số thiết kế, mọi dòng rơi vào một bin."""
    rng = np.random.default_rng(11)
    n = 20_000
    treatment = (rng.random(n) < 0.85).astype("float64")
    result = propensity_overlap(np.full(n, 0.85), treatment, n_bins=10)

    assert result["positivity_holds_in_sample"]
    assert result["n_occupied_bins"] == 1
    assert result["share_rows_in_single_arm_bins"] == pytest.approx(0.0)


def test_propensity_overlap_keeps_almost_all_rows_in_two_arm_bins_when_estimated():
    rng = np.random.default_rng(11)
    n = 400_000
    treatment = (rng.random(n) < 0.85).astype("float64")
    score = np.clip(0.85 + rng.normal(0, 0.02, n), 1e-6, 1 - 1e-6)
    result = propensity_overlap(score, treatment, n_bins=10)

    # Chỉ đuôi cực hiếm mới có thể chỉ có một arm; khối lượng phải ở vùng hai arm.
    assert result["share_rows_in_single_arm_bins"] < 1e-3


def test_arm_outcome_table_reports_absolute_event_counts():
    df = pd.DataFrame(
        {
            "treatment": [0, 0, 0, 1, 1, 1, 1],
            "conversion": [0, 1, 0, 1, 1, 0, 0],
        }
    )
    table = arm_outcome_table(df, ["conversion"]).set_index("treatment")

    assert table.loc[0, "n_events"] == 1
    assert table.loc[1, "n_events"] == 2
    assert table.loc[0, "rate"] == pytest.approx(1 / 3)


def test_post_treatment_leakage_report_identifies_both_signatures():
    rng = np.random.default_rng(5)
    n = 50_000
    treatment = (rng.random(n) < 0.85).astype("int8")
    # `gate` chỉ xảy ra dưới treatment; conversion chỉ xảy ra khi gate = 1.
    gate = np.where(treatment == 1, (rng.random(n) < 0.3).astype("int8"), 0)
    conversion = np.where(gate == 1, (rng.random(n) < 0.2).astype("int8"), 0)
    df = pd.DataFrame({"treatment": treatment, "gate": gate, "conversion": conversion})

    report = post_treatment_leakage_report(df, ["gate"]).set_index("column")
    assert report.loc["gate", "rate_control"] == 0.0
    assert report.loc["gate", "only_defined_under_treatment"]
    assert report.loc["gate", "necessary_for_outcome"]
    assert report.loc["gate", "outcome_rate_when_zero"] == 0.0


def test_post_treatment_leakage_report_clears_a_pre_treatment_column():
    rng = np.random.default_rng(6)
    n = 50_000
    treatment = (rng.random(n) < 0.85).astype("int8")
    pre = (rng.random(n) < 0.4).astype("int8")
    conversion = (rng.random(n) < 0.01).astype("int8")
    df = pd.DataFrame({"treatment": treatment, "pre": pre, "conversion": conversion})

    report = post_treatment_leakage_report(df, ["pre"]).set_index("column")
    assert not report.loc["pre", "only_defined_under_treatment"]
    assert not report.loc["pre", "necessary_for_outcome"]
    assert abs(report.loc["pre", "smd_by_treatment"]) < 0.05


# ---------------------------------------------------------------------------
# 3. Hiệu ứng trung bình và công suất
# ---------------------------------------------------------------------------


def test_difference_in_means_matches_hand_computed_values():
    outcome = np.r_[np.ones(30), np.zeros(70), np.ones(10), np.zeros(90)]
    treatment = np.r_[np.ones(100), np.zeros(100)]
    result = difference_in_means(outcome, treatment)

    assert result["rate_treated"] == pytest.approx(0.30)
    assert result["rate_control"] == pytest.approx(0.10)
    assert result["difference_in_means"] == pytest.approx(0.20)
    assert result["risk_ratio"] == pytest.approx(3.0)
    assert result["events_control"] == 10
    expected_se = np.sqrt(0.3 * 0.7 / 100 + 0.1 * 0.9 / 100)
    assert result["standard_error"] == pytest.approx(expected_se)
    assert result["ci_low"] < 0.20 < result["ci_high"]


def test_difference_in_means_covers_the_true_ate_on_a_simulated_rct():
    covered = 0
    trials = 40
    for seed in range(trials):
        outcome, treatment, _, tau = _binary_rct(n=200_000, seed=seed)
        result = difference_in_means(outcome, treatment)
        if result["ci_low"] <= tau.mean() <= result["ci_high"]:
            covered += 1
    # Coverage danh nghĩa 95%; ngưỡng nới để test không phụ thuộc một seed cụ thể.
    assert covered >= int(0.85 * trials)


def test_difference_in_means_returns_nan_risk_ratio_without_control_events():
    outcome = np.r_[np.ones(10), np.zeros(90), np.zeros(100)]
    treatment = np.r_[np.ones(100), np.zeros(100)]
    result = difference_in_means(outcome, treatment)

    assert result["events_control"] == 0
    assert np.isnan(result["risk_ratio"])
    assert result["difference_in_means"] == pytest.approx(0.10)


def test_mde_and_required_sample_size_are_inverses():
    baseline, share, n_total = 0.0029, 0.85, 13_979_592
    mde = minimum_detectable_effect(baseline, n_total, share)
    round_trip = required_sample_size(mde, baseline, share)
    assert round_trip == pytest.approx(n_total, rel=1e-6)


def test_mde_shrinks_with_the_square_root_of_sample_size():
    baseline, share = 0.0029, 0.85
    small = minimum_detectable_effect(baseline, 1_000_000, share)
    large = minimum_detectable_effect(baseline, 4_000_000, share)
    assert small / large == pytest.approx(2.0, rel=1e-9)


# ---------------------------------------------------------------------------
# 4. Heterogeneity
# ---------------------------------------------------------------------------


def test_binned_effect_table_recovers_a_monotone_effect():
    n = 600_000
    rng = np.random.default_rng(2)
    x = rng.random(n)
    baseline = np.full(n, 0.02)
    effect = 0.002 + 0.02 * x  # tăng đơn điệu theo x
    outcome, treatment, _, _ = _binary_rct(n=n, baseline=baseline, effect=effect, seed=21)
    table = binned_effect_table(outcome, treatment, quantile_bins(x, 5))

    assert len(table) == 5
    assert table["effect"].is_monotonic_increasing
    # Bin thấp nhất và cao nhất phải tách nhau bằng CI.
    assert table.iloc[0]["effect_ci_high"] < table.iloc[-1]["effect_ci_low"]


def test_binned_effect_table_drops_bins_without_events_in_both_arms():
    outcome = np.r_[np.ones(5), np.zeros(95), np.zeros(100)]
    treatment = np.r_[np.ones(50), np.zeros(50), np.ones(50), np.zeros(50)]
    bins = np.r_[np.zeros(100), np.ones(100)]
    with pytest.raises(ValueError, match="Không bin nào đủ sự kiện"):
        binned_effect_table(outcome, treatment, bins)


def test_cochran_q_is_zero_for_identical_estimates():
    result = cochran_q([0.5, 0.5, 0.5], [0.1, 0.2, 0.05])
    assert result["q_statistic"] == pytest.approx(0.0)
    assert result["i_squared"] == pytest.approx(0.0)
    assert result["pooled_estimate"] == pytest.approx(0.5)
    assert result["p_value"] == pytest.approx(1.0)


def test_cochran_q_matches_a_hand_computed_value():
    # se bằng nhau nên w bằng nhau; pooled = 0, Q = sum((theta/se)^2).
    result = cochran_q([-1.0, 0.0, 1.0], [0.5, 0.5, 0.5])
    assert result["pooled_estimate"] == pytest.approx(0.0)
    assert result["q_statistic"] == pytest.approx(8.0)
    assert result["df"] == 2


def test_cochran_q_rejects_a_single_estimate():
    with pytest.raises(ValueError, match="ít nhất 2 ước lượng"):
        cochran_q([0.5], [0.1])


def _strata_table(baseline_by_stratum, effect_by_stratum, n_per_stratum=400_000, seed=0):
    baseline = np.repeat(baseline_by_stratum, n_per_stratum)
    effect = np.repeat(effect_by_stratum, n_per_stratum)
    bins = np.repeat(np.arange(len(baseline_by_stratum)), n_per_stratum)
    outcome, treatment, _, _ = _binary_rct(
        n=len(baseline), baseline=baseline, effect=effect, seed=seed
    )
    return binned_effect_table(outcome, treatment, bins)


def test_prognostic_dominance_detected_when_effect_is_multiplicative():
    baseline = np.array([0.002, 0.006, 0.018, 0.050])
    summary = prognostic_dominance_summary(
        _strata_table(baseline, 0.5 * baseline, seed=31)
    )
    assert summary["pearson_r"] > 0.95
    assert summary["spearman_rho"] == pytest.approx(1.0)
    assert summary["pooled_risk_ratio"] == pytest.approx(1.5, rel=0.05)
    # Hiệu ứng bất biến trên thang nhân: Q của thang nhân nhỏ hơn hẳn thang cộng.
    assert summary["q_ratio_additive_over_multiplicative"] > 10


def test_prognostic_dominance_absent_when_effect_is_constant_additive():
    baseline = np.array([0.002, 0.006, 0.018, 0.050])
    summary = prognostic_dominance_summary(
        _strata_table(baseline, np.full(4, 0.004), seed=32)
    )
    # Hiệu ứng cộng bất biến: thang cộng mới là thang đồng nhất, không phải thang nhân.
    assert summary["q_ratio_additive_over_multiplicative"] < 1.0
    assert summary["q_multiplicative"] > summary["q_additive"]


def test_prognostic_dominance_requires_enough_strata():
    table = pd.DataFrame(
        {
            "baseline_rate": [0.01, 0.02],
            "effect": [0.001, 0.002],
            "standard_error": [0.0001, 0.0001],
            "log_risk_ratio": [0.1, 0.1],
            "se_log_risk_ratio": [0.01, 0.01],
        }
    )
    with pytest.raises(ValueError, match="ít nhất 3 tầng"):
        prognostic_dominance_summary(table)


def test_prognostic_dominance_disables_inference_for_overlapping_strata():
    baseline = np.array([0.002, 0.006, 0.018, 0.050])
    summary = prognostic_dominance_summary(
        _strata_table(baseline, 0.5 * baseline, seed=33),
        independent_strata=False,
    )
    assert summary["independent_strata"] is False
    assert summary["pearson_r"] > 0.95
    assert summary["pearson_p_value"] is None
    assert summary["q_additive"] is None
    assert summary["pooled_risk_ratio"] is None
    assert "Descriptive only" in summary["inference_note"]


def test_sample_representativity_flags_a_shifted_sample():
    rng = np.random.default_rng(9)
    full = pd.DataFrame({"x": rng.normal(size=100_000)})
    unbiased = full.sample(frac=0.05, random_state=1)
    shifted = full.nlargest(5_000, "x")

    good = sample_representativity(full, unbiased, ["x"]).iloc[0]
    bad = sample_representativity(full, shifted, ["x"]).iloc[0]
    assert abs(good["smd"]) < 0.05
    assert abs(bad["smd"]) > 1.0
