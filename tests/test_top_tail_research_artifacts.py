"""Vòng audit phần đuôi không được biến phát hiện hậu nghiệm thành kết luận.

Vòng top-tail v2 kiểm một quan sát **hậu nghiệm**: bốn causal candidate trông tốt hơn ở
budget `1–2%`. Rủi ro lớn nhất của một vòng như vậy là nó tự nâng quan sát đó thành bằng
chứng.

Bốn chốt chặn:

- protocol **tách bạch** audit hồi cứu với confirmation;
- audit **không** promote một chiến thắng hậu nghiệm, bất kể dấu của nó;
- khoảng đồng thời phải **phủ mọi** khoảng pointwise — nếu không thì mức tin cậy familywise
  bị phá và `16/16` dấu dương sẽ trông như bằng chứng;
- support và độ ổn định thành viên **được ghi lại**, vì `61,31%` overlap là lý do chính để
  không tin phần đuôi.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "configs" / "top_tail_research_protocol_v2.json"
ARTIFACT_DIR = ROOT / "output" / "improvement" / "top_tail_research_v2"


def test_top_tail_protocol_separates_retrospective_audit_from_confirmation():
    protocol = json.loads(PROTOCOL.read_text("utf-8"))

    assert protocol["estimand"]["outcome"] == "conversion"
    assert protocol["estimand"]["forbidden_features"] == ["visit", "exposure"]
    assert protocol["retrospective_audit"]["budget_grid"] == [0.01, 0.02]
    assert "no candidate selection" in protocol["scope_separation"][
        "retrospective_audit"
    ]
    assert protocol["future_experiment_gate"][
        "primary_budget_must_be_single_and_locked"
    ]
    assert protocol["future_experiment_gate"][
        "new_randomized_confirmation_required_for_promotion"
    ]


@pytest.mark.requires_artifacts
def test_retrospective_tail_audit_does_not_promote_post_hoc_wins():
    summary_path = ARTIFACT_DIR / "analysis_summary.json"
    if not summary_path.exists():
        pytest.skip(f"Top-tail research artifact is unavailable: {summary_path}")
    summary = json.loads(summary_path.read_text("utf-8"))

    assert summary["family_size"] == 20
    assert summary["protocol_sha256"] == hashlib.sha256(
        PROTOCOL.read_bytes()
    ).hexdigest()
    assert summary["all_causal_point_differences_positive"] is True
    assert summary["any_causal_simultaneous_lower_bound_positive"] is False
    assert summary["training_uncertainty_in_interval"] is False
    assert summary["promotion_allowed"] is False
    assert summary["decision"].startswith("retain_response")


@pytest.mark.requires_artifacts
def test_simultaneous_tail_intervals_cover_every_pointwise_interval():
    path = ARTIFACT_DIR / "simultaneous_tail_differences.csv"
    if not path.exists():
        pytest.skip(f"Top-tail research artifact is unavailable: {path}")
    frame = pd.read_csv(path)

    assert len(frame) == 20
    assert set(frame["budget_fraction"]) == {0.01, 0.02}
    assert (frame["simultaneous_ci_low"] <= frame["pointwise_ci_low"]).all()
    assert (frame["simultaneous_ci_high"] >= frame["pointwise_ci_high"]).all()
    assert not (frame["pointwise_ci_low"] > 0).any()


@pytest.mark.requires_artifacts
def test_tail_support_and_membership_stability_are_recorded():
    support_path = ARTIFACT_DIR / "tail_event_support.csv"
    overlap_path = ARTIFACT_DIR / "tail_membership_overlap.csv"
    if not support_path.exists() or not overlap_path.exists():
        pytest.skip("Top-tail support/overlap artifacts are unavailable")
    support = pd.read_csv(support_path)
    overlap = pd.read_csv(overlap_path)

    assert {"treated_events", "control_events", "boundary_tie_size"}.issubset(
        support.columns
    )
    assert {"overlap_fraction", "jaccard", "intersection_count"}.issubset(
        overlap.columns
    )
    dina_top_one = overlap.loc[
        (overlap["model"] == "DINA-CATE-Sentinel")
        & (overlap["budget_fraction"] == 0.01),
        "overlap_fraction",
    ].iloc[0]
    assert dina_top_one < 0.75
