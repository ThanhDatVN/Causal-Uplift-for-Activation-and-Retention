"""Lenta: the independent domain R10 needs, with its own post-treatment gate.

R10 asks whether the method recipe holds up in a domain it was not built on.
Hillstrom is e-mail marketing on a US retailer's list; Lenta is an SMS
campaign by a Russian grocery chain, with a different channel, a different
outcome and a different population.  That is what makes it a replication
rather than another slice of the same experiment -- unlike the Womens arm,
which shares the customers and the campaign and is reported separately for
exactly that reason.

Three things this module is careful about.

**Post-treatment columns.**  The frame ships ``response_sms`` and
``response_viber``, which record whether the customer responded *to the
campaign*.  They are consequences of the treatment, so a model that reads
them is reading the answer.  They are gated out by name and the gate is
asserted, not trusted.

**The treatment is unbalanced.**  Roughly three quarters of the frame is in
the test arm.  That is a design fact, not a nuisance: it is exactly the kind
of imbalance the asymmetry index was built to price, so the cohort's index
is computed and reported rather than assumed harmless.

**Nothing is redistributed.**  The raw file is fetched, hashed and left on
disk; only derived summaries are written into ``reports/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "CONTROL_GROUP",
    "DEFAULT_PATH",
    "OUTCOME_COLUMN",
    "POST_TREATMENT_COLUMNS",
    "SOURCE_URL",
    "TREATMENT_COLUMN",
    "TREATMENT_GROUP",
    "assert_no_post_treatment_features",
    "build_manifest",
    "feature_frame",
    "load_lenta",
    "main",
    "make_split",
]

SOURCE_URL = "https://sklift.s3.eu-west-2.amazonaws.com/lenta_dataset.csv.gz"
DEFAULT_PATH = "data/raw/lenta.csv.gz"

TREATMENT_COLUMN = "group"
TREATMENT_GROUP = "test"
CONTROL_GROUP = "control"
OUTCOME_COLUMN = "response_att"

#: Responses *to the campaign*.  A model that reads these is reading the
#: answer, so they never reach a feature frame.  ``response_att`` is the
#: outcome itself and is excluded from features for the same reason.
POST_TREATMENT_COLUMNS: tuple[str, ...] = (
    "response_att",
    "response_sms",
    "response_viber",
)

#: Hash of the file this study was run against, pinned after the first fetch
#: so a silently changed upstream file is caught rather than absorbed.
EXPECTED_SHA256: str | None = "b531544f6c072d22f232d91e20ffcaca265acf224e02687502a40e6d56135682"

DEVELOPMENT_FRACTION = 0.8
SPLIT_SALT = "lenta-v4.1"


def assert_no_post_treatment_features(columns: Sequence[str]) -> None:
    """Refuse a feature list that contains a consequence of the treatment."""

    leaked = sorted(set(columns) & set(POST_TREATMENT_COLUMNS))
    if leaked:
        raise ValueError(
            f"{leaked} are recorded after the treatment and may not be features; "
            "a model that reads them is reading the answer"
        )


def load_lenta(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    """Read the raw file and attach a stable row id.

    The row id is the position in the file as delivered.  The file is never
    reordered, so this is reproducible from the raw bytes alone and does not
    need a stored random state.
    """

    frame = pd.read_csv(path, compression="infer", low_memory=False)
    for column in (TREATMENT_COLUMN, OUTCOME_COLUMN):
        if column not in frame.columns:
            raise ValueError(
                f"{column!r} is missing from {path}; the upstream schema has changed "
                "and this module's assumptions need re-checking rather than patching"
            )
    groups = set(frame[TREATMENT_COLUMN].astype(str).unique())
    unexpected = groups - {TREATMENT_GROUP, CONTROL_GROUP}
    if unexpected:
        raise ValueError(
            f"unexpected treatment groups {sorted(unexpected)}; expected only "
            f"{TREATMENT_GROUP!r} and {CONTROL_GROUP!r}"
        )
    frame = frame.reset_index(drop=True)
    frame.insert(0, "row_id", [f"lenta-{index:07d}" for index in range(len(frame))])
    return frame


def feature_frame(frame: pd.DataFrame, *, max_categories: int = 40) -> pd.DataFrame:
    """X under the declared recipe, with the post-treatment gate applied.

    Columns are discovered rather than hard-coded, because the upstream frame
    carries nearly two hundred of them and a hand-written list would drift.
    What *is* hard-coded is the exclusion list, since that is the part where
    a mistake is silent and expensive.
    """

    excluded = {"row_id", TREATMENT_COLUMN, *POST_TREATMENT_COLUMNS}
    selected = [column for column in frame.columns if column not in excluded]
    assert_no_post_treatment_features(selected)

    features = frame.loc[:, selected].copy()
    # A high-cardinality string column would explode a one-hot encoder and is
    # almost certainly an identifier rather than a feature.
    for column in features.columns:
        if features[column].dtype == object and features[column].nunique() > max_categories:
            features = features.drop(columns=[column])
    return features


def make_split(frame: pd.DataFrame, *, salt: str = SPLIT_SALT) -> pd.Series:
    """Deterministic development/confirmation split, hashed per row id.

    Hashing rather than sampling means the split is reproducible from the raw
    file alone and is stable if rows are reordered.
    """

    def draw(row_id: str) -> float:
        digest = hashlib.sha256(f"{salt}:{row_id}".encode()).hexdigest()[:8]
        return int(digest, 16) / 0xFFFFFFFF

    values = frame["row_id"].map(draw)
    return pd.Series(
        np.where(values < DEVELOPMENT_FRACTION, "development", "confirmation"),
        index=frame.index,
        name="split",
    )


def file_digest(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(path: Path | str = DEFAULT_PATH) -> dict[str, Any]:
    """Everything a reader needs to check this study used the file it says.

    Outcome summaries are reported **development-side only**.  Reporting them
    over the whole file would read the confirmation outcomes, which is the
    one thing the split exists to prevent.
    """

    frame = load_lenta(path)
    split = make_split(frame)
    development = frame.loc[split.to_numpy() == "development"]
    arm = development[TREATMENT_COLUMN].astype(str)
    features = feature_frame(frame)

    by_arm = {
        str(name): {
            "n": len(group),
            "outcome_rate": float(group[OUTCOME_COLUMN].mean()),
        }
        for name, group in development.groupby(arm)
    }
    return {
        "dataset": "lenta",
        "source_url": SOURCE_URL,
        "path": str(path).replace("\\", "/"),
        "sha256": file_digest(path),
        "expected_sha256": EXPECTED_SHA256,
        "n_rows": len(frame),
        "n_columns": int(frame.shape[1]),
        "treatment_column": TREATMENT_COLUMN,
        "outcome_column": OUTCOME_COLUMN,
        "post_treatment_columns_excluded": list(POST_TREATMENT_COLUMNS),
        "n_features": int(features.shape[1]),
        "treated_share_whole_file": float(
            (frame[TREATMENT_COLUMN].astype(str) == TREATMENT_GROUP).mean()
        ),
        "split_salt": SPLIT_SALT,
        "development_fraction": DEVELOPMENT_FRACTION,
        "n_development": int((split == "development").sum()),
        "n_confirmation": int((split == "confirmation").sum()),
        "outcome_by_arm_development_only": by_arm,
        "confirmation_outcomes_read": False,
        "scope_note": (
            "An SMS campaign by a grocery retailer: a different channel, outcome "
            "and population from the e-mail study, which is what makes it a "
            "replication rather than another slice of the same experiment. The raw "
            "file is not redistributed; only this manifest and derived summaries are."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["manifest", "check"])
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--output", default="reports/v4/lenta_manifest.json")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print(f"{path} is missing; download it from {SOURCE_URL}")
        return 1

    manifest = build_manifest(path)
    if args.command == "check":
        if EXPECTED_SHA256 and manifest["sha256"] != EXPECTED_SHA256:
            print(
                f"digest mismatch: expected {EXPECTED_SHA256}, got {manifest['sha256']}. "
                "The upstream file has changed; results are not comparable."
            )
            return 1
        print(f"ok: {manifest['n_rows']:,} rows, sha256 {manifest['sha256']}")
        return 0

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"{manifest['n_rows']:,} rows, {manifest['n_features']} features, "
        f"treated share {manifest['treated_share_whole_file']:.4f}"
    )
    for name, entry in manifest["outcome_by_arm_development_only"].items():
        print(f"  {name:<10} n={entry['n']:,} outcome rate {entry['outcome_rate']:.4f}")
    print(f"Manifest: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
