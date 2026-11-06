"""Hillstrom MineThatData adapter: acquisition, contract and split (WP03).

The V4.1 plan names this the real-data primary: *"Hillstrom Mens versus No
email, conversion hai tuần, eligible source population"*.  It is the dataset
Orange could not be -- a randomised e-mail campaign with three arms, a real
spend outcome, and a documented design.

The raw file is **not redistributed**.  It is fetched from the author's site
into the local workspace, checksummed, and recorded in a manifest; the
repository ships the loader, not the data.

Three contract decisions are enforced here rather than left to the caller,
because each one is a way the study could quietly become invalid:

* **``segment`` is the treatment, never a feature.**  It names which arm the
  account was assigned to.  A model that reads it is reading the answer.
* **``visit``, ``conversion`` and ``spend`` are post-treatment.**  They are
  outcomes, so :func:`feature_frame` refuses to return them and
  :func:`assert_no_post_treatment_features` states why.
* **``history_segment`` is a binned copy of ``history``.**  Keeping both is a
  declared representation choice, not a default, so the recipe records which
  one it used.

The split is frozen before any label is read: 80% development / 20%
confirmation, hashed by account row id, so it is reproducible from the raw
file alone and does not depend on row order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "ARMS",
    "POST_TREATMENT_COLUMNS",
    "assert_no_post_treatment_features",
    "build_manifest",
    "feature_frame",
    "fetch_hillstrom",
    "load_hillstrom",
    "main",
    "make_split",
]

SOURCE_URL = (
    "http://www.minethatdata.com/"
    "Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
)
SOURCE_DESCRIPTION = (
    "Kevin Hillstrom, MineThatData E-Mail Analytics And Data Mining Challenge, "
    "published 2008-03-20. Released publicly for analysis; the author asks that "
    "the source be credited. Raw data is not redistributed by this repository."
)
DEFAULT_PATH = Path("data/raw/hillstrom.csv")
EXPECTED_ROWS = 64_000
#: Measured from the file this repository actually fetched on 2026-09-21.
#: Never write a checksum that has not been computed from the bytes on disk.
EXPECTED_SHA256: str | None = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"

#: The treatment column and its three arms, exactly as the source encodes them.
TREATMENT_COLUMN = "segment"
ARMS: tuple[str, ...] = ("No E-Mail", "Mens E-Mail", "Womens E-Mail")
CONTROL_ARM = "No E-Mail"

#: Measured after the e-mail was sent.  None of these may enter X.
POST_TREATMENT_COLUMNS: tuple[str, ...] = ("visit", "conversion", "spend")

#: The feature recipe declared in runbook §3.
NUMERIC_FEATURES: tuple[str, ...] = ("recency", "history")
BINARY_FEATURES: tuple[str, ...] = ("mens", "womens", "newbie")
CATEGORICAL_FEATURES: tuple[str, ...] = ("history_segment", "zip_code", "channel")

DEVELOPMENT_FRACTION = 0.8
SPLIT_SALT = "hillstrom-v4.1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_hillstrom(path: Path | str = DEFAULT_PATH, *, force: bool = False) -> Path:
    """Download the raw CSV atomically into the local workspace."""

    destination = Path(path)
    if destination.exists() and not force:
        _verify_checksum(destination)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".download")
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "TelcoChurnDecisionSystem/0.2 (research)"}
    )
    with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as out:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    partial.replace(destination)
    _verify_checksum(destination)
    return destination


def _verify_checksum(path: Path) -> None:
    """Fail when the file on disk is not the one this repository was built on."""

    if EXPECTED_SHA256 is None:
        return
    actual = file_sha256(path)
    if actual != EXPECTED_SHA256:
        raise ValueError(
            f"{path} has sha256 {actual}; the pinned source is {EXPECTED_SHA256}. "
            "The upstream file changed, or this is a different file. Delete it and "
            "refetch, or update the pin deliberately with the new value recorded."
        )


def load_hillstrom(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    """Read the raw CSV and check the structure the contract depends on."""

    frame = pd.read_csv(path)
    missing = [
        column
        for column in (
            *NUMERIC_FEATURES,
            *BINARY_FEATURES,
            *CATEGORICAL_FEATURES,
            TREATMENT_COLUMN,
            *POST_TREATMENT_COLUMNS,
        )
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"the source file is missing expected columns: {missing}")
    if len(frame) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} rows, found {len(frame)}")
    arms = sorted(frame[TREATMENT_COLUMN].unique())
    if arms != sorted(ARMS):
        raise ValueError(f"unexpected treatment arms: {arms}")
    # A stable identifier that does not depend on row order for its meaning.
    frame = frame.reset_index(drop=False).rename(columns={"index": "row_id"})
    return frame


def assert_no_post_treatment_features(columns: Sequence[str]) -> None:
    """Refuse any column that is measured after the e-mail was sent."""

    leaked = [column for column in columns if column in POST_TREATMENT_COLUMNS]
    if leaked:
        raise ValueError(
            f"post-treatment columns {leaked} cannot be features: they are measured after "
            "the assignment and carry the outcome"
        )
    if TREATMENT_COLUMN in columns:
        raise ValueError(
            f"{TREATMENT_COLUMN!r} is the treatment, not a feature; a model that reads it "
            "is reading the assignment"
        )


def feature_frame(frame: pd.DataFrame, *, keep_history_segment: bool = True) -> pd.DataFrame:
    """X under the declared recipe, with the post-treatment gate applied.

    ``history`` enters as ``log1p`` because the raw spend history is heavily
    right-skewed; the binned ``history_segment`` is the same information at a
    coarser grain, so keeping both is recorded as a choice rather than assumed.
    """

    categorical = list(CATEGORICAL_FEATURES)
    if not keep_history_segment:
        categorical.remove("history_segment")
    selected = [*NUMERIC_FEATURES, *BINARY_FEATURES, *categorical]
    assert_no_post_treatment_features(selected)
    features = frame.loc[:, selected].copy()
    features["history"] = np.log1p(features["history"].to_numpy(dtype=float))
    features = features.rename(columns={"history": "log1p_history"})
    return features


def make_split(frame: pd.DataFrame, *, salt: str = SPLIT_SALT) -> pd.Series:
    """Deterministic development/confirmation split, hashed per row id.

    Hashing rather than sampling means the split is reproducible from the raw
    file alone, is stable if rows are reordered, and does not need a stored
    random state that could drift.
    """

    def assign(row_id: int) -> str:
        digest = hashlib.sha256(f"{salt}:{row_id}".encode()).hexdigest()
        # First 8 hex digits as a uniform draw on [0, 1).
        draw = int(digest[:8], 16) / 0xFFFFFFFF
        return "development" if draw < DEVELOPMENT_FRACTION else "confirmation"

    return frame["row_id"].map(assign).astype("string")


def build_manifest(path: Path | str, frame: pd.DataFrame, split: pd.Series) -> dict[str, Any]:
    """Everything needed to say which file and which split produced a result.

    The outcome summary is computed on the **development split only**.  Arm
    counts are design facts and are reported for the whole file, but reading
    confirmation outcomes here would spend the confirmation split on a data
    card -- the one thing the data-role contract exists to prevent.  The
    manifest records that they were not read, so a later reader can tell the
    difference between "not interesting" and "deliberately unopened".
    """

    arm_counts = frame[TREATMENT_COLUMN].value_counts().to_dict()
    development = frame.loc[split.to_numpy() == "development"]
    outcome_by_arm = (
        development.groupby(TREATMENT_COLUMN)[["visit", "conversion", "spend"]]
        .agg({"visit": "mean", "conversion": "sum", "spend": "mean"})
        .to_dict(orient="index")
    )
    return {
        "dataset_id": "hillstrom_minethatdata",
        "version": "2008.03.20",
        "source_url": SOURCE_URL,
        "source_description": SOURCE_DESCRIPTION,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "raw_sha256": file_sha256(path),
        "raw_bytes": Path(path).stat().st_size,
        "rows": len(frame),
        "redistributed": False,
        "treatment_column": TREATMENT_COLUMN,
        "arms": {str(arm): int(count) for arm, count in arm_counts.items()},
        "control_arm": CONTROL_ARM,
        "post_treatment_columns": list(POST_TREATMENT_COLUMNS),
        "feature_recipe": {
            "numeric": list(NUMERIC_FEATURES),
            "numeric_transform": {"history": "log1p"},
            "binary": list(BINARY_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
            "excluded_as_treatment": [TREATMENT_COLUMN],
            "excluded_as_post_treatment": list(POST_TREATMENT_COLUMNS),
        },
        "split": {
            "rule": f"sha256('{SPLIT_SALT}:' + row_id), first 8 hex digits as a uniform draw",
            "development_fraction": DEVELOPMENT_FRACTION,
            "counts": {str(k): int(v) for k, v in split.value_counts().to_dict().items()},
        },
        "outcome_by_arm_development_only": {
            str(arm): {key: float(value) for key, value in row.items()}
            for arm, row in outcome_by_arm.items()
        },
        "confirmation_outcomes_read": False,
        "data_roles": {
            "development": "model selection, tuning, all exploratory readouts",
            "confirmation": "unopened; one primary contrast, after the protocol is frozen",
        },
        "scope_note": (
            "Randomised three-arm e-mail campaign with a two-week readout. The design is "
            "documented by the author but this repository has not verified assignment "
            "independently; treat the design probability as declared, not measured, until "
            "an assignment audit has been run."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "validate"))
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--manifest", default="reports/hillstrom/dataset_manifest.json")
    parser.add_argument("--split-output", default="data/splits/hillstrom_split.csv")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if args.command == "fetch":
        fetch_hillstrom(path, force=args.force)
        print(f"Fetched {path} ({path.stat().st_size:,} bytes)")
        print(f"sha256 {file_sha256(path)}")
        return 0

    if not path.exists():
        print(f"{path} is missing; run `python -m telco_churn.hillstrom_data fetch` first")
        return 1
    frame = load_hillstrom(path)
    split = make_split(frame)
    manifest = build_manifest(path, frame, split)

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    split_path = Path(args.split_output)
    split_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"row_id": frame["row_id"], "split": split}).to_csv(split_path, index=False)

    print(f"rows {manifest['rows']:,} | sha256 {manifest['raw_sha256'][:16]}...")
    print("arms:", manifest["arms"])
    print("split:", manifest["split"]["counts"])
    print("outcomes below are DEVELOPMENT SPLIT ONLY; confirmation stays unopened")
    for arm, row in manifest["outcome_by_arm_development_only"].items():
        print(
            f"  {arm:<14} visit {row['visit']:.4f} | conversions {row['conversion']:.0f} "
            f"| mean spend {row['spend']:.4f}"
        )
    print(f"Manifest: {manifest_path}")
    print(f"Split:    {split_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
