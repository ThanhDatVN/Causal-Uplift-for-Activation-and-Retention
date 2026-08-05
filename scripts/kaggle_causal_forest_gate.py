"""Resource and artifact gate for one Kaggle Causal Forest preflight stage.

Run stages separately in the same Kaggle session:

    python scripts/kaggle_causal_forest_gate.py --data-path ... --frac 0.20
    python scripts/kaggle_causal_forest_gate.py --data-path ... --frac 0.30
    python scripts/kaggle_causal_forest_gate.py --data-path ... --frac 0.50

The script refuses 30%/50% unless required prior manifests exist and passed.
It measures the full process tree RSS, verifies the Criteo checksum, and checks
the saved score alignment/finite contract. It does not claim model quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil


# Criteo v2.1 có hai dạng byte hợp lệ. Kaggle **giải nén** file `.csv.gz` khi upload
# trực tiếp, nên file mount vào `/kaggle/input` là CSV thô 3.248.115.221 byte chứ không
# phải bản nén 311.422.618 byte. Nội dung hai bản giống nhau bit-for-bit; chỉ container
# khác, nên chấp nhận cả hai checksum vẫn giữ nguyên đảm bảo "đúng v2.1, không bị cắt".
EXPECTED_SHA256 = {
    "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc": "csv.gz",
    "e4d7c710ca1f38e523309d0f8a0745d1b53e7392d51f20d1088b6cfeaef222ef": "csv",
}
STAGES = {
    0.001: None,  # local code-path smoke test only
    0.20: None,
    0.30: 0.20,
    0.50: 0.30,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(frac: float) -> str:
    return str(frac).replace(".", "p")


def _tree_rss(process: psutil.Process) -> int:
    total = 0
    try:
        total += process.memory_info().rss
        children = process.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0
    for child in children:
        try:
            total += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total


def _prior_manifest(root: Path, fraction: float) -> Path:
    return root / f"preflight_{_slug(fraction)}" / "gate_manifest.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, required=True)
    parser.add_argument("--frac", type=float, choices=sorted(STAGES), required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/kaggle/working/output/causal_forest"),
    )
    parser.add_argument("--max-ram-fraction", type=float, default=0.75)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--skip-prior-gate",
        action="store_true",
        help="Chỉ dùng cho local smoke test; không dùng cho Kaggle release run.",
    )
    args = parser.parse_args()
    if not 0 < args.max_ram_fraction < 1:
        raise ValueError("--max-ram-fraction phải nằm trong (0, 1)")

    expected_previous = STAGES[args.frac]
    if expected_previous is not None and not args.skip_prior_gate:
        prior_path = _prior_manifest(args.output_root, expected_previous)
        if not prior_path.exists():
            raise FileNotFoundError(
                f"Thiếu gate trước đó: {prior_path}. Không được nhảy thẳng "
                f"từ đầu lên {args.frac:.0%}."
            )
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if prior.get("status") != "passed":
            raise RuntimeError(f"Prior gate không pass: {prior_path}")

    actual_hash = _sha256(args.data_path)
    if actual_hash not in EXPECTED_SHA256:
        raise ValueError(
            f"Checksum Criteo không khớp: {actual_hash}; chấp nhận một trong "
            + ", ".join(f"{h} ({kind})" for h, kind in EXPECTED_SHA256.items())
        )
    data_form = EXPECTED_SHA256[actual_hash]
    print(f"[data] {args.data_path} dạng {data_form}, checksum khớp", flush=True)

    stage_dir = args.output_root / f"preflight_{_slug(args.frac)}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    log_path = stage_dir / "train.log"
    # Đường dẫn tuyệt đối suy ra từ vị trí của chính file này. Dùng đường dẫn
    # tương đối sẽ hỏng ngay khi gate được gọi từ thư mục khác repo root, đúng
    # trường hợp mặc định trên Kaggle (`cwd = /kaggle/working`).
    trainer = Path(__file__).resolve().parent / "train_causal_forest.py"
    if not trainer.exists():
        raise FileNotFoundError(f"Không tìm thấy trainer: {trainer}")
    command = [
        sys.executable,
        str(trainer),
        "--data-path",
        str(args.data_path),
        "--frac",
        str(args.frac),
        "--profile",
        "kaggle-safe",
        "--output-dir",
        str(stage_dir),
        "--seed",
        str(args.seed),
    ]
    system = psutil.virtual_memory()
    started = time.time()
    peak_rss = 0
    minimum_available = system.available
    with log_path.open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        process = psutil.Process(child.pid)
        while child.poll() is None:
            peak_rss = max(peak_rss, _tree_rss(process))
            minimum_available = min(
                minimum_available,
                psutil.virtual_memory().available,
            )
            time.sleep(args.poll_seconds)
        exit_code = child.wait()
    elapsed = time.time() - started

    score_path = stage_dir / "cate_causal_forest_kaggle_safe.npy"
    holdout_path = stage_dir / "holdout_test_yt.npz"
    finite = False
    aligned = False
    score_rows = 0
    if exit_code == 0 and score_path.exists() and holdout_path.exists():
        score = np.load(score_path)
        holdout = np.load(holdout_path)
        score_rows = len(score)
        finite = bool(np.isfinite(score).all())
        aligned = bool(
            len(score) == len(holdout["Y"]) == len(holdout["T"])
            and int(holdout["n_test"]) == len(score)
        )

    peak_fraction = peak_rss / system.total
    passed = bool(
        exit_code == 0
        and finite
        and aligned
        and peak_fraction < args.max_ram_fraction
    )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "scope": "resource_and_artifact_integrity_gate_only",
        "fraction": args.frac,
        "profile": "kaggle-safe",
        "command": command,
        "data": {
            "path": str(args.data_path),
            "sha256": actual_hash,
            # "csv.gz" hoặc "csv": Kaggle giải nén khi upload trực tiếp. Hai dạng có
            # nội dung giống nhau; ghi lại để audit biết bản nào đã được dùng.
            "form": data_form,
        },
        "runtime": {
            "logical_cpus": psutil.cpu_count(),
            "physical_cpus": psutil.cpu_count(logical=False),
            "system_ram_total_gb": system.total / 2**30,
            "system_ram_available_start_gb": system.available / 2**30,
            "peak_process_tree_rss_gb": peak_rss / 2**30,
            "peak_process_tree_ram_fraction": peak_fraction,
            "minimum_system_available_gb": minimum_available / 2**30,
            "wall_seconds": elapsed,
            "exit_code": exit_code,
        },
        "artifact_contract": {
            "score_path": str(score_path),
            "holdout_path": str(holdout_path),
            "score_rows": score_rows,
            "all_finite": finite,
            "aligned": aligned,
        },
        "stop_rule": {
            "max_ram_fraction": args.max_ram_fraction,
            "may_continue": passed and args.frac < 0.50,
            "quality_not_assessed": True,
        },
        "limitations": [
            "Passing this gate does not show that Causal Forest improves Qini.",
            "GPU selection does not accelerate EconML CausalForestDML itself.",
            "Kaggle resources and quota must be read live; they are not guaranteed.",
        ],
    }
    manifest_path = stage_dir / "gate_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    print(f"[write] {manifest_path}")
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
