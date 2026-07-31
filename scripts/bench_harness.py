"""
Benchmark harness — do wall time + peak RSS (toan bo process tree) cua 1 script
Python chay trong .venv, boc trong subprocess de moi lan chay hoan toan doc lap
(khong bi anh huong boi rac cua lan chay truoc).

Cach dung:
    .venv/Scripts/python.exe scripts/bench_harness.py \
        --tag bench_causal_forest_frac05 \
        --script benchmarks/bench_causal_forest.py \
        -- --frac 0.05 --n-estimators 500

Ghi 1 dong vao benchmarks/results.csv moi lan chay, va log stdout/stderr day du
vao benchmarks/logs/<tag>.log de debug khi co loi.
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
RESULTS_CSV = ROOT / "benchmarks" / "results.csv"
LOG_DIR = ROOT / "benchmarks" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "timestamp", "tag", "script", "args", "exit_code",
    "wall_time_s", "peak_rss_mb", "poll_samples", "log_file",
]


def tree_rss_mb(proc: psutil.Process) -> float:
    """RSS cong don cua process chinh + toan bo tien trinh con (vd: worker cua joblib/loky)."""
    total = 0
    try:
        total += proc.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0
    try:
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return total / (1024 ** 2)


def run(tag: str, script: str, extra_args: list, poll_interval: float = 0.2) -> dict:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    cmd = [str(venv_python), script] + extra_args
    log_file = LOG_DIR / f"{tag}.log"

    print(f">>> [{tag}] chay: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    peak_mb = 0.0
    samples = 0
    with open(log_file, "w", encoding="utf-8") as logf:
        popen = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=str(ROOT))
        try:
            proc = psutil.Process(popen.pid)
        except psutil.NoSuchProcess:
            proc = None
        while popen.poll() is None:
            if proc is not None:
                peak_mb = max(peak_mb, tree_rss_mb(proc))
            samples += 1
            time.sleep(poll_interval)
        exit_code = popen.wait()

    wall = time.time() - t0

    row = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tag": tag,
        "script": script,
        "args": " ".join(extra_args),
        "exit_code": exit_code,
        "wall_time_s": round(wall, 2),
        "peak_rss_mb": round(peak_mb, 1),
        "poll_samples": samples,
        "log_file": str(log_file.relative_to(ROOT)).replace("\\", "/"),
    }

    write_header = not RESULTS_CSV.exists()
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    status = "OK" if exit_code == 0 else f"LOI (exit={exit_code})"
    print(
        f"<<< [{tag}] {status}  wall={wall:.1f}s  peak_rss={peak_mb:.0f}MB  "
        f"log={row['log_file']}",
        flush=True,
    )
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sargs = args.script_args
    if sargs and sargs[0] == "--":
        sargs = sargs[1:]
    row = run(args.tag, args.script, sargs, args.interval)
    sys.exit(0 if row["exit_code"] == 0 else 1)
