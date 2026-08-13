"""Kiểm tra code đánh giá mới khớp artifact đã phát hành của các sprint trước.

Đây là loại test đắt giá nhất trong repo: nó bắt được trường hợp một refactor
làm đổi con số đã báo cáo mà không ai nhận ra. Test tự bỏ qua khi artifact
prediction chưa được sinh, vì các file ``.npz`` không được commit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation import qini_score
from src.paths import OUTPUT_DIR
from src.policy import doubly_robust_effect_signal
from src.policy_evaluation import dr_policy_value_curve

SPRINT2_DIR = OUTPUT_DIR / "sprint2"
PREDICTIONS = SPRINT2_DIR / "confirmation_predictions.npz"
BUDGET_CURVE = SPRINT2_DIR / "policy_budget_curve.csv"
CALIBRATION = SPRINT2_DIR / "calibration_comparison.csv"
SPRINT3_DIR = OUTPUT_DIR / "sprint3"
REGISTRY = OUTPUT_DIR / "improvement" / "registry.csv"
CRITEO_V2_1_SHA256 = (
    "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
)

# Xác suất gán treatment trên toàn bộ Criteo v2.1, đúng giá trị Sprint 2 đã dùng
# (``protocol_manifest.json`` → ``evaluation.propensity``).
FULL_ASSIGNMENT_PROBABILITY = 0.8500000596046448


requires_predictions = pytest.mark.skipif(
    not PREDICTIONS.exists(),
    reason=(
        "Cần output/sprint2/confirmation_predictions.npz; chạy "
        "scripts/run_sprint2_local.py để sinh."
    ),
)


@pytest.fixture(scope="module")
def sprint2():
    payload = np.load(PREDICTIONS)
    return {
        "outcome": payload["conversion"].astype("float64"),
        "treatment": payload["treatment"].astype("float64"),
        "response_score": payload["response_score"].astype("float64"),
        "x_renormalized": payload["x_renormalized"].astype("float64"),
        "mu0": payload["mu0_local_exact"].astype("float64"),
        "mu1": payload["mu1_local_exact"].astype("float64"),
    }


@requires_predictions
def test_new_policy_curve_reproduces_released_sprint2_budget_curve(sprint2):
    """``dr_policy_value_curve`` phải khớp cột DR đã phát hành ở Sprint 2.

    Sprint 2 cắt top-k cứng; hàm mới nội suy tuyến tính qua nhóm ở biên ngân sách.
    Sai khác vì thế là bậc ``1/n`` trên 1,4 triệu dòng, không phải sai khác công thức.
    """
    signal = doubly_robust_effect_signal(
        sprint2["outcome"],
        sprint2["treatment"],
        sprint2["mu0"],
        sprint2["mu1"],
        propensity=FULL_ASSIGNMENT_PROBABILITY,
    )
    released = pd.read_csv(BUDGET_CURVE)
    released = released.loc[released["policy"] == "Response top-k"]
    budgets = [
        value for value in released["budget_fraction"].tolist() if 0 < value <= 1
    ]
    curve = dr_policy_value_curve(
        signal,
        sprint2["response_score"],
        budgets=sorted(budgets),
    )
    lookup = released.set_index("budget_fraction")[
        "gross_incremental_conversions_per_customer_dr"
    ]
    for budget, value in zip(
        curve["budget_fraction"],
        curve["gross_value_per_customer"],
    ):
        assert value == pytest.approx(float(lookup.loc[budget]), abs=1e-7)


@requires_predictions
def test_qini_matches_released_sprint2_confirmation_metrics(sprint2):
    """Qini tính lại từ prediction đã lưu phải khớp con số đã báo cáo.

    Dung sai là ``1e-5`` tương đối chứ không phải bằng đúng: metric gốc được tính
    trên prediction ``float64`` còn ``confirmation_predictions.npz`` lưu
    ``float32``. Việc thu hẹp độ chính xác đổi thứ tự của một số cặp có score gần
    nhau, nên Qini lệch ở chữ số có nghĩa thứ bảy. Lệch lớn hơn mức đó là dấu hiệu
    công thức đã đổi, không phải nhiễu lưu trữ.
    """
    released = pd.read_csv(CALIBRATION)
    released = released.loc[released["split"] == "confirmation"].set_index("model")
    for model, score in (
        ("Response", sprint2["response_score"]),
        ("X-Renormalized", sprint2["x_renormalized"]),
    ):
        recomputed = qini_score(sprint2["outcome"], sprint2["treatment"], score)
        assert recomputed == pytest.approx(
            float(released.loc[model, "qini_score"]),
            rel=1e-5,
        )


SPRINT1_RELEASE_QINI = {
    "Response": 0.187886,
    "S-Learner": 0.177204,
    "X-Learner": 0.167168,
    "DR-Learner": 0.153967,
    "T-Learner": 0.142021,
}
SPRINT1_FINAL_TEST = (
    OUTPUT_DIR
    / "optimization"
    / "final_test_results_sprint1_release_5models.csv"
)


@pytest.mark.skipif(
    not SPRINT1_FINAL_TEST.exists(),
    reason="Cần artifact final test Sprint 1.",
)
def test_documented_sprint1_qini_matches_the_artifact():
    """Bảng Qini trong CLAUDE.md và báo cáo Sprint 1 phải khớp artifact.

    Đây là guard chống trôi tài liệu: nếu ai đó chạy lại release Sprint 1 và ra số
    khác, test này báo ngay thay vì để tài liệu tiếp tục trích số cũ.
    """
    released = pd.read_csv(SPRINT1_FINAL_TEST).set_index("model")
    assert set(SPRINT1_RELEASE_QINI) <= set(released.index)
    for model, documented in SPRINT1_RELEASE_QINI.items():
        assert float(released.loc[model, "qini_score"]) == pytest.approx(
            documented,
            abs=1e-6,
        )
        assert int(released.loc[model, "n_test"]) == 2_096_940


@requires_predictions
def test_full_budget_policy_value_equals_doubly_robust_ate(sprint2):
    signal = doubly_robust_effect_signal(
        sprint2["outcome"],
        sprint2["treatment"],
        sprint2["mu0"],
        sprint2["mu1"],
        propensity=FULL_ASSIGNMENT_PROBABILITY,
    )
    curve = dr_policy_value_curve(signal, sprint2["response_score"], budgets=[1.0])
    assert curve["gross_value_per_customer"][0] == pytest.approx(
        float(np.mean(signal))
    )


def test_sprint3_registry_preserves_estimands_and_confirmation_metrics():
    registry = pd.read_csv(REGISTRY)
    identity = ["run_id", "fold_seed", "outcome"]
    assert not registry.duplicated(identity).any()
    assert {"conversion", "visit"} <= set(registry["outcome"])

    sprint3 = registry["run_id"].astype(str).str.startswith("sprint3-")
    assert (registry.loc[sprint3, "data_sha256"] == CRITEO_V2_1_SHA256).all()

    confirmation = registry.loc[
        registry["status"] == "retrospective_confirmation"
    ].set_index("candidate")
    released = pd.read_csv(SPRINT3_DIR / "confirmation_metrics.csv").set_index(
        "model"
    )
    assert set(confirmation.index) == set(released.index)
    assert confirmation["policy_area_dr"].notna().all()


def test_expected_random_range_is_sensitivity_not_confidence_interval():
    curve = pd.read_csv(SPRINT3_DIR / "policy_budget_curve.csv")
    random_rows = curve["model"] == "Expected random (stochastic policy)"
    random_curve = curve.loc[random_rows]
    assert not random_curve.empty
    assert random_curve[["ci_low", "ci_high"]].isna().all().all()
    assert random_curve[["sensitivity_low", "sensitivity_high"]].notna().all().all()
    assert (
        random_curve["sensitivity_low"] <= random_curve["sensitivity_high"]
    ).all()


def test_historical_promotion_fails_unobserved_resource_guardrail():
    decision = pd.read_csv(SPRINT3_DIR / "promotion_decision.csv")
    assert not decision["condition_4_operational_guardrails_passed"].astype(bool).any()
    assert not decision["promoted"].astype(bool).any()
    assert set(decision["condition_4_evaluation"]) == {
        "conservative_fail_historical_max_memory_percent_not_recorded"
    }
