import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parent.parent
IMPROVEMENT = ROOT / "output" / "improvement"


def _require(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"Local causal-foundation artifact is not available: {path}")
    return path


@pytest.mark.requires_artifacts
def test_screen_fold_seeds_use_the_same_registered_oof_population():
    manifests = []
    for seed in (101, 202):
        path = _require(
            IMPROVEMENT
            / f"causal_foundation_screen_seed{seed}"
            / "run_manifest.json"
        )
        manifests.append(json.loads(path.read_text(encoding="utf-8")))

    assert manifests[0]["development_index_sha256"] == manifests[1][
        "development_index_sha256"
    ]
    assert manifests[0]["arm_counts"] == manifests[1]["arm_counts"]
    assert all(item["resource_gate_passed"] for item in manifests)


@pytest.mark.requires_artifacts
def test_no_causal_candidate_passes_the_two_seed_screen_gate():
    path = _require(
        IMPROVEMENT
        / "causal_foundation_comparison"
        / "advancement_decision.csv"
    )
    decisions = pd.read_csv(path).set_index("model")

    assert bool(decisions.loc["Response-Sentinel", "advance"])
    for candidate in (
        "Anchored-R25",
        "Anchored-R25-Sentinel",
        "Anchored-Pattern-R",
        "DINA-CATE-Sentinel",
    ):
        assert not bool(decisions.loc[candidate, "advance"])


@pytest.mark.requires_artifacts
def test_full_development_rejects_the_screen_finalist():
    decision_path = _require(
        IMPROVEMENT
        / "causal_foundation_finalist_comparison"
        / "advancement_decision.csv"
    )
    shortlist_path = _require(
        IMPROVEMENT
        / "causal_foundation_finalist_comparison"
        / "shortlist.json"
    )
    decisions = pd.read_csv(decision_path).set_index("model")
    shortlist = json.loads(shortlist_path.read_text(encoding="utf-8"))

    assert decisions.loc["Response-Sentinel", "min_policy_area_delta"] < 0
    assert not bool(decisions.loc["Response-Sentinel", "advance"])
    assert shortlist["shortlist"] == ["Response"]


@pytest.mark.requires_artifacts
def test_analysis_summary_retains_response_without_confirmation_reuse():
    path = _require(
        IMPROVEMENT
        / "causal_foundation_analysis"
        / "analysis_summary.json"
    )
    summary = json.loads(path.read_text(encoding="utf-8"))

    assert summary["decision"] == "retain_response"
    assert summary["causal_candidates_advancing"] == []
    assert summary["full_advancing_candidates"] == []
    assert summary["sprint2_confirmation_read"] is False
    assert summary["causal_forest_executed"] is False
