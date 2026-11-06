"""Lenta ingest and R10: the post-treatment gate and the honesty of "replication".

Two risks are worth testing here and neither is statistical.  The first is
leakage: Lenta ships columns that record the response *to the campaign*, and
a model that reads them is reading the answer.  The second is a quiet
substitution: calling something a replication when it shares the customers,
or when the protocol was re-implemented rather than reused.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from telco_churn import lenta_data
from telco_churn.external_replication import (
    PREDICTIONS,
    ReplicationReport,
    render_markdown,
)
from telco_churn.lenta_data import (
    OUTCOME_COLUMN,
    POST_TREATMENT_COLUMNS,
    TREATMENT_COLUMN,
    assert_no_post_treatment_features,
    feature_frame,
    make_split,
)


def _frame(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "row_id": [f"lenta-{index:07d}" for index in range(n)],
            TREATMENT_COLUMN: rng.choice(["test", "control"], n, p=[0.75, 0.25]),
            OUTCOME_COLUMN: rng.integers(0, 2, n).astype(float),
            "response_sms": rng.integers(0, 2, n).astype(float),
            "response_viber": rng.integers(0, 2, n).astype(float),
            "age": rng.normal(45, 12, n),
            "cheque_count_12m_g20": rng.poisson(3, n).astype(float),
            "gender": rng.choice(["M", "F", None], n),
            "customer_uuid": [hashlib.sha256(str(i).encode()).hexdigest() for i in range(n)],
        }
    )
    return frame


# -- the post-treatment gate ----------------------------------------------
def test_the_campaign_response_columns_are_declared_post_treatment() -> None:
    assert "response_sms" in POST_TREATMENT_COLUMNS
    assert "response_viber" in POST_TREATMENT_COLUMNS
    assert OUTCOME_COLUMN in POST_TREATMENT_COLUMNS


def test_a_feature_list_containing_a_response_column_is_refused() -> None:
    with pytest.raises(ValueError, match="reading the answer"):
        assert_no_post_treatment_features(["age", "response_sms"])


def test_the_feature_frame_excludes_every_post_treatment_column() -> None:
    features = feature_frame(_frame())
    for column in POST_TREATMENT_COLUMNS:
        assert column not in features.columns
    assert TREATMENT_COLUMN not in features.columns
    assert "row_id" not in features.columns


def test_a_high_cardinality_identifier_is_dropped() -> None:
    """An id column would explode a one-hot encoder and is not a feature."""

    features = feature_frame(_frame())
    assert "customer_uuid" not in features.columns
    assert "gender" in features.columns, "a real low-cardinality category is kept"


def test_real_features_survive_the_gate() -> None:
    features = feature_frame(_frame())
    assert "age" in features.columns
    assert "cheque_count_12m_g20" in features.columns


# -- the split -------------------------------------------------------------
def test_the_split_is_reproducible_from_the_row_id_alone() -> None:
    frame = _frame()
    assert make_split(frame).tolist() == make_split(frame.sample(frac=1)).sort_index().tolist()


def test_the_split_is_roughly_the_declared_fraction() -> None:
    split = make_split(_frame(4_000))
    share = float((split == "development").mean())
    assert share == pytest.approx(lenta_data.DEVELOPMENT_FRACTION, abs=0.03)


def test_a_different_salt_gives_a_different_split() -> None:
    frame = _frame()
    assert make_split(frame).tolist() != make_split(frame, salt="other").tolist()


# -- loading contracts -----------------------------------------------------
def test_an_unexpected_treatment_group_is_refused(tmp_path) -> None:
    frame = _frame()
    frame.loc[0, TREATMENT_COLUMN] = "holdout"
    path = tmp_path / "lenta.csv"
    frame.drop(columns=["row_id"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="unexpected treatment groups"):
        lenta_data.load_lenta(path)


def test_a_missing_outcome_column_is_refused(tmp_path) -> None:
    frame = _frame().drop(columns=[OUTCOME_COLUMN, "row_id"])
    path = tmp_path / "lenta.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="schema has changed"):
        lenta_data.load_lenta(path)


def test_the_digest_is_pinned_so_an_upstream_change_is_caught() -> None:
    """A hash that is None would absorb a silently changed file."""

    assert lenta_data.EXPECTED_SHA256
    assert len(lenta_data.EXPECTED_SHA256) == 64


# -- what counts as a replication -----------------------------------------
def _report(**overrides) -> ReplicationReport:
    base = {
        "dataset": "lenta",
        "started_at": "now",
        "n_units": 60_000,
        "n_events": 6_500,
        "propensity": 0.75,
        "asymmetry_index": 0.032,
        "n_development_total": 549_867,
    }
    base.update(overrides)
    return ReplicationReport(**base)


def test_the_predictions_are_registered_as_three_named_claims() -> None:
    assert len(PREDICTIONS) == 3
    assert {name for name, _text in PREDICTIONS} == {
        "P1_a_causal_learner_wins",
        "P2_configurations_stabilise",
        "P3_a_learning_curve_appears",
    }


def test_p1_is_falsified_when_no_causal_learner_beats_the_baseline() -> None:
    report = _report(
        screening={
            "results": [
                {"candidate_id": "M01", "status": "COMPLETED", "mean_delta_vs_baseline": 0.0},
                {"candidate_id": "M03", "status": "COMPLETED", "mean_delta_vs_baseline": -0.001},
            ]
        }
    )
    scored = report.score_predictions()["P1_a_causal_learner_wins"]
    assert scored["held"] is False
    assert scored["candidates_beating_the_baseline"] == []


def test_p1_holds_when_one_does() -> None:
    report = _report(
        screening={
            "results": [
                {"candidate_id": "M03", "status": "COMPLETED", "mean_delta_vs_baseline": 0.002},
            ]
        }
    )
    assert report.score_predictions()["P1_a_causal_learner_wins"]["held"] is True


def test_the_baseline_cannot_satisfy_p1_by_beating_itself() -> None:
    report = _report(
        screening={
            "results": [
                {"candidate_id": "M01", "status": "COMPLETED", "mean_delta_vs_baseline": 0.5},
            ]
        }
    )
    assert report.score_predictions()["P1_a_causal_learner_wins"]["held"] is False


def test_p2_needs_an_actually_stable_configuration() -> None:
    unstable = _report(
        tuning={
            "results": [
                {"candidate_id": "M03", "status": "COMPLETED", "configuration_stable": False}
            ]
        }
    )
    assert unstable.score_predictions()["P2_configurations_stabilise"]["held"] is False
    stable = _report(
        tuning={
            "results": [
                {"candidate_id": "M03", "status": "COMPLETED", "configuration_stable": True}
            ]
        }
    )
    assert stable.score_predictions()["P2_configurations_stabilise"]["held"] is True


def test_p3_needs_the_curve_to_actually_rise() -> None:
    flat = _report(
        curves={
            "curves": {
                "M01": [
                    {"training_fraction": 0.25, "mean_value": 0.002},
                    {"training_fraction": 1.0, "mean_value": 0.001},
                ]
            }
        }
    )
    assert flat.score_predictions()["P3_a_learning_curve_appears"]["held"] is False
    rising = _report(
        curves={
            "curves": {
                "M01": [
                    {"training_fraction": 0.25, "mean_value": 0.001},
                    {"training_fraction": 1.0, "mean_value": 0.002},
                ]
            }
        }
    )
    assert rising.score_predictions()["P3_a_learning_curve_appears"]["held"] is True


def test_the_artifact_says_why_this_domain_is_independent() -> None:
    payload = _report().to_dict()
    assert payload["is_independent_domain"] is True
    assert "Womens arm" in payload["why_independent"]
    assert "SMS" in payload["why_independent"]


def test_r04_is_declared_not_transferable_rather_than_quietly_skipped() -> None:
    """Running a different factorial under the same name would be substitution."""

    payload = _report().to_dict()
    assert payload["stages_replicated"] == ["R02", "R03", "R05"]
    assert "R04" in payload["stages_not_transferable"]
    assert "substitution" in payload["stages_not_transferable"]["R04"]


def test_the_artifact_declares_its_subsample(_unused=None) -> None:
    payload = _report().to_dict()
    assert payload["cohort"]["subsample_rows"] > 0
    assert payload["cohort"]["n_development_total"] > payload["cohort"]["subsample_rows"]


def test_two_datasets_is_not_called_a_settled_answer() -> None:
    assert "not a settled answer" in _report().to_dict()["scope_note"]


def test_the_markdown_lists_every_prediction_and_its_verdict() -> None:
    rendered = render_markdown(_report())
    for name, _text in PREDICTIONS:
        assert name in rendered
    assert "R04 is not run here" in rendered
