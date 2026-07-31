"""Ngoại suy resource CausalForestDML từ benchmark đã đo.

Kết quả là feasibility estimate, không phải bảo đảm của Kaggle.

Chạy:
    python scripts/assess_causal_forest_feasibility.py \
        --target-frac 0.50 --target-ram-gb 30 --target-cpus 4
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "benchmarks" / "results.csv"
OUTPUT_PATH = REPO_ROOT / "output" / "sprint1" / "causal_forest_feasibility.json"


def _fraction(command_args: str) -> float:
    match = re.search(r"--frac\s+([0-9.]+)", command_args)
    if not match:
        raise ValueError(f"Không đọc được --frac từ: {command_args}")
    return float(match.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-frac", type=float, default=0.50)
    parser.add_argument("--target-ram-gb", type=float, default=30.0)
    parser.add_argument("--target-cpus", type=int, default=4)
    parser.add_argument("--local-cpus", type=int, default=12)
    parser.add_argument("--max-ram-utilization", type=float, default=0.75)
    args = parser.parse_args()

    frame = pd.read_csv(RESULTS_PATH)
    frame = frame[
        frame["tag"].str.startswith("bench_cf_frac_") & (frame["exit_code"] == 0)
    ].copy()
    frame["fraction"] = frame["args"].map(_fraction)
    frame = frame.sort_values("fraction")
    if len(frame) < 3:
        raise ValueError("Cần ít nhất 3 benchmark Causal Forest thành công")

    memory_coeff = np.polyfit(frame["fraction"], frame["peak_rss_mb"], deg=1)
    time_coeff = np.polyfit(frame["fraction"], frame["wall_time_s"], deg=1)
    predicted_memory_mb = float(np.polyval(memory_coeff, args.target_frac))
    predicted_local_seconds = float(np.polyval(time_coeff, args.target_frac))

    # 24 GB is the earlier conservative envelope. Keep it as a guard rather
    # than reporting only the optimistic linear fit.
    conservative_memory_gb = max(predicted_memory_mb / 1024, 24.0)
    target_cpu_seconds = predicted_local_seconds * max(
        1.0, args.local_cpus / args.target_cpus
    )
    ram_limit_gb = args.target_ram_gb * args.max_ram_utilization
    target_meets_research_envelope = conservative_memory_gb <= ram_limit_gb
    minimum_ram_for_envelope_gb = (
        conservative_memory_gb / args.max_ram_utilization
    )

    report = {
        "evidence": frame[
            ["fraction", "wall_time_s", "peak_rss_mb", "args", "log_file"]
        ].to_dict(orient="records"),
        "target": {
            "fraction": args.target_frac,
            "system_ram_gb": args.target_ram_gb,
            "cpu_count": args.target_cpus,
            "max_ram_utilization": args.max_ram_utilization,
        },
        "research_profile_500_trees_extrapolation": {
            "linear_memory_gb": predicted_memory_mb / 1024,
            "conservative_memory_gb": conservative_memory_gb,
            "local_runtime_hours": predicted_local_seconds / 3600,
            "cpu_scaled_runtime_hours": target_cpu_seconds / 3600,
        },
        "decision": {
            "status": "preflight_required",
            "reason": (
                "50% chưa được duyệt. Research-profile envelope cần tối thiểu "
                f"{minimum_ram_for_envelope_gb:.1f} GB để giữ peak dưới "
                f"{args.max_ram_utilization:.0%}; target giả định "
                f"{args.target_ram_gb:.1f} GB "
                f"{'đạt' if target_meets_research_envelope else 'không đạt'} gate. "
                "Profile kaggle-safe phải benchmark live ở 20% và 30%; GPU không "
                "được sử dụng."
            ),
            "target_meets_research_profile_envelope": target_meets_research_envelope,
            "minimum_system_ram_for_research_envelope_gb": minimum_ram_for_envelope_gb,
            "recommended_profile": "kaggle-safe",
            "required_preflights": [0.20, 0.30],
            "fallback": (
                "Phát hành 5 model local; hoãn Causal Forest hoặc giảm forest profile. "
                "Không đổi common holdout chỉ để ép đủ model thứ sáu."
            ),
        },
        "limitations": [
            "Benchmark mới đo đến 20%; 50% là ngoại suy.",
            "CPU scaling có thể lệch khỏi giả định tuyến tính.",
            "Tài nguyên Kaggle có thể thay đổi; phải đọc RAM/CPU live trước khi chạy.",
            "Profile kaggle-safe 200 cây cần benchmark riêng ở 20% và 30%.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    print(f"[write] {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
