"""Rebuild Hillstrom development screening and record its producer and input hashes."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from reproduce_benchmark import ROOT, git_revision, sha256_file, source_fingerprint

from telco_churn.environment import verify_lock
from telco_churn.hillstrom_data import (
    DEFAULT_PATH,
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    SPLIT_SALT,
    make_split,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/v4/screening_reproduction")
    args = parser.parse_args()
    output = args.output.resolve()
    raw = ROOT / DEFAULT_PATH
    split = ROOT / "data/splits/hillstrom_split.csv"
    if not raw.exists() or not split.exists():
        parser.error(
            "Hillstrom data or split is missing; run python -m telco_churn.hillstrom_data fetch"
        )
    raw_hash = sha256_file(raw)
    if raw_hash != EXPECTED_SHA256:
        raise ValueError("Hillstrom data checksum differs from the pinned source")
    stored_split = pd.read_csv(split)
    expected_ids = list(range(EXPECTED_ROWS))
    expected_split = make_split(pd.DataFrame({"row_id": expected_ids})).tolist()
    if (
        stored_split["row_id"].tolist() != expected_ids
        or stored_split["split"].tolist() != expected_split
    ):
        raise ValueError("Hillstrom split manifest differs from the declared hash rule")

    source_before = source_fingerprint()
    started_at = datetime.now(UTC).isoformat()
    command = [
        sys.executable,
        "-m",
        "telco_churn.screening",
        "--output-dir",
        str(output),
    ]
    process = subprocess.run(command, cwd=ROOT, check=False)
    if process.returncode != 0:
        raise RuntimeError("Development screening refused or failed; see its gate output")
    if source_before != source_fingerprint():
        raise RuntimeError("Source files changed during screening")

    screening_path = output / "screening.json"
    report_path = output / "SCREENING_REPORT.md"
    screening = json.loads(screening_path.read_text(encoding="utf-8"))
    if screening["protocol"]["split"] != "development only; the confirmation split is not opened":
        raise RuntimeError("Screening result has the wrong split role")
    lock_path = ROOT / "locks/research.lock.txt"
    lock = verify_lock(lock_path)
    manifest = {
        "schema_version": 1,
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "run_role": "causal_development_screening_only",
        "run_argv": ["python", "scripts/reproduce_screening.py", *sys.argv[1:]],
        "run_command": shlex.join(["python", "scripts/reproduce_screening.py", *sys.argv[1:]]),
        "split_salt": SPLIT_SALT,
        "seed": 20260921,
        "treatment_arm": "Mens E-Mail",
        "git_revision": git_revision(),
        "producer_source_sha256": source_before,
        "dataset": {"path": str(raw), "sha256": raw_hash},
        "split": {"path": str(split), "sha256": sha256_file(split)},
        "screening": {"path": str(screening_path), "sha256": sha256_file(screening_path)},
        "report": {"path": str(report_path), "sha256": sha256_file(report_path)},
        "protocol": screening["protocol"],
        "gate": screening["gate"],
        "cohort": screening["cohort"],
        "n_completed": screening["n_completed"],
        "n_failed": screening["n_failed"],
        "shortlist": screening["shortlist"],
        "research_lock": {
            "path": str(lock_path),
            "sha256": sha256_file(lock_path),
            "satisfied": lock.satisfied,
            "missing": lock.missing,
            "changed": lock.changed,
            "extra_count": len(lock.extra),
        },
        "caution": "Development fold variation is not a population confidence interval or confirmation result.",
    }
    manifest_path = output / "RUN_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "shortlist": manifest["shortlist"]}))
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
