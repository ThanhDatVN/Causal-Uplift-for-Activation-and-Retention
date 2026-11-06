"""Fail-closed check for returned Kaggle/local nested-learner artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = "709cdc7cb859756e28c34942b41d0d12e7ece6315742f1b3779c650a66b0bcdd"
RAW_SHA256 = {
    "hillstrom": "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece",
    "lenta": "b531544f6c072d22f232d91e20ffcaca265acf224e02687502a40e6d56135682",
}
EXPECTED_DEVELOPMENT = {"lenta_sms": 549867, "hillstrom_mens": 34092, "hillstrom_womens": 34174}
EXPECTED_DEVELOPMENT_ID_SHA256 = {
    "hillstrom_mens": "0b54cb3d75f0b3112b4b542237af52bb98a9f2b74a8400a49e972fb259d1924b",
    "hillstrom_womens": "66df9b97a23e67e8e2d3e8d3b61aeaf7753fcfdaddd46ad2cae244439b6b859a",
    "lenta_sms_60000": "e5b942a157b081bc3c56de7b06bacba2ebef31264572291f2a39306ded23dd03",
    "lenta_sms_full": "f5d392917ee0aa133c9449b20599a688377efb30a93b38867fc507f0f4e3c9bc",
}
STUDIES = {
    "local-reproduction": ("hillstrom_mens", "hillstrom_womens", "lenta_sms"),
    "full-lenta": ("lenta_sms",),
}
EXPECTED_PACKAGES = {
    "numpy": "2.4.6",
    "pandas": "2.3.3",
    "scipy": "1.17.1",
    "scikit-learn": "1.7.2",
    "catboost": "1.2.10",
    "telcochurn-decision-system": "0.1.0",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--study", choices=tuple(STUDIES), required=True)
    args = parser.parse_args()
    manifest = json.loads((args.directory / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    require(manifest["protocol"] == "R4_nested_learner_portable_v1", "wrong protocol")
    require(manifest["status"] == "COMPLETE", "run did not complete")
    require(manifest["study"] == args.study and manifest["command"] == "run", "wrong study or command")
    require(manifest["confirmation_labels_accessed"] is False, "confirmation-label boundary failed")
    require(manifest["learner_source_sha256"] == SOURCE_SHA256, "wrong learner source")
    require(manifest["runner_sha256"] == sha(Path(__file__).with_name("run_learner.py")), "wrong runner")
    require(manifest["input_sha256"]["lenta"] == RAW_SHA256["lenta"], "wrong Lenta input")
    for name, expected in EXPECTED_PACKAGES.items():
        require(manifest["environment"]["packages"].get(name) == expected, f"wrong {name} version")
    if args.study == "local-reproduction":
        require(manifest["input_sha256"]["hillstrom"] == RAW_SHA256["hillstrom"], "wrong Hillstrom input")
    require(set(manifest["domains"]) == set(STUDIES[args.study]), "missing or extra domains")
    for domain, record in manifest["domains"].items():
        expected_n = 60000 if args.study == "local-reproduction" and domain == "lenta_sms" else EXPECTED_DEVELOPMENT[domain]
        require(record["n_development"] == expected_n, f"{domain}: wrong development count")
        split_key = f"lenta_sms_{'60000' if args.study == 'local-reproduction' else 'full'}" if domain == "lenta_sms" else domain
        require(record["development_id_sha256"] == EXPECTED_DEVELOPMENT_ID_SHA256[split_key], f"{domain}: wrong development IDs")
        require(record["roles"]["confirmation"] > 0, f"{domain}: missing confirmation role")
        if domain == "lenta_sms":
            require(record["evidence_role"] == "exploratory_assumed_propensity", "Lenta evidence role changed")
        path = args.directory / record["result_path"]
        require(path.name == record["result_path"] and sha(path) == record["result_sha256"], f"{domain}: result hash mismatch")
        result = json.loads(path.read_text(encoding="utf-8"))
        require(result["status"] == record["result_status"] == "COMPLETE_DEVELOPMENT", f"{domain}: incomplete result")
        require(result["development_id_sha256"] == record["development_id_sha256"], f"{domain}: split ID mismatch")
        require(len(result["folds"]) == 3 and not result["failures"], f"{domain}: failed or missing fold")
        require(all(all(value["status"] == "COMPLETE" for value in fold["outer_values"].values()) for fold in result["folds"]), f"{domain}: candidate failed")
    print(f"VERIFIED {args.study}: {', '.join(manifest['domains'])}")


if __name__ == "__main__":
    main()
