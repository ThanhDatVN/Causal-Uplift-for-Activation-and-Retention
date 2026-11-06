"""Validate the frozen problem contracts and write a reviewable manifest.

Run as ``python -m telco_churn.problem_contract_cli``.  Loading is the
validation: a contract that violates target-trial alignment, recodes unknown
outcomes as non-events or hides a post-assignment cohort restriction cannot be
constructed at all, so a non-zero exit here means the registry is broken.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .problem_contract import ContractViolation, load_contracts, summarise_contracts

DEFAULT_CONFIG = "configs/problem_contracts.toml"
DEFAULT_OUTPUT = "reports/v4/contracts.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    try:
        contracts = load_contracts(args.config)
    except ContractViolation as error:
        print(f"contract registry rejected: {error}")
        return 1

    summary = summarise_contracts(contracts.values())
    promotable = [row for row in summary if row["promotable"]]
    payload = {
        "config": args.config,
        "n_contracts": len(contracts),
        "n_promotable": len(promotable),
        "contracts": summary,
        "detail": {key: contract.to_dict() for key, contract in contracts.items()},
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"validated {len(contracts)} contract revisions ({len(promotable)} promotable)")
    for row in summary:
        flag = (
            "promotable" if row["promotable"] else f"negative control ({row['cohort_definition']})"
        )
        print(f"  {row['contract_id']}@{row['revision']}: {row['evidence_state']}, {flag}")
    print(f"Manifest: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
