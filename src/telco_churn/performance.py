"""Reproducible HTTP latency benchmark for the prediction endpoint."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from telco_churn.schema import FEATURE_COLUMNS, ID_COLUMN


def benchmark_api(
    url: str,
    data_path: Path,
    *,
    requests: int = 1_000,
    warmup: int = 50,
) -> dict:
    raw = pd.read_csv(data_path, keep_default_na=False)
    record = raw.iloc[0][[ID_COLUMN, *FEATURE_COLUMNS]].to_dict()
    record["SeniorCitizen"] = int(record["SeniorCitizen"])
    record["tenure"] = int(record["tenure"])
    record["MonthlyCharges"] = float(record["MonthlyCharges"])
    record["TotalCharges"] = float(record["TotalCharges"]) if record["TotalCharges"] else None
    payload = {"records": [record]}
    durations = []
    errors = 0
    with httpx.Client(timeout=30) as client:
        first_start = time.perf_counter()
        first_response = client.post(url, json=payload)
        cold_like_ms = (time.perf_counter() - first_start) * 1_000
        first_response.raise_for_status()
        for _ in range(warmup):
            client.post(url, json=payload).raise_for_status()
        start = time.perf_counter()
        for _ in range(requests):
            request_start = time.perf_counter()
            response = client.post(url, json=payload)
            durations.append((time.perf_counter() - request_start) * 1_000)
            errors += int(response.status_code != 200)
        elapsed = time.perf_counter() - start
        batch_latencies = {}
        for size in (100, 1_000):
            batch_start = time.perf_counter()
            response = client.post(url, json={"records": [record] * size})
            batch_latencies[str(size)] = {
                "status_code": response.status_code,
                "latency_ms": (time.perf_counter() - batch_start) * 1_000,
            }
    values = np.asarray(durations)
    return {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "url": url,
        "requests": requests,
        "warmup_requests": warmup,
        "payload_records": 1,
        "cold_like_first_request_ms": cold_like_ms,
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
        "requests_per_second_sequential": requests / elapsed,
        "errors": errors,
        "batch_latency": batch_latencies,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "methodology_note": "Sequential localhost HTTP; not a concurrent load or production SLA test.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/predict")
    parser.add_argument("--data", type=Path, default=Path("data/raw/Telco-Customer-Churn.csv"))
    parser.add_argument("--requests", type=int, default=1_000)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("reports/api/latency.json"))
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    result = benchmark_api(
        arguments.url,
        arguments.data,
        requests=arguments.requests,
        warmup=arguments.warmup,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
