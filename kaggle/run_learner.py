"""Frozen CPU runner for the nested learner reproduction and Lenta extension.

The original study code is imported from the packaged wheel. This wrapper
records the completed command, environment, input hashes, runtime, and result
hashes after fitting. It never selects or scores a confirmation row.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from telco_churn import learner_comparison as study

PROTOCOL = "R4_nested_learner_portable_v1"
SOURCE_SHA256 = "709cdc7cb859756e28c34942b41d0d12e7ece6315742f1b3779c650a66b0bcdd"
RAW_SHA256 = {
    "hillstrom": "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece",
    "lenta": "b531544f6c072d22f232d91e20ffcaca265acf224e02687502a40e6d56135682",
}
EXPECTED_DEVELOPMENT = {"lenta_sms": 549867, "hillstrom_mens": 34092, "hillstrom_womens": 34174}
STUDIES = {
    "local-reproduction": ("hillstrom_mens", "hillstrom_womens", "lenta_sms"),
    "full-lenta": ("lenta_sms",),
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _environment() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scipy", "scikit-learn", "catboost", "telcochurn-decision-system")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run"))
    parser.add_argument("--study", choices=tuple(STUDIES), required=True)
    parser.add_argument("--input-root", type=Path, required=True,
                        help="Directory containing data/raw/lenta.csv.gz and, for local reproduction, hillstrom.csv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.input_root.resolve():
        parser.error("output must differ from input root")
    if _sha(Path(study.__file__)) != SOURCE_SHA256:
        raise RuntimeError("installed learner source does not match the frozen wheel")
    study.LENTA_ROWS = 60000 if args.study == "local-reproduction" else EXPECTED_DEVELOPMENT["lenta_sms"]
    expected_paths = {"lenta": args.input_root / study.LENTA_PATH}
    if args.study == "local-reproduction":
        expected_paths["hillstrom"] = args.input_root / study.HILLSTROM_PATH
    for name, path in expected_paths.items():
        if not path.is_file() or _sha(path) != RAW_SHA256[name]:
            raise RuntimeError(f"missing or changed {name} input: {path}")
    if args.command == "run" and args.output.exists() and any(args.output.iterdir()):
        parser.error("run output directory must be empty; preserve prior results")

    started = time.perf_counter()
    manifest = {
        "protocol": PROTOCOL,
        "study": args.study,
        "command": args.command,
        "started_utc": datetime.now(UTC).isoformat(),
        "runner_sha256": _sha(Path(__file__)),
        "learner_source_sha256": SOURCE_SHA256,
        "input_sha256": {name: RAW_SHA256[name] for name in expected_paths},
        "environment": _environment(),
        "parameters": {
            "seed": study.SEED,
            "outer_folds": study.FOLDS,
            "inner_folds": study.FOLDS,
            "capacity_fraction": study.CAP,
            "candidates": list(study.CANDIDATES),
            "selectable": list(study.SELECTABLE),
            "lenta_rows": study.LENTA_ROWS,
            "lenta_sample_seed": study.LENTA_SAMPLE_SEED,
            "margin_per_1000": study.MARGIN_PER_1000,
        },
        "confirmation_labels_accessed": False,
        "limitation": "Raw CSV parsing includes all roles; only development labels are indexed. Lenta e=0.75 is an assumption, not a logged randomization probability.",
        "domains": {},
        "status": "RUNNING" if args.command == "run" else "PREFLIGHT",
    }
    _save(args.output / "RUN_MANIFEST.json", manifest)
    try:
        for domain in STUDIES[args.study]:
            data = study.load_domain(args.input_root, domain, outcomes=args.command == "run")
            expected_n = 60000 if args.study == "local-reproduction" and domain == "lenta_sms" else EXPECTED_DEVELOPMENT[domain]
            if len(data["features"]) != expected_n:
                raise RuntimeError(f"{domain}: expected {expected_n} development rows, got {len(data['features'])}")
            row = {
                "evidence_role": "exploratory_assumed_propensity" if domain == "lenta_sms" else "inspected_development",
                "n_development": len(data["features"]),
                "roles": data["roles"],
                "development_id_sha256": data["split_id_sha256"],
                "features": list(data["features"].columns),
                "propensity_note": data["propensity_note"],
            }
            if args.command == "run":
                outcome = study._one_domain(domain, data)
                result_path = args.output / f"{domain}.json"
                _save(result_path, outcome)
                row.update({"result_path": result_path.name, "result_sha256": _sha(result_path), "result_status": outcome["status"]})
            manifest["domains"][domain] = row
            _save(args.output / "RUN_MANIFEST.json", manifest)
        manifest["status"] = "COMPLETE" if args.command == "run" else "PREFLIGHT_COMPLETE"
    except Exception as exc:
        manifest["status"] = "FAILED"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - started
        _save(args.output / "RUN_MANIFEST.json", manifest)
    print(args.output / "RUN_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
