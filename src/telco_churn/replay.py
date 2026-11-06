"""Replay a planner evidence packet against a pinned local model bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .api import create_app


def _compare(expected: Any, actual: Any, path: str, differences: list[str]) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            differences.append(path)
            return
        for key in actual.keys() - expected.keys():
            differences.append(f"{path}.{key}:missing_from_packet")
        for key, value in expected.items():
            if key not in actual:
                differences.append(f"{path}.{key}:missing")
            else:
                _compare(value, actual[key], f"{path}.{key}", differences)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            differences.append(f"{path}:length")
            return
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            _compare(left, right, f"{path}[{index}]", differences)
    elif isinstance(expected, Real) and not isinstance(expected, bool):
        if (
            not isinstance(actual, Real)
            or isinstance(actual, bool)
            or not math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-10)
        ):
            differences.append(path)
    elif expected != actual or type(expected) is not type(actual):
        differences.append(path)


def replay_packet(
    packet: dict[str, Any], *, model_path: Path | None = None, bundle: dict | None = None
) -> dict[str, Any]:
    """Recompute a local draft and compare every exported decision field."""

    if not isinstance(packet, dict):
        raise TypeError("Packet must be a JSON object")
    version = packet.get("packet_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported packet version; export a current planner evidence packet")
    records = packet.get("input_records")
    if not isinstance(records, list) or not records:
        raise ValueError("Packet is missing input_records")
    if "assumptions" not in packet:
        raise ValueError("Packet is missing assumptions")
    if not isinstance(packet["assumptions"], dict):
        raise TypeError("Packet assumptions must be an object")
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    observed_digest = hashlib.sha256(encoded).hexdigest()
    differences: list[str] = []
    if observed_digest != packet.get("input_sha256"):
        differences.append("input_sha256")
    if len(records) != packet.get("input_customers"):
        differences.append("input_customers")
    if differences:
        return {"status": "MISMATCH", "differences": differences, "customers": len(records)}

    application = create_app(bundle=bundle, model_path=model_path)
    with TestClient(application) as client:
        response = client.post(
            f"/v{version}/campaigns/preview",
            json={**packet["assumptions"], "records": records},
        )
    if response.status_code != 200:
        return {
            "status": "MISMATCH",
            "differences": [f"api_status:{response.status_code}"],
            "customers": len(records),
        }
    current = response.json()
    fields = (
        "model_version",
        "model_sha256",
        "policy_type",
        "evidence_type",
        "assumption_warning",
        "summary",
        "sensitivity",
        "ranked_candidates",
        "selected",
    ) + (("score_scope_note",) if version == 1 else ("score_scope",))
    for key in fields:
        if key not in packet:
            differences.append(f"{key}:missing_from_packet")
        else:
            _compare(packet[key], current.get(key), key, differences)
    return {
        "status": "MATCH" if not differences else "MISMATCH",
        "differences": differences[:30],
        "customers": len(records),
        "model_version": current["model_version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("artifacts/models/champion.joblib"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        result = replay_packet(packet, model_path=args.model)
    except (OSError, TypeError, ValueError) as error:
        result = {"status": "ERROR", "reason": str(error)}
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
