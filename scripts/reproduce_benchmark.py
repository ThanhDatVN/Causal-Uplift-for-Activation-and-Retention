"""Rebuild the IBM benchmark and write a provenance manifest for this exact run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from telco_churn.data import DATA_SHA256, fetch_dataset
from telco_churn.environment import verify_lock
from telco_churn.train import run_training

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = ("src", "scripts", "pyproject.toml", "requirements-api.txt", ".github/workflows")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_fingerprint(root: Path = ROOT) -> str:
    """Hash code and build configuration in stable path order, excluding generated files."""

    files: list[Path] = []
    for name in SOURCE_PATHS:
        target = root / name
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(
                path for path in target.rglob("*") if path.is_file() and path.suffix != ".pyc"
            )
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda value: value.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or any(
            part.endswith((".egg-info", ".dist-info")) for part in path.parts
        ):
            continue
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def git_revision(root: Path = ROOT) -> str | None:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return process.stdout.strip() if process.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/raw/Telco-Customer-Churn.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/v4/reproduced_quick")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "artifacts/reproduced_quick")
    parser.add_argument("--fetch", action="store_true", help="Download IBM data if absent")
    parser.add_argument(
        "--full", action="store_true", help="Run the full benchmark instead of smoke"
    )
    args = parser.parse_args()
    args.data = args.data.resolve()
    args.output = args.output.resolve()
    args.model_dir = args.model_dir.resolve()
    os.chdir(ROOT)

    if not args.data.exists():
        if not args.fetch:
            parser.error("Dataset is missing; pass --fetch to download and checksum-verify it")
        fetch_dataset(args.data)
    observed_data_hash = sha256_file(args.data)
    if observed_data_hash != DATA_SHA256:
        raise ValueError("Dataset checksum differs from the reviewed IBM file")

    source_before = source_fingerprint()
    started_at = datetime.now(UTC).isoformat()
    metadata = run_training(args.data, args.output, args.model_dir, quick=not args.full)
    source_after = source_fingerprint()
    if source_before != source_after:
        raise RuntimeError(
            "Source files changed during training; this run has no stable producer digest"
        )

    split_path = ROOT / "data/splits/split_manifest.csv"
    model_path = args.model_dir / "champion.joblib"
    report_path = args.output / "BENCHMARK_REPORT.md"
    if metadata["dataset_sha256"] != observed_data_hash:
        raise RuntimeError("Model metadata does not match the input dataset")
    if metadata["split_manifest_sha256"] != sha256_file(split_path):
        raise RuntimeError("Model metadata does not match the frozen split manifest")
    lock_path = ROOT / "locks/research.lock.txt"
    lock_report = verify_lock(lock_path)
    manifest = {
        "schema_version": 1,
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "run_role": "predictive_frozen_test_full" if args.full else "predictive_frozen_test_smoke",
        "run_argv": ["python", "scripts/reproduce_benchmark.py", *sys.argv[1:]],
        "run_command": shlex.join(["python", "scripts/reproduce_benchmark.py", *sys.argv[1:]]),
        "git_revision": git_revision(),
        "producer_source_sha256": source_before,
        "source_hash_scope": list(SOURCE_PATHS),
        "dataset": {"path": str(args.data), "sha256": observed_data_hash},
        "split": {"path": str(split_path), "sha256": sha256_file(split_path)},
        "model": {"path": str(model_path), "sha256": sha256_file(model_path)},
        "report": {"path": str(report_path), "sha256": sha256_file(report_path)},
        "benchmark_protocol": metadata["benchmark_protocol"],
        "champion_model": metadata["champion_model"],
        "test_metrics": metadata["test_metrics"],
        "research_lock": {
            "path": str(lock_path),
            "sha256": sha256_file(lock_path),
            "satisfied": lock_report.satisfied,
            "missing": lock_report.missing,
            "changed": lock_report.changed,
            "extra_count": len(lock_report.extra),
        },
        "caution": (
            "Full protocol reproduces predictive metrics only; IBM has no treatment "
            "outcomes or validated 30-day horizon."
            if args.full
            else "Quick mode is a smoke reproduction; IBM has no treatment outcomes "
            "or validated 30-day horizon."
        ),
    }
    manifest_path = args.output / "RUN_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=float) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "model_sha256": manifest["model"]["sha256"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
