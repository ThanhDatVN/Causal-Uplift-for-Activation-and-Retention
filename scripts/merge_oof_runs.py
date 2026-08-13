"""Merge process-isolated OOF candidate runs after exact contract checks.

This utility exists for full-development runs that cannot keep multiple fitted
LightGBM candidates in one process without crossing the resource guard. It does
not recompute, transform, or select scores.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.compare_improvement_candidates import (
    RESERVED_KEYS,
    assert_comparable_runs,
)


def merge_candidate_config_hashes(manifests: list[dict]) -> dict[str, str]:
    """Union component config hashes while rejecting ambiguous name collisions."""
    merged: dict[str, str] = {}
    for manifest_index, manifest in enumerate(manifests):
        hashes = manifest.get("candidate_config_hashes")
        if not isinstance(hashes, dict):
            raise ValueError(
                f"Component manifest {manifest_index} thieu candidate_config_hashes"
            )
        for candidate, config_hash in hashes.items():
            if candidate in merged and merged[candidate] != config_hash:
                raise ValueError(
                    "Candidate config hash collision khi merge: "
                    f"{candidate!r}={merged[candidate]!r}/{config_hash!r}"
                )
            merged[candidate] = config_hash
    return merged


def legacy_candidate_config_hashes(run_dir: Path) -> dict[str, str]:
    """Recover diagnostic-only config hashes from a legacy metrics artifact."""
    metrics = pd.read_csv(run_dir / "oof_metrics.csv")
    required = {"candidate", "config_hash"}
    if not required.issubset(metrics.columns):
        raise ValueError(
            f"Legacy run {run_dir} thieu candidate/config_hash trong oof_metrics.csv"
        )
    pairs = metrics.loc[:, ["candidate", "config_hash"]].dropna().drop_duplicates()
    if pairs["candidate"].duplicated().any():
        raise ValueError(f"Legacy run {run_dir} co config hash mau thuan")
    return dict(zip(pairs["candidate"], pairs["config_hash"], strict=True))


def merge_oof_payloads(payloads: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    """Merge disjoint candidate scores while requiring identical evaluation arrays."""
    if len(payloads) < 2:
        raise ValueError("Can it nhat hai OOF payload de merge")
    reference = payloads[0]
    required = set(RESERVED_KEYS)
    missing = sorted(required - set(reference))
    if missing:
        raise ValueError(f"OOF payload dau tien thieu core arrays: {missing}")
    merged = {name: np.asarray(reference[name]) for name in required}
    score_names: set[str] = set()
    for payload_index, payload in enumerate(payloads):
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(
                f"OOF payload {payload_index} thieu core arrays: {missing}"
            )
        for name in required:
            if not np.array_equal(reference[name], payload[name]):
                raise ValueError(
                    f"OOF payload {payload_index} khac core array {name!r}"
                )
        for name, values in payload.items():
            if name in required:
                continue
            if name in score_names:
                raise ValueError(f"Candidate score bi trung khi merge: {name!r}")
            score_names.add(name)
            merged[name] = np.asarray(values)
    if not score_names:
        raise ValueError("Khong co candidate score nao de merge")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--allow-legacy-manifests",
        action="store_true",
        help=(
            "Chi cho phep tai lap artifact lich su; output la diagnostic va "
            "khong du dieu kien advancement."
        ),
    )
    args = parser.parse_args()
    if len(args.run_dir) < 2:
        parser.error("--run-dir phai duoc lap lai it nhat hai lan")

    manifests = [
        json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        for run_dir in args.run_dir
    ]
    if args.allow_legacy_manifests:
        for run_dir, manifest in zip(args.run_dir, manifests, strict=True):
            if manifest.get("manifest_schema_version") is None:
                manifest["candidate_config_hashes"] = legacy_candidate_config_hashes(
                    run_dir
                )
    payloads = []
    for run_dir in args.run_dir:
        with np.load(run_dir / "oof_scores.npz") as payload:
            payloads.append({name: payload[name] for name in payload.files})

    reference_manifest = manifests[0]
    for manifest, payload in zip(manifests[1:], payloads[1:], strict=True):
        assert_comparable_runs(
            reference_manifest,
            manifest,
            payloads[0],
            payload,
            allow_legacy_manifests=args.allow_legacy_manifests,
        )
        for field in ("fold_seed", "n_folds", "stage"):
            if manifest.get(field) != reference_manifest.get(field):
                raise ValueError(f"Component runs khac {field!r}")

    merged = merge_oof_payloads(payloads)
    merged_config_hashes = merge_candidate_config_hashes(manifests)
    completed = sorted(set(merged) - RESERVED_KEYS)
    metrics = pd.concat(
        [pd.read_csv(run_dir / "oof_metrics.csv") for run_dir in args.run_dir],
        ignore_index=True,
    )
    metrics = metrics.loc[metrics["candidate"].isin(completed)].copy()

    manifest = dict(reference_manifest)
    manifest.update(
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "component_run_dirs": [str(path) for path in args.run_dir],
            "candidates_completed": completed,
            "candidate_config_hashes": merged_config_hashes,
            "elapsed_seconds": float(
                sum(item.get("elapsed_seconds", 0.0) for item in manifests)
            ),
            "peak_process_rss_gb": float(
                max(item.get("peak_process_rss_gb", 0.0) for item in manifests)
            ),
            "min_system_available_ram_gb": float(
                min(
                    item.get("min_system_available_ram_gb", float("inf"))
                    for item in manifests
                )
            ),
            "max_system_memory_percent": float(
                max(item.get("max_system_memory_percent", 0.0) for item in manifests)
            ),
            "resource_gate_passed": all(
                item.get("resource_gate_passed", False) for item in manifests
            ),
            "scope_note": (
                "Process-isolated deterministic OOF runs merged after exact "
                "manifest, source-index, nuisance-signal and outcome checks."
            ),
            "evidence_eligibility": (
                "legacy_diagnostic_not_eligible_for_advancement"
                if args.allow_legacy_manifests
                else "strict_manifest_evidence"
            ),
        }
    )
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(
            f"Output directory khong rong o {args.output_dir}; dung namespace moi"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_dir / "oof_scores.npz", **merged)
    metrics.to_csv(args.output_dir / "oof_metrics.csv", index=False)
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {args.output_dir} candidates={completed}")


if __name__ == "__main__":
    main()
