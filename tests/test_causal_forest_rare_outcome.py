"""Khoá giao ước của protocol `causal-forest-rare-outcome-v1`.

Ba loại lỗi test này bắt, cả ba đều làm hỏng một lần chạy Kaggle dài:

1. **Hai bảng ``SCORE_NAMES`` lệch nhau.** Gate cố ý không import trainer để giữ
   tiến trình giám sát nhẹ, nên hai bảng được viết tay hai nơi. Lệch tên file thì
   gate báo thiếu artifact sau khi đã fit xong.
2. **Cấu hình trong code lệch cấu hình đã đăng ký.** Protocol là thứ được công bố
   trước khi chạy; nếu code chạy số khác thì kết quả không còn là kết quả đã đăng ký.
3. **Sai lý do tồn tại của profile.** ``rare-outcome`` chỉ có nghĩa nếu nó thực sự
   nâng số sự kiện control mỗi lá lên; test tính lại con số đó từ tỷ lệ đã đo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kaggle_causal_forest_gate import SCORE_NAMES as GATE_SCORE_NAMES
from scripts.train_causal_forest import PROFILES, SCORE_NAMES

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = REPO_ROOT / "configs" / "causal_forest_rare_outcome_protocol_v1.json"

# Đo trên toàn bộ Criteo v2.1, xem output/eda/average_treatment_effect.csv.
CONTROL_SHARE = 0.15
CONTROL_CONVERSION_RATE = 0.001938


@pytest.fixture(scope="module")
def protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_gate_and_trainer_agree_on_score_filenames():
    assert GATE_SCORE_NAMES == SCORE_NAMES


def test_every_profile_has_a_score_filename():
    assert set(SCORE_NAMES) == set(PROFILES)


def test_historical_score_filenames_are_unchanged():
    """Artifact đã phát hành đọc bằng đúng hai tên này; đổi là hỏng tái lập."""
    assert SCORE_NAMES["kaggle-safe"] == "cate_causal_forest_kaggle_safe.npy"
    assert SCORE_NAMES["research"] == "cate_causal_forest.npy"


def test_score_filenames_are_distinct():
    assert len(set(SCORE_NAMES.values())) == len(SCORE_NAMES)


def test_registered_protocol_matches_code(protocol):
    registered = protocol["configuration"]
    profile = PROFILES["rare-outcome"]
    for key in ("n_estimators", "min_samples_leaf", "cv", "max_samples", "inference"):
        assert profile[key] == registered[key], (
            f"Tham số {key} trong code là {profile[key]} nhưng protocol đăng ký "
            f"{registered[key]}"
        )


def test_n_estimators_divisible_by_subforest_size(protocol):
    """Trainer từ chối n_estimators không chia hết cho 4."""
    assert protocol["configuration"]["n_estimators"] % 4 == 0


def test_rare_outcome_raises_control_events_per_leaf():
    """Lý do tồn tại của profile: nâng số sự kiện control mỗi lá."""

    def events_per_leaf(leaf: int) -> float:
        return leaf * CONTROL_SHARE * CONTROL_CONVERSION_RATE

    old = events_per_leaf(PROFILES["kaggle-safe"]["min_samples_leaf"])
    new = events_per_leaf(PROFILES["rare-outcome"]["min_samples_leaf"])
    assert old < 0.2, f"kaggle-safe lẽ ra phải thiếu sự kiện control, đo được {old}"
    assert new > 2.0, f"rare-outcome phải có trên 2 sự kiện control mỗi lá, đo được {new}"
    assert new / old >= 15


def test_research_profile_is_not_the_rare_outcome_fix():
    """Ghi lại bằng test rằng `research` đi sai hướng trên ràng buộc đang bó.

    Nếu ai đó sửa `research` cho hợp outcome hiếm thì test này phải được đọc lại
    cùng tài liệu, chứ không phải sửa im lặng.
    """
    assert (
        PROFILES["research"]["min_samples_leaf"]
        < PROFILES["kaggle-safe"]["min_samples_leaf"]
    )


def test_protocol_declares_sprint3_split_and_frozen_signal(protocol):
    assert protocol["protocol_id"] == "causal-forest-rare-outcome-v1"
    assert protocol["data"]["split"] == "sprint3"
    assert protocol["data"]["train_rows"] == 5_591_836
    assert protocol["data"]["predict_rows"] == 1_397_959
    assert protocol["evaluation"]["signal_is_frozen"] is True
    assert protocol["evaluation"]["primary_metric"] == "policy_area_dr"


def test_protocol_states_expected_outcome_and_scope(protocol):
    """Protocol phải nói trước kỳ vọng, để kết quả không bị diễn giải hậu nghiệm."""
    assert protocol["status"] in {
        "registered_not_yet_run",
        "run_once_gate_failed_on_memory",
        "run_once_gate_passed",
    }
    assert protocol["decision_rule"]["expected_outcome"]
    assert protocol["scope_limits"]


def test_every_recorded_run_states_gate_outcome(protocol):
    """Mỗi lần chạy phải ghi đủ tài nguyên và trạng thái contract.

    Phân biệt 'artifact hỏng' với 'vượt ngân sách RAM' là điều quyết định điểm số
    có dùng được hay không, nên nó phải nằm trong artifact chứ không nằm trong trí nhớ.
    """
    for run in protocol.get("runs", []):
        assert run["gate_status"] in {"passed", "failed"}
        assert run["peak_ram_fraction"] > 0
        contract = run["artifact_contract"]
        assert set(contract) == {"score_rows", "all_finite", "aligned"}
        if run["gate_status"] == "failed":
            assert run["gate_failure_reason"], "Phải ghi vì sao gate fail"
