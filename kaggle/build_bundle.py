"""Build a private-upload Kaggle input from checksum-pinned local artifacts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / "kaggle"
DEST = ROOT / "dist" / "kaggle_nested_learner_cpu_20261002.zip"
WHEEL = ROOT / "dist" / "portfolio_20260930" / "telcochurn_decision_system-0.1.0-py3-none-any.whl"
FILES = {
    "data/raw/lenta.csv.gz": (ROOT / "data/raw/lenta.csv.gz", "b531544f6c072d22f232d91e20ffcaca265acf224e02687502a40e6d56135682"),
    "data/raw/hillstrom.csv": (ROOT / "data/raw/hillstrom.csv", "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"),
    WHEEL.name: (WHEEL, "9d9f0476cb619f40b5cb64915cc7ce71dae2cc699555d384c74d724086a3362e"),
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    for name, (path, expected) in FILES.items():
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"missing or changed input: {name} ({path})")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DEST, "w") as bundle:
        for name, (path, _) in FILES.items():
            bundle.write(path, name, compress_type=zipfile.ZIP_STORED if name.endswith(".gz") else zipfile.ZIP_DEFLATED)
        for path in (KAGGLE / "run_learner.py", KAGGLE / "verify_return.py", KAGGLE / "requirements.txt", KAGGLE / "README.md", KAGGLE / "full_lenta_cpu.ipynb"):
            bundle.write(path, path.name, compress_type=zipfile.ZIP_DEFLATED)
        bundle.writestr("INPUT_MANIFEST.json", json.dumps({name: expected for name, (_, expected) in FILES.items()}, indent=2) + "\n")
    with zipfile.ZipFile(DEST) as bundle:
        bad = bundle.testzip()
        if bad:
            raise RuntimeError(f"corrupt bundle member: {bad}")
    print(json.dumps({"path": str(DEST), "bytes": DEST.stat().st_size, "sha256": sha(DEST)}, indent=2))


if __name__ == "__main__":
    main()
