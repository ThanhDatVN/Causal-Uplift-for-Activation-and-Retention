"""Acquisition, parsing, and validation for the Orange Belgium uplift dataset.

The raw file is deliberately not redistributed.  It is licensed CC BY-NC-ND and
is downloaded from OpenML dataset 45580 into the user's local workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import urllib.request
from pathlib import Path

import pandas as pd

OPENML_ID = 45580
OPENML_URL = "https://www.openml.org/data/v1/download/22116701/churn-uplift-mlg.arff"
EXPECTED_MD5 = "bd328613c1c4ef793ab04cd4dd1c6db0"
EXPECTED_ROWS = 11_896
EXPECTED_NUMERIC = tuple(f"PC{i}" for i in range(1, 161))
EXPECTED_CATEGORICAL = tuple(f"FACTOR{i}" for i in range(1, 19))
FEATURE_COLUMNS = EXPECTED_NUMERIC + EXPECTED_CATEGORICAL
TARGET_COLUMN = "y"
TREATMENT_COLUMN = "t"
DEFAULT_PATH = Path("data/raw/churn-uplift-mlg.arff")


def file_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_orange(path: Path = DEFAULT_PATH, *, force: bool = False) -> Path:
    """Download atomically and require the exact OpenML checksum."""
    path = Path(path)
    if path.exists() and not force:
        actual = file_md5(path)
        if actual != EXPECTED_MD5:
            raise ValueError(
                f"Existing Orange file has MD5 {actual}; expected {EXPECTED_MD5}. "
                "Delete it or rerun with --force."
            )
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".download")
    request = urllib.request.Request(
        OPENML_URL,
        headers={"User-Agent": "TelcoChurnDecisionSystem/0.2 (+OpenML-45580)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
            expected_bytes = response.headers.get("Content-Length")
            written = 0
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
                written += len(chunk)
        if expected_bytes is not None and written != int(expected_bytes):
            raise OSError(f"Incomplete download: {written} of {expected_bytes} bytes")
        actual = file_md5(partial)
        if actual != EXPECTED_MD5:
            raise ValueError(f"Downloaded Orange file has MD5 {actual}; expected {EXPECTED_MD5}")
        partial.replace(path)
    finally:
        if partial.exists():
            partial.unlink()
    return path


def _arff_header(path: Path) -> tuple[list[str], int]:
    names: list[str] = []
    data_start: int | None = None
    attribute_pattern = re.compile(r"^@attribute\s+(?:'([^']+)'|\"([^\"]+)\"|(\S+))", re.IGNORECASE)
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream):
            stripped = line.strip()
            match = attribute_pattern.match(stripped)
            if match:
                names.append(next(group for group in match.groups() if group is not None))
            if stripped.lower() == "@data":
                data_start = line_number + 1
                break
    if data_start is None:
        raise ValueError("ARFF file has no @DATA marker")
    return names, data_start


def validate_orange(frame: pd.DataFrame) -> None:
    expected = [*FEATURE_COLUMNS, TARGET_COLUMN, TREATMENT_COLUMN]
    errors: list[str] = []
    if list(frame.columns) != expected:
        errors.append("schema/order differs from the documented 160 PC + 18 factor + y + t")
    if len(frame) != EXPECTED_ROWS:
        errors.append(f"row count is {len(frame):,}, expected {EXPECTED_ROWS:,}")
    if frame.isna().any().any():
        errors.append(f"found {int(frame.isna().sum().sum())} missing values")
    for column in (TARGET_COLUMN, TREATMENT_COLUMN):
        values = set(frame[column].unique())
        if not values.issubset({0, 1}) or len(values) != 2:
            errors.append(f"{column} must contain both 0 and 1; got {sorted(values)}")
    if errors:
        raise ValueError("Orange uplift validation failed: " + "; ".join(errors))


def load_orange(path: Path = DEFAULT_PATH, *, verify_checksum: bool = True) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run: python -m telco_churn.orange_data fetch")
    if verify_checksum and file_md5(path) != EXPECTED_MD5:
        raise ValueError("Orange raw file checksum mismatch")
    names, data_start = _arff_header(path)
    frame = pd.read_csv(path, skiprows=data_start, header=None, names=names, low_memory=False)
    for column in EXPECTED_NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    for column in EXPECTED_CATEGORICAL:
        frame[column] = frame[column].astype("string")
    frame[TARGET_COLUMN] = pd.to_numeric(frame[TARGET_COLUMN], errors="raise").astype("int8")
    frame[TREATMENT_COLUMN] = pd.to_numeric(frame[TREATMENT_COLUMN], errors="raise").astype("int8")
    frame.index = pd.Index([f"orange-{i:05d}" for i in range(len(frame))], name="row_id")
    validate_orange(frame)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "validate"), nargs="?", default="validate")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = fetch_orange(args.path, force=args.force) if args.action == "fetch" else args.path
    frame = load_orange(path)
    rates = frame.groupby(TREATMENT_COLUMN)[TARGET_COLUMN].agg(["count", "mean"])
    print(f"Validated OpenML {OPENML_ID}: {len(frame):,} rows, MD5 {file_md5(path)}")
    print(rates.to_string())


if __name__ == "__main__":
    main()
