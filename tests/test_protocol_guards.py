"""Những luật đã đăng ký có thực sự được cưỡng chế không.

Đây là nhóm test đặc thù nhất của repo. Nó không kiểm toán học mà kiểm **quy trình**.

- **Early stop phát hiện dominance theo budget** — candidate thua ở mọi mức `5–20%` phải bị
  dừng, không được chạy tiếp lên full.
- **Promotion guardrail kiểm đủ ba thứ**: resource gate, score hữu hạn không suy biến, và
  calibration hữu hạn nếu model ở thang CATE.
- **Execution contract từ chối CLI trôi khỏi protocol.** Đây là chỗ dễ mất chính trực nhất:
  chạy với `--pool-frac` khác rồi báo cáo như thể đúng protocol. Contract so tham số dòng
  lệnh với giao ước đã đăng ký và **dừng** nếu lệch, kể cả khi lệch có vẻ vô hại.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.run_oof_experiment import (
    early_stop_reason,
    validate_execution_contract,
)
from scripts.run_sprint3_confirmation import (
    aggregate_ensemble_entries,
    promotion_guardrail,
)


def _protocol():
    return {
        "early_stop": {
            "constant_score_unique_threshold": 3,
            "dominated_at_every_budget_5_to_20": True,
        }
    }


def test_early_stop_detects_budget_dominance():
    budgets = np.array([0.01, 0.05, 0.10, 0.20, 0.30])
    reason = early_stop_reason(
        np.arange(20, dtype="float64"),
        _protocol(),
        candidate_curve=np.array([2.0, 0.9, 0.8, 0.7, 2.0]),
        reference_curve=np.ones(5),
        budgets=budgets,
    )
    assert reason == "dominated_at_every_budget_5_to_20"


def test_promotion_guardrail_checks_resource_score_and_calibration():
    score = np.arange(20, dtype="float64")
    passed = promotion_guardrail(
        score,
        is_cate_scale=True,
        calibration_error=0.001,
        monitor=SimpleNamespace(breached=False),
        protocol=_protocol(),
    )
    assert passed["condition_4"] is True

    failed = promotion_guardrail(
        score,
        is_cate_scale=True,
        calibration_error=np.nan,
        monitor=SimpleNamespace(breached=False),
        protocol=_protocol(),
    )
    assert failed["condition_4"] is False
    assert failed["calibration_guardrail_passed"] is False


def test_ensemble_entries_are_averaged_across_seeds():
    entries = {
        "Ensemble-QAgg@seed101": {
            "method": "causal_q_aggregation",
            "full_sample_weights": {"a": 0.8, "b": 0.2},
        },
        "Ensemble-QAgg@seed202": {
            "method": "causal_q_aggregation",
            "full_sample_weights": {"a": 0.4, "b": 0.6},
        },
    }
    result = aggregate_ensemble_entries("Ensemble-QAgg", entries)
    assert result["full_sample_weights"] == pytest.approx({"a": 0.6, "b": 0.4})
    assert result["aggregation"] == "mean_weights_across_seeds"


def _registered_execution_protocol():
    return {
        "cross_fitting": {
            "n_folds": 3,
            "primary_fold_seed": 101,
            "secondary_fold_seed": 202,
        },
        "execution": {
            "smoke_pool_fraction": 0.01,
            "screen_pool_fraction": 0.15,
            "smoke_bootstrap_replicates": 30,
            "primary_seed_bootstrap_replicates": 200,
            "secondary_seed_bootstrap_replicates": 100,
            "process_isolated_component_bootstrap_replicates": 2,
        },
    }


@pytest.mark.parametrize(
    ("stage", "pool_fraction", "fold_seed", "n_boot"),
    [
        ("smoke", 0.01, 101, 30),
        ("screen", 0.15, 101, 200),
        ("screen", 0.15, 202, 100),
        ("finalist", 1.0, 101, 200),
        ("finalist", 1.0, 202, 2),
    ],
)
def test_registered_execution_contract_accepts_only_declared_runs(
    stage,
    pool_fraction,
    fold_seed,
    n_boot,
):
    validate_execution_contract(
        _registered_execution_protocol(),
        stage=stage,
        pool_fraction=pool_fraction,
        fold_seed=fold_seed,
        n_folds=3,
        n_boot=n_boot,
    )


@pytest.mark.parametrize(
    "override",
    [
        {"pool_fraction": 0.20},
        {"fold_seed": 999},
        {"n_folds": 5},
        {"n_boot": 50},
    ],
)
def test_registered_execution_contract_rejects_silent_cli_drift(override):
    values = {
        "stage": "screen",
        "pool_fraction": 0.15,
        "fold_seed": 101,
        "n_folds": 3,
        "n_boot": 200,
        **override,
    }
    with pytest.raises(ValueError):
        validate_execution_contract(_registered_execution_protocol(), **values)


def test_registered_execution_contract_rejects_outcome_estimand_drift():
    protocol = _registered_execution_protocol()
    protocol["estimand"] = {"outcome": "conversion"}

    with pytest.raises(ValueError, match="outcome"):
        validate_execution_contract(
            protocol,
            stage="screen",
            pool_fraction=0.15,
            fold_seed=101,
            n_folds=3,
            n_boot=200,
            outcome="visit",
        )
