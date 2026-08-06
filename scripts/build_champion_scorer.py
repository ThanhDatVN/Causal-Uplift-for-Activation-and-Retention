"""Fit và lưu champion scorer để web app chấm điểm batch.

Scorer được fit trên **development pool** (Sprint 2 ``fit + validation``), đúng
tập đã dùng để tạo mọi số liệu OOF của Sprint 3. Không fit thêm trên
confirmation: nếu làm vậy, các metric đã báo cáo sẽ không còn tương ứng với model
đang phục vụ.

Metadata kèm theo gồm lưới phân vị của score trên confirmation, để web app quy
một dòng tải lên về phân vị của population thay vì chỉ so trong lô tải lên.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.candidates import candidate_from_dict
from src.experiment import build_sprint3_splits, config_hash, environment_versions
from src.paths import OUTPUT_DIR, REPO_ROOT
from src.scoring import fit_persisted_scorer

PROTOCOL_PATH = REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"
SPRINT3_MANIFEST = OUTPUT_DIR / "sprint3" / "protocol_manifest.json"
WEBAPP_DIR = OUTPUT_DIR / "product" / "webapp"


def resolve_champion(explicit: str | None) -> str:
    if explicit:
        return explicit
    if SPRINT3_MANIFEST.exists():
        manifest = json.loads(SPRINT3_MANIFEST.read_text(encoding="utf-8"))
        champion = manifest.get("final_champion")
        if champion:
            return champion
    return "Response"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-percentiles", type=int, default=1001)
    parser.add_argument("--output-dir", type=Path, default=WEBAPP_DIR)
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    specs = {item["name"]: candidate_from_dict(item) for item in protocol["candidates"]}
    champion = resolve_champion(args.champion)
    if champion not in specs:
        raise ValueError(
            f"Champion {champion!r} không có trong protocol; có {sorted(specs)}. "
            "Ensemble chưa được hỗ trợ làm persisted scorer vì cần lưu nhiều model."
        )
    spec = specs[champion]
    print(f"[champion] {champion} (family={spec.family})", flush=True)

    splits = build_sprint3_splits()
    development = splits["development"]
    confirmation = splits["confirmation"]
    propensity = float(development.treatment.mean())
    print(
        f"[data] development={len(development):,} confirmation={len(confirmation):,}",
        flush=True,
    )

    started = time.perf_counter()
    scorer = fit_persisted_scorer(
        spec,
        development.X,
        development.treatment,
        development.outcome,
        propensity=propensity,
        seed=args.seed,
        metadata={
            "fitted_on": "sprint2 development pool (fit + validation)",
            "development_index_sha256": development.index_sha256,
            "config_hash": config_hash(spec.as_config()),
            "protocol_id": protocol["protocol_id"],
            "environment": environment_versions(),
        },
    )
    fit_seconds = time.perf_counter() - started
    print(f"[fit] {fit_seconds:.1f}s", flush=True)

    reference = scorer.score(confirmation.X)
    quantiles = np.linspace(0.0, 1.0, args.n_percentiles)
    values = np.quantile(reference, quantiles)
    # ``np.interp`` cần trục x tăng nghiêm ngặt; score rời rạc sinh ra vùng phẳng.
    unique_values, first_index = np.unique(values, return_index=True)
    scorer.metadata["score_percentiles"] = {
        "values": unique_values.tolist(),
        "quantiles": quantiles[first_index].tolist(),
        "reference_split": "sprint2 confirmation",
        "reference_rows": int(len(reference)),
    }
    scorer.metadata["score_summary"] = {
        "mean": float(np.mean(reference)),
        "std": float(np.std(reference)),
        "min": float(np.min(reference)),
        "max": float(np.max(reference)),
        "unique_count": int(np.unique(reference).size),
    }
    scorer.metadata["fit_seconds"] = fit_seconds

    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = scorer.save(args.output_dir / "champion_scorer.joblib")
    metadata = {
        "champion": champion,
        "family": spec.family,
        "params": spec.params,
        "is_cate_scale": spec.is_cate_scale,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": path.name,
        "artifact_bytes": path.stat().st_size,
        **{
            key: value
            for key, value in scorer.metadata.items()
            if key != "score_percentiles"
        },
        "score_percentile_points": len(
            scorer.metadata["score_percentiles"]["values"]
        ),
        "scope_note": (
            "Scorer chi nhan 12 feature tien treatment f0..f11. Score la diem uu "
            "tien de xep hang, khong phai xac suat conversion ca nhan."
        ),
    }
    (args.output_dir / "champion_scorer.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[write] {path} ({path.stat().st_size / 2**20:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
