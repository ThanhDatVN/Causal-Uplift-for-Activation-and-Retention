"""Hillstrom adapter: the contract, the split, and the leakage gates (WP03).

The dataset itself is fetched locally and not redistributed, so the tests that
need real bytes skip when it is absent.  Everything that can be checked on a
hand-built frame is checked without the download, because a leakage gate that
only works when the real file is present is not a gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from telco_churn.hillstrom_data import (
    ARMS,
    CONTROL_ARM,
    DEFAULT_PATH,
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    POST_TREATMENT_COLUMNS,
    TREATMENT_COLUMN,
    assert_no_post_treatment_features,
    build_manifest,
    feature_frame,
    file_sha256,
    load_hillstrom,
    make_split,
)

RAW = Path(DEFAULT_PATH)
needs_raw = pytest.mark.skipif(
    not RAW.exists(), reason="raw Hillstrom CSV is fetched locally and not redistributed"
)


def _fixture_frame(n: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    return pd.DataFrame(
        {
            "row_id": range(n),
            "recency": rng.integers(1, 12, n),
            "history": rng.gamma(2.0, 50.0, n),
            "mens": rng.integers(0, 2, n),
            "womens": rng.integers(0, 2, n),
            "newbie": rng.integers(0, 2, n),
            "history_segment": ["2) $100 - $200"] * n,
            "zip_code": ["Surburban"] * n,
            "channel": ["Web"] * n,
            TREATMENT_COLUMN: [ARMS[index % 3] for index in range(n)],
            "visit": rng.integers(0, 2, n),
            "conversion": rng.integers(0, 2, n),
            "spend": rng.gamma(1.0, 10.0, n),
        }
    )


# -- leakage gates ----------------------------------------------------------
@pytest.mark.parametrize("column", POST_TREATMENT_COLUMNS)
def test_a_post_treatment_column_can_never_be_a_feature(column: str) -> None:
    with pytest.raises(ValueError, match="post-treatment"):
        assert_no_post_treatment_features(["recency", column])


def test_the_treatment_column_can_never_be_a_feature() -> None:
    with pytest.raises(ValueError, match="is the treatment"):
        assert_no_post_treatment_features(["recency", TREATMENT_COLUMN])


def test_the_feature_frame_excludes_outcomes_and_the_arm() -> None:
    features = feature_frame(_fixture_frame())
    for forbidden in (*POST_TREATMENT_COLUMNS, TREATMENT_COLUMN):
        assert forbidden not in features.columns
    assert "log1p_history" in features.columns
    assert "history" not in features.columns, "the raw skewed column is replaced, not kept twice"


def test_history_segment_can_be_dropped_as_a_declared_choice() -> None:
    kept = feature_frame(_fixture_frame(), keep_history_segment=True)
    dropped = feature_frame(_fixture_frame(), keep_history_segment=False)
    assert "history_segment" in kept.columns
    assert "history_segment" not in dropped.columns
    assert len(dropped.columns) == len(kept.columns) - 1


def test_log1p_is_applied_to_the_spend_history() -> None:
    frame = _fixture_frame()
    features = feature_frame(frame)
    expected = np.log1p(frame["history"].to_numpy(dtype=float))
    assert np.allclose(features["log1p_history"].to_numpy(), expected)


# -- the split --------------------------------------------------------------
def test_the_split_is_deterministic_and_order_independent() -> None:
    frame = _fixture_frame(400)
    first = make_split(frame)
    shuffled = frame.sample(frac=1.0, random_state=1).reset_index(drop=True)
    second = make_split(shuffled)
    # Same row_id must land in the same split whatever order it arrives in.
    lookup = dict(zip(shuffled["row_id"], second, strict=True))
    assert all(
        lookup[row_id] == value for row_id, value in zip(frame["row_id"], first, strict=True)
    )


def test_the_split_holds_roughly_the_declared_fraction() -> None:
    frame = _fixture_frame(4000)
    share = (make_split(frame) == "development").mean()
    assert 0.77 < share < 0.83


def test_a_different_salt_gives_a_different_split() -> None:
    frame = _fixture_frame(400)
    assert not make_split(frame).equals(make_split(frame, salt="other"))


# -- the manifest -----------------------------------------------------------
def test_the_manifest_never_reads_confirmation_outcomes(tmp_path) -> None:
    frame = _fixture_frame(400)
    split = make_split(frame)
    raw = tmp_path / "fake.csv"
    raw.write_bytes(b"not the real file")
    manifest = build_manifest(raw, frame, split)

    assert manifest["confirmation_outcomes_read"] is False
    assert "outcome_by_arm" not in manifest, "the whole-file outcome summary must not exist"

    # The reported conversions must match the development split alone.
    development = frame.loc[split.to_numpy() == "development"]
    for arm, row in manifest["outcome_by_arm_development_only"].items():
        expected = development.loc[development[TREATMENT_COLUMN] == arm, "conversion"].sum()
        assert row["conversion"] == pytest.approx(float(expected))


def test_the_manifest_records_provenance_and_refuses_redistribution(tmp_path) -> None:
    raw = tmp_path / "fake.csv"
    raw.write_bytes(b"bytes")
    frame = _fixture_frame(40)
    manifest = build_manifest(raw, frame, make_split(frame))
    assert manifest["redistributed"] is False
    assert manifest["raw_sha256"] == file_sha256(raw)
    assert manifest["source_url"].startswith("http")
    assert manifest["retrieved_at"]
    assert manifest["feature_recipe"]["excluded_as_post_treatment"] == list(POST_TREATMENT_COLUMNS)


# -- the real file ----------------------------------------------------------
@needs_raw
def test_the_fetched_file_matches_the_pinned_checksum() -> None:
    assert EXPECTED_SHA256 is not None, "the checksum must be measured, never invented"
    assert file_sha256(RAW) == EXPECTED_SHA256


@needs_raw
def test_the_real_file_has_the_declared_shape() -> None:
    frame = load_hillstrom(RAW)
    assert len(frame) == EXPECTED_ROWS
    assert sorted(frame[TREATMENT_COLUMN].unique()) == sorted(ARMS)
    assert CONTROL_ARM in set(frame[TREATMENT_COLUMN])
    # Roughly a third per arm: this is the balanced design Orange did not have.
    shares = frame[TREATMENT_COLUMN].value_counts(normalize=True)
    assert shares.min() > 0.32


@needs_raw
def test_the_real_split_covers_every_row_exactly_once() -> None:
    frame = load_hillstrom(RAW)
    split = make_split(frame)
    assert len(split) == len(frame)
    assert set(split.unique()) == {"development", "confirmation"}
    assert split.isna().sum() == 0


@needs_raw
def test_the_shipped_manifest_is_current() -> None:
    path = Path("reports/hillstrom/dataset_manifest.json")
    if not path.exists():
        pytest.skip("manifest not generated in this working copy")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["raw_sha256"] == file_sha256(RAW)
    assert manifest["rows"] == EXPECTED_ROWS
    assert manifest["confirmation_outcomes_read"] is False


@needs_raw
def test_the_assignment_audit_runs_on_the_primary_contrast() -> None:
    """The same audit that rejected Orange must be runnable here."""

    import json
    from pathlib import Path as _Path

    report = _Path("reports/v4/assignment_audit_hillstrom.json")
    if not report.exists():
        pytest.skip("the Hillstrom audit has not been run in this working copy")
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["dataset"].startswith("Hillstrom")
    # Only the declared primary contrast is audited, not all three arms.
    assert payload["n_rows"] < EXPECTED_ROWS
    assert payload["n_features"] == 8
    propensity = payload["estimated_propensity"]
    kept = (
        propensity["effective_sample_size_estimated_e"]
        / propensity["effective_sample_size_constant_e"]
    )
    # The result this unblocks: reweighting stays usable, unlike Orange.
    assert kept > 0.5
